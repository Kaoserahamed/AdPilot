"""Cross-cutting request handling: request ids, structured errors, headers, rate limiting.

Implements PRD §11.1 (validate all requests, rate limiting, restricted CORS,
audit logs) and PRD §14 (errors carry a user message, internal code, request id,
and timestamp, and never expose internal detail).

Rate limiting is an in-process fixed-window counter keyed by client and route
group. That is deliberate for the MVP: it needs no Redis, and it is honest about
its limits. A multi-process deployment must move this to shared storage, which
is noted in the README rather than implied to be cluster-safe.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import bind_request_id, get_logger, request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# Requests per window per client. Auth routes are stricter because they are the
# usual target of credential stuffing.
DEFAULT_RATE_LIMIT = 120
AUTH_RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60

logger = get_logger("request")


@dataclass
class RateLimit:
    """Fixed-window counter shared across requests."""

    limit: int = DEFAULT_RATE_LIMIT
    window_seconds: int = RATE_WINDOW_SECONDS
    hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def check(self, key: str, limit: int | None = None) -> bool:
        """Record a hit and report whether the caller is within the limit."""

        effective = limit if limit is not None else self.limit
        now = time.monotonic()
        bucket = self.hits[key]
        bucket.append(now)
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        return len(bucket) <= effective

    def reset(self) -> None:
        self.hits.clear()


rate_limit = RateLimit()


# Health and readiness endpoints are polled by load balancers, so they are
# exempt: rate limiting them would report a false outage during a traffic spike.
EXEMPT_PATHS = frozenset({"/api/health", "/api/ready"})


def _client_key(request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{request.url.path}"


def _is_auth_route(path: str) -> bool:
    return path.startswith("/api/v1/auth")


def _error_payload(request: Request, code: str, message: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    }


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, emit a structured access log, and add security headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id
        # Bind for the whole request so any handler that logs without passing an
        # explicit request_id still has it attached by the formatter.
        token = bind_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_error", extra={"path": request.url.path, "method": request.method})
            response = JSONResponse(status_code=500, content=_error_payload(request, "internal_error", "Something went wrong. Please try again."))
        finally:
            request_id_var.reset(token)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(elapsed_ms, 2),
            },
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject callers that exceed the per-route request budget."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or not request.url.path.startswith("/api/") or request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        key = _client_key(request)
        limit = AUTH_RATE_LIMIT if _is_auth_route(request.url.path) else DEFAULT_RATE_LIMIT
        if not rate_limit.check(key, limit):
            logger.warning("rate_limited", extra={"path": request.url.path, "client": key, "limit": limit})
            return JSONResponse(
                status_code=429,
                content=_error_payload(request, "rate_limited", "Too many requests. Please slow down and try again shortly."),
                headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
            )
        return await call_next(request)


def install_middleware(app: FastAPI) -> None:
    """Register middleware. Order matters: rate limiting runs before routing."""

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)