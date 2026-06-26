"""Shared pytest fixtures.

The ``fakes`` bundle wires every port fake plus a fresh event bus; the
convenience fixtures (``fake_brain``, ``store``, …) hand back the *same*
instances from that bundle so a test can mix-and-match without them drifting
out of sync.
"""

import pytest

from jarvis.app.events import EventBus
from tests.fakes import (
    FakeBrain,
    FakeHomeAssistant,
    FakeNotifier,
    Fakes,
    FakeSpeakerIdentifier,
    FakeTextToSpeech,
    InMemoryStore,
    make_fakes,
)


@pytest.fixture
def fakes() -> Fakes:
    return make_fakes()


@pytest.fixture
def fake_brain(fakes: Fakes) -> FakeBrain:
    return fakes.brain


@pytest.fixture
def fake_speaker_id(fakes: Fakes) -> FakeSpeakerIdentifier:
    return fakes.speaker_id


@pytest.fixture
def fake_tts(fakes: Fakes) -> FakeTextToSpeech:
    return fakes.tts


@pytest.fixture
def fake_notifier(fakes: Fakes) -> FakeNotifier:
    return fakes.notifier


@pytest.fixture
def fake_hub(fakes: Fakes) -> FakeHomeAssistant:
    return fakes.hub


@pytest.fixture
def store(fakes: Fakes) -> InMemoryStore:
    return fakes.store


@pytest.fixture
def event_bus(fakes: Fakes) -> EventBus:
    return fakes.bus
