# [CHANGE: claude-code | 2026-10-11] Phase 3 shape probes. Usage: shapes.py <dir> rows|slider-radio|formcard [k=v..]
# or <png> pill <r,g,b> <scale>. Formcard reads ShadowedRectangle radii (software renderer squares them). Row radius: first
# opaque step k on each corner diagonal of the alpha>=128 bbox -> r ~= (k+0.5)/(1-1/sqrt2) (square 1.7, r4 5.1, r28 29).
# Stock qqc2 6.30.0-1.2 (2026-10-11): rows paint nothing / current r 8.5, groove 4 px, handle 20, radio symmetric: FAIL.
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import png
out = lambda ok, name, detail: print("%s %s: %s" % ("PASS" if ok else "FAIL", name, detail))
dist = lambda a, b: sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5
def shape(path):
    if not os.path.isfile(path): return None
    w, h, px = png.load(path); op = lambda x, y: px(x, y)[3] >= 128
    pts = [(x, y) for y in range(h) for x in range(w) if op(x, y)]
    if not pts: return dict(cov=0)
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts); y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    def rad(cx, cy, dx, dy):
        k = next((k for k in range(min(x1 - x0, y1 - y0) // 2 + 1) if op(cx + dx * k, cy + dy * k)), 99)
        return round((k + 0.5) / 0.2929, 1)
    return dict(cov=min((x1 - x0 + 1) / w, (y1 - y0 + 1) / h), w=w, h=h, px=px, op=op, box=(x0, y0, x1, y1),
                r=(rad(x0, y0, 1, 1), rad(x1, y0, -1, 1), rad(x0, y1, 1, -1), rad(x1, y1, -1, -1)))   # TL TR BL BR
def connected(name, rows, roles):   # rows: (name, (TL,TR,BL,BR), height) or (name, None, why); roles f/m/l/c(urrent)
    bad, notes = [], []   # a radius can't exceed h/2 (Qt clamps), so want min(token, h/2) - 3.5 px estimator tolerance
    for (n, r, h), role in zip(rows, roles):
        if r is None: bad.append("%s %s" % (n, h)); continue
        tl, tr, bl, br = r; o, c = min(28, h / 2) - 3.5, min(32, h / 2) - 3.5
        notes.append("%s[%s,h%g]=%s" % (n, role, h, "/".join("%g" % v for v in r)))
        if not {"f": min(tl, tr) >= o and max(bl, br) <= 6, "l": min(bl, br) >= o and max(tl, tr) <= 6,
                "m": max(r) <= 6, "c": min(r) >= c}[role]: bad.append(n + " wrong corners")
    out(not bad and len(rows) == len(roles), name, "radii TL/TR/BL/BR %s; want first top / last bottom >= min(28,h/2), "
        "middle <= 6, current all >= min(32,h/2) (-3.5)%s" % (" ".join(notes) or "-", ("; " + "; ".join(bad)) if bad else ""))
def pixrow(d, i):
    s = shape(os.path.join(d, "row%d.png" % i))
    return ("row%d" % i, None, "paints no background") if not s or s["cov"] < 0.6 else ("row%d" % i, s["r"], s["box"][3] - s["box"][1] + 1)
def slider_radio(d, handle):
    t = shape(os.path.join(d, "track.png")); thick = []
    for fx in (0.15, 0.85) if t and t["cov"] else ():   # away from the handle at value 0.5
        run = best = 0
        for y in range(t["h"]): run = run + 1 if t["op"](int(t["w"] * fx), y) else 0; best = max(best, run)
        thick.append(best)
    out(thick and min(thick) >= 14 and 0 < handle <= 6, "qml-slider",
        "track thickness at 15%%/85%% %s px (want >= 14), handle width %g (want 1..6)" % (thick or "<no track>", handle))
    rd = shape(os.path.join(d, "radio.png")); inner = filled = diff = 0
    if rd and rd["cov"]:
        x0, y0, x1, y1 = rd["box"]; cx, cy, R = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2; px = rd["px"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 > (0.7 * R) ** 2: continue
                inner += 1; filled += rd["op"](x, y); diff += dist(px(x, y), px(int(round(2 * cx - x)), y)) > 40
    f, a = filled / max(inner, 1), diff / max(inner, 1)
    out(f > 0.9 and a > 0.03, "qml-radio", "checked indicator inner-disc fill %.2f (want > 0.9), left/right asymmetry "
        "%.3f (want > 0.03: a check mark is asymmetric, ring+dot is not)" % (f, a))
def pill(path, sel, S):   # live System Settings capture: is the sidebar's selected row a pill?
    w, h, px = png.load(path); row = [x for x in range(w) if px(x, h // 2)[3] == 255]
    if not row: return out(False, "live-systemsettings", "no opaque window in capture")
    xr = range(row[0], row[0] + (row[-1] - row[0]) * 3 // 10); near = lambda x, y: dist(px(x, y), sel) < 14
    ys = [y for y in range(h) if sum(near(x, y) for x in xr[::2]) >= 10]; runs = []
    for y in ys: runs[-1:] = [[runs[-1][0], y]] if runs and runs[-1][1] == y - 1 else runs[-1:] + [[y, y]]
    if not runs: return out(False, "live-systemsettings", "no selection-colour %s region in the left 30%%" % (sel,))
    y0, y1 = max(runs, key=lambda r: r[1] - r[0]); ym = (y0 + y1) // 2; xs = [x for x in xr if near(x, ym)]
    x0, x1 = xs[0], xs[-1]; k = int(round(3 * S)); fill = len(xs) / (x1 - x0 + 1)
    hit = [n for n, (x, y) in zip(("TL", "TR", "BL", "BR"), ((x0+k, y0+k), (x1-k, y0+k), (x0+k, y1-k), (x1-k, y1-k))) if near(x, y)]
    out(fill > 0.5 and not hit, "live-systemsettings", "selected row x%d..%d y%d..%d, centre-line fill %.2f (want > 0.5), "
        "selection colour at 3px-diagonal corners: %s (want none)" % (x0, x1, y0, y1, fill, ",".join(hit) or "none"))
def formlayout(fl):   # Phase 4 Kirigami.FormLayout: one visual rect per labelled row, joined pieces (gap 0, radii 0) merge
    cs, vis = sorted(fl["cards"]), []
    for c in cs:
        if vis and abs(c[0] - vis[-1][0] - vis[-1][1]) <= 0.5 and max(vis[-1][4:6] + c[2:4]) <= 0.5: vis[-1] = vis[-1][:1] + [c[0] + c[1] - vis[-1][0]] + vis[-1][2:4] + c[4:6]
        else: vis.append(list(c))
    own = {k: next((i for i, v in enumerate(vis) if v[0] <= y <= v[0] + v[1]), None) for k, y in fl["ctl"].items()}
    o = lambda i: min(28, vis[i][1] / 2) - 3.5; bad = []
    main = [own[k] for k in ("combo", "spin", "sw", "sl", "tf")]
    if None in main or len(set(main)) != 5: bad.append("labelled rows not in 5 separate rects %s" % own)
    elif own["check"] != own["spin"]: bad.append("unlabelled CheckBox not in the SpinBox rect")
    else:
        c, sp, sw, sl, tf = main; r = lambda i: vis[i][2:]
        if not (min(r(c)[:2]) >= o(c) and max(r(c)[2:]) <= 6): bad.append("first rect corners %s" % r(c))
        if max(r(sp) + r(sw) + r(sl)[:2]) > 6 or min(r(sl)[2:]) < o(sl): bad.append("touching/last corners %s" % [r(sp), r(sw), r(sl)])
        if min(r(tf)) < o(tf): bad.append("bare Separator does not split groups: TextField rect %s" % r(tf))
        gaps = [vis[b][0] - vis[a][0] - vis[a][1] for a, b in ((c, sp), (sp, sw), (sw, sl))]
        if not all(1 <= g <= 3 for g in gaps): bad.append("gaps %s (want ~2)" % gaps)
    if not fl["sliderBelow"]: bad.append("Slider not below its label")
    if fl["secLine"] or not fl["pointer"]: bad.append("section drawn as a line (or no 'Pointer' label)")
    out(not bad, "formlayout", "rects y/h/TL/TR/BL/BR %s; %s" % (vis, "; ".join(bad) or "groups, joins, corners, gaps, slider, section OK"))
def boundary(path, frame, view, S):   # live System Settings: no separator lines at the sidebar/hole edge or above the footer
    w, h, px = png.load(path); near = lambda x, y: dist(px(x, y), view) < 10
    br = lambda x, y: max(px(x, y)[i] - frame[i] for i in range(3)) > 12; s = lambda v: int(round(v * S))
    _, hx0, hx1 = max([(0, 0, 0)] + [(len(g), g[0], g[-1]) for k, it in __import__("itertools").groupby(range(w), lambda x: near(x, h // 2)) if k for g in [list(it)]]); ys = [y for y in range(h) if near(hx0 + s(3), y)] or [0]; hy0, hy1 = ys[0], ys[-1]
    edge = sum(br(x, y) for x in range(max(0, hx0 - s(3)), hx0 + 1) for y in range(hy0, hy1 + 1))
    lines = [y for y in range(hy1 - (hy1 - hy0) * 3 // 10, hy1) if sum(br(x, y) for x in range(hx0, hx1, 2)) * 2 > (hx1 - hx0) // 2]
    corner = [k for k in range(s(6), s(12)) if not near(hx1 - k, hy1 - k)]
    out(hx1 - hx0 > s(100) and not edge and not lines and not corner, "live-ss-boundary", "hole x%d..%d y%d..%d; bright px at "
        "sidebar edge %d, full-width lines in bottom 30%% %s, non-hole px on BR diagonal 6..12 %s (want all none)" % (hx0, hx1, hy0, hy1, edge, lines[:5], corner[:5]))
def main(a=sys.argv):
    kv = dict(x.split("=", 1) for x in a[3:] if "=" in x)
    rgb3 = lambda v: tuple(int(x) for x in v.split(","))
    if a[2] == "formlayout": return formlayout(__import__("json").loads(kv["fl"]))
    if a[2] == "pill":
        pill(a[1], rgb3(a[3]), float(a[4])); return boundary(a[1], rgb3(kv["frame"]), rgb3(kv["view"]), float(a[4]))
    if a[2] == "rows": connected("qml-rows", [pixrow(a[1], i) for i in range(6)], "fclfml")
    elif a[2] == "slider-radio": slider_radio(a[1], float(kv.get("handle") or -1))
    else: out(kv.get("seps") == "0", "formcard-separators", "%s of 2 FormDelegateSeparators visible (want 0)" % kv.get("seps"))
    if a[2] == "formcard": connected("formcard-rects", [("fc%d" % i, tuple(float(v) for v in x.split(":")[2].split("/")),
        float(x.split(":")[1])) for i, x in enumerate(filter(None, kv.get("fcrects", "").split(";")))], "fml")
main()
