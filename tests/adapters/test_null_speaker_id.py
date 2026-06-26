"""Tests for the null SpeakerIdentifier adapter (README §3.7, §7)."""

from jarvis.adapters.speaker_id import NullSpeakerIdentifier
from jarvis.domain.models import HOUSEHOLD_SPEAKER_ID, Room, Speaker, SpeakerProfile
from jarvis.ports import SpeakerIdentifier


def test_satisfies_the_port():
    assert isinstance(NullSpeakerIdentifier(), SpeakerIdentifier)


async def test_returns_household_default_and_ignores_audio():
    resolver = NullSpeakerIdentifier()
    room = Room(id="kitchen", area="kitchen")
    speaker = await resolver.identify(None, room)
    assert speaker.id == HOUSEHOLD_SPEAKER_ID
    # The household speaker is the "unknown" identity; downstream must cope.
    assert speaker.is_known is False
    # Audio is ignored — same result regardless of what's passed.
    assert (await resolver.identify(b"some-audio", room)).id == HOUSEHOLD_SPEAKER_ID


async def test_accepts_an_injected_default():
    custom = Speaker(id="household", profile=SpeakerProfile(display_name="Home"))
    resolver = NullSpeakerIdentifier(default=custom)
    assert (await resolver.identify(None, Room(id="den", area="den"))) is custom
