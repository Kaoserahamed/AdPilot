from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
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
