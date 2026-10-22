#!/usr/bin/env python3
"""
Build blue and green variants of the Figma "typing" buddy and laptop
as a two-pose stop-motion animation.

Design reference:
    Figma file lWE17f1tRRDXWsbxTcbsmo, node 5227:48162

The source node is a 50x50 frame composed from separate body, arm, and
laptop vector layers. Relative to the Figma reference, the
downstroke moves the arm one 2px grid step downward to meet the darker
row below, while the upstroke uses the reference position. Its 400ms /
600ms pose cadence creates a 1-second typing loop.

Outputs:
  assets/typing-blue.gif
  assets/typing-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

BODY_SOURCE = os.path.join(ASSETS, "typing-body-source.svg")
CONTACT_SOURCE = os.path.join(ASSETS, "typing-contact-source.svg")
LAPTOP_SOURCE = os.path.join(ASSETS, "typing-laptop-source.svg")
REFERENCE_SOURCE = os.path.join(ASSETS, "typing-source-revised.png")

WIDTH = HEIGHT = 50
BODY_OFFSET = (0, 22)
ARM_SEGMENT_OFFSETS = ((24, 38), (26, 38))
LAPTOP_OFFSET = (22, 32)
POSES = ((2, 400), (0, 600))
TRANSPARENT = (0, 0, 0, 0)

PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),
        "MID": (0, 119, 184, 255),
        "DEEP": (0, 78, 124, 255),
        "PUPIL": (25, 26, 27, 255),
        "DETAIL": (85, 85, 85, 255),
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),
        "MID": (0, 154, 124, 255),
        "DEEP": (0, 69, 56, 255),
        "PUPIL": (25, 26, 27, 255),
        "DETAIL": (85, 85, 85, 255),
    },
}

SOURCE_ROLES = {
    "#24BFA5": "LIGHT",
    "#009A7C": "MID",
    "#004538": "DEEP",
    "#191A1B": "PUPIL",
    "#555555": "DETAIL",
}

RECT_PATH = re.compile(
    r"^M(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)"
    r"H(-?\d+(?:\.\d+)?)V(-?\d+(?:\.\d+)?)"
    r"H(-?\d+(?:\.\d+)?)V(-?\d+(?:\.\d+)?)Z$"
)


def load_rectangles(path):
    """Read the axis-aligned pixel rectangles from a Figma SVG layer."""
    root = ET.parse(path).getroot()
    rectangles = []
    for element in root.iter():
        if not element.tag.endswith("path"):
            continue
        data = element.get("d", "")
        match = RECT_PATH.match(data)
        if not match:
            raise ValueError(f"Unsupported Figma path in {path}: {data}")
        x0, y0, x1, y1, x2, y2 = (float(value) for value in match.groups())
        if (x0, y0) != (x2, y2):
            raise ValueError(f"Open Figma rectangle in {path}: {data}")
        fill = element.get("fill", "").upper()
        try:
            role = SOURCE_ROLES[fill]
        except KeyError as error:
            raise ValueError(f"Unsupported Figma fill in {path}: {fill}") from error
        rectangles.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), role))
    return rectangles


def draw_layer(frame, rectangles, offset, palette):
    """Draw one exported Figma layer at its original frame offset."""
    offset_x, offset_y = offset
    draw = ImageDraw.Draw(frame)
    for x0, y0, x1, y1, role in rectangles:
        bounds = (
            round(x0 + offset_x),
            round(y0 + offset_y),
            round(x1 + offset_x) - 1,
            round(y1 + offset_y) - 1,
        )
        draw.rectangle(bounds, fill=palette[role])


def build_frame(palette, arm_y_offset):
    """Compose one pose while preserving the Figma layer order."""
    frame = Image.new("RGBA", (WIDTH, HEIGHT), TRANSPARENT)
    draw_layer(frame, BODY_RECTS, BODY_OFFSET, palette)
    for offset_x, offset_y in ARM_SEGMENT_OFFSETS:
        draw_layer(
            frame,
            CONTACT_RECTS,
            (offset_x, offset_y + arm_y_offset),
            palette,
        )
    draw_layer(
        frame,
        LAPTOP_RECTS,
        LAPTOP_OFFSET,
        palette,
    )
    return frame


def verify_figma_reference(frame):
    """Ensure the green reference pose is pixel-identical to the node export."""
    reference = Image.open(REFERENCE_SOURCE).convert("RGBA")
    if reference.size != (WIDTH, HEIGHT):
        reference = reference.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
    if list(frame.getdata()) != list(reference.getdata()):
        differences = sum(
            expected != actual
            for expected, actual in zip(reference.getdata(), frame.getdata())
        )
        raise ValueError(f"Generated downstroke differs from Figma at {differences} pixels")


def write_gif(frames, palette, out_path):
    """Write fixed-palette frames with transparent disposal via gifsicle."""
    roles = ("PUPIL", "DETAIL", "DEEP", "MID", "LIGHT")
    palette_bytes = [0, 0, 0]
    for role in roles:
        palette_bytes.extend(palette[role][:3])
    palette_bytes.extend([0] * (256 * 3 - len(palette_bytes)))

    color_to_index = {TRANSPARENT: 0}
    for index, role in enumerate(roles, start=1):
        color_to_index[palette[role]] = index

    with tempfile.TemporaryDirectory() as temp_dir:
        frame_paths = []
        for index, (frame, _delay_ms) in enumerate(frames):
            indexed = Image.new("P", (WIDTH, HEIGHT), 0)
            indexed.putpalette(palette_bytes)
            source_pixels = frame.load()
            target_pixels = indexed.load()
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    target_pixels[x, y] = color_to_index[source_pixels[x, y]]
            indexed.info["transparency"] = 0
            frame_path = os.path.join(temp_dir, f"frame-{index}.gif")
            indexed.save(frame_path, "GIF", transparency=0, disposal=2, optimize=False)
            frame_paths.append(frame_path)

        command = ["gifsicle", "--loopcount=0", "--no-warnings"]
        for frame_path, (_frame, delay_ms) in zip(frame_paths, frames):
            command += [
                f"--delay={max(1, round(delay_ms / 10))}",
                "--disposal=background",
                frame_path,
            ]
        command += ["--output", out_path]
        subprocess.run(command, check=True)


BODY_RECTS = load_rectangles(BODY_SOURCE)
CONTACT_RECTS = load_rectangles(CONTACT_SOURCE)
LAPTOP_RECTS = load_rectangles(LAPTOP_SOURCE)


def main():
    green_reference_pose = build_frame(PALETTES["green"], 0)
    verify_figma_reference(green_reference_pose)

    for variant, palette in PALETTES.items():
        frames = [
            (build_frame(palette, arm_y_offset), delay_ms)
            for arm_y_offset, delay_ms in POSES
        ]
        out_path = os.path.join(ASSETS, f"typing-{variant}.gif")
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} ({len(frames)} frames)")


if __name__ == "__main__":
    main()