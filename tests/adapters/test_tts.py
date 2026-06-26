"""Tests for the voice adapters (README §5, §6)."""

from jarvis.adapters.tts import HaPiperTextToSpeech, NullTextToSpeech
from jarvis.ports import TextToSpeech
from tests.fakes import FakeHomeAssistant


def test_adapters_satisfy_the_port():
    assert isinstance(HaPiperTextToSpeech(FakeHomeAssistant()), TextToSpeech)
    assert isinstance(NullTextToSpeech(), TextToSpeech)


async def test_speaks_to_mapped_media_player():
    hub = FakeHomeAssistant()
    voice = HaPiperTextToSpeech(
        hub,
        tts_entity_id="tts.piper",
        area_to_media_player={"kitchen": "media_player.kitchen"},
    )
    await voice.speak("dinner's ready", area="kitchen")

    call = hub.service_calls[0]
    assert (call.domain, call.service) == ("tts", "speak")
    assert call.data["message"] == "dinner's ready"
    assert call.data["media_player_entity_id"] == "media_player.kitchen"
    assert call.target["entity_id"] == "tts.piper"


async def test_falls_back_to_area_target_when_unmapped():
    hub = FakeHomeAssistant()
    voice = HaPiperTextToSpeech(hub)
    await voice.speak("hello den", area="den")

    call = hub.service_calls[0]
    assert "media_player_entity_id" not in call.data
    assert call.target["area_id"] == "den"


async def test_null_tts_is_a_noop():
    # Must not raise; simply does nothing (HA speaks the returned text).
    await NullTextToSpeech().speak("anything", area="kitchen")
