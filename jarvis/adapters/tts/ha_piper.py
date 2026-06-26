"""The voice — speak a reply into a room via Home Assistant / Piper (README §5, §6).

Depends on the ``HomeAssistant`` port (never on the hub's REST adapter directly),
so it is testable against the hub fake. It calls a configurable TTS service
(``tts.speak`` by default) targeting the originating area.

Exactly which service and target shape a given Home Assistant install wants is
deployment-specific (``tts.speak`` vs ``assist_satellite.announce``, media-player
per area, etc.), so the service, the TTS entity, and the area→media-player map are
all configurable and verified on the box (README §10 acceptance). This adapter is
used for *proactive* speech — async-job acks and completion notices (M2); in the
M1 conversation-agent path the reply text is spoken by Home Assistant's own
pipeline (see ``NullTextToSpeech``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jarvis.ports.home_assistant import HomeAssistant

__all__ = ["HaPiperTextToSpeech"]


class HaPiperTextToSpeech:
    def __init__(
        self,
        hub: HomeAssistant,
        *,
        tts_entity_id: str = "tts.piper",
        service: tuple[str, str] = ("tts", "speak"),
        area_to_media_player: Mapping[str, str] | None = None,
    ) -> None:
        self._hub = hub
        self._tts_entity_id = tts_entity_id
        self._service = service
        self._area_to_media_player = dict(area_to_media_player or {})

    async def speak(self, text: str, *, area: str) -> None:
        domain, service = self._service
        data: dict[str, Any] = {"message": text, "cache": True}
        target: dict[str, Any] = {"entity_id": self._tts_entity_id}

        media_player = self._area_to_media_player.get(area)
        if media_player is not None:
            data["media_player_entity_id"] = media_player
        else:
            # Fall back to area targeting when no explicit media player is mapped.
            target["area_id"] = area

        await self._hub.call_service(domain, service, data=data, target=target)
