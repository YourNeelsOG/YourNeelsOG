#!/usr/bin/env python3
"""One-off preprocessing step: converts assets/source/avatar-original.png into
a character-density ASCII grid, written to assets/avatar_ascii.txt.

Run this whenever the source avatar image changes (needs Pillow, installed in
.venv). generate_terminal.py just reads the resulting text file — the main
generator stays dependency-free.
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "assets" / "source" / "avatar-original.png"
OUT_PATH = ROOT / "assets" / "avatar_ascii.txt"

RAMP = " .:-=+*#%@"  # low density -> high density

# Monospace character cell aspect ratio (width/height) at typical terminal
# metrics, used to keep the ascii art from looking stretched/squashed.
CELL_ASPECT = 0.44


def image_to_ascii(path, rows):
    img = Image.open(path).convert("RGBA")
    bg = Image.new("RGB", img.size, (0, 0, 0))
    bg.paste(img, mask=img.split()[3])
    gray = bg.convert("L")

    w, h = gray.size
    cols = round(rows * (w / h) / CELL_ASPECT)
    small = gray.resize((cols, rows), Image.Resampling.BOX)

    pixels = small.load()
    out_rows = []
    for y in range(rows):
        line = []
        for x in range(cols):
            brightness = pixels[x, y]
            idx = round(brightness / 255 * (len(RAMP) - 1))
            line.append(RAMP[idx])
        out_rows.append("".join(line))
    return out_rows


def main():
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 26
    ascii_rows = image_to_ascii(SOURCE_PATH, rows)
    OUT_PATH.write_text("\n".join(ascii_rows) + "\n")
    print(f"wrote {OUT_PATH}: {len(ascii_rows)} rows x {len(ascii_rows[0])} cols")


if __name__ == "__main__":
    main()
