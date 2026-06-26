"""The ``SpeakerIdentifier`` port — identity is first-class but pluggable.

The null adapter returns the household default; the future voice-embedding
adapter resolves an utterance to an enrolled profile (README §3.7, §7). Code that
uses identity must degrade gracefully when the speaker is unknown.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from jarvis.domain.models import Room, Speaker

__all__ = ["AudioRef", "SpeakerIdentifier"]

# A reference to the audio to identify: raw bytes, or a hub-side handle (e.g. a
# stream/clip id). The null adapter ignores it; the voice adapter narrows it.
AudioRef = bytes | str


@runtime_checkable
class SpeakerIdentifier(Protocol):
    async def identify(self, audio_or_ref: AudioRef | None, room: Room) -> Speaker: ...
