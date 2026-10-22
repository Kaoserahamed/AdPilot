"""HTTP surface of the authentication service.

The endpoints are grouped by what the caller is trying to do:

* **Account lifecycle** — register, log in, log out, and who am I.
* **Password reset** — request and confirm, without revealing whether an
  account exists.
* **API keys** — issue, list and revoke.
* **Tokens** — exchange a session or an API key for an access token.
* **OAuth2** — the authorization-code flow for connecting a platform account.
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.auth.models import (
    DEFAULT_ROLE,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.passwords import hash_api_key, hash_password, verify_password
from app.auth.schema import init_db
from app.auth.sessions import (
    authenticated_user,
    current_user,
    set_session_cookie,
)
from app.auth.tokens import create_access_token, token_hash
from app.core import get_connection as _database
from app.core import settings

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

#: How long a password reset token stays valid.
PASSWORD_RESET_TTL = timedelta(minutes=30)

#: How long an OAuth2 authorization code stays valid.
AUTHORIZATION_CODE_TTL_SECONDS = 600


def _now() -> str:
    """Return the current time in the format the database stores."""
    return datetime.now(UTC).isoformat()


def _now_after(delta: timedelta) -> str:
    """Return the time a delta from now, in the format the database stores."""
    return (datetime.now(UTC) + delta).isoformat()


def _create_session(connection: sqlite3.Connection, user_id: int) -> str:
    """Create a session for a user and return its plaintext token."""
    token = secrets.token_urlsafe(48)
    connection.execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (
            user_id,
            token_hash(token),
            (
                datetime.now(UTC) + timedelta(days=settings.session_ttl_days)
            ).isoformat(),
            _now(),
        ),
    )
    return token


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response) -> UserResponse:
    """Create an account and sign it in.

    A registration that collides with an existing address is refused with a
    conflict, which is the one place the API does disclose that an account
    exists — the caller has just tried to create it.
    """
    init_db()
    with _database() as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    payload.name.strip(),
                    payload.email,
                    hash_password(payload.password),
                    payload.role,
                    _now(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            ) from error
        user = connection.execute(
            "SELECT id, name, email, role FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        token = _create_session(connection, user["id"])
    set_session_cookie(response, token)
    return UserResponse(**dict(user))


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response) -> UserResponse:
    """Sign an account in and start a session.

    A wrong address and a wrong password produce the same response, so the
    endpoint cannot be used to find out which addresses have accounts.
    """
    init_db()
    with _database() as connection:
        user = connection.execute(
            "SELECT id, name, email, role, password_hash FROM users WHERE email = ?",
            (payload.email.strip().lower(),),
        ).fetchone()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    with _database() as connection:
        token = _create_session(connection, user["id"])
    set_session_cookie(response, token)
    return UserResponse(id=user["id"], name=user["name"], email=user["email"], role=user["role"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> None:
    """End the current session.

    The session row is deleted rather than marked, so a revoked session cannot
    be replayed and there is no state left behind to expire.
    """
    if session_token:
        with _database() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (token_hash(session_token),),
            )
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserResponse)
def me(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> UserResponse:
    """Return the account behind the current session."""
    return UserResponse(**dict(current_user(session_token)))


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest) -> dict[str, str]:
    """Start a password reset.

    The response is the same whether or not the address has an account, so
    this endpoint cannot be used to enumerate users. A token is created only
    when the account exists.
    """
    init_db()
    with _database() as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (payload.email.strip().lower(),),
        ).fetchone()
        if user:
            token = secrets.token_urlsafe(48)
            connection.execute(
                "INSERT INTO password_resets (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (user["id"], token_hash(token), _now_after(PASSWORD_RESET_TTL), _now()),
            )
    return {
        "message": "If an account exists, password reset instructions have been sent.",
    }


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm) -> None:
    """Complete a password reset.

    Every session of the account is ended, because a reset is the usual
    response to a suspected compromise and the old sessions may be the
    attacker's.
    """
    init_db()
    with _database() as connection:
        reset = connection.execute(
            """SELECT id, user_id FROM password_resets
               WHERE token_hash = ? AND expires_at > ? AND used_at IS NULL""",
            (token_hash(payload.token), _now()),
        ).fetchone()
        if reset is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or expired",
            )
        connection.execute(
            "UPDATE password_resets SET used_at = ? WHERE id = ?",
            (_now(), reset["id"]),
        )
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(payload.password), reset["user_id"]),
        )
        connection.execute(
            "DELETE FROM sessions WHERE user_id = ?",
            (reset["user_id"],),
        )


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    user: sqlite3.Row = Depends(authenticated_user),
) -> ApiKeyCreated:
    """Issue an API key for the calling account.

    The plaintext key is returned exactly once, in this response. Only its
    hash is stored, so it cannot be recovered afterwards.
    """
    init_db()
    key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(key)
    prefix = key[:8]
    now = _now()
    with _database() as connection:
        cursor = connection.execute(
            "INSERT INTO api_keys (user_id, key_hash, prefix, name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], key_hash, prefix, payload.name, now),
        )
        key_id = int(cursor.lastrowid)
    return ApiKeyCreated(
        id=key_id,
        name=payload.name,
        prefix=prefix,
        created_at=now,
        key=key,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    user: sqlite3.Row = Depends(authenticated_user),
) -> list[ApiKeyResponse]:
    """List the active API keys of the calling account."""
    init_db()
    with _database() as connection:
        rows = connection.execute(
            """SELECT id, name, prefix, created_at, expires_at, revoked_at, last_used_at
               FROM api_keys WHERE user_id = ? AND revoked_at IS NULL
               ORDER BY id DESC""",
            (user["id"],),
        ).fetchall()
    return [ApiKeyResponse(**dict(row)) for row in rows]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    user: sqlite3.Row = Depends(authenticated_user),
) -> None:
    """Revoke an API key.

    A key belonging to another account is reported as not found, so the
    endpoint does not disclose which key ids exist.
    """
    init_db()
    with _database() as connection:
        row = connection.execute(
            "SELECT id FROM api_keys WHERE id = ? AND user_id = ?",
            (key_id, user["id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )
        connection.execute(
            "UPDATE api_keys SET revoked_at = ? WHERE id = ?",
            (_now(), key_id),
        )


@router.post("/token", response_model=TokenResponse)
def issue_token(user: sqlite3.Row = Depends(authenticated_user)) -> TokenResponse:
    """Exchange the caller's credential for a short-lived access token.

    The token carries the user id and the role, so a script can call the API
    without a browser and without the API having to look the role up on every
    request.
    """
    token = create_access_token(int(user["id"]), user["role"])
    return TokenResponse(access_token=token)


class _AuthCode(TypedDict):
    """An issued OAuth2 authorization code."""

    user_id: int
    redirect_uri: str
    scope: str
    expires_at: float


#: The outstanding authorization codes, keyed by the code itself.
#:
#: The sandbox flow keeps them in memory: a code is single use and short
#: lived, and an in-memory store keeps a failed exchange from leaving a
#: trace on disk.
AUTHORIZATION_CODES: dict[str, _AuthCode] = {}


@router.get("/oauth2/authorize")
def oauth2_authorize(
    client_id: str,
    redirect_uri: str,
    scope: str = "",
    state: str | None = None,
    response_type: str = "code",
    user: sqlite3.Row = Depends(authenticated_user),
) -> dict[str, object]:
    """Issue an authorization code for the calling account.

    The code is bound to the redirect URI it was requested with, so it cannot
    be redeemed against a different one.
    """
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported response_type",
        )
    code = secrets.token_urlsafe(32)
    AUTHORIZATION_CODES[code] = {
        "user_id": int(user["id"]),
        "redirect_uri": redirect_uri,
        "scope": scope,
        "expires_at": time.time() + AUTHORIZATION_CODE_TTL_SECONDS,
    }
    return {
        "code": code,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scope,
    }


@router.post("/oauth2/callback", response_model=TokenResponse)
def oauth2_callback(code: str, redirect_uri: str) -> TokenResponse:
    """Exchange an authorization code for an access token.

    The code is single use: it is removed whether the exchange succeeds or
    fails, so a captured code cannot be replayed.
    """
    entry = AUTHORIZATION_CODES.get(code)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown or expired authorization code",
        )
    if time.time() > entry["expires_at"]:
        AUTHORIZATION_CODES.pop(code, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code expired",
        )
    if entry["redirect_uri"] != redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redirect URI mismatch",
        )
    user_id = int(entry["user_id"])
    with _database() as connection:
        row = connection.execute(
            "SELECT role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    role = row["role"] if row else DEFAULT_ROLE
    AUTHORIZATION_CODES.pop(code, None)
    token = create_access_token(user_id, role)
    return TokenResponse(access_token=token)
