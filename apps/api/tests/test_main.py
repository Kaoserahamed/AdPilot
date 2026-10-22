"""Tests for the application wiring.

The API is assembled from one router per service. A router that is added but
not mounted — or mounted on the wrong prefix — would pass every unit test and
still break the product, so the wiring is asserted directly.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_the_openapi_schema_builds() -> None:
    """The schema is generated from the routes, so it building means the app is sound."""
    schema = app.openapi()

    assert schema["openapi"].startswith("3.")


def test_every_service_router_is_mounted() -> None:
    """Each service contributes its paths to the API."""
    paths = set(app.openapi()["paths"])

    for prefix in (
        "/api/v1/auth/register",
        "/api/v1/campaigns",
        "/api/v1/creatives",
        "/api/v1/ai/generate-campaign",
        "/api/v1/analytics/overview",
        "/api/v1/platforms",
        "/api/v1/publishing/jobs",
        "/api/v1/activity",
        "/api/v1/monitoring/snapshot",
    ):
        assert prefix in paths


def test_the_health_endpoints_are_public() -> None:
    """A load balancer can reach them without a credential."""
    with TestClient(app) as client:
        health = client.get("/api/health")
        ready = client.get("/api/ready")

    assert health.status_code == 200
    assert ready.status_code == 200


def test_the_ready_probe_reports_its_configuration() -> None:
    """The readiness probe says which environment and which integrations it is in."""
    with TestClient(app) as client:
        payload = client.get("/api/ready").json()

    assert payload["status"] == "ready"
    assert payload["integrations"] in {"live", "sandbox"}
    assert payload["ai_provider"]


def test_an_unknown_route_is_a_not_found() -> None:
    """An unknown path is a clean 404, not a stack trace."""
    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
