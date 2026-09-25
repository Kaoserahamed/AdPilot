from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def campaign_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "campaigns.db"))
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={"name": "Campaign Owner", "email": "owner@example.com", "password": "correct-horse-battery"})
        assert response.status_code == 201
        yield client


def campaign_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Launch tour package",
        "product": "Bangladesh tour package",
        "description": "A seven day guided tour for curious university students.",
        "objective": "sales",
        "location": "Dhaka, Bangladesh",
        "audience": "University students aged 18 to 25",
        "budget": 500,
        "duration_days": 7,
        "landing_page": "https://example.com/tour",
        "tone": "Adventurous and warm",
        "offer": "10% early booking discount",
        "platforms": ["Meta", "Google"],
    }
    payload.update(overrides)
    return payload


def test_campaign_crud_and_activity(campaign_client: TestClient) -> None:
    created = campaign_client.post("/api/v1/campaigns", json=campaign_payload())
    assert created.status_code == 201
    campaign = created.json()
    assert campaign["status"] == "DRAFT"
    assert campaign["platforms"] == ["Meta", "Google"]
    assert campaign_client.get("/api/v1/campaigns").json()[0]["id"] == campaign["id"]

    updated = campaign_client.put(f"/api/v1/campaigns/{campaign['id']}", json={"name": "Updated tour campaign", "budget": 750})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated tour campaign"
    assert updated.json()["budget"] == 750

    assert campaign_client.delete(f"/api/v1/campaigns/{campaign['id']}").status_code == 204
    assert campaign_client.get("/api/v1/campaigns").json() == []
    assert campaign_client.get(f"/api/v1/campaigns/{campaign['id']}").status_code == 404


def test_campaign_validation_rejects_incomplete_brief(campaign_client: TestClient) -> None:
    response = campaign_client.post("/api/v1/campaigns", json=campaign_payload(landing_page="not-a-url", platforms=[]))

    assert response.status_code == 422


def test_campaign_ownership_is_enforced(campaign_client: TestClient) -> None:
    created = campaign_client.post("/api/v1/campaigns", json=campaign_payload())
    campaign_id = created.json()["id"]
    campaign_client.post("/api/v1/auth/logout")
    campaign_client.post("/api/v1/auth/register", json={"name": "Other User", "email": "other@example.com", "password": "correct-horse-battery"})

    assert campaign_client.get(f"/api/v1/campaigns/{campaign_id}").status_code == 404
    assert campaign_client.put(f"/api/v1/campaigns/{campaign_id}", json={"name": "Should not work"}).status_code == 404
    assert campaign_client.delete(f"/api/v1/campaigns/{campaign_id}").status_code == 404
