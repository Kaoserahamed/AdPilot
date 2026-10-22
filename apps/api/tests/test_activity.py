"""Tests for the activity log endpoint.

The activity log is what an advertiser reads to see what happened to a
campaign, so it has to be scoped to the caller and it has to be ordered.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def activity_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a client with an isolated authentication database."""
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "activity.db"))
    with TestClient(app) as client:
        yield client


def _register(client: TestClient, email: str = "alex@example.com") -> None:
    """Register an account so the caller is authenticated."""
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Alex Morgan", "email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201


def test_the_activity_log_requires_a_session(activity_client: TestClient) -> None:
    """The log is not public."""
    response = activity_client.get("/api/v1/activity")

    assert response.status_code == 401


def test_the_activity_log_is_empty_for_a_new_account(activity_client: TestClient) -> None:
    """An account that has done nothing sees nothing."""
    _register(activity_client)

    response = activity_client.get("/api/v1/activity")

    assert response.status_code == 200
    assert response.json() == []


def test_creating_a_campaign_is_recorded(activity_client: TestClient) -> None:
    """The log shows what the caller did."""
    _register(activity_client)
    activity_client.post(
        "/api/v1/campaigns",
        json={
            "name": "Spring sale",
            "product": "Shoes",
            "description": "The very best shoes",
            "objective": "traffic",
            "location": "New York",
            "audience": "Everyone",
            "budget": 100,
            "duration_days": 7,
            "landing_page": "https://example.com",
            "tone": "friendly",
            "offer": "10% off",
            "platforms": ["Meta"],
        },
    )

    response = activity_client.get("/api/v1/activity")

    assert response.status_code == 200
    entries = response.json()
    assert entries
    assert entries[0]["action"] == "CAMPAIGN_CREATED"


def test_the_log_is_scoped_to_the_caller(activity_client: TestClient) -> None:
    """One advertiser never sees another advertiser's activity."""
    _register(activity_client, "alex@example.com")
    activity_client.post(
        "/api/v1/campaigns",
        json={
            "name": "Spring sale",
            "product": "Shoes",
            "description": "The very best shoes",
            "objective": "traffic",
            "location": "New York",
            "audience": "Everyone",
            "budget": 100,
            "duration_days": 7,
            "landing_page": "https://example.com",
            "tone": "friendly",
            "offer": "10% off",
            "platforms": ["Meta"],
        },
    )
    activity_client.post("/api/v1/auth/logout")
    _register(activity_client, "sam@example.com")

    response = activity_client.get("/api/v1/activity")

    assert response.status_code == 200
    assert response.json() == []
