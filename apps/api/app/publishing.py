"""Asynchronous campaign publishing (PRD §8.16, §10).

Workflow::

    User clicks Publish -> validate -> persist job -> queue -> worker
    -> platform API (adapter contract) -> update campaign status

Publishing never happens inline in the request. The job row is committed before
the queue is touched, so a queue failure cannot lose work, and campaign status
is always derived from stored job and platform records.
"""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import _current_user
from .config import settings
from .jobs import get_queue
from .logging_config import get_logger
from .platforms import get_adapter

logger = get_logger("publishing")

router = APIRouter(prefix="/api/v1/campaigns", tags=["publishing"])
jobs_router = APIRouter(prefix="/api/v1/publishing", tags=["publishing"])

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]

MAX_PUBLISH_ATTEMPTS = 3


class PublishingJobResponse(BaseModel):
    id: int
    campaign_id: int
    status: JobStatus
    attempt: int
    error: str | None
    created_at: str
    updated_at: str


class PlatformCampaignResponse(BaseModel):
    id: int
    platform: str
    external_campaign_id: str
    status: str
    detail: str | None
    updated_at: str


class PublishResponse(BaseModel):
    campaign_id: int
    status: str
    job: PublishingJobResponse
    message: str


class CampaignStatusResponse(BaseModel):
    campaign_id: int
    status: str
    updated_at: str
    platforms: list[PlatformCampaignResponse]
    jobs: list[PublishingJobResponse]


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_publishing_db() -> None:
    """Create publishing tables. Safe to call repeatedly."""

    from .ai import init_ai_db
    from .auth import init_db
    from .campaigns import init_campaign_db
    from .creatives import init_creative_db
    from .platforms import init_platform_db

    init_db()
    init_campaign_db()
    init_creative_db()
    init_ai_db()
    init_platform_db()
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS publishing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                attempt INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_publishing_jobs_campaign
                ON publishing_jobs(campaign_id, id);
            CREATE INDEX IF NOT EXISTS idx_platform_campaigns_campaign
                ON platform_campaigns(campaign_id);
            """
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _owned_campaign(connection: sqlite3.Connection, campaign_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return row


def _set_campaign_status(connection: sqlite3.Connection, campaign_id: int, user_id: int, new_status: str) -> None:
    connection.execute(
        "UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (new_status, _now(), campaign_id, user_id),
    )


def _log(connection: sqlite3.Connection, user_id: int, campaign_id: int, action: str, detail: str) -> None:
    connection.execute(
        "INSERT INTO activity_logs (user_id, campaign_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, campaign_id, action, detail, _now()),
    )


def _job_response(row: sqlite3.Row) -> PublishingJobResponse:
    return PublishingJobResponse(
        id=row["id"],
        campaign_id=row["campaign_id"],
        status=row["status"],
        attempt=row["attempt"],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _platform_campaigns(connection: sqlite3.Connection, campaign_id: int) -> list[PlatformCampaignResponse]:
    rows = connection.execute(
        "SELECT id, platform, external_campaign_id, status, detail, updated_at FROM platform_campaigns WHERE campaign_id = ? ORDER BY id",
        (campaign_id,),
    ).fetchall()
    return [
        PlatformCampaignResponse(
            id=row["id"],
            platform=row["platform"],
            external_campaign_id=row["external_campaign_id"],
            status=row["status"],
            detail=row["detail"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
def _recent_jobs(connection: sqlite3.Connection, campaign_id: int) -> list[PublishingJobResponse]:
    rows = connection.execute(
        "SELECT * FROM publishing_jobs WHERE campaign_id = ? ORDER BY id DESC LIMIT 10",
        (campaign_id,),
    ).fetchall()
    return [_job_response(row) for row in rows]


class PublishingError(Exception):
    """Raised inside the worker when publishing cannot continue."""


def _resolve_accounts(connection: sqlite3.Connection, platforms: list[str], user_id: int) -> dict[str, sqlite3.Row]:
    """Return the connected account row per platform, raising when one is missing."""

    accounts: dict[str, sqlite3.Row] = {}
    for platform in platforms:
        row = connection.execute(
            "SELECT * FROM connected_accounts WHERE user_id = ? AND platform = ? ORDER BY connected_at DESC LIMIT 1",
            (user_id, platform.lower()),
        ).fetchone()
        if row is None:
            raise PublishingError(f"No connected {platform} advertising account. Connect the account before publishing.")
        accounts[platform] = row
    return accounts


def _roll_up_status(statuses: list[str]) -> str:
    """Combine per-platform statuses into one campaign status."""

    if not statuses:
        return "PENDING_REVIEW"
    if any(item in {"FAILED", "REJECTED"} for item in statuses):
        return "REJECTED" if all(item == "REJECTED" for item in statuses) else "FAILED"
    if all(item == "ACTIVE" for item in statuses):
        return "ACTIVE"
    return "PENDING_REVIEW"


def _publish_to_platform(
    campaign: dict[str, object],
    platforms: list[str],
    ads_by_platform: dict[str, list[dict[str, object]]],
    accounts: dict[str, sqlite3.Row],
    connection: sqlite3.Connection,
) -> dict[str, str]:
    """Create the campaign and its ads on every platform, then submit for review."""

    outcomes: dict[str, str] = {}
    for platform in platforms:
        adapter = get_adapter(platform)
        account = accounts[platform]
        created = adapter.create_campaign({**campaign, "account_id": account["external_account_id"]})
        external_id = str(created["external_id"])
        for ad in ads_by_platform.get(platform, []):
            adapter.create_ad({**ad, "external_campaign_id": external_id})
        published = adapter.publish_campaign(external_id)
        status_value = str(published.get("status", "PENDING_REVIEW"))
        connection.execute(
            """INSERT INTO platform_campaigns (user_id, campaign_id, connected_account_id, platform, external_campaign_id, status, detail, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                campaign["user_id"],
                campaign["id"],
                account["id"],
                adapter.name,
                external_id,
                status_value,
                str(published.get("detail", "")),
                _now(),
                _now(),
            ),
        )
        outcomes[platform] = status_value
    return outcomes


