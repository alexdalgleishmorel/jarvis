"""Tests for SessionManager continuity logic (README §5, §6)."""

from datetime import datetime, timedelta
from itertools import count

from jarvis.domain.models import Session
from jarvis.domain.sessions import DEFAULT_IDLE_TIMEOUT, SessionManager

BASE = datetime(2026, 6, 26, 9, 0, 0)


def _manager(idle_timeout=timedelta(minutes=5)) -> SessionManager:
    ids = count(1)
    return SessionManager(idle_timeout=idle_timeout, id_factory=lambda: f"sess-{next(ids)}")


def _existing(now=BASE, *, brain_session_id="brain-1") -> Session:
    return Session(
        id="sess-existing",
        room_id="kitchen",
        speaker_id="household",
        created_at=now,
        last_active_at=now,
        brain_session_id=brain_session_id,
    )


def test_creates_new_session_when_none_exists():
    manager = _manager()
    session = manager.resolve(None, room_id="kitchen", speaker_id="household", now=BASE)
    assert session.id == "sess-1"
    assert session.key == ("kitchen", "household")
    assert session.brain_session_id is None
    assert session.created_at == session.last_active_at == BASE


def test_continues_within_idle_timeout():
    manager = _manager()
    existing = _existing()
    later = BASE + timedelta(minutes=2)
    session = manager.resolve(existing, room_id="kitchen", speaker_id="household", now=later)
    # Same session object, activity bumped, brain session id retained for --resume.
    assert session is existing
    assert session.last_active_at == later
    assert session.brain_session_id == "brain-1"


def test_starts_fresh_after_idle_timeout():
    manager = _manager()
    existing = _existing()
    later = BASE + timedelta(minutes=6)  # past the 5-minute window
    session = manager.resolve(existing, room_id="kitchen", speaker_id="household", now=later)
    assert session is not existing
    assert session.id == "sess-1"
    assert session.brain_session_id is None
    assert session.created_at == later


def test_idle_timeout_boundary_is_inclusive():
    manager = _manager()
    existing = _existing()
    at_boundary = BASE + timedelta(minutes=5)
    assert manager.is_active(existing, now=at_boundary) is True
    just_after = BASE + timedelta(minutes=5, seconds=1)
    assert manager.is_active(existing, now=just_after) is False


def test_default_idle_timeout():
    assert SessionManager().idle_timeout == DEFAULT_IDLE_TIMEOUT
