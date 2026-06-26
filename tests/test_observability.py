"""Tests for structured logging, trace ids, and the event-logging observer (§13)."""

import io
import json
import logging

from jarvis.app.observability import (
    configure_logging,
    new_trace_id,
    register_event_logging,
)
from jarvis.domain.models import Utterance
from jarvis.domain.routing import RoutingPolicy
from jarvis.domain.sessions import SessionManager
from jarvis.services.handle_utterance import HandleUtterance
from tests.fakes import Fakes


def test_new_trace_id_is_unique_hex():
    a, b = new_trace_id(), new_trace_id()
    assert a != b
    assert all(c in "0123456789abcdef" for c in a)


def test_json_formatter_emits_structured_fields():
    buf = io.StringIO()
    configure_logging(stream=buf, name="jarvis.test")
    logging.getLogger("jarvis.test").info("hello", extra={"trace_id": "t-1", "cost": 0.5})

    line = json.loads(buf.getvalue().strip())
    assert line["message"] == "hello"
    assert line["level"] == "INFO"
    assert line["logger"] == "jarvis.test"
    assert line["trace_id"] == "t-1"
    assert line["cost"] == 0.5
    assert "time" in line


async def test_single_utterance_produces_one_correlated_trace(fakes: Fakes):
    buf = io.StringIO()
    configure_logging(stream=buf, name="jarvis")
    register_event_logging(fakes.bus)

    use_case = HandleUtterance(
        speaker_identifier=fakes.speaker_id,
        session_manager=SessionManager(),
        routing_policy=RoutingPolicy(),
        brain=fakes.brain,
        tts=fakes.tts,
        store=fakes.store,
        events=fakes.bus,
        trace_id_factory=lambda: "trace-xyz",
    )

    await use_case(Utterance(text="what's the weather?", area="kitchen"))
    await fakes.bus.drain()

    lines = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    by_topic = {line["topic"]: line for line in lines if "topic" in line}

    # One correlated trace: both lifecycle events share the trace id.
    assert {"utterance.received", "response.ready"} <= set(by_topic)
    assert all(line["trace_id"] == "trace-xyz" for line in by_topic.values())

    # response.ready carries cost + latency.
    ready = by_topic["response.ready"]
    assert "cost" in ready
    assert ready["latency_ms"] is not None and ready["latency_ms"] >= 0
