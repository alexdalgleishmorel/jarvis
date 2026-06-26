"""In-memory fake for the ``SpeakerIdentifier`` port."""

from __future__ import annotations

from jarvis.domain.models import Room, Speaker
from jarvis.ports.speaker_id import AudioRef


class FakeSpeakerIdentifier:
    def __init__(self, speaker: Speaker | None = None) -> None:
        self.speaker = speaker or Speaker.household()
        self.calls: list[tuple[AudioRef | None, Room]] = []

    async def identify(self, audio_or_ref: AudioRef | None, room: Room) -> Speaker:
        self.calls.append((audio_or_ref, room))
        return self.speaker
