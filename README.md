# Pixoo Claude — Home Assistant Integration

A HACS custom integration that shows your **Claude usage** — and any Home
Assistant **sensors** you choose — on a [Divoom Pixoo 64](https://divoom.com/products/pixoo-64)
(64×64 RGB LED matrix), driven over the Pixoo's local HTTP API. No cloud, no
Divoom account.

Home Assistant renders each purpose-built 64×64 frame (Pillow, already bundled
with HA) and pushes it to the panel over your LAN.

![Pixoo Claude — normal and full states](docs/preview.png)

## What it shows

The panel rotates through **pages**, each shown for a configurable interval:

**Claude usage** (from the [hass-claude-usage](https://github.com/trickv/hass-claude-usage)
integration):
- *Normal* — a Claude critter + clock header, then **Session** and **Week**
  usage as colour-coded bars (green → amber → red), each with its own reset
  countdown.
- *When a limit is hit* — the maxed metric flips to **red / FULL** with its reset
  time, and your **Extra-usage credits** appear as an amount/total (e.g.
  `240 / 500`) instead of a bar.

**Monitored sensors** — each sensor you add (see below) appears as a labelled
bar; up to two share a page. A sensor that crosses its alert threshold can
**flash** and, optionally, **take over** the screen until it clears.

Extras: a bar **blinks** as it approaches its limit, the Claude mascot can do a
gentle idle **dance**, bars can show **remaining instead of used**, and the panel
can fall back to the Divoom **cloud channel** when there's nothing to show.

## Requirements

- A Divoom Pixoo 64 on your LAN with a reachable IP (the Divoom app shows it; a
  static DHCP lease is recommended). Enable **LAN control** in the Divoom app.
- Home Assistant with HACS.
- *(Optional, for the Claude page)* the
  [hass-claude-usage](https://github.com/trickv/hass-claude-usage) integration
  installed and reporting sensors.

## Installation (HACS custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/ijtan/pixoo-claude-hacs` with category **Integration**.
3. Install **Pixoo Claude**, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → search **Pixoo Claude**.
5. Enter a name and your Pixoo's IP address.

## Options

Open the integration's **Configure** dialog:

| Option | Default | Description |
|---|---|---|
| IP address | — | Edit if the device IP changes |
| Show Claude usage | on | Master switch for the Claude page. When off, the panel is handed back to the cloud channel |
| Use the cloud channel when idle | off | When there's no active session (usage 0%), show the Divoom cloud channel; return automatically once usage resumes |
| Show remaining instead of used | off | Display `100 − used %` rather than used %. Bars still redden as you run low |
| Flash a bar at or above this % | 95 | A bar blinks past this usage (100%/FULL always flashes). Set to 100 to flash only when maxed |
| Animate the Claude mascot | off | Gentle idle bob; pauses while a bar is flashing |
| Seconds per page | 8 | How long each page stays up before rotating |
| Breached sensors take over | on | A monitored sensor over its threshold shows alone until it clears, instead of waiting its rotation turn |
| Sensor bars per page | 2 | How many monitored-sensor bars stack on one page (1–4); more = denser rows |
| Show the clock | on | Header clock (top-right) |
| Brightness | 80 | Panel brightness (0–100) |

## Monitored sensors

Add any HA sensor as a rotating page: on the integration's device, use
**Add → Monitored sensor** (a config *subentry*). Add as many as you like;
reconfigure or remove them the same way.

| Field | Description |
|---|---|
| Entity | The sensor to track |
| Label | Shown above the bar (defaults to the entity name) |
| Minimum / Maximum value | Map the raw value to 0% / 100% on the bar |
| Value display | Show a **percentage** or the **raw value** under the bar |
| Unit | Suffix for raw display (blank = the entity's own unit) |
| Alert threshold | Flash (and prioritise) at/above this. Percentage mode: 0–100; raw mode: the raw value. `0` = no alert |
| Icon | Small glyph next to the label (none / bolt / calendar / star / dot / square) |
| Accent color | Colour for the icon + label (the bar keeps its danger colour) |

## How it works

The Pixoo is a network framebuffer — it can't compute a countdown itself, so HA
renders the whole 64×64 frame and POSTs it via `Draw/SendHttpGif`. Notes:

- Countdowns render at **minute resolution**; frames are pushed **only when the
  content changes**, plus a periodic recovery re-push, to keep WiFi traffic
  light.
- **Animations** (flash, dance) are real multi-frame GIFs: one POST per frame,
  sharing an incrementing `PicID`, looped on the device. The GIF id is synced
  from the panel and reset every 32 frames to dodge the firmware's long-run
  freeze — see [docs/ideas.md](docs/ideas.md).
- Pages rotate on a timer; a watched entity changing re-renders the current page
  without advancing the carousel.

## Credits

Inspired by the [Mini Screen ESP32](https://github.com/ijtan/mini-screen-esp32-hacs)
integration, which shows the same Claude sensors on a monochrome OLED. Push
strategy follows [SomethingWithComputers/pixoo](https://github.com/SomethingWithComputers/pixoo)
and [gickowtf/pixoo-homeassistant](https://github.com/gickowtf/pixoo-homeassistant).

## Disclaimer

Not affiliated with Anthropic or Divoom. "Claude" is a trademark of Anthropic.
