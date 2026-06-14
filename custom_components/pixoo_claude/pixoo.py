"""Async client for the Divoom Pixoo 64 local HTTP API.

The Pixoo exposes a JSON command endpoint at http://<ip>:80/post. We use:
  • Draw/ResetHttpGifId  — reset the GIF id before a fresh frame
  • Draw/SendHttpGif     — push a 64x64 RGB frame (base64 in PicData)
  • Channel/SetBrightness
  • Channel/SetIndex     — hand the panel back to a built-in channel
  • Device/GetDeviceTime — cheap reachability probe
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Built-in Pixoo channels (Channel/SetIndex → SelectIndex).
CHANNEL_FACES = 0       # clock faces
CHANNEL_CLOUD = 1       # Divoom online gallery
CHANNEL_VISUALIZER = 2
CHANNEL_CUSTOM = 3

# Frames are ~16 KB and the panel can be slow/lossy over weak WiFi — be patient.
_POST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_PROBE_TIMEOUT = aiohttp.ClientTimeout(total=8)


def _url(ip: str) -> str:
    return f"http://{ip}:80/post"


async def async_post(
    session: aiohttp.ClientSession, ip: str, payload: dict[str, Any],
    timeout: aiohttp.ClientTimeout = _POST_TIMEOUT,
) -> dict | None:
    """POST a command to the Pixoo. Returns the parsed JSON or None on failure."""
    try:
        async with session.post(_url(ip), json=payload, timeout=timeout) as resp:
            if resp.status >= 400:
                _LOGGER.warning("Pixoo at %s returned HTTP %s for %s",
                                ip, resp.status, payload.get("Command"))
                return None
            return await resp.json(content_type=None)
    except asyncio.CancelledError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.warning("Cannot reach Pixoo at %s (%s): %s",
                        ip, payload.get("Command"), err)
        return None


async def async_send_frame(
    session: aiohttp.ClientSession, ip: str, gif_payload: dict[str, Any],
    retries: int = 2,
) -> bool:
    """Reset the GIF id then push a Draw/SendHttpGif frame, with retries.

    Returns True if the device acknowledged (error_code 0).
    """
    for attempt in range(1, retries + 1):
        await async_post(session, ip, {"Command": "Draw/ResetHttpGifId"})
        result = await async_post(session, ip, gif_payload)
        if result is not None and result.get("error_code", 0) == 0:
            return True
        if attempt < retries:
            await asyncio.sleep(2)
    _LOGGER.warning("Pixoo at %s did not accept the frame after %d attempt(s)",
                    ip, retries)
    return False


async def async_set_brightness(
    session: aiohttp.ClientSession, ip: str, level: int
) -> None:
    """Set panel brightness (0-100)."""
    level = max(0, min(100, int(level)))
    await async_post(session, ip, {"Command": "Channel/SetBrightness", "Brightness": level})


async def async_set_channel(
    session: aiohttp.ClientSession, ip: str, index: int = CHANNEL_CLOUD
) -> bool:
    """Switch the panel to a built-in channel (e.g. the cloud gallery).

    Used to hand the screen back when we have nothing to show, instead of
    leaving a stale Claude frame frozen on the panel. Returns True on ack.
    """
    result = await async_post(
        session, ip, {"Command": "Channel/SetIndex", "SelectIndex": int(index)}
    )
    return result is not None and result.get("error_code", 0) == 0


async def async_reachable(ip: str) -> bool:
    """Probe the Pixoo with a cheap command. Used by the config flow."""
    try:
        async with aiohttp.ClientSession() as session:
            result = await async_post(
                session, ip, {"Command": "Device/GetDeviceTime"}, timeout=_PROBE_TIMEOUT
            )
            return result is not None
    except aiohttp.ClientError:
        return False
