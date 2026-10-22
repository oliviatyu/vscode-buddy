#!/usr/bin/env python3
"""
Build the "tool" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Source: Figma design node 4840:3423 in the Polish Push May-June 2026
file (fileKey lWE17f1tRRDXWsbxTcbsmo). The buddy leans forward in a
low, wide "reaching" pose while a small wrench floats to the upper
right of the head, with two clusters of sparkles rising off the head
(DEEP cluster on the left, MID cluster on the right).

Unlike the other themed sprites this pose is 32x24 (wider than the
standard 24x24) because the wrench floats off the buddy's right side.
The .screen in buddy_sprite.html resizes to the sprite's natural
dimensions, so wider sprites are rendered at the same 10px-per-source
scale.

Symbols:

  L = LIGHT   -> theme light (body highlight, wrench highlight)
  M = MID     -> theme mid   (body fill, right-side sparkles)
  D = DEEP    -> theme deep  (outline, left-side sparkles, wrench outline)
  P = PUPIL   -> near-black  (#191a1b, eye pupils)
  . = transparent

Animation:
  The wrench gently bobs while the buddy stays still -- reads as
  "using the tool". Four-frame loop:

    Frame 0 (400ms): rest             (wrench at y=0)
    Frame 1 (200ms): wrench down 1px  (impact)
    Frame 2 (400ms): rest
    Frame 3 (200ms): wrench down 1px

Outputs:
  assets/tool-blue.gif   (VS Code palette,  32x24, 4 frames)
  assets/tool-green.gif  (Insiders palette, 32x24, 4 frames)

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Themed palettes. Blue values are lifted straight from the Figma
# reference (node 4840:3423). Green values mirror the ramp already
# used by search-green / cool-green / branch-green / etc.
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

W = 32
H = 24


# --- Creature ---------------------------------------------------------
#
# Rows 0-9 hold the sparkle antennae (DEEP cluster on the left, MID
# cluster on the right -- mirrored intentionally, matching the Figma
# reference).
# Rows 10-23 hold the wide "reaching" body. The pupils sit at cols
# 10-11 and 16-17 of rows 16-19 (2x2 each). The head widens to col 23
# at the pupil-and-belly band (rows 16-21) before contracting again
# at the chin (rows 22-23).
#
# The CREATURE_ROWS grid is 24 wide -- the last 8 cols of the 32-wide
# sprite are reserved for the wrench, which is painted separately so
# it can be shifted per frame without touching the buddy.

CREATURE_ROWS = [
    "........................",  # 0
    "........................",  # 1
    "......DD........MM......",  # 2   sparkle tips: DEEP left, MID right
    "......DD........MM......",  # 3
    "....DD..DD....MM..MM....",  # 4   sparkle spread
    "....DD..DD....MM..MM....",  # 5
    "..........DDMM..........",  # 6   converging spine (DEEP over MID)
    "..........DDMM..........",  # 7
    "........DDMMLLLL........",  # 8   spine base merging into head
    "........DDMMLLLL........",  # 9
    "......DDMMLLLLLLLL......",  # 10  head starts widening
    "......DDMMLLLLLLLL......",  # 11
    "....DDMMLLLLLLLLLLLL....",  # 12
    "....DDMMLLLLLLLLLLLL....",  # 13
    "..DDMMLLLLLLLLLLLLLLLL..",  # 14
    "..DDMMLLLLLLLLLLLLLLLL..",  # 15
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # 16  pupil row (LEFT eye 10-11, RIGHT eye 16-17), head extends to col 23
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # 17
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # 18
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # 19
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 20
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 21
    "..DDDDMMMMLLLLLLLLLLLL..",  # 22  chin band contracts back to col 21
    "..DDDDMMMMLLLLLLLLLLLL..",  # 23
]

# Sanity check: creature width must match, and the wrench+creature
# together should not exceed W columns.
CREATURE_W = 24
assert all(len(row) == CREATURE_W for row in CREATURE_ROWS), \
    "CREATURE_ROWS must all be CREATURE_W chars wide"
assert len(CREATURE_ROWS) == H


# --- Wrench -----------------------------------------------------------
#
# Local 10x16 grid placed at sprite (WRENCH_X_REST, WRENCH_Y_REST) at
# rest. Lifted straight from the Figma "Group 52" wrench.

WRENCH_ROWS = [
    "..DD..DD..",  # 0  top prongs
    "..DD..DD..",  # 1
    "DDLLDDLLDD",  # 2  wrench head / opening
    "DDLLDDLLDD",  # 3
    "DDLLDDLLDD",  # 4
    "DDLLDDLLDD",  # 5
    "DDLLLLLLDD",  # 6  head base
    "DDLLLLLLDD",  # 7
    "..DDLLDD..",  # 8  handle
    "..DDLLDD..",  # 9
    "..DDLLDD..",  # 10
    "..DDLLDD..",  # 11
    "..DDLLDD..",  # 12
    "..DDLLDD..",  # 13
    "LLDDDDDD..",  # 14 handle butt (LL is a highlight tab)
    "LLDDDDDD..",  # 15
]

WRENCH_W = 10
WRENCH_H = 16
WRENCH_X_REST = 22   # left edge of wrench in sprite space
WRENCH_Y_REST = 2    # top edge of wrench in sprite space
assert all(len(row) == WRENCH_W for row in WRENCH_ROWS)
assert len(WRENCH_ROWS) == WRENCH_H

SYM_TO_SLOT = {
    "L": "LIGHT",
    "M": "MID",
    "D": "DEEP",
    "P": "PUPIL",
}


# --- Animation --------------------------------------------------------
#
# Only the wrench moves. Each frame is (wrench_y_offset, delay_ms).

FRAMES = [
    (0, 400),   # rest
    (1, 200),   # tap: wrench dips 1px
    (0, 400),   # rest
    (1, 200),   # tap
]


# --- Rendering --------------------------------------------------------

def paint_creature(im, palette):
    px = im.load()
    for y, row in enumerate(CREATURE_ROWS):
        for x, sym in enumerate(row):
            slot = SYM_TO_SLOT.get(sym)
            if slot is None:
                continue
            px[x, y] = palette[slot]


def paint_wrench(im, palette, y_offset):
    px = im.load()
    for wy, row in enumerate(WRENCH_ROWS):
        for wx, sym in enumerate(row):
            slot = SYM_TO_SLOT.get(sym)
            if slot is None:
                continue
            sx = WRENCH_X_REST + wx
            sy = WRENCH_Y_REST + wy + y_offset
            if 0 <= sx < W and 0 <= sy < H:
                px[sx, sy] = palette[slot]


def render_frame(palette, wrench_y_offset):
    im = Image.new("RGBA", (W, H), BG)
    paint_creature(im, palette)
    paint_wrench(im, palette, wrench_y_offset)
    return im


def build_frames(palette):
    return [render_frame(palette, dy) for (dy, _delay) in FRAMES]


def write_gif(frames, palette, out_path):
    """Assemble the multi-frame transparent GIF via gifsicle so per-frame
    delays are exact and the transparent index survives optimisation."""
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
        for i, frame in enumerate(frames):
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            src = frame.load()
            dst = idx.load()
            for y in range(H):
                for x in range(W):
                    dst[x, y] = color_to_index.get(src[x, y], 0)
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2)
            frame_paths.append(p)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cmd = [
            "gifsicle",
            "--loopcount=0",
            "--no-warnings",
            "--disposal=background",
            "--transparent=0",
        ]
        # Per-frame delays via --delay + individual frame files.
        # gifsicle supports interleaving --delay before each input file.
        interleaved = []
        for (_, delay_ms), p in zip(FRAMES, frame_paths):
            delay_cs = max(1, delay_ms // 10)
            interleaved.extend([f"--delay={delay_cs}", p])
        cmd.extend(interleaved)
        cmd.extend(["--output", out_path])
        subprocess.run(cmd, check=True)


def main():
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"tool-{name}.gif")
        frames = build_frames(palette)
        write_gif(frames, palette, out_path)
        total_ms = sum(d for (_, d) in FRAMES)
        print(f"Wrote {out_path} ({W}x{H}, {len(frames)} frames, {total_ms} ms loop)")


if __name__ == "__main__":
    main()
