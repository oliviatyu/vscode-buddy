#!/usr/bin/env python3
"""
Recolor clapping-1.gif into themed blue / green variants matching the
idle / sleep palette (see build_sleep_themed.py, build_idle_breathing_blue.py).
Motion, frame count, and per-frame delays are preserved exactly; only
the pixels are remapped.

Source palette (from assets/clapping-1.gif):
  (255, 255, 255) white       -> USED FOR BOTH body interior AND the
                                 surrounding background. The source has
                                 no real transparent pixels, so we
                                 flood-fill from the canvas edges to
                                 split these two roles:
                                   - reachable-from-edge white -> transparent
                                   - enclosed white            -> LIGHT (body)
  (203, 204, 206) light gray  -> highlight/shade  -> MID
  ( 35,  31,  32) near-black  -> outline / arms / eyes / mouth. Further
                                 split by adjacency to background:
                                   - touches BG (body outline + clapping
                                     arms)                       -> DEEP
                                   - fully interior (eye slits,
                                     mouth, tiny face marks)     -> PUPIL
                                 Same convention as build_sleep_themed.py.

Outputs:
  assets/clapping-blue.gif
  assets/clapping-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import deque

from PIL import Image, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "clapping-1.gif")

BG = (0, 0, 0, 0)

# Idle palette (reproduced from build_sleep_themed.py so the clapping
# recolor matches every other themed state exactly).
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c  (outline + clapping arms)
        "PUPIL": (25, 26, 27, 255),     # #191a1b  (eyes / mouth)
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
}

# Source pixel colors in clapping-1.gif (verified via getcolors()).
SRC_WHITE     = (255, 255, 255, 255)
SRC_LIGHTGRAY = (203, 204, 206, 255)
SRC_NEARBLACK = ( 35,  31,  32, 255)

W = H = 24
OUT_FRAME_MS = 40  # matches source; overridden per-frame from the src duration

# Figma reference (node 4840:2144) shades the creature from a top-right
# light source: only the LEFT side of the body carries an outline (a
# 2-column DEEP rim with a 2-column MID inner stripe), the RIGHT side is
# flush LIGHT with no outline, and the two clapping arms are colored by
# side -- LEFT arm DEEP, RIGHT arm MID. The head/body starts at row 8
# in every source frame; rows 0-7 are exclusively the animating arms.
BODY_TOP_Y = 8
MID_X = W // 2  # 12 -- x < MID_X is "left half" (arm/body)

# Eye pupils sit as a 2x2 block per eye at rows 13-14, cols 9-10 (left
# eye) and cols 15-16 (right eye). To match the idle / speak blink
# convention we treat the TOP row of each pupil as the eyelid: on blink
# frames those four pixels become LIGHT while the bottom row stays PUPIL,
# reading as an eyelid coming down rather than the eyes vanishing.
PUPIL_TOP_XY    = [(9, 13), (10, 13), (15, 13), (16, 13)]
PUPIL_BOTTOM_XY = [(9, 14), (10, 14), (15, 14), (16, 14)]

# Which source frames get the blink applied. Frame 16 is the peak of the
# clap; blinking on the last few frames of the loop feels like the buddy
# scrunches its eyes at the moment of impact, then reopens as the loop
# restarts. 3 frames at 40ms each = 120ms — matches the idle blink feel.
BLINK_FRAME_INDICES = {14, 15, 16}


def build_remap(palette):
    """Return a dict {source_rgba: target_rgba} for the given palette.
    SRC_WHITE and SRC_NEARBLACK are deliberately omitted -- both are
    handled per-pixel in recolor_frames():
      - SRC_WHITE is split via flood-fill into background (transparent)
        vs. body-fill (LIGHT).
      - SRC_NEARBLACK is split via BG adjacency into outline/arms (DEEP)
        vs. interior/eyes/mouth (PUPIL).
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


