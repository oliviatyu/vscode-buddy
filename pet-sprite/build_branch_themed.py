#!/usr/bin/env python3
"""
Build the "branch" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Matches Figma reference node 4910:2148 (Polish Push May-June 2026 file,
fileKey lWE17f1tRRDXWsbxTcbsmo) pixel-for-pixel.

Sprite layout (34x31, transparent background):
  - Buddy: 24x24 creature (unchanged from build_sleep_themed.py's grid)
           positioned at sprite (0, 7) so the branch trunk has 7 rows
           of headroom above the buddy's antlers -- 6 for the branch
           itself + 1 spare row so the animation can bob upward.
  - Branch accessory: a vertical zigzag trunk to the right of the buddy
           at sprite col 24-25, with two horizontal bumps and three
           bright green sparkle leaves scattered along its length. The
           branch bobs subtly up and down while the buddy stays fixed.

Creature palette placement (unchanged, per Figma 4840:3751):
  - Antlers on the head are in blue (DEEP + MID). Left antler uses DEEP
    at the tips, right antler uses MID.
  - Body is a chunky 3-step gradient on the left side (DEEP -> MID ->
    LIGHT) with pure LIGHT filling the rest -- there is no full outline.
  - PUPIL is used only for the two eye rectangles.

Branch palette (per Figma 4910:2148):
  - Trunk / offshoots -> MID (VS Code blue for the blue variant,
                              Insiders green for the green variant).
  - Sparkle leaves    -> bright activity green (#00ff61), kept constant
                              across both themes for visual contrast.

Animation:
  6 frames -- a slow bob (4 frames at 220 ms) that shifts the entire
  branch (trunk + leaves) up 1 px, back to baseline, down 1 px, back to
  baseline, followed by a short eye-blink at the rest position (2
  frames, 140 ms each). Buddy body pixels stay perfectly still across
  every frame; only the branch and the eyes change.

Output:
  assets/branch-blue.gif   (VS Code palette)
  assets/branch-green.gif  (Insiders palette)

Both GIFs are 34x31 pixels, 6 frames, transparent background -- so they
composite onto any surface, matching idle-breathing.gif and
sleep-{blue,green}.gif.

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# 4-tone palette, shared with build_sleep_themed.py so branch sits
# consistently next to the sleep sprite in the two themes.
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c  (from Figma 4840:3751)
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451  (matches sleep-green)
        "PUPIL": (25, 26, 27, 255),     # #191a1b
    },
}

# Pupil coordinates in the 24x24 CREATURE grid. Each eye is a 2x2 chunky
# pixel that spans rows 16-19 (top half rows 16-17, bottom half rows
# 18-19). Blinking mimics idle-breathing / speak: the TOP chunky pixel
# becomes body-fill LIGHT and only the BOTTOM chunky pixel remains as
# pupil, reading as an eyelid dropping down over the eye.
PUPIL_TOP_PIXELS = [
    (10, 16), (11, 16), (10, 17), (11, 17),   # left pupil top half
    (16, 16), (17, 16), (16, 17), (17, 17),   # right pupil top half
]

# Bright activity green used for the sparkle leaves on both themes.
# Sampled directly from Figma node 4910:2148.
SPARK = (0, 255, 97, 255)

# Output sprite bounds. 34 wide (tight-cropped to the far-right leaf) x
# 31 tall (24 for the buddy + 6 for the trunk above + 1 headroom row so
# the branch can bob upward by one pixel).
OUT_W = 34
OUT_H = 31

# Buddy sprite is 24x24 and sits at (BUDDY_X, BUDDY_Y) inside the sprite.
BUDDY_X = 0
BUDDY_Y = 7
CREATURE_W = 24
CREATURE_H = 24

# Branch is drawn with its ICON_ROWS[0] row landing on BRANCH_BASE_Y.
# Baseline of 1 gives 1 row of headroom above so a -1 offset frame can
# push the branch up without clipping. Down offsets stay clear of the
# buddy body because trunk pixels live at x=24-25 while buddy pixels
# only span x=0-23.
BRANCH_BASE_Y = 1

# 6-frame animation loop: 4 bob frames with eyes open, then a short
# blink at the rest position. Each tuple is (y_offset, eyes_open,
# delay_ms).
FRAMES = [
    ( 0, True,  220),   # rest, open
    (-1, True,  220),   # up 1, open
    ( 0, True,  220),   # rest, open
    ( 1, True,  220),   # down 1, open
    ( 0, False, 140),   # rest, BLINK
    ( 0, True,  140),   # rest, open (recovery before loop)
]

# --- Creature pixel data ---------------------------------------------------
# Ripped pixel-for-pixel from Figma node 4840:3751 (24x24). See docstring
# for palette placement notes.
#   .  transparent
#   L  LIGHT  (body fill)
#   M  MID    (mid shading / right antler)
#   D  DEEP   (deep shading / left antler)
#   #  PUPIL  (eyes only)
CREATURE_ROWS = [
    "........................",  #  0
    "........................",  #  1
    "......DD........MM......",  #  2  antler tips
    "......DD........MM......",  #  3
    "....DD..DD....MM..MM....",  #  4
    "....DD..DD....MM..MM....",  #  5
    "..........DDMM..........",  #  6  antlers meet the head
    "..........DDMM..........",  #  7
    "........DDMMLLLL........",  #  8  head crown
    "........DDMMLLLL........",  #  9
    "......DDMMLLLLLLLL......",  # 10
    "......DDMMLLLLLLLL......",  # 11
    "....DDMMLLLLLLLLLLLL....",  # 12
    "....DDMMLLLLLLLLLLLL....",  # 13
    "..DDMMLLLLLLLLLLLLLLLL..",  # 14
    "..DDMMLLLLLLLLLLLLLLLL..",  # 15
    "DDMMMMLLLL##LLLL##LLLLLL",  # 16  eye row
    "DDMMMMLLLL##LLLL##LLLLLL",  # 17
    "DDMMMMLLLL##LLLL##LLLLLL",  # 18
    "DDMMMMLLLL##LLLL##LLLLLL",  # 19
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 20
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 21
    "..DDDDMMMMLLLLLLLLLLLL..",  # 22  base sits above baseline
    "..DDDDMMMMLLLLLLLLLLLL..",  # 23
]

# --- Branch accessory pixel data --------------------------------------------
# Ripped pixel-for-pixel from Figma node 4910:2148. A vertical zigzag
# trunk in blue at sprite col 24-25, with two 2-unit horizontal bumps and
# three bright green sparkle leaves. Every visible pixel is drawn as a
# 2x2 block to match the buddy's chunky pixel unit.
#
#   .  transparent
#   B  blue branch body   (source #0077b8, remapped to palette["MID"])
#   G  green sparkle leaf (kept as SPARK = #00ff61 on both themes)
#
# Grid is 34 wide (tight-cropped -- rightmost pixel is the far-right
# leaf at col 33) x 24 rows tall (trunk top to trunk bottom). Buddy is
# painted separately at sprite (0, 7); no overlap between the two
# layers.
ICON_ROWS = [
    #         111111111122222222223333
    # 12345678901234567890123456789012 34
    "........................BB........",  # y= 0  trunk top
    "........................BB........",  # y= 1
    "..................GG....BB........",  # y= 2  upper-left leaf tip
    "..................GG....BB........",  # y= 3
    "....................BBBB..........",  # y= 4  upper-left bump
    "....................BBBB..........",  # y= 5
    "........................BB......GG",  # y= 6  far-right leaf
    "........................BB......GG",  # y= 7
    "........................BB....GG..",  # y= 8  inner-right leaf
    "........................BB....GG..",  # y= 9
    "..........................BBBB....",  # y=10  right-side bump
    "..........................BBBB....",  # y=11
    "........................BB........",  # y=12  trunk continues
    "........................BB........",  # y=13
    "........................BB........",  # y=14
    "........................BB........",  # y=15
    "........................BB........",  # y=16
    "........................BB........",  # y=17
    "........................BB........",  # y=18
    "........................BB........",  # y=19
    "........................BB........",  # y=20
    "........................BB........",  # y=21
    "........................BB........",  # y=22  trunk bottom
    "........................BB........",  # y=23
]


def paint_creature(palette, eyes_open=True):
    """Render the creature from CREATURE_ROWS using the themed palette.
    Returns a 24x24 RGBA frame with a transparent background. When
    eyes_open is False, the top chunky pixel of each pupil is replaced
    with LIGHT so the buddy looks like it's blinking (eyelid halfway
    down).
    """
    out = Image.new("RGBA", (CREATURE_W, CREATURE_H), BG)
    opix = out.load()
    lookup = {
        "L": palette["LIGHT"],
        "M": palette["MID"],
        "D": palette["DEEP"],
        "#": palette["PUPIL"],
    }
    for y, row in enumerate(CREATURE_ROWS):
        for x, ch in enumerate(row):
            color = lookup.get(ch)
            if color is not None:
                opix[x, y] = color
    if not eyes_open:
        for (px_, py_) in PUPIL_TOP_PIXELS:
            opix[px_, py_] = palette["LIGHT"]
    return out


def paint_branch(canvas, palette, y_offset=0):
    """Paint the branch accessory from ICON_ROWS onto `canvas` in place,
    themed by `palette`. The branch's ICON_ROWS[0] row lands on
    (BRANCH_BASE_Y + y_offset). Pixels outside the sprite are skipped.
    """
    cpix = canvas.load()
    for y, row in enumerate(ICON_ROWS):
        ty = BRANCH_BASE_Y + y + y_offset
        if ty < 0 or ty >= OUT_H:
            continue
        for x, ch in enumerate(row):
            if x >= OUT_W:
                continue
            if ch == "B":
                cpix[x, ty] = palette["MID"]
            elif ch == "G":
                cpix[x, ty] = SPARK
            # "." -> leave transparent


def build_frames(palette):
    """Build one canvas per FRAMES entry. Buddy is painted at the same
    (BUDDY_X, BUDDY_Y) on every frame so its body pixels stay static;
    only the branch position and the pupils change.
    """
    open_eyes = paint_creature(palette, eyes_open=True)
    blink_eyes = paint_creature(palette, eyes_open=False)
    frames = []
    for y_offset, eyes_open, delay_ms in FRAMES:
        canvas = Image.new("RGBA", (OUT_W, OUT_H), BG)
        paint_branch(canvas, palette, y_offset)
        creature = open_eyes if eyes_open else blink_eyes
        canvas.paste(creature, (BUDDY_X, BUDDY_Y), creature)
        frames.append((canvas, delay_ms))
    return frames


def write_gif(frames_ms, palette, out_path):
    """Write frames as a transparent-background looping GIF via gifsicle
    so per-frame delays and the transparent index are preserved exactly.
    frames_ms is a list of (PIL.Image RGBA, delay_ms) tuples.
    """
    opaque = [palette["PUPIL"], palette["DEEP"], palette["MID"], palette["LIGHT"], SPARK]
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
        for path, (_, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def main():
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"branch-{name}.gif")
        frames = build_frames(palette)
        write_gif(frames, palette, out_path)
        w, h = frames[0][0].size
        print(f"Wrote {out_path} ({w}x{h}, {len(frames)} frames)")


if __name__ == "__main__":
    main()
