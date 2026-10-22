#!/usr/bin/env python3
"""
Bake `sing-source-themed.png` (Figma export of node 4840:4311 in file
lWE17f1tRRDXWsbxTcbsmo, "Polish Push May–June 2026") into blue + green
ANIMATED GIFs matching the palette used by the other tamagotchi
states (see build_sleep_themed.py, build_idle_breathing_blue.py).

Source palette (already themed in blue by the Figma design):
  ( 35,  35,  35) canvas background          -> transparent
  ( 35, 168, 242) light blue  #23a8f2        -> LIGHT
  (  0, 119, 184) mid blue    #0077b8        -> MID
  (  0,  78, 124) deep blue   #004e7c        -> DEEP  (outline / notes shadow)
  ( 25,  26,  27) near-black  #191a1b        -> PUPIL (eye slits, mouth)

Animation: choppy, deliberately stop-motion. The mouth cycles through
open -> small -> closed -> small (roughly 200ms each), and the music
notes hop to a new offset on each frame so they feel like they're
floating out of the character in discrete beats.

The source is tightly cropped to the character + music-notes bounding
box, then padded so the notes have room to hop up / sideways without
being clipped.

Outputs:
  assets/sing-blue.gif
  assets/sing-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "sing-source-themed.png")

BG = (0, 0, 0, 0)
SRC_BG = (35, 35, 35, 255)

# Source (Figma) colors, in blue.
SRC_LIGHT = (35, 168, 242, 255)
SRC_MID   = (0, 119, 184, 255)
SRC_DEEP  = (0,  78, 124, 255)
SRC_PUPIL = (25, 26, 27, 255)

# Target palettes. Green ramp matches build_sleep_themed.py / idle green.
PALETTES = {
    "blue": {
        SRC_LIGHT: (35, 168, 242, 255),
        SRC_MID:   (0, 119, 184, 255),
        SRC_DEEP:  (0,  78, 124, 255),
        SRC_PUPIL: (25, 26, 27, 255),
    },
    "green": {
        SRC_LIGHT: (36, 191, 165, 255),   # #24bfa5
        SRC_MID:   (0, 154, 124, 255),    # #009a7c
        SRC_DEEP:  (0, 100,  81, 255),    # #006451
        SRC_PUPIL: (25, 26, 27, 255),     # eyes stay near-black
    },
}


def crop_to_content(img):
    """Return (cropped_image, (left, top)). Trims the (35,35,35) border
    so the output is only the character + notes."""
    W, H = img.size
    px = img.load()
    xs, ys = [], []
    for y in range(H):
        for x in range(W):
            if px[x, y] != SRC_BG:
                xs.append(x)
                ys.append(y)
    if not xs:
        return img, (0, 0)
    left, right = min(xs), max(xs) + 1
    top, bottom = min(ys), max(ys) + 1
    return img.crop((left, top, right, bottom)), (left, top)


def recolor(img, remap):
    """Return a new RGBA image with SRC_BG made transparent and every
    other known color mapped via `remap`. Unknown non-bg colors are
    preserved (should not occur for a clean Figma export)."""
    W, H = img.size
    src_px = img.load()
    out = Image.new("RGBA", (W, H), BG)
    out_px = out.load()
    for y in range(H):
        for x in range(W):
            c = src_px[x, y]
            if c == SRC_BG or c[3] == 0:
                out_px[x, y] = BG
            else:
                out_px[x, y] = remap.get(c, c)
    return out


# --- Animation config -------------------------------------------------
#
# Mouth position in the cropped source (verified from the ASCII dump of
# sing-source-themed.png): the original mouth is a 4x4 PUPIL block at
# cols 11-14 rows 22-25. We erase it from the "character base" and
# repaint one of these shapes on each frame:
MOUTH_X0, MOUTH_Y0 = 11, 22
MOUTH_W,  MOUTH_H  = 4,  4

# Music-note region in the cropped source. Notes and body share the top
# 16 rows, and the head widens to the right in the last few rows, so a
# single x threshold isn't enough — we'd either clip the right ear
# (rows 7-10 cols 14-19, the mid-blue mirror of the deep-blue left
# antenna) or drag part of the head (rows 13-15 cols 14-17) with the
# note animation.
#
# Instead, we use a per-row "max body x" table derived directly from the
# ASCII dump of sing-source-themed.png: a lit pixel is a note iff
# y <= NOTES_MAX_Y AND x > BODY_MAX_X_PER_ROW[y]. Rows outside this
# range have no notes.
NOTES_MAX_Y = 15
BODY_MAX_X_PER_ROW = {
    #  y : max x of character body/antennae/ears on that row (-1 = row
    #      is entirely notes-or-empty on the character side).
     0: -1,  1: -1,  2: -1,  3: -1,  4: -1,  5: -1,  6: -1,
     7: 17,  8: 17,               # top blocks: left antenna @6-7, right ear @16-17
     9: 19, 10: 19,               # bottom prongs: L @4-5,8-9  R @14-15,18-19
    11: 13, 12: 13,               # top of head (no ear pixels this row)
    13: 15, 14: 15,               # head widens (LLLL at cols 12-15)
    15: 17,                       # head widest (LLLLLLLL at cols 10-17)
}

# Per-frame (mouth_shape, (dx, dy)) where dx/dy is the note offset in
# pixels within the padded canvas. Deliberately jerky — this is stop-
# motion, not smooth animation.
FRAMES = [
    ("wide",   ( 0,  0)),
    ("small",  ( 0, -1)),
    ("closed", (+1, -2)),
    ("small",  (-1, -1)),
]
FRAME_DELAY_CS = 18  # ~180ms per frame; choppy on purpose.

# Padding around the cropped sprite so shifted notes don't get clipped.
PAD_TOP, PAD_LEFT, PAD_RIGHT, PAD_BOTTOM = 2, 1, 1, 0


def mouth_pixels(shape):
    """Return the (x, y) coords (in cropped-image coord space) that
    should be PUPIL for the given mouth shape. Everything else in the
    MOUTH_W x MOUTH_H mouth rect stays LIGHT (body fill)."""
    if shape == "wide":
        return [(MOUTH_X0 + dx, MOUTH_Y0 + dy)
                for dy in range(MOUTH_H) for dx in range(MOUTH_W)]
    if shape == "small":
        # Inner 2x2, so the mouth looks like a small pursed opening.
        return [(MOUTH_X0 + dx, MOUTH_Y0 + dy)
                for dy in (1, 2) for dx in (1, 2)]
    if shape == "closed":
        # Single row of 4 across the middle — the mouth is shut, like
        # a held note between syllables.
        return [(MOUTH_X0 + dx, MOUTH_Y0 + 1) for dx in range(MOUTH_W)]
    raise ValueError(f"Unknown mouth shape: {shape}")


def build_frames(themed, remap):
    """Given the already-recolored, cropped source image, return a list
    of RGBA frames implementing the singing animation."""
    W, H = themed.size
    LIGHT = remap[SRC_LIGHT]
    PUPIL = remap[SRC_PUPIL]

    # Split the sprite into a character base (mouth erased to LIGHT,
    # notes cleared to transparent) and a notes-only layer.
    src_px = themed.load()
    notes = Image.new("RGBA", (W, H), BG)
    npx = notes.load()
    base = themed.copy()
    bpx = base.load()

    for y in range(H):
        for x in range(W):
            c = src_px[x, y]
            if c == BG:
                continue
            body_max = BODY_MAX_X_PER_ROW.get(y, W)  # rows >15 -> all body
            if y <= NOTES_MAX_Y and x > body_max:
                # This is a note pixel: move it to the notes layer,
                # clear it from the base.
                npx[x, y] = c
                bpx[x, y] = BG

    # Erase mouth to LIGHT so per-frame mouth shapes overwrite cleanly.
    for dy in range(MOUTH_H):
        for dx in range(MOUTH_W):
            bpx[MOUTH_X0 + dx, MOUTH_Y0 + dy] = LIGHT

    canvas_w = W + PAD_LEFT + PAD_RIGHT
    canvas_h = H + PAD_TOP + PAD_BOTTOM

    frames = []
    for shape, (dx, dy) in FRAMES:
        frame = Image.new("RGBA", (canvas_w, canvas_h), BG)
        frame.paste(base, (PAD_LEFT, PAD_TOP), base)
        fpx = frame.load()
        for (mx, my) in mouth_pixels(shape):
            fpx[mx + PAD_LEFT, my + PAD_TOP] = PUPIL
        frame.paste(notes, (PAD_LEFT + dx, PAD_TOP + dy), notes)
        frames.append(frame)
    return frames


def write_animated_gif(frames, out_path, palette_colors, delay_cs):
    """Write a multi-frame transparent GIF. Palette index 0 is the
    transparent slot; each entry in `palette_colors` is placed at
    indices 1..N. gifsicle stitches the per-frame indexed GIFs into
    one animation with the requested frame delay."""
    W, H = frames[0].size
    pal_bytes = [0, 0, 0]
    for r, g, b, _a in palette_colors:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {BG: 0}
    for i, c in enumerate(palette_colors, start=1):
        color_to_index[c] = i

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, frame in enumerate(frames):
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            src_px = frame.load()
            idx_px = idx.load()
            for y in range(H):
                for x in range(W):
                    idx_px[x, y] = color_to_index.get(src_px[x, y], 0)
            idx.info["transparency"] = 0
            fp = os.path.join(tmp, f"f{i:02d}.gif")
            idx.save(fp, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(fp)

        subprocess.run(
            ["gifsicle", "--no-warnings", "--loopcount=0",
             "--disposal=background", f"--delay={delay_cs}",
             *frame_paths, "--output", out_path],
            check=True,
        )


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f"Source not found: {SRC}")
    src = Image.open(SRC).convert("RGBA")
    cropped, offset = crop_to_content(src)
    print(f"Source {src.size} -> cropped {cropped.size} at offset {offset}")

    for name, remap in PALETTES.items():
        themed = recolor(cropped, remap)
        frames = build_frames(themed, remap)
        # Palette order: PUPIL (darkest) -> DEEP -> MID -> LIGHT, so the
        # optimized GIF is deterministic across builds.
        pal = [
            remap[SRC_PUPIL],
            remap[SRC_DEEP],
            remap[SRC_MID],
            remap[SRC_LIGHT],
        ]
        out_path = os.path.join(ASSETS, f"sing-{name}.gif")
        write_animated_gif(frames, out_path, pal, FRAME_DELAY_CS)
        fw, fh = frames[0].size
        print(f"Wrote {out_path} ({fw}x{fh}, {len(frames)} frames)")


if __name__ == "__main__":
    main()
