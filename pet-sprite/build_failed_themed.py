#!/usr/bin/env python3
"""
Build a "failed" (dead / errored) Buddy Veee sprite matching the Polish
Push May-June 2026 Figma design at
    https://www.figma.com/design/lWE17f1tRRDXWsbxTcbsmo/...?node-id=5224-47784

The Figma source is a full-color 24x24 rendering of the buddy in its
"failed" pose: same fill + shadow palette as the idle buddy, but the
top of the head is broken into two jagged spikes (a DARK-blue chunk
on the left, a MID-blue chunk on the right, as if the shell cracked),
and the eyes are inward-facing closed chevrons made from three 2x2
PUPIL blocks each.

This script draws the sprite directly from a pixel-code grid so the
output is exact pixel-art (no anti-aliasing) and shares the palette
with build_idle_breathing_blue.py / build_sleep_themed.py — themed
buddies read as the same character across states.

Outputs (a single-frame static GIF per palette):
  assets/failed-blue.gif
  assets/failed-green.gif

Usage:
  python3 build_failed_themed.py                              # both blue + green
  python3 build_failed_themed.py --palette blue               # blue only
  python3 build_failed_themed.py --palette green --out foo.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import argparse
import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

# --- Palette (mirrors build_idle_breathing_blue.py so themed buddies read
# as the same character across states). ---------------------------------
BG = (0, 0, 0, 0)

PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2 body fill
        "MID":   (0, 119, 184, 255),    # #0077b8 mid outline
        "DARK":  (0,  78, 124, 255),    # #004e7c dark shadow
        "PUPIL": (25, 26, 27, 255),     # #191a1b eyes
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5 body fill
        "MID":   (0, 154, 124, 255),    # #009a7c mid outline
        "DARK":  (0, 100,  81, 255),    # #006451 dark shadow (matches sleep-green DEEP)
        "PUPIL": (25, 26, 27, 255),     # #191a1b eyes
    },
}

# Semantic pixel codes:
#   . = transparent background
#   L = body fill (LIGHT)
#   M = mid outline (MID)
#   D = dark shadow (DARK) — left edge + left half of the shattered top
#   P = closed-eye pixel (PUPIL) — the inward-facing chevrons
#
# The silhouette matches the Figma export at node 5224-47784. The top
# has two chunky spikes — the LEFT spike is DARK (as if pushed down
# into shadow) and the RIGHT spike is MID — reading as a cracked shell.
# The left eye points right and the right eye points left; each uses
# three 2x2 blocks, matching the source SVG exactly.
# Left eye: cols 7-10, right eye: cols 15-18, both at rows 14-19.
W = H = 24

FAILED_ROWS = [
    "........................",  # y= 0
    "........................",  # y= 1
    "......DDDD....MMMM......",  # y= 2  cracked-top spikes: DARK left, MID right
    "......DDDD....MMMM......",  # y= 3
    "....DD....DDMM....MM....",  # y= 4
    "....DD....DDMM....MM....",  # y= 5
    "..DD....DDMMLLLL....MM..",  # y= 6
    "..DD....DDMMLLLL....MM..",  # y= 7
    "......DDMMLLLLLLLL......",  # y= 8
    "......DDMMLLLLLLLL......",  # y= 9
    "....DDMMLLLLLLLLLLLL....",  # y=10
    "....DDMMLLLLLLLLLLLL....",  # y=11
    "..DDMMLLLLLLLLLLLLLLLL..",  # y=12
    "..DDMMLLLLLLLLLLLLLLLL..",  # y=13
    "DDMMLLLPPLLLLLLLLPPLLLLL",  # y=14  chevron outer blocks
    "DDMMLLLPPLLLLLLLLPPLLLLL",  # y=15
    "DDMMLLLLLPPLLLLPPLLLLLLL",  # y=16  chevron inner blocks
    "DDMMLLLLLPPLLLLPPLLLLLLL",  # y=17
    "DDMMLLLPPLLLLLLLLPPLLLLL",  # y=18  chevron outer blocks
    "DDMMLLLPPLLLLLLLLPPLLLLL",  # y=19
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # y=20  MM bar
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # y=21  MM bar
    "..DDDDMMMMLLLLLLLLLLLL..",  # y=22  bottom bar
    "..DDDDMMMMLLLLLLLLLLLL..",  # y=23
]


def build_frame(palette):
    code_to_rgba = {
        ".": BG,
        "L": palette["LIGHT"],
        "M": palette["MID"],
        "D": palette["DARK"],
        "P": palette["PUPIL"],
    }
    im = Image.new("RGBA", (W, H), BG)
    for y, row in enumerate(FAILED_ROWS):
        assert len(row) == W, f"row {y} has {len(row)} chars, expected {W}"
        for x, ch in enumerate(row):
            im.putpixel((x, y), code_to_rgba[ch])
    return im


def write_gif(frame, palette, out_path):
    """Write a single-frame transparent-background GIF via gifsicle.
    The "failed" sprite is static — one frame is enough — but we still
    route through gifsicle so the palette + transparency handling
    matches every other themed buddy asset in this folder.
    """
    opaque = [palette["PUPIL"], palette["DARK"], palette["MID"], palette["LIGHT"]]
    pal_bytes = [0, 0, 0]  # index 0 = transparent
    for r, g, b, _a in opaque:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {
        BG: 0,
        palette["PUPIL"]: 1,
        palette["DARK"]:  2,
        palette["MID"]:   3,
        palette["LIGHT"]: 4,
    }

    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "f000.gif")
        idx = Image.new("P", (W, H), 0)
        idx.putpalette(pal_bytes)
        src_pixels = frame.load()
        idx_pixels = idx.load()
        for y in range(H):
            for x in range(W):
                idx_pixels[x, y] = color_to_index[src_pixels[x, y]]
        idx.info["transparency"] = 0
        idx.save(p, "GIF", transparency=0, disposal=2)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cmd = [
            "gifsicle",
            "--loop=0",
            "--disposal=background",
            "--transparent=0",
            "--delay=100",  # 1s — irrelevant for a static single-frame GIF
            "--output", out_path,
            p,
        ]
        subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--palette",
        choices=["blue", "green", "both"],
        default="both",
        help="Which color variant(s) to render (default: both).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path override. Only valid with a single --palette; "
             "defaults to assets/failed-<palette>.gif for each variant.",
    )
    args = parser.parse_args()

    variants = ["blue", "green"] if args.palette == "both" else [args.palette]
    if args.out and len(variants) != 1:
        parser.error("--out can only be used with a single --palette")

    for name in variants:
        palette = PALETTES[name]
        out_path = args.out or os.path.join(ASSETS, f"failed-{name}.gif")
        frame = build_frame(palette)
        write_gif(frame, palette, out_path)
        print(f"wrote {out_path}  (static, palette={name})")


if __name__ == "__main__":
    main()
