#!/usr/bin/env python3
"""Build the themed "press button" Buddy animation from two Figma poses.

Design references:
  Start: Figma file lWE17f1tRRDXWsbxTcbsmo, node 5205:46681
  End:   Figma file lWE17f1tRRDXWsbxTcbsmo, node 5210:46916

The one-shot sequence moves the button 2px toward Buddy, dips its raised cap,
then reveals the two 2px sound-effect blocks before changing to the authored
wink. The button base remains anchored throughout.

Outputs:
  assets/press-button-blue.gif
  assets/press-button-green.gif

Requires: python3, Pillow, gifsicle (brew install gifsicle).
"""

import os
import subprocess
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

START_SOURCE = os.path.join(ASSETS, "press-button-start-source.png")
END_SOURCE = os.path.join(ASSETS, "press-button-end-source.png")

WIDTH = HEIGHT = 50
BODY_RIGHT = 27
BUTTON_SOURCE_BOX = (31, 38, 41, 44)
BUTTON_ORIGIN = (29, 38)
BUTTON_CAP_BOX = (2, 0, 8, 2)
BUTTON_CAP_PRESSED_ORIGIN = (2, 2)
TRANSPARENT = (0, 0, 0, 0)
FIGMA_FRAME_FILL = (35, 35, 35, 255)

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

EXPECTED_REFERENCES = {
    "start": {
        "bbox": (3, 22, 41, 44),
        "counts": {"LIGHT": 200, "MID": 96, "DEEP": 68, "PUPIL": 16},
    },
    "end": {
        "bbox": (3, 22, 42, 44),
        "counts": {"LIGHT": 210, "MID": 100, "DEEP": 68, "PUPIL": 22},
    },
}

CONTACT_ARM_BLOCKS = (
    (27, 36, "LIGHT"),
    (29, 36, "LIGHT"),
    (31, 36, "LIGHT"),
)

DOWNSTROKE_ARM_BLOCKS = (
    (27, 38, "LIGHT"),
    (29, 38, "LIGHT"),
    (31, 38, "LIGHT"),
)

LOW_POP_BLOCK = ((38, 35, "LIGHT"),)
HIGH_POP_BLOCK = ((40, 33, "MID"),)

FRAME_SEQUENCE = (
    ("rest", 500),
    ("contact", 300),
    ("button-down", 350),
    ("pop-low", 250),
    ("pop-high", 450),
    ("wink", 350),
)


def normalize_reference(path, remove_frame_fill=False):
    image = Image.open(path).convert("RGBA")
    source_size = image.size
    if source_size != (WIDTH, HEIGHT):
        if source_size[0] % WIDTH or source_size[1] % HEIGHT:
            raise ValueError(f"Figma export has unsupported size: {source_size}")
        image = image.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)

    pixels = []
    for pixel in image.getdata():
        if remove_frame_fill and pixel == FIGMA_FRAME_FILL:
            pixels.append(TRANSPARENT)
        else:
            pixels.append(pixel)
    image.putdata(pixels)
    return image


def verify_reference(name, image):
    expected = EXPECTED_REFERENCES[name]
    if image.getbbox() != expected["bbox"]:
        raise ValueError(f"{name} reference bounds changed: {image.getbbox()}")

    counts = {role: 0 for role in SOURCE_COLORS.values()}
    for pixel in image.getdata():
        if pixel == TRANSPARENT:
            continue
        try:
            counts[SOURCE_COLORS[pixel]] += 1
        except KeyError as error:
            raise ValueError(f"Unexpected {name} reference color: {pixel}") from error
    if counts != expected["counts"]:
        raise ValueError(f"{name} reference pixel counts changed: {counts}")


def paint_blocks(frame, blocks):
    pixels = frame.load()
    for x, y, role in blocks:
        color = SOURCE_ROLE_COLORS[role]
        for offset_y in (0, 1):
            for offset_x in (0, 1):
                pixels[x + offset_x, y + offset_y] = color


def build_action_frame(
    body_reference,
    button_reference,
    blocks,
    button_pressed=False,
):
    frame = Image.new("RGBA", (WIDTH, HEIGHT), TRANSPARENT)
    frame.paste(body_reference.crop((0, 0, BODY_RIGHT, HEIGHT)), (0, 0))
    button = button_reference.crop(BUTTON_SOURCE_BOX)
    if button_pressed:
        cap = button.crop(BUTTON_CAP_BOX)
        button.paste(TRANSPARENT, BUTTON_CAP_BOX)
        button.paste(cap, BUTTON_CAP_PRESSED_ORIGIN, cap)
    frame.paste(button, BUTTON_ORIGIN, button)
    paint_blocks(frame, blocks)
    return frame


def recolor(frame, palette):
    themed = Image.new("RGBA", frame.size, TRANSPARENT)
    themed.putdata([
        TRANSPARENT if pixel == TRANSPARENT else palette[SOURCE_COLORS[pixel]]
        for pixel in frame.getdata()
    ])
    return themed


def write_gif(frames, palette, out_path):
    roles = ("PUPIL", "DEEP", "MID", "LIGHT")
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
            indexed.putdata([color_to_index[pixel] for pixel in frame.getdata()])
            indexed.info["transparency"] = 0
            frame_path = os.path.join(temp_dir, f"frame-{index}.gif")
            indexed.save(
                frame_path,
                "GIF",
                transparency=0,
                disposal=2,
                optimize=False,
            )
            frame_paths.append(frame_path)

        command = ["gifsicle", "--no-warnings"]
        last_frame_index = len(frame_paths) - 1
        for index, (frame_path, (_frame, delay_ms)) in enumerate(
            zip(frame_paths, frames)
        ):
            command += [
                f"--delay={max(1, round(delay_ms / 10))}",
                "--disposal=none" if index == last_frame_index else "--disposal=background",
                frame_path,
            ]
        command += ["--output", out_path]
        subprocess.run(command, check=True)


def main():
    start = normalize_reference(START_SOURCE, remove_frame_fill=True)
    end = normalize_reference(END_SOURCE)
    verify_reference("start", start)
    verify_reference("end", end)
    source_frames = {
        "rest": build_action_frame(start, start, ()),
        "contact": build_action_frame(start, start, CONTACT_ARM_BLOCKS),
        "button-down": build_action_frame(
            start,
            start,
            DOWNSTROKE_ARM_BLOCKS,
            button_pressed=True,
        ),
        "pop-low": build_action_frame(
            start,
            start,
            CONTACT_ARM_BLOCKS + LOW_POP_BLOCK,
        ),
        "pop-high": build_action_frame(
            start,
            start,
            CONTACT_ARM_BLOCKS + LOW_POP_BLOCK + HIGH_POP_BLOCK,
        ),
        "wink": build_action_frame(
            end,
            start,
            CONTACT_ARM_BLOCKS + LOW_POP_BLOCK + HIGH_POP_BLOCK,
        ),
    }

    for variant, palette in PALETTES.items():
        frames = [
            (recolor(source_frames[name], palette), delay_ms)
            for name, delay_ms in FRAME_SEQUENCE
        ]
        out_path = os.path.join(ASSETS, f"press-button-{variant}.gif")
        write_gif(frames, palette, out_path)
        total_ms = sum(delay_ms for _name, delay_ms in FRAME_SEQUENCE)
        print(f"Wrote {out_path} ({len(frames)} frames, {total_ms}ms one-shot)")


if __name__ == "__main__":
    main()