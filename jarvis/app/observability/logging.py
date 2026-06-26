"""Structured (JSON) logging (README §13).

One JSON object per line: timestamp, level, logger, message, plus any structured
fields passed via ``extra=`` (e.g. ``trace_id``, ``cost``, ``latency_ms``). No
third-party dependency — just the stdlib ``logging`` module with a JSON formatter.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

__all__ = ["JsonFormatter", "configure_logging"]

# Standard LogRecord attributes; anything else on the record is a structured extra.
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(
    *,
    level: int = logging.INFO,
    stream: TextIO | None = None,
    name: str | None = None,
) -> None:
    """Attach a JSON handler. ``name=None`` configures the root logger (production);
    a named logger is isolated (``propagate=False``) and is handy for tests."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())

    target = logging.getLogger(name)
    target.handlers = [handler]
    target.setLevel(level)
    if name is not None:
        target.propagate = False
