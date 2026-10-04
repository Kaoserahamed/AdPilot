"""Campaign activity log (PRD §8.21, §10).

Every important action writes to ``activity_logs``. This module exposes the log
so users and support can audit what happened and when.
"""

import sqlite3

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from pydantic import BaseModel

from .auth import _current_user
from .config import settings

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class ActivityEntry(BaseModel):
    id: int
    campaign_id: int | None
    action: str
    detail: str | None
    created_at: str


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


@router.get("", response_model=list[ActivityEntry])
def list_activity(
    campaign_id: int | None = Query(default=None, description="Restrict to a single campaign"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    user=Depends(_user),
) -> list[ActivityEntry]:
    """Return the caller's activity log, newest first."""

    from .auth import init_db

    init_db()
    with _database() as connection:
        if campaign_id is None:
            rows = connection.execute(
                "SELECT id, campaign_id, action, detail, created_at FROM activity_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user["id"], limit),
            ).fetchall()
        else:
            owned = connection.execute("SELECT 1 FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user["id"])).fetchone()
            if owned is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
            rows = connection.execute(
                "SELECT id, campaign_id, action, detail, created_at FROM activity_logs WHERE user_id = ? AND campaign_id = ? ORDER BY id DESC LIMIT ?",
                (user["id"], campaign_id, limit),
            ).fetchall()
    return [
        ActivityEntry(id=row["id"], campaign_id=row["campaign_id"], action=row["action"], detail=row["detail"], created_at=row["created_at"])
        for row in rows
    ]


@router.get("/recent", response_model=list[ActivityEntry])
def recent_activity(limit: int = Query(default=10, ge=1, le=MAX_LIMIT), user=Depends(_user)) -> list[ActivityEntry]:
    """Recent activity across all campaigns, for dashboard display."""

    return list_activity(campaign_id=None, limit=limit, user=user)
