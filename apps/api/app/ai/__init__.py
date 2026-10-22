"""AI service: campaign copy generation and the analytics assistant.

Two capabilities live here, and they are separate on purpose:

* **Copy generation** (``routes``) — generate, regenerate, edit and store the
  ad copy for a campaign. A generation is a stored artifact, so it can be
  compared, edited and reused.
* **The analytics assistant** (``analytics_ai``) — answer a question about a
  campaign's performance. It is read-only and grounded: it collects facts from
  the analytics service and refuses to claim anything those facts do not
  support.

The assistant depends on the analytics service for facts. The analytics service
does not depend on the assistant, so there is no cycle between them.
"""

from app.ai.analytics_ai import (
    AnalyzeRequest,
    AnswerResponse,
    MetricLine,
    build_summary,
    collect_facts,
    verify_supported,
)
from app.ai.analytics_ai import (
    router as analytics_ai_router,
)
from app.ai.routes import (
    AIProvider,
    AudienceProfile,
    CampaignContent,
    EditAction,
    EditRequest,
    GeminiProvider,
    GenerateRequest,
    GenerationResponse,
    GoogleAd,
    Messaging,
    MetaAd,
    OpenAIProvider,
    Platform,
    SandboxProvider,
    Strategy,
    get_provider,
    init_ai_db,
    router,
)
from app.core import settings

__all__ = [
    "settings",
    "AIProvider",
    "AnalyzeRequest",
    "AnswerResponse",
    "AudienceProfile",
    "CampaignContent",
    "EditAction",
    "EditRequest",
    "GeminiProvider",
    "GenerateRequest",
    "GenerationResponse",
    "GoogleAd",
    "Messaging",
    "MetaAd",
    "MetricLine",
    "OpenAIProvider",
    "Platform",
    "SandboxProvider",
    "Strategy",
    "analytics_ai_router",
    "build_summary",
    "collect_facts",
    "get_provider",
    "init_ai_db",
    "router",
    "verify_supported",
]
