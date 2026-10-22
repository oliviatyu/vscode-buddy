#!/usr/bin/env python3
"""Build the Figma-authored eating interaction for Buddy.

The rest, open-mouth, and blown-cheek closed-mouth poses are exact Figma
keyframes. Eating alternates the authored open/closed poses three times
before returning to the authored Eat rest state.
"""

import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
BG = (0, 0, 0, 0)
W, H = 34, 24
FIGMA_REST_SVG = os.path.join(ASSETS, "eat-figma-before.svg")
FIGMA_OPEN_SVG = os.path.join(ASSETS, "eat-figma-idle.svg")
FIGMA_CLOSE_SVG = os.path.join(ASSETS, "eat-figma-close.svg")
FIGMA_SIDE_OPEN_SVG = os.path.join(ASSETS, "eat-figma-side-open.svg")

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
        "DEEP": (0, 100, 81, 255),
        "PUPIL": (25, 26, 27, 255),
    },
}

FIGMA_COLOR_SLOTS = {
    "#23A8F2": "LIGHT",
    "#0077B8": "MID",
    "#004E7C": "DEEP",
    "#191A1B": "PUPIL",
    "#555555": "PUPIL",
}


def rect(image, box, color):
    pixels = image.load()
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            if 0 <= x < W and 0 <= y < H:
                pixels[x, y] = color


def frame_from_svg(path, palette):
    image = Image.new("RGBA", (W, H), BG)
    root = ET.parse(path).getroot()
    for path in root.iter("{http://www.w3.org/2000/svg}path"):
        data = path.get("d")
        slot = FIGMA_COLOR_SLOTS.get(path.get("fill", "").upper())
        if not data or not slot:
            continue
        numbers = [int(value) for value in re.findall(r"-?\d+", data)]
        xs = numbers[0::2]
        ys = numbers[1::2]
        rect(image, (min(xs), min(ys), max(xs), max(ys)), palette[slot])
    return image


def base_frame(palette):
    return frame_from_svg(FIGMA_REST_SVG, palette)


def eating_open_frame(palette):
    frame = frame_from_svg(FIGMA_OPEN_SVG, palette)
    rect(frame, (9, 12, 13, 16), palette["LIGHT"])
    rect(frame, (15, 12, 19, 16), palette["LIGHT"])
    rect(frame, (10, 12, 12, 16), palette["PUPIL"])
    rect(frame, (16, 12, 18, 16), palette["PUPIL"])
    rect(frame, (10, 18, 18, 22), palette["LIGHT"])
    rect(frame, (12, 18, 16, 22), palette["PUPIL"])
    return frame


def tracking_frame(palette):
    return eating_open_frame(palette)


def chewing_closed_frame(palette):
    frame = frame_from_svg(FIGMA_CLOSE_SVG, palette)
    rect(frame, (9, 12, 13, 16), palette["LIGHT"])
    rect(frame, (15, 12, 19, 16), palette["LIGHT"])
    rect(frame, (10, 12, 12, 16), palette["PUPIL"])
    rect(frame, (16, 12, 18, 16), palette["PUPIL"])
    rect(frame, (10, 19, 18, 21), palette["LIGHT"])
    rect(frame, (11, 19, 17, 21), palette["PUPIL"])
    return frame


def side_open_frame(palette):
    frame = frame_from_svg(FIGMA_SIDE_OPEN_SVG, palette)
    rect(frame, (16, 16, 24, 22), BG)
    return frame





def clear_mouth(image, palette):
    rect(image, (10, 16, 22, 22), palette["LIGHT"])


def draw_mouth(image, palette, mouth):
    dark = palette["PUPIL"]
    if mouth == "closed":
        rect(image, (12, 18, 18, 20), dark)
    elif mouth == "chew-left":
        rect(image, (10, 18, 16, 20), dark)
    elif mouth == "chew-right":
        rect(image, (14, 18, 20, 20), dark)
    elif mouth == "pucker":
        rect(image, (18, 16, 20, 20), dark)
    elif mouth == "open":
        rect(image, (12, 16, 20, 22), dark)
    elif mouth == "wide":
        rect(image, (8, 16, 22, 22), dark)
    elif mouth == "pac-open":
        rect(image, (18, 16, 22, 22), dark)
        rect(image, (14, 18, 22, 20), dark)
    elif mouth == "pac-wide":
        rect(image, (20, 14, 22, 22), dark)
        rect(image, (16, 16, 22, 22), dark)
        rect(image, (12, 18, 22, 20), dark)
    elif mouth == "gulp":
        rect(image, (12, 16, 20, 22), dark)
        rect(image, (14, 18, 18, 20), palette["DEEP"])


def draw_food(image, palette, x, y, kind="pellet"):
    if x is None:
        return
    if kind == "powerup":
        rect(image, (x + 1, y, x + 3, y + 4), palette["LIGHT"])
        rect(image, (x, y + 1, x + 4, y + 3), palette["LIGHT"])
        rect(image, (x + 1, y + 1, x + 3, y + 3), palette["MID"])
    else:
        rect(image, (x, y, x + 3, y + 3), palette["MID"])
        rect(image, (x, y, x + 2, y + 1), palette["LIGHT"])


