"""Config flow for the Pixoo Claude integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from . import pixoo
from .const import (
    CONF_BRIGHTNESS, CONF_CLAUDE_ENABLED, CONF_CLOUD_WHEN_IDLE, CONF_DANCE,
    CONF_FLASH_THRESHOLD, CONF_INVERT, CONF_IP_ADDRESS, CONF_NAME,
    CONF_SHOW_CLOCK, DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Pixoo Claude"


class PixooClaudeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_address: str = user_input[CONF_IP_ADDRESS].strip()
            name: str = user_input[CONF_NAME].strip()

            await self.async_set_unique_id(ip_address)
            self._abort_if_unique_id_configured()

            if not await pixoo.async_reachable(ip_address):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name, CONF_IP_ADDRESS: ip_address},
                )

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_IP_ADDRESS): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PixooClaudeOptionsFlow:
        return PixooClaudeOptionsFlow()


class PixooClaudeOptionsFlow(OptionsFlow):
    """Edit IP + display options after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current_ip: str = self.config_entry.data.get(CONF_IP_ADDRESS, "")
        opts = self.config_entry.options

        if user_input is not None:
            new_ip: str = user_input[CONF_IP_ADDRESS].strip()
            if not await pixoo.async_reachable(new_ip):
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_IP_ADDRESS: new_ip},
                )
                return self.async_create_entry(title="", data={
                    CONF_CLAUDE_ENABLED:  user_input.get(CONF_CLAUDE_ENABLED, True),
                    CONF_CLOUD_WHEN_IDLE: user_input.get(CONF_CLOUD_WHEN_IDLE, False),
                    CONF_INVERT:          user_input.get(CONF_INVERT, False),
                    CONF_FLASH_THRESHOLD: user_input.get(CONF_FLASH_THRESHOLD, 95),
                    CONF_DANCE:           user_input.get(CONF_DANCE, False),
                    CONF_SHOW_CLOCK:      user_input.get(CONF_SHOW_CLOCK, True),
                    CONF_BRIGHTNESS:      user_input.get(CONF_BRIGHTNESS, 80),
                })

        schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS, default=current_ip): str,
            vol.Optional(CONF_CLAUDE_ENABLED, default=opts.get(CONF_CLAUDE_ENABLED, True)): bool,
            vol.Optional(CONF_CLOUD_WHEN_IDLE, default=opts.get(CONF_CLOUD_WHEN_IDLE, False)): bool,
            vol.Optional(CONF_INVERT, default=opts.get(CONF_INVERT, False)): bool,
            vol.Optional(CONF_FLASH_THRESHOLD, default=opts.get(CONF_FLASH_THRESHOLD, 95)):
                vol.All(int, vol.Range(min=50, max=100)),
            vol.Optional(CONF_DANCE, default=opts.get(CONF_DANCE, False)): bool,
            vol.Optional(CONF_SHOW_CLOCK, default=opts.get(CONF_SHOW_CLOCK, True)): bool,
            vol.Optional(CONF_BRIGHTNESS, default=opts.get(CONF_BRIGHTNESS, 80)):
                vol.All(int, vol.Range(min=0, max=100)),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
