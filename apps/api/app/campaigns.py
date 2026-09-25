import json
import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import _current_user
from .config import settings

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

Objective = Literal["traffic", "leads", "sales", "brand_awareness", "engagement"]
Platform = Literal["Meta", "Google", "YouTube"]
CampaignStatus = Literal["DRAFT", "READY", "VALIDATION_FAILED", "PUBLISHING", "PENDING_REVIEW", "ACTIVE", "PAUSED", "REJECTED", "FAILED"]


class CampaignCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Annotated[str, Field(min_length=2, max_length=120)]
    product: Annotated[str, Field(min_length=2, max_length=160)]
    description: Annotated[str, Field(min_length=10, max_length=4000)]
    objective: Objective
    location: Annotated[str, Field(min_length=2, max_length=160)]
    audience: Annotated[str, Field(min_length=2, max_length=400)]
    budget: Annotated[float, Field(gt=0, le=10_000_000)]
    duration_days: Annotated[int, Field(ge=1, le=365)]
    landing_page: Annotated[str, Field(min_length=8, max_length=2048)]
    tone: Annotated[str, Field(min_length=2, max_length=80)]
    offer: Annotated[str | None, Field(max_length=240)] = None
    platforms: Annotated[list[Platform], Field(min_length=1, max_length=3)]
    brand_guidelines: Annotated[str | None, Field(max_length=4000)] = None
    existing_copy: Annotated[str | None, Field(max_length=4000)] = None
    competitor_notes: Annotated[str | None, Field(max_length=4000)] = None
    instructions: Annotated[str | None, Field(max_length=4000)] = None

    @field_validator("landing_page")
    @classmethod
    def validate_landing_page(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("Landing page must start with http:// or https://")
        return value

    @field_validator("platforms")
    @classmethod
    def unique_platforms(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Platforms must be unique")
        return value


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    product: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, min_length=10, max_length=4000)
    objective: Objective | None = None
    location: str | None = Field(default=None, min_length=2, max_length=160)
    audience: str | None = Field(default=None, min_length=2, max_length=400)
    budget: float | None = Field(default=None, gt=0, le=10_000_000)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    landing_page: str | None = Field(default=None, min_length=8, max_length=2048)
    tone: str | None = Field(default=None, min_length=2, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    platforms: list[Platform] | None = Field(default=None, min_length=1, max_length=3)
    status: CampaignStatus | None = None
    brand_guidelines: str | None = Field(default=None, max_length=4000)
    existing_copy: str | None = Field(default=None, max_length=4000)
    competitor_notes: str | None = Field(default=None, max_length=4000)
    instructions: str | None = Field(default=None, max_length=4000)


class CampaignResponse(BaseModel):
    id: int
    name: str
    product: str
    description: str
    objective: str
    location: str
    audience: str
    budget: float
    currency: str
    duration_days: int
    landing_page: str
    tone: str
    offer: str | None
    platforms: list[str]
    status: str
    spend: float
    created_at: str
    updated_at: str


def init_campaign_db() -> None:
    from .auth import init_db

    init_db()
    with sqlite3.connect(settings.auth_db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL, product TEXT NOT NULL, description TEXT NOT NULL,
                objective TEXT NOT NULL, location TEXT NOT NULL, audience TEXT NOT NULL,
                budget REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', duration_days INTEGER NOT NULL,
                landing_page TEXT NOT NULL, tone TEXT NOT NULL, offer TEXT, platforms TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'DRAFT', brand_guidelines TEXT, existing_copy TEXT,
                competitor_notes TEXT, instructions TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE, action TEXT NOT NULL,
                detail TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """
        )



def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _row(row: sqlite3.Row) -> CampaignResponse:
    return CampaignResponse(
        id=row["id"], name=row["name"], product=row["product"], description=row["description"],
        objective=row["objective"], location=row["location"], audience=row["audience"], budget=row["budget"],
        currency=row["currency"], duration_days=row["duration_days"], landing_page=row["landing_page"],
        tone=row["tone"], offer=row["offer"], platforms=json.loads(row["platforms"]), status=row["status"],
        spend=0.0, created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _log(connection: sqlite3.Connection, user_id: int, campaign_id: int, action: str, detail: str) -> None:
    connection.execute("INSERT INTO activity_logs (user_id, campaign_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, campaign_id, action, detail, datetime.now(timezone.utc).isoformat()))


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(user=Depends(_user)) -> list[CampaignResponse]:
    init_campaign_db()
    with sqlite3.connect(settings.auth_db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY updated_at DESC", (user["id"],)).fetchall()
    return [_row(row) for row in rows]


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, user=Depends(_user)) -> CampaignResponse:
    init_campaign_db()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(settings.auth_db_path) as connection:
        cursor = connection.execute(
            """INSERT INTO campaigns (user_id, name, product, description, objective, location, audience, budget, duration_days, landing_page, tone, offer, platforms, brand_guidelines, existing_copy, competitor_notes, instructions, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], payload.name, payload.product, payload.description, payload.objective, payload.location, payload.audience, payload.budget, payload.duration_days, payload.landing_page, payload.tone, payload.offer, json.dumps(payload.platforms), payload.brand_guidelines, payload.existing_copy, payload.competitor_notes, payload.instructions, now, now),
        )
        _log(connection, user["id"], cursor.lastrowid, "CAMPAIGN_CREATED", payload.name)
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM campaigns WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row(row)


def _owned_campaign(connection: sqlite3.Connection, campaign_id: int, user_id: int) -> sqlite3.Row:
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return row


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: int, user=Depends(_user)) -> CampaignResponse:
    init_campaign_db()
    with sqlite3.connect(settings.auth_db_path) as connection:
        return _row(_owned_campaign(connection, campaign_id, user["id"]))


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(campaign_id: int, payload: CampaignUpdate, user=Depends(_user)) -> CampaignResponse:
    init_campaign_db()
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one campaign field is required")
    with sqlite3.connect(settings.auth_db_path) as connection:
        _owned_campaign(connection, campaign_id, user["id"])
        if "platforms" in values:
            values["platforms"] = json.dumps(values["platforms"])
        values["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{field} = ?" for field in values)
        connection.execute(f"UPDATE campaigns SET {assignments} WHERE id = ? AND user_id = ?", (*values.values(), campaign_id, user["id"]))
        _log(connection, user["id"], campaign_id, "CAMPAIGN_UPDATED", ", ".join(values.keys()))
        row = _owned_campaign(connection, campaign_id, user["id"])
    return _row(row)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int, user=Depends(_user)) -> Response:
    init_campaign_db()
    with sqlite3.connect(settings.auth_db_path) as connection:
        _owned_campaign(connection, campaign_id, user["id"])
        _log(connection, user["id"], campaign_id, "CAMPAIGN_DELETED", "Campaign removed")
        connection.execute("DELETE FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user["id"]))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
