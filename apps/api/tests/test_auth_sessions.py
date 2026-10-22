"""Tests for the request-scoped identity and the role check.

These are the tests that pin the authorization rule: a role is a property of
the account, and every credential type resolves to the same answer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import create_access_token, decode_access_token
from app.auth.sessions import require_role
from app.main import app


@pytest.fixture()
def auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a client with an isolated authentication database."""
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "auth.db"))
    with TestClient(app) as client:
        yield client


def _register(client: TestClient, role: str = "advertiser") -> dict[str, object]:
    """Register an account, then end its session.

    The session is ended so that the credential under test is the only one the
    request carries. A session takes priority over a header, and a test that
    meant to exercise an API key would otherwise pass on the cookie.
    """
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alex Morgan",
            "email": "alex@example.com",
            "password": "correct-horse-battery",
            "role": role,
        },
    )
    assert response.status_code == 201
    account = response.json()
    client.post("/api/v1/auth/logout")
    return account


def test_a_session_authenticates_a_request(auth_client: TestClient) -> None:
    """The cookie issued at login identifies the account."""
    auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": "alex@example.com", "password": "correct-horse-battery"},
    )

    response = auth_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "alex@example.com"


def test_an_api_key_authenticates_a_request(auth_client: TestClient) -> None:
    """A key presented in the Authorization header identifies the account."""
    account = _register(auth_client)
    auth_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})
    created = auth_client.post("/api/v1/auth/api-keys", json={"name": "ci"})
    key = created.json()["key"]
    auth_client.post("/api/v1/auth/logout")

    response = auth_client.post("/api/v1/auth/token", headers={"Authorization": f"Api-Key {key}"})

    assert response.status_code == 200
    issued = decode_access_token(response.json()["access_token"])
    assert issued is not None
    assert issued["sub"] == str(account["id"])


def test_an_api_key_works_in_the_x_api_key_header(auth_client: TestClient) -> None:
    """The dedicated header is accepted as well."""
    _register(auth_client)
    auth_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})
    created = auth_client.post("/api/v1/auth/api-keys", json={"name": "ci"})
    key = created.json()["key"]
    auth_client.post("/api/v1/auth/logout")

    response = auth_client.post("/api/v1/auth/token", headers={"X-API-Key": key})

    assert response.status_code == 200


def test_a_wrong_api_key_is_refused(auth_client: TestClient) -> None:
    """A key that was never issued does not authenticate."""
    _register(auth_client)

    response = auth_client.post(
        "/api/v1/auth/token",
        headers={"Authorization": "Api-Key not-a-real-key"},
    )

    assert response.status_code == 401


def test_a_revoked_api_key_stops_working(auth_client: TestClient) -> None:
    """Revoking a key takes effect on the next request."""
    _register(auth_client)
    auth_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})
    created = auth_client.post("/api/v1/auth/api-keys", json={"name": "ci"})
    key = created.json()["key"]
    auth_client.delete(f"/api/v1/auth/api-keys/{created.json()['id']}")
    auth_client.post("/api/v1/auth/logout")

    response = auth_client.post("/api/v1/auth/token", headers={"Authorization": f"Api-Key {key}"})

    assert response.status_code == 401


def test_an_access_token_authenticates_a_request(auth_client: TestClient) -> None:
    """An access token identifies the account without a session."""
    account = _register(auth_client)
    token = create_access_token(int(account["id"]), str(account["role"]))

    response = auth_client.post("/api/v1/auth/token", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    issued = decode_access_token(response.json()["access_token"])
    assert issued is not None
    assert issued["sub"] == str(account["id"])


def test_a_tampered_token_is_refused(auth_client: TestClient) -> None:
    """A token whose signature does not match is refused."""
    account = _register(auth_client)
    token = create_access_token(int(account["id"]), str(account["role"]))
    tampered = token[:-4] + "AAAA"

    response = auth_client.post("/api/v1/auth/token", headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401


def test_the_role_check_admits_a_permitted_role() -> None:
    """A role inside the permitted set passes through."""
    dependency = require_role("admin")
    user = {"role": "admin"}

    assert dependency(user=user) is user


def test_the_role_check_refuses_a_role_outside_the_set() -> None:
    """A role outside the permitted set is refused with a 403."""
    dependency = require_role("admin")

    with pytest.raises(HTTPException) as refusal:
        dependency(user={"role": "advertiser"})

    assert refusal.value.status_code == 403
    assert refusal.value.detail == "Insufficient role"


def test_the_role_check_refuses_an_account_with_no_role() -> None:
    """An account with no role at all is refused rather than allowed."""
    dependency = require_role("advertiser")

    with pytest.raises(HTTPException) as refusal:
        dependency(user={})

    assert refusal.value.status_code == 403


def test_an_api_key_reaches_a_service_endpoint(auth_client: TestClient) -> None:
    """A key is for programmatic access, so it works outside the auth routes."""
    _register(auth_client)
    auth_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})
    created = auth_client.post("/api/v1/auth/api-keys", json={"name": "ci"})
    key = created.json()["key"]
    auth_client.post("/api/v1/auth/logout")

    response = auth_client.get("/api/v1/campaigns", headers={"Authorization": f"Api-Key {key}"})

    assert response.status_code == 200


def test_a_permitted_role_may_change_a_campaign(auth_client: TestClient) -> None:
    """A role inside the permitted set may change a campaign."""
    _register(auth_client, role="advertiser")
    auth_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})

    response = auth_client.post(
        "/api/v1/campaigns",
        json={
            "name": "Spring sale",
            "product": "Shoes",
            "description": "The very best shoes",
            "objective": "traffic",
            "location": "New York",
            "audience": "Everyone",
            "budget": 100,
            "duration_days": 7,
            "landing_page": "https://example.com",
            "tone": "friendly",
            "offer": "10% off",
            "platforms": ["Meta"],
        },
    )

    assert response.status_code == 201
