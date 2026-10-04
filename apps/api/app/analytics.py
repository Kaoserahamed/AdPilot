"""Unified campaign analytics (PRD §8.18, §8.19, §10).

Every metric keeps its platform, campaign, value, currency, reporting period,
and source, so the dashboard can distinguish numbers reported by an advertising
platform from numbers AdPilot derives. Derived metrics (CTR, CPC, CPA, ROAS)
are always marked ``calculated``; platform-reported values keep the source the
adapter supplied.

Metric synchronization runs through the same replaceable queue as publishing
(PRD §8.17), so a slow platform cannot block a dashboard request.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from .auth import _current_user
from .config import settings
from .jobs import get_queue
from .platforms import get_adapter

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

PLATFORM_METRICS = ("spend", "impressions", "reach", "clicks", "conversions", "revenue")
CALCULATED_METRICS = ("ctr", "cpc", "cpa", "roas")
REPORTING_PERIOD_DAYS = 7


class MetricPoint(BaseModel):
    metric: str
    value: float
    currency: str
    source: str
    calculated: bool
    reported_at: str


class PlatformBreakdown(BaseModel):
    platform: str
    spend: float
    impressions: int
    clicks: int
    conversions: int
    ctr: float | None
    cpc: float | None
    cpa: float | None
    roas: float | None
    currency: str
    calculated_fields: list[str]


class CampaignAnalytics(BaseModel):
    campaign_id: int
    campaign_name: str
    status: str
    reporting_period_days: int
    platforms: list[PlatformBreakdown]
    totals: dict[str, float]
    calculated_fields: list[str]
    synced_at: str | None


class AnalyticsOverview(BaseModel):
    reporting_period_days: int
    active_campaigns: int
    draft_campaigns: int
    pending_review_campaigns: int
    total_spend: float
    total_impressions: int
    total_clicks: int
    total_conversions: int
    currency: str
    calculated_fields: list[str]
    platforms: list[PlatformBreakdown]
    campaigns: list[CampaignAnalytics]


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_analytics_db() -> None:
    """Create the metric store. Safe to call repeatedly."""

    from .auth import init_db

    init_db()
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS campaign_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                source TEXT NOT NULL,
                calculated INTEGER NOT NULL DEFAULT 0,
                reported_at TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(campaign_id, platform, metric, period_end)
            );
            CREATE INDEX IF NOT EXISTS idx_campaign_metrics_campaign
                ON campaign_metrics(campaign_id, platform);
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _owned_campaign(connection: sqlite3.Connection, campaign_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return row


def _currency_for(connection: sqlite3.Connection, user_id: int, platform: str) -> str:
    row = connection.execute(
        "SELECT currency FROM connected_accounts WHERE user_id = ? AND platform = ? ORDER BY connected_at DESC LIMIT 1",
        (user_id, platform),
    ).fetchone()
    return row["currency"] if row else "USD"


def _derive(spend: float, impressions: int, clicks: int, conversions: int, revenue: float) -> dict[str, float | None]:
    """Compute derived metrics. Any undefined ratio is reported as ``None``."""

    return {
        "ctr": round((clicks / impressions) * 100, 4) if impressions else None,
        "cpc": round(spend / clicks, 4) if clicks else None,
        "cpa": round(spend / conversions, 4) if conversions else None,
        "roas": round(revenue / spend, 4) if spend else None,
    }
def sync_campaign_metrics(campaign_id: int, user_id: int) -> None:
    """Pull metrics from each platform adapter and store them with full provenance."""

    from .campaigns import init_campaign_db
    from .platforms import init_platform_db

    init_campaign_db()
    init_platform_db()
    init_analytics_db()
    # Snap the reporting period to the UTC day so repeated syncs upsert the same
    # rows instead of appending a new snapshot on every call.
    period_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = period_end - timedelta(days=REPORTING_PERIOD_DAYS)

    with _database() as connection:
        _owned_campaign(connection, campaign_id, user_id)
        rows = connection.execute("SELECT platform, external_campaign_id FROM platform_campaigns WHERE campaign_id = ?", (campaign_id,)).fetchall()

    for row in rows:
        adapter = get_adapter(row["platform"])
        if not adapter.supports_metrics:
            continue
        payload = adapter.get_metrics(row["external_campaign_id"])
        with _database() as connection:
            currency = _currency_for(connection, user_id, row["platform"])
            source = str(payload.get("source", adapter.name))
            for metric in PLATFORM_METRICS:
                if payload.get(metric) is None:
                    continue
                connection.execute(
                    """INSERT INTO campaign_metrics (campaign_id, user_id, platform, metric, value, currency, source, calculated, reported_at, period_start, period_end, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                       ON CONFLICT(campaign_id, platform, metric, period_end)
                       DO UPDATE SET value = excluded.value, source = excluded.source, reported_at = excluded.reported_at""",
                    (campaign_id, user_id, row["platform"], metric, float(payload[metric]), currency, source, _now(), period_start.isoformat(), period_end.isoformat(), _now()),
                )
            base = {metric: float(payload.get(metric) or 0) for metric in PLATFORM_METRICS}
            for metric, value in _derive(base["spend"], int(base["impressions"]), int(base["clicks"]), int(base["conversions"]), base["revenue"]).items():
                if value is None:
                    continue
                connection.execute(
                    """INSERT INTO campaign_metrics (campaign_id, user_id, platform, metric, value, currency, source, calculated, reported_at, period_start, period_end, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'adpilot', 1, ?, ?, ?, ?)
                       ON CONFLICT(campaign_id, platform, metric, period_end)
                       DO UPDATE SET value = excluded.value""",
                    (campaign_id, user_id, row["platform"], metric, value, currency, _now(), period_start.isoformat(), period_end.isoformat(), _now()),
                )
            connection.execute(
                "INSERT INTO activity_logs (user_id, campaign_id, action, detail, created_at) VALUES (?, ?, 'METRICS_SYNCED', ?, ?)",
                (user_id, campaign_id, f"Synced metrics for {row['platform']}", _now()),
            )


def _breakdown(connection: sqlite3.Connection, campaign_id: int, platform: str) -> PlatformBreakdown | None:
    rows = connection.execute(
        "SELECT metric, MAX(value) AS value, MAX(currency) AS currency FROM campaign_metrics WHERE campaign_id = ? AND platform = ? GROUP BY metric",
        (campaign_id, platform),
    ).fetchall()
    if not rows:
        return None
    values = {row["metric"]: float(row["value"]) for row in rows}
    currency = next((row["currency"] for row in rows if row["currency"]), "USD")
    derived = _derive(
        values.get("spend", 0.0),
        int(values.get("impressions", 0)),
        int(values.get("clicks", 0)),
        int(values.get("conversions", 0)),
        values.get("revenue", 0.0),
    )
    calculated = [name for name in CALCULATED_METRICS if values.get(name) is not None]
    return PlatformBreakdown(
        platform=platform,
        spend=values.get("spend", 0.0),
        impressions=int(values.get("impressions", 0)),
        clicks=int(values.get("clicks", 0)),
        conversions=int(values.get("conversions", 0)),
        ctr=derived["ctr"],
        cpc=derived["cpc"],
        cpa=derived["cpa"],
        roas=derived["roas"],
        currency=currency,
        calculated_fields=calculated,
    )


def _campaign_analytics(connection: sqlite3.Connection, campaign: sqlite3.Row) -> CampaignAnalytics:
    rows = connection.execute("SELECT DISTINCT platform FROM campaign_metrics WHERE campaign_id = ? ORDER BY platform", (campaign["id"],)).fetchall()
    platforms = [item for item in (_breakdown(connection, campaign["id"], row["platform"]) for row in rows) if item is not None]
    totals = {
        "spend": round(sum(item.spend for item in platforms), 2),
        "impressions": sum(item.impressions for item in platforms),
        "clicks": sum(item.clicks for item in platforms),
        "conversions": sum(item.conversions for item in platforms),
    }
    latest = connection.execute("SELECT MAX(reported_at) AS latest FROM campaign_metrics WHERE campaign_id = ?", (campaign["id"],)).fetchone()
    return CampaignAnalytics(
        campaign_id=campaign["id"],
        campaign_name=campaign["name"],
        status=campaign["status"],
        reporting_period_days=REPORTING_PERIOD_DAYS,
        platforms=platforms,
        totals=totals,
        calculated_fields=list(CALCULATED_METRICS),
        synced_at=latest["latest"] if latest else None,
    )


def _platform_rollup(per_campaign: list[CampaignAnalytics]) -> list[PlatformBreakdown]:
    """Aggregate campaign-level platforms into one row per advertising platform."""

    totals: dict[str, dict[str, float]] = {}
    for entry in per_campaign:
        for item in entry.platforms:
            bucket = totals.setdefault(item.platform, {"spend": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0})
            bucket["spend"] += item.spend
            bucket["impressions"] += item.impressions
            bucket["clicks"] += item.clicks
            bucket["conversions"] += item.conversions
    rollups = []
    for platform, bucket in sorted(totals.items()):
        derived = _derive(bucket["spend"], int(bucket["impressions"]), int(bucket["clicks"]), int(bucket["conversions"]), 0.0)
        rollups.append(
            PlatformBreakdown(
                platform=platform,
                spend=round(bucket["spend"], 2),
                impressions=int(bucket["impressions"]),
                clicks=int(bucket["clicks"]),
                conversions=int(bucket["conversions"]),
                ctr=derived["ctr"],
                cpc=derived["cpc"],
                cpa=derived["cpa"],
                roas=None,
                currency="USD",
                calculated_fields=[name for name in ("ctr", "cpc", "cpa") if derived[name] is not None],
            )
        )
    return rollups


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(user=Depends(_user)) -> AnalyticsOverview:
    """Aggregated performance across every campaign, platform, and reporting period."""

    init_analytics_db()
    with _database() as connection:
        campaigns = connection.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
        per_campaign = [_campaign_analytics(connection, campaign) for campaign in campaigns]
        return AnalyticsOverview(
            reporting_period_days=REPORTING_PERIOD_DAYS,
            active_campaigns=sum(1 for campaign in campaigns if campaign["status"] == "ACTIVE"),
            draft_campaigns=sum(1 for campaign in campaigns if campaign["status"] == "DRAFT"),
            pending_review_campaigns=sum(1 for campaign in campaigns if campaign["status"] in {"PENDING_REVIEW", "PUBLISHING"}),
            total_spend=round(sum(item.totals["spend"] for item in per_campaign), 2),
            total_impressions=sum(int(item.totals["impressions"]) for item in per_campaign),
            total_clicks=sum(int(item.totals["clicks"]) for item in per_campaign),
            total_conversions=sum(int(item.totals["conversions"]) for item in per_campaign),
            currency="USD",
            calculated_fields=list(CALCULATED_METRICS),
            platforms=_platform_rollup(per_campaign),
            campaigns=per_campaign,
        )


@router.get("/platforms", response_model=list[PlatformBreakdown])
def platform_analytics(user=Depends(_user)) -> list[PlatformBreakdown]:
    """Performance rolled up by advertising platform."""

    return analytics_overview(user=user).platforms


@router.get("/campaigns/{campaign_id}/metrics", response_model=list[MetricPoint])
def campaign_metric_points(campaign_id: int, user=Depends(_user)) -> list[MetricPoint]:
    """Raw metric points with source, currency, and reporting period retained."""

    init_analytics_db()
    with _database() as connection:
        _owned_campaign(connection, campaign_id, user["id"])
        rows = connection.execute(
            "SELECT metric, value, currency, source, calculated, reported_at FROM campaign_metrics WHERE campaign_id = ? ORDER BY metric",
            (campaign_id,),
        ).fetchall()
        return [
            MetricPoint(
                metric=row["metric"],
                value=float(row["value"]),
                currency=row["currency"],
                source=row["source"],
                calculated=bool(row["calculated"]),
                reported_at=row["reported_at"],
            )
            for row in rows
        ]


@router.post("/campaigns/{campaign_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def request_metric_sync(campaign_id: int, user=Depends(_user)) -> dict[str, str]:
    """Queue a metric synchronization for a published campaign."""

    init_analytics_db()
    with _database() as connection:
        _owned_campaign(connection, campaign_id, user["id"])
        submitted = connection.execute("SELECT 1 FROM platform_campaigns WHERE campaign_id = ? LIMIT 1", (campaign_id,)).fetchone()
    if submitted is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Publish the campaign before syncing metrics")
    get_queue().enqueue(campaign_id, lambda: sync_campaign_metrics(campaign_id, user["id"]))
    return {"campaign_id": str(campaign_id), "status": "QUEUED", "message": "Metric synchronization queued"}


@router.get("/campaigns/{campaign_id}", response_model=CampaignAnalytics)
def campaign_analytics(campaign_id: int, user=Depends(_user)) -> CampaignAnalytics:
    """Per-platform performance for one campaign."""

    init_analytics_db()
    with _database() as connection:
        campaign = _owned_campaign(connection, campaign_id, user["id"])
        return _campaign_analytics(connection, campaign)