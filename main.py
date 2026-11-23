#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

Copies the meme image (meme.png, next to this script) to /output/entry.png
and validates it against the competition gate:
  - valid PNG (signature + IHDR)
  - at most 1,048,576 bytes
  - width and height at most 1024 each

Standard library only.
"""

import os
import shutil
import struct
import sys

MAX_BYTES = 1_048_576
MAX_DIM = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_dimensions(path):
    """Return (width, height) read from the PNG IHDR chunk."""
    with open(path, "rb") as f:
        header = f.read(33)
    if len(header) < 33 or header[:8] != PNG_SIGNATURE:
        raise ValueError("not a valid PNG file (bad signature)")
    length, chunk_type = struct.unpack(">I4s", header[8:16])
    if chunk_type != b"IHDR" or length != 13:
        raise ValueError("not a valid PNG file (missing IHDR chunk)")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "meme.png")
    out_dir = "/output"
    dest = os.path.join(out_dir, "entry.png")

    if not os.path.isfile(source):
        print(f"error: source image not found: {source}", file=sys.stderr)
        return 1

    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(source, dest)

    size = os.path.getsize(dest)
    if size > MAX_BYTES:
        print(f"error: entry.png is {size} bytes, over the "
              f"{MAX_BYTES} byte limit", file=sys.stderr)
        return 1

    width, height = read_png_dimensions(dest)
    if width > MAX_DIM or height > MAX_DIM:
        print(f"error: entry.png is {width}x{height}, over the "
              f"{MAX_DIM}x{MAX_DIM} limit", file=sys.stderr)
        return 1

    print(f"OK: /output/entry.png is a valid PNG, "
          f"{width}x{height}, {size} bytes - gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
