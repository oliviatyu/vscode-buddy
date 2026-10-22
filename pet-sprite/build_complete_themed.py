#!/usr/bin/env python3
"""
Build themed blue / green variants of the "complete" sprite from the
existing reference animation ``assets/complete.gif``.

The reference is a 24x24, 31-frame GIF (70 ms per frame) showing the
buddy raising both arms in celebration: arms start in a wide "X" pose
at the bottom of the character's head, rise up through a wave, and
settle in a V pose above the head. The body/head stays constant across
frames -- only rows 0-9 (the arms) animate.

Palette (matches build_working_themed.py / build_sleep_themed.py):
  blue:  LIGHT #23a8f2 · MID #0077b8 · DEEP #004e7c · PUPIL #191a1b
  green: LIGHT #24bfa5 · MID #009a7c · DEEP #006451 · PUPIL #191a1b

Source palette (in ``complete.gif``):
  (35, 31, 32)     dark   -> DEEP  if the dark component touches the
                            transparent background (body outline,
                            floating arms/hands)
                         -> PUPIL if the dark component is fully
                            enclosed inside the body (eyes)
  (203, 204, 206)  gray   -> MID   (interior shading down the left side)
  (255, 255, 255)  white  -> LIGHT if enclosed inside the body outline,
                            TRANSPARENT if reachable from the canvas
                            edge (background)

Outputs:
  assets/complete-blue.gif
  assets/complete-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import deque

from PIL import Image, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "complete.gif")

PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
}

SRC_DARK  = (35, 31, 32)
SRC_MID   = (203, 204, 206)
SRC_LIGHT = (255, 255, 255)

# Eye pupil geometry (identical across every frame -- the head/body are
# static, only the arms/ears animate). Each eye is a 2x2 chunky pixel
# stacked vertically: TOP chunk = rows 15-16, BOTTOM chunk = rows 17-18,
# at cols 8-9 (left eye) and 14-15 (right eye).
PUPIL_TOP_XY = [
    (8, 15), (9, 15), (8, 16), (9, 16),
    (14, 15), (15, 15), (14, 16), (15, 16),
]

# The arms rise into a closed "circle" above the head at source frame
# 14 and hold that pose through the end of the GIF. A beat later, blink
# for 3 frames (~210ms at 70ms/frame) as a little "ta-da" punctuation
# after the ears complete the circle. The pose then re-opens for the
# remaining frames so the animation ends with the eyes open.
BLINK_FRAME_INDICES = {20, 21, 22}


def recolor_frame(rgba: Image.Image, palette: dict) -> Image.Image:
    """Remap the reference-frame colours to the themed palette.

    Uses the same flood-fill + 8-connected-component classification as
    build_working_themed.py so the semantics are consistent across the
    themed sprite family.
    """
    W, H = rgba.size
    px = rgba.load()

    # 1. Flood-fill white pixels reachable from the border. These become
    #    transparent background; enclosed white becomes LIGHT.
    outside = [[False] * H for _ in range(W)]
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            r, g, b, _ = px[x, y]
            if (r, g, b) == SRC_LIGHT and not outside[x][y]:
                outside[x][y] = True
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            r, g, b, _ = px[x, y]
            if (r, g, b) == SRC_LIGHT and not outside[x][y]:
                outside[x][y] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not outside[nx][ny]:
                r, g, b, _ = px[nx, ny]
                if (r, g, b) == SRC_LIGHT:
                    outside[nx][ny] = True
                    q.append((nx, ny))

    # 2. Classify each dark 8-connected component as outline (touches
    #    background) or enclosed (eyes).
    role = [[None] * H for _ in range(W)]
    seen = [[False] * H for _ in range(W)]
    neighbors8 = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)]
    for sy in range(H):
        for sx in range(W):
            if seen[sx][sy]:
                continue
            r, g, b, _ = px[sx, sy]
            if (r, g, b) != SRC_DARK:
                continue
            comp = []
            touches_bg = False
            stack = [(sx, sy)]
            seen[sx][sy] = True
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for dx, dy in neighbors8:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < W and 0 <= ny < H):
                        touches_bg = True
                        continue
                    if outside[nx][ny]:
                        touches_bg = True
                        continue
                    if not seen[nx][ny]:
                        rr, gg, bb, _a = px[nx, ny]
                        if (rr, gg, bb) == SRC_DARK:
                            seen[nx][ny] = True
                            stack.append((nx, ny))
            label = "OUT" if touches_bg else "EYE"
            for x, y in comp:
                role[x][y] = label

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    op = out.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            key = (r, g, b)
            if key == SRC_DARK:
                op[x, y] = palette["DEEP"] if role[x][y] == "OUT" else palette["PUPIL"]
            elif key == SRC_MID:
                op[x, y] = palette["MID"]
            elif key == SRC_LIGHT:
                if outside[x][y]:
                    op[x, y] = (0, 0, 0, 0)
                else:
                    op[x, y] = palette["LIGHT"]
            else:
                op[x, y] = (r, g, b, a)
    return out


def build_variant(variant: str) -> str:
    palette = PALETTES[variant]
    src = Image.open(SRC)

    # Fixed indexed palette: 0=transparent, then PUPIL / DEEP / MID / LIGHT.
    pal_bytes = [0, 0, 0]
    for r, g, b, _a in (palette["PUPIL"], palette["DEEP"], palette["MID"], palette["LIGHT"]):
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))
    color_to_index = {
        (0, 0, 0, 0): 0,
        palette["PUPIL"]: 1,
        palette["DEEP"]:  2,
        palette["MID"]:   3,
        palette["LIGHT"]: 4,
    }

    delays = []
    rgba_frames = []
    for i, f in enumerate(ImageSequence.Iterator(src)):
        delays.append(f.info.get("duration", 70))
        recolored = recolor_frame(f.convert("RGBA"), palette)
        if i in BLINK_FRAME_INDICES:
            # Lower the eyelid: convert the TOP chunky pixel of each eye
            # (rows 15-16, cols 8-9 + 14-15) to LIGHT so the eye reads as
            # a slit under a dropped lid. Same convention as
            # build_clapping_themed / build_idle_breathing.
            bp = recolored.load()
            for (x, y) in PUPIL_TOP_XY:
                if bp[x, y] == palette["PUPIL"]:
                    bp[x, y] = palette["LIGHT"]
        rgba_frames.append(recolored)

    W, H = rgba_frames[0].size

    with tempfile.TemporaryDirectory() as td:
        frame_paths = []
        for i, fr in enumerate(rgba_frames):
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            src_px = fr.load()
            dst_px = idx.load()
            for y in range(H):
                for x in range(W):
                    dst_px[x, y] = color_to_index.get(src_px[x, y], 0)
            idx.info["transparency"] = 0
            p = os.path.join(td, f"f_{i:03d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(p)

        out_path = os.path.join(ASSETS, f"complete-{variant}.gif")
        # Play once and hold on the final frame: the arms/ears rise into
        # a closed "circle" above the head at frame 14 and stay in that
        # pose through the end of the source GIF (frame 30). Using
        # --no-loopcount stops the animation on the circle instead of
        # snapping back to the wide-X starting pose.
        args = ["gifsicle", "--no-loopcount", "--no-warnings"]
        for p, delay_ms in zip(frame_paths, delays):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", p]
        args += ["--output", out_path]
        subprocess.run(args, check=True)
    return out_path


def main() -> None:
    for variant in ("blue", "green"):
        out = build_variant(variant)
        size = os.path.getsize(out)
        print(f"wrote {out} ({size} bytes)")


if __name__ == "__main__":
    main()
