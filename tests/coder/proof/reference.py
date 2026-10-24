# Reference implementation of TASK.md (LUMA ranges) — used ONLY to validate the hidden tests.
# [CHANGE: claude-code | 2026-10-23] DECISION 157 proof harness.
import re
from functools import total_ordering

_ID = r"[0-9A-Za-z-]+"
_NUM = r"0|[1-9]\d*"
_FULL = re.compile(rf"^({_NUM})\.({_NUM})\.({_NUM})(?:-({_ID}(?:\.{_ID})*))?(?:\+({_ID}(?:\.{_ID})*))?$")

@total_ordering
class Version:
    def __init__(self, major, minor, patch, pre=(), build=()):
        self.major, self.minor, self.patch, self.pre, self.build = major, minor, patch, tuple(pre), tuple(build)
    @property
    def tup(self):
        return (self.major, self.minor, self.patch)
    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += "-" + ".".join(str(x) for x in self.pre)
        if self.build:
            s += "+" + ".".join(self.build)
        return s
    def __repr__(self):
        return f"Version({str(self)!r})"
    def _key_cmp(self, o):
        if self.tup != o.tup:
            return -1 if self.tup < o.tup else 1
        if not self.pre and not o.pre:
            return 0
        if not self.pre:
            return 1
        if not o.pre:
            return -1
        for a, b in zip(self.pre, o.pre):
            if a == b:
                continue
            ai, bi = isinstance(a, int), isinstance(b, int)
            if ai and bi:
                return -1 if a < b else 1
            if ai != bi:
                return -1 if ai else 1
            return -1 if a < b else 1
        if len(self.pre) == len(o.pre):
            return 0
        return -1 if len(self.pre) < len(o.pre) else 1
    def __eq__(self, o):
        return isinstance(o, Version) and self._key_cmp(o) == 0
    def __lt__(self, o):
        return self._key_cmp(o) < 0
    def __hash__(self):
        return hash((self.tup, self.pre))

def _pre_ids(s):
    out = []
    for p in s.split("."):
        if p.isdigit():
            if len(p) > 1 and p[0] == "0":
                raise ValueError(f"leading zero in numeric pre-release id {p!r}")
            out.append(int(p))
        else:
            out.append(p)
    return tuple(out)

def parse_version(s):
    if not isinstance(s, str):
        raise ValueError("not a string")
    t = s.strip()
    if t[:1] in ("v", "="):
        t = t[1:]
    m = _FULL.match(t)
    if not m:
        raise ValueError(f"invalid version {s!r}")
    pre = _pre_ids(m.group(4)) if m.group(4) else ()
    build = tuple(m.group(5).split(".")) if m.group(5) else ()
    return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre, build)

def compare(a, b):
    return parse_version(a)._key_cmp(parse_version(b))

# ---------- ranges ----------
# A comparator is (op, Version, excl_pre_upper) with op in {">", ">=", "<", "<=", "="} or ("none",) / ("any",)
_WILD = {"x", "X", "*"}

def _parse_partial(s):
    """-> (parts: list[int] of length 0..3, full Version or None)"""
    t = s
    if t[:1] in ("v", "="):
        t = t[1:]
    if not t:
        raise ValueError("empty version in range")
    if _FULL.match(t):
        return None, parse_version(t)
    comps = t.split(".")
    if len(comps) > 3:
        raise ValueError(f"too many components {s!r}")
    parts = []
    for c in comps:
        if c in _WILD:
            break
        if not re.fullmatch(_NUM, c):
            raise ValueError(f"bad component {c!r} in {s!r}")
        parts.append(int(c))
    else:
        if len(parts) == 3:  # 3 numeric comps but _FULL failed -> impossible unless pre/build junk
            raise ValueError(f"invalid {s!r}")
    # anything after first wildcard must still be numeric or wildcard
    seen = False
    for c in comps:
        if c in _WILD:
            seen = True
        elif seen and not re.fullmatch(_NUM, c):
            raise ValueError(f"bad component {c!r}")
    return parts, None

def V(a, b, c, pre=()):
    return Version(a, b, c, pre)

def _bump(parts):
    """upper exclusive bound for a partial: 1 -> 2.0.0, 1.2 -> 1.3.0"""
    if len(parts) == 1:
        return V(parts[0] + 1, 0, 0)
    return V(parts[0], parts[1] + 1, 0)

def _fill(parts):
    p = parts + [0] * (3 - len(parts))
    return V(*p)

ANY = [("any",)]
NONE = [("none",)]

