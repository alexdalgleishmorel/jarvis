"""SessionManager — conversation continuity, keyed by ``(room_id, speaker_id)``.

A new utterance within the idle timeout continues the same brain session (so
"what about tomorrow?" works); otherwise it starts fresh. The manager holds the
mapping to the brain's ``session_id`` via the ``Session`` it returns, and knows
nothing about how the brain is invoked (README §5, §6).

Pure domain logic: no clock and no storage. The caller (the use-case) loads the
existing session for the key from the ``Store``, passes ``now`` in, and persists
the result — keeping this deterministic and testable. The idle timeout is
config-driven (README §3.5), defaulting here only for convenience.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from jarvis.domain.models import Session

__all__ = ["DEFAULT_IDLE_TIMEOUT", "SessionManager"]

DEFAULT_IDLE_TIMEOUT = timedelta(minutes=5)


def _new_id() -> str:
    return uuid4().hex


class SessionManager:
    def __init__(
        self,
        *,
        idle_timeout: timedelta = DEFAULT_IDLE_TIMEOUT,
        id_factory: Callable[[], str] = _new_id,
    ) -> None:
        self.idle_timeout = idle_timeout
        self._id_factory = id_factory

    def is_active(self, session: Session, *, now: datetime) -> bool:
        """True if ``session`` is still within the idle window at ``now``."""
        return now - session.last_active_at <= self.idle_timeout

    def resolve(
        self,
        existing: Session | None,
        *,
        room_id: str,
        speaker_id: str,
        now: datetime,
    ) -> Session:
        """Continue ``existing`` if it is still active, else start a fresh session.

        ``existing`` is the session previously stored for ``(room_id, speaker_id)``
        (or ``None``). Continuing bumps ``last_active_at`` and keeps the brain
        ``session_id`` so the next invocation can ``--resume``; starting fresh
        yields a new id with no brain session yet.
        """
        if existing is not None and self.is_active(existing, now=now):
            existing.last_active_at = now
            return existing
        return Session(
            id=self._id_factory(),
            room_id=room_id,
            speaker_id=speaker_id,
            created_at=now,
            last_active_at=now,
        )
