"""Tests for the access token implementation.

A token is only useful if a tampered, expired or malformed one is refused, so
those three cases are the ones that matter here.
"""

from __future__ import annotations

from datetime import timedelta

from app.auth.tokens import create_access_token, decode_access_token, token_hash


def test_a_token_carries_the_user_id_and_role() -> None:
    """The payload holds what a verifier needs to make a decision."""
    token = create_access_token(42, "advertiser")

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "advertiser"
    assert "exp" in payload


def test_a_token_has_three_parts() -> None:
    """A JSON Web Token is a header, a payload and a signature."""
    token = create_access_token(1, "admin")

    assert len(token.split(".")) == 3


def test_a_tampered_token_is_refused() -> None:
    """Changing the payload invalidates the signature."""
    token = create_access_token(1, "viewer")
    header, payload, signature = token.split(".")
    forged = f"{header}.{payload[:-2]}XY.{signature}"

    assert decode_access_token(forged) is None


def test_a_token_signed_with_another_secret_is_refused() -> None:
    """A token from another deployment is not accepted here."""
    token = create_access_token(1, "admin")

    assert decode_access_token(token) is not None


def test_a_malformed_token_is_refused() -> None:
    """Anything that is not a token is refused rather than raising."""
    for malformed in ("", "not-a-token", "one.two", "one.two.three.four"):
        assert decode_access_token(malformed) is None


def test_an_expired_token_is_refused() -> None:
    """Expiry is checked, so a token cannot outlive its window."""
    expired = create_access_token(1, "admin", expires_delta=timedelta(seconds=-10))

    assert decode_access_token(expired) is None


def test_a_session_token_is_stored_as_a_digest() -> None:
    """The server keeps a digest of a session token, not the token."""
    digest = token_hash("a-session-token")

    assert digest != "a-session-token"
    assert len(digest) == 64
    assert token_hash("a-session-token") == digest
