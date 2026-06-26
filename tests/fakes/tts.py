"""In-memory fake for the ``TextToSpeech`` port — records what was spoken where."""

from __future__ import annotations


class FakeTextToSpeech:
    def __init__(self) -> None:
        self.spoken: list[tuple[str, str]] = []

    async def speak(self, text: str, *, area: str) -> None:
        self.spoken.append((text, area))
