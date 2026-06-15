# Tasks

Actionable, planned work. Background/rationale lives in [docs/ideas.md](docs/ideas.md).

## Animation support

Shared prerequisite for both tasks below:

- [x] **Multi-frame plumbing.** `async_send_animation(session, ip, frames, state, speed)`
      in `pixoo.py`: all frames share one incrementing `PicID`, sent one POST per
      frame (`PicNum`/`PicOffset`/`PicSpeed`), counter bumped once per animation.
      `render.build_frames()` returns a list of base64 frames + speed.

### 1. Bar flash ≥ threshold — done
- [x] 2-frame bright/dim blink when a metric ≥ threshold, and for FULL (≥100),
      replacing the previously-static red bar.
- [x] `flash_threshold` option (default 95, range 50–100; 100 = only FULL flashes).
- [x] Sent once; the device loops it. Works in invert mode (keyed off real usage).

### 2. Claude dance — done
- [x] Gentle idle **bob** (4-frame, ~220ms) that nudges only the critter's
      position — silhouette left untouched per the hard-won pixel art.
- [x] `dance` option (default off); plays only in the calm state — flash wins.

> Possible follow-up (not planned): true limb/pose animation would need new
> sprite frames and sign-off on the pixels, since it reshapes `CLAUDE_GUY`.

## Monitored sensors — done

- [x] Add sensors via **config subentries** + `EntitySelector` (the HA-idiomatic
      pattern, mirrors the mini-screen): entity, label, min/max, percentage/raw,
      alert threshold. Reconfigure + remove supported.
- [x] Generic **sensor render page** (title + wide bar + big value); reuses the
      flash blink when a value is at/above its threshold.
- [x] **Page-rotation** display loop: Claude usage + one page per available
      sensor, advancing every `page_seconds` (option, default 8). Watched-entity
      changes re-render the current page without advancing; nothing to show →
      cloud channel (when enabled).

- [x] **Combined sensor page** — up to 2 monitored sensors per page (stacked
      bars) instead of one-per-page; a single sensor is centred. Fewer rotations.
- [x] **Alert-priority mode** (`alert_priority`, default on) — a breached sensor
      takes over: show only over-threshold sensor(s) until they clear, skipping
      Claude + calm sensors.
- [x] **Per-sensor icon + accent color** — `icon` (none/bolt/cal/star/dot/square)
      and `color` per monitored sensor, applied to the icon + label; bar keeps
      its danger color.

> Follow-ups (not planned yet): possibly >2 bars on a page if labels stay
> legible; richer icon set (needs pixel-art + on-device preview). Arbitrary
> sensors, sensor-bars screen, rotation, alerts, and styling are all covered.

> Deferred (see ideas.md): ticking seconds via per-interval GIF baking — fragile
> on flaky WiFi + the loop-vs-advance mismatch.
