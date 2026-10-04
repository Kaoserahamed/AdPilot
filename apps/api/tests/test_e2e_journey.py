"""End-to-end validation of the primary user journey (PRD §15, §21).

Walks the full flow a new user completes, asserting each release criterion in
order:

    Register -> Login -> Create campaign -> Upload creative -> Generate AI content
    -> Review -> Connect platform -> Validate -> Publish -> Retrieve metrics
    -> View dashboard -> Ask AI to summarise

This is the acceptance gate for the MVP, so it deliberately uses only public
HTTP endpoints rather than internal functions.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.jobs import InlineQueue
from app.main import app
from app.platforms import SandboxAdapter

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89" + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4" + b"\x00\x00\x00\x00IEND\xaeB`\x82"

CAMPAIGN = {
    "name": "Bangladesh tour package",
    "product": "Bangladesh Tour Package",
    "description": "A seven day guided tour package for university students in Dhaka.",
    "objective": "sales",
    "location": "Dhaka, Bangladesh",
    "audience": "University students aged 18-24",
    "budget": 100,
    "duration_days": 7,
    "landing_page": "https://example.com/tour",
    "tone": "Warm and encouraging",
    "offer": "Early booking discount",
    "platforms": ["Meta"],
}


@pytest.fixture()
def journey_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    jobs_module.set_queue(InlineQueue())
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "e2e.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))

    def metrics(self: SandboxAdapter, external_id: str) -> dict[str, object]:
        return {
            "external_id": external_id,
            "spend": 42.75,
            "impressions": 8421,
            "reach": 6100,
            "clicks": 327,
            "conversions": 47,
            "revenue": 310.0,
            "source": "sandbox",
        }

    monkeypatch.setattr(SandboxAdapter, "get_metrics", metrics)
    with TestClient(app) as client:
        yield client
    jobs_module.set_queue(None)


def test_mvp_release_journey(journey_client: TestClient) -> None:
    # Register
    assert journey_client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": "alex@example.com", "password": "correct-horse-battery"},
    ).status_code == 201

    # Login
    assert journey_client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": "correct-horse-battery"}).status_code == 200
    assert journey_client.get("/api/v1/auth/me").json()["email"] == "alex@example.com"

    # Create campaign
    campaign_id = journey_client.post("/api/v1/campaigns", json=CAMPAIGN).json()["id"]

    # Upload creative
    creative = journey_client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")})
    assert creative.status_code == 201
    assert journey_client.post(f"/api/v1/creatives/{creative.json()['id']}/attach", json={"campaign_ids": [campaign_id]}).status_code in {200, 204}

    # Generate AI content
    generation = journey_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})
    assert generation.status_code in {200, 201}
    assert generation.json()["content"]["platform_ads"]

    # Edit AI content
    edited = journey_client.post("/api/v1/ai/edit", json={"campaign_id": campaign_id, "platform": "Meta", "action": "change_cta", "value": "Book now"})
    assert edited.status_code in {200, 201}
    assert edited.json()["content"]["platform_ads"][0]["cta"] == "Book now"

    # Validate and review
    assert journey_client.post(f"/api/v1/campaigns/{campaign_id}/validate").json()["ready"] is True
    assert journey_client.post(f"/api/v1/campaigns/{campaign_id}/review/confirm").status_code == 200

    # Connect advertising accounts
    assert journey_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"}).status_code == 201
    assert journey_client.get("/api/v1/platforms/accounts").json()

    # Publish
    assert journey_client.post(f"/api/v1/campaigns/{campaign_id}/publish").status_code == 202

    # Campaign status
    status = journey_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()
    assert status["platforms"][0]["status"] == "PENDING_REVIEW"

    # Retrieve metrics
    assert journey_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync").status_code == 202
    overview = journey_client.get("/api/v1/analytics/overview").json()
    assert overview["total_spend"] == 42.75
    assert overview["total_conversions"] == 47

    # View unified analytics
    assert journey_client.get("/api/v1/analytics/platforms").json()[0]["platform"] == "meta"
    assert journey_client.get(f"/api/v1/analytics/campaigns/{campaign_id}").json()["totals"]["clicks"] == 327

    # Ask AI to summarise performance
    answer = journey_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id, "question": "Summarize this campaign."})
    assert answer.status_code == 200
    assert "42.75" in answer.json()["summary"]
    assert answer.json()["data_complete"] is True

    # Audit trail covers the journey
    actions = [entry["action"] for entry in journey_client.get("/api/v1/activity").json()]
    for expected in ("CAMPAIGN_CREATED", "CAMPAIGN_VALIDATED", "REVIEW_CONFIRMED", "CAMPAIGN_SUBMITTED", "METRICS_SYNCED"):
        assert expected in actions


def test_every_release_criteria_endpoint_requires_authentication(journey_client: TestClient) -> None:
    """Every MVP release-criteria endpoint must exist and reject anonymous access."""

    protected = [
        ("GET", "/api/v1/campaigns"),
        ("POST", "/api/v1/campaigns"),
        ("GET", "/api/v1/creatives"),
        ("POST", "/api/v1/ai/generate-campaign"),
        ("POST", "/api/v1/ai/regenerate"),
        ("POST", "/api/v1/ai/edit"),
        ("POST", "/api/v1/ai/analyze"),
        ("GET", "/api/v1/platforms"),
        ("GET", "/api/v1/platforms/accounts"),
        ("POST", "/api/v1/campaigns/1/validate"),
        ("POST", "/api/v1/campaigns/1/review/confirm"),
        ("POST", "/api/v1/campaigns/1/publish"),
        ("GET", "/api/v1/campaigns/1/status"),
        ("POST", "/api/v1/campaigns/1/pause"),
        ("GET", "/api/v1/publishing/jobs"),
        ("GET", "/api/v1/analytics/overview"),
        ("GET", "/api/v1/analytics/platforms"),
        ("GET", "/api/v1/analytics/campaigns/1"),
        ("POST", "/api/v1/analytics/campaigns/1/sync"),
        ("GET", "/api/v1/activity"),
        ("GET", "/api/v1/monitoring/snapshot"),
    ]
    for method, path in protected:
        response = journey_client.request(method, path, json={})
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}, expected 401"


def test_unauthenticated_health_endpoints_stay_public(journey_client: TestClient) -> None:
    assert journey_client.get("/api/health").status_code == 200
    assert journey_client.get("/api/ready").status_code == 200
    assert journey_client.get("/api/v1/monitoring/health-metrics").status_code == 200