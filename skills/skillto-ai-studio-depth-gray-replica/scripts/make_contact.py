"""Build review-only contact sheets from sampled source frames."""

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("frames", type=Path)
    parser.add_argument("--fps", type=float)
    parser.add_argument("--per-sheet", type=int, default=10)
    args = parser.parse_args()
    files = sorted(args.frames.glob("frame-*.jpg"))
    if not files:
        raise SystemExit("No frames")
    for start in range(0, len(files), args.per_sheet):
        chunk = files[start:start + args.per_sheet]
        width, height = 300, 565
        sheet = Image.new("RGB", (width * 5, height * 2), "white")
        draw = ImageDraw.Draw(sheet)
        for offset, file in enumerate(chunk):
            index = start + offset
            frame = Image.open(file).convert("RGB")
            frame.thumbnail((width, height - 24))
            x = (offset % 5) * width + (width - frame.width) // 2
            y = (offset // 5) * height + 24
            sheet.paste(frame, (x, y))
            match = re.search(r"frame-([0-9]+(?:\.[0-9]+)?)s", file.stem)
            timestamp = float(match.group(1)) if match else index / args.fps
            draw.text(((offset % 5) * width + 8, (offset // 5) * height + 4), f"{timestamp:.2f}s", fill="black")
        dest = args.frames.parent / f"contact-{start // args.per_sheet + 1:02d}.jpg"
        sheet.save(dest, quality=88)
        print(dest)


if __name__ == "__main__":
    main()
