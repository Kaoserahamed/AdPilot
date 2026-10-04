"""Tests for the AI analytics assistant (PRD §8.20)."""

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.analytics_ai import MetricLine as Fact
from app.analytics_ai import build_summary, verify_supported
from app.jobs import InlineQueue
from app.main import app
from app.platforms import SandboxAdapter

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89" + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4" + b"\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture()
def inline_queue() -> InlineQueue:
    jobs_module.set_queue(InlineQueue())
    yield InlineQueue()
    jobs_module.set_queue(None)


@pytest.fixture()
def assistant_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline_queue: InlineQueue) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "assistant.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={"name": "Assistant Owner", "email": "assistant@example.com", "password": "correct-horse-battery"},
        ).status_code == 201
        yield client


def synced_campaign(client: TestClient, monkeypatch: pytest.MonkeyPatch, **metrics: float) -> int:
    """Publish a campaign and sync stubbed platform metrics into the store."""

    campaign_id = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Assistant tour",
            "product": "Tour Package",
            "description": "A seven day guided tour package for university students.",
            "objective": "sales",
            "location": "Dhaka",
            "audience": "University students",
            "budget": 100,
            "duration_days": 7,
            "landing_page": "https://example.com/tour",
            "tone": "Warm",
            "platforms": ["Meta"],
        },
    ).json()["id"]
    creative_id = client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")}).json()["id"]
    client.post(f"/api/v1/creatives/{creative_id}/attach", json={"campaign_ids": [campaign_id]})
    client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})
    client.post(f"/api/v1/campaigns/{campaign_id}/validate")
    client.post(f"/api/v1/campaigns/{campaign_id}/review/confirm")
    client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})
    client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    payload = {"spend": 120.0, "impressions": 4000, "reach": 3200, "clicks": 160, "conversions": 8, "revenue": 640.0, "source": "sandbox", **metrics}
    monkeypatch.setattr(SandboxAdapter, "get_metrics", lambda self, external_id: dict(payload))
    client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")
    return campaign_id


# --- Factual grounding ------------------------------------------------------


def test_summary_uses_only_stored_values() -> None:
    campaign = {"id": 1, "name": "Tour", "objective": "sales", "status": "ACTIVE", "budget": 100.0}
    facts = [
        Fact(metric="spend", value=120.0, currency="USD", source="sandbox", calculated=False, reported_at="2026-01-01"),
        Fact(metric="impressions", value=4000.0, currency="USD", source="sandbox", calculated=False, reported_at="2026-01-01"),
    ]
    summary, highlights = build_summary(campaign, facts, "2026-01-01T00:00:00+00:00", "2026-01-08T00:00:00+00:00")
    assert "Spend: USD 120" in summary
    assert "Impressions: 4,000" in summary
    assert any("sandbox" in line for line in summary.split(". "))


def test_summary_omits_metrics_that_were_never_reported() -> None:
    campaign = {"id": 1, "name": "Tour", "objective": "sales", "status": "ACTIVE", "budget": 100.0}
    facts = [Fact(metric="spend", value=10.0, currency="USD", source="sandbox", calculated=False, reported_at="2026-01-01")]
    summary, _ = build_summary(campaign, facts, "2026-01-01", "2026-01-08")
    assert "Conversions" not in summary


def test_verify_rejects_invented_figures() -> None:
    facts = [Fact(metric="spend", value=120.0, currency="USD", source="sandbox", calculated=False, reported_at="2026-01-01")]
    with pytest.raises(HTTPException) as raised:
        verify_supported("Spend was 9999.", [], facts)
    assert raised.value.status_code == 502


def test_verify_accepts_stored_figures() -> None:
    facts = [
        Fact(metric="spend", value=120.0, currency="USD", source="sandbox", calculated=False, reported_at="2026-01-01"),
        Fact(metric="ctr", value=4.0, currency="USD", source="adpilot", calculated=True, reported_at="2026-01-01"),
    ]
    verify_supported("Spend: USD 120", ["ctr 4"], facts)


# --- Endpoint ---------------------------------------------------------------


def test_analyze_returns_factual_summary(assistant_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = synced_campaign(assistant_client, monkeypatch)
    response = assistant_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id})
    assert response.status_code == 200
    body = response.json()
    assert "Spend: USD 120" in body["summary"]
    assert body["data_complete"] is True
    assert body["facts"]
    assert body["provider"]
    assert body["model"]


def test_analyze_accepts_a_question(assistant_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = synced_campaign(assistant_client, monkeypatch)
    body = assistant_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id, "question": "What happened last week?"}).json()
    assert body["question"] == "What happened last week?"
    assert body["highlights"][0] == "Question: What happened last week?"


def test_analyze_requires_synced_metrics(assistant_client: TestClient) -> None:
    campaign_id = assistant_client.post(
        "/api/v1/campaigns",
        json={
            "name": "No metrics",
            "product": "Tour",
            "description": "A description long enough to pass validation",
            "objective": "traffic",
            "location": "Dhaka",
            "audience": "Students",
            "budget": 10,
            "duration_days": 3,
            "landing_page": "https://example.com",
            "tone": "Warm",
            "platforms": ["Meta"],
        },
    ).json()["id"]
    assert assistant_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id}).status_code == 409


def test_analyze_reports_unavailable_metrics(assistant_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = synced_campaign(assistant_client, monkeypatch)
    body = assistant_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id}).json()
    assert body["data_complete"] is True
    assert body["unavailable"] == []


def test_analyze_requires_authentication(assistant_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = synced_campaign(assistant_client, monkeypatch)
    assistant_client.post("/api/v1/auth/logout")
    assert assistant_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id}).status_code == 401


def test_analyze_is_owner_scoped(assistant_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = synced_campaign(assistant_client, monkeypatch)
    assistant_client.post("/api/v1/auth/logout")
    assistant_client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": "other-assistant@example.com", "password": "correct-horse-battery"},
    )
    assert assistant_client.post("/api/v1/ai/analyze", json={"campaign_id": campaign_id}).status_code == 404