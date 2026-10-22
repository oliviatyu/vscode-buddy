#!/usr/bin/env python3
"""
Build the "coffee" state sprite for the Buddy Veee tamagotchi in the
themed VS Code blue / Insiders green palettes.

Source: Figma design node 4840:3977 in the Polish Push May-June 2026
file (fileKey lWE17f1tRRDXWsbxTcbsmo). Unlike the older
coffee-source.png (kept alongside for reference), the Figma design uses
the full 4-color themed palette -- outlines and steam are DEEP blue
rather than near-black, matching the other themed states
(sleep/cool/branch/etc.). Eye slits stay near-black.

The pixel map below is lifted directly from the Figma render (bounding
box x[5..44] y[20..43] of the 50x50 canvas), so no flood-fill / role
inference is needed. Symbols:

  L = LIGHT   -> theme light  (body highlight, coffee liquid highlight)
  M = MID     -> theme mid    (body / cup midtone)
  D = DEEP    -> theme deep   (outline, steam, cup outline)
  # = PUPIL   -> near-black   (#191a1b, eye slits only)
  . = transparent

Animation:
  Steam emerges from the coffee cup as a puff cycle, borrowing the
  same stop-motion pattern as heart-rainbow's popping heart: a hold
  (no steam), then the tip wisps appear at the cup rim, then the full
  puff (matching the original static layout), then the upper wisps
  drift up while the lower ones dissipate, then back to the hold.
  Ears, eyes, cup, and body all stay static -- only the 4 LIGHT-color
  wisp pixel-clusters flicker in and out.

Outputs:
  assets/coffee-blue.gif   (VS Code palette, animated)
  assets/coffee-green.gif  (Insiders palette, animated)

Both GIFs are 40x24 pixels, 4 stages, transparent background.

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
# reference (node 4840:3977). Green values mirror the ramp already used
# by sleep-green / cool-green / branch-green.
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

# 40x24 pixel map, lifted directly from the Figma render.
# Row 0 = top of the sprite, col 0 = left.
PIXMAP = [
    "......................DD........MM......",  # 0
    "......................DD........MM......",  # 1
    "....................DD..DD....MM..MM....",  # 2
    "....................DD..DD....MM..MM....",  # 3
    "..........................DDMM..........",  # 4
    "..........................DDMM..........",  # 5
    "........................DDMMLLLL........",  # 6
    "LL...LL.................DDMMLLLL........",  # 7
    "LL...LL...............DDMMLLLLLLLL......",  # 8
    "..LL...LL.............DDMMLLLLLLLL......",  # 9
    "..LL...LL...........DDMMLLLLLLLLLLLL....",  # 10
    "....................DDMMLLLLLLLLLLLL....",  # 11
    "..DDDDDDDDDD......DDLLLLLLLLLLLLLLLLLL..",  # 12
    "..DDDDDDDDDD......DDLLLLLLLLLLLLLLLLLL..",  # 13
    "DDLLLLLLLLLLDDDDDDMM####LLLL####LLLLLLLL",  # 14
    "DDLLLLLLLLLLDDDDDDMM####LLLL####LLLLLLLL",  # 15
    "DDLLLLLLLLLLDD..DDMMLLLLLLLLLLLLLLLLLLLL",  # 16
    "DDLLLLLLLLLLDD..DDMMLLLLLLLLLLLLLLLLLLLL",  # 17
    "DDLLLLLLLLLLDD..DDMMLLLLLLLLLLLLLLLLLLLL",  # 18
    "DDLLLLLLLLLLDD..DDMMLLLLLLLLLLLLLLLLLLLL",  # 19
    "DDLLLLLLLLLLDD....DDDDMMLLLLLLLLLLLLLL..",  # 20
    "DDLLLLLLLLLLDD....DDDDMMLLLLLLLLLLLLLL..",  # 21
    "..DDDDDDDDDD............................",  # 22
    "..DDDDDDDDDD............................",  # 23
]

W = len(PIXMAP[0])
H = len(PIXMAP)
assert all(len(row) == W for row in PIXMAP), "PIXMAP rows must all be same width"
assert (W, H) == (40, 24), f"Expected 40x24, got {W}x{H}"

SYM_TO_SLOT = {
    "L": "LIGHT",
    "M": "MID",
    "D": "DEEP",
    "#": "PUPIL",
}

# --- Animation config -------------------------------------------------
#
# The DEEP + MID curls in rows 0-5 are the character's ears (antennae)
# and MUST stay static. The actual steam is four little LIGHT-color
# 2x2 chunky wisps sitting above the coffee cup rim -- two "trails"
# (left + right), each made of a lower + upper wisp offset diagonally
# up-left so they read as a rising puff.
#
# Animation follows the same puff pattern as the heart-rainbow easter
# egg: stop-motion stages of pause -> tip appears -> grows -> rises
# -> loops. At any given stage only a SUBSET of the four wisps is
# rendered, so the steam looks like it's genuinely emerging from the
# cup rather than sliding around as a fixed shape.
#
# Wisp positions are the (x, y) top-left of each 2x2 chunky pixel:
WISPS = {
    "A_low":  (2, 9),   # left trail, lower wisp (near cup rim)
    "A_high": (0, 7),   # left trail, upper wisp (up-left of A_low)
    "B_low":  (7, 9),   # right trail, lower wisp
    "B_high": (5, 7),   # right trail, upper wisp
}

# Per-stage (active_wisp_names, delay_ms). The pause holds the longest
# so each puff feels deliberate; the emerge/grow/rise beats tick by
# quickly enough to read as popping, not sliding. Loops seamlessly:
# stage 3 (top wisps only) fades to stage 0 (nothing), which reads as
# the last of the puff dissipating before a fresh one starts.
STAGES = [
    # (active wisps, delay in milliseconds)
    # Real coffee steam rises slowly and lingers -- each beat holds
    # long enough to read as a gentle drifting curl rather than a
    # snappy pop.
    ((),                                     1200),  # 0: pause -- no steam
    (("A_low", "B_low"),                      450),  # 1: tips emerge at cup rim
    (("A_low", "A_high", "B_low", "B_high"),  550),  # 2: full puff (matches original layout)
    (("A_high", "B_high"),                    650),  # 3: puff rises, lower wisps have drifted up + dissipated
]

# Every wisp pixel that appears in ANY stage. Used to omit these
# 16 coordinates from the base layer so the per-stage steam layer can
# repaint them fresh without leaving artifacts.
STEAM_COORDS = frozenset(
    (wx + dx, wy + dy)
    for (wx, wy) in WISPS.values()
    for dx in (0, 1) for dy in (0, 1)
)


def render_layers(palette):
    """Split the sprite into (base, wisp_images).

    - base:  the full character + cup + ears + eyes, with the 16
             wisp pixels omitted so per-stage wisp layers can be
             pasted on top without leaving artifacts.
    - wisp_images: dict mapping wisp name -> RGBA image (40x24) with
             only that wisp's 4 pixels colored (rest transparent).

    All images are 40x24."""
    LIGHT = palette["LIGHT"]
    base = Image.new("RGBA", (W, H), BG)
    bpx = base.load()
    for y, row in enumerate(PIXMAP):
        for x, sym in enumerate(row):
            slot = SYM_TO_SLOT.get(sym)
            if slot is None:
                continue
            if (x, y) in STEAM_COORDS:
                continue  # wisps are painted per-stage on top
            bpx[x, y] = palette[slot]

    wisp_images = {}
    for name, (wx, wy) in WISPS.items():
        wimg = Image.new("RGBA", (W, H), BG)
        wpx = wimg.load()
        for dx in (0, 1):
            for dy in (0, 1):
                wpx[wx + dx, wy + dy] = LIGHT
        wisp_images[name] = wimg
    return base, wisp_images


def build_frames(palette):
    """Compose one RGBA frame per STAGE. Returns a list of (frame,
    delay_ms) tuples so the caller can hand per-frame delays to
    gifsicle -- same shape as build_rainbow.py's heart-rainbow."""
    base, wisp_images = render_layers(palette)

    frames = []
    for active_wisps, delay_ms in STAGES:
        f = Image.new("RGBA", (W, H), BG)
        f.paste(base, (0, 0), base)
        for name in active_wisps:
            wisp = wisp_images[name]
            f.paste(wisp, (0, 0), wisp)
        frames.append((f, delay_ms))
    return frames


