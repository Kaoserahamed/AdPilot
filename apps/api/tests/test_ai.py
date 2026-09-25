from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def ai_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "ai.db"))
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json={"name": "AI Owner", "email": "ai@example.com", "password": "correct-horse-battery"}).status_code == 201
        yield client


def campaign_payload() -> dict[str, object]:
    return {"name": "Tour launch", "product": "Bangladesh tour package", "description": "A seven day guided tour package for university students.", "objective": "sales", "location": "Dhaka, Bangladesh", "audience": "University students", "budget": 500, "duration_days": 7, "landing_page": "https://example.com/tour", "tone": "Adventurous and warm", "platforms": ["Meta", "Google"]}


def create_campaign(client: TestClient) -> int:
    return client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]


def test_generate_and_latest_generation(ai_client: TestClient) -> None:
    campaign_id = create_campaign(ai_client)
    response = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})

    assert response.status_code == 201
    generated = response.json()
    assert generated["provider"] == "sandbox"
    assert generated["status"] == "generated"
    assert {ad["platform"] for ad in generated["content"]["platform_ads"]} == {"Meta", "Google"}
    assert ai_client.get(f"/api/v1/ai/campaigns/{campaign_id}/generation").json()["id"] == generated["id"]


def test_edit_and_manual_review_save(ai_client: TestClient) -> None:
    campaign_id = create_campaign(ai_client)
    generated = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id}).json()
    edited = ai_client.post("/api/v1/ai/edit", json={"campaign_id": campaign_id, "platform": "Meta", "action": "change_cta", "value": "Book now"})

    assert edited.status_code == 201
    assert edited.json()["status"] == "edited"
    assert any(ad["cta"] == "Book now" for ad in edited.json()["content"]["platform_ads"] if ad["platform"] == "Meta")

    content = edited.json()["content"]
    saved = ai_client.put(f"/api/v1/ai/generations/{edited.json()['id']}", json={"content": content})
    assert saved.status_code == 200
    assert saved.json()["status"] == "reviewed"
    assert generated["id"] != saved.json()["id"]


def test_malformed_provider_output_is_rejected(ai_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = create_campaign(ai_client)

    class InvalidProvider:
        name = "invalid"
        model = "test"

        def generate(self, campaign: dict[str, object], instruction: str | None = None) -> dict[str, object]:
            return {"strategy": {"unexpected": "missing required fields"}}

        def edit(self, content: dict[str, object], platform: str, action: str, value: str | None = None) -> dict[str, object]:
            return content

    monkeypatch.setattr("app.ai.get_provider", lambda: InvalidProvider())
    response = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})

    assert response.status_code == 422
    assert ai_client.get(f"/api/v1/ai/campaigns/{campaign_id}/generation").status_code == 404


def test_generation_is_owner_scoped(ai_client: TestClient) -> None:
    campaign_id = create_campaign(ai_client)
    generated = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id}).json()
    ai_client.post("/api/v1/auth/logout")
    ai_client.post("/api/v1/auth/register", json={"name": "Other AI User", "email": "other-ai@example.com", "password": "correct-horse-battery"})

    assert ai_client.get(f"/api/v1/ai/campaigns/{campaign_id}/generation").status_code == 404
    assert ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id}).status_code == 404
    assert ai_client.put(f"/api/v1/ai/generations/{generated['id']}", json={"content": generated["content"]}).status_code == 404
