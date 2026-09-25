from fastapi import Response

import base64
import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .auth import _current_user
from .config import settings

router = APIRouter(prefix="/api/v1/platforms", tags=["platforms"])
accounts_router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


class PlatformCapabilities(BaseModel):
    platform: str
    label: str
    connected: bool
    supports_oauth: bool
    supports_video: bool
    supports_metrics: bool
    supports_pause: bool
    sandbox: bool


class AccountResponse(BaseModel):
    id: int
    platform: str
    platform_label: str
    external_account_id: str
    name: str
    currency: str
    status: str
    connected_at: str
    sandbox: bool


class ConnectRequest(BaseModel):
    platform: str
    account_name: str | None = Field(default=None, max_length=120)


class PlatformOperationResult(BaseModel):
    platform: str
    external_id: str
    status: str
    detail: str
    sandbox: bool


class AdPlatformAdapter(Protocol):
    name: str
    label: str
    supports_oauth: bool
    supports_video: bool
    supports_metrics: bool
    supports_pause: bool

    def get_accounts(self, user_id: int) -> list[dict[str, object]]: ...
    def connect_account(self, user_id: int, account_name: str | None = None) -> dict[str, object]: ...
    def validate_campaign(self, campaign: dict[str, object], creative_types: list[str] | None = None) -> list[str]: ...
    def upload_creative(self, creative: dict[str, object]) -> dict[str, object]: ...
    def create_campaign(self, campaign: dict[str, object]) -> dict[str, object]: ...
    def create_ad(self, ad: dict[str, object]) -> dict[str, object]: ...
    def publish_campaign(self, external_campaign_id: str) -> dict[str, object]: ...
    def pause_campaign(self, external_campaign_id: str) -> dict[str, object]: ...
    def get_campaign_status(self, external_campaign_id: str) -> dict[str, object]: ...
    def get_metrics(self, external_campaign_id: str) -> dict[str, object]: ...

