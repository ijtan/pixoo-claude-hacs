"""
64x64 RGB frame rendering for the Pixoo Claude integration.

Ported from tools/pixoo_claude_mock.py (the design sandbox) — crisp 3x5 pixel
font, 8x8 icons and the Claude critter sprite, all hand-drawn so they're pixel
exact at 64x64. Pure Pillow + Python; no Home Assistant imports here so it can
run in an executor thread.
"""
from __future__ import annotations

import base64

from PIL import Image

W = H = 64
BLACK = (0, 0, 0)
WHITE = (235, 235, 235)
DIM   = (60, 60, 60)              # bar track
GREY  = (140, 140, 150)          # footer / clock
RED   = (229, 57, 53)
CLAUDE_ORANGE = (217, 119, 87)   # Claude brand "clay" orange (#D97757)


def bar_color(pct: int):
    """Color thresholds — the whole point of going RGB."""
    if pct >= 100: return RED               # FULL
    if pct >= 85:  return (255, 87, 34)     # orange-red
    if pct >= 60:  return (255, 179, 0)     # amber
    return (61, 220, 132)                   # green


# ── Tiny 3x5 pixel font (uppercase, digits, a few symbols) ───────────────────
FONT = {
    'A': ["010","101","111","101","101"], 'B': ["110","101","110","101","110"],
    'C': ["011","100","100","100","011"], 'D': ["110","101","101","101","110"],
    'E': ["111","100","110","100","111"], 'F': ["111","100","110","100","100"],
    'G': ["011","100","101","101","011"], 'H': ["101","101","111","101","101"],
    'I': ["111","010","010","010","111"], 'J': ["001","001","001","101","010"],
    'K': ["101","101","110","101","101"], 'L': ["100","100","100","100","111"],
    'M': ["101","111","111","101","101"], 'N': ["101","111","111","111","101"],
    'O': ["010","101","101","101","010"], 'P': ["110","101","110","100","100"],
    'Q': ["010","101","101","110","011"], 'R': ["110","101","110","101","101"],
    'S': ["011","100","010","001","110"], 'T': ["111","010","010","010","010"],
    'U': ["101","101","101","101","111"], 'V': ["101","101","101","101","010"],
    'W': ["101","101","111","111","101"], 'X': ["101","101","010","101","101"],
    'Y': ["101","101","010","010","010"], 'Z': ["111","001","010","100","111"],
    '0': ["111","101","101","101","111"], '1': ["010","110","010","010","111"],
    '2': ["111","001","111","100","111"], '3': ["111","001","111","001","111"],
    '4': ["101","101","111","001","001"], '5': ["111","100","111","001","111"],
    '6': ["111","100","111","101","111"], '7': ["111","001","010","010","010"],
    '8': ["111","101","111","101","111"], '9': ["111","101","111","001","111"],
    '%': ["101","001","010","100","101"], ':': ["000","010","000","010","000"],
    '-': ["000","000","111","000","000"], '.': ["000","000","000","000","010"],
    '$': ["011","110","010","011","110"], '/': ["001","001","010","100","100"],
    ' ': ["000","000","000","000","000"],
}
CH_W, CH_H, CH_GAP = 3, 5, 1

# ── 8x8 icons ────────────────────────────────────────────────────────────────
ICONS = {
    "bolt": [  # session
        "00011100","00111000","01110000","11111100",
        "00111110","00011100","00111000","01100000"],
    "cal": [   # week
        "01000010","11111111","10000001","10110101",
        "10000001","10110101","10000001","11111111"],
    "star": [  # extra / credits
        "00011000","00011000","01011010","00111100",
        "01111110","00111100","01011010","00011000"],
}

# The Claude critter (user-tuned). 10px wide (even) so the 4 legs sit symmetric;
# body 8px (cols 1-8), arms poke out to cols 0/9 at eye level. Eyes are BLACK.
PALETTE = {"o": CLAUDE_ORANGE, "b": (0, 0, 0)}
CLAUDE_GUY = [
    " oooooooo ",   # square, flat forehead
    " oooooooo ",
    "oobooooboo",   # black eyes (1px, 1 in from each side) + arms (eye level)
    "oooooooooo",   # arms 2 tall
    " oooooooo ",
    " oooooooo ",
    " o o  o o ",   # legs: outer at sides, skip 1, then 2px gap dead-centre
    " o o  o o ",
]

MARGIN = 1  # 1px breathing room around the panel


