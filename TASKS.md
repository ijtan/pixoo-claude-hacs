# Tasks

Actionable, planned work. Background/rationale lives in [docs/ideas.md](docs/ideas.md).

## Animation support

Shared prerequisite for both tasks below:

- [ ] **Multi-frame plumbing.** Add `async_send_animation(session, ip, frames, state, speed)`
      to `pixoo.py`: all frames share one `PicID`, sent as one POST per frame
      (`PicNum` = len, `PicOffset` = 0…N‑1, `PicSpeed` = ms/frame), then bump the
      GIF counter once for the whole animation. Have `render` (optionally) return
      a list of frames instead of a single image.

### 1. Bar flash ≥ threshold
- [ ] 2-frame bright/dim loop on a bar when session ≥ ~95% (and reuse for the
      existing FULL state, replacing the current static red bar).
- [ ] Configurable threshold option (default ~95%); FULL (100%) always flashes.
- [ ] Send once and let the device loop it (no per-tick re-push needed).

### 2. Claude dance
- [ ] ~6-frame pose loop on the `CLAUDE_GUY` sprite (leg/arm shuffle), `PicSpeed`
      ~120–150ms. Keep the approved silhouette — don't reshape it.
- [ ] Decide when it plays (e.g. idle/normal state) and gate behind an option.

> Deferred (see ideas.md): ticking seconds via per-interval GIF baking — fragile
> on flaky WiFi + the loop-vs-advance mismatch.
