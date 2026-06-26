"""The Jarvis conversation-agent integration for Home Assistant.

Bridges HA's Assist pipeline to the conductor: it registers a conversation agent
that forwards each turn to the conductor's ``/ingress/utterance`` endpoint and
speaks the reply. This is HA-runtime code (it imports ``homeassistant``) and so
lives outside the conductor's package and CI gate; it's verified on the box.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.CONVERSATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
