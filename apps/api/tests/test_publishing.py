from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.jobs import InlineQueue, RecordingQueue
from app.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89" + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4" + b"\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture()
def inline_queue() -> InlineQueue:
    """Run publishing jobs synchronously so assertions never race the worker."""

    jobs_module.set_queue(InlineQueue())
    yield InlineQueue()
    jobs_module.set_queue(None)


@pytest.fixture()
def publish_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline_queue: InlineQueue) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "publishing.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={"name": "Publish Owner", "email": "publish@example.com", "password": "correct-horse-battery"},
        ).status_code == 201
        yield client


def payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "Tour launch",
        "product": "Bangladesh Tour Package",
        "description": "A seven day guided tour package for university students.",
        "objective": "sales",
        "location": "Dhaka",
        "audience": "University students",
        "budget": 100,
        "duration_days": 7,
        "landing_page": "https://example.com/tour",
        "tone": "Warm",
        "platforms": ["Meta"],
    }
    base.update(overrides)
    return base


def ready_campaign(client: TestClient, platforms: list[str] | None = None) -> int:
    """Create a campaign that passes validation and review confirmation."""

    campaign_id = client.post("/api/v1/campaigns", json=payload(platforms=platforms or ["Meta"])).json()["id"]
    creative_id = client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")}).json()["id"]
    client.post(f"/api/v1/creatives/{creative_id}/attach", json={"campaign_ids": [campaign_id]})
    client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})
    assert client.post(f"/api/v1/campaigns/{campaign_id}/validate").json()["ready"] is True
    assert client.post(f"/api/v1/campaigns/{campaign_id}/review/confirm").status_code == 200
    return campaign_id


def test_publish_emits_structured_job_logs(publish_client: TestClient, captured_logs) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})

    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    queued = captured_logs.find("publishing_job_queued")
    assert queued["campaign_id"] == campaign_id
    assert queued["job_id"] > 0
    assert queued["logger"] == "adpilot.publishing"
    # Every record must be joinable back to the request that caused it.
    assert queued["request_id"]

    started = captured_logs.find("publishing_job_started")
    assert started["campaign_id"] == campaign_id
    assert started["platforms"] == ["Meta"]


def test_publish_failure_is_logged_with_a_reason(publish_client: TestClient, captured_logs) -> None:
    campaign_id = ready_campaign(publish_client)
    # No connected account, so the worker fails the job.

    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    failure = captured_logs.find("publishing_job_failed")
    assert failure["campaign_id"] == campaign_id
    assert failure["reason"]
    assert failure["level"] == "WARNING"


def test_publishing_requires_review_confirmation(publish_client: TestClient) -> None:
    campaign_id = publish_client.post("/api/v1/campaigns", json=payload()).json()["id"]
    assert publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").status_code == 409


def test_publish_queues_job_and_updates_status(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})

    response = publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")
    assert response.status_code == 202
    assert response.json()["status"] == "PUBLISHING"
    assert response.json()["job"]["status"] == "QUEUED"

    status = publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()
    assert status["status"] == "PENDING_REVIEW"
    assert status["platforms"][0]["platform"] == "meta"
    assert status["platforms"][0]["external_campaign_id"].startswith("meta-campaign-")
    assert status["jobs"][0]["status"] == "SUCCEEDED"
    assert status["jobs"][0]["attempt"] == 1


def test_publish_records_activity_log(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")
    actions = [item["action"] for item in publish_client.get("/api/v1/activity").json()]
    assert "CAMPAIGN_PUBLISH_REQUESTED" in actions
    assert "CAMPAIGN_SUBMITTED" in actions


def test_publish_fails_without_connected_account(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")
    status = publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()
    assert status["status"] == "FAILED"
    assert status["jobs"][0]["status"] == "FAILED"
    assert "connected" in status["jobs"][0]["error"].lower()


def test_duplicate_publish_is_rejected(publish_client: TestClient) -> None:
    queue = RecordingQueue()
    jobs_module.set_queue(queue)
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})

    assert publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").status_code == 202
    assert publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").status_code == 409
    assert len(queue.jobs) == 1


