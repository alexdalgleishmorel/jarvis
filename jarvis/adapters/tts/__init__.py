"""Voice adapters. ``HaPiperTextToSpeech`` speaks via the hub; ``NullTextToSpeech``
is the no-op used when Home Assistant's pipeline speaks the reply (README §5, §6)."""

from jarvis.adapters.tts.ha_piper import HaPiperTextToSpeech
from jarvis.adapters.tts.null import NullTextToSpeech

__all__ = ["HaPiperTextToSpeech", "NullTextToSpeech"]
