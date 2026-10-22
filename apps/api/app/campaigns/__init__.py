"""Campaign service: campaign records and brief validation.

A campaign is the unit an advertiser works on. This package owns two things:

* **The campaign record** — its brief, budget, platforms and lifecycle status,
  with per-user ownership so one advertiser never sees another's campaigns.
* **Brief validation** — the checks a campaign must pass before it can be
  published, and the review confirmation that moves it to ``READY``.

Both are part of the same service because validation reads the campaign and
its attached creatives, and the review confirmation writes the campaign's
status back. Splitting them would mean splitting one transaction in two.
"""

from app.campaigns.routes import (
    CampaignCreate,
    CampaignResponse,
    CampaignStatus,
    CampaignUpdate,
    Objective,
    Platform,
    init_campaign_db,
    router,
)
from app.campaigns.validation import (
    PlatformCheck,
    ValidationResponse,
)
from app.campaigns.validation import (
    router as validation_router,
)
from app.core import settings

__all__ = [
    "settings",
    "CampaignCreate",
    "CampaignResponse",
    "CampaignStatus",
    "CampaignUpdate",
    "Objective",
    "Platform",
    "PlatformCheck",
    "ValidationResponse",
    "init_campaign_db",
    "router",
    "validation_router",
]
