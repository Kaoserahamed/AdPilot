"""AI analytics assistant (PRD §8.20).

The assistant answers questions about retrieved campaign data. Its factual
source is the stored metrics and their provenance, never free-form invention.

That constraint is enforced, not just requested of the model:

* the assistant receives only a facts document built from stored metric rows;
* every figure it reports is checked against that document, and any figure that
  cannot be traced back to a stored value is rejected before it reaches the
  user;
* metrics that do not exist are reported as unavailable rather than estimated.

The model formats and explains; it never supplies numbers.
"""

import re
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from .analytics import CALCULATED_METRICS, REPORTING_PERIOD_DAYS, init_analytics_db
from .analytics import _database as _analytics_database
from .auth import _current_user
from .config import settings
from .db import get_connection as _database
from .db import owned_campaign as _owned_campaign

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

QuestionKind = Literal["summary", "period", "comparison", "custom"]


class AnalyzeRequest(BaseModel):
    campaign_id: int
    question: Annotated[str | None, Field(max_length=1000)] = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class MetricLine(BaseModel):
    metric: str
    value: float
    currency: str
    source: str
    calculated: bool
    reported_at: str


class AnswerResponse(BaseModel):
    campaign_id: int
    question: str
    period_start: str
    period_end: str
    summary: str
    highlights: list[str]
    facts: list[MetricLine]
    data_complete: bool
    unavailable: list[str]
    provider: str
    model: str


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def collect_facts(campaign_id: int, user_id: int) -> tuple[list[MetricLine], str, str]:
    """Read stored metric rows with their provenance. Returns facts and period."""

    init_analytics_db()
    with _analytics_database() as connection:
        _owned_campaign(connection, campaign_id, user_id)
        rows = connection.execute(
            "SELECT metric, value, currency, source, calculated, reported_at, period_start, period_end FROM campaign_metrics WHERE campaign_id = ? ORDER BY metric",
            (campaign_id,),
        ).fetchall()
    if not rows:
        return ([], "", "")
    facts = [
        MetricLine(
            metric=row["metric"],
            value=float(row["value"]),
            currency=row["currency"],
            source=row["source"],
            calculated=bool(row["calculated"]),
            reported_at=row["reported_at"],
        )
        for row in rows
    ]
    return (facts, min(row["period_start"] for row in rows), max(row["period_end"] for row in rows))


def facts_document(campaign: sqlite3.Row, facts: list[MetricLine], period_start: str, period_end: str) -> dict[str, object]:
    """The only factual source the assistant is allowed to use.

    Built for an external model provider: it is the exact payload that would be
    sent if a provider that consumes prompts were configured. The built-in
    provider does not need it because ``build_summary`` reads the same facts
    directly, so the document is assembled but not consumed on that path.
    """

    return {
        "campaign": {
            "id": campaign["id"],
            "name": campaign["name"],
            "objective": campaign["objective"],
            "status": campaign["status"],
            "budget": campaign["budget"],
        },
        "reporting_period": {"start": period_start, "end": period_end, "days": REPORTING_PERIOD_DAYS},
        "metrics": [fact.model_dump() for fact in facts],
    }


def _format_number(value: float, metric: str) -> str:
    if metric in CALCULATED_METRICS:
        return f"{value:g}"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"
def build_summary(campaign: sqlite3.Row, facts: list[MetricLine], period_start: str, period_end: str) -> tuple[str, list[str]]:
    """Deterministic summary built only from stored values."""

    by_metric = {fact.metric: fact for fact in facts}
    lines = [f"{campaign['name']} reporting period {period_start[:10]} to {period_end[:10]}."]
    highlights: list[str] = []
    for metric in ("spend", "impressions", "clicks", "conversions"):
        fact = by_metric.get(metric)
        if fact is None:
            continue
        prefix = f"{fact.currency} " if metric == "spend" else ""
        statement = f"{metric.capitalize()}: {prefix}{_format_number(fact.value, metric)}"
        lines.append(f"{statement} (source: {fact.source}).")
        highlights.append(statement)
    derived = [fact for fact in facts if fact.metric in CALCULATED_METRICS]
    if derived:
        highlights.append("Derived by AdPilot: " + ", ".join(f"{fact.metric} {_format_number(fact.value, fact.metric)}" for fact in derived) + ".")
    else:
        highlights.append("No derived ratios are available for this period.")
    return (" ".join(lines), highlights)


ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _numbers_in(text: str) -> set[str]:
    def normalise(token: str) -> str:
        token = token.replace(",", "").rstrip(".")
        stripped = token.lstrip("0")
        return stripped or "0"

    return {normalise(match) for match in re.findall(r"\d[\d,]*\.?\d*", ISO_DATE.sub(" ", text))}


def verify_supported(summary: str, highlights: list[str], facts: list[MetricLine], allowed: set[str] | None = None) -> None:
    """Reject any figure in the answer that cannot be traced to a stored value.

    This is the guard that makes "the AI must not invent missing metrics" an
    enforced property rather than a prompt instruction. Dates are stripped
    before comparison, and ``allowed`` carries non-metric numbers such as the
    campaign id and budget.
    """

    known: set[str] = {"0", "1"} | {token for value in (allowed or set()) for token in _numbers_in(str(value))}
    for fact in facts:
        known.add(_numbers_in(f"{fact.value}").pop() if _numbers_in(f"{fact.value}") else str(fact.value))
        known.add(str(int(fact.value)) if float(fact.value).is_integer() else f"{fact.value:g}")
        formatted = _numbers_in(_format_number(fact.value, fact.metric))
        if formatted:
            known.add(formatted.pop())
    for token in _numbers_in(summary) | {token for line in highlights for token in _numbers_in(line)}:
        if token not in known:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Assistant response referenced a figure that is not present in stored metrics",
            )


@router.post("/analyze", response_model=AnswerResponse)
def analyze_performance(payload: AnalyzeRequest, user=Depends(_user)) -> AnswerResponse:
    """Answer a question about a campaign using only retrieved campaign data."""

    from .ai import get_provider

    provider = get_provider()
    init_analytics_db()
    with _database() as connection:
        campaign = _owned_campaign(connection, payload.campaign_id, user["id"])
        campaign_data = dict(campaign)

    facts, period_start, period_end = collect_facts(payload.campaign_id, user["id"])
    if not facts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No synced metrics are available for this campaign yet. Publish it and sync metrics first.",
        )

    # Assembled for external providers; the built-in path builds its summary
    # from the same facts directly, so the result is intentionally unused here.
    _document = facts_document(campaign_data, facts, period_start, period_end)
    summary, highlights = build_summary(campaign_data, facts, period_start, period_end)
    if payload.question:
        highlights.insert(0, f"Question: {payload.question}")
    verify_supported(summary, highlights, facts, allowed={campaign_data["id"], campaign_data["budget"]})

    unavailable = [
        metric
        for metric in ("spend", "impressions", "reach", "clicks", "conversions", "revenue")
        if metric not in {fact.metric for fact in facts}
    ]
    return AnswerResponse(
        campaign_id=payload.campaign_id,
        question=payload.question or "Summarize this campaign.",
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        highlights=highlights,
        facts=facts,
        data_complete=not unavailable,
        unavailable=unavailable,
        provider=provider.name,
        model=provider.model,
    )
