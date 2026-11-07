#!/usr/bin/env python3
"""tests/sleep/png_stats.py <file.png> — prints "WIDTH HEIGHT STDDEV": the largest pixel stddev of R, G and B, 0-255.

Per channel, so a flat frame of any colour is near 0, not just the black a failed WebGL page draws.
Standard library only.
[CHANGE: claude-code | 2026-11-07]
"""
import statistics
import struct
import sys
import zlib
from pathlib import Path

CHANNELS = {2: 3, 6: 4}  # PNG colour type: RGB, RGBA


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def unfilter(kind, row, prev, step):
    if kind == 0:
        return row
    for i, value in enumerate(row):
        a = row[i - step] if i >= step else 0
        b = prev[i]
        c = prev[i - step] if i >= step else 0
        row[i] = (value + (a, b, (a + b) // 2, paeth(a, b, c))[kind - 1]) & 255
    return row


def stats(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{path}: not a PNG")
    pos, idat = 8, []
    while pos < len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", data[pos + 8:pos + 21])
        elif kind == b"IDAT":
            idat.append(data[pos + 8:pos + 8 + size])
        pos += size + 12
    if depth != 8 or colour not in CHANNELS or interlace:
        sys.exit(f"{path}: only 8-bit, non-interlaced RGB or RGBA is handled (depth {depth}, type {colour})")
    step = CHANNELS[colour]
    raw, stride = zlib.decompress(b"".join(idat)), width * step
    prev, samples = bytearray(stride), ([], [], [])
    for y in range(height):  # every row must be decoded, filters depend on the one above
        start = y * (stride + 1)
        prev = unfilter(raw[start], bytearray(raw[start + 1:start + 1 + stride]), prev, step)
        if y % 16 == 0:
            for channel, values in enumerate(samples):
                values += prev[channel::step * 16]
    return width, height, max(statistics.pstdev(values) for values in samples)


if __name__ == "__main__":
    width, height, stddev = stats(sys.argv[1])
    print(width, height, f"{stddev:.2f}")
