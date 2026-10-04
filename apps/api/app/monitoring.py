"""Runtime metrics for monitoring (PRD §20, §22).

Exposes queue depth, job outcomes, and adoption counters so an operator can see
whether publishing is healthy without attaching a debugger. Values come from the
database and the in-process queue, so no new infrastructure is required.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends
from pydantic import BaseModel

from .auth import _current_user
from .config import settings

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


class JobCounts(BaseModel):
    queued: int
    running: int
    succeeded: int
    failed: int


class MonitoringSnapshot(BaseModel):
    generated_at: str
    window_hours: int
    jobs: JobCounts
    campaigns_by_status: dict[str, int]
    connected_accounts: int
    activity_events: int
    ai_provider: str
    integrations: str
    environment: str


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def build_snapshot(window_hours: int) -> MonitoringSnapshot:
    """Collect a monitoring snapshot without requiring authentication."""

    from .analytics import init_analytics_db
    from .publishing import init_publishing_db

    init_publishing_db()
    init_analytics_db()
    since = (datetime.now(UTC) - timedelta(hours=window_hours)).isoformat()
    with _database() as connection:
        counts = {row["status"]: row["total"] for row in connection.execute("SELECT status, COUNT(*) AS total FROM publishing_jobs GROUP BY status").fetchall()}
        campaigns = {row["status"]: row["total"] for row in connection.execute("SELECT status, COUNT(*) AS total FROM campaigns GROUP BY status").fetchall()}
        accounts = connection.execute("SELECT COUNT(*) AS total FROM connected_accounts").fetchone()["total"]
        activity = connection.execute("SELECT COUNT(*) AS total FROM activity_logs WHERE created_at >= ?", (since,)).fetchone()["total"]

    return MonitoringSnapshot(
        generated_at=datetime.now(UTC).isoformat(),
        window_hours=window_hours,
        jobs=JobCounts(
            queued=counts.get("QUEUED", 0),
            running=counts.get("RUNNING", 0),
            succeeded=counts.get("SUCCEEDED", 0),
            failed=counts.get("FAILED", 0),
        ),
        campaigns_by_status=campaigns,
        connected_accounts=int(accounts),
        activity_events=int(activity),
        ai_provider=settings.ai_provider,
        integrations="live" if settings.live_external_apis else "sandbox",
        environment=settings.app_env,
    )


@router.get("/snapshot", response_model=MonitoringSnapshot)
def snapshot(window_hours: int = 24, user=Depends(_user)) -> MonitoringSnapshot:
    """Operational snapshot for the signed-in user."""

    return build_snapshot(max(window_hours, 1))


@router.get("/health-metrics", response_model=dict[str, object])
def health_metrics() -> dict[str, object]:
    """Unauthenticated liveness detail safe to expose to a load balancer."""

    snapshot_data = build_snapshot(1)
    return {
        "status": "ok",
        "queue_backlog": snapshot_data.jobs.queued + snapshot_data.jobs.running,
        "failed_jobs": snapshot_data.jobs.failed,
        "generated_at": snapshot_data.generated_at,
    }
