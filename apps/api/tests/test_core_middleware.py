"""Tests for the cross-cutting request middleware.

The middleware is what makes a request traceable and what keeps an unauthenticated
caller from hammering the credential endpoints, so both behaviours are pinned
here.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import middleware
from app.core.middleware import (
    AUTH_RATE_LIMIT,
    DEFAULT_RATE_LIMIT,
    EXEMPT_PATHS,
    REQUEST_ID_HEADER,
    RateLimit,
    install_middleware,
)


def test_a_request_carries_a_request_id() -> None:
    """Every response can be joined back to a request."""
    app = FastAPI()
    install_middleware(app)

    @app.get("/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        response = client.get("/probe")

    assert response.headers[REQUEST_ID_HEADER]


def test_a_supplied_request_id_is_kept() -> None:
    """A caller that already has a request id keeps it, so traces stay joined."""
    app = FastAPI()
    install_middleware(app)

    @app.get("/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        response = client.get("/probe", headers={REQUEST_ID_HEADER: "req-abc"})

    assert response.headers[REQUEST_ID_HEADER] == "req-abc"


def test_security_headers_are_present() -> None:
    """The browser is told not to sniff, frame or embed the API."""
    app = FastAPI()
    install_middleware(app)

    @app.get("/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        response = client.get("/probe")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_the_rate_limiter_counts_within_a_window() -> None:
    """A caller is allowed up to the limit and then refused."""
    limiter = RateLimit(limit=2, window_seconds=60)

    assert limiter.check("client")
    assert limiter.check("client")
    assert not limiter.check("client")


def test_the_rate_limiter_separates_callers() -> None:
    """One caller exhausting the limit does not affect another."""
    limiter = RateLimit(limit=1, window_seconds=60)

    assert limiter.check("first")
    assert not limiter.check("first")
    assert limiter.check("second")


def test_the_rate_limiter_can_be_reset() -> None:
    """Resetting clears the window, which is what the test fixture needs."""
    limiter = RateLimit(limit=1, window_seconds=60)
    limiter.check("client")

    limiter.reset()

    assert limiter.check("client")


def test_the_auth_routes_have_the_stricter_limit() -> None:
    """Credential stuffing is the usual target, so the limit is tighter."""
    assert AUTH_RATE_LIMIT < DEFAULT_RATE_LIMIT


def test_the_health_endpoints_are_exempt() -> None:
    """A load balancer polling health must not be reported as an outage."""
    assert "/api/health" in EXEMPT_PATHS
    assert "/api/ready" in EXEMPT_PATHS


def test_an_exhausted_client_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The limiter answers with a refusal once the window is used up."""
    monkeypatch.setattr(middleware, "DEFAULT_RATE_LIMIT", 2)
    app = FastAPI()
    install_middleware(app)

    @app.get("/api/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        assert client.get("/api/probe").status_code == 200
        assert client.get("/api/probe").status_code == 200
        refused = client.get("/api/probe")

    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "rate_limited"


def test_the_limiter_only_covers_the_api_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """A path outside the API is not part of the request budget."""
    monkeypatch.setattr(middleware, "DEFAULT_RATE_LIMIT", 1)
    app = FastAPI()
    install_middleware(app)

    @app.get("/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        for _ in range(5):
            assert client.get("/probe").status_code == 200


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    """Keep the process-wide limiter from leaking between tests."""
    middleware.rate_limit.reset()
    yield
    middleware.rate_limit.reset()
