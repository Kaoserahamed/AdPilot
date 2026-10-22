"""Session tokens and JSON Web Tokens.

Two kinds of token are issued, and they are used for different things:

* A **session token** is high-entropy random material handed to the browser in
  an HTTP-only cookie. The server stores only its SHA-256 digest, so a
  database dump does not yield a usable session.
* An **access token** is a short-lived HS256 JSON Web Token carrying the user
  id and the role. It is what a script uses to call the API without a
  browser, and it is verified by signature and expiry on every request.

The signing secret comes from the environment, so a deployment that forgets to
set it is obvious rather than silently signing tokens with a default.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta

from app.core import settings


def token_hash(token: str) -> str:
    """Return the digest stored for a session token.

    A session token is 384 bits of randomness, so a fast digest is the right
    choice: brute-forcing it is hopeless and a slow function would only add
    latency to every request.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def _b64url(data: bytes) -> str:
    """Encode bytes as unpadded base64url."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Decode unpadded base64url back to bytes."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user_id: int, role: str, expires_delta: timedelta | None = None) -> str:
    """Return a signed HS256 access token for a user.

    The token carries the user id as ``sub`` and the account's role, so a
    verifier can make an authorization decision without a database round trip.
    """
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        settings.jwt_secret.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url(signature)}"


def decode_access_token(token: str) -> dict[str, object] | None:
    """Return the payload of a valid access token, or ``None``.

    ``None`` covers every failure — a malformed token, a bad signature and an
    expired token alike. The caller learns only that the token is not usable,
    never which of the three it was.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        signature = _b64url_decode(parts[2])
        expected = hmac.new(
            settings.jwt_secret.encode(),
            signing_input,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64url_decode(parts[1]))
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None
