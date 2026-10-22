"""Publishing service: platform adapters, campaign publishing, jobs and the activity log.

Four things belong to this service, and they are grouped because a publish
touches all of them:

* **Platform adapters** (``platforms``) — the sandbox and live adapters for
  Meta, Google and YouTube, and the connected platform accounts.
* **Publishing** (``routes``) — the queued job that pushes a campaign to its
  platforms, the campaign status and pause controls, and the job list and
  retry path.
* **Response models** (``models``) — the shapes publishing returns, kept apart
  from the routes so the route module stays about behaviour.
* **The activity log** (``activity``) — the record of what happened to a
  campaign, written by the publishing flow and read by the dashboard.

The analytics service reads the connected accounts, so it depends on this
package; this package does not depend on the analytics service.
"""

from app.core import settings
from app.publishing.activity import (
    ActivityEntry,
)
from app.publishing.activity import (
    router as activity_router,
)
from app.publishing.models import (
    CampaignStatusResponse,
    JobStatus,
    PlatformCampaignResponse,
    PublishingJobResponse,
    PublishResponse,
)
from app.publishing.platforms import (
    AccountResponse,
    AdPlatformAdapter,
    ConnectRequest,
    GoogleAdsAdapter,
    MetaAdapter,
    PlatformCapabilities,
    PlatformOperationResult,
    SandboxAdapter,
    YouTubeAdapter,
    _decrypt_token,
    _encrypt_token,
    accounts_router,
    get_adapter,
    init_platform_db,
)
from app.publishing.platforms import (
    router as platforms_router,
)
from app.publishing.routes import (
    init_publishing_db,
    jobs_router,
    router,
)

__all__ = [
    "settings",
    "AccountResponse",
    "ActivityEntry",
    "AdPlatformAdapter",
    "CampaignStatusResponse",
    "ConnectRequest",
    "GoogleAdsAdapter",
    "JobStatus",
    "MetaAdapter",
    "PlatformCampaignResponse",
    "PlatformCapabilities",
    "PlatformOperationResult",
    "PublishResponse",
    "PublishingJobResponse",
    "SandboxAdapter",
    "YouTubeAdapter",
    "_decrypt_token",
    "_encrypt_token",
    "accounts_router",
    "activity_router",
    "get_adapter",
    "init_platform_db",
    "init_publishing_db",
    "jobs_router",
    "platforms_router",
    "router",
]
