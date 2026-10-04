from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89" + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4" + b"\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture()
def validation_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "validation.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json={"name": "Validation Owner", "email": "validation@example.com", "password": "correct-horse-battery"}).status_code == 201
        yield client


def campaign_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"name": "Validation campaign", "product": "Tour package", "description": "A seven day guided tour package for university students.", "objective": "sales", "location": "Dhaka", "audience": "University students", "budget": 500, "duration_days": 7, "landing_page": "https://example.com/tour", "tone": "Warm", "platforms": ["Meta"]}
    payload.update(overrides)
    return payload


def test_validation_fails_without_creative_and_generated_content(validation_client: TestClient) -> None:
    campaign_id = validation_client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]
    response = validation_client.post(f"/api/v1/campaigns/{campaign_id}/validate")
    assert response.status_code == 200
    result = response.json()
    assert result["ready"] is False
    assert "Attach at least one creative before publishing" in result["errors"]
    assert result["generated_content_ready"] is False
    assert validation_client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == "VALIDATION_FAILED"


def test_validation_passes_with_creative_and_generated_content(validation_client: TestClient) -> None:
    campaign_id = validation_client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]
    creative_id = validation_client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")}).json()["id"]
    validation_client.post(f"/api/v1/creatives/{creative_id}/attach", json={"campaign_ids": [campaign_id]})
    validation_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})
    response = validation_client.post(f"/api/v1/campaigns/{campaign_id}/validate")
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert validation_client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"] == "READY"


def test_review_confirmation_requires_valid_campaign(validation_client: TestClient) -> None:
    campaign_id = validation_client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]
    assert validation_client.post(f"/api/v1/campaigns/{campaign_id}/review/confirm").status_code == 422


def test_validation_is_owner_scoped(validation_client: TestClient) -> None:
    campaign_id = validation_client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]
    validation_client.post("/api/v1/auth/logout")
    validation_client.post("/api/v1/auth/register", json={"name": "Other Validation User", "email": "other-validation@example.com", "password": "correct-horse-battery"})
    assert validation_client.post(f"/api/v1/campaigns/{campaign_id}/validate").status_code == 404
