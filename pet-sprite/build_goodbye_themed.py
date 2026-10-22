#!/usr/bin/env python3
"""
Build the "goodbye" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Source: node 4915:16 in the Polish Push May-June 2026 Figma file
(fileKey lWE17f1tRRDXWsbxTcbsmo). Design shows the buddy in a happy
squinty-eyed pose with a DETACHED hand mitten floating up and to the
right, plus a diagonal sparkle "motion trail" of 2 chunky LIGHT dots
between the body and the hand -- reading as a cheerful farewell wave.

Bounding box in the 51x50 source render:
  Body      : canvas (5..28, 20..43)  — 24x24, same footprint as the
              other themed sprites (smile, sleep, speechless...)
  Hand      : canvas (35..50, 26..38) — 16x13 mitten
  Sparkles  : canvas (33,32) & (31,34), each 2x2 LIGHT chunks

We crop with a 5px left / 20px top offset so the output is 46x24 pixels
with the character flush-left, matching the coffee / tool / walking
themed sprites' composition style (character + right-side prop).

Semantic slots (pixel-identical to every other themed state):
  LIGHT   body/hand highlight, sparkles
  MID     body/hand midtone, antennae right
  DEEP    body outline, antenna left
  PUPIL   eye slits

Animation: a gentle vertical wave -- the detached hand and its two
sparkles slide together on a 4-frame loop (up → mid → down → mid),
so the sparkle trail stays visually attached to the hand as it waves.
Everything else (body, antennae, squinty eyes) is static. Loops
forever.

Outputs:
  assets/goodbye-blue.gif   (VS Code palette,  46x24, 4 frames)
  assets/goodbye-green.gif  (Insiders palette, 46x24, 4 frames)

Both GIFs are 46x24 with a transparent background so they drop into
the same sprite surface as coffee-*.gif and friends.

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Themed palettes — same values used by every other themed state so the
# variant toggle is drop-in compatible.
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c
        "PUPIL": (25,  26,  27, 255),   # #191a1b
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451
        "PUPIL": (25,  26,  27, 255),   # #191a1b
    },
}

W, H = 46, 24

SYM_TO_SLOT = {
    "L": "LIGHT",
    "M": "MID",
    "D": "DEEP",
    "#": "PUPIL",
}

# ─── Body layer (46x24) ───────────────────────────────────────────────
# Character body + antennae + eyes, WITHOUT the detached hand and its
# sparkle trail. Sparkle + hand pixels are painted per-frame on top
# from HAND / SPARKLES below, so their positions can be shifted for
# the wave loop without disturbing the body.
BODY = [
    "......DD........MM............................",  # 0
    "......DD........MM............................",  # 1
    "........DD....MM..............................",  # 2
    "........DD....MM..............................",  # 3
    "........DD....MM..............................",  # 4
    "........DD....MM..............................",  # 5
    "..........DDMM................................",  # 6
    "..........DDMM................................",  # 7
    "........DDMMLLLL..............................",  # 8
    "........DDMMLLLL..............................",  # 9
    "......DDMMLLLLLLLL............................",  # 10
    "......DDMMLLLLLLLL............................",  # 11
    "....DDMMLLLLLLLLLLLL..........................",  # 12
    "....DDMMLLLLLLLLLLLL..........................",  # 13
    "..DDMMLLLLLLLLLLLLLLLL........................",  # 14
    "..DDMMLLLLLLLLLLLLLLLL........................",  # 15
    "DDMMLLLLLLLLLLLLLLLLLLLLLLLL..................",  # 16
    "DDMMLLLLL####LLL####LLLLLLLL..................",  # 17
    "DDMMLLLLL####LLL####LLLLLL....................",  # 18
    "DDMMLLL##LLLLLLLLLLL##LLLL....................",  # 19
    "DDMMLLL##LLLLLLLLLLL##LL......................",  # 20
    "DDMMLLLLLLLLLLLLLLLLLLLL......................",  # 21
    "..DDMMMMLLLLLLLLLLLLLL........................",  # 22
    "..DDMMMMLLLLLLLLLLLLLL........................",  # 23
]
assert len(BODY) == H
assert all(len(r) == W for r in BODY), [len(r) for r in BODY]


# ─── Detached hand (16x13 mitten) ─────────────────────────────────────
# Reference position: top-left at sprite (30, 6) — matches the source.
HAND_ORIGIN = (30, 6)
HAND = [
    "..MMMMMM........",  # 0
    "..MMMMMMMMMM....",  # 1
    "MMLLLLLLMMMM....",  # 2
    "MMLLLLLLLLLLMM..",  # 3
    "MMLLLLLLLLLLMM..",  # 4
    "MMMMLLLLLLLLLLMM",  # 5
    "..MMLLLLLLLLLLMM",  # 6
    "....MMLLLLLLLLMM",  # 7
    "....MMLLLLLLLLMM",  # 8
    "......MMMMLLLLMM",  # 9
    "......MMMMLLLLMM",  # 10
    "..........MMMMMM",  # 11
    "..........MMMM..",  # 12
]
HAND_W, HAND_H = 16, 13
assert len(HAND) == HAND_H
assert all(len(r) == HAND_W for r in HAND)


# ─── Sparkle trail ────────────────────────────────────────────────────
# Two 2x2 LIGHT chunks trailing diagonally from the body up toward the
# hand. Positions are top-left in sprite coords at REST (matches the
# Figma source vectors at canvas (33,32) and (31,34)).
SPARKLES = [(28, 12), (26, 14)]

# ─── Arm bridge ───────────────────────────────────────────────────────
# The Figma source leaves a corner-only touch between sparkle A
# (28-29, 12-13) and the hand's bottom-left corner (30, 11) MM, which
# reads as a broken arm. We fill it with 2 permanent LIGHT pixels at
# (30-31, 12) so sparkle A → bridge → hand always share edges, giving
# the arm a solid, unbroken shape. The bridge sits inside the natural
# gap of the hand row (row 12 of the hand grid is `..MMLL...`) so it
# does not disturb the mitten silhouette. On the "hand up" wave frame
# we add a second 2-pixel bridge one row higher so the arm stretches
# with the hand and stays connected end-to-end.
BRIDGE_STATIC = [(30, 12), (31, 12)]
BRIDGE_UP_EXTRA = [(30, 11), (31, 11)]


# ─── Wave animation ───────────────────────────────────────────────────
# 4-frame gentle vertical wave: mid → up → mid → down → mid ...
# Only the HAND shifts -- the two sparkles stay anchored to the body,
# because they represent the motion trail left behind by the waving
# hand and act as the connective "arm" between body and hand. The
# static BRIDGE_STATIC pixels (30-31, 12) always sit between sparkle A
# and the hand's bottom-left corner so the arm never breaks; the "up"
# frame additionally paints BRIDGE_UP_EXTRA (30-31, 11) so the arm
# stretches up with the hand and stays edge-connected end-to-end.
FRAMES = [
    # (hand_dx, hand_dy, extra_bridges, delay_ms)
    ( 0,  0, [],              200),   # 0: rest
    ( 0, -1, BRIDGE_UP_EXTRA, 200),   # 1: up (arm stretches — extra bridge at row 11)
    ( 0,  0, [],              200),   # 2: rest
    ( 0,  1, [],              200),   # 3: down (arm compresses — hand overlaps rest bridges)
]


def paint(px, x, y, palette, slot):
    """Paint a single pixel if it's in bounds."""
    if 0 <= x < W and 0 <= y < H:
        px[x, y] = palette[slot]


