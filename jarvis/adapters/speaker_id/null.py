"""The null ``SpeakerIdentifier`` — returns the household default (README §3.7, §7).

Identity is first-class but pluggable: today the resolver ignores the audio and
returns one shared household speaker. When the voice-embedding adapter lands
(M4), only that adapter and an enrolment flow are new — the session key already
includes ``speaker_id`` and per-user context already hangs off the profile.

Rule: downstream code must work when the speaker is the household default
(``Speaker.is_known`` is ``False``).
"""

from __future__ import annotations

from jarvis.domain.models import Room, Speaker
from jarvis.ports.speaker_id import AudioRef

__all__ = ["NullSpeakerIdentifier"]


class NullSpeakerIdentifier:
    def __init__(self, default: Speaker | None = None) -> None:
        # The household profile may later come from config; default to the
        # canonical household speaker.
        self._default = default or Speaker.household()

    async def identify(self, audio_or_ref: AudioRef | None, room: Room) -> Speaker:
        return self._default
