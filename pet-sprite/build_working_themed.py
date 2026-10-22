#!/usr/bin/env python3
"""
Build themed blue / green variants of the "working" sprite from the
existing reference animation ``assets/processing-pingpong.gif``.

Design reference (Figma file lWE17f1tRRDXWsbxTcbsmo):
  - node 4271:4404 – blue "working" frame
  - node 4271:4448 – green "working" frame

Both Figma frames match the character in ``processing-pingpong.gif``:
a small monitor buddy with two X-shaped antennae on top, a ">_"
terminal prompt inside the screen, and a tiny grey shadow foot at
the bottom-left. The Figma files are single frames; the animation
comes from the existing 58-frame ping-pong gif (25 fps).

Palette (matches build_sleep_themed.py / build_speak_themed.py):
  blue:  LIGHT #23a8f2 · MID #0077b8 · DEEP #004e7c · PUPIL #191a1b
  green: LIGHT #24bfa5 · MID #009a7c · DEEP #006451 · PUPIL #191a1b

Source palette (from processing-pingpong.gif):
  (35, 31, 32)     → DEEP if the dark pixel touches the background
                     (outer outline of monitor body, screen frame,
                     antennae) – matches Figma node 4840:2560 which
                     uses a dark themed blue for the outline rather
                     than near-black.
                   → PUPIL if the dark pixel is fully enclosed inside
                     the monitor body (">_" prompt, cursor).
  (203, 204, 206)  → MID    – small shadow / foot pixel
  (255, 255, 255)  → LIGHT  – if enclosed inside the monitor body
                    TRANSPARENT if reachable from outside (background,
                    and the empty space between the antenna Xs).

Outputs:
  assets/working-blue.gif
  assets/working-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import deque

from PIL import Image, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "processing-pingpong.gif")

PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c  (outline; from Figma 4840:2560)
        "PUPIL": (25, 26, 27, 255),     # #191a1b  (enclosed marks: >_, cursor)
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451  (outline; mirrors blue ramp)
        "PUPIL": (25, 26, 27, 255),     # #191a1b  (enclosed marks: >_, cursor)
    },
}

# Source colours in the reference gif.
SRC_DARK  = (35, 31, 32)
SRC_MID   = (203, 204, 206)
SRC_LIGHT = (255, 255, 255)


def recolor_frame(rgba: Image.Image, palette: dict) -> Image.Image:
    """Return a new RGBA frame with source colours mapped to the palette.

    White pixels that are reachable from the frame border via 4-neighbour
    flood-fill on white are treated as background and become transparent;
    other white pixels are the enclosed monitor interior and become LIGHT.

    Dark pixels are further split via 8-connected components: any
    component that touches the canvas border or a background pixel is
    the outline (monitor body, screen frame, antennae) and becomes
    DEEP; fully enclosed components (the ">_" prompt and cursor) stay
    PUPIL. Mirrors the convention in build_sleep_themed.py.
    """
    W, H = rgba.size
    px = rgba.load()

    # Flood-fill from every border pixel that is currently white.
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

    # Classify each SRC_DARK pixel as either OUTLINE (touches bg) or
    # ENCLOSED (fully inside the body) via 8-connected components.
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
                # Any unexpected colour – keep as-is.
                op[x, y] = (r, g, b, a)
    return out


def build_variant(variant: str) -> str:
    """Recolor every frame of ``processing-pingpong.gif`` and write
    ``assets/working-<variant>.gif`` with a fixed 4-colour indexed
    palette (index 0 = transparent) so gifsicle preserves transparency
    across all frames — same recipe used by ``build_speak_themed.py``.
    """
    palette = PALETTES[variant]
    src = Image.open(SRC)

    # Fixed palette: index 0 transparent, then PUPIL / DEEP / MID / LIGHT.
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
    for f in ImageSequence.Iterator(src):
        delays.append(f.info.get("duration", 40))
        rgba_frames.append(recolor_frame(f.convert("RGBA"), palette))

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

        out_path = os.path.join(ASSETS, f"working-{variant}.gif")
        args = ["gifsicle", "--loopcount=0", "--no-warnings"]
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
