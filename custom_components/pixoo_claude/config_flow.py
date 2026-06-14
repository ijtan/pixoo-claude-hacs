"""Config flow for the Pixoo Claude integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector, SelectOptionDict, SelectSelector, SelectSelectorConfig,
)

from . import pixoo
from .const import (
    CONF_BRIGHTNESS, CONF_CLAUDE_ENABLED, CONF_CLOUD_WHEN_IDLE, CONF_DANCE,
    CONF_FLASH_THRESHOLD, CONF_INVERT, CONF_IP_ADDRESS, CONF_NAME,
    CONF_PAGE_SECONDS, CONF_SHOW_CLOCK, DOMAIN, SUBENTRY_TYPE_MONITOR,
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Monitored sensors are added as subentries on this config entry."""
        return {SUBENTRY_TYPE_MONITOR: PixooMonitorSubentryFlow}


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
                    CONF_PAGE_SECONDS:    user_input.get(CONF_PAGE_SECONDS, 8),
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
            vol.Optional(CONF_PAGE_SECONDS, default=opts.get(CONF_PAGE_SECONDS, 8)):
                vol.All(int, vol.Range(min=2, max=60)),
            vol.Optional(CONF_SHOW_CLOCK, default=opts.get(CONF_SHOW_CLOCK, True)): bool,
            vol.Optional(CONF_BRIGHTNESS, default=opts.get(CONF_BRIGHTNESS, 80)):
                vol.All(int, vol.Range(min=0, max=100)),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


class PixooMonitorSubentryFlow(ConfigSubentryFlow):
    """Add / edit a monitored sensor shown as a rotating page on the panel."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._show_form(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._show_form(user_input, reconfigure=True)

    async def _show_form(
        self, user_input: dict[str, Any] | None, reconfigure: bool = False,
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        existing: dict[str, Any] = {}
        if reconfigure:
            existing = dict(self._get_reconfigure_subentry().data)

        if user_input is not None:
            try:
                entity_id = str(user_input["entity_id"]).strip()
                label = str(user_input.get("label", "")).strip()
                min_value = float(user_input.get("min_value", 0))
                max_value = float(user_input.get("max_value", 100))
                value_type = str(user_input.get("value_type", "percentage"))
                unit = str(user_input.get("unit", "")).strip()
                threshold = float(user_input.get("threshold", 0))
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_monitor_config"
            else:
                if not entity_id or value_type not in {"percentage", "raw"}:
                    errors["base"] = "invalid_monitor_config"
                elif max_value <= min_value:
                    errors["base"] = "invalid_range"
                elif value_type == "percentage" and not 0 <= threshold <= 100:
                    errors["base"] = "threshold_range"
                else:
                    title = label or entity_id.split(".")[-1].replace("_", " ").title()
                    data = {
                        "entity_id": entity_id,
                        "label": label,
                        "min_value": min_value,
                        "max_value": max_value,
                        "value_type": value_type,
                        "unit": unit,
                        "threshold": threshold,
                    }
                    if reconfigure:
                        return self.async_update_and_abort(
                            self._get_entry(),
                            self._get_reconfigure_subentry(),
                            title=title, data=data,
                        )
                    return self.async_create_entry(title=title, data=data)

        schema = vol.Schema({
            vol.Required("entity_id", default=existing.get("entity_id", "")): EntitySelector(),
            vol.Optional("label", default=existing.get("label", "")): str,
            vol.Optional("min_value", default=existing.get("min_value", 0)): vol.Coerce(float),
            vol.Optional("max_value", default=existing.get("max_value", 100)): vol.Coerce(float),
            vol.Optional("value_type", default=existing.get("value_type", "percentage")):
                SelectSelector(SelectSelectorConfig(options=[
                    SelectOptionDict(value="percentage", label="Percentage"),
                    SelectOptionDict(value="raw", label="Raw value"),
                ])),
            vol.Optional("unit", default=existing.get("unit", "")): str,
            vol.Optional("threshold", default=existing.get("threshold", 0)): vol.Coerce(float),
        })
        step = "reconfigure" if reconfigure else "user"
        return self.async_show_form(step_id=step, data_schema=schema, errors=errors)
