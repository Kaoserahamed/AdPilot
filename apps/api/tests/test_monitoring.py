"""Monitoring endpoint and structured logging tests (PRD §20, §22)."""

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.jobs import InlineQueue
from app.logging_config import JsonFormatter, request_id_var
from app.main import app
from app.middleware import REQUEST_ID_HEADER
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

class _Capture(logging.Handler):
    """Collect formatted log lines so tests can assert on the JSON payload."""

    def __init__(self) -> None:
        super().__init__()
        self.formatter = JsonFormatter()
        self.records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(json.loads(self.formatter.format(record)))


@pytest.fixture()
def captured_logs() -> _Capture:
    """Attach a capture handler to the adpilot logger tree for one test."""

    capture = _Capture()
    logger = logging.getLogger("adpilot")
    logger.addHandler(capture)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    yield capture
    logger.removeHandler(capture)
    logger.setLevel(previous_level)


def test_request_emits_structured_log_with_request_id(monitoring_client: TestClient, captured_logs: _Capture) -> None:
    monitoring_client.get("/api/health")

    assert captured_logs.records, "expected the request to emit a log record"
    entry = captured_logs.records[-1]
    assert entry["message"] == "request_completed"
    assert entry["request_id"]
    assert entry["method"] == "GET"
    assert entry["path"] == "/api/health"
    assert entry["status_code"] == 200
    assert isinstance(entry["duration_ms"], (int, float))


def test_log_request_id_matches_the_response_header(monitoring_client: TestClient, captured_logs: _Capture) -> None:
    response = monitoring_client.get("/api/ready")

    # The id in the log must be the same one handed back to the caller, or the
    # two cannot be joined when debugging a report.
    assert captured_logs.records[-1]["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_log_reuses_a_client_supplied_request_id(monitoring_client: TestClient, captured_logs: _Capture) -> None:
    response = monitoring_client.get("/api/health", headers={REQUEST_ID_HEADER: "trace-abc-123"})

    assert captured_logs.records[-1]["request_id"] == "trace-abc-123"
    assert response.headers[REQUEST_ID_HEADER] == "trace-abc-123"


def test_log_includes_level_and_logger_name(monitoring_client: TestClient, captured_logs: _Capture) -> None:
    monitoring_client.get("/api/health")

    entry = captured_logs.records[-1]
    assert entry["level"] == "INFO"
    assert entry["logger"] == "adpilot.request"
    assert entry["timestamp"].endswith("Z")


def test_request_id_context_does_not_leak_between_requests(monitoring_client: TestClient, captured_logs: _Capture) -> None:
    monitoring_client.get("/api/health", headers={REQUEST_ID_HEADER: "first-id"})
    monitoring_client.get("/api/health")

    ids = [record["request_id"] for record in captured_logs.records if record["message"] == "request_completed"]
    assert ids[-2] == "first-id"
    assert ids[-1] != "first-id"


def test_json_formatter_includes_ambient_request_id() -> None:
    """A log emitted outside the request middleware still carries a request_id field."""

    record = logging.LogRecord("adpilot.worker", logging.INFO, __file__, 1, "worker_tick", None, None)
    token = request_id_var.set("ambient-id")
    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert payload["request_id"] == "ambient-id"
    assert payload["message"] == "worker_tick"


def test_json_formatter_serialises_exception_details() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("adpilot.worker", logging.ERROR, __file__, 1, "failed", None, None)
        record.exc_info = __import__("sys").exc_info()

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "ERROR"
    assert "boom" in payload["exception"]

def test_build_snapshot_without_request_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "direct.db"))
    snapshot = build_snapshot(6)
    assert snapshot.window_hours == 6
    assert snapshot.jobs.queued == 0