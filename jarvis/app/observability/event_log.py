"""An observer that logs every event as a structured line (README §3.6, §13).

This is the canonical example of the observer pattern: it subscribes to the bus
and is never in the request's critical path. Each event becomes one JSON log line
carrying the ``trace_id`` and the event's own fields (cost and latency on
``response.ready``), so a whole utterance is correlated by trace id.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from jarvis.app.events import EventBus
from jarvis.domain.events import Event

__all__ = ["register_event_logging"]

logger = logging.getLogger("jarvis.events")


async def _log_event(event: Event) -> None:
    logger.info("event %s", event.topic, extra={"topic": event.topic, **asdict(event)})


def register_event_logging(bus: EventBus) -> None:
    bus.subscribe("*", _log_event)
