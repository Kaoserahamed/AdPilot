import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel

from .ai import CampaignContent
from .auth import _current_user
from .config import settings
from .db import get_connection as _database
from .db import owned_campaign as _owned_campaign

router = APIRouter(prefix="/api/v1/campaigns", tags=["validation"])


class PlatformCheck(BaseModel):
    platform: str
    ready: bool
    errors: list[str]
    warnings: list[str]


class ValidationResponse(BaseModel):
    campaign_id: int
    ready: bool
    errors: list[str]
    warnings: list[str]
    platform_checks: list[PlatformCheck]
    creative_count: int
    generated_content_ready: bool
    checked_at: str


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _creative_types(connection: sqlite3.Connection, campaign_id: int) -> list[str]:
    return [row["file_type"] for row in connection.execute("SELECT c.file_type FROM campaign_creatives cc JOIN creatives c ON c.id = cc.creative_id WHERE cc.campaign_id = ?", (campaign_id,))]


def _validate_platforms(campaign: sqlite3.Row, creative_types: list[str], generated: CampaignContent | None) -> tuple[list[str], list[str], list[PlatformCheck]]:
    errors: list[str] = []
    warnings: list[str] = []
    platforms = json.loads(campaign["platforms"])
    required = {"name": "Campaign name", "product": "Product", "description": "Description", "objective": "Objective", "location": "Target location", "audience": "Target audience", "budget": "Budget", "duration_days": "Duration", "landing_page": "Landing page", "tone": "Tone"}
    for field, label in required.items():
        if campaign[field] in (None, ""):
            errors.append(f"{label} is required")
    if float(campaign["budget"] or 0) <= 0:
        errors.append("Budget must be greater than zero")
    if int(campaign["duration_days"] or 0) <= 0:
        errors.append("Campaign duration must be greater than zero")
    if not creative_types:
        errors.append("Attach at least one creative before publishing")
    if generated is None:
        warnings.append("Generate and review platform content before publishing")
    checks: list[PlatformCheck] = []
    for platform in platforms:
        platform_errors: list[str] = []
        platform_warnings: list[str] = list(warnings)
        if platform in {"Google", "YouTube"} and not any(item in {"image", "video"} for item in creative_types):
            platform_errors.append(f"{platform} requires an image or video creative")
        if generated is not None:
            matching_ads = [ad for ad in generated.platform_ads if ad.platform == platform]
            if not matching_ads:
                platform_errors.append(f"No generated content found for {platform}")
        checks.append(PlatformCheck(platform=platform, ready=not platform_errors and not errors, errors=platform_errors + errors, warnings=platform_warnings))
    return errors, warnings, checks



@router.post("/{campaign_id}/validate", response_model=ValidationResponse)
def validate_campaign(campaign_id: int, user=Depends(_user)) -> ValidationResponse:
    from .ai import init_ai_db
    from .creatives import init_creative_db
    init_ai_db()
    init_creative_db()
    with _database() as connection:
        campaign = _owned_campaign(connection, campaign_id, user["id"])
        creative_types = _creative_types(connection, campaign_id)
        generation = connection.execute("SELECT content FROM ai_generations WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (campaign_id, user["id"])).fetchone()
    generated = CampaignContent.model_validate_json(generation["content"]) if generation else None
    errors, warnings, checks = _validate_platforms(campaign, creative_types, generated)
    ready = not errors and all(check.ready for check in checks)
    checked_at = datetime.now(UTC).isoformat()
    with _database() as connection:
        connection.execute("UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?", ("READY" if ready else "VALIDATION_FAILED", checked_at, campaign_id, user["id"]))
        connection.execute("INSERT INTO activity_logs (user_id, campaign_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)", (user["id"], campaign_id, "CAMPAIGN_VALIDATED", "Validation passed" if ready else "Validation failed", checked_at))
    return ValidationResponse(campaign_id=campaign_id, ready=ready, errors=errors, warnings=warnings, platform_checks=checks, creative_count=len(creative_types), generated_content_ready=generated is not None, checked_at=checked_at)


@router.post("/{campaign_id}/review/confirm", response_model=ValidationResponse)
def confirm_review(campaign_id: int, user=Depends(_user)) -> ValidationResponse:
    from .ai import init_ai_db
    from .creatives import init_creative_db
    init_ai_db()
    init_creative_db()
    with _database() as connection:
        campaign = _owned_campaign(connection, campaign_id, user["id"])
        creative_types = _creative_types(connection, campaign_id)
        generation = connection.execute("SELECT content FROM ai_generations WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (campaign_id, user["id"])).fetchone()
    generated = CampaignContent.model_validate_json(generation["content"]) if generation else None
    errors, warnings, checks = _validate_platforms(campaign, creative_types, generated)
    ready = not errors and all(check.ready for check in checks)
    if not ready:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Campaign must pass validation before review confirmation")
    checked_at = datetime.now(UTC).isoformat()
    with _database() as connection:
        connection.execute("UPDATE campaigns SET status = 'READY', updated_at = ? WHERE id = ? AND user_id = ?", (checked_at, campaign_id, user["id"]))
        connection.execute("INSERT INTO activity_logs (user_id, campaign_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)", (user["id"], campaign_id, "REVIEW_CONFIRMED", "User confirmed campaign for later publishing", checked_at))
    return ValidationResponse(campaign_id=campaign_id, ready=True, errors=[], warnings=warnings, platform_checks=checks, creative_count=len(creative_types), generated_content_ready=generated is not None, checked_at=checked_at)
