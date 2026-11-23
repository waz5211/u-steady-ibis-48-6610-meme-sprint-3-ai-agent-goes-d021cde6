#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

Copies the meme image (meme.png, next to this script) to /output/entry.png
and validates it against the competition gate:
  - valid PNG (signature + IHDR + IEND, with IHDR CRC checked)
  - at most 1,048,576 bytes
  - width and height at most 1024 each

The copy is only accepted once the written file is verified byte-identical
to the validated source, so a truncated or corrupted write cannot slip
through as a "valid" entry.

Standard library only.
"""

import hashlib
import os
import shutil
import struct
import sys
import zlib

MAX_BYTES = 1_048_576
MAX_DIM = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHUNK_HEADER_SIZE = 8  # 4-byte length + 4-byte type
IHDR_LENGTH = 13


class GateError(ValueError):
    """Raised when the image fails a competition gate check."""


def _read_exact(f, n, what):
    data = f.read(n)
    if len(data) != n:
        raise GateError(f"truncated PNG: could not read {what} "
                        f"(got {len(data)} of {n} bytes)")
    return data


def read_png_dimensions(path):
    """Return (width, height) read from the PNG IHDR chunk.

    Validates the PNG signature, requires IHDR to be the first chunk with
    its declared length of 13, and checks the IHDR CRC so a corrupted
    header is rejected instead of trusting its declared dimensions.
    """
    with open(path, "rb") as f:
        # 8-byte signature + 8-byte chunk header + 13-byte IHDR + 4-byte CRC
        header = _read_exact(f, 8 + CHUNK_HEADER_SIZE + IHDR_LENGTH + 4,
                             "PNG signature and IHDR chunk")
    if header[:8] != PNG_SIGNATURE:
        raise GateError("not a valid PNG file: bad 8-byte signature")
    length, chunk_type = struct.unpack(">I4s", header[8:16])
    if chunk_type != b"IHDR":
        raise GateError("not a valid PNG file: first chunk is "
                        f"{chunk_type!r}, expected IHDR")
    if length != IHDR_LENGTH:
        raise GateError(f"not a valid PNG file: IHDR length is {length}, "
                        f"expected {IHDR_LENGTH}")
    ihdr_data = header[16:16 + IHDR_LENGTH]
    crc_stored, = struct.unpack(">I", header[16 + IHDR_LENGTH:])
    crc_actual = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    if crc_stored != crc_actual:
        raise GateError("not a valid PNG file: IHDR CRC mismatch "
                        f"(stored {crc_stored:#010x}, computed "
                        f"{crc_actual:#010x})")
    width, height = struct.unpack(">II", ihdr_data[:8])
    if width == 0 or height == 0:
        raise GateError(f"not a valid PNG file: zero dimension "
                        f"({width}x{height})")
    return width, height


def check_png_complete(path):
    """Require a well-formed IEND chunk at the end of the file.

    Walks the chunk list so a PNG cut off mid-stream is rejected even
    when its header looks fine.
    """
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        f.seek(8)
        offset = 8
        seen_iend = False
        while offset + CHUNK_HEADER_SIZE <= file_size:
            f.seek(offset)
            raw = f.read(CHUNK_HEADER_SIZE)
            length, chunk_type = struct.unpack(">I4s", raw)
            if chunk_type == b"IEND":
                if length != 0:
                    raise GateError("not a valid PNG file: IEND chunk "
                                    f"has length {length}, expected 0")
                if offset + CHUNK_HEADER_SIZE + 4 != file_size:
                    raise GateError("not a valid PNG file: trailing data "
                                    "after IEND chunk")
                seen_iend = True
                break
            # Skip chunk data + CRC; guard against a bogus huge length.
            next_offset = offset + CHUNK_HEADER_SIZE + length + 4
            if next_offset > file_size:
                raise GateError(f"truncated PNG: {chunk_type!r} chunk at "
                                f"offset {offset} claims {length} bytes, "
                                f"past end of file")
            offset = next_offset
        if not seen_iend:
            raise GateError("truncated PNG: no IEND chunk found")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def check_gate(path):
    """Run every gate check on the file at ``path``.

    Returns (width, height, size). Raises GateError with a specific
    message on the first failing check.
    """
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise GateError(f"entry is {size} bytes, over the "
                        f"{MAX_BYTES:,} byte limit")
    width, height = read_png_dimensions(path)
    if width > MAX_DIM or height > MAX_DIM:
        raise GateError(f"entry is {width}x{height}, over the "
                        f"{MAX_DIM}x{MAX_DIM} limit")
    check_png_complete(path)
    return width, height, size


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "meme.png")
    out_dir = "/output"
    dest = os.path.join(out_dir, "entry.png")

    if not os.path.isfile(source):
        print(f"error: source image not found: {source}", file=sys.stderr)
        return 1

    # Validate the source before copying, so we never write a file we
    # already know fails the gate.
    try:
        src_width, src_height, src_size = check_gate(source)
    except GateError as exc:
        print(f"error: source image fails the gate: {exc}", file=sys.stderr)
        return 1

    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(source, dest)

    # The copy is only good if it is byte-identical to the validated
    # source; a partial write would otherwise pass the header checks
    # only if the truncation happened to land after IEND, so verify.
    src_hash = sha256_file(source)
    dst_hash = sha256_file(dest)
    if src_hash != dst_hash:
        print(f"error: copy failed integrity check: {dest} differs from "
              f"{source} (sha256 {dst_hash[:12]}... != "
              f"{src_hash[:12]}...)", file=sys.stderr)
        return 1

    # Re-run the gate on the written file itself, so the file that is
    # actually submitted is the one that was checked.
    try:
        width, height, size = check_gate(dest)
    except GateError as exc:
        print(f"error: written entry.png fails the gate: {exc}",
              file=sys.stderr)
        return 1

    print(f"OK: /output/entry.png is a valid PNG, {width}x{height}, "
          f"{size} bytes, sha256 {dst_hash[:16]}... - gate passed "
          f"(source was {src_width}x{src_height}, {src_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
