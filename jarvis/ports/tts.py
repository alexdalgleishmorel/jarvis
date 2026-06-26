"""The ``TextToSpeech`` port — the voice (README §5, §6).

Speaks a reply back to the originating room. ``area`` is the Home Assistant area
the audio plays in.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["TextToSpeech"]


@runtime_checkable
class TextToSpeech(Protocol):
    async def speak(self, text: str, *, area: str) -> None: ...
