#!/usr/bin/env python3
"""
Bake `coffee-source.png` (raw Figma export) into a blue-themed
single-frame GIF matching the palette used by the other tamagotchi
states (see build_sleep_themed.py).

Note: `sing` used to be built here too, but it now has a fully themed
Figma reference — see build_sing_themed.py for the current sing
pipeline. This script is kept scoped to coffee to avoid clobbering the
new sing-blue.gif / sing-green.gif output.

Source palette (coffee-source.png, 40x24):
  (241, 241, 241) light gray -> USED FOR BOTH body interior AND the
                                surrounding background.
  (203, 204, 206) mid gray   -> shade/highlight   -> MID
  ( 35,  31,  32) near-black -> outline / accent  -> PUPIL

Because "background" and "body interior" share the same RGB value, we
flood-fill from the canvas edges to split the two roles:
  - reachable-from-edge bg-color pixels -> transparent
  - enclosed bg-color pixels            -> LIGHT (blue body fill)

The coffee cup handle hole (rows 16-17) is correctly reached from the
outside and stays transparent; the cup interior is enclosed and becomes
the theme color (so it reads as coffee in the tinted cup).

Outputs:
  assets/coffee.gif    (single frame, transparent background)

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Blue palette (matches the other states shipped in this folder).
PALETTE = {
    "LIGHT": (35, 168, 242, 255),   # #23a8f2
    "MID":   (0, 119, 184, 255),    # #0077b8
    "PUPIL": (25, 26, 27, 255),     # #191a1b
}

SRC_MID_GRAY   = (203, 204, 206, 255)
SRC_NEAR_BLACK = ( 35,  31,  32, 255)

# One entry per source PNG: (filename_stem, background_color_in_source).
# `sing` intentionally omitted — see build_sing_themed.py.
SOURCES = [
    ("coffee", (241, 241, 241, 255)),
]


def flood_bg_mask(pixels, W, H, bg_color):
    """Return a 2D boolean grid: True = "reachable from any canvas edge
    via bg-color pixels" (4-connected flood fill). Used to distinguish
    outside-the-character bg pixels from enclosed body-interior pixels
    that happen to share the same RGB.
    """
    mask = [[False] * W for _ in range(H)]
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if pixels[x, y] == bg_color and not mask[y][x]:
                mask[y][x] = True
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if pixels[x, y] == bg_color and not mask[y][x]:
                mask[y][x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not mask[ny][nx]:
                if pixels[nx, ny] == bg_color:
                    mask[ny][nx] = True
                    q.append((nx, ny))
    return mask


def recolor(src_path, bg_color):
    """Load the source PNG, remap pixels to the blue palette, and return
    an RGBA image with a transparent background."""
    src = Image.open(src_path).convert("RGBA")
    W, H = src.size
    px = src.load()

    bg_mask = flood_bg_mask(px, W, H, bg_color)

    out = Image.new("RGBA", (W, H), BG)
    opx = out.load()
    for y in range(H):
        for x in range(W):
            c = px[x, y]
            if c == bg_color:
                opx[x, y] = BG if bg_mask[y][x] else PALETTE["LIGHT"]
            elif c == SRC_MID_GRAY:
                opx[x, y] = PALETTE["MID"]
            elif c == SRC_NEAR_BLACK:
                opx[x, y] = PALETTE["PUPIL"]
            elif c[3] == 0:
                opx[x, y] = BG
            else:
                opx[x, y] = c
    return out


def write_gif(img, out_path):
    """Write a single-frame transparent GIF via gifsicle so the
    transparent background is preserved exactly (Pillow's own GIF writer
    keeps producing surprising palettes with alpha in the mix)."""
    W, H = img.size
    opaque = [PALETTE["PUPIL"], PALETTE["MID"], PALETTE["LIGHT"]]
    pal_bytes = [0, 0, 0]  # index 0 = transparent slot
    for r, g, b, _a in opaque:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {
        BG: 0,
        PALETTE["PUPIL"]: 1,
        PALETTE["MID"]:   2,
        PALETTE["LIGHT"]: 3,
    }

    with tempfile.TemporaryDirectory() as tmp:
        idx = Image.new("P", (W, H), 0)
        idx.putpalette(pal_bytes)
        src_px = img.load()
        idx_px = idx.load()
        for y in range(H):
            for x in range(W):
                idx_px[x, y] = color_to_index.get(src_px[x, y], 0)
        idx.info["transparency"] = 0
        tmp_gif = os.path.join(tmp, "f.gif")
        idx.save(tmp_gif, "GIF", transparency=0, disposal=2, optimize=False)

        subprocess.run(
            ["gifsicle", "--no-warnings", "--loopcount=0",
             "--disposal=background", tmp_gif, "--output", out_path],
            check=True,
        )


def main():
    for stem, bg_color in SOURCES:
        src_path = os.path.join(ASSETS, f"{stem}-source.png")
        out_path = os.path.join(ASSETS, f"{stem}.gif")
        if not os.path.exists(src_path):
            raise SystemExit(f"Source not found: {src_path}")
        img = recolor(src_path, bg_color)
        write_gif(img, out_path)
        print(f"Wrote {out_path} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
