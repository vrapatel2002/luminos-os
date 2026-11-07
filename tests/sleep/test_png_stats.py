# tests/sleep/test_png_stats.py — the poster check in live.sh has to be right about what it reports.
# [CHANGE: claude-code | 2026-11-07]
import random
import statistics
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png_stats import paeth, stats


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def png(path, rows, width, step, filters=(0,), chunks=1):
    """Write rows of raw bytes, cycling through the given PNG row filters. Split IDAT if asked."""
    raw, prev = bytearray(), bytes(width * step)
    for y, row in enumerate(rows):
        kind = filters[y % len(filters)]
        raw.append(kind)
        for i, value in enumerate(row):
            a = row[i - step] if i >= step else 0
            b = prev[i]
            c = prev[i - step] if i >= step else 0
            predicted = (0, a, b, (a + b) // 2, paeth(a, b, c))[kind]
            raw.append((value - predicted) & 255)
        prev = row
    packed = zlib.compress(bytes(raw))
    cut = len(packed) // chunks + 1
    colour = {3: 2, 4: 6}[step]
    head = struct.pack(">IIBBBBB", width, len(rows), 8, colour, 0, 0, 0)
    body = chunk(b"IHDR", head)
    for i in range(0, len(packed), cut):
        body += chunk(b"IDAT", packed[i:i + cut])
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + body + chunk(b"IEND", b""))


def noise_rows(width, height, step, seed=1):
    rng = random.Random(seed)
    return [bytes(rng.randrange(256) for _ in range(width * step)) for _ in range(height)]


def expected(rows, step):
    values = ([], [], [])
    for row in rows[::16]:
        for channel, seen in enumerate(values):
            seen += row[channel::step * 16]
    return max(statistics.pstdev(seen) for seen in values)


@pytest.mark.parametrize("step", [3, 4])
@pytest.mark.parametrize("filters", [(0,), (1,), (2,), (3,), (4,), (0, 1, 2, 3, 4)])
def test_decodes_every_filter_exactly(tmp_path, step, filters):
    rows = noise_rows(64, 48, step)
    png(tmp_path / "x.png", rows, 64, step, filters, chunks=3)
    width, height, stddev = stats(tmp_path / "x.png")
    assert (width, height) == (64, 48)
    assert stddev == pytest.approx(expected(rows, step))
    assert stddev > 5


@pytest.mark.parametrize("colour", [(0, 0, 0), (255, 255, 255), (10, 20, 80)])
def test_a_flat_frame_of_any_colour_is_flat(tmp_path, colour):
    rows = [bytes(colour) * 64] * 48
    png(tmp_path / "x.png", rows, 64, 3, (0, 1, 2, 3, 4))
    assert stats(tmp_path / "x.png")[2] < 1


def test_samples_one_pixel_in_sixteen_each_way(tmp_path):
    rows = [bytearray(64 * 3) for _ in range(48)]
    rows[0][48:51] = b"\xff\xff\xff"  # pixel 16 of row 0: sampled
    png(tmp_path / "x.png", [bytes(r) for r in rows], 64, 3)
    assert stats(tmp_path / "x.png")[2] > 5
    rows[0][48:51] = b"\x00\x00\x00"
    rows[1][3:6] = b"\xff\xff\xff"  # an unsampled row
    png(tmp_path / "x.png", [bytes(r) for r in rows], 64, 3)
    assert stats(tmp_path / "x.png")[2] < 1


def test_refuses_what_it_cannot_read(tmp_path):
    (tmp_path / "x.png").write_bytes(b"not a png")
    with pytest.raises(SystemExit):
        stats(tmp_path / "x.png")
