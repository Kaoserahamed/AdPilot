"""Tests for the service configuration.

The settings are read from the environment, so the defaults are part of the
contract: a deployment that sets nothing must still get a working service.
"""

from __future__ import annotations

from app.core import settings


def test_the_session_cookie_has_a_stable_name() -> None:
    """The client and the server have to agree on the cookie name."""
    assert settings.session_cookie_name == "adpilot_session"


def test_a_session_lasts_a_week_by_default() -> None:
    """A week is long enough to be usable and short enough to be revoked."""
    assert settings.session_ttl_days == 7


def test_an_access_token_lasts_an_hour_by_default() -> None:
    """A script's token is short lived, so a leak expires on its own."""
    assert settings.access_token_expire_minutes == 60


def test_the_database_path_is_configurable() -> None:
    """The database lives on a volume in production, not in the image."""
    assert settings.auth_db_path


def test_the_web_origin_is_configurable() -> None:
    """The browser origin the API accepts is part of the deployment config."""
    assert settings.web_origin


def test_live_external_apis_are_off_by_default() -> None:
    """The sandbox adapters are the default; live clients are opt-in."""
    assert settings.live_external_apis is False
