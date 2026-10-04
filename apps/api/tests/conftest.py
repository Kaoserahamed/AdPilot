"""Shared fixtures for API tests."""

import pytest

from app.middleware import rate_limit


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Keep the process-wide rate limiter from leaking between tests."""

    rate_limit.reset()
    yield
    rate_limit.reset()