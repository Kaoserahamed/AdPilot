"""Tests for the structured logging helpers.

The point of the JSON formatter is that a log line can be joined back to the
request that produced it, so the request id has to be present on every record.
"""

from __future__ import annotations

import json
import logging

from app.core.logging_config import (
    JsonFormatter,
    bind_request_id,
    configure_logging,
    get_logger,
    request_id_var,
)


def test_a_record_is_rendered_as_one_json_object() -> None:
    """Each record is a single line of JSON, so a log stays greppable."""
    formatter = JsonFormatter()
    record = logging.LogRecord("adpilot.test", logging.INFO, __file__, 1, "hello", None, None)

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "adpilot.test"


def test_every_record_carries_the_request_id() -> None:
    """A line can always be joined back to its request."""
    formatter = JsonFormatter()
    record = logging.LogRecord("adpilot.test", logging.INFO, __file__, 1, "hello", None, None)

    payload = json.loads(formatter.format(record))

    assert payload["request_id"] == request_id_var.get()


def test_a_bound_request_id_reaches_the_record() -> None:
    """The ambient request id is what the formatter emits."""
    formatter = JsonFormatter()
    record = logging.LogRecord("adpilot.test", logging.INFO, __file__, 1, "hello", None, None)

    bind_request_id("req-123")
    payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "req-123"


def test_an_explicit_request_id_wins_over_the_ambient_one() -> None:
    """A record that states its own request id is not overridden."""
    formatter = JsonFormatter()
    record = logging.LogRecord("adpilot.test", logging.INFO, __file__, 1, "hello", None, None)
    record.request_id = "explicit"

    bind_request_id("ambient")
    payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "explicit"


def test_a_structured_field_survives_into_the_payload() -> None:
    """A field passed through ``extra`` is emitted as a queryable field."""
    formatter = JsonFormatter()
    record = logging.LogRecord("adpilot.test", logging.INFO, __file__, 1, "hello", None, None)
    record.job_id = 42

    payload = json.loads(formatter.format(record))

    assert payload["job_id"] == 42


def test_a_logger_is_namespaced_under_adpilot() -> None:
    """Every logger lives under one tree, so a level can be set for all of it."""
    assert get_logger("jobs").name == "adpilot.jobs"
    assert get_logger("adpilot.already").name == "adpilot.already"


def test_an_unknown_level_falls_back_to_info() -> None:
    """A typo in the environment must not stop the service from starting."""
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    try:
        configure_logging("not-a-level")
        assert root.level == logging.INFO
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)


def test_configuring_logging_replaces_the_handlers() -> None:
    """Repeated calls cannot end up duplicating every line."""
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    try:
        configure_logging("DEBUG")
        configure_logging("DEBUG")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)
