"""End-to-end tests for handle_utterance against the port fakes (README §6).

Zero network, zero token spend — the whole foundation exercised in one flow.
"""

from datetime import datetime

from jarvis.domain.events import Event
from jarvis.domain.models import Utterance
from jarvis.domain.routing import RoutingPolicy
from jarvis.domain.sessions import SessionManager
from jarvis.ports.brain import BrainRateLimited
from jarvis.ports.events import EventPublisher
from jarvis.services.handle_utterance import (
    DEFAULT_FALLBACK_MESSAGE,
    DEFAULT_RATE_LIMIT_MESSAGE,
    HandleUtterance,
)
from tests.fakes import FakeBrain, Fakes

BASE = datetime(2026, 6, 26, 9, 0, 0)


def _build(fakes: Fakes, *, brain=None, trace_id="trace-1") -> HandleUtterance:
    return HandleUtterance(
        speaker_identifier=fakes.speaker_id,
        session_manager=SessionManager(),
        routing_policy=RoutingPolicy(),
        brain=brain or fakes.brain,
        tts=fakes.tts,
        store=fakes.store,
        events=fakes.bus,
        clock=lambda: BASE,
        trace_id_factory=lambda: trace_id,
    )


def _record(fakes: Fakes) -> list[Event]:
    captured: list[Event] = []

    async def recorder(event: Event) -> None:
        captured.append(event)

    fakes.bus.subscribe("*", recorder)
    return captured


def test_event_bus_satisfies_publisher_port(fakes: Fakes):
    assert isinstance(fakes.bus, EventPublisher)


async def test_quick_qa_happy_path(fakes: Fakes):
    events = _record(fakes)
    use_case = _build(fakes)

    response = await use_case(Utterance(text="what's the weather?", area="kitchen"))
    await fakes.bus.drain()

    # Spoken answer routed to the originating area.
    assert fakes.tts.spoken == [("(fake answer)", "kitchen")]
    # Response carries trace id, cost, latency, and the brain session id.
    assert response.text == "(fake answer)"
    assert response.trace_id == "trace-1"
    assert response.brain_session_id == "fake-session"
    assert response.latency_ms is not None and response.latency_ms >= 0

    # The brain was reached with the household speaker's request.
    assert fakes.brain.last_call.request.speaker.id == "household"

    # Session persisted with the brain session id for --resume.
    stored = await fakes.store.get_session(("kitchen", "household"))
    assert stored is not None
    assert stored.brain_session_id == "fake-session"

    # Both lifecycle events fired with the trace id.
    topics = [e.topic for e in events]
    assert topics == ["utterance.received", "response.ready"]
    assert all(e.trace_id == "trace-1" for e in events)


async def test_session_is_resumed_within_timeout(fakes: Fakes):
    use_case = _build(fakes)

    await use_case(Utterance(text="who won in 1998?", area="kitchen"))
    await use_case(Utterance(text="what about 1999?", area="kitchen"))

    # The second invocation saw the session with the brain id from the first,
    # so the brain can --resume the conversation.
    assert fakes.brain.calls[1].session.brain_session_id == "fake-session"
    assert fakes.brain.calls[0].session.id == fakes.brain.calls[1].session.id


async def test_fail_soft_when_brain_errors(fakes: Fakes):
    events = _record(fakes)
    brain = FakeBrain(error=RuntimeError("rate limited"))
    use_case = _build(fakes, brain=brain)

    # Must not raise — the room gets graceful audio feedback instead.
    response = await use_case(Utterance(text="anything", area="den"))
    await fakes.bus.drain()

    assert response.text == DEFAULT_FALLBACK_MESSAGE
    assert fakes.tts.spoken == [(DEFAULT_FALLBACK_MESSAGE, "den")]
    # response.ready still published (with no cost) so observers see the outcome.
    assert [e.topic for e in events] == ["utterance.received", "response.ready"]
    ready = events[-1]
    assert ready.text == DEFAULT_FALLBACK_MESSAGE
    assert ready.cost is None


async def test_rate_limited_speaks_distinct_message(fakes: Fakes):
    brain = FakeBrain(error=BrainRateLimited("429 rate limit"))
    use_case = _build(fakes, brain=brain)

    response = await use_case(Utterance(text="anything", area="den"))
    await fakes.bus.drain()

    # Distinct "at my limit" message, not the generic failure fallback (§8).
    assert response.text == DEFAULT_RATE_LIMIT_MESSAGE
    assert response.text != DEFAULT_FALLBACK_MESSAGE
    assert fakes.tts.spoken == [(DEFAULT_RATE_LIMIT_MESSAGE, "den")]
