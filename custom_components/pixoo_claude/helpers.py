"""Shared helpers for the Pixoo Claude integration."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import CLAUDE_DOMAIN, CLAUDE_KEYS, DOMAIN


def device_info(entry_id: str, name: str) -> DeviceInfo:
    """Return a DeviceInfo block for a Pixoo Claude config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=name,
        manufacturer="Divoom",
        model="Pixoo 64",
    )


def parse_float(state_value: Any) -> float | None:
    """Parse a sensor state into a float, or None if not numeric."""
    try:
        return float(state_value)
    except (TypeError, ValueError):
        return None


def is_truthy_state(state_value: Any) -> bool:
    """Return True for the various ways an 'on' / enabled state is rendered."""
    return str(state_value).strip().lower() in {"true", "on", "1", "yes", "enabled"}


def state_to_percent(state_value: Any, min_value: float, max_value: float) -> int:
    """Scale a raw sensor value into a 0-100 percentage (clamped)."""
    raw = parse_float(state_value)
    if raw is None:
        return 0
    span = max_value - min_value
    if span == 0:
        return 0
    return max(0, min(100, int(round((raw - min_value) / span * 100.0))))


def threshold_to_pct(
    raw: float, value_type: str, min_value: float, max_value: float
) -> int:
    """Convert a configured threshold (raw or %) to a 0-100 percentage."""
    if value_type == "raw":
        return state_to_percent(raw, min_value, max_value)
    return max(0, min(100, int(round(raw))))


def monitor_value_text(
    hass: HomeAssistant, entity_id: str, state_value: Any, value_type: str, unit: str
) -> str:
    """Text shown under a monitored sensor's bar.

    Percentage mode → "" (the renderer shows "<pct>%"); raw mode → the raw value
    with a unit suffix (explicit unit, else the entity's own unit_of_measurement).
    """
    if value_type != "raw":
        return ""
    suffix = unit.strip()
    if not suffix:
        state = hass.states.get(entity_id)
        suffix = state.attributes.get("unit_of_measurement", "") if state else ""
    return f"{state_value} {suffix}".strip()


def find_claude_entities(hass: HomeAssistant) -> dict[str, str]:
    """Locate the hass-claude-usage sensors via the entity registry.

    Returns a dict mapping each known sensor key (see CLAUDE_KEYS) to its current
    entity_id, matched on the unique_id suffix so it survives entity renames.
    Identical to the mini_screen_esp32 implementation — both read the same sensors.
    """
    registry = er.async_get(hass)
    found: dict[str, str] = {}
    for ent in registry.entities.values():
        if ent.platform != CLAUDE_DOMAIN:
            continue
        uid = ent.unique_id or ""
        ce = ent.config_entry_id or ""
        key = uid[len(ce) + 1:] if ce and uid.startswith(ce + "_") else uid
        if key in CLAUDE_KEYS:
            found[key] = ent.entity_id
    return found


def reset_countdown_coarse(state_value: Any) -> str:
    """Format a reset-timestamp sensor state as a MINUTE-resolution countdown.

    The Pixoo can't tick a countdown itself and we don't want a per-second 16 KB
    push, so granularity stops at minutes:
      • under 1 hour → "59M"
      • under 1 day  → "4H12M"
      • else         → "3D6H"
    Returns "NOW" if past, or "" if unparseable. Output is upper-case to match
    the on-screen font.
    """
    if not state_value or str(state_value).lower() in {"unknown", "unavailable", "none"}:
        return ""
    target = dt_util.parse_datetime(str(state_value))
    if target is None:
        return ""
    now = dt_util.utcnow()
    if target.tzinfo is None:
        target = target.replace(tzinfo=now.tzinfo)
    delta = int((target - now).total_seconds())
    if delta <= 0:
        return "NOW"
    minutes = delta // 60
    if minutes < 60:
        return f"{minutes}M"
    hours, rem_m = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}H{rem_m:02d}M"
    days, rem_h = divmod(hours, 24)
    return f"{days}D{rem_h}H"