def render(palette):
    """Kept for backwards compatibility with any callers that want a
    single still frame -- returns the "full puff" stage so the still
    matches the original coffee.gif layout."""
    base, wisp_images = render_layers(palette)
    out = base.copy()
    for wisp in wisp_images.values():
        out.paste(wisp, (0, 0), wisp)
    return out


def write_animated_gif(frames_ms, out_path, palette):
    """Write a multi-frame transparent GIF via gifsicle with per-frame
    delays (frames_ms is a list of (PIL Image, delay_ms) tuples).
    gifsicle preserves the transparent index exactly, which Pillow's
    own GIF writer sometimes bakes to background."""
    fw, fh = frames_ms[0][0].size
    # Fixed slot order so the palette indices are stable across writes.
    opaque = [palette["PUPIL"], palette["DEEP"], palette["MID"], palette["LIGHT"]]
    pal_bytes = [0, 0, 0]  # index 0 = transparent slot
    for r, g, b, _a in opaque:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {
        BG: 0,
        palette["PUPIL"]: 1,
        palette["DEEP"]:  2,
        palette["MID"]:   3,
        palette["LIGHT"]: 4,
    }

    with tempfile.TemporaryDirectory() as tmp:
        frame_paths = []
        for i, (frame, _delay) in enumerate(frames_ms):
            idx = Image.new("P", (fw, fh), 0)
            idx.putpalette(pal_bytes)
            src_px = frame.load()
            idx_px = idx.load()
            for y in range(fh):
                for x in range(fw):
                    idx_px[x, y] = color_to_index.get(src_px[x, y], 0)
            idx.info["transparency"] = 0
            fp = os.path.join(tmp, f"f{i:02d}.gif")
            idx.save(fp, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(fp)

        args = ["gifsicle", "--no-warnings", "--loopcount=0", "--transparent=0"]
        for path, (_, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def main():
    for variant, palette in PALETTES.items():
        frames_ms = build_frames(palette)
        out_path = os.path.join(ASSETS, f"coffee-{variant}.gif")
        write_animated_gif(frames_ms, out_path, palette)
        fw, fh = frames_ms[0][0].size
        delays = [d for _, d in frames_ms]
        print(f"Wrote {out_path} ({fw}x{fh}, {len(frames_ms)} frames, delays_ms={delays})")


if __name__ == "__main__":
    main()
