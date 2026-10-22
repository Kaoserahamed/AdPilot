"""Request-scoped identity: who is calling, and what they may do.

Authentication accepts three credentials, checked in that order:

1. A **session cookie**, issued at login and stored server-side as a hash.
2. An **API key**, presented in ``Authorization: Api-Key``, in
   ``Authorization: Bearer`` or in ``X-API-Key``.
3. An **access token**, presented in ``Authorization: Bearer``.

A session and an API key identify a user; an access token carries the user id
and the role in its signed payload, so it is trusted without a database round
trip. The role is what authorization is decided from, and it is always the
role the account holds — a token cannot elevate it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, Response, status

from app.auth.models import DEFAULT_ROLE
from app.auth.passwords import verify_api_key
from app.auth.tokens import decode_access_token, token_hash
from app.core import get_connection as _database
from app.core import settings


def now_iso() -> str:
    """Return the current time in the format the database stores."""
    return datetime.now(UTC).isoformat()


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie to a response.

    The cookie is HTTP-only, so script cannot read it, and is marked secure
    outside development, so it is not sent over plain HTTP in production.
    """
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


def user_for_session(token: str | None) -> sqlite3.Row | None:
    """Return the account a session token belongs to, or ``None``."""
    if not token:
        return None
    with _database() as connection:
        return connection.execute(
            """SELECT u.id, u.name, u.email, u.role FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > ?""",
            (token_hash(token), now_iso()),
        ).fetchone()


def current_user(session_token: str | None) -> sqlite3.Row:
    """Return the account behind a session token, or refuse the request."""
    user = user_for_session(session_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def extract_api_key(authorization: str | None, x_api_key: str | None) -> str | None:
    """Return the API key carried by a request, if there is one."""
    if x_api_key:
        return x_api_key
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() in {"apikey", "api-key", "bearer"}:
            return parts[1]
    return None


def user_for_api_key(key: str) -> dict[str, object] | None:
    """Return the account an API key belongs to, or ``None``.

    A revoked or expired key never matches, and the comparison against each
    candidate hash is constant time.
    """
    with _database() as connection:
        rows = connection.execute(
            """SELECT u.id, u.name, u.email, u.role, k.key_hash
               FROM api_keys k
               JOIN users u ON u.id = k.user_id
               WHERE k.revoked_at IS NULL AND (k.expires_at IS NULL OR k.expires_at > ?)""",
            (now_iso(),),
        ).fetchall()
    for row in rows:
        if verify_api_key(key, row["key_hash"]):
            return {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}
    return None


def user_for_access_token(token: str) -> dict[str, object] | None:
    """Return the account an access token was issued for, or ``None``.

    The role comes from the token's signed payload, which is trusted because
    the signature was verified. The account is still read back, so a token for
    an account that has since been deleted stops working.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    subject = payload.get("sub")
    if subject is None:
        return None
    with _database() as connection:
        row = connection.execute(
            "SELECT id, name, email, role FROM users WHERE id = ?",
            (int(subject),),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": payload.get("role", row["role"]) or DEFAULT_ROLE,
    }


def authenticated_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> sqlite3.Row | dict[str, object]:
    """Return the account behind a request, or refuse the request.

    The credential is tried as a session first, then as an API key, then as an
    access token. A bearer header is ambiguous — it may carry either an API
    key or an access token — so both are attempted.
    """
    session_user = user_for_session(session_token)
    if session_user:
        return session_user

    key = extract_api_key(authorization, x_api_key)
    if key:
        api_user = user_for_api_key(key)
        if api_user:
            return api_user
        token_user = user_for_access_token(key)
        if token_user:
            return token_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_role(
    *allowed_roles: str,
) -> Callable[[sqlite3.Row | dict[str, object]], sqlite3.Row | dict[str, object]]:
    """Return a dependency that admits only the listed roles.

    The check is on the role the account holds, so it is the same answer
    whether the caller authenticated with a session, an API key or an access
    token.
    """

    def dependency(
        user: sqlite3.Row | dict[str, object] = Depends(authenticated_user),
    ) -> sqlite3.Row | dict[str, object]:
        # A row and a dict raise different errors for a missing key, and an
        # account with no role at all must be refused rather than crash.
        try:
            role = user["role"]
        except (KeyError, IndexError):
            role = None
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return dependency
