Write a single Python 3 module `solution.py` (standard library only) implementing version ranges for a
package manager called LUMA. Follow this specification EXACTLY — it is deliberately NOT identical to npm/semver.

## 1. Versions
`parse_version(s: str) -> Version`
- Form: `MAJOR.MINOR.PATCH`, optionally followed by `-PRE` and/or `+BUILD`.
- MAJOR, MINOR, PATCH are non-negative decimal integers with NO leading zeros (`0` is fine, `01` is invalid).
- PRE is one or more dot-separated identifiers; each identifier is non-empty and uses only `[0-9A-Za-z-]`.
  An identifier made only of digits is "numeric" and must not have leading zeros (`0` ok, `007` invalid).
- BUILD is one or more dot-separated non-empty identifiers of `[0-9A-Za-z-]` (leading zeros allowed). BUILD is
  kept but IGNORED for ordering and matching.
- A single leading `v` or `=` is allowed and ignored (`v1.2.3`, `=1.2.3`). Surrounding whitespace is ignored.
- Anything else raises `ValueError`.
- `Version` must expose `.major .minor .patch` (ints), `.pre` (tuple of str|int, numeric identifiers as int,
  `()` if none), `.build` (tuple of str), and `str(v)` returns the canonical form without `v`/`=`
  (e.g. `str(parse_version(" v1.2.3-rc.1+b5 ")) == "1.2.3-rc.1+b5"`).

## 2. Ordering
`compare(a: str, b: str) -> int` returns -1, 0 or 1 (inputs are version strings).
Versions also support `< <= > >= == !=` with each other.
- Compare MAJOR, MINOR, PATCH numerically.
- If equal: a version WITH a pre-release is LOWER than the same version without one.
- Two pre-releases: compare identifier by identifier left to right. Numeric < alphanumeric. Two numerics compare
  numerically, two alphanumerics compare by ASCII. If all shared identifiers are equal, the one with MORE
  identifiers is HIGHER.
- BUILD never affects ordering: `1.0.0+a == 1.0.0+b`.

## 3. Ranges
`satisfies(version: str, range_str: str, include_pre: bool = False) -> bool`
`max_satisfying(versions: list[str], range_str: str, include_pre: bool = False) -> str | None`
  (returns the ORIGINAL string of the highest satisfying version, or None; invalid version strings in the list
  are skipped silently).

A range is one or more SETS separated by `||`; a version satisfies the range if it satisfies ANY set.
A set is one or more comparators separated by whitespace; ALL must hold. An empty set (empty string or only
spaces) means "any version". Whitespace between an operator and its version is allowed (`>= 1.2.3`).
An invalid range raises `ValueError` from `satisfies` / `max_satisfying` (e.g. `>=1.2.3.4`, `~>1`, `1.2.3 -`,
`a.b.c`, `||` with an empty side is NOT invalid: it is an empty set = any version).

Partial versions are allowed inside ranges: `1`, `1.2`, and wildcards `x`, `X`, `*` in any position at or after
the first wildcard (`1.x`, `1.2.*`, `*`). Once a component is a wildcard, every later component is treated as a
wildcard too (`1.x.3` means `1.x.x`). A partial version may not carry a pre-release.

### 3.1 Comparator desugaring (this table is the law)
| Comparator | Means |
|---|---|
| `1.2.3` or `=1.2.3` | `=1.2.3` (exact; build metadata ignored) |
| `*`, `x`, empty | any version |
| `1` / `1.x` | `>=1.0.0 <2.0.0` |
| `1.2` / `1.2.x` | `>=1.2.0 <1.3.0` |
| `>1.2.3` | `>1.2.3` |
| `>1.2` | `>=1.3.0` |
| `>1` | `>=2.0.0` |
| `>=1.2` | `>=1.2.0` |
| `<1.2` | `<1.2.0` |
| `<=1.2` | `<1.3.0` |
| `<=1` | `<2.0.0` |
| `>*` or `<*` | matches NOTHING |
| `>=*` or `<=*` | any version |
| `~1.2.3` | `>=1.2.3 <1.3.0` |
| `~1.2` | `>=1.2.0 <1.3.0` |
| `~1` | `>=1.0.0 <2.0.0` |
| `~0.2.3` | `>=0.2.3 <0.3.0` |
| `^1.2.3` | `>=1.2.3 <2.0.0` |
| `^0.2.3` | `>=0.2.3 <0.3.0` |
| `^0.0.3` | `>=0.0.3 <0.0.4` |
| `^0.0` | `>=0.0.0 <0.1.0` |
| `^0` | `>=0.0.0 <1.0.0` |
| `^1.2` | `>=1.2.0 <2.0.0` |
| `A - B` (spaces around `-` required) | `>=A' <=B'` where a partial A fills missing parts with 0, and a partial B means "up to the end of that partial": `1.2 - 2.3` = `>=1.2.0 <2.4.0`, `1 - 2` = `>=1.0.0 <3.0.0`, `1.2.3 - 2.3.4` = `>=1.2.3 <=2.3.4` |

`~` and `^` may be followed by a FULL version with a pre-release (`^1.2.3-beta.2` = `>=1.2.3-beta.2 <2.0.0`).
Upper bounds produced by the table (`<2.0.0` etc.) EXCLUDE every pre-release of that upper version
(`2.0.0-rc.1` does NOT satisfy `^1.2.3`) — note this is different from plain ordering, where 2.0.0-rc.1 < 2.0.0.
A user-written `<2.0.0` also excludes `2.0.0-*`.

### 3.2 Pre-release rule
If `include_pre` is False, a version that HAS a pre-release satisfies a set only if (a) it satisfies every
comparator of the set AND (b) at least one comparator in THAT SAME set was written with a full version that has
a pre-release and the same MAJOR.MINOR.PATCH as the candidate. Example: `1.2.3-rc.2` satisfies `>=1.2.3-rc.1`
but not `>=1.2.2`; `1.2.4-rc.1` does not satisfy `>=1.2.3-rc.1` (different tuple).
If `include_pre` is True, pre-releases are matched purely by ordering — EXCEPT that the upper-bound exclusion of
3.1 still applies (`2.0.0-rc.1` still fails `^1.2.3` even with include_pre=True).

Examples:
```
satisfies("1.2.7", "^1.2.3") -> True
satisfies("1.3.0", "~1.2.3") -> False
satisfies("0.3.1", "^0.2.3 || ^0.3.0") -> True
max_satisfying(["1.2.3", "1.2.4-rc.1", "1.2.4", "bogus"], "~1.2") -> "1.2.4"
```
