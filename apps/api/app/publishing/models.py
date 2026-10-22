"""Response models for the publishing service.

The models live apart from the routes so that the route module stays about
*behaviour* — what happens when a campaign is published — and the shapes it
returns live in one place that the job routes and the campaign routes both
read.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

#: The states a publishing job moves through.
JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]


class PublishingJobResponse(BaseModel):
    """One attempt to publish a campaign to a platform."""

    id: int
    campaign_id: int
    status: JobStatus
    attempt: int
    error: str | None
    created_at: str
    updated_at: str


class PlatformCampaignResponse(BaseModel):
    """The state of a campaign on one advertising platform."""

    id: int
    platform: str
    external_campaign_id: str
    status: str
    detail: str | None
    updated_at: str


class PublishResponse(BaseModel):
    """The result of asking for a campaign to be published."""

    campaign_id: int
    status: str
    job: PublishingJobResponse
    message: str


class CampaignStatusResponse(BaseModel):
    """The status of a campaign, with its platform states and recent jobs."""

    campaign_id: int
    status: str
    updated_at: str
    platforms: list[PlatformCampaignResponse]
    jobs: list[PublishingJobResponse]
