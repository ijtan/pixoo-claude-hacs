# Pixoo Claude — Home Assistant Integration

A HACS custom integration that shows your **Claude usage** on a [Divoom Pixoo 64](https://divoom.com/products/pixoo-64) (64×64 RGB LED matrix), driven over the Pixoo's local HTTP API — no cloud, no Divoom account.

It reads the sensors from the [hass-claude-usage](https://github.com/trickv/hass-claude-usage) integration and renders a purpose-built 64×64 frame in Home Assistant, then pushes it to the panel.

![Pixoo Claude — normal and full states](docs/preview.png)

## What it shows

**Normal** — a Claude critter + clock header, then **Session** and **Week** usage as colour-coded bars (green → amber → red), each with its own reset countdown.

**When a limit is hit** — the maxed metric flips to **red / FULL** with its reset time, and your **Extra-usage credits** appear as an amount/total (e.g. `240 / 500`) instead of a bar.

The screen switches between these states automatically.

## Requirements

- A Divoom Pixoo 64 on your LAN with a reachable IP (the Divoom app shows it; a static DHCP lease is recommended).
- The [hass-claude-usage](https://github.com/trickv/hass-claude-usage) integration installed and reporting sensors.
- Home Assistant with HACS.

## Installation (HACS custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/ijtan/pixoo-claude-hacs` with category **Integration**.
3. Install **Pixoo Claude**, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → search **Pixoo Claude**.
5. Enter a name and your Pixoo's IP address.

## Options

After setup, open the integration's **Configure**:

| Option | Default | Description |
|---|---|---|
| Pixoo IP address | — | Edit if the device IP changes |
| Show Claude usage | on | Master enable for the render loop |
| Show clock in header | on | Toggle the header clock |
| Brightness | 80 | Panel brightness (0–100) |

## How it works

The Pixoo is a network framebuffer — it can't compute a countdown itself, so Home Assistant renders the whole 64×64 frame (Pillow, already bundled with HA) and POSTs it via `Draw/SendHttpGif`. Countdowns are rendered at **minute resolution** and frames are pushed **only when the content changes**, plus a periodic recovery re-push, to keep traffic light over WiFi.

## Credits

Inspired by the [Mini Screen ESP32](https://github.com/ijtan/mini-screen-esp32-hacs) integration, which shows the same Claude sensors on a monochrome OLED.

## Disclaimer

Not affiliated with Anthropic or Divoom. "Claude" is a trademark of Anthropic.