def build_frame(palette, dx, dy, extra_bridges=()):
    """Render one 46x24 RGBA frame: static body + hand shifted by
    (dx, dy) + sparkles + arm bridge (static + optional per-frame
    extras). Bridge and sparkles are painted AFTER the hand so they
    always sit on top of the mitten's outline — this is what keeps the
    arm visually attached to the hand corner on every wave beat."""
    img = Image.new("RGBA", (W, H), BG)
    px = img.load()

    # Body
    for y, row in enumerate(BODY):
        for x, ch in enumerate(row):
            slot = SYM_TO_SLOT.get(ch)
            if slot is not None:
                paint(px, x, y, palette, slot)

    # Hand
    ox, oy = HAND_ORIGIN
    for hy, row in enumerate(HAND):
        for hx, ch in enumerate(row):
            slot = SYM_TO_SLOT.get(ch)
            if slot is not None:
                paint(px, ox + hx + dx, oy + hy + dy, palette, slot)

    # Sparkles (each is a 2x2 LIGHT chunk that stays anchored to the
    # body — the sparkles are the "arm" / trail between body and hand
    # and should NOT shift with the hand, or the arm breaks visually.)
    for (sx, sy) in SPARKLES:
        for ddx in (0, 1):
            for ddy in (0, 1):
                paint(px, sx + ddx, sy + ddy, palette, "LIGHT")

    # Arm bridge — permanent pixels that fill the corner-only gap
    # between sparkle A and the hand, plus per-frame extras that
    # stretch the bridge when the hand waves up.
    for (bx, by) in list(BRIDGE_STATIC) + list(extra_bridges):
        paint(px, bx, by, palette, "LIGHT")

    return img


def write_animated_gif(frames_ms, out_path, palette):
    """Write a multi-frame transparent GIF via gifsicle so per-frame
    delays are exact and the transparent index survives optimisation."""
    fw, fh = frames_ms[0][0].size
    opaque_slots = ["PUPIL", "DEEP", "MID", "LIGHT"]
    pal_bytes = [0, 0, 0]  # index 0 = transparent placeholder
    for slot in opaque_slots:
        r, g, b, _a = palette[slot]
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {BG: 0}
    for i, slot in enumerate(opaque_slots, start=1):
        color_to_index[palette[slot]] = i

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, (frame, _delay) in enumerate(frames_ms):
            idx = Image.new("P", (fw, fh), 0)
            idx.putpalette(pal_bytes)
            src = frame.load()
            dst = idx.load()
            for y in range(fh):
                for x in range(fw):
                    dst[x, y] = color_to_index.get(src[x, y], 0)
            idx.info["transparency"] = 0
            p = os.path.join(tmp, f"f{i:02d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(p)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        args = ["gifsicle", "--no-warnings", "--loopcount=0", "--transparent=0"]
        for path, (_, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def main():
    for variant, palette in PALETTES.items():
        frames_ms = [
            (build_frame(palette, dx, dy, extras), delay_ms)
            for (dx, dy, extras, delay_ms) in FRAMES
        ]
        out_path = os.path.join(ASSETS, f"goodbye-{variant}.gif")
        write_animated_gif(frames_ms, out_path, palette)
        total_ms = sum(d for _, _, _, d in FRAMES)
        print(f"Wrote {out_path} ({W}x{H}, {len(frames_ms)} frames, "
              f"{total_ms} ms loop)")


if __name__ == "__main__":
    main()
