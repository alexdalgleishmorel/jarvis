"""Domain events — the vocabulary published across the request lifecycle (§6).

These live in the domain so any producer (a use-case, an adapter) can publish
them without depending on ``app``. The concrete bus that delivers them is
infrastructure in ``jarvis.app.events`` behind the ``EventPublisher`` port.

Every stage publishes one of these; observers (logging, the future dashboard
live view) subscribe and are never in the request's critical path. Each event
carries the per-utterance ``trace_id`` so a whole flow can be correlated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

__all__ = [
    "Event",
    "JobCompleted",
    "JobFailed",
    "JobStarted",
    "ResponseReady",
    "UtteranceReceived",
]


@dataclass(frozen=True, slots=True)
class Event:
    """Base for all events. ``topic`` is the dotted name subscribers match on."""

    trace_id: str
    topic: ClassVar[str] = "event"


@dataclass(frozen=True, slots=True)
class UtteranceReceived(Event):
    text: str
    area: str
    speaker_id: str
    topic: ClassVar[str] = "utterance.received"


@dataclass(frozen=True, slots=True)
class ResponseReady(Event):
    text: str
    cost: float | None = None
    latency_ms: float | None = None
    topic: ClassVar[str] = "response.ready"


@dataclass(frozen=True, slots=True)
class JobStarted(Event):
    job_id: str
    topic: ClassVar[str] = "job.started"


@dataclass(frozen=True, slots=True)
class JobCompleted(Event):
    job_id: str
    summary: str
    topic: ClassVar[str] = "job.completed"


@dataclass(frozen=True, slots=True)
class JobFailed(Event):
    job_id: str
    error: str
    topic: ClassVar[str] = "job.failed"
