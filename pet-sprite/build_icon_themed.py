#!/usr/bin/env python3
"""
Build the "icon" state for the Buddy Veee tamagotchi.

Concept: the buddy tips over to the left and lands as the classic
VS Code app icon (the chevron-marked round shape). He STAYS laying
down -- no getting back up. The animation plays ONCE and holds on
the icon pose; this state does NOT loop.

Canvas: 52 wide × 34 tall. The buddy body itself is always 24 × 24
pixels; the extra padding exists so the whole tipping motion is
fully visible without clipping. The standing buddy is anchored with
his 24×24 sprite pasted at (BUDDY_OFF_X, BUDDY_OFF_Y) = (26, 10), so
his base row sits on canvas row 33 (the ground line) and he pivots
around canvas coords (26, 33) -- the bottom-LEFT corner of his
sprite bounding box. That pivot placement means every pixel of the
falling buddy lands cleanly inside the canvas with at least a 2 px
margin on every side. Standing occupies x=26..49 (right half); the
final laying-down icon pose is pasted at (2, 10) so it occupies
x=2..25 (left half), sits on the ground row, and its antenna trail
reaches the left edge with a 2 px margin.

Motion beat:
  1. Idle rest                    -- slow breathing, upright, front
  2. Tip over to the left         -- slow rotation keyframes, ends
                                     flat on his side with FACE still
                                     visible
  3. Pause laying down            -- hold on the face-visible fallen
                                     pose for a beat so the viewer
                                     registers that he's down
  4. Turn / show his back         -- instant swap to the VS Code app
                                     icon pose from Figma (the black
                                     chevron mark reads as the "tail"
                                     on his back). Held forever.

The end-frame is a pixel-for-pixel copy of the Figma reference at
https://www.figma.com/design/lWE17f1tRRDXWsbxTcbsmo/Polish-Push-May---June-2026?node-id=4929-116
-- the classic VS Code app icon rendered in the theme palette.

The GIF is authored with `--no-loopcount`, so browsers play it once
and stop; the final frame's 30-second delay is a belt-and-braces
measure against players that ignore the loop-count metadata.

Palette (matches other themed builds -- blue = VS Code, green = Insiders):
  blue:  LIGHT #23a8f2 · MID #0077b8 · DEEP #004e7c · PUPIL #191a1b
  green: LIGHT #24bfa5 · MID #009a7c · DEEP #006451 · PUPIL #191a1b

Outputs:
  assets/icon-blue.gif
  assets/icon-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

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

# --- Buddy sprite geometry ------------------------------------------------
# The buddy body itself is always 24 × 24 pixels. The output canvas is
# larger so the buddy has room to tip over and lie down without being
# clipped.
BUDDY_W = BUDDY_H = 24
FRAME_W = 52
FRAME_H = 34
BUDDY_OFF_X = 26  # buddy standing occupies canvas x=26..49
BUDDY_OFF_Y = 10  # buddy standing occupies canvas y=10..33 (base = ground)

# Pivot for the fall / rise, in FRAME coords: bottom-LEFT corner of
# the standing buddy's 24×24 sprite bounding box. Rotating positive
# angles is visually CCW in PIL, which tips the buddy's TOP down to
# the LEFT and lays him out along the ground. Because the pivot is
# the left corner of the base (not the centre), every pixel of the
# rotated buddy stays at y ≤ 33 (on-canvas) and x ≥ 3 (well within
# the canvas) -- nothing gets clipped at any fall angle.
PIVOT = (BUDDY_OFF_X, BUDDY_OFF_Y + BUDDY_H - 1)  # (26, 33)

# --- Poses ----------------------------------------------------------------
# Legend for all pose grids (matches the idle / worry / smile builds):
#   .  transparent
#   D  DEEP
#   M  MID
#   L  LIGHT
#   P  PUPIL

# REST pose -- verbatim from idle-breathing so the icon state starts on
# the exact same silhouette the user is looking at when they arrive.
REST_ROWS = [
    "....MM............MM....",  #  0  antennae (both MID, matches idle)
    "....MM............MM....",  #  1
    "......MM........MM......",  #  2
    "......MM........MM......",  #  3
    "........MM....MM........",  #  4
    "........MM....MM........",  #  5
    "..........DDMM..........",  #  6  head tip -- DEEP shadow starts here
    "..........DDMM..........",  #  7
    "........DDMMLLLL........",  #  8
    "........DDMMLLLL........",  #  9
    "......DDMMLLLLLLLL......",  # 10
    "......DDMMLLLLLLLL......",  # 11
    "....DDMMLLLLLLLLLLLL....",  # 12
    "....DDMMLLLLLLLLLLLL....",  # 13
    "..DDMMLLLLLLLLLLLLLLLL..",  # 14
    "..DDMMLLLLLLLLLLLLLLLL..",  # 15
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # 16  pupils (open)
    "DDMMMMLLLLPPLLLLPPLLLLLL",  # 17
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 18
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 19
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 20
    "DDMMMMLLLLLLLLLLLLLLLLLL",  # 21
    "..DDMMMMMMLLLLLLLLLLLL..",  # 22  base
    "..DDMMMMMMLLLLLLLLLLLL..",  # 23
]

# ICON pose -- the buddy laying down / "back turned" as the VS Code
# app icon. Pixel-for-pixel from the Figma reference (24×24).
# Body sits on the right half of the sprite; the antenna trail
# reaches the left edge as the classic VS Code diagonal shadow, and
# the black "eye" cluster in the centre is the icon's chevron mark.
ICON_ROWS = [
    "................DDDDDD..",  #  0
    "................DDDDDD..",  #  1
    "..............DDMMMMMMDD",  #  2
    "..............DDMMMMMMDD",  #  3
    "DD..........DDMMMMMMMMMM",  #  4  antenna-tip trailing off left
    "DD..........DDMMMMMMMMMM",  #  5
    "..DD......DDMMLLLLLLLLMM",  #  6
    "..DD......DDMMLLLLLLLLMM",  #  7
    "....DD..DDMMLLLLLLLLLLMM",  #  8
    "....DD..DDMMLLLLLLLLLLMM",  #  9
    "......DDMMLLLLLPPPPLLLLL",  # 10  chevron mark (VS Code >)
    "......DDMMLLLLLPPPPLLLLL",  # 11
    "......MMLLLLLPPPPPPLLLLL",  # 12
    "......MMLLLLLPPPPPPLLLLL",  # 13
    "....MM..LLLLLLLPPPPLLLLL",  # 14
    "....MM..LLLLLLLPPPPLLLLL",  # 15
    "..MM......LLLLLLLLLLLLLL",  # 16
    "..MM......LLLLLLLLLLLLLL",  # 17
    "MM..........LLLLLLLLLLLL",  # 18
    "MM..........LLLLLLLLLLLL",  # 19
    "..............LLLLLLLLLL",  # 20
    "..............LLLLLLLLLL",  # 21
    "................LLLLLL..",  # 22  base sits on ground row
    "................LLLLLL..",  # 23
]

CHAR_TO_SLOT = {
    "D": "DEEP",
    "M": "MID",
    "L": "LIGHT",
    "P": "PUPIL",
}


def rasterize(rows, palette, size):
    """Render an ASCII grid to an RGBA image of the given (w, h) size."""
    w, h = size
    assert len(rows) == h, f"grid must have {h} rows, got {len(rows)}"
    img = Image.new("RGBA", size, BG)
    px = img.load()
    for y, row in enumerate(rows):
        assert len(row) == w, f"row {y} must be {w} wide, got {len(row)}"
        for x, ch in enumerate(row):
            slot = CHAR_TO_SLOT.get(ch)
            if slot is not None:
                px[x, y] = palette[slot]
    return img


def place_in_frame(pose_24, offset=(BUDDY_OFF_X, BUDDY_OFF_Y)):
    """Paste a 24×24 pose into a fresh FRAME_W×FRAME_H canvas at the
    standing position. Returns the framed image."""
    frame = Image.new("RGBA", (FRAME_W, FRAME_H), BG)
    frame.paste(pose_24, offset, pose_24)
    return frame


def rotate_around(img, angle_deg, pivot):
    """Rotate img counter-clockwise by angle_deg around pivot (px, py).
    Returns a same-size image with nearest-neighbour resampling so
    pixel-art hard edges are preserved."""
    w, h = img.size
    # Place img on a canvas ~3× as large so the rotation has room; put
    # the pivot at that canvas's centre, rotate, then crop so pivot
    # stays at the same location in the output.
    big = Image.new("RGBA", (w * 3, h * 3), BG)
    cx, cy = big.size[0] // 2, big.size[1] // 2
    px, py = pivot
    big.paste(img, (cx - px, cy - py), img)
    rotated = big.rotate(angle_deg, resample=Image.NEAREST, expand=False)
    left = cx - px
    top = cy - py
    return rotated.crop((left, top, left + w, top + h))


def build_frames(palette):
    """Return the list of (PIL.Image RGBA FRAME_W×FRAME_H, delay_ms)
    tuples for a one-shot (non-looping) animation."""
    # 24×24 pose rasters.
    rest_24 = rasterize(REST_ROWS, palette, (BUDDY_W, BUDDY_H))
    icon_24 = rasterize(ICON_ROWS, palette, (BUDDY_W, BUDDY_H))

    # Framed poses on the wider FRAME_W × FRAME_H canvas.
    rest = place_in_frame(rest_24)
    # Icon pose is anchored to the LEFT half so the antenna trail
    # reaches the left edge and the round body sits above the ground
    # row. offset x=2 gives a 2 px left margin; y=BUDDY_OFF_Y keeps
    # the base on the ground line.
    icon = place_in_frame(icon_24, offset=(2, BUDDY_OFF_Y))

    fall_angles = (25, 50, 72, 90)

    frames = []

    # 0-13 (14 * 90 = 1260 ms): slow idle rest, upright, front.
    for _ in range(14):
        frames.append((rest, 90))

    # 14-17 (4 * 130 = 520 ms): tip over to the left, ending at 90°
    # -- the buddy is now flat on his side with his FACE still
    # visible (this is just REST rotated 90° CCW).
    for a in fall_angles:
        frames.append((rotate_around(rest, a, PIVOT), 130))

    # 18-20 (3 * 280 = 840 ms): PAUSE laying down with the face
    # still visible. The buddy is fallen but hasn't turned yet --
    # this beat gives the viewer time to register that he's down
    # before he flips to show his back.
    fallen_front = rotate_around(rest, 90, PIVOT)
    for _ in range(3):
        frames.append((fallen_front, 280))

    # 21 (1 * 30_000 ms): TURN. Instantaneous swap to the VS Code
    # app icon pose from the Figma reference -- his BACK is now
    # facing the viewer, with the black chevron mark (the "tail")
    # visible on his back. He stays down; he does NOT stand back
    # up. The huge delay keeps the pose on screen even if a player
    # ignores --no-loopcount.
    frames.append((icon, 30_000))

    return frames


def write_gif(frames_ms, palette, out_path):
    """Write a looping transparent GIF via gifsicle for exact per-frame
    delays (Pillow's animated-GIF writer is unreliable with
    transparency)."""
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
                    c = src_pixels[x, y]
                    # Rotation can leave alpha=0 pixels with any RGB
                    # value -- treat anything not fully opaque as
                    # background so we don't smear stray colours.
                    if c[3] < 128:
                        idx_pixels[x, y] = 0
                    else:
                        idx_pixels[x, y] = color_to_index.get(
                            (c[0], c[1], c[2], 255), 0
                        )
            idx.info["transparency"] = 0
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(p)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        # `--no-loopcount` strips the NETSCAPE looping extension so
        # browsers play the animation once and freeze on the final
        # frame. The final frame's 30-second delay is belt-and-braces
        # for the small number of players that ignore that.
        args = ["gifsicle", "--no-loopcount", "--no-warnings",
                "--transparent=0"]
        for path, (_frame, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def main():
    for name, palette in PALETTES.items():
        frames = build_frames(palette)
        out = os.path.join(ASSETS, f"icon-{name}.gif")
        write_gif(frames, palette, out)
        # Report duration excluding the trailing hold so the number
        # reflects how long the animation actually runs.
        active_ms = sum(d for _, d in frames[:-1])
        print(f"wrote {out}  ({len(frames)} frames, "
              f"{active_ms} ms active + {frames[-1][1]//1000}s hold, "
              f"canvas {FRAME_W}×{FRAME_H})")


if __name__ == "__main__":
    main()
