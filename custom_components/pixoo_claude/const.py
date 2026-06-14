"""Constants for the Pixoo Claude integration."""

DOMAIN = "pixoo_claude"

CONF_IP_ADDRESS = "ip_address"
CONF_NAME = "name"

# Options keys
CONF_CLAUDE_ENABLED = "claude_enabled"
CONF_BRIGHTNESS = "brightness"
CONF_SHOW_CLOCK = "show_clock"
CONF_CLOUD_WHEN_IDLE = "cloud_when_idle"
CONF_INVERT = "invert"  # show remaining (100-usage) instead of usage

# ── hass-claude-usage integration (https://github.com/trickv/hass-claude-usage) ──
# Reused verbatim from the mini_screen_esp32 integration so the Pixoo reads the
# exact same sensors.
CLAUDE_DOMAIN = "hass_claude_usage"

# Sensor "keys" (suffix of the integration's unique_id: "{entry_id}_{key}")
CLAUDE_KEYS = {
    "session_usage_percent",
    "session_reset_time",
    "week_usage_percent",
    "week_reset_time",
    "extra_usage_enabled",
    "extra_usage_percent",
    "extra_usage_credits",
    "extra_usage_limit",
}

# Pixoo is a network framebuffer — it can't tick a countdown itself, so HA renders
# the whole frame and pushes it. To avoid hammering a ~16 KB POST over (often
# flaky) WiFi, countdowns are rendered at MINUTE resolution and frames are pushed
# only when the rendered content changes — plus a periodic recovery re-push.
PUSH_TICK_SECONDS = 15          # how often we re-evaluate (minute boundary, state)
CLAUDE_REPUSH_HEARTBEAT = 120   # force a re-push at least this often (recovery)
