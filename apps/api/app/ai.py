

import json
import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Literal, Protocol

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


from .auth import _current_user
from .config import settings

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
Platform = Literal["Meta", "Google", "YouTube"]
EditAction = Literal["regenerate", "shorten", "expand", "change_tone", "professional", "casual", "change_cta", "rewrite_headline", "alternative"]


class GenerateRequest(BaseModel):
    campaign_id: int
    instruction: Annotated[str | None, Field(max_length=2000)] = None


class EditRequest(BaseModel):
    campaign_id: int
    platform: Platform
    action: EditAction
    value: Annotated[str | None, Field(max_length=1000)] = None


class Strategy(BaseModel):
    objective: str
    positioning: str
    channel_plan: list[str]


class AudienceProfile(BaseModel):
    primary: str
    insights: list[str]
    locations: list[str]


class Messaging(BaseModel):
    value_proposition: str
    proof_points: list[str]
    tone: str
    call_to_action: str


class MetaAd(BaseModel):
    platform: Literal["Meta"] = "Meta"
    primary_text: Annotated[str, Field(min_length=1, max_length=2000)]
    headline: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    cta: Annotated[str, Field(min_length=1, max_length=80)]


class GoogleAd(BaseModel):
    platform: Literal["Google", "YouTube"]
    headline: Annotated[str, Field(min_length=1, max_length=90)]
    long_headline: Annotated[str, Field(min_length=1, max_length=180)]
    description: Annotated[str, Field(min_length=1, max_length=300)]
    video_hook: Annotated[str, Field(min_length=1, max_length=300)]
    video_script: Annotated[str, Field(min_length=1, max_length=4000)]
    cta: Annotated[str, Field(min_length=1, max_length=80)]


class CampaignContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Strategy
    audience: AudienceProfile
    messaging: Messaging
    platform_ads: Annotated[list[MetaAd | GoogleAd], Field(min_length=1, max_length=3)]

    @field_validator("platform_ads")
    @classmethod
    def unique_platforms(cls, value: list[MetaAd | GoogleAd]) -> list[MetaAd | GoogleAd]:
        platforms = [item.platform for item in value]
        if len(platforms) != len(set(platforms)):
            raise ValueError("Each platform may appear only once")
        return value


class GenerationResponse(BaseModel):
    id: int
    campaign_id: int
    provider: str
    model: str
    status: Literal["generated", "edited", "reviewed"]
    content: CampaignContent
    created_at: str


class AIProvider(Protocol):
    name: str
    model: str

    def generate(self, campaign: dict[str, object], instruction: str | None = None) -> dict[str, object]: ...
    def edit(self, content: dict[str, object], platform: str, action: str, value: str | None = None) -> dict[str, object]: ...



class SandboxProvider:
    name = "sandbox"
    model = "deterministic-v1"

    def generate(self, campaign: dict[str, object], instruction: str | None = None) -> dict[str, object]:
        product = str(campaign["product"])
        audience = str(campaign["audience"])
        location = str(campaign["location"])
        tone = str(campaign["tone"])
        offer = str(campaign.get("offer") or "Discover what is waiting for you.")
        cta = "Learn more"
        ads: list[dict[str, object]] = []
        platforms = list(campaign.get("platforms") or [])
        if "Meta" in platforms:
            ads.append({"platform": "Meta", "primary_text": f"Ready for {product.lower()}? Discover a better way to make every moment count.", "headline": f"Meet {product}", "description": f"Built for {audience.lower()} in {location}.", "cta": cta})
        for platform in platforms:
            if platform in {"Google", "YouTube"}:
                ads.append({"platform": platform, "headline": f"Discover {product}", "long_headline": f"Take the next step with {product}", "description": f"A clear choice for {audience.lower()} in {location}.", "video_hook": f"What if {product.lower()} was made for your next chapter?", "video_script": f"Open on the moment that matters. Show how {product} fits into real life. Close with: {offer}", "cta": cta})
                break
        return {"strategy": {"objective": str(campaign["objective"]), "positioning": f"{tone} positioning for {audience}", "channel_plan": [str(item) for item in platforms]}, "audience": {"primary": audience, "insights": [f"Interested in {product}", f"Based in or targeting {location}"], "locations": [location]}, "messaging": {"value_proposition": offer, "proof_points": [f"Designed for {audience}", f"Clear value in {location}"], "tone": tone, "call_to_action": cta}, "platform_ads": ads}

    def edit(self, content: dict[str, object], platform: str, action: str, value: str | None = None) -> dict[str, object]:
        edited = json.loads(json.dumps(content))
        for ad in edited.get("platform_ads", []):
            if ad.get("platform") != platform:
                continue
            if action in {"shorten", "expand"}:
                field = "primary_text" if "primary_text" in ad else "description"
                text = str(ad.get(field, ""))
                ad[field] = text[: max(40, int(len(text) * 0.7))] if action == "shorten" else text + " Discover the details and decide on your own schedule."
            elif action in {"professional", "casual", "change_tone"}:
                target = value or ("Professional and clear" if action == "professional" else "Friendly and relaxed" if action == "casual" else str(value or ""))
                ad["headline"] = f"{ad.get('headline', '').split(':')[0]}: {target}"
            elif action == "change_cta" and "cta" in ad:
                ad["cta"] = value or "Get started"
            elif action == "rewrite_headline" and "headline" in ad:
                ad["headline"] = value or f"Discover {ad.get('headline', 'your next favorite')} today"
        return edited


