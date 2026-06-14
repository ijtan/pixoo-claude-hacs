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

> Deferred (see ideas.md): ticking seconds via per-interval GIF baking — fragile
> on flaky WiFi + the loop-vs-advance mismatch.