def classify_nearblack(pixels, bg_mask):
    """Return a 2D grid `role` where role[y][x] is one of:
      - None  : this pixel isn't SRC_NEARBLACK
      - "OUT" : this pixel is part of a near-black connected component
                that touches the background (outline / clapping arms)
      - "EYE" : this pixel is part of a near-black component that is
                fully enclosed inside the body (eye slits, mouth, tiny
                interior face marks)

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


def apply_figma_shading(remapped, palette):
    """Post-process a recolored frame in place so it matches the Figma
    reference (node 4840:2144):

      * Arm rows (0..BODY_TOP_Y-1): every DEEP pixel with x >= MID_X is
        remapped to MID, giving the LEFT arm a DEEP outline and the
        RIGHT arm a MID outline. When the arms clap together the two
        colors meet in the middle of the merged column, preserving the
        DD-on-left / MM-on-right convention throughout the animation.
      * Body rows (BODY_TOP_Y..H-1): for each row, the leftmost DEEP
        pixels stay DEEP, the two columns immediately to their right
        become MID (a subtle inner shadow), and every other DEEP or MID
        pixel in that row is flattened to LIGHT. This removes the
        right-side outline entirely and pulls the body fill flush to
        the canvas edge, matching the top-right-lit look of the Figma.
        PUPIL pixels (eyes / mouth) are never touched.
    """
    DEEP  = palette["DEEP"]
    MID   = palette["MID"]
    LIGHT = palette["LIGHT"]
    px = remapped.load()

    # 1. Arms: recolor the right-hand arm outline pixels.
    for y in range(BODY_TOP_Y):
        for x in range(W):
            if px[x, y] == DEEP and x >= MID_X:
                px[x, y] = MID

    # 2. Body: rewrite each row to a left-only outline.
    for y in range(BODY_TOP_Y, H):
        deep_xs = [x for x in range(W) if px[x, y] == DEEP]
        if not deep_xs:
            continue
        left_x = min(deep_xs)
        keep_deep = {left_x, left_x + 1}
        mid_cols  = {left_x + 2, left_x + 3}
        for x in range(W):
            c = px[x, y]
            if c == DEEP:
                if x in keep_deep:
                    continue  # stays DEEP
                px[x, y] = LIGHT
            elif c == MID:
                if x in mid_cols:
                    continue  # already the desired MID column
                px[x, y] = LIGHT
        # Ensure the two MID columns are set even if the source didn't
        # already carry SRC_LIGHTGRAY there (rows 8..13 need this).
        for x in mid_cols:
            if 0 <= x < W and px[x, y] == LIGHT:
                px[x, y] = MID


def apply_blink(remapped, palette):
    """Close the eyes by remapping the TOP row of each 2x2 pupil block to
    LIGHT (body fill). The bottom row stays PUPIL, so the eye reads as a
    slit under a lowered eyelid — same convention as build_idle_breathing
    and build_speak_themed.
    """
    LIGHT = palette["LIGHT"]
    PUPIL = palette["PUPIL"]
    px = remapped.load()
    for (x, y) in PUPIL_TOP_XY:
        if px[x, y] == PUPIL:
            px[x, y] = LIGHT


def recolor_frames(palette):
    """Load every frame of the source, composite it onto a fresh canvas
    so previous frames aren't inherited, remap the pixels, and return a
    list of (RGBA_image, delay_ms) tuples.
    """
    remap = build_remap(palette)
    src = Image.open(SRC)

    frames_out = []
    for frame_index, frame in enumerate(ImageSequence.Iterator(src)):
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
                    rpix[x, y] = BG if bg_mask[y][x] else palette["LIGHT"]
                elif c[3] == 0:
                    rpix[x, y] = BG
                elif c == SRC_NEARBLACK:
                    rpix[x, y] = palette["DEEP"] if nb_role[y][x] == "OUT" else palette["PUPIL"]
                else:
                    rpix[x, y] = remap.get(c, c)

        apply_figma_shading(remapped, palette)
        if frame_index in BLINK_FRAME_INDICES:
            apply_blink(remapped, palette)

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
        out_path = os.path.join(ASSETS, f"clapping-{name}.gif")
        frames = recolor_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
