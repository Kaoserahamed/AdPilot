from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import decode_access_token, hash_password
from app.main import app


@pytest.fixture()
def auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "auth.db"))
    with TestClient(app) as client:
        yield client


def test_password_hash_is_not_plaintext() -> None:
    encoded = hash_password("correct horse battery staple")

    assert "correct horse battery staple" not in encoded
    assert encoded.startswith("scrypt$")


def test_register_login_and_current_user(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": "alex@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "alex@example.com"
    assert "adpilot_session" in response.cookies
    assert auth_client.get("/api/v1/auth/me").json()["name"] == "Alex Morgan"

    logout = auth_client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert auth_client.get("/api/v1/auth/me").status_code == 401


def test_invalid_credentials_are_generic(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": "alex@example.com", "password": "correct-horse-battery"},
    )
    auth_client.post("/api/v1/auth/logout")

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "alex@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_protected_current_user_requires_session(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/auth/me").status_code == 401


@pytest.fixture()
def logged_in_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "auth.db"))
    client = TestClient(app)
    client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": "alex@example.com", "password": "correct-horse-battery"},
    )
    client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})
    return client


def test_register_assigns_default_advertiser_role(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": "alex@example.com", "password": "correct-horse-battery"},
    )
    auth_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"})
    assert auth_client.get("/api/v1/auth/me").json()["role"] == "advertiser"


def test_register_accepts_publisher_role(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Pat Lee", "email": "pat@example.com", "password": "correct-horse-battery", "role": "publisher"},
    )
    auth_client.post("/api/v1/auth/login", json={"email": "pat@example.com", "password": "correct-horse-battery"})
    assert auth_client.get("/api/v1/auth/me").json()["role"] == "publisher"


def test_register_rejects_invalid_role(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Bad", "email": "bad@example.com", "password": "correct-horse-battery", "role": "owner"},
    )
    assert response.status_code == 422


def test_api_key_crud(logged_in_client: TestClient) -> None:
    created = logged_in_client.post("/api/v1/auth/api-keys", json={"name": "Campaign key"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Campaign key"
    assert body["key"] and body["prefix"] == body["key"][:8]
    key_id = body["id"]

    listed = logged_in_client.get("/api/v1/auth/api-keys")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == key_id
    assert "key" not in listed.json()[0]

    revoked = logged_in_client.delete(f"/api/v1/auth/api-keys/{key_id}")
    assert revoked.status_code == 204

    listed_again = logged_in_client.get("/api/v1/auth/api-keys")
    assert listed_again.status_code == 200
    assert listed_again.json() == []


def test_api_key_authenticates_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "apikey.db"))
    owner = TestClient(app)
    owner.post(
        "/api/v1/auth/register",
        json={"name": "Owner", "email": "owner@example.com", "password": "correct-horse-battery"},
    )
    owner.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse-battery"})
    created = owner.post("/api/v1/auth/api-keys", json={"name": "API key"})
    api_key = created.json()["key"]

    client = TestClient(app)
    listed = client.get("/api/v1/auth/api-keys", headers={"Authorization": f"Api-Key {api_key}"})
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    bad = client.get("/api/v1/auth/api-keys", headers={"Authorization": "Api-Key wrong-key"})
    assert bad.status_code == 401


def test_issue_and_decode_jwt(logged_in_client: TestClient) -> None:
    issued = logged_in_client.post("/api/v1/auth/token")
    assert issued.status_code == 200
    assert issued.json()["token_type"] == "bearer"

    payload = decode_access_token(issued.json()["access_token"])
    assert payload is not None
    assert payload["role"] == "advertiser"

    assert decode_access_token("not-a-token") is None


def test_oauth2_authorize_and_callback(logged_in_client: TestClient) -> None:
    authorize = logged_in_client.get(
        "/api/v1/auth/oauth2/authorize",
        params={"client_id": "sandbox-client", "redirect_uri": "https://example.com/callback"},
    )
    assert authorize.status_code == 200
    code = authorize.json()["code"]

    callback = logged_in_client.post(
        "/api/v1/auth/oauth2/callback",
        params={"code": code, "redirect_uri": "https://example.com/callback"},
    )
    assert callback.status_code == 200
    payload = decode_access_token(callback.json()["access_token"])
    assert payload is not None
    assert payload["role"] == "advertiser"

    replay = logged_in_client.post(
        "/api/v1/auth/oauth2/callback",
        params={"code": code, "redirect_uri": "https://example.com/callback"},
    )
    assert replay.status_code == 400


def test_oauth2_authorize_requires_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "oauth.db"))
    client = TestClient(app)
    response = client.get(
        "/api/v1/auth/oauth2/authorize",
        params={"client_id": "sandbox-client", "redirect_uri": "https://example.com/callback"},
    )
    assert response.status_code == 401
