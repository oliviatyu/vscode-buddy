#!/usr/bin/env python3
"""
Build the "worry" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Source: node 4915:172 in the Polish Push May-June 2026 Figma file
(fileKey lWE17f1tRRDXWsbxTcbsmo). The base sprite is a 24x24 frame
showing the buddy with X-shaped ("><") eyes, two zig-zag stress
antennae above the head, and two sweat droplets frozen in mid-arc on
either side of the head -- the classic pixel-art "stressed / worried"
pose.

Pixel grid is baked directly from the Figma export -- the source PNG
has exactly 5 colors (background gray + 4 semantic slots) so we can
lift positions verbatim without SVG parsing.

Semantic slots (match smile / cool / sleep etc.):
  DEEP    outermost outline / left stress-line   (`L`)
  MID     mid outline / right stress-line        (`M`)
  LIGHT   body highlight / sweat droplets        (`#`)
  PUPIL   X-eyes                                 (`D`)

Animation (2-frame worry loop, ~1200 ms total):
  Sweat: holds the Figma peak pose (both inner + outer droplets on
    each side) so the sweat reads as constant tension. No per-drop
    lifecycle -- the motion is carried by the flip instead.
  Body: the entire 24x24 sprite flips horizontally between frames so
    the buddy visibly swivels back and forth, like he's worrying about
    which way to go. The zig-zag stress antennae swap sides on the
    flip, which sells the head-turn. Eyes stay open in the `>< ><`
    Figma X the whole time -- no blink.

Outputs:
  assets/worry-blue.gif   (VS Code palette,  24x24, 2-frame loop)
  assets/worry-green.gif  (Insiders palette, 24x24, 2-frame loop)

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Themed palettes. Blue values are lifted directly from the Figma
# source (node 4915:172). Green values mirror the ramp already used by
# smile-green / cool-green / sleep-green / working-green etc.
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

# Base sprite -- body + stress lines + normal X eyes. Sweat droplets
# are painted per-frame as pixel overlays (not baked in here) so we
# can animate them without duplicating the whole grid.
# Legend:
#   .  transparent background
#   L  DEEP   (outermost outline / left stress-line)
#   M  MID    (mid outline / right stress-line)
#   #  LIGHT  (body fill)
#   D  PUPIL  (X eyes)
BASE_SPRITE = [
    "......LL........MM......",  #  0
    "......LL........MM......",  #  1
    "........LL....MM........",  #  2
    "........LL....MM........",  #  3
    "........LL....MM........",  #  4
    "........LL....MM........",  #  5
    "..........LLMM..........",  #  6  (sweat cleared, painted per-frame)
    "..........LLMM..........",  #  7
    "........LLMM####........",  #  8  (sweat cleared, painted per-frame)
    "........LLMM####........",  #  9
    "......LLMM########......",  # 10
    "......LLMM########......",  # 11
    "....LLMM############....",  # 12
    "....LLMM############....",  # 13
    "..LLMM################..",  # 14
    "..LLMM###DD#######DD##..",  # 15  -- normal X eyes (overridden on wince)
    "LLMM#####DD#######DD####",  # 16
    "LLMM#######DD###DD######",  # 17
    "LLMM#######DD###DD######",  # 18
    "LLMM#####DD#######DD####",  # 19
    "LLMM#####DD#######DD####",  # 20
    "LLMM####################",  # 21
    "..LLMMMM##############..",  # 22
    "..LLMMMM##############..",  # 23
]

# Sweat droplet positions. Each 2x2 block is one droplet frozen at a
# moment along its arc. INNER = just leaving the head (lower, closer
# to the body). OUTER = mid-flight (higher, further away). Both are
# on-screen every frame -- the Figma peak pose.
SWEAT_INNER_LEFT  = [(3, 8), (4, 8), (3, 9), (4, 9)]
SWEAT_INNER_RIGHT = [(20, 8), (21, 8), (20, 9), (21, 9)]
SWEAT_OUTER_LEFT  = [(1, 6), (2, 6), (1, 7), (2, 7)]
SWEAT_OUTER_RIGHT = [(22, 6), (23, 6), (22, 7), (23, 7)]

ALL_SWEATS = (
    SWEAT_INNER_LEFT + SWEAT_INNER_RIGHT +
    SWEAT_OUTER_LEFT + SWEAT_OUTER_RIGHT
)

# Per-frame recipe: (flip_horizontally?, sweat pixel coords, delay_ms).
# The buddy holds the Figma peak-sweat pose and just swivels left/right
# by flipping the whole sprite each frame -- reads as "worried, looking
# around, unsure which way to go."
FRAMES = [
    # 0 -- facing forward (Figma-native orientation), matches the
    # Figma reference pixel-for-pixel.
    (False, ALL_SWEATS, 600),

    # 1 -- mirrored: stress lines swap sides, body flips, sweats stay
    # in place (2x2 blocks are symmetric across the flip axis at
    # x=11.5, so the sweat silhouette is preserved even after mirror).
    (True, ALL_SWEATS, 600),
]

CHAR_TO_SLOT = {
    "L": "DEEP",
    "M": "MID",
    "#": "LIGHT",
    "D": "PUPIL",
}


def sprite_rows_for_frame(_frame_idx):
    """Return the 24-row grid for this frame. All frames share the same
    base grid; the horizontal flip is applied to the rasterized image,
    not to the ASCII rows."""
    return list(BASE_SPRITE)


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


def rasterize_frame(frame_idx, palette):
    """Full per-frame render: base rows + sweat pixels, mirrored
    horizontally if the recipe asks for it."""
    img = rasterize(sprite_rows_for_frame(frame_idx), palette)
    flip, sweat_pixels, _delay = FRAMES[frame_idx]
    px = img.load()
    for (x, y) in sweat_pixels:
        px[x, y] = palette["LIGHT"]
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
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
    for i, (_flip, _sweat, delay) in enumerate(FRAMES):
        img = rasterize_frame(i, palette)
        frames.append((img, delay))
    return frames


def main():
    os.makedirs(ASSETS, exist_ok=True)
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"worry-{name}.gif")
        frames = build_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({len(frames)} frames, {W}x{H})")


if __name__ == "__main__":
    main()