class SandboxAdapter:
    name = "sandbox"
    label = "Sandbox"
    supports_oauth = False
    supports_video = True
    supports_metrics = True
    supports_pause = True

    def get_accounts(self, user_id: int) -> list[dict[str, object]]:
        return [{"external_account_id": f"{self.name}-sandbox-{user_id}", "name": f"{self.label} test account", "currency": "USD", "status": "ACTIVE"}]

    def connect_account(self, user_id: int, account_name: str | None = None) -> dict[str, object]:
        return {"external_account_id": f"{self.name}-sandbox-{user_id}", "name": account_name or f"{self.label} test account", "currency": "USD", "status": "ACTIVE", "access_token": f"sandbox-token-{secrets.token_urlsafe(24)}"}

    def validate_campaign(self, campaign: dict[str, object], creative_types: list[str] | None = None) -> list[str]:
        warnings: list[str] = []
        if not campaign.get("landing_page"):
            warnings.append("Landing page is required before publishing")
        if float(campaign.get("budget") or 0) <= 0:
            warnings.append("Budget must be greater than zero")
        if not creative_types:
            warnings.append("Attach at least one creative before publishing")
        if self.name == "google" and not any(item in {"video", "image"} for item in creative_types or []):
            warnings.append("Google/YouTube requires an image or video creative")
        return warnings

    def upload_creative(self, creative: dict[str, object]) -> dict[str, object]:
        return {"external_id": f"{self.name}-creative-{uuid4().hex[:16]}", "status": "UPLOADED"}

    def create_campaign(self, campaign: dict[str, object]) -> dict[str, object]:
        return {"external_id": f"{self.name}-campaign-{uuid4().hex[:16]}", "status": "CREATED"}

    def create_ad(self, ad: dict[str, object]) -> dict[str, object]:
        return {"external_id": f"{self.name}-ad-{uuid4().hex[:16]}", "status": "CREATED"}

    def publish_campaign(self, external_campaign_id: str) -> dict[str, object]:
        return {"external_id": external_campaign_id, "status": "PENDING_REVIEW", "detail": "Sandbox platform review is pending"}

    def pause_campaign(self, external_campaign_id: str) -> dict[str, object]:
        return {"external_id": external_campaign_id, "status": "PAUSED", "detail": "Campaign paused in sandbox"}

    def get_campaign_status(self, external_campaign_id: str) -> dict[str, object]:
        return {"external_id": external_campaign_id, "status": "PENDING_REVIEW", "detail": "Awaiting sandbox platform review"}

    def get_metrics(self, external_campaign_id: str) -> dict[str, object]:
        return {"external_id": external_campaign_id, "spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0, "source": "sandbox"}


class MetaAdapter(SandboxAdapter):
    name = "meta"
    label = "Meta Ads"
    supports_oauth = True


class GoogleAdsAdapter(SandboxAdapter):
    name = "google"
    label = "Google Ads / YouTube"
    supports_oauth = True


class YouTubeAdapter(SandboxAdapter):
    name = "youtube"
    label = "YouTube Ads"
    supports_oauth = True


ADAPTERS: dict[str, AdPlatformAdapter] = {"meta": MetaAdapter(), "google": GoogleAdsAdapter(), "youtube": YouTubeAdapter()}


def get_adapter(platform: str) -> AdPlatformAdapter:
    adapter = ADAPTERS.get(platform.lower())
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported advertising platform")
    return adapter

    def create_ad(self, ad: dict[str, object]) -> dict[str, object]: ...
    def publish_campaign(self, external_campaign_id: str) -> dict[str, object]: ...
    def pause_campaign(self, external_campaign_id: str) -> dict[str, object]: ...
    def get_campaign_status(self, external_campaign_id: str) -> dict[str, object]: ...
    def get_metrics(self, external_campaign_id: str) -> dict[str, object]: ...


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt_token(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stored platform credential cannot be decrypted") from error
    connection = sqlite3.connect(settings.auth_db_path)

def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_platform_db() -> None:
    from .auth import init_db
    from .campaigns import init_campaign_db

    init_db()
    init_campaign_db()
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS connected_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                platform TEXT NOT NULL, external_account_id TEXT NOT NULL, name TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'ACTIVE',
                access_token_encrypted TEXT NOT NULL, connected_at TEXT NOT NULL,
                UNIQUE(user_id, platform, external_account_id)
            );
            CREATE TABLE IF NOT EXISTS platform_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                connected_account_id INTEGER NOT NULL REFERENCES connected_accounts(id) ON DELETE CASCADE,
                platform TEXT NOT NULL, external_campaign_id TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            """
        )


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _account(row: sqlite3.Row, adapter: AdPlatformAdapter) -> AccountResponse:
    return AccountResponse(id=row["id"], platform=adapter.name, platform_label=adapter.label, external_account_id=row["external_account_id"], name=row["name"], currency=row["currency"], status=row["status"], connected_at=row["connected_at"], sandbox=True)


def _owned_account(connection: sqlite3.Connection, account_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM connected_accounts WHERE id = ? AND user_id = ?", (account_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connected account not found")
    return row



@router.get("", response_model=list[PlatformCapabilities])
def list_platforms(user=Depends(_user)) -> list[PlatformCapabilities]:
    init_platform_db()
    with _database() as connection:
        connected = {(row["platform"], row["external_account_id"]) for row in connection.execute("SELECT platform, external_account_id FROM connected_accounts WHERE user_id = ?", (user["id"],))}
    return [PlatformCapabilities(platform=adapter.name, label=adapter.label, connected=any(key[0] == adapter.name for key in connected), supports_oauth=adapter.supports_oauth, supports_video=adapter.supports_video, supports_metrics=adapter.supports_metrics, supports_pause=adapter.supports_pause, sandbox=True) for adapter in ADAPTERS.values()]


@router.get("/accounts", response_model=list[AccountResponse])
def list_connected_accounts(user=Depends(_user)) -> list[AccountResponse]:
    init_platform_db()
    with _database() as connection:
        rows = connection.execute("SELECT * FROM connected_accounts WHERE user_id = ? ORDER BY connected_at DESC", (user["id"],)).fetchall()
        return [_account(row, get_adapter(row["platform"])) for row in rows]


@router.post("/accounts/connect", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def connect_account(payload: ConnectRequest, user=Depends(_user)) -> AccountResponse:
    init_platform_db()
    adapter = get_adapter(payload.platform)
    account = adapter.connect_account(user["id"], payload.account_name)
    token = _encrypt_token(str(account.pop("access_token")))
    with _database() as connection:
        connection.execute("INSERT OR IGNORE INTO connected_accounts (user_id, platform, external_account_id, name, currency, status, access_token_encrypted, connected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (user["id"], adapter.name, account["external_account_id"], account["name"], account.get("currency", "USD"), account.get("status", "ACTIVE"), token, datetime.now(timezone.utc).isoformat()))
        row = connection.execute("SELECT * FROM connected_accounts WHERE user_id = ? AND platform = ? AND external_account_id = ?", (user["id"], adapter.name, account["external_account_id"])).fetchone()
    return _account(row, adapter)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_account(account_id: int, user=Depends(_user)) -> Response:
    init_platform_db()
    with _database() as connection:
        _owned_account(connection, account_id, user["id"])
        connection.execute("DELETE FROM connected_accounts WHERE id = ? AND user_id = ?", (account_id, user["id"]))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
