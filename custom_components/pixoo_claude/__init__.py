"""Pixoo Claude — show Claude usage on a Divoom Pixoo 64."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from . import pixoo
from .const import (
    CLAUDE_REPUSH_HEARTBEAT, CONF_BRIGHTNESS, CONF_CLAUDE_ENABLED, CONF_IP_ADDRESS,
    CONF_NAME, CONF_SHOW_CLOCK, DOMAIN, PUSH_TICK_SECONDS,
)
from .helpers import (
    find_claude_entities, is_truthy_state, parse_float, reset_countdown_coarse,
)
from .render import build_gif_payload

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []  # no entities yet — driven entirely by the Claude loop


def _clamp_pct(value: float | None) -> int | None:
    if value is None:
        return None
    return max(0, int(round(value)))


def _apply_claude(hass: HomeAssistant, entry: ConfigEntry, entry_data: dict[str, Any]) -> None:
    """Set up (or restart) the Claude usage render+push loop for one entry."""
    for key in ("claude_unsub", "claude_state_unsub"):
        unsub = entry_data.get(key)
        if unsub is not None:
            unsub()
            entry_data[key] = None

    if not entry.options.get(CONF_CLAUDE_ENABLED, True):
        return

    ip: str = entry_data["ip_address"]
    session = async_get_clientsession(hass)
    entry_data["last_sig"] = None
    entry_data["last_push"] = 0.0

    async def _refresh_claude() -> None:
        ent = find_claude_entities(hass)
        states = {k: hass.states.get(v) for k, v in ent.items()}

        def num(key: str) -> float | None:
            s = states.get(key)
            return parse_float(s.state) if s else None

        session_pct = _clamp_pct(num("session_usage_percent"))
        week_pct = _clamp_pct(num("week_usage_percent"))
        if session_pct is None and week_pct is None:
            return  # nothing usable yet — leave whatever is on the panel

        s_pct = session_pct if session_pct is not None else 0
        w_pct = week_pct if week_pct is not None else 0
        s_full = session_pct is not None and session_pct >= 100
        w_full = week_pct is not None and week_pct >= 100

        # Extra/credits surface only once a limit is hit and overflow has started.
        extra_enabled = (
            is_truthy_state(states["extra_usage_enabled"].state)
            if states.get("extra_usage_enabled") else False
        )
        credits = num("extra_usage_credits") or 0.0
        limit = num("extra_usage_limit")
        credits_txt = ""
        if (s_full or w_full) and extra_enabled and credits > 0:
            credits_txt = f"{credits:.0f}/{limit:.0f}" if limit else f"{credits:.0f}"

        def reset_txt(key: str) -> str:
            s = states.get(key)
            return reset_countdown_coarse(s.state) if s else ""

        session_reset = reset_txt("session_reset_time")
        week_reset = reset_txt("week_reset_time")

        clock_txt = ""
        if entry.options.get(CONF_SHOW_CLOCK, True):
            now = dt_util.now()
            clock_txt = f"{now.hour}:{now.minute:02d}"

        # Dedupe on everything that affects the rendered frame; force a periodic
        # re-push so a rebooted/desynced panel recovers.
        sig = (s_pct, w_pct, credits_txt, session_reset, week_reset, clock_txt)
        now_mono = time.monotonic()
        if (sig == entry_data.get("last_sig")
                and (now_mono - entry_data.get("last_push", 0.0)) < CLAUDE_REPUSH_HEARTBEAT):
            return

        payload = await hass.async_add_executor_job(
            lambda: build_gif_payload(
                session=s_pct, week=w_pct, credits_txt=credits_txt,
                session_reset=session_reset, week_reset=week_reset,
                clock_txt=clock_txt,
            )
        )
        ok = await pixoo.async_send_frame(session, ip, payload)
        if ok:
            entry_data["last_sig"] = sig
            entry_data["last_push"] = now_mono

    @callback
    def _tick(_now: Any) -> None:
        hass.async_create_task(_guarded_refresh())

    async def _guarded_refresh() -> None:
        try:
            await _refresh_claude()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Pixoo Claude: refresh failed")

    entry_data["claude_unsub"] = async_track_time_interval(
        hass, _tick, timedelta(seconds=PUSH_TICK_SECONDS)
    )

    claude_entity_ids = list(find_claude_entities(hass).values())
    if claude_entity_ids:
        @callback
        def _on_state(event: Event) -> None:
            if event.data.get("new_state") is None:
                return
            hass.async_create_task(_guarded_refresh())

        entry_data["claude_state_unsub"] = async_track_state_change_event(
            hass, claude_entity_ids, _on_state
        )

    hass.async_create_task(_guarded_refresh())
    _LOGGER.debug("Pixoo Claude loop started for %s", ip)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pixoo Claude from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    ip_address: str = entry.data[CONF_IP_ADDRESS]
    name: str = entry.data[CONF_NAME]

    entry_data: dict[str, Any] = {
        "ip_address": ip_address,
        "name": name,
        "entry": entry,
        "claude_unsub": None,
        "claude_state_unsub": None,
        "last_sig": None,
        "last_push": 0.0,
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    # Apply brightness from options on startup
    session = async_get_clientsession(hass)
    brightness = entry.options.get(CONF_BRIGHTNESS)
    if brightness is not None:
        hass.async_create_task(pixoo.async_set_brightness(session, ip_address, int(brightness)))

    _apply_claude(hass, entry, entry_data)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-apply settings when the options flow saves."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is None:
        return
    session = async_get_clientsession(hass)
    brightness = entry.options.get(CONF_BRIGHTNESS)
    if brightness is not None:
        hass.async_create_task(
            pixoo.async_set_brightness(session, entry_data["ip_address"], int(brightness))
        )
    _apply_claude(hass, entry, entry_data)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is not None:
        for key in ("claude_unsub", "claude_state_unsub"):
            unsub = entry_data.get(key)
            if unsub is not None:
                unsub()
                entry_data[key] = None
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
