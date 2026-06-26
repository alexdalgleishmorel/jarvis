"""Tests for the HA conversation ingress adapter + FastAPI endpoint (README §4-6)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.adapters.ingress import HaConversationIngress, HaConversationPayload
from jarvis.app.api import create_ingress_router
from jarvis.domain.routing import RoutingPolicy
from jarvis.domain.sessions import SessionManager
from jarvis.services.handle_utterance import HandleUtterance
from tests.fakes import Fakes, make_fakes


def test_adapter_maps_payload_and_defaults_area():
    ingress = HaConversationIngress(default_area="home")
    utterance = ingress.to_utterance(
        HaConversationPayload(text="hi", area=None, conversation_id="c1")
    )
    assert utterance.text == "hi"
    assert utterance.area == "home"  # defaulted
    assert utterance.conversation_id == "c1"


def _client(fakes: Fakes) -> TestClient:
    use_case = HandleUtterance(
        speaker_identifier=fakes.speaker_id,
        session_manager=SessionManager(),
        routing_policy=RoutingPolicy(),
        brain=fakes.brain,
        tts=fakes.tts,
        store=fakes.store,
        events=fakes.bus,
        trace_id_factory=lambda: "trace-1",
    )
    app = FastAPI()
    app.include_router(create_ingress_router(use_case, HaConversationIngress(default_area="home")))
    return TestClient(app)


def test_endpoint_runs_the_pipeline_and_returns_reply():
    fakes = make_fakes()
    client = _client(fakes)

    resp = client.post(
        "/ingress/utterance",
        json={"text": "what's the weather?", "area": "kitchen", "conversation_id": "c1"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "(fake answer)"
    assert body["trace_id"] == "trace-1"
    assert body["conversation_id"] == "c1"
    # The brain was reached with the originating area.
    assert fakes.brain.last_call.request.utterance.area == "kitchen"


def test_endpoint_defaults_area_when_missing():
    fakes = make_fakes()
    client = _client(fakes)

    resp = client.post("/ingress/utterance", json={"text": "hello"})

    assert resp.status_code == 200
    assert fakes.brain.last_call.request.utterance.area == "home"


def test_endpoint_validates_required_text():
    fakes = make_fakes()
    client = _client(fakes)

    resp = client.post("/ingress/utterance", json={"area": "kitchen"})

    assert resp.status_code == 422
