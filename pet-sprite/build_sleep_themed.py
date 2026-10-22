#!/usr/bin/env python3
"""
Recolor sleep-1.gif into themed blue / green variants matching the idle
palette (see build_idle_breathing_blue.py). Motion, frame count, and
per-frame delays are preserved exactly; only the pixels are remapped.

Source palette (from assets/sleep-1.gif):
  (255, 255, 255) white       -> USED FOR BOTH body interior AND the
                                 surrounding background. The source has
                                 no real transparent pixels, so we
                                 flood-fill from the canvas edges to
                                 split these two roles:
                                   - reachable-from-edge white -> transparent
                                   - enclosed white            -> LIGHT (body)
  (203, 204, 206) light gray  -> highlight/shade  -> MID
  ( 35,  31,  32) near-black  -> outline/pupils/Z. Further split by
                                 adjacency to background:
                                   - touches BG (outline / Z strokes) -> DEEP
                                   - fully interior (closed eyes)     -> PUPIL
                                 This matches the Figma sleep design
                                 (node 4840:2336 of file lWE17f1tRRDXWsbxTcbsmo),
                                 which uses a darker blue for the outline
                                 and reserves near-black for the eye slits.

Outputs:
  assets/sleep-blue.gif
  assets/sleep-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import deque

from PIL import Image, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "sleep-1.gif")

BG = (0, 0, 0, 0)

# Idle palette (reproduced from build_idle_breathing_blue.py so the sleep
# recolor matches the idle recolor exactly).
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c  (outline; from Figma 4840:2336)
        "PUPIL": (25, 26, 27, 255),     # #191a1b  (eyes only)
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451  (outline; MID * ~0.65, mirrors blue ramp)
        "PUPIL": (25, 26, 27, 255),     # #191a1b  (eyes only)
    },
}

# Source pixel colors in sleep-1.gif (verified via getcolors()).
SRC_WHITE     = (255, 255, 255, 255)
SRC_LIGHTGRAY = (203, 204, 206, 255)
SRC_NEARBLACK = ( 35,  31,  32, 255)

W = H = 24
OUT_FRAME_MS = 40  # matches source; overridden per-frame from the src duration


def build_remap(palette):
    """Return a dict {source_rgba: target_rgba} for the given palette.
    Note: SRC_WHITE and SRC_NEARBLACK are deliberately omitted — both
    are handled per-pixel in recolor_frames():
      - SRC_WHITE is split via flood-fill into background (transparent)
        vs. body-fill (LIGHT).
      - SRC_NEARBLACK is split via BG adjacency into outline (DEEP) vs.
        interior/eyes (PUPIL).
    """
    return {
        SRC_LIGHTGRAY: palette["MID"],
    }


def flood_bg_mask(pixels):
    """Return a 2D boolean grid where True means "this pixel is background"
    (a SRC_WHITE pixel reachable from any canvas edge without crossing
    a non-white pixel). Uses 4-connected flood fill.
    """
    mask = [[False] * W for _ in range(H)]
    q = deque()

    # Seed the queue with every edge pixel that is white.
    for x in range(W):
        for y in (0, H - 1):
            if pixels[x, y] == SRC_WHITE and not mask[y][x]:
                mask[y][x] = True
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if pixels[x, y] == SRC_WHITE and not mask[y][x]:
                mask[y][x] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not mask[ny][nx]:
                if pixels[nx, ny] == SRC_WHITE:
                    mask[ny][nx] = True
                    q.append((nx, ny))
    return mask


def _is_bg_or_oob(x, y, bg_mask):
    """True if (x, y) is outside the canvas OR a background (transparent)
    pixel per bg_mask.
    """
    if not (0 <= x < W and 0 <= y < H):
        return True
    return bg_mask[y][x]


def classify_nearblack(pixels, bg_mask):
    """Return a 2D grid `role` where role[y][x] is one of:
      - None  : this pixel isn't SRC_NEARBLACK
      - "OUT" : this pixel is part of a near-black connected component
                that touches the background (outline / Z strokes)
      - "EYE" : this pixel is part of a near-black component that is
                fully enclosed inside the body (the closed-eye slits)

    Components are computed with 8-connectivity so the 2-pixel-thick
    outlines in the doubled-pixel source stay as one contiguous group
    rather than getting split into "outer rim" and "inner rim" halves.
    """
    role = [[None] * W for _ in range(H)]
    visited = [[False] * W for _ in range(H)]
    neighbors8 = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)]

    for sy in range(H):
        for sx in range(W):
            if visited[sy][sx] or pixels[sx, sy] != SRC_NEARBLACK:
                continue
            # BFS the whole 8-connected component of near-black pixels.
            comp = []
            touches_bg = False
            stack = [(sx, sy)]
            visited[sy][sx] = True
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for dx, dy in neighbors8:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < W and 0 <= ny < H):
                        touches_bg = True
                        continue
                    if bg_mask[ny][nx]:
                        touches_bg = True
                        continue
                    if not visited[ny][nx] and pixels[nx, ny] == SRC_NEARBLACK:
                        visited[ny][nx] = True
                        stack.append((nx, ny))
            label = "OUT" if touches_bg else "EYE"
            for x, y in comp:
                role[y][x] = label
    return role


def recolor_frames(palette):
    """Load every frame of the source, composite it onto a fresh canvas
    so previous frames aren't inherited, remap the pixels, and return a
    list of (RGBA_image, delay_ms) tuples.
    """
    remap = build_remap(palette)
    src = Image.open(SRC)

    frames_out = []
    for frame in ImageSequence.Iterator(src):
        rgba = frame.convert("RGBA")
        pixels = rgba.load()

        bg_mask = flood_bg_mask(pixels)
        nb_role = classify_nearblack(pixels, bg_mask)

        remapped = Image.new("RGBA", (W, H), BG)
        rpix = remapped.load()
        for y in range(H):
            for x in range(W):
                c = pixels[x, y]
                if c == SRC_WHITE:
                    # Background stays transparent; enclosed white becomes
                    # the themed body fill.
                    rpix[x, y] = BG if bg_mask[y][x] else palette["LIGHT"]
                elif c[3] == 0:
                    rpix[x, y] = BG
                elif c == SRC_NEARBLACK:
                    # Outline components (touch bg) become DEEP; fully
                    # enclosed components (the closed eyes) stay PUPIL.
                    rpix[x, y] = palette["DEEP"] if nb_role[y][x] == "OUT" else palette["PUPIL"]
                else:
                    rpix[x, y] = remap.get(c, c)

        delay = frame.info.get("duration", OUT_FRAME_MS)
        frames_out.append((remapped, delay))
    return frames_out


def write_gif(frames_ms, palette, out_path):
    """Write frames as a transparent-background GIF via gifsicle so
    per-frame delays and the transparent BG are preserved exactly.
    """
    # Palette layout: index 0 = transparent, then the four opaque colors.
    opaque = [palette["PUPIL"], palette["DEEP"], palette["MID"], palette["LIGHT"]]
    pal_bytes = [0, 0, 0]  # placeholder for transparent slot
    for r, g, b, _a in opaque:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {
        BG: 0,
        palette["PUPIL"]: 1,
        palette["DEEP"]:  2,
        palette["MID"]:   3,
        palette["LIGHT"]: 4,
    }

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, (frame, _) in enumerate(frames_ms):
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            src_pixels = frame.load()
            idx_pixels = idx.load()
            for y in range(H):
                for x in range(W):
                    c = src_pixels[x, y]
                    idx_pixels[x, y] = color_to_index.get(c, 0)
            idx.info["transparency"] = 0
            idx.save(p, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(p)

        # Assemble with gifsicle: exact per-frame delays (in centiseconds),
        # infinite loop, transparent index preserved.
        args = ["gifsicle", "--loopcount=0", "--no-warnings"]
        for path, (_, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f"Source not found: {SRC}")

    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"sleep-{name}.gif")
        frames = recolor_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
