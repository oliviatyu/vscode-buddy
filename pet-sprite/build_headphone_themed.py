#!/usr/bin/env python3
"""
Build the animated "headphone" state sprite for the Buddy Veee tamagotchi
in the themed VS Code blue / Insiders green palettes.

Base pose:
  Transcribed pixel-for-pixel from Figma node 4909:1464 in the Polish
  Push May-June 2026 file (fileKey lWE17f1tRRDXWsbxTcbsmo). The sprite
  is drawn on a 28x24 canvas at the same "chunky 2x2" scale as the
  branch antler tips -- every visual unit in the Figma reference is a
  2x2 native pixel block, and this file keeps that as-is.

Layout (transparent background, 28x24):
  - Rows  0-3 : four twinkle sparkles above the headband (two on each
                side of the stem), painted in LIGHT.
  - Rows  4-5 : short headband stem coming down onto the head, LIGHT.
  - Rows  6-11: the DEEP headphone HEADBAND -- a horizontal bar across
                the top of the head that arches down on each side to
                meet the ear cups.
  - Rows 10-16: the DEEP headphone EAR CUPS on the left and right of
                the head (chunky trapezoidal rectangles). The head
                itself fills between them in LIGHT.
  - Rows 17-23: the creature's lower body, with the canonical left-edge
                MID outline (matching branch / cool / speak), an open
                square mouth (rows 17-20), and eyes tucked between the
                ear cups (rows 13-14) in PUPIL.

Animation (matches build_sing_themed.py -- the buddy is jamming out):
  Choppy, deliberately stop-motion. The mouth cycles through
  wide -> small -> closed -> small (~280 ms per frame -- a chiller
  tempo than sing). The antenna tips (the LIGHT twinkle sparkles above
  the headband) bob down 1 pixel on the "small" frames, giving the ears
  a subtle bounce on the beat. Everything below the headband stays
  static.

Palette semantics (4 colors, same set as idle-breathing / sleep-* etc.):
  LIGHT  -- bright body fill and sparkles
  MID    -- lower-body left-edge outline
  DEEP   -- headphone headband + ear cups
  PUPIL  -- eyes and open mouth

Outputs:
  assets/headphone-blue.gif   (VS Code palette,   28x24, 4 frames)
  assets/headphone-green.gif  (Insiders palette,  28x24, 4 frames)

Both GIFs have a transparent background so they composite onto any
surface, matching the other themed sprites.

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# 4-tone palette, shared with build_branch_themed.py / build_sleep_themed.py
# so the headphone sprite sits consistently next to its themed neighbors.
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

OUT_W = 28
OUT_H = 24

# --- Sprite pixel data ------------------------------------------------------
# Pixel-for-pixel from Figma node 4909:1464. Every char is one native
# pixel; the chunky look comes from painting in 2x2 blocks (the Figma
# vector rects were themselves 2x2).
#   .  transparent
#   L  LIGHT   (body fill + sparkles + headband)
#   M  MID     (mid outline / bottom shadow)
#   D  DEEP    (dark outline at head top-left)
#   #  PUPIL   (eyes + open mouth)
SPRITE_ROWS = [
    "........LL........LL........",  #  0  sparkle tops
    "........LL........LL........",  #  1
    "......LL..LL....LL..LL......",  #  2  sparkle wings
    "......LL..LL....LL..LL......",  #  3
    "............LLLL............",  #  4  headband stem
    "............LLLL............",  #  5
    "........DDDDDDDDDDDD........",  #  6  DEEP headband bar
    "........DDDDDDDDDDDD........",  #  7
    "......DD..LLLLLLLL..DD......",  #  8  headband shoulders + head top
    "......DD..LLLLLLLL..DD......",  #  9
    "....DD..LLLLLLLLLLLL..DD....",  # 10  ear-cup tops peek out
    "DDDDDD..LLLLLLLLLLLL..DDDDDD",  # 11  ear cups widen
    "DDDDLLLLLLLLLLLLLLLLLLLLDDDD",  # 12  ear cup + head
    "DDDDLLLLLL####LL####LLLLDDDD",  # 13  eyes tucked between cups
    "DDDDLLLLLL####LL####LLLLDDDD",  # 14
    "DDDDLLLLLLLLLLLLLLLLLLLLDDDD",  # 15  ear cup + head
    "DDDDLLLLLLLLLLLLLLLLLLLLDDDD",  # 16
    "..MMLLLLLLLLL####LLLLLLLLL..",  # 17  open mouth top
    "..MMLLLLLLLLL####LLLLLLLLL..",  # 18
    "..MMLLLLLLLLL####LLLLLLLLL..",  # 19
    "..MMLLLLLLLLL####LLLLLLLLL..",  # 20
    "..MMLLLLLLLLLLLLLLLLLLLLLL..",  # 21
    "....MMMMMMLLLLLLLLLLLLLL....",  # 22  base shadow
    "....MMMMMMLLLLLLLLLLLLLL....",  # 23
]


# --- Animation config -------------------------------------------------------
# Mouth is a 4x4 PUPIL block at cols 13-16, rows 17-20 in SPRITE_ROWS.
# On each animation frame we blank it back to LIGHT, then repaint the
# per-shape PUPIL pixels below. Same recipe as build_sing_themed.py.
MOUTH_X0, MOUTH_Y0 = 13, 17
MOUTH_W,  MOUTH_H  = 4,  4

# Sparkle antennae live at rows 0-3, cols 6-21 in SPRITE_ROWS. On the
# "down" frames we clear those 4 rows and repaint the sparkle 1 pixel
# lower, so the ear tips look like they're bobbing on the beat. The
# wings' bottom row lands on the headband stem (row 4) -- both are LIGHT
# so the overlap just widens the stem for one frame, which reads as an
# accent on the beat.
SPARKLE_ROWS = [
    "........LL........LL........",  # tip top
    "........LL........LL........",  # tip bottom
    "......LL..LL....LL..LL......",  # wings top
    "......LL..LL....LL..LL......",  # wings bottom
]
SPARKLE_TOP_Y = 0

# Mouth cycle mirrors sing: open -> pursed -> closed -> pursed. The
# tip bob is synced so the ears drop on the pursed frames. Delay is in
# centiseconds; 28 == 280ms, a bit slower than sing so the buddy grooves
# to a chiller tempo.
MOUTH_CYCLE = ["wide", "small", "closed", "small"]
TIP_CYCLE   = ["up",   "down",  "up",     "down"]
FRAME_DELAY_CS = 28


def mouth_pixels(shape):
    """Return the (x, y) coords inside the 4x4 mouth rect that should
    be PUPIL for the given mouth shape. Anything else in the rect stays
    LIGHT (body fill)."""
    if shape == "wide":
        return [(MOUTH_X0 + dx, MOUTH_Y0 + dy)
                for dy in range(MOUTH_H) for dx in range(MOUTH_W)]
    if shape == "small":
        # Inner 2x2 -- pursed opening.
        return [(MOUTH_X0 + dx, MOUTH_Y0 + dy)
                for dy in (1, 2) for dx in (1, 2)]
    if shape == "closed":
        # Single row of 4 across the middle of the rect -- held note.
        return [(MOUTH_X0 + dx, MOUTH_Y0 + 1) for dx in range(MOUTH_W)]
    raise ValueError(f"Unknown mouth shape: {shape}")


def build_base_frame(palette):
    """Render SPRITE_ROWS using the themed palette. Returns 28x24 RGBA."""
    canvas = Image.new("RGBA", (OUT_W, OUT_H), BG)
    pix = canvas.load()
    lookup = {
        "L": palette["LIGHT"],
        "M": palette["MID"],
        "D": palette["DEEP"],
        "#": palette["PUPIL"],
    }
    for y, row in enumerate(SPRITE_ROWS):
        for x, ch in enumerate(row):
            color = lookup.get(ch)
            if color is not None:
                pix[x, y] = color
    return canvas


def build_animation_frames(palette):
    """Return a list of 28x24 RGBA frames for the mouth + tip-bob cycle."""
    base = build_base_frame(palette)
    LIGHT = palette["LIGHT"]
    PUPIL = palette["PUPIL"]

    # Erase the mouth to LIGHT on the shared base so per-frame shapes
    # overwrite cleanly.
    bpx = base.load()
    for dy in range(MOUTH_H):
        for dx in range(MOUTH_W):
            bpx[MOUTH_X0 + dx, MOUTH_Y0 + dy] = LIGHT

    frames = []
    for shape, tip in zip(MOUTH_CYCLE, TIP_CYCLE):
        frame = base.copy()
        fpx = frame.load()

        # Shift sparkle antennae down 1 pixel on "down" frames.
        if tip == "down":
            # Wipe the canonical sparkle rows so nothing lingers at the
            # top. Row 4 (headband stem) stays intact because we only
            # clear rows 0-3, and the shifted wings-bottom paints over
            # row 4 with LIGHT (same color as the stem).
            for y in range(SPARKLE_TOP_Y, SPARKLE_TOP_Y + len(SPARKLE_ROWS)):
                for x in range(OUT_W):
                    fpx[x, y] = BG
            offset_y = SPARKLE_TOP_Y + 1
            for dy, row in enumerate(SPARKLE_ROWS):
                for dx, ch in enumerate(row):
                    if ch == "L":
                        fpx[dx, offset_y + dy] = LIGHT

        # Paint the mouth for this frame.
        for (x, y) in mouth_pixels(shape):
            fpx[x, y] = PUPIL
        frames.append(frame)
    return frames


def write_gif(frames, palette, out_path):
    """Write an animated transparent GIF via gifsicle so the transparent
    index is preserved exactly across frames."""
    opaque = [palette["PUPIL"], palette["DEEP"], palette["MID"], palette["LIGHT"]]
    color_to_index = {BG: 0}
    pal_bytes = [0, 0, 0]  # index 0 = transparent placeholder
    for color in opaque:
        if color in color_to_index:
            continue
        color_to_index[color] = len(color_to_index)
        r, g, b, _a = color
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, frame in enumerate(frames):
            idx = Image.new("P", frame.size, 0)
            idx.putpalette(pal_bytes)
            src_pixels = frame.load()
            idx_pixels = idx.load()
            for y in range(frame.height):
                for x in range(frame.width):
                    idx_pixels[x, y] = color_to_index.get(src_pixels[x, y], 0)
            idx.info["transparency"] = 0
            fp = os.path.join(tmp, f"f{i:03d}.gif")
            idx.save(fp, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(fp)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        subprocess.run([
            "gifsicle",
            "--loopcount=0",
            "--no-warnings",
            "--disposal=background",
            "--transparent=0",
            f"--delay={FRAME_DELAY_CS}",
            *frame_paths,
            "--output", out_path,
        ], check=True)


def main():
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"headphone-{name}.gif")
        frames = build_animation_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({frames[0].size[0]}x{frames[0].size[1]}, "
              f"{len(frames)} frames)")


if __name__ == "__main__":
    main()
