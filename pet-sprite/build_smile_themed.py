#!/usr/bin/env python3
"""
Build the "smile" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Source: node 4840:2144 in the Polish Push May-June 2026 Figma file
(fileKey lWE17f1tRRDXWsbxTcbsmo). The base sprite is a 24x24 frame
showing the buddy with a big open grin -- two 2x2 pupil corners at
the sides of the mouth plus a 6x2 flat mouth block below. The mouth
stays static; the eyes blink on a slow cycle.

Pixel grid is baked directly from the Figma export -- the source PNG has
exactly 5 colors (background gray + 4 semantic slots) so we can lift
positions verbatim without SVG parsing.

Semantic slots:
  LIGHT   body highlight        (right side + interior)
  MID     body midtone / left-antenna       (2nd ring in)
  DEEP    body outline / right-antenna      (outermost)
  PUPIL   eyes + mouth

Outputs:
  assets/smile-blue.gif   (VS Code palette, 2-frame blink loop)
  assets/smile-green.gif  (Insiders palette, 2-frame blink loop)

Both GIFs are 24x24 with a transparent background so they drop into the
same slot on the sprite surface as the other state gifs.

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Themed palettes. Blue values are lifted directly from the Figma source
# (node 4840:2144). Green values mirror the ramp already used by
# sleep-green / branch-green / working-green / cool-green.
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),  # #23a8f2
        "MID":   (0, 119, 184, 255),   # #0077b8
        "DEEP":  (0,  78, 124, 255),   # #004e7c
        "PUPIL": (25,  26,  27, 255),  # #191a1b
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),  # #24bfa5
        "MID":   (0, 154, 124, 255),   # #009a7c
        "DEEP":  (0, 100,  81, 255),   # #006451
        "PUPIL": (25,  26,  27, 255),  # #191a1b
    },
}

W = H = 24

# Base sprite with the original flat smile baked in on rows 19-20.
# Rows 13-14 are the eyes and get rewritten per-frame to blink.
# Everything else stays fixed.
# One char per pixel, 24 columns wide × 24 rows tall.
# Legend:
#   .  transparent background
#   L  DEEP   (outermost outline / left-antenna tip)
#   M  MID    (2nd ring in / right-antenna tip)
#   #  LIGHT  (body fill)
#   D  PUPIL  (eyes + mouth)
BASE_SPRITE = [
    "........................",
    "........................",
    "....LLLL........MMMM....",
    "....LLLL........MMMM....",
    "........LL....MM........",
    "........LL....MM........",
    "..........LLMM..........",
    "..........LLMM..........",
    "........LLMM####........",
    "........LLMM####........",
    "......LLMM########......",
    "......LLMM########......",
    "....LLMM############....",
    "....LLMM#DD####DD###....",   # row 13 -- overridden per frame (eye top)
    "..LLMM###DD####DD#####..",   # row 14 -- overridden per frame (eye bottom)
    "..LLMM################..",
    "LLMM####################",
    "LLMM####DD######DD######",   # smile corners (top row)
    "LLMM####DD######DD######",   # smile corners (bottom row)
    "LLMM######DDDDDD########",   # mouth (flat top row)
    "LLMM######DDDDDD########",   # mouth (flat bottom row)
    "LLMM####################",
    "..LLMM################..",
    "..LLMM################..",
]

# Per-frame eye overrides (rows 13-14). Each entry is a
# (row_13, row_14) pair, each exactly 24 chars long.
#
# Frame 0 -- eyes open:   2x2 pupil block at cols 9-10 and 15-16
#                         (matches the baked base sprite).
# Frame 1 -- eyes closed: top row cleared, bottom row is a 4-wide
#                         horizontal eyelid stretched over each eye
#                         (2-wide -> 4-wide is a classic pixel-art
#                         blink cue).
EYE_FRAMES = [
    (
        "....LLMM#DD####DD###....",
        "..LLMM###DD####DD#####..",
    ),
    (
        "....LLMM############....",
        "..LLMM##DDDD##DDDD####..",
    ),
]

# Per-frame durations in milliseconds. Long open hold + quick blink.
FRAME_DELAYS_MS = [2400, 140]

CHAR_TO_SLOT = {
    "L": "DEEP",
    "M": "MID",
    "#": "LIGHT",
    "D": "PUPIL",
}


def sprite_for_frame(frame_idx):
    rows = list(BASE_SPRITE)
    r13, r14 = EYE_FRAMES[frame_idx]
    rows[13] = r13
    rows[14] = r14
    return rows


def rasterize(sprite_rows, palette):
    """Render a 24x24 sprite grid to an RGBA image using the palette."""
    assert len(sprite_rows) == H, f"sprite must have {H} rows, got {len(sprite_rows)}"
    img = Image.new("RGBA", (W, H), BG)
    px = img.load()
    for y, row in enumerate(sprite_rows):
        assert len(row) == W, f"row {y} must be {W} wide, got {len(row)}"
        for x, ch in enumerate(row):
            slot = CHAR_TO_SLOT.get(ch)
            if slot is None:
                continue
            px[x, y] = palette[slot]
    return img


def write_gif(frames_ms, palette, out_path):
    """Write a looping transparent GIF with per-frame delays via
    gifsicle (Pillow's GIF writer is unreliable with transparent
    animations)."""
    opaque_slots = ["PUPIL", "DEEP", "MID", "LIGHT"]
    pal_bytes = [0, 0, 0]  # index 0 = transparent placeholder
    for slot in opaque_slots:
        r, g, b, _a = palette[slot]
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {BG: 0}
    for i, slot in enumerate(opaque_slots, start=1):
        color_to_index[palette[slot]] = i

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, (frame, _delay) in enumerate(frames_ms):
            idx = Image.new("P", frame.size, 0)
            idx.putpalette(pal_bytes)
            src_pixels = frame.load()
            idx_pixels = idx.load()
            for y in range(frame.height):
                for x in range(frame.width):
                    idx_pixels[x, y] = color_to_index.get(src_pixels[x, y], 0)
            idx.info["transparency"] = 0

            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(p)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        args = ["gifsicle", "--loopcount=0", "--no-warnings", "--transparent=0"]
        for path, (_frame, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def build_frames(palette):
    frames = []
    for i, delay in enumerate(FRAME_DELAYS_MS):
        img = rasterize(sprite_for_frame(i), palette)
        frames.append((img, delay))
    return frames


def main():
    os.makedirs(ASSETS, exist_ok=True)
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"smile-{name}.gif")
        frames = build_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({len(frames)} frames, {W}x{H})")


if __name__ == "__main__":
    main()
