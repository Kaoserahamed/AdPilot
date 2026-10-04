"""Structured JSON logging for the API service.

The service already generates a request id per request (see :mod:`.middleware`),
but plain ``logging.basicConfig`` output dropped that field on the floor and left
operators grepping unstructured text. This module renders each record as a single
JSON object so request id, path, and status are queryable fields.

Design notes:

- No third-party logging framework is used. The stdlib is enough here, and it
  keeps the dependency surface small for a service whose supply chain is audited.
- ``request_id`` is attached through a :class:`contextvars.ContextVar` rather than
  by threading a logger argument through every call site. ContextVar propagates
  across ``await`` boundaries, so a log emitted deep inside a request handler
  still carries the correct id even under concurrency.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

# Populated per request by the middleware and read by the formatter.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

#: Keys present on every ``LogRecord``; anything else came from ``extra`` and is
#: therefore a structured field worth emitting.
_RESERVED_RECORD_KEYS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "message", "module",
        "msecs", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "taskName", "thread", "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render a log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # Present on every record so a log line can always be joined back to
            # a request, even when the handler never attached one explicitly.
            "request_id": request_id_var.get(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            # `request_id` passed via `extra` wins over the ambient context.
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger.

    Existing handlers are replaced so repeated calls (for example on reload)
    cannot end up duplicating every line.
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())


def bind_request_id(request_id: str) -> Any:
    """Bind a request id to the current context and return the reset token."""

    return request_id_var.set(request_id)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the ``adpilot`` hierarchy."""

    return logging.getLogger(f"adpilot.{name}" if not name.startswith("adpilot") else name)