"""Monitoring endpoint tests (PRD §20, §22)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.jobs import InlineQueue
from app.main import app
from app.monitoring import build_snapshot

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89" + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4" + b"\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture()
def monitoring_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    jobs_module.set_queue(InlineQueue())
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "monitoring.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={"name": "Ops Owner", "email": "ops@example.com", "password": "correct-horse-battery"},
        ).status_code == 201
        yield client
    jobs_module.set_queue(None)


def create_campaign(client: TestClient) -> int:
    return client.post(
        "/api/v1/campaigns",
        json={
            "name": "Ops campaign",
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


def test_snapshot_reports_job_queue_state(monitoring_client: TestClient) -> None:
    create_campaign(monitoring_client)
    body = monitoring_client.get("/api/v1/monitoring/snapshot").json()
    assert body["jobs"]["queued"] == 0
    assert body["jobs"]["failed"] == 0
    assert body["jobs"]["succeeded"] == 0
    assert body["campaigns_by_status"]["DRAFT"] == 1
    assert body["activity_events"] > 0
    assert body["generated_at"]
    assert body["integrations"] in {"sandbox", "live"}


def test_snapshot_counts_failed_jobs(monitoring_client: TestClient) -> None:
    campaign_id = create_campaign(monitoring_client)
    creative_id = monitoring_client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")}).json()["id"]
    monitoring_client.post(f"/api/v1/creatives/{creative_id}/attach", json={"campaign_ids": [campaign_id]})
    monitoring_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})
    monitoring_client.post(f"/api/v1/campaigns/{campaign_id}/validate")
    monitoring_client.post(f"/api/v1/campaigns/{campaign_id}/review/confirm")
    monitoring_client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    body = monitoring_client.get("/api/v1/monitoring/snapshot").json()
    assert body["jobs"]["failed"] == 1
    assert body["jobs"]["succeeded"] == 0


def test_health_metrics_need_no_authentication(monitoring_client: TestClient) -> None:
    body = monitoring_client.get("/api/v1/monitoring/health-metrics").json()
    assert body["status"] == "ok"
    assert body["queue_backlog"] == 0
    assert body["failed_jobs"] == 0


def test_snapshot_requires_authentication(monitoring_client: TestClient) -> None:
    monitoring_client.post("/api/v1/auth/logout")
    assert monitoring_client.get("/api/v1/monitoring/snapshot").status_code == 401


def test_snapshot_window_is_bounded(monitoring_client: TestClient) -> None:
    body = monitoring_client.get("/api/v1/monitoring/snapshot?window_hours=0").json()
    assert body["window_hours"] >= 1


def test_build_snapshot_without_request_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "direct.db"))
    snapshot = build_snapshot(6)
    assert snapshot.window_hours == 6
    assert snapshot.jobs.queued == 0