class OpenAIProvider(SandboxProvider):
    name = "openai"

    def __init__(self) -> None:
        self.model = settings.ai_model


class GeminiProvider(SandboxProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.model = settings.ai_model


def get_provider() -> AIProvider:
    if not settings.ai_api_key or settings.ai_provider == "mock":
        return SandboxProvider()
    if settings.ai_provider == "openai":
        return OpenAIProvider()
    if settings.ai_provider == "gemini":
        return GeminiProvider()
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Configured AI provider is not supported")


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_ai_db() -> None:
    from .auth import init_db
    from .campaigns import init_campaign_db

    init_db()
    init_campaign_db()
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ai_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                provider TEXT NOT NULL, model TEXT NOT NULL, action TEXT NOT NULL,
                content TEXT NOT NULL, instruction TEXT, created_at TEXT NOT NULL
            );
            """
        )


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _owned_campaign(connection: sqlite3.Connection, campaign_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return row


def _owned_generation(connection: sqlite3.Connection, generation_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM ai_generations WHERE id = ? AND user_id = ?", (generation_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI generation not found")
    return row


def _row(row: sqlite3.Row) -> GenerationResponse:
    return GenerationResponse(id=row["id"], campaign_id=row["campaign_id"], provider=row["provider"], model=row["model"], status=row["action"], content=CampaignContent.model_validate_json(row["content"]), created_at=row["created_at"])


def _campaign_context(row: sqlite3.Row) -> dict[str, object]:
    return {**dict(row), "platforms": json.loads(row["platforms"])}


def _save(connection: sqlite3.Connection, user_id: int, campaign_id: int, provider: AIProvider, action: str, content: CampaignContent, instruction: str | None) -> GenerationResponse:
    now = datetime.now(timezone.utc).isoformat()
    cursor = connection.execute("INSERT INTO ai_generations (user_id, campaign_id, provider, model, action, content, instruction, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (user_id, campaign_id, provider.name, provider.model, action, content.model_dump_json(), instruction, now))
    connection.execute("INSERT INTO activity_logs (user_id, campaign_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, campaign_id, "AI_CONTENT_" + action.upper(), f"{provider.name} generated content for campaign {campaign_id}", now))
    return _row(connection.execute("SELECT * FROM ai_generations WHERE id = ?", (cursor.lastrowid,)).fetchone())


@router.get("/campaigns/{campaign_id}/generation", response_model=GenerationResponse)
def latest_generation(campaign_id: int, user=Depends(_user)) -> GenerationResponse:
    init_ai_db()
    with _database() as connection:
        _owned_campaign(connection, campaign_id, user["id"])
        row = connection.execute("SELECT * FROM ai_generations WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (campaign_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No generated content found for this campaign")
    return _row(row)

@router.post("/generate-campaign", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
def generate_campaign(payload: GenerateRequest, user=Depends(_user)) -> GenerationResponse:
    init_ai_db()
    provider = get_provider()
    with _database() as connection:
        campaign = _owned_campaign(connection, payload.campaign_id, user["id"])
        try:
            raw_content = provider.generate(_campaign_context(campaign), payload.instruction)
        except ValidationError:
            raise
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI provider could not generate campaign content") from error
        try:
            content = CampaignContent.model_validate(raw_content)
        except ValidationError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="AI provider returned invalid structured content") from error
        return _save(connection, user["id"], payload.campaign_id, provider, "generated", content, payload.instruction)


@router.post("/regenerate", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
def regenerate_campaign(payload: GenerateRequest, user=Depends(_user)) -> GenerationResponse:
    return generate_campaign(payload, user)


class SaveContentRequest(BaseModel):
    content: CampaignContent


@router.post("/edit", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
def edit_content(payload: EditRequest, user=Depends(_user)) -> GenerationResponse:
    init_ai_db()
    provider = get_provider()
    with _database() as connection:
        latest = connection.execute("SELECT * FROM ai_generations WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (payload.campaign_id, user["id"])).fetchone()
        if latest is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generate content before editing")
        current = CampaignContent.model_validate_json(latest["content"])
        try:
            raw_content = provider.edit(current.model_dump(), payload.platform, payload.action, payload.value)
        except ValidationError:
            raise
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI provider could not edit campaign content") from error
        try:
            content = CampaignContent.model_validate(raw_content)
        except ValidationError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="AI provider returned invalid structured content") from error
        return _save(connection, user["id"], payload.campaign_id, provider, "edited", content, f"{payload.action}:{payload.value or ''}")


@router.put("/generations/{generation_id}", response_model=GenerationResponse)
def save_generation(generation_id: int, payload: SaveContentRequest, user=Depends(_user)) -> GenerationResponse:
    init_ai_db()
    provider = get_provider()
    try:
        content = CampaignContent.model_validate(payload.content)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Generated content failed schema validation") from error
    with _database() as connection:
        existing = _owned_generation(connection, generation_id, user["id"])
        return _save(connection, user["id"], existing["campaign_id"], provider, "reviewed", content, "manual review save")
