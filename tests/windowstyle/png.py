# [CHANGE: claude-code | 2026-10-10] Stdlib PNG reader (8-bit RGB/RGBA, non-interlaced) — python-pillow is not installed.
import struct, zlib
def load(path):
    d = open(path, "rb").read(); assert d[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat = 8, b""
    while pos < len(d):
        n, typ = struct.unpack(">I4s", d[pos:pos + 8]); body = d[pos + 8:pos + 8 + n]; pos += 12 + n
        if typ == b"IHDR": w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT": idat += body
    assert depth == 8 and ctype in (2, 6) and inter == 0, "unsupported PNG %d/%d/%d" % (depth, ctype, inter)
    bpp = 4 if ctype == 6 else 3; raw = zlib.decompress(idat); stride = w * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[i]; line = bytearray(raw[i + 1:i + 1 + stride]); i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0; b = prev[x]; c = prev[x - bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line)); prev = line
    def px(x, y):
        r = rows[y]; o = x * bpp
        return tuple(r[o:o + 3]) + ((r[o + 3],) if bpp == 4 else (255,))
    return w, h, px