def _fail_job(job_id: int, campaign_id: int, user_id: int, message: str) -> None:
    """Record a terminal failure without exposing internal detail."""

    logger.warning(
        "publishing_job_failed",
        extra={"job_id": job_id, "campaign_id": campaign_id, "user_id": user_id, "reason": message[:500]},
    )
    with _database() as connection:
        connection.execute(
            "UPDATE publishing_jobs SET status = 'FAILED', error = ?, updated_at = ? WHERE id = ?",
            (message[:500], _now(), job_id),
        )
        _set_campaign_status(connection, campaign_id, user_id, "FAILED")
        _log(connection, user_id, campaign_id, "CAMPAIGN_FAILED", message[:500])


def _process_job(job_id: int) -> None:
    """Worker entry point: publish one campaign job."""

    init_publishing_db()
    with _database() as connection:
        job = connection.execute("SELECT * FROM publishing_jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None or job["status"] == "SUCCEEDED":
            return
        attempt = int(job["attempt"]) + 1
        connection.execute(
            "UPDATE publishing_jobs SET status = 'RUNNING', attempt = ?, updated_at = ? WHERE id = ?",
            (attempt, _now(), job_id),
        )
        campaign = _owned_campaign(connection, job["campaign_id"], job["user_id"])

        from .ai import CampaignContent

        generation = connection.execute(
            "SELECT content FROM ai_generations WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (campaign["id"], job["user_id"]),
        ).fetchone()
        generated = CampaignContent.model_validate_json(generation["content"]) if generation else None

    data = dict(campaign)
    try:
        platforms = json.loads(data["platforms"])
        ads_by_platform: dict[str, list[dict[str, object]]] = {}
        for ad in generated.platform_ads if generated else []:
            ads_by_platform.setdefault(ad.platform, []).append(ad.model_dump())
        with _database() as connection:
            accounts = _resolve_accounts(connection, platforms, data["user_id"])
            _set_campaign_status(connection, data["id"], data["user_id"], "PUBLISHING")
            _log(connection, data["user_id"], data["id"], "CAMPAIGN_SUBMITTED", f"Publishing job {job_id} started")
            logger.info(
                "publishing_job_started",
                extra={"job_id": job_id, "campaign_id": data["id"], "attempt": attempt, "platforms": platforms},
            )
            outcomes = _publish_to_platform(data, platforms, ads_by_platform, accounts, connection)
            final = _roll_up_status(list(outcomes.values()))
            connection.execute(
                "UPDATE publishing_jobs SET status = 'SUCCEEDED', error = NULL, updated_at = ? WHERE id = ?",
                (_now(), job_id),
            )
            _set_campaign_status(connection, data["id"], data["user_id"], final)
            _log(connection, data["user_id"], data["id"], "CAMPAIGN_STATUS_CHANGED", f"Platform submission finished with status {final}")
            logger.info(
                "publishing_job_succeeded",
                extra={"job_id": job_id, "campaign_id": data["id"], "status": final, "outcomes": outcomes},
            )
    except PublishingError as error:
        _fail_job(job_id, data["id"], data["user_id"], str(error))
    except HTTPException as error:
        _fail_job(job_id, data["id"], data["user_id"], str(error.detail))
    except Exception:  # noqa: BLE001 - the job row records the outcome; never leak internals
        _fail_job(job_id, data["id"], data["user_id"], "Publishing failed while preparing platform submissions.")


@router.post("/{campaign_id}/publish", response_model=PublishResponse, status_code=status.HTTP_202_ACCEPTED)
def publish_campaign(campaign_id: int, user=Depends(_user)) -> PublishResponse:
    """Queue a publishing job. Publishing only runs after review confirmation."""

    init_publishing_db()
    with _database() as connection:
        campaign = _owned_campaign(connection, campaign_id, user["id"])
        if campaign["status"] not in {"READY", "FAILED", "PAUSED"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign must pass review before publishing")
        active = connection.execute(
            "SELECT id FROM publishing_jobs WHERE campaign_id = ? AND user_id = ? AND status IN ('QUEUED', 'RUNNING') ORDER BY id DESC LIMIT 1",
            (campaign_id, user["id"]),
        ).fetchone()
        if active is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A publishing job is already in progress for this campaign")
        cursor = connection.execute(
            "INSERT INTO publishing_jobs (campaign_id, user_id, status, attempt, created_at, updated_at) VALUES (?, ?, 'QUEUED', 0, ?, ?)",
            (campaign_id, user["id"], _now(), _now()),
        )
        job_id = int(cursor.lastrowid)
        _log(connection, user["id"], campaign_id, "CAMPAIGN_PUBLISH_REQUESTED", f"Queued publishing job {job_id}")
        job = connection.execute("SELECT * FROM publishing_jobs WHERE id = ?", (job_id,)).fetchone()

    get_queue().enqueue(job_id, lambda: _process_job(job_id))
    # Logged outside the transaction so a queue failure is visible here even
    # though the job row is already committed.
    logger.info("publishing_job_queued", extra={"job_id": job_id, "campaign_id": campaign_id, "user_id": user["id"]})
    return PublishResponse(campaign_id=campaign_id, status="PUBLISHING", job=_job_response(job), message="Publishing job queued. Track progress with the status endpoint.")


@router.get("/{campaign_id}/status", response_model=CampaignStatusResponse)
def campaign_status(campaign_id: int, user=Depends(_user)) -> CampaignStatusResponse:
    """Report campaign status with per-platform submissions and recent jobs."""

    init_publishing_db()
    with _database() as connection:
        campaign = _owned_campaign(connection, campaign_id, user["id"])
        return CampaignStatusResponse(
            campaign_id=campaign_id,
            status=campaign["status"],
            updated_at=campaign["updated_at"],
            platforms=_platform_campaigns(connection, campaign_id),
            jobs=_recent_jobs(connection, campaign_id),
        )


@router.post("/{campaign_id}/pause", response_model=CampaignStatusResponse)
def pause_campaign(campaign_id: int, user=Depends(_user)) -> CampaignStatusResponse:
    """Pause the campaign on every platform it was submitted to."""

    init_publishing_db()
    with _database() as connection:
        _owned_campaign(connection, campaign_id, user["id"])
        rows = connection.execute("SELECT * FROM platform_campaigns WHERE campaign_id = ?", (campaign_id,)).fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign has not been submitted to any platform yet")
        for row in rows:
            adapter = get_adapter(row["platform"])
            result = adapter.pause_campaign(row["external_campaign_id"])
            connection.execute(
                "UPDATE platform_campaigns SET status = ?, detail = ?, updated_at = ? WHERE id = ?",
                (str(result.get("status", "PAUSED")), str(result.get("detail", "")), _now(), row["id"]),
            )
        _set_campaign_status(connection, campaign_id, user["id"], "PAUSED")
        _log(connection, user["id"], campaign_id, "CAMPAIGN_PAUSED", "Campaign paused by user")
        campaign = _owned_campaign(connection, campaign_id, user["id"])
        return CampaignStatusResponse(
            campaign_id=campaign_id,
            status=campaign["status"],
            updated_at=campaign["updated_at"],
            platforms=_platform_campaigns(connection, campaign_id),
            jobs=_recent_jobs(connection, campaign_id),
        )


@jobs_router.get("/jobs", response_model=list[PublishingJobResponse])
def list_jobs(user=Depends(_user)) -> list[PublishingJobResponse]:
    """List the caller's publishing jobs, newest first."""

    init_publishing_db()
    with _database() as connection:
        rows = connection.execute("SELECT * FROM publishing_jobs WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user["id"],)).fetchall()
        return [_job_response(row) for row in rows]


@jobs_router.post("/jobs/{job_id}/retry", response_model=PublishingJobResponse)
def retry_job(job_id: int, user=Depends(_user)) -> PublishingJobResponse:
    """Requeue a failed publishing job, bounded by the attempt limit."""

    init_publishing_db()
    with _database() as connection:
        job = connection.execute("SELECT * FROM publishing_jobs WHERE id = ? AND user_id = ?", (job_id, user["id"])).fetchone()
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing job not found")
        if int(job["attempt"]) >= MAX_PUBLISH_ATTEMPTS:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Retry limit of {MAX_PUBLISH_ATTEMPTS} attempts reached")
        connection.execute("UPDATE publishing_jobs SET status = 'QUEUED', error = NULL, updated_at = ? WHERE id = ?", (_now(), job_id))
        updated = connection.execute("SELECT * FROM publishing_jobs WHERE id = ?", (job_id,)).fetchone()
    get_queue().enqueue(job_id, lambda: _process_job(job_id))
    return _job_response(updated)
