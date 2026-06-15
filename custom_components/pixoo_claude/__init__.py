"""Pixoo Claude — Claude usage + monitored sensors on a Divoom Pixoo 64."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

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
    CLAUDE_REPUSH_HEARTBEAT, CONF_ALERT_PRIORITY, CONF_BRIGHTNESS,
    CONF_CLAUDE_ENABLED, CONF_CLOUD_WHEN_IDLE, CONF_DANCE, CONF_FLASH_THRESHOLD,
    CONF_INVERT, CONF_IP_ADDRESS, CONF_NAME, CONF_PAGE_SECONDS, CONF_SHOW_CLOCK,
    DOMAIN, SUBENTRY_TYPE_MONITOR,
)
from .helpers import (
    find_claude_entities, is_truthy_state, monitor_value_text, parse_float,
    reset_countdown_coarse, state_to_percent, threshold_to_pct,
)
from .render import build_frames, build_sensor_page_frames

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []  # no entities — driven entirely by the display loop


def _clamp_pct(value: float | None) -> int | None:
    if value is None:
        return None
    return max(0, int(round(value)))


def _apply_display(hass: HomeAssistant, entry: ConfigEntry, entry_data: dict[str, Any]) -> None:
    """Set up (or restart) the rotating display loop for one entry.

    Pages = the Claude usage screen (if enabled and has data) + one page per
    monitored-sensor subentry. The carousel advances one page every
    ``page_seconds``; a watched-entity change re-renders the *current* page
    without advancing. With nothing to show, optionally hand the panel back to
    the Divoom cloud channel.
    """
    for key in ("display_unsub", "display_state_unsub"):
        unsub = entry_data.get(key)
        if unsub is not None:
            unsub()
            entry_data[key] = None

    ip: str = entry_data["ip_address"]
    session = async_get_clientsession(hass)

    claude_enabled = entry.options.get(CONF_CLAUDE_ENABLED, True)
    cloud_when_idle = entry.options.get(CONF_CLOUD_WHEN_IDLE, False)
    invert = entry.options.get(CONF_INVERT, False)
    flash_threshold = entry.options.get(CONF_FLASH_THRESHOLD, 95)
    dance = entry.options.get(CONF_DANCE, False)
    page_seconds = max(2, int(entry.options.get(CONF_PAGE_SECONDS, 8)))
    alert_priority = entry.options.get(CONF_ALERT_PRIORITY, True)

    def _monitors() -> list:
        return [s for s in entry.subentries.values()
                if s.subentry_type == SUBENTRY_TYPE_MONITOR]

    if not claude_enabled and not _monitors():
        # Nothing configured to show — hand the panel back to the cloud channel.
        hass.async_create_task(pixoo.async_set_channel(session, ip, pixoo.CHANNEL_CLOUD))
        return

    entry_data["last_sig"] = None
    entry_data["last_push"] = 0.0
    entry_data["page_index"] = 0

    def _claude_data() -> dict[str, Any] | None:
        """Claude usage as a render dict + sig, or None to skip the page (no
        data, or idle while cloud_when_idle so the panel can fall through)."""
        ent = find_claude_entities(hass)
        states = {k: hass.states.get(v) for k, v in ent.items()}

        def num(key: str) -> float | None:
            s = states.get(key)
            return parse_float(s.state) if s else None

        session_pct = _clamp_pct(num("session_usage_percent"))
        week_pct = _clamp_pct(num("week_usage_percent"))
        if session_pct is None and week_pct is None:
            return None

        s_pct = session_pct if session_pct is not None else 0
        w_pct = week_pct if week_pct is not None else 0
        if cloud_when_idle and s_pct <= 0:
            return None

        s_full = session_pct is not None and session_pct >= 100
        w_full = week_pct is not None and week_pct >= 100
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

        sig = ("claude", s_pct, w_pct, credits_txt, session_reset, week_reset,
               clock_txt, invert, flash_threshold, dance)
        return {
            "kind": "claude", "sig": sig,
            "session": s_pct, "week": w_pct, "credits_txt": credits_txt,
            "session_reset": session_reset, "week_reset": week_reset,
            "clock_txt": clock_txt,
        }

    def _sensor_data(sub) -> dict[str, Any] | None:
        """Monitored sensor as a render dict + sig, or None if unavailable."""
        cfg = sub.data
        entity_id = cfg.get("entity_id")
        st = hass.states.get(entity_id) if entity_id else None
        if st is None or str(st.state).lower() in ("unknown", "unavailable", "none", ""):
            return None
        if parse_float(st.state) is None:
            return None

        min_v = float(cfg.get("min_value", 0))
        max_v = float(cfg.get("max_value", 100))
        value_type = cfg.get("value_type", "percentage")
        unit = cfg.get("unit", "")
        threshold = float(cfg.get("threshold", 0))
        label = cfg.get("label") or sub.title or entity_id

        if value_type == "raw":
            pct = state_to_percent(st.state, min_v, max_v)
        else:
            pct = max(0, min(100, int(round(parse_float(st.state)))))
        value_txt = monitor_value_text(hass, entity_id, st.state, value_type, unit)
        over = threshold > 0 and pct >= threshold_to_pct(threshold, value_type, min_v, max_v)
        icon = cfg.get("icon", "none")
        icon = None if icon in (None, "", "none") else icon
        color = cfg.get("color", "white")

        sig = ("sensor", entity_id, pct, value_txt, over, label, icon, color)
        return {"kind": "sensor", "sig": sig, "label": label, "pct": pct,
                "value_txt": value_txt, "over": over, "icon": icon, "color": color}

    async def _refresh(advance: bool) -> None:
        rows = [sd for sub in _monitors() if (sd := _sensor_data(sub)) is not None]
        alerts = [r for r in rows if r["over"]]

        pages: list[dict[str, Any]] = []
        if alert_priority and alerts:
            # A breached sensor takes over: show only alert rows, skip Claude.
            sensor_rows = alerts
        else:
            sensor_rows = rows
            if claude_enabled:
                cd = _claude_data()
                if cd is not None:
                    pages.append(cd)
        # Monitored sensors share pages — up to 2 bars each.
        for i in range(0, len(sensor_rows), 2):
            chunk = sensor_rows[i:i + 2]
            sig = ("sensors", tuple(r["sig"] for r in chunk))
            pages.append({"kind": "sensors", "sig": sig, "rows": chunk})

        now_mono = time.monotonic()
        if not pages:
            if cloud_when_idle:
                idle_sig = ("cloud",)
                if (idle_sig == entry_data.get("last_sig")
                        and (now_mono - entry_data.get("last_push", 0.0)) < CLAUDE_REPUSH_HEARTBEAT):
                    return
                if await pixoo.async_set_channel(session, ip, pixoo.CHANNEL_CLOUD):
                    entry_data["last_sig"] = idle_sig
                    entry_data["last_push"] = now_mono
            return

        n = len(pages)
        if advance:
            entry_data["page_index"] = entry_data.get("page_index", 0) + 1
        idx = entry_data.get("page_index", 0) % n
        entry_data["page_index"] = idx
        page = pages[idx]

        sig = page["sig"]
        if (sig == entry_data.get("last_sig")
                and (now_mono - entry_data.get("last_push", 0.0)) < CLAUDE_REPUSH_HEARTBEAT):
            return

        if page["kind"] == "claude":
            frames, speed = await hass.async_add_executor_job(
                lambda: build_frames(
                    session=page["session"], week=page["week"],
                    credits_txt=page["credits_txt"],
                    session_reset=page["session_reset"], week_reset=page["week_reset"],
                    clock_txt=page["clock_txt"], invert=invert,
                    flash_threshold=flash_threshold, dance=dance,
                )
            )
        else:
            frames, speed = await hass.async_add_executor_job(
                lambda: build_sensor_page_frames(page["rows"])
            )

        ok = await pixoo.async_send_animation(session, ip, frames, entry_data, speed=speed)
        if ok:
            entry_data["last_sig"] = sig
            entry_data["last_push"] = now_mono

    async def _guarded_refresh(advance: bool) -> None:
        try:
            await _refresh(advance)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Pixoo display: refresh failed")

    @callback
    def _tick(_now: Any) -> None:
        hass.async_create_task(_guarded_refresh(advance=True))

    entry_data["display_unsub"] = async_track_time_interval(
        hass, _tick, timedelta(seconds=page_seconds)
    )

    watch_ids = list(find_claude_entities(hass).values())
    watch_ids += [s.data.get("entity_id") for s in _monitors() if s.data.get("entity_id")]
    if watch_ids:
        @callback
        def _on_state(event: Event) -> None:
            if event.data.get("new_state") is None:
                return
            hass.async_create_task(_guarded_refresh(advance=False))

        entry_data["display_state_unsub"] = async_track_state_change_event(
            hass, watch_ids, _on_state
        )

    hass.async_create_task(_guarded_refresh(advance=False))
    _LOGGER.debug("Pixoo display loop started for %s", ip)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pixoo Claude from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    ip_address: str = entry.data[CONF_IP_ADDRESS]
    name: str = entry.data[CONF_NAME]

    entry_data: dict[str, Any] = {
        "ip_address": ip_address,
        "name": name,
        "entry": entry,
        "display_unsub": None,
        "display_state_unsub": None,
        "last_sig": None,
        "last_push": 0.0,
        "page_index": 0,
        "gif_counter": None,  # synced from the device on first frame push
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    # Apply brightness from options on startup
    session = async_get_clientsession(hass)
    brightness = entry.options.get(CONF_BRIGHTNESS)
    if brightness is not None:
        hass.async_create_task(pixoo.async_set_brightness(session, ip_address, int(brightness)))

    _apply_display(hass, entry, entry_data)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-apply settings when the options flow (or a subentry) changes."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is None:
        return
    session = async_get_clientsession(hass)
    brightness = entry.options.get(CONF_BRIGHTNESS)
    if brightness is not None:
        hass.async_create_task(
            pixoo.async_set_brightness(session, entry_data["ip_address"], int(brightness))
        )
    _apply_display(hass, entry, entry_data)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is not None:
        for key in ("display_unsub", "display_state_unsub"):
            unsub = entry_data.get(key)
            if unsub is not None:
                unsub()
                entry_data[key] = None
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
