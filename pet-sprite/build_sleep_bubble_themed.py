#!/usr/bin/env python3
"""
Build the animated "sleep bubble" state from Figma node 5262:49755 in
lWE17f1tRRDXWsbxTcbsmo and the existing themed sleep animation.

The Figma source is a 4x export of a 50x50 composition: a 24x24 Buddy at
(10, 20), a 2x2 bubble at (25, 40), then two 4x4 bubbles at (32, 36) and
(38, 32). The Figma body supplies every rendered body pixel and shade. The
existing sleep GIF supplies only the timing and two-pixel breathing range;
none of its body artwork is composited into this state. Two complete sleep
loops are used, with each bubble appearing cumulatively from left to right
on the sleep animation's pose changes.

Outputs:
  assets/sleep-bubble-blue.gif
  assets/sleep-bubble-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image, ImageSequence


HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SOURCE = os.path.join(ASSETS, "sleep-bubble-source.png")

SOURCE_SIZE = (200, 200)
NATIVE_SIZE = (50, 50)
EXPORT_SCALE = 4
TRANSPARENT = (0, 0, 0, 0)
BODY_SIZE = (24, 24)
BODY_OFFSET = (10, 20)
BUBBLE_BOXES = (
    (25, 40, 27, 42),
    (32, 36, 36, 40),
    (38, 32, 42, 36),
)

SOURCE_COLOR_TO_SLOT = {
    (0, 69, 56, 255): "DEEP",
    (0, 154, 124, 255): "MID",
    (36, 191, 165, 255): "LIGHT",
    (25, 26, 27, 255): "PUPIL",
}

PALETTES = {
    "blue": {
        "DEEP": (0, 78, 124, 255),
        "MID": (0, 119, 184, 255),
        "LIGHT": (35, 168, 242, 255),
        "PUPIL": (25, 26, 27, 255),
    },
    "green": {
        "DEEP": (0, 69, 56, 255),
        "MID": (0, 154, 124, 255),
        "LIGHT": (36, 191, 165, 255),
        "PUPIL": (25, 26, 27, 255),
    },
}


def load_native_source():
    source = Image.open(SOURCE).convert("RGBA")
    if source.size != SOURCE_SIZE:
        raise ValueError(f"Expected a {SOURCE_SIZE} Figma export, got {source.size}")

    for block_y in range(0, source.height, EXPORT_SCALE):
        for block_x in range(0, source.width, EXPORT_SCALE):
            colors = {
                source.getpixel((block_x + offset_x, block_y + offset_y))
                for offset_y in range(EXPORT_SCALE)
                for offset_x in range(EXPORT_SCALE)
            }
            if len(colors) != 1:
                raise ValueError(
                    f"Figma export is not a lossless {EXPORT_SCALE}x pixel grid "
                    f"at ({block_x}, {block_y})"
                )

    return source.resize(NATIVE_SIZE, Image.Resampling.NEAREST)


def recolor_source_pixel(source_color, palette):
    if source_color[3] == 0:
        return TRANSPARENT
    slot = SOURCE_COLOR_TO_SLOT.get(source_color)
    if slot is None:
        raise ValueError(f"Unexpected Figma color {source_color}")
    return palette[slot]


def load_body(source, palette):
    body = Image.new("RGBA", BODY_SIZE, TRANSPARENT)
    for pixel_y in range(BODY_SIZE[1]):
        for pixel_x in range(BODY_SIZE[0]):
            source_color = source.getpixel(
                (BODY_OFFSET[0] + pixel_x, BODY_OFFSET[1] + pixel_y)
            )
            body.putpixel(
                (pixel_x, pixel_y),
                recolor_source_pixel(source_color, palette),
            )

    # The final Figma composition paints the first two bubbles over the body.
    # Restore the light body fill beneath every overlap so bubbles can reveal
    # independently without leaving mid-shade pixels in the default pose.
    body_left, body_top = BODY_OFFSET
    body_right = body_left + BODY_SIZE[0]
    body_bottom = body_top + BODY_SIZE[1]
    for bubble_left, bubble_top, bubble_right, bubble_bottom in BUBBLE_BOXES:
        for pixel_y in range(max(body_top, bubble_top), min(body_bottom, bubble_bottom)):
            for pixel_x in range(max(body_left, bubble_left), min(body_right, bubble_right)):
                body.putpixel(
                    (pixel_x - body_left, pixel_y - body_top),
                    palette["LIGHT"],
                )
    return body


def build_breathing_poses(body):
    resting = body
    breathing = Image.new("RGBA", BODY_SIZE, TRANSPARENT)
    breathing.alpha_composite(
        body.resize((BODY_SIZE[0], BODY_SIZE[1] - 2), Image.Resampling.NEAREST),
        (0, 2),
    )
    return resting, breathing


def load_bubbles(source, palette):
    bubbles = []
    for left, top, right, bottom in BUBBLE_BOXES:
        bubble = Image.new("RGBA", (right - left, bottom - top), TRANSPARENT)
        for pixel_y in range(top, bottom):
            for pixel_x in range(left, right):
                source_color = source.getpixel((pixel_x, pixel_y))
                bubble.putpixel(
                    (pixel_x - left, pixel_y - top),
                    recolor_source_pixel(source_color, palette),
                )
        if bubble.getbbox() is None:
            raise ValueError(f"Empty bubble box {(left, top, right, bottom)}")
        bubbles.append((bubble, (left, top)))
    return bubbles


def load_sleep_cadence(variant):
    source_path = os.path.join(ASSETS, f"sleep-{variant}.gif")
    source = Image.open(source_path)
    if source.size != BODY_SIZE:
        raise ValueError(f"Expected a {BODY_SIZE} sleep body, got {source.size}")
    if source.info.get("loop") != 0:
        raise ValueError(f"Expected {source_path} to loop forever")

    cadence = []
    first_pose = None
    for frame in ImageSequence.Iterator(source):
        pose_bytes = frame.convert("RGBA").tobytes()
        if first_pose is None:
            first_pose = pose_bytes
        cadence.append((pose_bytes != first_pose, frame.info.get("duration", 40)))
    if len(cadence) < 2 or not any(is_breathing for is_breathing, _ in cadence):
        raise ValueError(f"Expected two sleep poses, got {len(cadence)} frame")
    return cadence


def find_pose_change(cadence):
    for frame_index, (is_breathing, _delay) in enumerate(cadence[1:], start=1):
        if is_breathing:
            return frame_index
    raise ValueError("Sleep animation contains only one visual pose")


def build_frames(source, palette, variant):
    cadence = load_sleep_cadence(variant)
    pose_change = find_pose_change(cadence)
    frame_count = len(cadence)
    reveal_frames = (pose_change, frame_count, frame_count + pose_change)
    body_poses = build_breathing_poses(load_body(source, palette))
    bubbles = load_bubbles(source, palette)
    frames = []

    for output_index in range(frame_count * 2):
        is_breathing, delay = cadence[output_index % frame_count]
        body = body_poses[1 if is_breathing else 0]
        composed = Image.new("RGBA", NATIVE_SIZE, TRANSPARENT)
        composed.alpha_composite(body, BODY_OFFSET)

        visible_bubbles = sum(
            output_index >= reveal_frame for reveal_frame in reveal_frames
        )
        for bubble, bubble_position in bubbles[:visible_bubbles]:
            composed.alpha_composite(bubble, bubble_position)
        frames.append((composed, delay))

    return frames, reveal_frames


def write_gif(frames, palette, output_path):
    slot_order = ("PUPIL", "DEEP", "MID", "LIGHT")
    palette_bytes = [0, 0, 0]
    for slot in slot_order:
        red, green, blue, _alpha = palette[slot]
        palette_bytes.extend((red, green, blue))
    palette_bytes.extend([0] * (256 * 3 - len(palette_bytes)))

    color_to_index = {TRANSPARENT: 0}
    for index, slot in enumerate(slot_order, start=1):
        color_to_index[palette[slot]] = index

    with tempfile.TemporaryDirectory() as temp_dir:
        frame_paths = []
        for frame_index, (frame, _delay) in enumerate(frames):
            indexed = Image.new("P", NATIVE_SIZE, 0)
            indexed.putpalette(palette_bytes)
            for pixel_y in range(frame.height):
                for pixel_x in range(frame.width):
                    color = frame.getpixel((pixel_x, pixel_y))
                    if color[3] == 0:
                        continue
                    palette_index = color_to_index.get(color)
                    if palette_index is None:
                        raise ValueError(
                            f"Unexpected output color {color} at "
                            f"({pixel_x}, {pixel_y})"
                        )
                    indexed.putpixel((pixel_x, pixel_y), palette_index)
            indexed.info["transparency"] = 0
            frame_path = os.path.join(temp_dir, f"frame-{frame_index:03d}.gif")
            indexed.save(
                frame_path,
                "GIF",
                transparency=0,
                disposal=2,
                optimize=False,
            )
            frame_paths.append(frame_path)

        command = [
            "gifsicle",
            "--loopcount=0",
            "--no-warnings",
            "--transparent=0",
        ]
        for frame_path, (_frame, delay) in zip(frame_paths, frames):
            command.extend(
                (
                    f"--delay={max(1, round(delay / 10))}",
                    "--disposal=background",
                    frame_path,
                )
            )
        command.extend(("--output", output_path))
        subprocess.run(command, check=True)


def main():
    if not os.path.exists(SOURCE):
        raise SystemExit(f"Source not found: {SOURCE}")

    source = load_native_source()
    for variant, palette in PALETTES.items():
        output_path = os.path.join(ASSETS, f"sleep-bubble-{variant}.gif")
        frames, reveal_frames = build_frames(source, palette, variant)
        write_gif(frames, palette, output_path)
        print(
            f"wrote {output_path} ({len(frames)} frames, "
            f"reveals at {reveal_frames}, canvas {NATIVE_SIZE[0]}x{NATIVE_SIZE[1]})"
        )


if __name__ == "__main__":
    main()