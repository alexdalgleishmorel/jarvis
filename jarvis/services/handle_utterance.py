"""handle_utterance — the Quick Q&A request lifecycle (README §6).

Orchestrates one utterance end to end: identify the speaker, resolve the
session, classify the route, ask the brain, speak the answer, and publish events
along the way. The brain is reached only through the ``Brain`` port (README §13).

Two principles shape the shape of this code:

* **Local-first, fail-soft (§3.8).** If the brain is slow or unavailable we speak
  an immediate, graceful fallback and never hang the room.
* **Observability (§13).** A per-utterance ``trace_id`` threads through every
  event; cost and latency are captured on the brain invocation.

The clock and trace-id factory are injected so the flow stays deterministic in
tests; the composition root supplies real ones.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from jarvis.domain.events import ResponseReady, UtteranceReceived
from jarvis.domain.models import Request, Response, Room, Route, Session, Utterance
from jarvis.domain.routing import RoutingPolicy
from jarvis.domain.sessions import SessionManager
from jarvis.ports.brain import Brain, BrainRateLimited, Budget
from jarvis.ports.events import EventPublisher
from jarvis.ports.speaker_id import SpeakerIdentifier
from jarvis.ports.store import Store
from jarvis.ports.tts import TextToSpeech

__all__ = ["DEFAULT_FALLBACK_MESSAGE", "HandleUtterance"]

logger = logging.getLogger("jarvis.services.handle_utterance")

DEFAULT_FALLBACK_MESSAGE = "Sorry, I'm having trouble reaching my brain right now."
DEFAULT_RATE_LIMIT_MESSAGE = "I'm at my limit right now — try me again in a little while."


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_trace_id() -> str:
    return uuid4().hex


class HandleUtterance:
    def __init__(
        self,
        *,
        speaker_identifier: SpeakerIdentifier,
        session_manager: SessionManager,
        routing_policy: RoutingPolicy,
        brain: Brain,
        tts: TextToSpeech,
        store: Store,
        events: EventPublisher,
        model: str | None = None,
        tools: Sequence[str] | None = None,
        budget: Budget | None = None,
        fallback_message: str = DEFAULT_FALLBACK_MESSAGE,
        rate_limit_message: str = DEFAULT_RATE_LIMIT_MESSAGE,
        clock: Callable[[], datetime] = _utcnow,
        trace_id_factory: Callable[[], str] = _new_trace_id,
    ) -> None:
        self._speaker_identifier = speaker_identifier
        self._session_manager = session_manager
        self._routing_policy = routing_policy
        self._brain = brain
        self._tts = tts
        self._store = store
        self._events = events
        self._model = model
        self._tools = tools
        self._budget = budget
        self._fallback_message = fallback_message
        self._rate_limit_message = rate_limit_message
        self._clock = clock
        self._trace_id_factory = trace_id_factory

    async def __call__(self, utterance: Utterance) -> Response:
        trace_id = self._trace_id_factory()
        now = self._clock()

        # area → room. The full rooms↔satellites mapping lands in M3; for now a
        # room is its area.
        room = Room(id=utterance.area, area=utterance.area)

        speaker = await self._speaker_identifier.identify(None, room)
        await self._events.publish(
            UtteranceReceived(
                trace_id=trace_id,
                text=utterance.text,
                area=utterance.area,
                speaker_id=speaker.id,
            )
        )

        request = Request(utterance=utterance, room=room, speaker=speaker, trace_id=trace_id)
        existing = await self._store.get_session((room.id, speaker.id))
        session = self._session_manager.resolve(
            existing, room_id=room.id, speaker_id=speaker.id, now=now
        )

        decision = self._routing_policy.classify(request)
        if decision.route is Route.ASYNC_JOB:
            # The ASYNC_JOB ack + run_job path is wired in M2 (#20); until then we
            # answer synchronously rather than drop the request.
            logger.info(
                "async_job routing not yet implemented (trace=%s); handling as quick QA",
                trace_id,
            )

        return await self._quick_qa(request, session, trace_id)

    async def _quick_qa(self, request: Request, session: Session, trace_id: str) -> Response:
        started = perf_counter()
        try:
            result = await self._brain.invoke(
                request,
                session,
                tools=self._tools,
                model=self._model,
                budget=self._budget,
            )
        except BrainRateLimited:
            # Quota/rate limit (§8): a distinct, graceful "at my limit" message.
            logger.warning("brain rate-limited (trace=%s)", trace_id)
            return await self._speak_failure(request, trace_id, started, self._rate_limit_message)
        except Exception:
            # Fail-soft (§3.8): speak an immediate, graceful fallback. Never hang
            # the room, never re-raise into the request path.
            logger.exception("brain invocation failed (trace=%s); speaking fallback", trace_id)
            return await self._speak_failure(request, trace_id, started, self._fallback_message)

        latency_ms = (perf_counter() - started) * 1000

        # Remember the brain session id so the next utterance can --resume.
        session.brain_session_id = result.brain_session_id
        await self._store.upsert_session(session)

        await self._tts.speak(result.text, area=request.room.area)

        logger.info(
            "quick_qa ok trace=%s cost=%s latency_ms=%.1f",
            trace_id,
            result.cost,
            latency_ms,
        )
        await self._events.publish(
            ResponseReady(
                trace_id=trace_id,
                text=result.text,
                cost=result.cost,
                latency_ms=latency_ms,
            )
        )
        return Response(
            text=result.text,
            trace_id=trace_id,
            cost=result.cost,
            latency_ms=latency_ms,
            brain_session_id=result.brain_session_id,
        )

    async def _speak_failure(
        self, request: Request, trace_id: str, started: float, message: str
    ) -> Response:
        """Speak a graceful message and publish response.ready — never re-raise."""
        latency_ms = (perf_counter() - started) * 1000
        await self._tts.speak(message, area=request.room.area)
        await self._events.publish(
            ResponseReady(trace_id=trace_id, text=message, latency_ms=latency_ms)
        )
        return Response(text=message, trace_id=trace_id, latency_ms=latency_ms)
