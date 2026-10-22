#!/usr/bin/env python3
"""
Build the animated "cool" state sprite for the Buddy Veee tamagotchi
in the themed VS Code blue / Insiders green palettes.

Base pose (rest with sunglasses on):
  Derived from assets/cool-source-themed.svg -- refreshed Figma design
  at node 4840:3312 in the Polish Push May-June 2026 file (fileKey
  lWE17f1tRRDXWsbxTcbsmo). The rest pose is transcribed pixel-for-pixel
  from that SVG into REST_ROWS below, so this script no longer needs
  to parse the SVG at runtime -- the SVG stays as reference / source
  of truth for the resting silhouette.

Motion (50 frames * 40 ms = 2000 ms loop, stop-motion pixel-art style
matching idle-breathing.gif):
    - Frames  0-14 (0-600 ms):     BARE FACE -- no glasses, two 2x3
                                  pupils showing under the brow.
  - Frames 15-17 (600-720 ms):   Glasses drop-in position HIGH -- the
                                  whole sunglasses component is stamped
                                  at the TOP of the canvas (brow rows
                                                                    0-1, lenses rows 2-4).
  - Frames 18-20 (720-840 ms):   Position MID -- same glasses stamp,
                                                                    now at rows 5-9 (over the head).
  - Frames 21-23 (840-960 ms):   Position CLOSE -- glasses stamp at
                                                                    rows 10-14, just above the final
                                  face position.
    - Frames 24-49 (960-2000 ms):  REST -- glasses stamp at rows 14-18
                                                                    (final settled cool pose, lenses
                                                                    extending through row 18).

The GLASSES SHAPE never changes -- it is a single static 14x5 stamp
that is simply positioned at four discrete Y offsets across the drop.
There is no arm and no hand: the effect reads as the glasses falling
straight down onto the face in stop-motion snaps.

Palette semantics (4 colors, same as idle-breathing / sleep-* etc.):
  LIGHT  -- bright body fill
  MID    -- mid outline / cheek shadow
  DEEP   -- dark outline / left-edge shadow
  PUPIL  -- solid sunglass lens/frame AND bare-face eye pupils

Canvas / body layout:
  The output canvas is 24x24 -- same as idle-breathing / sleep-* etc.
  The buddy BODY is exactly 24x24 and always fills the canvas. During
  the drop, the glasses stamp temporarily overlays antennae/head
  pixels; those pixels return to normal as soon as the glasses move on.

Outputs:
  assets/cool-blue.gif   (VS Code palette,   24x24, 50 frames)
  assets/cool-green.gif  (Insiders palette,  24x24, 50 frames)

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
# reference (node 4840:3314). Green values mirror the analogous ramp
# already used by sleep-green / branch-green / working-green.
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c
        "PUPIL": (25,  26,  27, 255),   # #191a1b (solid sunglass fill)
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451 (matches sleep-green DEEP)
        "PUPIL": (25,  26,  27, 255),   # #191a1b (solid sunglass fill)
    },
}

W = H = 24
OUT_FRAME_MS = 40
OUT_FRAMES = 50


# --- Poses (each row is 24 chars, one char per pixel) ------------------
# Legend:
#   . = transparent    L = LIGHT body fill
#   M = MID outline    D = DEEP shadow    P = PUPIL (glasses / eyes)


# REST pose -- BODY WITHOUT GLASSES. This is the buddy silhouette that
# the glasses stamp lands on top of; rows 14-17 have the bare face
# (LIGHT fill + 2x3 PUPIL eyes at x=10-11 and x=16-17). Combining this
# with the glasses stamp at rest Y (=14) reproduces the updated
# assets/cool-source-themed.svg pixel-for-pixel.
BARE_FACE_ROWS = [
    "........................",  # 0
    "........................",  # 1
    "......DD........MM......",  # 2   antennae tips
    "......DD........MM......",  # 3
    "....DD..DD....MM..MM....",  # 4   antennae mid
    "....DD..DD....MM..MM....",  # 5
    "..........DDMM..........",  # 6   top of head
    "..........DDMM..........",  # 7
    "........DDMMLLLL........",  # 8
    "........DDMMLLLL........",  # 9
    "......DDLLLLLLLLLL......",  # 10
    "......DDLLLLLLLLLL......",  # 11
    "....DDLLLLLLLLLLLLLL....",  # 12
    "....DDLLLLLLLLLLLLLL....",  # 13
    "..DDLLLLLLLLLLLLLLLLLL..",  # 14  bare brow area (glasses land here at rest)
    "..DDLLLLLLLLLLLLLLLLLL..",  # 15
    "DDMMLLLLLLPPLLLLPPLLLLLL",  # 16  bare face + 2x3 pupils at 10-11 and 16-17
    "DDMMLLLLLLPPLLLLPPLLLLLL",  # 17
    "DDMMLLLLLLPPLLLLPPLLLLLL",  # 18
    "DDMMLLLLLLLLLLLLLLLLLLLL",  # 19
    "DDMMLLLLLLLLLLLLLLLLLLLL",  # 20
    "DDMMLLLLLLLLLLLLLLLLLLLL",  # 21
    "..DDMMMMLLLLLLLLLLLLLL..",  # 22  chin bar
    "..DDMMMMLLLLLLLLLLLLLL..",  # 23
]


# GLASSES stamp -- the sunglasses as a single, complete, STATIC
# component. It is 14 wide (columns 0..13 relative to the stamp) and 4
# rows tall. Non-`.` pixels are PUPIL; `.` pixels are transparent so the
# body underneath shows through (which is how the bridge gap between
# the two lenses works).
#
#   PPPPPPPPPPPPPP   brow bar (14 wide)
#   PPPPPPPPPPPPPP
#   PPPPPP..PPPPPP   left lens (6 wide) + bridge gap (2) + right lens (6)
#   PPPPPP..PPPPPP
#   PPPPPP..PPPPPP
#
# This shape is NEVER redrawn -- the animation just moves it to
# different Y positions on the canvas.
GLASSES_STAMP = [
    "PPPPPPPPPPPPPP",
    "PPPPPPPPPPPPPP",
    "PPPPPP..PPPPPP",
    "PPPPPP..PPPPPP",
    "PPPPPP..PPPPPP",
]
GLASSES_X = 6         # left edge of the stamp in canvas coordinates
GLASSES_H = len(GLASSES_STAMP)
GLASSES_W = len(GLASSES_STAMP[0])

# Discrete drop Y positions (top row of the stamp). Stop-motion feel
# comes from big evenly-spaced jumps -- roughly 5 rows per step -- with
# no interpolation between them.
GLASSES_Y_HIGH  = 0     # brow at rows 0-1,   lenses at rows 2-4
GLASSES_Y_MID   = 5     # brow at rows 5-6,   lenses at rows 7-9
GLASSES_Y_CLOSE = 10    # brow at rows 10-11, lenses at rows 12-14
GLASSES_Y_REST  = 14    # brow at rows 14-15, lenses at rows 16-18 (final)


# --- Rendering ---------------------------------------------------------

def render_rows(rows, palette):
    """Turn a list of 24 24-char strings into a 24x24 RGBA image."""
    code = {
        ".": BG,
        "L": palette["LIGHT"],
        "M": palette["MID"],
        "D": palette["DEEP"],
        "P": palette["PUPIL"],
    }
    im = Image.new("RGBA", (W, H), BG)
    px = im.load()
    for y, row in enumerate(rows):
        assert len(row) == W, f"row {y} has {len(row)} chars, expected {W}"
        for x, ch in enumerate(row):
            px[x, y] = code[ch]
    return im


def stamp_glasses(base_im, y_offset, palette):
    """Return a copy of base_im with the (static) GLASSES_STAMP pasted
    at (GLASSES_X, y_offset). Only non-`.` pixels overwrite the base;
    the transparent bridge lets the body underneath show through. Stamp
    pixels that fall outside the canvas (e.g. when the glasses are
    partially above the top) are clipped."""
    out = base_im.copy()
    px = out.load()
    pupil = palette["PUPIL"]
    for sy, row in enumerate(GLASSES_STAMP):
        cy = y_offset + sy
        if cy < 0 or cy >= H:
            continue
        for sx, ch in enumerate(row):
            if ch == ".":
                continue
            cx = GLASSES_X + sx
            if cx < 0 or cx >= W:
                continue
            px[cx, cy] = pupil
    return out


def write_gif(frames, palette, out_path):
    """Assemble a multi-frame transparent GIF via gifsicle so per-frame
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

        delay_cs = OUT_FRAME_MS // 10  # 40 ms -> 4 cs
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cmd = [
            "gifsicle",
            # Play the drop sequence exactly once and freeze on the final
            # REST frame (glasses on face). buddy_sprite.html cache-busts
            # on state switch so the animation replays when the user
            # returns to the "cool" tab.
            "--no-loopcount",
            "--no-warnings",
            "--disposal=background",
            "--transparent=0",
            f"--delay={delay_cs}",
            "--output", out_path,
        ] + frame_paths
        subprocess.run(cmd, check=True)


