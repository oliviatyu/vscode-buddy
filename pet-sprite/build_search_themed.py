#!/usr/bin/env python3
"""
Build the "search" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Source: Figma design node 4840:4130 in the Polish Push May-June 2026
file (fileKey lWE17f1tRRDXWsbxTcbsmo). The buddy is stretched into a
wide "peering / scanning" pose -- lower/wider body, wide-set 2x2
pupils, and a cluster of sparkle antennae rising up from the head
(mirrored DEEP/LIGHT pair on either side of a central spine).

The REST_ROWS pixel map below is lifted straight from the Figma
render (bounding box x[13..36] y[22..43] of the 50x50 canvas) so no
runtime parsing is needed -- the design lives in code as a 24x24
grid. Symbols:

  L = LIGHT       -> theme light  (body highlight, right-side sparkles)
  M = MID         -> theme mid    (body fill / cheek plate)
  D = DEEP        -> theme deep   (outline / left-side sparkles)
  P = PUPIL       -> near-black   (#191a1b, eye pupils)
  . = transparent

Animation:
  The buddy is SEARCHING -- scanning left/right. Only the two 2x2
  pupils move; everything else (body, sparkle antennae, chin bar)
  stays static. Four-frame loop at 500ms/frame = 2000 ms cycle:

    Frame 0 (500ms):  eyes CENTER  (rest, matches Figma design)
    Frame 1 (500ms):  eyes RIGHT   (both pupils shift +1px)
    Frame 2 (500ms):  eyes CENTER  (back to rest)
    Frame 3 (500ms):  eyes LEFT    (both pupils shift -1px)

  The eye sockets sit inside a solid MID cheek plate (cols 0-23 of
  rows 14-15) so pupils can slide 1px in either direction without
  crossing any other feature.

Outputs:
  assets/search-blue.gif   (VS Code palette,   24x24, 4 frames)
  assets/search-green.gif  (Insiders palette,  24x24, 4 frames)

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Themed palettes. Blue values are lifted straight from the Figma
# reference (node 4840:4130). Green values mirror the ramp already
# used by sleep-green / cool-green / branch-green / coffee-green.
PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),   # #23a8f2
        "MID":   (0, 119, 184, 255),    # #0077b8
        "DEEP":  (0,  78, 124, 255),    # #004e7c
        "PUPIL": (25,  26,  27, 255),   # #191a1b
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),   # #24bfa5
        "MID":   (0, 154, 124, 255),    # #009a7c
        "DEEP":  (0, 100,  81, 255),    # #006451
        "PUPIL": (25,  26,  27, 255),   # #191a1b
    },
}

W = H = 24
OUT_FRAME_MS = 500


# --- Rest pose (eyes centered, matches Figma exactly) ------------------
#
# Rows 2-9 are the sparkle antennae rising up from the head; the DEEP
# sparkles on the LEFT and LIGHT sparkles on the RIGHT are the intended
# directional shading (light source coming from top-right) -- NOT a
# twinkle -- so they stay static across frames.
#
# Rows 10-23 are the wide, stretched body. The 2x2 pupils at rows 14-15
# sit at cols 5-6 (left eye) and cols 18-19 (right eye) in the rest
# pose. They are the ONLY thing that changes across frames.

REST_ROWS = [
    "........................",  # 0
    "........................",  # 1
    "......DD........LL......",  # 2   outer sparkle tips
    "......DD........LL......",  # 3
    "....DD..DD....LL..LL....",  # 4   outer sparkle spread
    "....DD..DD....LL..LL....",  # 5
    "..........DDLL..........",  # 6   central spine tip
    "..........DDLL..........",  # 7
    "........DDLLLLLL........",  # 8   central spine base
    "........DDLLLLLL........",  # 9
    "..MMMMMMLLLLLLLLMMMMMM..",  # 10  top of head
    "..MMMMMMLLLLLLLLMMMMMM..",  # 11
    "MMMMMMMMMMLLLLMMMMMMMMMM",  # 12  head widens
    "MMMMMMMMMMLLLLMMMMMMMMMM",  # 13
    "MMMMMPPMMMMMMMMMMMMPPMMM",  # 14  eye plate + centered pupils
    "MMMMMPPMMMMMMMMMMMMPPMMM",  # 15
    "MMMMMMMMMMLLLLMMMMMMMMMM",  # 16
    "MMMMMMMMMMLLLLMMMMMMMMMM",  # 17
    "DDMMMMMMLLLLLLLLMMMMMMDD",  # 18
    "DDMMMMMMLLLLLLLLMMMMMMDD",  # 19
    "DDLLLLLLLLLLLLLLLLLLLLDD",  # 20  belly bar
    "DDLLLLLLLLLLLLLLLLLLLLDD",  # 21
    "..DDDDDDDDDDDDDDDDDDDD..",  # 22  chin bar
    "..DDDDDDDDDDDDDDDDDDDD..",  # 23
]

SYM_TO_SLOT = {
    "L": "LIGHT",
    "M": "MID",
    "D": "DEEP",
    "P": "PUPIL",
}

# 2x2 pupil top-left positions in the REST pose. Both eyes shift
# together across the four scan frames.
PUPIL_ROW_TOP = 14           # pupils occupy rows 14-15
LEFT_PUPIL_REST_X = 5        # left eye pupil at cols 5-6
RIGHT_PUPIL_REST_X = 18      # right eye pupil at cols 18-19

# Per-frame pupil shift in pixels (applied to BOTH eyes).
SCAN_SHIFTS = [0, +1, 0, -1]  # center, right, center, left


# --- Rendering ---------------------------------------------------------

def render_base(palette):
    """Render the rest pose WITHOUT pupils -- the 4 pupil cells are
    left as their underlying MID cheek plate so per-frame pupil
    overlays can be pasted cleanly."""
    im = Image.new("RGBA", (W, H), BG)
    px = im.load()
    for y, row in enumerate(REST_ROWS):
        assert len(row) == W, f"row {y} has {len(row)} chars, expected {W}"
        for x, sym in enumerate(row):
            slot = SYM_TO_SLOT.get(sym)
            if slot is None:
                continue
            if sym == "P":
                # Underlying cheek plate is MID everywhere the pupils sit.
                px[x, y] = palette["MID"]
            else:
                px[x, y] = palette[slot]
    return im


def stamp_pupils(base_im, shift, palette):
    """Return a copy of base_im with both 2x2 pupils painted at
    (rest_x + shift, PUPIL_ROW_TOP)."""
    out = base_im.copy()
    px = out.load()
    pupil = palette["PUPIL"]
    for eye_x in (LEFT_PUPIL_REST_X, RIGHT_PUPIL_REST_X):
        x0 = eye_x + shift
        for dx in (0, 1):
            for dy in (0, 1):
                cx = x0 + dx
                cy = PUPIL_ROW_TOP + dy
                if 0 <= cx < W and 0 <= cy < H:
                    px[cx, cy] = pupil
    return out


def build_frames(palette):
    """Return the 4-frame scan sequence for a palette."""
    base = render_base(palette)
    return [stamp_pupils(base, shift, palette) for shift in SCAN_SHIFTS]


def write_gif(frames, palette, out_path):
    """Assemble a multi-frame transparent GIF via gifsicle so per-frame
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
        for i, frame in enumerate(frames):
            idx = Image.new("P", (W, H), 0)
            idx.putpalette(pal_bytes)
            src = frame.load()
            dst = idx.load()
            for y in range(H):
                for x in range(W):
                    dst[x, y] = color_to_index.get(src[x, y], 0)
            p = os.path.join(tmp, f"f{i:03d}.gif")
            idx.save(p, "GIF", transparency=0, disposal=2)
            frame_paths.append(p)

        delay_cs = OUT_FRAME_MS // 10  # 500 ms -> 50 cs
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cmd = [
            "gifsicle",
            "--loopcount=0",
            "--no-warnings",
            "--disposal=background",
            "--transparent=0",
            f"--delay={delay_cs}",
            "--output", out_path,
        ] + frame_paths
        subprocess.run(cmd, check=True)


def main():
    for name, palette in PALETTES.items():
        out_path = os.path.join(ASSETS, f"search-{name}.gif")
        frames = build_frames(palette)
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({W}x{H}, {len(frames)} frames, "
              f"{len(frames) * OUT_FRAME_MS} ms loop)")


if __name__ == "__main__":
    main()
