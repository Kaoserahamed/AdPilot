import base64
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platforms import MetaAdapter, GoogleAdsAdapter, _decrypt_token, _encrypt_token


@pytest.fixture()
def platform_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "platforms.db"))
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json={"name": "Platform Owner", "email": "platform@example.com", "password": "correct-horse-battery"}).status_code == 201
        yield client


def test_adapter_contract_and_capabilities(platform_client: TestClient) -> None:
    response = platform_client.get("/api/v1/platforms")
    assert response.status_code == 200
    platforms = {item["platform"]: item for item in response.json()}
    assert set(platforms) == {"meta", "google", "youtube"}
    assert platforms["meta"]["supports_oauth"] is True
    assert platforms["meta"]["sandbox"] is True
    assert MetaAdapter().get_metrics("external-id")["source"] == "sandbox"
    assert GoogleAdsAdapter().publish_campaign("external-id")["status"] == "PENDING_REVIEW"
    assert GoogleAdsAdapter().pause_campaign("external-id")["status"] == "PAUSED"


def test_connect_and_disconnect_sandbox_account(platform_client: TestClient) -> None:
    connected = platform_client.post("/api/v1/platforms/accounts/connect", json={"platform": "meta", "account_name": "Growth sandbox"})
    assert connected.status_code == 201
    account = connected.json()
    assert account["platform"] == "meta"
    assert account["sandbox"] is True
    assert "access_token" not in account

    listed = platform_client.get("/api/v1/platforms/accounts")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [account["id"]]
    assert platform_client.get("/api/v1/platforms").json()[0]["connected"] is True
    assert platform_client.delete(f"/api/v1/platforms/accounts/{account['id']}").status_code == 204
    assert platform_client.get("/api/v1/platforms/accounts").json() == []


def test_access_token_is_encrypted_at_rest(platform_client: TestClient, tmp_path: Path) -> None:
    platform_client.post("/api/v1/platforms/accounts/connect", json={"platform": "google"})
    with sqlite3.connect(tmp_path / "platforms.db") as connection:
        stored = connection.execute("SELECT access_token_encrypted FROM connected_accounts").fetchone()[0]
    assert "sandbox-token" not in stored
    assert _decrypt_token(stored).startswith("sandbox-token")
    assert _decrypt_token(_encrypt_token("secret")) == "secret"


def test_platform_account_ownership_is_enforced(platform_client: TestClient) -> None:
    account_id = platform_client.post("/api/v1/platforms/accounts/connect", json={"platform": "meta"}).json()["id"]
    platform_client.post("/api/v1/auth/logout")
    platform_client.post("/api/v1/auth/register", json={"name": "Other Platform User", "email": "other-platform@example.com", "password": "correct-horse-battery"})

    assert platform_client.get("/api/v1/platforms/accounts").json() == []
    assert platform_client.delete(f"/api/v1/platforms/accounts/{account_id}").status_code == 404
