"""Observability — structured logging, trace ids, and the event-logging observer.

Wired by the composition root: ``configure_logging`` at startup, ``new_trace_id``
injected into the use-case, and ``register_event_logging`` to log the lifecycle.
"""

from jarvis.app.observability.event_log import register_event_logging
from jarvis.app.observability.logging import JsonFormatter, configure_logging
from jarvis.app.observability.trace import new_trace_id

__all__ = [
    "JsonFormatter",
    "configure_logging",
    "new_trace_id",
    "register_event_logging",
]
