"""In-memory fakes for every port + a bundle that wires a fully-faked conductor.

Principle #9 (README §3.9): every port has a fake, so use-cases are testable
without the hub, audio, or token spend. Import these directly or take the
``fakes`` pytest fixture (see ``tests/conftest.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.app.events import EventBus
from tests.fakes.brain import BrainCall, FakeBrain
from tests.fakes.home_assistant import FakeHomeAssistant, ServiceCall
from tests.fakes.notifier import FakeNotifier
from tests.fakes.speaker_id import FakeSpeakerIdentifier
from tests.fakes.store import InMemoryStore
from tests.fakes.tts import FakeTextToSpeech

__all__ = [
    "BrainCall",
    "FakeBrain",
    "FakeHomeAssistant",
    "FakeNotifier",
    "FakeSpeakerIdentifier",
    "FakeTextToSpeech",
    "Fakes",
    "InMemoryStore",
    "ServiceCall",
    "make_fakes",
]


@dataclass
class Fakes:
    """Every fake plus a fresh event bus — the seam for use-case tests."""

    brain: FakeBrain
    speaker_id: FakeSpeakerIdentifier
    tts: FakeTextToSpeech
    notifier: FakeNotifier
    hub: FakeHomeAssistant
    store: InMemoryStore
    bus: EventBus


def make_fakes() -> Fakes:
    return Fakes(
        brain=FakeBrain(),
        speaker_id=FakeSpeakerIdentifier(),
        tts=FakeTextToSpeech(),
        notifier=FakeNotifier(),
        hub=FakeHomeAssistant(),
        store=InMemoryStore(),
        bus=EventBus(),
    )