def build_sequence(palette):
    """Return the 50-frame glasses-drop sequence for a palette."""
    bare = render_rows(BARE_FACE_ROWS, palette)
    poses = {
        "bare":  bare,
        "high":  stamp_glasses(bare, GLASSES_Y_HIGH,  palette),
        "mid":   stamp_glasses(bare, GLASSES_Y_MID,   palette),
        "close": stamp_glasses(bare, GLASSES_Y_CLOSE, palette),
        "rest":  stamp_glasses(bare, GLASSES_Y_REST,  palette),
    }
    seq = []
    for i in range(OUT_FRAMES):
        if i < 15:
            seq.append(poses["bare"])       # 0-14  (15 frames, 600 ms)
        elif i < 18:
            seq.append(poses["high"])       # 15-17 (3 frames, 120 ms)
        elif i < 21:
            seq.append(poses["mid"])        # 18-20 (3 frames, 120 ms)
        elif i < 24:
            seq.append(poses["close"])      # 21-23 (3 frames, 120 ms)
        else:
            seq.append(poses["rest"])       # 24-49 (26 frames, 1040 ms)
    return seq


def main():
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"cool-{name}.gif")
        frames = build_sequence(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({W}x{H}, {OUT_FRAMES} frames, "
              f"{OUT_FRAMES * OUT_FRAME_MS} ms loop)")


if __name__ == "__main__":
    main()
