#!/usr/bin/env python3
"""Build the themed hiding Buddy animation from the linked Figma pose.

Design reference:
  Figma file lWE17f1tRRDXWsbxTcbsmo, node 5218:47441

Only the pupils move. They look left for 800ms and right for 1200ms,
matching the 2000ms loop and primary pose change of the idle state.

Outputs:
  assets/hiding-blue.gif
  assets/hiding-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SOURCE = os.path.join(ASSETS, "hiding-source.png")

WIDTH = HEIGHT = 50
TRANSPARENT = (0, 0, 0, 0)
LEDGE_FILL = (24, 25, 25, 255)
LEDGE_BORDER = (54, 54, 54, 255)

SOURCE_COLORS = {
    (36, 191, 165, 255): "LIGHT",
    (0, 154, 124, 255): "MID",
    (0, 69, 56, 255): "DEEP",
    (25, 26, 27, 255): "PUPIL",
}
SOURCE_ROLE_COLORS = {role: color for color, role in SOURCE_COLORS.items()}

PALETTES = {
    "blue": {
        "LIGHT": (35, 168, 242, 255),
        "MID": (0, 119, 184, 255),
        "DEEP": (0, 78, 124, 255),
        "PUPIL": (25, 26, 27, 255),
    },
    "green": {
        "LIGHT": (36, 191, 165, 255),
        "MID": (0, 154, 124, 255),
        "DEEP": (0, 69, 56, 255),
        "PUPIL": (25, 26, 27, 255),
    },
}

EXPECTED_COUNTS = Counter({
    SOURCE_ROLE_COLORS["LIGHT"]: 122,
    SOURCE_ROLE_COLORS["MID"]: 44,
    SOURCE_ROLE_COLORS["DEEP"]: 38,
    SOURCE_ROLE_COLORS["PUPIL"]: 12,
    LEDGE_FILL: 400,
    LEDGE_BORDER: 40,
})

PUPIL_PIXELS = tuple(
    (x, y)
    for y in range(29, 32)
    for x in (23, 24, 29, 30)
)

FRAME_SEQUENCE = (
    ("left", -1, 800),
    ("right", 1, 1200),
)


def normalize_reference(path):
    image = Image.open(path).convert("RGBA")
    source_size = image.size
    if source_size != (WIDTH, HEIGHT):
        if source_size[0] % WIDTH or source_size[1] % HEIGHT:
            raise ValueError(f"Figma export has unsupported size: {source_size}")
        image = image.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
    return image


def verify_reference(image):
    if image.getbbox() != (5, 15, 45, 43):
        raise ValueError(f"Hiding reference bounds changed: {image.getbbox()}")

    observed_counts = Counter(
        pixel for pixel in image.getdata() if pixel != TRANSPARENT
    )
    if observed_counts != EXPECTED_COUNTS:
        raise ValueError(f"Hiding reference colors changed: {observed_counts}")

    observed_pupils = tuple(
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if image.getpixel((x, y)) == SOURCE_ROLE_COLORS["PUPIL"]
    )
    if observed_pupils != PUPIL_PIXELS:
        raise ValueError(f"Hiding pupil geometry changed: {observed_pupils}")


def shift_eyes(reference, offset):
    destination_pixels = tuple((x + offset, y) for x, y in PUPIL_PIXELS)
    allowed_colors = {
        SOURCE_ROLE_COLORS["LIGHT"],
        SOURCE_ROLE_COLORS["PUPIL"],
    }
    for point in destination_pixels:
        if reference.getpixel(point) not in allowed_colors:
            raise ValueError(f"Eye shift leaves the face at {point}")

    frame = reference.copy()
    for point in PUPIL_PIXELS:
        frame.putpixel(point, SOURCE_ROLE_COLORS["LIGHT"])
    for point in destination_pixels:
        frame.putpixel(point, SOURCE_ROLE_COLORS["PUPIL"])
    return frame


def apply_palette(frame, palette):
    themed = frame.copy()
    themed.putdata([
        palette[SOURCE_COLORS[pixel]] if pixel in SOURCE_COLORS else pixel
        for pixel in frame.getdata()
    ])
    return themed


def write_gif(frames, palette, out_path):
    colors = [
        TRANSPARENT,
        palette["PUPIL"],
        palette["DEEP"],
        palette["MID"],
        palette["LIGHT"],
        LEDGE_FILL,
        LEDGE_BORDER,
    ]
    palette_bytes = []
    for red, green, blue, _alpha in colors:
        palette_bytes.extend([red, green, blue])
    palette_bytes.extend([0] * (256 * 3 - len(palette_bytes)))
    color_to_index = {color: index for index, color in enumerate(colors)}

    with tempfile.TemporaryDirectory() as temp_dir:
        frame_paths = []
        for index, (frame, _delay_ms) in enumerate(frames):
            indexed = Image.new("P", (WIDTH, HEIGHT), 0)
            indexed.putpalette(palette_bytes)
            indexed.putdata([color_to_index[pixel] for pixel in frame.getdata()])
            frame_path = os.path.join(temp_dir, f"frame-{index}.gif")
            indexed.save(
                frame_path,
                "GIF",
                transparency=0,
                disposal=2,
                optimize=False,
            )
            frame_paths.append(frame_path)

        command = ["gifsicle", "--no-warnings", "--loop=0"]
        for frame_path, (_frame, delay_ms) in zip(frame_paths, frames):
            command += [
                f"--delay={delay_ms // 10}",
                "--disposal=background",
                frame_path,
            ]
        command += ["--output", out_path]
        subprocess.run(command, check=True)


def main():
    reference = normalize_reference(SOURCE)
    verify_reference(reference)
    source_frames = {
        name: shift_eyes(reference, offset)
        for name, offset, _delay_ms in FRAME_SEQUENCE
    }

    for variant, palette in PALETTES.items():
        frames = [
            (apply_palette(source_frames[name], palette), delay_ms)
            for name, _offset, delay_ms in FRAME_SEQUENCE
        ]
        out_path = os.path.join(ASSETS, f"hiding-{variant}.gif")
        write_gif(frames, palette, out_path)
        print(f"Wrote {out_path} (2 frames, 2000ms loop)")


if __name__ == "__main__":
    main()