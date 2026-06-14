"""Async client for the Divoom Pixoo 64 local HTTP API.

The Pixoo exposes a JSON command endpoint at http://<ip>:80/post. We use:
  • Draw/GetHttpGifId    — read the device's current GIF id (sync our counter)
  • Draw/ResetHttpGifId  — reset the GIF id (only every N frames)
  • Draw/SendHttpGif     — push a 64x64 RGB frame (base64 in PicData)
  • Channel/SetBrightness
  • Channel/SetIndex     — hand the panel back to a built-in channel
  • Device/GetDeviceTime — cheap reachability probe

Push strategy mirrors the SomethingWithComputers/pixoo lib (and gickowtf's HA
integration): each frame uses a *monotonically incrementing* PicID synced from
the device, and we reset the GIF id only every REFRESH_COUNTER_LIMIT frames —
the documented way to dodge the firmware's "~300 frames then it freezes" bug.
That's one POST per frame (not reset+send each time), which is far gentler on
flaky WiFi than hammering a reset before every push.
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

# Reset the device GIF id once the counter passes this, to avoid the firmware
# freeze after a few hundred frames (same value the reference libs use).
REFRESH_COUNTER_LIMIT = 32

# Frames are ~16 KB and the panel can be slow/lossy over weak WiFi. One POST per
# frame + a moderate timeout; on failure we just give up and let the next tick
# (and the heartbeat re-push) recover — no retry storm.
_POST_TIMEOUT = aiohttp.ClientTimeout(total=15)
_PROBE_TIMEOUT = aiohttp.ClientTimeout(total=10)


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


async def async_get_gif_id(session: aiohttp.ClientSession, ip: str) -> int | None:
    """Read the device's current HTTP GIF id, so our counter starts in sync."""
    result = await async_post(session, ip, {"Command": "Draw/GetHttpGifId"})
    if result is not None and result.get("error_code", 0) == 0:
        try:
            return int(result.get("PicId", 0))
        except (TypeError, ValueError):
            return None
    return None


async def async_reset_gif_id(session: aiohttp.ClientSession, ip: str) -> None:
    """Reset the device's HTTP GIF id (done periodically, not per frame)."""
    await async_post(session, ip, {"Command": "Draw/ResetHttpGifId"})


async def async_send_animation(
    session: aiohttp.ClientSession, ip: str, frames: list[str],
    state: dict[str, Any], speed: int = 1000, width: int = 64, retries: int = 2,
) -> bool:
    """Push a (possibly multi-frame) animation via Draw/SendHttpGif.

    `frames` is a list of base64 PicData strings — one entry is just a static
    image. All frames of a push share one device-synced, incrementing PicID and
    are sent one POST each (PicOffset 0..N-1, PicNum = N, PicSpeed = ms/frame);
    the device then loops them on its own. The GIF buffer is reset only every
    REFRESH_COUNTER_LIMIT frames. `state` persists the counter across calls.
    Returns True only if every frame acked (error_code 0).
    """
    if not frames:
        return False

    counter = state.get("gif_counter")
    if counter is None:
        synced = await async_get_gif_id(session, ip)
        counter = synced if synced is not None else 0

    num = len(frames)
    ok = False
    for attempt in range(1, retries + 1):
        counter += 1
        if counter >= REFRESH_COUNTER_LIMIT:
            await async_reset_gif_id(session, ip)
            counter = 1

        all_acked = True
        for offset, pic_data in enumerate(frames):
            result = await async_post(session, ip, {
                "Command": "Draw/SendHttpGif",
                "PicNum": num,
                "PicWidth": width,
                "PicOffset": offset,
                "PicID": counter,
                "PicSpeed": speed,
                "PicData": pic_data,
            })
            if result is None or result.get("error_code", 0) != 0:
                all_acked = False
                break

        if all_acked:
            ok = True
            break
        if attempt < retries:
            await asyncio.sleep(3)

    state["gif_counter"] = counter
    if not ok:
        _LOGGER.warning("Pixoo at %s did not accept the %d-frame animation after %d attempt(s)",
                        ip, num, retries)
    return ok


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