def test_pause_requires_prior_submission(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    assert publish_client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 409


def test_pause_updates_platform_and_campaign(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    response = publish_client.post(f"/api/v1/campaigns/{campaign_id}/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "PAUSED"
    assert response.json()["platforms"][0]["status"] == "PAUSED"


def test_failed_campaign_can_be_republished(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")
    assert publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()["status"] == "FAILED"

    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})
    assert publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").status_code == 202
    assert publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()["status"] == "PENDING_REVIEW"


def test_retry_requeues_failed_job(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    job_id = publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").json()["job"]["id"]
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})

    retried = publish_client.post(f"/api/v1/publishing/jobs/{job_id}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "QUEUED"

    status = publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()
    assert status["status"] == "PENDING_REVIEW"
    assert status["jobs"][0]["status"] == "SUCCEEDED"
    assert status["jobs"][0]["attempt"] == 2


def test_retry_stops_at_attempt_limit(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    job_id = publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").json()["job"]["id"]
    for _ in range(2):
        publish_client.post(f"/api/v1/publishing/jobs/{job_id}/retry")
    assert publish_client.post(f"/api/v1/publishing/jobs/{job_id}/retry").status_code == 409


def test_jobs_are_owner_scoped(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    job_id = publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish").json()["job"]["id"]

    publish_client.post("/api/v1/auth/logout")
    publish_client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": "other-pub@example.com", "password": "correct-horse-battery"},
    )
    assert publish_client.post(f"/api/v1/publishing/jobs/{job_id}/retry").status_code == 404
    assert publish_client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 404
    assert publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").status_code == 404


def test_jobs_list_returns_only_own_jobs(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")
    assert len(publish_client.get("/api/v1/publishing/jobs").json()) == 1


def test_publishing_requires_authentication(publish_client: TestClient) -> None:
    publish_client.post("/api/v1/auth/logout")
    assert publish_client.get("/api/v1/publishing/jobs").status_code == 401
    assert publish_client.post("/api/v1/campaigns/1/pause").status_code == 401


# --- Activity log ----------------------------------------------------------


def test_activity_records_campaign_lifecycle(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    entries = publish_client.get("/api/v1/activity").json()
    actions = [entry["action"] for entry in entries]
    assert actions[0] == "CAMPAIGN_STATUS_CHANGED"
    assert "CAMPAIGN_CREATED" in actions
    assert "CAMPAIGN_VALIDATED" in actions
    assert "REVIEW_CONFIRMED" in actions
    assert all(entry["detail"] is not None or entry["action"] for entry in entries)


def test_activity_can_be_filtered_by_campaign(publish_client: TestClient) -> None:
    first = ready_campaign(publish_client)
    second = ready_campaign(publish_client)
    entries = publish_client.get(f"/api/v1/activity?campaign_id={first}").json()
    assert {entry["campaign_id"] for entry in entries} == {first}
    assert all(entry["campaign_id"] != second for entry in entries)


def test_activity_limit_is_respected(publish_client: TestClient) -> None:
    ready_campaign(publish_client)
    assert len(publish_client.get("/api/v1/activity?limit=2").json()) == 2


def test_activity_rejects_invalid_limit(publish_client: TestClient) -> None:
    assert publish_client.get("/api/v1/activity?limit=0").status_code == 422
    assert publish_client.get("/api/v1/activity?limit=9999").status_code == 422


def test_activity_is_owner_scoped(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client)
    publish_client.post("/api/v1/auth/logout")
    publish_client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": "other-activity@example.com", "password": "correct-horse-battery"},
    )
    assert publish_client.get("/api/v1/activity").json() == []
    assert publish_client.get(f"/api/v1/activity?campaign_id={campaign_id}").status_code == 404


def test_recent_activity_endpoint(publish_client: TestClient) -> None:
    ready_campaign(publish_client)
    recent = publish_client.get("/api/v1/activity/recent?limit=5").json()
    everything = publish_client.get("/api/v1/activity?limit=200").json()
    assert 0 < len(recent) <= 5
    assert recent == everything[: len(recent)]


def test_activity_requires_authentication(publish_client: TestClient) -> None:
    publish_client.post("/api/v1/auth/logout")
    assert publish_client.get("/api/v1/activity").status_code == 401
def test_publishing_multiple_platforms(publish_client: TestClient) -> None:
    campaign_id = ready_campaign(publish_client, platforms=["Meta", "Google"])
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Meta"})
    publish_client.post("/api/v1/platforms/accounts/connect", json={"platform": "Google"})
    publish_client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    status = publish_client.get(f"/api/v1/campaigns/{campaign_id}/status").json()
    assert {item["platform"] for item in status["platforms"]} == {"meta", "google"}
    assert status["status"] == "PENDING_REVIEW"
