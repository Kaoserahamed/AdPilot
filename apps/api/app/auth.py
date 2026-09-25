import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

from .config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class RegisterRequest(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=80)]
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address")
        return normalized


class LoginRequest(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class PasswordResetRequest(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]


class PasswordResetConfirm(BaseModel):
    token: Annotated[str, Field(min_length=20, max_length=200)]
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserResponse(BaseModel):
    id: int
    name: str
    email: str


def _database() -> sqlite3.Connection:
    path = Path(settings.auth_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            );
            """
        )


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response) -> UserResponse:
    init_db()
    with _database() as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (payload.name.strip(), payload.email, hash_password(payload.password), datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from error
        user = connection.execute("SELECT id, name, email FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    token = secrets.token_urlsafe(48)
    with _database() as connection:
        connection.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], _token_hash(token), (datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days)).isoformat(), datetime.now(timezone.utc).isoformat()),
        )
    _set_session_cookie(response, token)
    return UserResponse(**dict(user))


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response) -> UserResponse:
    init_db()
    with _database() as connection:
        user = connection.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (payload.email.strip().lower(),)).fetchone()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = secrets.token_urlsafe(48)
    with _database() as connection:
        connection.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], _token_hash(token), (datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days)).isoformat(), datetime.now(timezone.utc).isoformat()),
        )
    _set_session_cookie(response, token)
    return UserResponse(id=user["id"], name=user["name"], email=user["email"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)) -> None:
    if session_token:
        with _database() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(session_token),))
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserResponse)
def me(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)) -> UserResponse:
    return UserResponse(**dict(_current_user(session_token)))


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest) -> dict[str, str]:
    init_db()
    with _database() as connection:
        user = connection.execute("SELECT id FROM users WHERE email = ?", (payload.email.strip().lower(),)).fetchone()
        if user:
            token = secrets.token_urlsafe(48)
            connection.execute(
                "INSERT INTO password_resets (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (user["id"], _token_hash(token), (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(), datetime.now(timezone.utc).isoformat()),
            )
    return {"message": "If an account exists, password reset instructions have been sent."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm) -> None:
    init_db()
    with _database() as connection:
        reset = connection.execute(
            "SELECT id, user_id FROM password_resets WHERE token_hash = ? AND expires_at > ? AND used_at IS NULL",
            (_token_hash(payload.token), datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        if reset is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is invalid or expired")
        connection.execute("UPDATE password_resets SET used_at = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), reset["id"]))
        connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.password), reset["user_id"]))
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (reset["user_id"],))



def _user_for_token(token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    with _database() as connection:
        return connection.execute(
            """SELECT u.id, u.name, u.email FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > ?""",
            (_token_hash(token), datetime.now(timezone.utc).isoformat()),
        ).fetchone()


def _current_user(session_token: str | None) -> sqlite3.Row:
    user = _user_for_token(session_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user
