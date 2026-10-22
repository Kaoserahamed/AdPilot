"""Analytics service: campaign metrics, derived KPIs and the monitoring snapshot.

This package owns everything that reports on what happened:

* **Campaign analytics** (``routes``) — reported metrics from the ad
  platforms, the KPIs derived from them (CTR, CPC, CPA, ROAS), the overview
  and the per-platform rollup.
* **Monitoring** (``monitoring``) — the operational snapshot of the queue
  depth, job outcomes and campaign statuses.

The publishing service is the only writer of performance data, and it writes
it through the shared database; the analytics service only reads. That is why
this package depends on publishing for the platform adapters but publishing
does not depend on it.
"""

from app.analytics.monitoring import (
    JobCounts,
    MonitoringSnapshot,
    build_snapshot,
)
from app.analytics.monitoring import (
    router as monitoring_router,
)
from app.analytics.routes import (
    CALCULATED_METRICS,
    PLATFORM_METRICS,
    REPORTING_PERIOD_DAYS,
    AnalyticsOverview,
    CampaignAnalytics,
    MetricPoint,
    PlatformBreakdown,
    _derive,
    init_analytics_db,
    router,
)
from app.core import settings

__all__ = [
    "settings",
    "CALCULATED_METRICS",
    "PLATFORM_METRICS",
    "REPORTING_PERIOD_DAYS",
    "AnalyticsOverview",
    "CampaignAnalytics",
    "JobCounts",
    "MetricPoint",
    "MonitoringSnapshot",
    "PlatformBreakdown",
    "_derive",
    "build_snapshot",
    "init_analytics_db",
    "monitoring_router",
    "router",
]
