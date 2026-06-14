# Ideas & deferred work

Notes on things we considered but deliberately left out, so the reasoning isn't
lost. Not a commitment — a parking lot.

## Animated frames (GIF) — what the Pixoo can actually do

`Draw/SendHttpGif` is an **animation** command, not just a still image:

- All frames of one animation share a single `PicID`; you send **one POST per
  frame** (no batching — `Draw/CommandList` can't bundle them), with
  `PicNum` = total frames and `PicOffset` = 0…N‑1. `PicSpeed` = ms per frame.
- The device **loops** the animation on its own once uploaded — it plays for
  "free" without re-pushing.
- Practical frame cap ≈ **40 safe / 59 hard**; more can crash the panel.
- Frame sizes must be 16×16, 32×32 or 64×64.

Refs: [pixoo-rest](https://github.com/4ch1m/pixoo-rest/blob/master/app.py),
[Grayda/pixoo_api NOTES](https://github.com/Grayda/pixoo_api/blob/main/NOTES.md),
[SomethingWithComputers/pixoo](https://github.com/SomethingWithComputers/pixoo).

### Loop-safe animations — good fit (deferred, not rejected)
Anything where *repeating looks correct* is ideal: send once, let it loop, no
timing needed (the 120s heartbeat re-push is enough).

- **Claude dance** — short ~6-frame pose loop on the `CLAUDE_GUY` sprite.
- **Bar flash ≥ threshold** — 2-frame bright/dim loop when session ≥ ~95% (and
  the existing FULL state). This is the proper fix for the currently-static
  "FULL" flash.

Both need shared plumbing: an `async_send_animation()` in `pixoo.py` (same
incrementing-PicID counter, but bump once per *animation*, all frames sharing
the id) and `render` returning a frame list.

### Ticking seconds by "baking" the next interval — considered, NOT pursued
Idea: generate N frames (one per second) for the next ~15s, push once, then on
the next tick push the next window with the minute updated.

Why it's fragile here:

1. **The GIF loops, it doesn't advance.** A 15-frame/1s clip plays 0→14 then
   loops back to 0. To show continuous seconds you must re-push *exactly* on the
   loop boundary; a late push (network/WiFi/HA jitter) makes the panel replay
   0–14 → visible stutter/rewind. `PicSpeed` isn't wall-accurate, so it drifts
   within the window too.
2. **Upload cost returns.** 15 frames = ~15 POSTs every 15s ≈ 1 POST/sec
   sustained (~240 KB/15s) — basically pushing every second, just bursted. That
   undoes the gentle "one POST per frame" design and, on this panel's flaky WiFi
   (~33% loss), a burst can take longer than the window and fall permanently
   behind.

**Decision:** keep the clock at minute resolution on our custom frame. If true
ticking seconds are ever wanted, the Pixoo's **native clock channel** does it
for free (trade-off: no Claude bars while shown). A loop-safe middle ground
(blinking `:` colon or a subtle "breathing" pulse) could add life without
needing wall-clock accuracy.
