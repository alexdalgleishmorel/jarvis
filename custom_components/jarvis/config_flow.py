"""Config flow — ask for the conductor URL (and default area) in the UI."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_DEFAULT_AREA, CONF_URL, DEFAULT_AREA, DEFAULT_URL, DOMAIN


class JarvisConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Jarvis", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=DEFAULT_URL): str,
                vol.Optional(CONF_DEFAULT_AREA, default=DEFAULT_AREA): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