def _desugar(op, text):
    """-> (list of comparators, has_pre_full: Version|None)"""
    parts, full = _parse_partial(text)
    if full is not None:
        hp = full if full.pre else None
        if op in ("", "="):
            return [("=", full)], hp
        if op in (">", ">=", "<", "<="):
            return [(op, full)], hp
        if op == "~":
            return [(">=", full), ("<", V(full.major, full.minor + 1, 0))], hp
        if op == "^":
            if full.major > 0:
                up = V(full.major + 1, 0, 0)
            elif full.minor > 0:
                up = V(0, full.minor + 1, 0)
            else:
                up = V(0, 0, full.patch + 1)
            return [(">=", full), ("<", up)], hp
        raise ValueError(op)
    # partial / wildcard
    n = len(parts)
    if n == 0:
        if op in (">", "<"):
            return NONE, None
        return ANY, None
    if op in ("", "=", "~"):
        if op == "~" and n == 2:
            return [(">=", _fill(parts)), ("<", _bump(parts))], None
        return [(">=", _fill(parts)), ("<", _bump(parts))], None
    if op == "^":
        if parts[0] > 0 or n == 1:
            up = V(parts[0] + 1, 0, 0)
        else:  # 0.y
            up = V(0, parts[1] + 1, 0)
        return [(">=", _fill(parts)), ("<", up)], None
    if op == ">":
        return [(">=", _bump(parts))], None
    if op == ">=":
        return [(">=", _fill(parts))], None
    if op == "<":
        return [("<", _fill(parts))], None
    if op == "<=":
        return [("<", _bump(parts))], None
    raise ValueError(op)

_OP = re.compile(r"^(>=|<=|>|<|=|~|\^)?\s*(.*)$")

def _parse_set(s):
    toks = s.split()
    comps, pres = [], []
    if not toks:
        return ANY, pres
    i = 0
    if "-" in toks:
        # hyphen range must be exactly: A - B
        if len(toks) != 3 or toks[1] != "-":
            raise ValueError(f"bad hyphen range {s!r}")
        a, b = toks[0], toks[2]
        pa, fa = _parse_partial(a)
        pb, fb = _parse_partial(b)
        lo = fa if fa is not None else _fill(pa)
        if fa is not None and fa.pre:
            pres.append(fa)
        out = [(">=", lo)] if (fa is not None or pa) else []
        if fb is not None:
            out.append(("<=", fb))
            if fb.pre:
                pres.append(fb)
        elif pb:
            out.append(("<", _bump(pb) if len(pb) < 3 else None))
        return (out or ANY), pres
    # join operator tokens that are separated from their version by whitespace
    merged = []
    while i < len(toks):
        t = toks[i]
        if t in (">=", "<=", ">", "<", "=", "~", "^"):
            if i + 1 >= len(toks):
                raise ValueError(f"operator without version in {s!r}")
            merged.append(t + toks[i + 1]); i += 2
        else:
            merged.append(t); i += 1
    for t in merged:
        m = _OP.match(t)
        op, rest = m.group(1) or "", m.group(2)
        if not rest or rest[0] in "<>=~^":
            raise ValueError(f"bad comparator {t!r}")
        c, hp = _desugar(op, rest)
        comps.extend(c)
        if hp is not None:
            pres.append(hp)
    return comps, pres

def _parse_range(r):
    if not isinstance(r, str):
        raise ValueError("range must be str")
    return [_parse_set(s) for s in r.split("||")]

def _ok(c, v):
    if c[0] == "any":
        return True
    if c[0] == "none":
        return False
    op, b = c
    k = v._key_cmp(b)
    if op == "=":
        return k == 0
    if op == ">":
        return k > 0
    if op == ">=":
        return k >= 0
    if op == "<=":
        return k <= 0
    if op == "<":
        if not b.pre and v.pre and v.tup == b.tup:
            return False  # upper bound excludes its own pre-releases
        return k < 0
    raise AssertionError(op)

def _sat(v, sets, include_pre):
    for comps, pres in sets:
        if not all(_ok(c, v) for c in comps):
            continue
        if v.pre and not include_pre and not any(p.tup == v.tup for p in pres):
            continue
        return True
    return False

def satisfies(version, range_str, include_pre=False):
    sets = _parse_range(range_str)
    return _sat(parse_version(version), sets, include_pre)

def max_satisfying(versions, range_str, include_pre=False):
    sets = _parse_range(range_str)
    best = None
    for s in versions:
        try:
            v = parse_version(s)
        except ValueError:
            continue
        if _sat(v, sets, include_pre) and (best is None or v > best[0]):
            best = (v, s)
    return best[1] if best else None
