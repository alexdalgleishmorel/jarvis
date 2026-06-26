"""Domain entities and value objects — the plain data the whole system speaks.

No I/O, no third-party imports (README §3.1, §5). Only the standard library.

Two flavours of type live here:

* **Value objects** are ``frozen`` — immutable, compared by value (``Utterance``,
  ``Request``, ``Response``, ``Room``, ``Speaker``, ``SpeakerProfile``,
  ``Capability``, ``RoutingDecision``).
* **Entities** have identity and mutable state over their lifetime (``Session``,
  ``Job``).

Timestamps are passed in, never read from a clock here — the domain stays
deterministic and testable (the clock is injected at the edges).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

__all__ = [
    "HOUSEHOLD_SPEAKER_ID",
    "Capability",
    "Job",
    "JobStatus",
    "Request",
    "Response",
    "Room",
    "Route",
    "RoutingDecision",
    "Session",
    "Speaker",
    "SpeakerProfile",
    "Utterance",
]

# The id of the default speaker the null resolver returns when identity is
# unknown (README §3.7, §7). Identity-dependent code must work for this id.
HOUSEHOLD_SPEAKER_ID = "household"


# ──────────────────────────── Places & people ────────────────────────────


@dataclass(frozen=True, slots=True)
class Room:
    """A room, mapped to a Home Assistant *area*.

    ``area`` is the hub's area id we route audio to; ``id`` is our stable key
    (often equal to ``area`` until the rooms↔satellites mapping lands in M3).
    """

    id: str
    area: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class SpeakerProfile:
    """What a speaker's identity binds to (README §7).

    Most fields are seams for later milestones; today the household profile is
    permissive and unbound. ``permissions`` holds capability names, with ``"*"``
    meaning "all". Enforcement lands in M4 — for now the data just rides along.
    """

    display_name: str
    calendar_account: str | None = None
    gmail_account: str | None = None
    preferred_voice: str | None = None
    permissions: frozenset[str] = frozenset()

    def allows(self, capability: str) -> bool:
        return "*" in self.permissions or capability in self.permissions


@dataclass(frozen=True, slots=True)
class Speaker:
    """Who is talking. Resolved by a ``SpeakerIdentifier`` (null today)."""

    id: str
    profile: SpeakerProfile

    @property
    def is_known(self) -> bool:
        """False for the household default / unknown speaker."""
        return self.id != HOUSEHOLD_SPEAKER_ID

    @classmethod
    def household(cls) -> Speaker:
        """The default speaker used when identity is unknown (README §7)."""
        return cls(
            id=HOUSEHOLD_SPEAKER_ID,
            profile=SpeakerProfile(display_name="Household", permissions=frozenset({"*"})),
        )


# ──────────────────────────── Request lifecycle ────────────────────────────


@dataclass(frozen=True, slots=True)
class Utterance:
    """A transcribed thing someone said, as it arrives from the hub.

    Carries the raw text plus where it came from (HA ``area``) and the hub's
    conversation id. The speaker is *not* here yet — it is resolved by the
    use-case and attached to the enriched ``Request``.
    """

    text: str
    area: str
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class Request:
    """An enriched, domain-level request the brain acts on.

    Built by ``handle_utterance`` after identification: it pairs the raw
    ``Utterance`` with the resolved ``Room`` and ``Speaker`` and a per-utterance
    ``trace_id`` (README §6).
    """

    utterance: Utterance
    room: Room
    speaker: Speaker
    trace_id: str

    @property
    def text(self) -> str:
        return self.utterance.text


@dataclass(frozen=True, slots=True)
class Response:
    """The domain-level reply that gets spoken and published on ``response.ready``.

    Cost and latency are captured on every brain invocation (README §13).
    """

    text: str
    trace_id: str
    cost: float | None = None
    latency_ms: float | None = None
    brain_session_id: str | None = None


# ──────────────────────────── Routing ────────────────────────────


class Route(Enum):
    """How a request should flow. Device commands are handled upstream by the
    hub and never reach us (README §5)."""

    QUICK_QA = "quick_qa"
    ASYNC_JOB = "async_job"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """The output of ``RoutingPolicy`` — the chosen route and why."""

    route: Route
    reason: str = ""


# ──────────────────────────── Sessions & jobs ────────────────────────────


@dataclass(slots=True)
class Session:
    """Conversation continuity, keyed by ``(room_id, speaker_id)`` (README §5, §6).

    An entity: ``brain_session_id`` and ``last_active_at`` change as the
    conversation continues. The ``SessionManager`` owns the timeout logic; this
    is just the state.
    """

    id: str
    room_id: str
    speaker_id: str
    created_at: datetime
    last_active_at: datetime
    brain_session_id: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.room_id, self.speaker_id)


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Job:
    """An async, fire-and-notify unit of work (README §6 async flow).

    An entity whose ``status``/``summary`` evolve as it runs. Created in M2 by
    ``run_job``; the messenger notifies on completion. We never read code aloud.
    """

    id: str
    trace_id: str
    prompt: str
    target_repo: str | None = None
    status: JobStatus = JobStatus.QUEUED
    summary: str | None = None
    brain_session_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ──────────────────────────── Capabilities ────────────────────────────


@dataclass(frozen=True, slots=True)
class Capability:
    """A tool/capability the brain can be granted, gated per speaker (README §10).

    ``required_permission`` names the permission a ``SpeakerProfile`` must hold
    to use it; ``None`` means unrestricted.
    """

    name: str
    description: str = ""
    required_permission: str | None = None
