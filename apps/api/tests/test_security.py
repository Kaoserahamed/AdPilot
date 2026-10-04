"""Security hardening tests (PRD §11.1, §14)."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware import (
    AUTH_RATE_LIMIT,
    DEFAULT_RATE_LIMIT,
    REQUEST_ID_HEADER,
    RateLimit,
    rate_limit,
)


@pytest.fixture()
def hardened_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "hardening.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        yield client


# --- Rate limiter unit behaviour --------------------------------------------


def test_rate_limit_allows_up_to_the_limit() -> None:
    limiter = RateLimit(limit=3, window_seconds=60)
    assert all(limiter.check("client", 3) for _ in range(3))
    assert limiter.check("client", 3) is False


def test_rate_limit_is_per_key() -> None:
    limiter = RateLimit(limit=1, window_seconds=60)
    assert limiter.check("a", 1) is True
    assert limiter.check("b", 1) is True
    assert limiter.check("a", 1) is False


def test_rate_limit_window_expires() -> None:
    limiter = RateLimit(limit=1, window_seconds=1)
    assert limiter.check("a", 1) is True
    assert limiter.check("a", 1) is False
    time.sleep(1.1)
    assert limiter.check("a", 1) is True


# --- Headers and request ids -------------------------------------------------


def test_responses_carry_a_request_id(hardened_client: TestClient) -> None:
    assert hardened_client.get("/api/health").headers[REQUEST_ID_HEADER]


def test_supplied_request_id_is_echoed(hardened_client: TestClient) -> None:
    response = hardened_client.get("/api/health", headers={REQUEST_ID_HEADER: "abc123"})
    assert response.headers[REQUEST_ID_HEADER] == "abc123"


def test_security_headers_are_present(hardened_client: TestClient) -> None:
    headers = hardened_client.get("/api/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"


def test_security_headers_on_error_responses(hardened_client: TestClient) -> None:
    response = hardened_client.get("/api/v1/campaigns")
    assert response.status_code == 401
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# --- Rate limiting in practice ----------------------------------------------


def test_auth_route_rate_limit_is_enforced(hardened_client: TestClient) -> None:
    statuses = [hardened_client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever12"}).status_code for _ in range(AUTH_RATE_LIMIT + 5)]
    assert 429 in statuses


def test_rate_limited_response_explains_itself(hardened_client: TestClient) -> None:
    for _ in range(AUTH_RATE_LIMIT + 1):
        response = hardened_client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever12"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["error"]["code"] == "rate_limited"


def test_health_endpoint_is_never_rate_limited(hardened_client: TestClient) -> None:
    statuses = [hardened_client.get("/api/health").status_code for _ in range(DEFAULT_RATE_LIMIT + 20)]
    assert set(statuses) == {200}


def test_rate_limit_is_per_route(hardened_client: TestClient) -> None:
    for _ in range(AUTH_RATE_LIMIT + 2):
        hardened_client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever12"})
    assert hardened_client.get("/api/health").status_code == 200


# --- Errors ------------------------------------------------------------------


def test_errors_do_not_leak_internals(hardened_client: TestClient) -> None:
    response = hardened_client.get("/api/v1/campaigns/999999")
    assert response.status_code == 401
    body = response.text.lower()
    for leak in ("traceback", "sqlite", "select", "sql", "file \""):
        assert leak not in body


def test_unknown_route_returns_structured_error(hardened_client: TestClient) -> None:
    response = hardened_client.get("/api/v1/does-not-exist")
    assert response.status_code == 404