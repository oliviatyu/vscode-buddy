#!/usr/bin/env python3
"""
Build themed blue / green variants of the "speak" sprite based on the
Figma design (file lWE17f1tRRDXWsbxTcbsmo, node 4891:511).

The output GIF matches the Figma canvas exactly: 36 wide × 33 tall,
with the character at the bottom-left and the speech bubble at the
top-right, mirrored horizontally so its tail curls down-left toward
the character's head — identical composition to Figma.

  ┌─────────────────────────────────────┐
  │                    ,--speech--,     │ ← bubble (16x16), placed at
  │                    │ · · ·    │     │   (20, 0), mirrored
  │                    `--v-------'     │   with 3 animated typing dots
  │        ,--char--,                   │
  │       antennae + head + eyes + feet │ ← character (24x22),
  │                                     │   placed at (0, 11)
  └─────────────────────────────────────┘

Palette (matches Figma node 4840:3596):
  blue:  LIGHT #23a8f2 · MID #0077b8 · DEEP #004e7c · PUPIL #191a1b
  green: LIGHT #24bfa5 · MID #009a7c · DEEP #006652 · PUPIL #191a1b

- LIGHT fills the enclosed body interior (identified via flood-fill
  from outside) AND the enclosed bubble interior.
- MID is the small highlight/shine on the character's upper-left arm
  (rgba(203,204,206) in the source).
- DEEP is every outline pixel around the body / bubble / antennae
  (per updated Figma design — previously rendered as PUPIL near-black).
- PUPIL stays reserved for the eye pixels and the typing dots inside
  the bubble.

Dots inside the bubble cycle PUPIL → LIGHT to give a typing indicator.

Outputs:
  assets/speak-blue.gif
  assets/speak-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

W, H = 36, 33  # matches Figma frame 4891:511
BG = (0, 0, 0, 0)

PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0, 78, 124, 255),     # #004e7c — outline color per Figma
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 102, 82, 255),     # #006652 — outline color (green analog)
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
}

# ─── Figma pixel data ────────────────────────────────────────────────────
# Character body — 24 wide × 22 tall as extracted directly from the
# Figma design (frame 4840:3596, character = child "Layer_1").
#
# The character has asymmetric lighting per Figma — light comes from
# the top-right, so:
#   * outline on the LEFT / BOTTOM-LEFT is DEEP #004e7c (symbol '0')
#   * inner shading band is MID  #0077b8              (symbol '1')
#   * body fill is LIGHT #23a8f2                       (symbol 'L')
#   * RIGHT / BOTTOM-RIGHT edges have NO dark outline — the LIGHT fill
#     runs all the way to the shape's edge.
#   * the LEFT antenna is DEEP, the RIGHT antenna is MID.
#   * eye pixels are PUPIL near-black                  (symbol 'E')
#   * '.' = transparent margin (flood-filled to None by classify_interior).
CHAR_ROWS = [
    "......00........11......",  # row  0 – antenna tips (L=DEEP, R=MID)
    "......00........11......",  # row  1
    "....00..00....11..11....",  # row  2
    "....00..00....11..11....",  # row  3
    "..........0011..........",  # row  4 – head crown top (L=DEEP, R=MID)
    "..........0011..........",  # row  5
    "........0011LLLL........",  # row  6 – head crown
    "........0011LLLL........",  # row  7
    "......0011LLLLLLLL......",  # row  8
    "......0011LLLLLLLL......",  # row  9
    "....0011LLLLLLLLLLLL....",  # row 10
    "....0011LLLLLLLLLLLL....",  # row 11
    "..0011LLLLLLLLLLLLLLLL..",  # row 12
    "..0011LLLLLLLLLLLLLLLL..",  # row 13
    "001111LLLLEELLLLEELLLLLL",  # row 14 – body + eyes
    "001111LLLLEELLLLEELLLLLL",  # row 15
    "001111LLLLEELLLLEELLLLLL",  # row 16
    "001111LLLLEELLLLEELLLLLL",  # row 17
    "001111LLLLLLLLLLLLLLLLLL",  # row 18 – wider MID band on lower-left arm
    "001111LLLLLLLLLLLLLLLLLL",  # row 19
    "..00001111LLLLLLLLLLLL..",  # row 20 – bottom bar (DEEP+MID on left, LIGHT on right)
    "..00001111LLLLLLLLLLLL..",  # row 21
]
assert all(len(r) == 24 for r in CHAR_ROWS)
assert len(CHAR_ROWS) == 22

# Speech bubble — 16 wide × 16 tall as authored in Figma.
# 0 = outline (dark),  D = dot (animated: DARK ↔ LIGHT),  . = interior
# (becomes LIGHT fill).  Note this is the UN-MIRRORED source; the
# stamp step below applies the horizontal mirror that Figma's
# -scale-x-100 gives it so the tail points toward the character.
BUBBLE_ROWS = [
    "..000000000000..",  # row  0 – top curve
    "..000000000000..",  # row  1
    "00............00",  # row  2
    "00............00",  # row  3
    "00............00",  # row  4
    "00..DD.DD.DD..00",  # row  5 – 3 dots
    "00..DD.DD.DD..00",  # row  6
    "00............00",  # row  7
    "00............00",  # row  8
    "00............00",  # row  9
    "..0000....0000..",  # row 10 – bottom corners
    "..0000....0000..",  # row 11
    "......00..00....",  # row 12 – tail curl
    "......00..00....",  # row 13
    "........0000....",  # row 14 – tail tip
    "........0000....",  # row 15
]
assert all(len(r) == 16 for r in BUBBLE_ROWS)
assert len(BUBBLE_ROWS) == 16

# Where in the 36x33 canvas each element lives (matches Figma exactly).
CHAR_OX, CHAR_OY     = 0, 11
BUBBLE_OX, BUBBLE_OY = 20, 0
BUBBLE_MIRROR_X      = True  # matches Figma's -scale-x-100 on Group 25


def _compute_bubble_interior_mask():
    """Precompute a 16x16 boolean mask: True for cells enclosed by the
    bubble outline (i.e. bubble interior — body + tail interior),
    False for cells outside the outline (rounded-rect corners of the
    16x16 bounding box). Uses a 4-connected flood fill from the
    bubble's own bounding-box edges through every non-outline cell."""
    def blocked(ch):
        return ch == "0"  # only the outline blocks — dots pass through
    exterior = [[False] * 16 for _ in range(16)]
    q = deque()
    for x in range(16):
        for y in (0, 15):
            if not blocked(BUBBLE_ROWS[y][x]) and not exterior[y][x]:
                exterior[y][x] = True
                q.append((x, y))
    for y in range(16):
        for x in (0, 15):
            if not blocked(BUBBLE_ROWS[y][x]) and not exterior[y][x]:
                exterior[y][x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < 16 and 0 <= ny < 16 and not exterior[ny][nx]:
                if not blocked(BUBBLE_ROWS[ny][nx]):
                    exterior[ny][nx] = True
                    q.append((nx, ny))
    return [
        [(not exterior[y][x]) and not blocked(BUBBLE_ROWS[y][x])
         for x in range(16)]
        for y in range(16)
    ]


BUBBLE_INTERIOR_MASK = _compute_bubble_interior_mask()


# ─── Frame construction ──────────────────────────────────────────────────
def blank_grid():
    """Return a WxH grid of None (transparent placeholder)."""
    return [[None] * W for _ in range(H)]


# Eye pixels come from the 'E' cells in CHAR_ROWS. In the speak pose the
# eyes are 2 chunky pixels tall (rows 14-15 = top chunky pixel, rows 16-17
# = bottom chunky pixel) — taller than the idle pose which only has the
# bottom chunky pixel. When blinking we mimic idle's eyelid-down direction:
# the TOP chunky pixel becomes body fill (L) and only the BOTTOM chunky
# pixel remains as pupil (P), so the closed height matches idle exactly.
EYE_TOP_CHAR_ROWS = {14, 15}   # chunky pixel that disappears when eyes close


def stamp_char(grid, eyes_open=True):
    """Stamp the character onto the grid.
    Values written:
      'O'  = outline (renders as DEEP)
      'M'  = mid highlight (renders as MID)
      'L'  = explicit body fill (renders as LIGHT). Written explicitly
             because the character shape is open on the right — relying
             on flood-fill from the outside would erase interior pixels.
      'P'  = eye pixel (renders as PUPIL near-black)
      '.'  = interior placeholder (kept as-is; flood-filled later)

    When eyes_open is False, the top chunky pixel of each eye (CHAR_ROWS
    rows 14-15) renders as body fill instead of pupil, leaving only the
    bottom chunky pixel (rows 16-17) as a slit — the same blink shape and
    direction as build_idle_breathing_blue.py.
    """
    for cy, row in enumerate(CHAR_ROWS):
        for cx, ch in enumerate(row):
            x, y = cx + CHAR_OX, cy + CHAR_OY
            if not (0 <= x < W and 0 <= y < H):
                continue
            if ch == "0":
                grid[y][x] = "O"
            elif ch == "1":
                grid[y][x] = "M"
            elif ch == "L":
                grid[y][x] = "L"
            elif ch == "E":
                if (not eyes_open) and cy in EYE_TOP_CHAR_ROWS:
                    grid[y][x] = "L"   # eyelid down over top half of eye
                else:
                    grid[y][x] = "P"
            elif grid[y][x] is None:
                grid[y][x] = "."


def _bubble_lookup(bx, by):
    """Return (char, interior_flag) for the bubble cell at (bx, by),
    honouring BUBBLE_MIRROR_X so the tail curls toward the character."""
    src_bx = (15 - bx) if BUBBLE_MIRROR_X else bx
    return BUBBLE_ROWS[by][src_bx], BUBBLE_INTERIOR_MASK[by][src_bx]


def stamp_bubble(grid, dot_states):
    """Stamp the bubble onto the grid, drawing OVER any character
    pixels that share cells with the bubble body / outline.

    dot_states: iterable of 3 booleans — True = dot DARK (visible),
    False = dot LIGHT (typing-indicator "off"). Dots are numbered
    left-to-right in the FINAL (mirrored) composition, so state[0]
    is the leftmost visible dot in the rendered image.
    """
    for by in range(16):
        prev_ch = None
        run_dot_index = -1
        for bx in range(16):
            x, y = bx + BUBBLE_OX, by + BUBBLE_OY
            if not (0 <= x < W and 0 <= y < H):
                continue
            ch, interior = _bubble_lookup(bx, by)
            if ch == "0":
                grid[y][x] = "O"
            elif ch == "D":
                if prev_ch != "D":
                    run_dot_index += 1
                # Dots render as PUPIL (near-black) when "on", LIGHT when "off".
                grid[y][x] = "P" if dot_states[run_dot_index] else "L"
            else:
                # Only fill the enclosed bubble interior with LIGHT.
                # Bounding-box corners outside the outline are left
                # alone so the exterior stays transparent and any
                # character pixels underneath the corners remain visible.
                if interior:
                    grid[y][x] = "L"
            prev_ch = ch


def classify_interior(grid):
    """Convert every '.' cell in the grid to either 'L' (body
    interior) or None (exterior transparent) via 4-connected
    flood-fill from the canvas edges.

    The flood treats both '.' (character placeholder) and None
    (never-stamped) cells as "open" for propagation — that way a '.'
    cell reachable from an edge via a chain of untouched cells is
    still correctly classified as exterior. Only 'O' / 'M' / 'L'
    pixels (already-committed colors) block the flood.
    """
    def is_open(cell):
        return cell == "." or cell is None

    exterior = [[False] * W for _ in range(H)]
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if is_open(grid[y][x]) and not exterior[y][x]:
                exterior[y][x] = True
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if is_open(grid[y][x]) and not exterior[y][x]:
                exterior[y][x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not exterior[ny][nx]:
                if is_open(grid[ny][nx]):
                    exterior[ny][nx] = True
                    q.append((nx, ny))
    for y in range(H):
        for x in range(W):
            if grid[y][x] == ".":
                grid[y][x] = None if exterior[y][x] else "L"


def grid_to_rgba(grid, palette):
    """Render the symbolic grid to a WxH RGBA image using the palette."""
    lookup = {
        "O": palette["DEEP"],   # outlines
        "M": palette["MID"],    # arm / bubble shading
        "L": palette["LIGHT"],  # body + bubble interior fill
        "P": palette["PUPIL"],  # eyes + typing dots
        None: BG,
    }
    img = Image.new("RGBA", (W, H), BG)
    px = img.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = lookup[grid[y][x]]
    return img


# ─── Animation timeline ──────────────────────────────────────────────────
# Typing-indicator cycle. Each entry is (dot_states, delay_ms, eyes_open).
# dot_states = (dot1_dark, dot2_dark, dot3_dark), left-to-right in the
# FINAL rendered image. eyes_open=False triggers a blink (top chunky pixel
# of each eye becomes body fill, matching idle-breathing).
TIMELINE = [
    ((True,  False, False), 220, True),   # dot 1 lights up
    ((True,  True,  False), 220, True),   # dot 2 lights up
    ((True,  True,  True ), 220, True),   # dot 3 lights up
    ((True,  True,  True ), 100, True),   # hold all three — eyes open
    ((True,  True,  True ), 160, False),  # BLINK during hold (~160ms, matches idle)
    ((False, False, False), 180, True),   # brief clear before looping
]


def build_frames(palette):
    frames = []
    for dot_states, delay, eyes_open in TIMELINE:
        grid = blank_grid()
        stamp_char(grid, eyes_open=eyes_open)
        stamp_bubble(grid, dot_states)
        classify_interior(grid)
        frames.append((grid_to_rgba(grid, palette), delay))
    return frames


# ─── GIF writer (transparent BG, per-frame delays via gifsicle) ─────────
def write_gif(frames_ms, palette, out_path):
    opaque = [palette["PUPIL"], palette["MID"], palette["LIGHT"], palette["DEEP"]]
    pal_bytes = [0, 0, 0]  # index 0 = transparent
    for r, g, b, _a in opaque:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {
        BG: 0,
        palette["PUPIL"]: 1,
        palette["MID"]:   2,
        palette["LIGHT"]: 3,
        palette["DEEP"]:  4,
    }

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, (frame, _) in enumerate(frames_ms):
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            src = frame.load()
            dst = idx.load()
            for y in range(H):
                for x in range(W):
                    dst[x, y] = color_to_index.get(src[x, y], 0)
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
    os.makedirs(ASSETS, exist_ok=True)
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"speak-{name}.gif")
        frames = build_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({len(frames)} frames, {W}x{H})")


if __name__ == "__main__":
    main()
