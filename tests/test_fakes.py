"""Tests for the port fakes and the test harness (README §3.9)."""

from datetime import datetime

import pytest

from jarvis.domain.models import (
    Capability,
    Job,
    Request,
    Room,
    Session,
    Speaker,
    Utterance,
)
from jarvis.ports import (
    Brain,
    HomeAssistant,
    Notifier,
    SpeakerIdentifier,
    Store,
    TextToSpeech,
)
from jarvis.ports.home_assistant import Area, Entity
from tests.fakes import Fakes


def _request() -> Request:
    return Request(
        utterance=Utterance(text="hi", area="kitchen"),
        room=Room(id="kitchen", area="kitchen"),
        speaker=Speaker.household(),
        trace_id="t-1",
    )


def _session() -> Session:
    now = datetime(2026, 1, 1)
    return Session(
        id="s1",
        room_id="kitchen",
        speaker_id="household",
        created_at=now,
        last_active_at=now,
    )


def test_every_fake_satisfies_its_port(fakes: Fakes):
    assert isinstance(fakes.brain, Brain)
    assert isinstance(fakes.speaker_id, SpeakerIdentifier)
    assert isinstance(fakes.tts, TextToSpeech)
    assert isinstance(fakes.notifier, Notifier)
    assert isinstance(fakes.hub, HomeAssistant)
    assert isinstance(fakes.store, Store)


async def test_fake_brain_records_calls_and_returns_canned_result(fake_brain):
    result = await fake_brain.invoke(
        _request(), _session(), tools=["calendar", "web_search"], model="fast"
    )
    assert result.text == "(fake answer)"
    assert result.brain_session_id == "fake-session"
    assert fake_brain.last_call.model == "fast"
    assert fake_brain.last_call.tools == ("calendar", "web_search")


async def test_fake_brain_can_inject_errors():
    from tests.fakes import FakeBrain

    brain = FakeBrain(error=RuntimeError("rate limited"))
    with pytest.raises(RuntimeError, match="rate limited"):
        await brain.invoke(_request(), _session())
    # the call is still recorded before raising
    assert len(brain.calls) == 1


async def test_speaker_id_returns_household_by_default(fake_speaker_id):
    speaker = await fake_speaker_id.identify(None, Room(id="kitchen", area="kitchen"))
    assert speaker.id == "household"
    assert fake_speaker_id.calls == [(None, Room(id="kitchen", area="kitchen"))]


async def test_tts_and_notifier_record(fake_tts, fake_notifier):
    await fake_tts.speak("hello kitchen", area="kitchen")
    await fake_notifier.notify("job done", target="#general")
    assert fake_tts.spoken == [("hello kitchen", "kitchen")]
    assert fake_notifier.sent == [("job done", "#general")]


async def test_in_memory_store_roundtrips(store):
    session = _session()
    await store.upsert_session(session)
    assert await store.get_session(("kitchen", "household")) is session

    job = Job(id="j1", trace_id="t-1", prompt="bump deps")
    await store.upsert_job(job)
    assert (await store.list_jobs()) == [job]

    speaker = Speaker.household()
    await store.upsert_speaker(speaker)
    assert await store.get_speaker("household") is speaker

    await store.upsert_capability(Capability(name="calendar"))
    assert [c.name for c in await store.list_capabilities()] == ["calendar"]

    await store.set_config("session.idle_timeout_s", "120")
    assert await store.get_config("session.idle_timeout_s") == "120"
    assert await store.get_config("missing") is None


async def test_fake_hub_filters_and_records_service_calls():
    hub = _hub_with_entities()
    assert [a.id for a in await hub.get_areas()] == ["kitchen", "den"]

    kitchen = await hub.list_entities(area="kitchen")
    assert {e.entity_id for e in kitchen} == {"light.kitchen"}

    lights = await hub.list_entities(domain="light")
    assert {e.entity_id for e in lights} == {"light.kitchen", "light.den"}

    await hub.call_service("light", "turn_on", target={"entity_id": "light.kitchen"})
    assert hub.service_calls[0].service == "turn_on"
    assert hub.service_calls[0].target == {"entity_id": "light.kitchen"}


def _hub_with_entities():
    from tests.fakes import FakeHomeAssistant

    return FakeHomeAssistant(
        areas=[Area(id="kitchen", name="Kitchen"), Area(id="den", name="Den")],
        entities=[
            Entity(entity_id="light.kitchen", state="on", area_id="kitchen"),
            Entity(entity_id="light.den", state="off", area_id="den"),
        ],
    )
