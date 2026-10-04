"""Shared fixtures for API tests."""

import json
import logging

import pytest

from app.logging_config import JsonFormatter
from app.middleware import rate_limit


class LogCapture(logging.Handler):
    """Collect structured log lines so tests can assert on the JSON payload."""

    def __init__(self) -> None:
        super().__init__()
        self.formatter = JsonFormatter()
        self.records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(json.loads(self.formatter.format(record)))

    def messages(self) -> list[str]:
        """Return the emitted messages in order."""

        return [record["message"] for record in self.records]

    def find(self, message: str) -> dict:
        """Return the most recent record for ``message``."""

        matches = [record for record in self.records if record["message"] == message]
        assert matches, f"no log record with message {message!r} in {self.messages()}"
        return matches[-1]


@pytest.fixture()
def captured_logs() -> LogCapture:
    """Attach a capture handler to the adpilot logger tree for one test."""

    capture = LogCapture()
    logger = logging.getLogger("adpilot")
    logger.addHandler(capture)
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    yield capture
    logger.removeHandler(capture)
    logger.setLevel(previous_level)


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Keep the process-wide rate limiter from leaking between tests."""

    rate_limit.reset()
    yield
    rate_limit.reset()
