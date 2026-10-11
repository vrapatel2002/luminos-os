# [CHANGE: claude-code | 2026-10-10] icons-mono probe for luminos-windowstyle-check. Usage: icons.py <theme> <icon>...
# Resolves each icon at 22 then 24 px (scale 1) through the theme's index.theme Inherits chain (+hicolor), like the
# freedesktop lookup; monochrome = <= 2 distinct fill/stroke/stop-color values on rendered elements (namedview/metadata
# skipped; ColorScheme-*/currentColor = 1). Proven 2026-10-10: Papirus-Dark sound/network = 4/3 colours -> FAIL; YAMIS = 1.
import configparser, gzip, os, re, sys, xml.etree.ElementTree as ET
ROOTS = [os.path.expanduser("~/.local/share/icons"), os.path.expanduser("~/.icons"), "/usr/share/icons"]
def theme_dirs(name):
    return [os.path.join(r, name) for r in ROOTS if os.path.isfile(os.path.join(r, name, "index.theme"))]
def index(name):
    cp = configparser.ConfigParser(interpolation=None, strict=False); cp.optionxform = str
    for d in theme_dirs(name): cp.read(os.path.join(d, "index.theme")); break
    return cp
def matches(sec, size):
    g = lambda k, dflt: int(sec.get(k, dflt))
    if g("Scale", 1) != 1: return False
    t, s = sec.get("Type", "Threshold"), g("Size", 0)
    if t == "Fixed": return s == size
    if t == "Scalable": return g("MinSize", s) <= size <= g("MaxSize", s)
    return abs(s - size) <= g("Threshold", 2)
def lookup(theme, icon, seen):
    if theme in seen or not theme_dirs(theme): return None
    seen.add(theme); cp = index(theme)
    subs = [d for d in cp.get("Icon Theme", "Directories", fallback="").split(",") if d and cp.has_section(d)]
    for size in (22, 24):
        for sub in (d for d in subs if matches(cp[d], size)):
            for base in theme_dirs(theme):
                for ext in (".svg", ".svgz", ".png"):
                    p = os.path.join(base, sub, icon + ext)
                    if os.path.isfile(p): return p
    for parent in cp.get("Icon Theme", "Inherits", fallback="").split(","):
        r = parent.strip() and lookup(parent.strip(), icon, seen)
        if r: return r
    return None
SKIP = ("namedview", "metadata", "style", "title", "desc")   # Inkscape page/desk colours never render
def colours(path):
    cs = set()
    def walk(e):
        if e.tag.split("}")[-1] in SKIP: return
        st = dict(kv.split(":", 1) for kv in e.get("style", "").replace(" ", "").split(";") if ":" in kv)
        for k in ("fill", "stroke", "stop-color"):
            v = (st.get(k) or e.get(k) or "").strip().lower()
            if v in ("", "none", "transparent", "inherit"): continue
            cs.add("<scheme-text>" if v == "currentcolor" or "ColorScheme-" in e.get("class", "") else v)
        for c in e: walk(c)
    if path.endswith(".png"): return None
    walk(ET.fromstring((gzip.open if path.endswith(".svgz") else open)(path, "rb").read())); return cs
def main():
    theme, icons = sys.argv[1], sys.argv[2:]; bad, notes = [], []
    if re.match(r"(?i)(papirus|yaru)", theme): bad.append("theme %s is Papirus/Yaru" % theme)
    for icon in icons:
        p = lookup(theme, icon, set()) or lookup("hicolor", icon, set())
        if not p: bad.append("%s not found at 22/24" % icon); continue
        cs = colours(os.path.realpath(p)); n = "png" if cs is None else len(cs)
        notes.append("%s=%s(%s)" % (icon, os.path.relpath(p, "/usr/share/icons") if p.startswith("/usr") else p, n))
        if cs is None or len(cs) > 2: bad.append("%s has %s colours" % (icon, n))
    print("%s icons-mono: theme '%s'; %s%s" % ("FAIL" if bad else "PASS", theme, " ".join(notes),
                                               ("; " + "; ".join(bad)) if bad else ""))
main()
