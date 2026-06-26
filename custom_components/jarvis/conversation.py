"""The Jarvis conversation agent.

Forwards each Assist turn to the conductor's ``/ingress/utterance`` endpoint and
speaks the returned text. The originating area is resolved from the calling
device (device registry → area), so the conductor knows which room asked.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEFAULT_AREA,
    CONF_URL,
    DEFAULT_AREA,
    DEFAULT_URL,
    REQUEST_TIMEOUT_S,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([JarvisConversationAgent(entry)])


class JarvisConversationAgent(conversation.ConversationEntity):
    """A conversation agent that delegates to the Jarvis conductor."""

    _attr_has_entity_name = True
    _attr_name = "Jarvis"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | str:
        # The conductor (Claude) handles any language; let HA send them all.
        return MATCH_ALL

    def _resolve_area(self, user_input: conversation.ConversationInput) -> str:
        """Map the calling device to its HA area; fall back to the configured default."""
        default_area = self._entry.data.get(CONF_DEFAULT_AREA, DEFAULT_AREA)
        if not user_input.device_id:
            return default_area
        device = dr.async_get(self.hass).async_get(user_input.device_id)
        if device and device.area_id:
            return device.area_id
        return default_area

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        url = self._entry.data.get(CONF_URL, DEFAULT_URL).rstrip("/") + "/ingress/utterance"
        payload = {
            "text": user_input.text,
            "area": self._resolve_area(user_input),
            "conversation_id": user_input.conversation_id,
        }

        intent_response = intent.IntentResponse(language=user_input.language)
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_S):
                async with session.post(url, json=payload) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            speech = data.get("text", "")
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Could not reach the Jarvis conductor at %s: %s", url, err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                "Sorry, I couldn't reach Jarvis right now.",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=user_input.conversation_id
            )

        intent_response.async_set_speech(speech)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=user_input.conversation_id
        )
