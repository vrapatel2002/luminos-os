# [CHANGE: claude-code | 2026-10-10] Pixel probes for luminos-windowstyle-check on a `spectacle -b -a` capture of
# tests/windowstyle/probe-window.qml (800x500 logical, body = palette Window). Usage: probe.py <png> <scale>
# Window = alpha==255 run (Spectacle 6.7 includes the shadow). Proven vs stock Breeze 2026-10-10 (1860x1316 @2x):
# corners FAIL (bottom square, top barely rounded); no-strip PASSes when header==body (FAILs at RGB distance >= 6);
# header FAILs on Breeze's icon/pin buttons top-left and centred title.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import png
def dist(a, b): return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5
def median(cols): return tuple(sorted(c[i] for c in cols)[len(cols) // 2] for i in range(3))
def out(ok, name, detail): print("%s %s: %s" % ("PASS" if ok else "FAIL", name, detail))
def main():
    w, h, px = png.load(sys.argv[1]); S = float(sys.argv[2])
    op = lambda x, y: px(x, y)[3] == 255
    row = [x for x in range(w) if op(x, h // 2)]
    if not row: return out(False, "shot-window", "no opaque pixels in %dx%d capture" % (w, h))
    L, R = row[0], row[-1]
    col = [y for y in range(h) if op(L + (R - L) * 3 // 10, y)]; T, B = col[0], col[-1]
    lw, lh = (R - L + 1) / S, (B - T + 1) / S
    if abs(lw - 800) > 3: return out(False, "shot-window", "captured window is %.0f logical px wide, not the 800 px probe window" % lw)
    out(True, "shot-window", "probe window at x%d..%d y%d..%d (%.0fx%.0f logical)" % (L, R, T, B, lw, lh))
    s = lambda v: int(round(v * S))
    corners = {"TL": (L + s(3), T + s(3)), "TR": (R - s(3), T + s(3)), "BL": (L + s(3), B - s(3)), "BR": (R - s(3), B - s(3))}
    inner = op(L + s(20), T + s(20)) and op(L + s(20), B - s(20))
    square = [k for k, (x, y) in corners.items() if op(x, y)]
    out(inner and not square, "shot-corners", "inner(20px) opaque=%s; corners opaque at 3px diagonal (want none): %s"
        % (inner, ",".join(square) or "none"))
    xs = range(L + (R - L) // 4, L + (R - L) // 2)
    head = median([px(x, T + s(20)) for x in xs]); body = median([px(x, T + s(48)) for x in xs])
    d = dist(head, body)
    out(d < 6, "shot-no-strip", "header %s vs body %s, RGB distance %.1f (want < 6)" % (head[:3], body[:3], d))
    ink = lambda x0, x1, y0, y1: sum(1 for x in range(max(L, x0), min(R, x1)) for y in range(y0, y1, 2)
                                     if dist(px(x, y), head) > 40)
    y0, y1 = T + s(6), T + s(34)
    slots = [ink(R - s(8 + 36 * (i + 1)), R - s(8 + 36 * i), y0, y1) for i in range(3)]
    left = ink(L + s(8), L + s(120), y0, y1); mid = ink(L + s(120), R - s(8 + 108), y0, y1)
    ok = all(n >= 4 for n in slots) and left == 0 and mid == 0
    out(ok, "shot-header", "glyph px in close/max/min slots %s (want each >= 4), left 120px %d, middle %d (want 0, 0)"
        % (slots, left, mid))
main()
