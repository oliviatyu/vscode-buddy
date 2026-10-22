#!/usr/bin/env python3
"""
Bake the "rainbow" and "heart rainbow" tamagotchi sprites from Figma
into single-frame transparent GIFs.

Sources (file lWE17f1tRRDXWsbxTcbsmo, "Polish Push May–June 2026"):
  - rainbow:       node 4840:2239   (creature only)
  - heart-rainbow: node 4840:2944   (creature + floating heart, mouth open)

Both Figma nodes are 50x50 canvases painted with 2x2 pixel blocks, so
the native buddy is only 12 wide × 11 tall. To match the visual size
of the other 24x24 buddies (smile, idle, cool, etc.), we 2x-upscale
the body and pad it to 24x24 — that matches the intent of the Figma
source (each design pixel is a 2x2 block) and gives us a 24x24 rainbow
buddy. The heart-rainbow variant reuses that same 24x24 body but with
a wider eye spacing + open smile mouth, and stacks the heart accessory
OUTSIDE the body canvas (same pattern as coffee / sing / speak) so the
buddy is never squeezed.

Outputs:
  assets/rainbow.gif        (24x24, 7 frames, stop-motion — base-blue
                             buddy with a diagonal rainbow shine that
                             sweeps across his body at 45° up-right,
                             one colour-width per frame)
  assets/heart-rainbow.gif  (24x40, 6 frames, stop-motion — heart pops
                             out of the buddy's head, growing from a
                             single pixel to a full-size heart while
                             rising, then holds on the full heart)

The rainbow theme is NOT re-tinted for VS Code / Insiders — one shared
PNG per state is enough (matches the `complete` and `search` states
which also ship only one variant).

Palette lifted verbatim from the Figma export (spectral colours are
now used as the SHINE overlay, not the static body fill; the base body
is 3-tone blue, matching smile-blue / sleep-blue / cool-blue):
  R  #FF000B  red         (antennas + heart + shine)
  O  #FFA700  orange      (crown + shine)
  Y  #FFF200  yellow      (shine)
  G  #00FF61  green       (shine)
  C  #00CCFF  cyan        (shine)
  B  #008CFF  blue        (shine)
  P  #B200FF  purple      (shine)
  #  #191A1B  near-black  (eyes + mouth)
  L  #23A8F2  light-blue  (body highlight — base tone under shine)
  M  #0077B8  mid-blue    (body midtone — base tone under shine)
  D  #004E7C  deep-blue   (body outline — base tone under shine)

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BG = (0, 0, 0, 0)

# Ordered palette. Index 0 is transparent; 1..N map to CHAR_TO_COLOR below.
# gifsicle wants the transparent index first so the disposal + transparency
# flags line up.
PALETTE_ORDER = [
    ("R", (255,   0,  11, 255)),
    ("O", (255, 167,   0, 255)),
    ("Y", (255, 242,   0, 255)),
    ("G", (  0, 255,  97, 255)),
    ("C", (  0, 204, 255, 255)),
    ("B", (  0, 140, 255, 255)),
    ("P", (178,   0, 255, 255)),
    ("#", ( 25,  26,  27, 255)),
    # Base blue body tones (used when the rainbow shine is NOT overhead).
    ("L", ( 35, 168, 242, 255)),  # highlight  #23a8f2
    ("M", (  0, 119, 184, 255)),  # midtone    #0077b8
    ("D", (  0,  78, 124, 255)),  # deep       #004e7c
]
CHAR_TO_COLOR = {ch: rgba for ch, rgba in PALETTE_ORDER}

# Body pixels in RAINBOW_NATIVE (the shape source) are the ones that
# the diagonal shine sweeps across. Everything except the eyes gets the
# shine — antennas (tip of head), crown / ears, and body all shimmer
# together so the rainbow reads as light passing over the WHOLE buddy,
# not just his belly. Only the eyes stay near-black so he keeps eye
# contact through the animation.
BODY_CHARS = frozenset("ROYGCBP")
BODY_CHAR_TO_BASE = {
    "R": CHAR_TO_COLOR["L"],  # antenna (was red)     → LIGHT
    "O": CHAR_TO_COLOR["L"],  # crown / ears          → LIGHT
    "Y": CHAR_TO_COLOR["L"],  # yellow was brightest  → LIGHT
    "C": CHAR_TO_COLOR["L"],  # cyan was highlight    → LIGHT
    "G": CHAR_TO_COLOR["M"],  # green mid             → MID
    "B": CHAR_TO_COLOR["M"],  # blue mid              → MID
    "P": CHAR_TO_COLOR["D"],  # purple darkest        → DEEP
}

# Ordered spectrum for the diagonal shine (ROYGBIV). Each entry paints
# a 2-native-pixel-wide diagonal band; the whole 14-native-pixel-wide
# rainbow slides up-right across the buddy in stop-motion frames.
RAINBOW_SHINE_COLORS = [
    CHAR_TO_COLOR["R"],
    CHAR_TO_COLOR["O"],
    CHAR_TO_COLOR["Y"],
    CHAR_TO_COLOR["G"],
    CHAR_TO_COLOR["C"],
    CHAR_TO_COLOR["B"],
    CHAR_TO_COLOR["P"],
]
# 2 native pixels per colour × 7 colours = 14-native-pixel cycle.
# Advancing SHINE_STEP == SHINE_BAND per frame shifts the pattern by
# exactly one whole colour each tick — that's the deliberate stop-motion
# "jump", no half-steps. 7 frames covers one full cycle and loops.
SHINE_BAND = 2
SHINE_STEP = 2
SHINE_FRAMES = (SHINE_BAND * len(RAINBOW_SHINE_COLORS)) // SHINE_STEP  # 7
SHINE_DELAY_MS = 160

# Native (pre-upscale) content grids, tight-cropped to bounding box.
# Legend above. `.` = transparent. Each character is one native design
# pixel; the whole thing is 2x-upscaled before writing so 1 char = 2x2
# output pixels. That matches how the Figma source was painted.
#
# rainbow: 12 wide × 11 tall (native) → 24x22 after 2x upscale → padded
# to 24x24 with 1 transparent row above + 1 below so the buddy stays
# vertically centred and matches the other 24x24 tamagotchi sprites.
#
# heart-rainbow: 12 wide × 18 tall (native) → 24x36 after 2x upscale.
# The buddy sits at the bottom (same rows as `rainbow`) and the heart
# extends above it so the sprite frame grows upward, not around.

RAINBOW_NATIVE = [
    "...R....R...",  # antenna tops
    "..R.R..R.R..",  # antenna bases
    ".....OO.....",  # crown
    "....OOOO....",  # crown
    "...CCGYYY...",  # body top
    "..BCCGGYYY..",
    ".PBBCGGGYYY.",
    "PPBBC#CG#GYY",  # eyes (#)
    "PPBBB#CC#GGG",
    "PPPBBBBBCCCG",
    ".PPPPBBBCCC.",
]

# heart-rainbow body: same rainbow palette + antennas + crown, but with
# a wider eye spacing and an open smile mouth (matches Figma node
# 4840:2944). This is composed as a standalone 12x11 grid so it can be
# 2x-upscaled + padded to 24x24 identically to the plain rainbow body,
# then the heart is pasted ABOVE that 24x24 canvas — same pattern as
# coffee / sing / speak, where the accessory extends the canvas rather
# than compressing the buddy.

HEART_BODY_NATIVE = [
    "...R....R...",  # antenna tops
    "..R.R..R.R..",  # antenna bases
    ".....OO.....",  # crown
    "....OOOO....",
    "...CCGYYY...",  # body top
    "..BCCGGYYY..",
    ".PBB#GG#YYY.",  # eye tops at cols 4 & 7 — symmetric around col 5.5
    "PPBBCCCGGGYY",
    "PPB#CCCG#GGG",  # smile upturned corners at cols 3 & 8 (moved out from cols 4 & 7)
    "PPPB####CCCG",  # open mouth (#### at cols 4–7 → symmetric around col 5.5)
    ".PPPPBBBCCC.",
]

# TOP-row eye pixels for the heart-rainbow buddy in native coordinates.
# Blinking replaces just these pixels with the body colour directly
# beneath them (row+1, same col), leaving the row-8 pupil pixel visible
# as a bottom slit — the same idle-blink pattern as build_idle_breathing.
HEART_EYE_TOP_NATIVE = [(4, 6), (7, 6)]

# Stop-motion animation stages for heart-rainbow. Each stage is a
# native 12-wide grid (variable height) plus a y_offset saying where
# the top of the grid sits inside the 8-native-row heart region above
# the buddy. The heart both GROWS (top expands upward) and RISES (tip
# lifts 2 native pixels from the buddy's head to its final resting
# spot).
#
# Heart region layout (8 native rows = 16 rendered rows tall):
#   row 0 = top of canvas
#   row 7 = touches buddy top (antenna tips)
HEART_STAGES = [
    # (grid, y_offset_native)
    # Stage 0: buddy alone (empty heart region — the breath pause)
    ([], 0),
    # Stage 1: single tip pixel emerging from buddy's head
    ([
        "......R.....",
    ], 7),
    # Stage 2: 2-row bud (tip still at buddy head — starts to grow)
    ([
        ".....R.R....",
        "......R.....",
    ], 6),
    # Stage 3: 3-row small heart (rises 1 native row; tip at row 6)
    ([
        ".....R.R....",
        ".....RRR....",
        "......R.....",
    ], 4),
    # Stage 4: 5-row medium heart (rises another native row; tip at row 5)
    ([
        "....RR.RR...",
        "...RRRRRRR..",
        "....RRRRR...",
        ".....RRR....",
        "......R.....",
    ], 1),
    # Stage 5: full 6-row heart, settled at top of canvas (tip at row 5)
    ([
        "....RR.RR...",
        "...RRRRRRR..",
        "...RRRRRRR..",
        "....RRRRR...",
        ".....RRR....",
        "......R.....",
    ], 0),
]

# Per-frame delays in ms. Longer holds on the pause + final beats give
# the sequence a deliberate stop-motion feel; the growth steps in the
# middle tick by quickly enough to read as "popping" not sliding.
HEART_TIMELINE_MS = [
    500,   # stage 0 — buddy alone
    120,   # stage 1 — tip appears
    120,   # stage 2 — bud
    140,   # stage 3 — small heart, first rise
    140,   # stage 4 — medium heart, second rise
    900,   # stage 5 — full heart, hold before looping
]
assert len(HEART_TIMELINE_MS) == len(HEART_STAGES)

# Heart region height (native rows) above the buddy body. Chosen so the
# fully-grown heart (6 native rows) fits with 2 native rows of breathing
# room between its tip and the buddy's antennae.
HEART_REGION_NATIVE_H = 8

# Upscale factor: each native pixel becomes SCALE×SCALE output pixels.
SCALE = 2


def rasterize_native(grid):
    """Render a native-resolution grid to an RGBA image (no upscale)."""
    h = len(grid)
    w = len(grid[0]) if grid else 0
    img = Image.new("RGBA", (w, h), BG)
    px = img.load()
    for y, row in enumerate(grid):
        assert len(row) == w, f"row {y} must be {w} wide, got {len(row)}"
        for x, ch in enumerate(row):
            color = CHAR_TO_COLOR.get(ch)
            if color is None:
                continue
            px[x, y] = color
    return img


def upscale(img, scale):
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def pad_to(img, target_w, target_h):
    """Pad transparent margins so the buddy sits centred in the target
    canvas. If the image is already larger than the target, returns it
    unchanged."""
    if img.width >= target_w and img.height >= target_h:
        return img
    canvas = Image.new("RGBA", (max(img.width, target_w), max(img.height, target_h)), BG)
    off_x = (canvas.width - img.width) // 2
    off_y = (canvas.height - img.height) // 2
    canvas.paste(img, (off_x, off_y), img)
    return canvas


def blink_body_grid(grid, eye_top_positions):
    """Return a copy of a native list-of-strings body grid with the
    given (col, row) eye-top pixels replaced by the body colour of the
    pixel directly below (row+1, same col). Mirrors the idle blink:
    the top pupil pixel becomes body-fill, leaving the row-below pupil
    pixel visible as a slit."""
    rows = [list(r) for r in grid]
    for x, y in eye_top_positions:
        below = grid[y + 1][x]
        assert below not in ("#", "."), (
            f"pixel below eye ({x},{y}) is '{below}', can't blink"
        )
        rows[y][x] = below
    return ["".join(r) for r in rows]


def write_gif(frames_ms, out_path):
    """Write a transparent GIF via gifsicle (Pillow's writer sometimes
    drops the transparent index / bakes background between frames).

    frames_ms accepts either:
      * a single PIL Image → written as a 1-frame static GIF.
      * a list of (PIL Image, delay_ms) tuples → written as an animated
        GIF looping forever with per-frame delays and background
        disposal so transparent pixels genuinely stay transparent.
    All frames in a multi-frame sequence must share the same dimensions.
    """
    if isinstance(frames_ms, Image.Image):
        frames_ms = [(frames_ms, 100)]
    assert frames_ms, "need at least one frame"

    first_size = frames_ms[0][0].size
    for frame, _ in frames_ms:
        assert frame.size == first_size, "all frames must share dimensions"

    pal_bytes = [0, 0, 0]  # index 0 = transparent placeholder
    for _ch, (r, g, b, _a) in PALETTE_ORDER:
        pal_bytes.extend([r, g, b])
    pal_bytes.extend([0] * (256 * 3 - len(pal_bytes)))

    color_to_index = {BG: 0}
    for i, (_ch, rgba) in enumerate(PALETTE_ORDER, start=1):
        color_to_index[rgba] = i

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
        args = [
            "gifsicle",
            "--loopcount=0",
            "--no-warnings",
            "--transparent=0",
        ]
        for path, (_, delay_ms) in zip(frame_paths, frames_ms):
            centis = max(1, round(delay_ms / 10))
            args += [f"--delay={centis}", "--disposal=background", path]
        args += ["--output", out_path]
        subprocess.run(args, check=True)


def build_rainbow_shine_frames():
    """Build stop-motion frames of the rainbow buddy with a 45\u00b0-diagonal
    rainbow shine sweeping over his body.

    Motion vector is (+1, -1) in screen coords \u2014 up-right at 45\u00b0. Bands
    are therefore constant along `x - y` (they run NW\u2192SE visually), and
    the pattern shifts by SHINE_STEP native pixels along `+ (x - y)`
    per frame. With SHINE_STEP == SHINE_BAND, each frame jumps the whole
    rainbow by exactly one colour \u2014 that's the intentional stop-motion
    chunkiness (no interpolated slide).

    Body pixels always show a rainbow colour every frame; only the eyes
    are unaffected. BODY_CHAR_TO_BASE exists as a fallback (and is added
    to the palette) so the underlying blue base is available if the
    shine is ever masked to a narrower band later.
    """
    native_w = len(RAINBOW_NATIVE[0])
    native_h = len(RAINBOW_NATIVE)
    n_colors = len(RAINBOW_SHINE_COLORS)

    frames = []
    for t in range(SHINE_FRAMES):
        native = Image.new("RGBA", (native_w, native_h), BG)
        px = native.load()
        for y, row in enumerate(RAINBOW_NATIVE):
            for x, ch in enumerate(row):
                if ch == ".":
                    continue
                if ch in BODY_CHARS:
                    # Phase along the up-right motion axis. Subtracting
                    # t * SHINE_STEP makes the pattern advance in the
                    # +(x - y) direction over time, i.e., toward the
                    # top-right of the canvas.
                    phase = (x - y) - t * SHINE_STEP
                    idx = (phase // SHINE_BAND) % n_colors
                    px[x, y] = RAINBOW_SHINE_COLORS[idx]
                else:
                    px[x, y] = CHAR_TO_COLOR[ch]
        padded = pad_to(upscale(native, SCALE), 24, 24)
        frames.append((padded, SHINE_DELAY_MS))
    return frames


def render_heart_stage(stage_grid, y_offset_native):
    """Render one heart stage into a 24 × (HEART_REGION_NATIVE_H*SCALE)
    rendered image. `stage_grid` is a native-resolution list of rows
    (may be empty for the "no heart" stage). `y_offset_native` is the
    native-row index in the heart region where the TOP row of the stage
    should land."""
    canvas = Image.new(
        "RGBA",
        (12 * SCALE, HEART_REGION_NATIVE_H * SCALE),
        BG,
    )
    if not stage_grid:
        return canvas
    stage_img = upscale(rasterize_native(stage_grid), SCALE)
    canvas.paste(stage_img, (0, y_offset_native * SCALE), stage_img)
    return canvas


def main():
    # rainbow: 7-frame stop-motion of a diagonal rainbow shine sweeping
    # up-right across a base-blue buddy body. One full colour-width
    # jump per frame (no interpolation) for a chunky stop-motion feel.
    rainbow_frames = build_rainbow_shine_frames()
    rainbow_out = os.path.join(ASSETS, "rainbow.gif")
    write_gif(rainbow_frames, rainbow_out)
    total_ms = sum(delay for _, delay in rainbow_frames)
    print(
        f"Wrote {rainbow_out} (24x24, "
        f"{len(rainbow_frames)} frames, {total_ms}ms loop)"
    )

    # heart-rainbow: 24-wide canvas, 16 rendered rows of heart region on
    # top of the same 24x24 buddy sprite that `rainbow.gif` uses (with the
    # heart-variant eyes + open smile mouth). Six stop-motion stages:
    # buddy alone → tip → bud → small → medium → full-heart hold.
    # During the full-heart hold we do an idle-style eye blink: split the
    # 900ms rest into open (400ms) → blinked (160ms) → open (340ms) so the
    # total loop length stays 1920ms.
    heart_body = pad_to(upscale(rasterize_native(HEART_BODY_NATIVE), SCALE), 24, 24)
    heart_body_blink = pad_to(
        upscale(
            rasterize_native(
                blink_body_grid(HEART_BODY_NATIVE, HEART_EYE_TOP_NATIVE)
            ),
            SCALE,
        ),
        24, 24,
    )
    heart_region_h = HEART_REGION_NATIVE_H * SCALE
    canvas_h = heart_region_h + 24

    def compose(stage_grid, y_off, body_img):
        frame = Image.new("RGBA", (24, canvas_h), BG)
        heart_layer = render_heart_stage(stage_grid, y_off)
        frame.paste(heart_layer, (0, 0), heart_layer)
        frame.paste(body_img, (0, heart_region_h), body_img)
        return frame

    frames_ms = []
    for (stage_grid, y_off), delay in zip(HEART_STAGES[:-1], HEART_TIMELINE_MS[:-1]):
        frames_ms.append((compose(stage_grid, y_off, heart_body), delay))

    # Full-heart hold, split around a single blink frame.
    full_stage, full_y = HEART_STAGES[-1]
    frames_ms.append((compose(full_stage, full_y, heart_body), 400))
    frames_ms.append((compose(full_stage, full_y, heart_body_blink), 160))
    frames_ms.append((compose(full_stage, full_y, heart_body), 340))

    heart_out = os.path.join(ASSETS, "heart-rainbow.gif")
    write_gif(frames_ms, heart_out)
    total_ms = sum(d for _, d in frames_ms)
    print(
        f"Wrote {heart_out} (24x{canvas_h}, "
        f"{len(frames_ms)} frames, {total_ms}ms loop)"
    )


if __name__ == "__main__":
    main()
