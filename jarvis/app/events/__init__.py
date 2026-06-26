"""The in-process event bus (README §3.6).

The event *types* live in ``jarvis.domain.events`` (so producers can publish
without depending on ``app``); they are re-exported here for convenience. The
``EventBus`` mechanism lives here and satisfies the ``EventPublisher`` port.
"""

from jarvis.app.events.bus import EventBus, EventHandler
from jarvis.domain.events import (
    Event,
    JobCompleted,
    JobFailed,
    JobStarted,
    ResponseReady,
    UtteranceReceived,
)

__all__ = [
    "Event",
    "EventBus",
    "EventHandler",
    "JobCompleted",
    "JobFailed",
    "JobStarted",
    "ResponseReady",
    "UtteranceReceived",
]
