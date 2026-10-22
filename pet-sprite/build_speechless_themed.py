#!/usr/bin/env python3
"""
Build the "speechless" state sprite for the Buddy Veee tamagotchi in
the themed VS Code blue / Insiders green palettes.

Source: node 4840:3864 in the Polish Push May-June 2026 Figma file
(fileKey lWE17f1tRRDXWsbxTcbsmo). 24x24 frame showing the buddy with
two square eyes and NO mouth — the "speechless" / silent look. The
open-eye pose is pixel-identical to the Figma export.

Motion: an idle-style blink. The eye is 4 rows tall (a 4-wide chunky
top pixel + a 2-wide chunky bottom pixel). On blink, the TOP chunky
pixel becomes body fill and only the BOTTOM chunky pixel remains as
a slit — the same eyelid-down direction as build_speak_themed.py and
build_idle_breathing_blue.py.

Pixel grid is baked directly from the Figma export -- the source PNG
has exactly 5 colors (background gray + 4 semantic slots) so we can
lift positions verbatim without SVG parsing.

Semantic slots:
  LIGHT   body highlight        (right side + interior)
  MID     body midtone / right-antenna
  DEEP    body outline / left-antenna
  PUPIL   eyes

Outputs:
  assets/speechless-blue.gif   (VS Code palette,  24x24, 2 frames)
  assets/speechless-green.gif  (Insiders palette, 24x24, 2 frames)

Both GIFs are 24x24, transparent background -- drop-in compatible with
smile-{blue,green}.gif on the sprite surface.

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
# (node 4840:3864). Green values mirror the ramp already used by
# smile-green / sleep-green / branch-green / cool-green.
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

# Sprite grid, one char per pixel, 24 columns wide × 24 rows tall.
# Legend:
#   .  transparent background
#   L  DEEP   (outermost outline / left-antenna)
#   M  MID    (2nd ring in / right-antenna)
#   #  LIGHT  (body fill)
#   D  PUPIL  (eyes)
SPRITE = [
    "......LL........MM......",
    "......LL........MM......",
    "....LL..LL....MM..MM....",
    "....LL..LL....MM..MM....",
    "..LL......LLMM......MM..",
    "..LL......LLMM......MM..",
    "........LLMM####........",
    "........LLMM####........",
    "......LLMM########......",
    "......LLMM########......",
    "....LLMM############....",
    "....LLMM############....",
    "..LLMM################..",
    "..LLMM################..",
    "LLMM####################",
    "LLMM####DDDD###DDDD#####",
    "LLMM####DDDD###DDDD#####",
    "LLMM######DD#####DD#####",
    "LLMM######DD#####DD#####",
    "LLMM####################",
    "LLMMMM##################",
    "LLMMMM##################",
    "..LLLLMMMM############..",
    "..LLLLMMMM############..",
]

CHAR_TO_SLOT = {
    "L": "DEEP",
    "M": "MID",
    "#": "LIGHT",
    "D": "PUPIL",
}


# ─── Blink ────────────────────────────────────────────────────────────
# Each eye is 4 rows tall in the open pose:
#   rows 15-16 : top chunky pupil pixel (4 cols wide)
#   rows 17-18 : bottom chunky pupil pixel (2 cols wide, indented)
# On blink the eyelid drops halfway: the TOP chunky pixel becomes body
# fill and only the BOTTOM chunky pixel remains as a slit. This mirrors
# the direction used by build_idle_breathing_blue.py and
# build_speak_themed.py so blinks read the same across every state.
EYELID_ROWS = {15, 16}


def close_eyes(sprite):
    """Return a copy of SPRITE with the top chunky pupil pixel replaced
    by body fill, leaving a slit on the bottom row."""
    return [
        (row.replace("D", "#") if y in EYELID_ROWS else row)
        for y, row in enumerate(sprite)
    ]


# Two-frame timeline: long open hold + short blink. Delays in ms match
# the idle-breathing blink cadence (2600 open / 120 closed).
TIMELINE = [
    (SPRITE,             2600),
    (close_eyes(SPRITE),  120),
]


def rasterize(grid, palette):
    """Render a grid of SPRITE-style chars to a 24x24 RGBA image."""
    assert len(grid) == H, f"grid must have {H} rows, got {len(grid)}"
    img = Image.new("RGBA", (W, H), BG)
    px = img.load()
    for y, row in enumerate(grid):
        assert len(row) == W, f"row {y} must be {W} wide, got {len(row)}"
        for x, ch in enumerate(row):
            slot = CHAR_TO_SLOT.get(ch)
            if slot is None:
                continue
            px[x, y] = palette[slot]
    return img


def write_gif(frames_ms, palette, out_path):
    """Write a multi-frame transparent GIF via gifsicle so per-frame
    delays are exact and the transparent index survives optimisation."""
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
            src = frame.load()
            dst = idx.load()
            for y in range(frame.height):
                for x in range(frame.width):
                    dst[x, y] = color_to_index.get(src[x, y], 0)
            idx.info["transparency"] = 0
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(p)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        args = ["gifsicle", "--loopcount=0", "--no-warnings"]
        for path, (_, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background",
                     "--transparent=0", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def main():
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"speechless-{name}.gif")
        frames_ms = [(rasterize(grid, palette), delay)
                     for grid, delay in TIMELINE]
        write_gif(frames_ms, palette, out_path)
        total_ms = sum(d for _, d in TIMELINE)
        print(f"Wrote {out_path} ({W}x{H}, {len(frames_ms)} frames, "
              f"{total_ms} ms loop)")


if __name__ == "__main__":
    main()