class FB:
    """Tiny framebuffer over a PIL image."""

    def __init__(self):
        self.img = Image.new("RGB", (W, H), BLACK)
        self.px = self.img.load()

    def put(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.px[x, y] = c

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def char(self, x, y, ch, c):
        g = FONT.get(ch.upper())
        if not g:
            return
        for r in range(CH_H):
            for col in range(CH_W):
                if g[r][col] == "1":
                    self.put(x + col, y + r, c)

    def text(self, x, y, s, c):
        cx = x
        for ch in s:
            self.char(cx, y, ch, c)
            cx += CH_W + CH_GAP
        return cx - CH_GAP - x

    def char_scaled(self, x, y, ch, c, s):
        g = FONT.get(ch.upper())
        if not g:
            return
        for r in range(CH_H):
            for col in range(CH_W):
                if g[r][col] == "1":
                    self.rect(x + col * s, y + r * s, x + col * s + s - 1, y + r * s + s - 1, c)

    def text_scaled(self, x, y, txt, c, s):
        cx = x
        for ch in txt:
            self.char_scaled(cx, y, ch, c, s)
            cx += (CH_W + CH_GAP) * s
        return cx - CH_GAP * s - x

    def sprite(self, x, y, rows, palette):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in palette:
                    self.put(x + i, y + j, palette[ch])

    def icon(self, x, y, name, c):
        for r, row in enumerate(ICONS[name]):
            for col, bit in enumerate(row):
                if bit == "1":
                    self.put(x + col, y + r, c)


def text_w(s, scale=1):
    return (len(s) * (CH_W + CH_GAP) - CH_GAP) * scale


def _draw_header(fb, clock_txt):
    fb.sprite(MARGIN, MARGIN, CLAUDE_GUY, PALETTE)   # the Claude critter
    fb.text(13, 2, "CLAUDE", WHITE)
    if clock_txt:
        fb.text(W - MARGIN - text_w(clock_txt), 2, clock_txt, GREY)


def _draw_bar_block(fb, yb, icon_name, pct, reset_txt, invert=False):
    """A labelled bar with its reset countdown tucked underneath.

    Color and fill always track how *low* you are: usage-based color (red as you
    run out) and, in invert mode, the bar shows REMAINING (100-usage) so it
    shrinks and reddens as the metric is consumed.
    """
    col = bar_color(pct)                         # danger color from usage
    shown = max(0, min(100, (100 - pct) if invert else pct))
    fb.icon(MARGIN, yb + 1, icon_name, WHITE)
    bx0, bx1 = 12, 49
    by0, by1 = yb + 2, yb + 6                    # thin 5px bar
    fb.rect(bx0, by0, bx1, by1, DIM)            # track
    span = bx1 - bx0
    fillx = bx0 + int(round(span * shown / 100.0))
    fb.rect(bx0, by0, fillx, by1, col)          # fill
    fb.text(W - MARGIN - text_w(f"{shown}%"), by0, f"{shown}%", WHITE)
    if reset_txt:
        fb.text(12, by1 + 3, reset_txt, GREY)


def render(session, week, credits_txt="", session_reset="", week_reset="",
           clock_txt="", flash_on=True, invert=False) -> Image.Image:
    """
    Adaptive Claude-usage screen.
      Normal (nothing maxed): Session + Week bars, each with its own reset time.
      A limit is FULL:        the maxed metric (red) + its reset + Credits as an
                              amount/total number (only if credits_txt given).
    """
    fb = FB()
    _draw_header(fb, clock_txt)

    full = None
    if session >= 100:   full = ("bolt", "SESSION", session_reset)
    elif week >= 100:    full = ("cal",  "WEEK",    week_reset)

    if full is None:
        _draw_bar_block(fb, 12, "bolt", session,
                        ("RESETS " + session_reset) if session_reset else "", invert)
        _draw_bar_block(fb, 38, "cal", week,
                        ("RESETS " + week_reset) if week_reset else "", invert)
    else:
        icon_name, label, reset_txt = full
        fb.icon(MARGIN, 13, icon_name, WHITE)
        fb.text(13, 14, label, WHITE)
        fb.text(W - MARGIN - text_w("FULL"), 14, "FULL", RED)
        fb.rect(12, 22, 51, 25, RED if flash_on else DIM)
        if reset_txt:
            fb.text(12, 30, "RESETS " + reset_txt, GREY)
        if credits_txt:
            fb.icon(MARGIN, 40, "star", CLAUDE_ORANGE)
            fb.text(13, 40, "CREDITS", WHITE)
            amt, _, tot = credits_txt.partition("/")
            fb.text_scaled(12, 47, amt.strip(), CLAUDE_ORANGE, 2)
            if tot:
                fb.text(12, 57, "/ " + tot.strip(), GREY)

    return fb.img


def image_to_pic_data(img: Image.Image) -> str:
    """Base64-encode a 64x64 RGB image as Pixoo Draw/SendHttpGif PicData."""
    data = bytearray()
    px = img.load()
    for y in range(H):
        for x in range(W):
            data += bytes(px[x, y])
    return base64.b64encode(bytes(data)).decode()


def build_gif_payload(**kwargs) -> dict:
    """Render a frame and wrap it in a Draw/SendHttpGif command payload.

    Accepts the same keyword args as render(). Safe to call in an executor.
    """
    img = render(**kwargs)
    return {
        "Command": "Draw/SendHttpGif",
        "PicNum": 1, "PicWidth": W, "PicOffset": 0,
        "PicID": 1, "PicSpeed": 1000,
        "PicData": image_to_pic_data(img),
    }
