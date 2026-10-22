#!/usr/bin/env python3
"""
Build an idle-breathing GIF for the Buddy Veee sprite matching the Polish
Push May-June 2026 Figma file (fileKey lWE17f1tRRDXWsbxTcbsmo). Supports
multiple color palettes; all palettes share the same silhouette and motion.

Available palettes:
  blue  -> Figma node 4842-7457
  green -> Figma node 4841-7104

Motion is stop-motion pixel-art:
    - Frames 0-19  (0-800 ms):   REST pose, 2x3 eyes open
    - Frames 20-22 (800-920 ms): COMPRESSED pose, 2x3 eyes open
    - Frames 23-27 (920-1120 ms): COMPRESSED pose, single-row blink
    - Frames 28-49 (1120-2000 ms): COMPRESSED pose, 2x3 eyes open

50 frames * 40 ms = 2000 ms loop. Assembly is done via gifsicle for
exact per-frame delays; Pillow's GIF writer collapses duplicate frames.

Usage:
  python3 build_idle_breathing_blue.py                       # blue -> assets/idle-breathing.gif
  python3 build_idle_breathing_blue.py --palette green       # green -> assets/idle-breathing.gif
  python3 build_idle_breathing_blue.py --palette green --out /path/to/green24.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import argparse
import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
DEFAULT_OUT = os.path.join(ASSETS, "idle-breathing.gif")

# --- Palettes sampled from Figma exports. -----------------------------------
# BG is always fully transparent so the sprite composites onto any background.
# The five colors are keyed by their semantic role (see CODE_TO_RGBA below).
BG = (0, 0, 0, 0)

PALETTES = {
    # Blue variant (Figma node 4842-7457)
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2 bright body fill
        "MID":   (0, 119, 184, 255),    # #0077b8 mid outline / highlight
        "DARK":  (0,  78, 124, 255),    # #004e7c dark shadow (left edge)
        "PUPIL": (25, 26, 27, 255),     # #191a1b pupils
    },
    # Green variant (Figma node 4841-7104)
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5 bright body fill
        "MID":   (0, 154, 124, 255),    # #009a7c mid outline / highlight
        "DARK":  (0,  69,  56, 255),    # #004538 dark shadow (left edge)
        "PUPIL": (25, 26, 27, 255),     # #191a1b pupils
    },
}

# These four module-level colors are set from the chosen palette at run time.
# Semantic aliases so the sprite reads clearly:
#   . = background   P = pupil
#   D = dark shadow  M = mid outline   L = bright body fill
PUPIL = DARK = MID = LIGHT = None  # populated by apply_palette()
CODE_TO_RGBA: dict[str, tuple[int, int, int, int]] = {}


def apply_palette(name: str) -> None:
    global PUPIL, DARK, MID, LIGHT, CODE_TO_RGBA
    pal = PALETTES[name]
    PUPIL = pal["PUPIL"]
    DARK = pal["DARK"]
    MID = pal["MID"]
    LIGHT = pal["LIGHT"]
    CODE_TO_RGBA = {
        ".": BG,
        "P": PUPIL,
        "D": DARK,
        "M": MID,
        "L": LIGHT,
    }

# --- Blue REST pose (24x24). Reproduced exactly from Figma export. ---------
# Each row is 24 characters. Row 0 is at the top of the image.
REST_ROWS = [
    "....MM............MM....",  # y= 0
    "....MM............MM....",  # y= 1
    "......MM........MM......",  # y= 2
    "......MM........MM......",  # y= 3
    "........MM....MM........",  # y= 4
    "........MM....MM........",  # y= 5
    "..........DDMM..........",  # y= 6
    "..........DDMM..........",  # y= 7
    "........DDMMLLLL........",  # y= 8
    "........DDMMLLLL........",  # y= 9
    "......DDMMLLLLLLLL......",  # y=10
    "......DDMMLLLLLLLL......",  # y=11
    "....DDMMLLLLLLLLLLLL....",  # y=12
    "....DDMMLLLLLLLLLLLL....",  # y=13
    "..DDMMLLLLLLLLLLLLLLLL..",  # y=14
    "..DDMMLLLLLLLLLLLLLLLL..",  # y=15
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # y=16  <- pupil row (open)
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # y=17  <- pupil row (open)
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # y=18  <- pupil row (open)
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # y=19
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # y=20
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # y=21
    "..DDMMMMMMLLLLLLLLLLLL..",  # y=22  <- bottom bar (fixed)
    "..DDMMMMMMLLLLLLLLLLLL..",  # y=23  <- bottom bar (fixed)
]

# Pupil pixel coordinates in the REST pose. Each eye is a 2x3 block; we split
# it into rows so the blink can replace the top two rows with body fill and
# leave the bottom row as a visible slit.
PUPIL_PIXELS_REST_TOP = [
    (10, 16), (11, 16),  # left eye, top row
    (16, 16), (17, 16),  # right eye, top row
]
PUPIL_PIXELS_REST_MIDDLE = [
    (10, 17), (11, 17),  # left eye, middle row
    (16, 17), (17, 17),  # right eye, middle row
]
PUPIL_PIXELS_REST_BOTTOM = [
    (10, 18), (11, 18),  # left eye, bottom row
    (16, 18), (17, 18),  # right eye, bottom row
]

W = H = 24
BAR_ROWS = 2                # rows 22-23 stay fixed
COMPRESS_OFFSET = 1         # head+eyes shift down 1 image pixel on exhale
OUT_FRAME_MS = 40           # per-frame delay
OUT_FRAMES = 50


def build_rest_frame():
    im = Image.new("RGBA", (W, H))
    for y, row in enumerate(REST_ROWS):
        assert len(row) == W, f"row {y} has {len(row)} chars, expected {W}"
        for x, ch in enumerate(row):
            im.putpixel((x, y), CODE_TO_RGBA[ch])
    return im


def blink(im):
    """Return a copy with the top two pupil rows replaced by body fill,
    leaving the bottom row as a slit so the eyes do not vanish entirely.
    """
    out = im.copy()
    for x, y in PUPIL_PIXELS_REST_TOP + PUPIL_PIXELS_REST_MIDDLE:
        out.putpixel((x, y), LIGHT)
    return out


def compress(im, offset=COMPRESS_OFFSET):
    """Shift rows 0..(H-BAR_ROWS-1) DOWN by offset, fill the newly exposed
    top rows with BG, keep the bottom bar (rows 22-23) fixed.

    This is what makes the body walls compress from 4 rows to 3 rows on the
    exhale — the top of the creature drops down while the bar stays put.
    """
    out = Image.new("RGBA", (W, H), BG)
    body_h = H - BAR_ROWS                       # 22
    src_body = im.crop((0, 0, W, body_h - offset))  # top 21 rows of source
    out.paste(src_body, (0, offset))            # paste at y=offset (=1)
    # Paste the bar back in on top so it stays anchored.
    bar = im.crop((0, body_h, W, H))
    out.paste(bar, (0, body_h))
    return out


def write_gif(frames_ms, out_path):
    """frames_ms is a list of (PIL.Image RGBA 24x24, delay_ms) tuples.

    All delays should be OUT_FRAME_MS; we still pass a list for flexibility.
    Uses gifsicle to assemble so per-frame delays are exact.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # Write each frame as an indexed-palette single-frame GIF with the
        # transparent BG marked so gifsicle can combine them cleanly.
        # GIF only supports 1-bit alpha, so we build the palette by hand:
        # index 0 = transparent; remaining indices = the sprite colors.
        opaque_palette = [PUPIL, DARK, MID, LIGHT]  # RGBA -> we drop the A
        pal_bytes = [0, 0, 0]                       # index 0 placeholder (transparent)
        for r, g, b, _a in opaque_palette:
            pal_bytes.extend([r, g, b])
        # Pad palette to 256 * 3 bytes (required by PIL).
        pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

        color_to_index = {
            (0, 0, 0, 0): 0,
            PUPIL: 1,
            DARK: 2,
            MID: 3,
            LIGHT: 4,
        }

        frame_paths = []
        for i, (frame, _) in enumerate(frames_ms):
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            for y in range(H):
                for x in range(W):
                    idx.putpixel((x, y), color_to_index[frame.getpixel((x, y))])
            idx.save(p, "GIF", transparency=0, disposal=2)
            frame_paths.append(p)

        # Assemble with gifsicle. Each frame's --delay is in centiseconds.
        delay_cs = OUT_FRAME_MS // 10  # 40ms -> 4cs
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cmd = [
            "gifsicle",
            "--loop=0",
            "--disposal=background",
            "--transparent=0",
            f"--delay={delay_cs}",
            "--output",
            out_path,
        ] + frame_paths
        subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", choices=sorted(PALETTES.keys()),
                        default="blue",
                        help="Which color variant to render (default: blue).")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help=f"Output GIF path (default: {DEFAULT_OUT}).")
    args = parser.parse_args()

    apply_palette(args.palette)

    rest = build_rest_frame()
    rest_blink = blink(rest)
    comp = compress(rest)
    comp_blink = compress(rest_blink)  # compress the blinked frame

    seq = []
    for i in range(OUT_FRAMES):
        if i < 20:
            seq.append((rest, OUT_FRAME_MS))              # frames 0-19  rest
        elif 23 <= i <= 27:
            seq.append((comp_blink, OUT_FRAME_MS))        # frames 23-27 blink
        else:
            seq.append((comp, OUT_FRAME_MS))              # 20-22, 28-49

    write_gif(seq, args.out)
    print(f"wrote {args.out}  ({OUT_FRAMES} frames * {OUT_FRAME_MS}ms = {OUT_FRAMES*OUT_FRAME_MS}ms loop, palette={args.palette})")


if __name__ == "__main__":
    main()
