"""Structural-typing smoke test: a minimal stub satisfies each port.

The ports are ``runtime_checkable`` Protocols, so a duck-typed stub with the
right methods passes ``isinstance``. This also documents each signature.
"""

from datetime import datetime

from jarvis.domain.models import Capability, Job, Request, Room, Session, Speaker, Utterance
from jarvis.ports import (
    Brain,
    BrainResult,
    Budget,
    HomeAssistant,
    Notifier,
    SpeakerIdentifier,
    Store,
    TextToSpeech,
    Usage,
)
from jarvis.ports.home_assistant import Area, Entity


class StubBrain:
    async def invoke(self, request, session, *, tools=None, model=None, budget=None):
        return BrainResult(text="ok", brain_session_id="b1", cost=0.0, usage=Usage())


class StubSpeakerId:
    async def identify(self, audio_or_ref, room):
        return Speaker.household()


class StubTTS:
    async def speak(self, text, *, area):
        return None


class StubNotifier:
    async def notify(self, message, *, target=None):
        return None


class StubHub:
    async def get_areas(self):
        return [Area(id="kitchen", name="Kitchen")]

    async def list_entities(self, *, area=None, domain=None):
        return [Entity(entity_id="light.kitchen", state="on")]

    async def call_service(self, domain, service, *, data=None, target=None):
        return None


class StubStore:
    async def get_session(self, key):
        return None

    async def upsert_session(self, session):
        return None

    async def get_job(self, job_id):
        return None

    async def upsert_job(self, job):
        return None

    async def list_jobs(self):
        return []

    async def get_speaker(self, speaker_id):
        return None

    async def upsert_speaker(self, speaker):
        return None

    async def list_speakers(self):
        return []

    async def list_capabilities(self):
        return []

    async def upsert_capability(self, capability):
        return None

    async def get_config(self, key):
        return None

    async def set_config(self, key, value):
        return None


def test_stubs_satisfy_protocols():
    assert isinstance(StubBrain(), Brain)
    assert isinstance(StubSpeakerId(), SpeakerIdentifier)
    assert isinstance(StubTTS(), TextToSpeech)
    assert isinstance(StubNotifier(), Notifier)
    assert isinstance(StubHub(), HomeAssistant)
    assert isinstance(StubStore(), Store)


async def test_brain_invoke_roundtrip():
    request = Request(
        utterance=Utterance(text="hi", area="kitchen"),
        room=Room(id="kitchen", area="kitchen"),
        speaker=Speaker.household(),
        trace_id="t-1",
    )
    now = datetime(2026, 1, 1)
    session = Session(
        id="s1", room_id="kitchen", speaker_id="household", created_at=now, last_active_at=now
    )
    result = await StubBrain().invoke(
        request, session, tools=["calendar"], budget=Budget(max_turns=4)
    )
    assert result.text == "ok"
    assert result.brain_session_id == "b1"


async def test_store_and_hub_methods_callable():
    store: Store = StubStore()
    assert await store.list_jobs() == []
    hub: HomeAssistant = StubHub()
    areas = await hub.get_areas()
    assert areas[0].id == "kitchen"


def test_capability_and_job_importable():
    # Sanity that the domain types the ports reference are wired through.
    assert Capability(name="web_search").name == "web_search"
    assert Job(id="j", trace_id="t", prompt="p").id == "j"
