"""Tests for unified analytics (PRD §8.18, §8.19)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.analytics import _derive
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
def analytics_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline_queue: InlineQueue) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "analytics.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={"name": "Analytics Owner", "email": "analytics@example.com", "password": "correct-horse-battery"},
        ).status_code == 201
        yield client


def published_campaign(client: TestClient, platform: str = "Meta") -> int:
    """Create, review, connect and publish a campaign ready for metric sync."""

    payload = {
        "name": "Analytics tour",
        "product": "Tour Package",
        "description": "A seven day guided tour package for university students.",
        "objective": "sales",
        "location": "Dhaka",
        "audience": "University students",
        "budget": 100,
        "duration_days": 7,
        "landing_page": "https://example.com/tour",
        "tone": "Warm",
        "platforms": [platform],
    }
    campaign_id = client.post("/api/v1/campaigns", json=payload).json()["id"]
    creative_id = client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")}).json()["id"]
    client.post(f"/api/v1/creatives/{creative_id}/attach", json={"campaign_ids": [campaign_id]})
    client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})
    client.post(f"/api/v1/campaigns/{campaign_id}/validate")
    client.post(f"/api/v1/campaigns/{campaign_id}/review/confirm")
    client.post("/api/v1/platforms/accounts/connect", json={"platform": platform})
    client.post(f"/api/v1/campaigns/{campaign_id}/publish")
    return campaign_id


def stub_metrics(spend: float, impressions: int, clicks: int, conversions: int, revenue: float | None = None):
    """Patch the sandbox adapter to return non-zero metrics."""

    def fake(self: SandboxAdapter, external_id: str) -> dict[str, object]:
        payload: dict[str, object] = {"external_id": external_id, "spend": spend, "impressions": impressions, "clicks": clicks, "conversions": conversions, "source": "sandbox"}
        if revenue is not None:
            payload["revenue"] = revenue
        return payload

    return fake


# --- Derived metric maths ---------------------------------------------------


def test_derives_ratios() -> None:
    derived = _derive(spend=100.0, impressions=1000, clicks=50, conversions=5, revenue=400.0)
    assert derived["ctr"] == 5.0
    assert derived["cpc"] == 2.0
    assert derived["cpa"] == 20.0
    assert derived["roas"] == 4.0


def test_derived_metrics_are_none_without_denominator() -> None:
    derived = _derive(spend=100.0, impressions=0, clicks=0, conversions=0, revenue=400.0)
    assert derived["ctr"] is None
    assert derived["cpc"] is None
    assert derived["cpa"] is None
    assert derived["roas"] == 4.0


def test_roas_is_none_without_spend() -> None:
    assert _derive(spend=0.0, impressions=10, clicks=1, conversions=1, revenue=50.0)["roas"] is None


# --- Metric synchronization -------------------------------------------------


def test_sync_stores_metrics_with_provenance(analytics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = published_campaign(analytics_client)
    monkeypatch.setattr(SandboxAdapter, "get_metrics", stub_metrics(120.5, 4000, 160, 8, 500.0))

    assert analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync").status_code == 202

    by_metric = {point["metric"]: point for point in analytics_client.get(f"/api/v1/analytics/campaigns/{campaign_id}/metrics").json()}
    assert by_metric["spend"]["value"] == 120.5
    assert by_metric["spend"]["source"] == "sandbox"
    assert by_metric["spend"]["calculated"] is False
    assert by_metric["spend"]["currency"] == "USD"
    assert by_metric["ctr"]["calculated"] is True
    assert by_metric["ctr"]["source"] == "adpilot"
    assert by_metric["ctr"]["value"] == 4.0


def test_sync_requires_prior_publication(analytics_client: TestClient) -> None:
    campaign_id = analytics_client.post(
        "/api/v1/campaigns",
        json={
            "name": "Unpublished",
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
    assert analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync").status_code == 409


def test_sync_is_idempotent(analytics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = published_campaign(analytics_client)
    monkeypatch.setattr(SandboxAdapter, "get_metrics", stub_metrics(10.0, 100, 5, 1))
    analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")
    first = analytics_client.get(f"/api/v1/analytics/campaigns/{campaign_id}/metrics").json()
    analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")
    second = analytics_client.get(f"/api/v1/analytics/campaigns/{campaign_id}/metrics").json()
    assert len(first) == len(second)

# --- Analytics endpoints ----------------------------------------------------


def test_campaign_analytics_reports_platforms(analytics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = published_campaign(analytics_client)
    monkeypatch.setattr(SandboxAdapter, "get_metrics", stub_metrics(200.0, 1000, 50, 5))
    analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")

    body = analytics_client.get(f"/api/v1/analytics/campaigns/{campaign_id}").json()
    assert body["campaign_id"] == campaign_id
    assert body["platforms"][0]["platform"] == "meta"
    assert body["platforms"][0]["spend"] == 200.0
    assert body["platforms"][0]["ctr"] == 5.0
    assert body["totals"]["spend"] == 200.0
    assert body["synced_at"] is not None


def test_overview_counts_campaigns_and_totals(analytics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = published_campaign(analytics_client)
    monkeypatch.setattr(SandboxAdapter, "get_metrics", stub_metrics(75.0, 300, 15, 3))
    analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")

    body = analytics_client.get("/api/v1/analytics/overview").json()
    assert body["total_spend"] == 75.0
    assert body["total_impressions"] == 300
    assert body["total_clicks"] == 15
    assert body["total_conversions"] == 3
    assert body["pending_review_campaigns"] == 1
    assert [item["platform"] for item in body["platforms"]] == ["meta"]
    assert "roas" in body["calculated_fields"]


def test_overview_is_empty_for_new_account(analytics_client: TestClient) -> None:
    body = analytics_client.get("/api/v1/analytics/overview").json()
    assert body["total_spend"] == 0.0
    assert body["campaigns"] == []
    assert body["platforms"] == []


def test_platform_breakdown_rolls_up(analytics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = published_campaign(analytics_client)
    monkeypatch.setattr(SandboxAdapter, "get_metrics", stub_metrics(40.0, 200, 10, 2))
    analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")

    platforms = analytics_client.get("/api/v1/analytics/platforms").json()
    assert platforms[0]["platform"] == "meta"
    assert platforms[0]["cpc"] == 4.0


def test_analytics_requires_authentication(analytics_client: TestClient) -> None:
    analytics_client.post("/api/v1/auth/logout")
    assert analytics_client.get("/api/v1/analytics/overview").status_code == 401
    assert analytics_client.get("/api/v1/analytics/platforms").status_code == 401


def test_analytics_is_owner_scoped(analytics_client: TestClient) -> None:
    campaign_id = published_campaign(analytics_client)
    analytics_client.post("/api/v1/auth/logout")
    analytics_client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": "other-analytics@example.com", "password": "correct-horse-battery"},
    )
    assert analytics_client.get(f"/api/v1/analytics/campaigns/{campaign_id}").status_code == 404
    assert analytics_client.get("/api/v1/analytics/overview").json()["total_spend"] == 0.0

def test_sync_records_activity(analytics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = published_campaign(analytics_client)
    monkeypatch.setattr(SandboxAdapter, "get_metrics", stub_metrics(10.0, 100, 5, 1))
    analytics_client.post(f"/api/v1/analytics/campaigns/{campaign_id}/sync")
    actions = [entry["action"] for entry in analytics_client.get("/api/v1/activity").json()]
    assert "METRICS_SYNCED" in actions


def test_derived_metrics_are_none_without_denominator() -> None:
    derived = _derive(spend=100.0, impressions=0, clicks=0, conversions=0, revenue=400.0)
    assert derived["ctr"] is None
    assert derived["cpc"] is None
    assert derived["cpa"] is None
    assert derived["roas"] == 4.0


def test_roas_is_none_without_spend() -> None:
    assert _derive(spend=0.0, impressions=10, clicks=1, conversions=1, revenue=50.0)["roas"] is None