def draw_effect(image, palette, effect):
    if effect == "suction":
        rect(image, (24, 14, 28, 16), palette["DEEP"])
        rect(image, (26, 20, 32, 22), palette["MID"])
    elif effect == "crumbs":
        rect(image, (21, 15, 23, 17), palette["MID"])
        rect(image, (24, 19, 26, 21), palette["LIGHT"])
    elif effect == "sparkle":
        for x, y in ((5, 10), (21, 12), (23, 18)):
            rect(image, (x, y, x + 2, y + 2), palette["LIGHT"])
    elif effect == "flash":
        for x, y in ((4, 9), (21, 9), (23, 14), (3, 18), (20, 22)):
            rect(image, (x, y, x + 2, y + 2), palette["LIGHT"])


def make_frame(palette, mouth="closed", eyes="open", food=None, effect=None):
    image = base_frame(palette)
    clear_mouth(image, palette)
    draw_mouth(image, palette, mouth)
    if food:
        draw_food(image, palette, *food)
    draw_effect(image, palette, effect)
    return image


def concept_frames(palette, concept):
    frame = lambda delay, **kwargs: (make_frame(palette, **kwargs), delay)
    rest = frame_from_svg(FIGMA_REST_SVG, palette)
    if concept == "classic":
        mouth_open = eating_open_frame(palette)
        mouth_closed = chewing_closed_frame(palette)
        return [
            (mouth_open.copy(), 220),
            (mouth_closed.copy(), 280),
            (mouth_open.copy(), 220),
            (mouth_closed.copy(), 280),
            (mouth_open.copy(), 220),
            (mouth_closed.copy(), 280),
            (rest.copy(), 500),
        ]
    if concept == "side":
        chew_open = eating_open_frame(palette)
        chew_closed = chewing_closed_frame(palette)
        return [
            (chew_open.copy(), 300),
            (chew_closed.copy(), 400),
            (chew_open.copy(), 300),
            (chew_closed.copy(), 400),
            (chew_open.copy(), 300),
            (chew_closed.copy(), 400),
            (rest.copy(), 500),
        ]
    if concept == "vacuum":
        return [
            frame(220, mouth="pucker", eyes="wide"),
            frame(260, mouth="pucker", eyes="wide", effect="suction"),
            frame(260, mouth="open", eyes="wide", effect="suction"),
            frame(220, mouth="gulp", eyes="wide"),
            frame(240, mouth="chew-left"),
            frame(760, mouth="closed", eyes="happy"),
        ]
    if concept == "combo":
        return [
            frame(180, mouth="open", eyes="wide"),
            frame(120, mouth="closed", effect="crumbs"),
            frame(160, mouth="open"),
            frame(120, mouth="wide"),
            frame(120, mouth="closed", effect="crumbs"),
            frame(160, mouth="open"),
            frame(120, mouth="closed", effect="crumbs"),
            frame(650, mouth="closed", eyes="happy", effect="sparkle"),
        ]
    return [
        frame(240, eyes="wide"),
        frame(260, mouth="open", eyes="wide"),
        frame(320, mouth="wide", eyes="wide"),
        frame(180, mouth="gulp", eyes="wide", effect="flash"),
        frame(220, mouth="closed", effect="flash"),
        frame(900, mouth="closed", eyes="happy", effect="sparkle"),
    ]


def write_gif(frames, palette, output):
    roles = ("PUPIL", "DEEP", "MID", "LIGHT")
    palette_bytes = [0, 0, 0]
    for role in roles:
        palette_bytes.extend(palette[role][:3])
    palette_bytes.extend([0] * (256 * 3 - len(palette_bytes)))
    color_to_index = {BG: 0}
    for index, role in enumerate(roles, start=1):
        color_to_index[palette[role]] = index

    with tempfile.TemporaryDirectory() as temp_dir:
        paths = []
        for index, (image, _delay) in enumerate(frames):
            indexed = Image.new("P", image.size, 0)
            indexed.putpalette(palette_bytes)
            indexed.putdata([color_to_index[pixel] for pixel in image.getdata()])
            path = os.path.join(temp_dir, f"frame-{index}.gif")
            indexed.save(path, "GIF", transparency=0, disposal=2, optimize=False)
            paths.append(path)

        command = ["gifsicle", "--loopcount=0", "--no-warnings", "--transparent=0"]
        for path, (_image, delay) in zip(paths, frames):
            command += [
                f"--delay={max(1, round(delay / 10))}",
                "--disposal=background",
                path,
            ]
        command += ["--output", output]
        subprocess.run(command, check=True)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    for variant, palette in PALETTES.items():
        idle_output = os.path.join(ASSETS, f"eat-idle-{variant}.gif")
        idle = base_frame(palette).crop((0, 0, 24, 24))
        write_gif([(idle, 1000)], palette, idle_output)
        print(f"Wrote {idle_output}")
        tracking_output = os.path.join(ASSETS, f"eat-tracking-{variant}.gif")
        tracking = tracking_frame(palette).crop((0, 0, 24, 24))
        write_gif([(tracking, 1000)], palette, tracking_output)
        print(f"Wrote {tracking_output}")
        side_tracking_output = os.path.join(ASSETS, f"eat-side-tracking-{variant}.gif")
        side_tracking = side_open_frame(palette).crop((0, 0, 24, 24))
        write_gif([(side_tracking, 1000)], palette, side_tracking_output)
        print(f"Wrote {side_tracking_output}")
    for concept in ("classic", "side"):
        for variant, palette in PALETTES.items():
            output = os.path.join(ASSETS, f"eat-{concept}-{variant}.gif")
            write_gif(concept_frames(palette, concept), palette, output)
            print(f"Wrote {output}")


if __name__ == "__main__":
    main()
