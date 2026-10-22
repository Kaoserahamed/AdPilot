"""Shared infrastructure for the AdPilot API.

Configuration, the database handle, the job queue, structured logging and the
HTTP middleware are the pieces every service needs. Keeping them in one
package means a service module imports exactly one thing from the platform,
and it keeps the dependency direction one-way: services depend on core, never
the reverse.

The names below are re-exported so that a service writes
``from app.core import settings`` rather than reaching into a specific module
and coupling itself to that module's layout.
"""

from app.core.config import Settings, settings
from app.core.db import get_connection, owned_campaign
from app.core.jobs import (
    InlineQueue,
    JobCallable,
    JobQueue,
    RecordingQueue,
    ThreadQueue,
    get_queue,
    set_queue,
)
from app.core.logging_config import (
    JsonFormatter,
    bind_request_id,
    configure_logging,
    get_logger,
    request_id_var,
)
from app.core.middleware import (
    AUTH_RATE_LIMIT,
    DEFAULT_RATE_LIMIT,
    EXEMPT_PATHS,
    RATE_WINDOW_SECONDS,
    REQUEST_ID_HEADER,
    SECURITY_HEADERS,
    RateLimit,
    RateLimitMiddleware,
    RequestContextMiddleware,
    install_middleware,
    rate_limit,
)

__all__ = [
    "AUTH_RATE_LIMIT",
    "DEFAULT_RATE_LIMIT",
    "EXEMPT_PATHS",
    "InlineQueue",
    "JobCallable",
    "JobQueue",
    "JsonFormatter",
    "RATE_WINDOW_SECONDS",
    "REQUEST_ID_HEADER",
    "RateLimit",
    "RateLimitMiddleware",
    "RecordingQueue",
    "RequestContextMiddleware",
    "SECURITY_HEADERS",
    "Settings",
    "ThreadQueue",
    "bind_request_id",
    "configure_logging",
    "get_connection",
    "get_logger",
    "get_queue",
    "install_middleware",
    "owned_campaign",
    "rate_limit",
    "request_id_var",
    "set_queue",
    "settings",
]
