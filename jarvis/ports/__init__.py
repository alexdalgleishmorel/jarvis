"""Ports — the interfaces (Protocols) the conductor depends on.

Everything that touches the outside world (the hub, brain, voice, messenger,
store, speaker ID) sits behind one of these ports. Ports import only from
``jarvis.domain`` (README §3.1, §5).
"""

from jarvis.ports.brain import Brain, BrainResult, Budget, Usage
from jarvis.ports.events import EventPublisher
from jarvis.ports.home_assistant import Area, Entity, HomeAssistant
from jarvis.ports.notifier import Notifier
from jarvis.ports.speaker_id import AudioRef, SpeakerIdentifier
from jarvis.ports.store import Store
from jarvis.ports.tts import TextToSpeech

__all__ = [
    "Area",
    "AudioRef",
    "Brain",
    "BrainResult",
    "Budget",
    "Entity",
    "EventPublisher",
    "HomeAssistant",
    "Notifier",
    "SpeakerIdentifier",
    "Store",
    "TextToSpeech",
    "Usage",
]
