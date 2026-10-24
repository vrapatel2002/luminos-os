# Hidden tests for TASK.md (LUMA ranges). The writer never sees these. [CHANGE: claude-code | 2026-10-23]
import pytest
import solution as S

SAT = [
    # (version, range, include_pre, expected)
    ("1.2.7", "^1.2.3", False, True),
    ("1.3.0", "~1.2.3", False, False),
    ("0.3.1", "^0.2.3 || ^0.3.0", False, True),
    ("1.2.3", "", False, True),
    ("1.2.3", "   ", False, True),
    ("1.2.3", "*", False, True),
    ("1.2.3-rc.1", "*", False, False),
    ("1.2.3-rc.1", "*", True, True),
    ("1.9.9", "1", False, True),
    ("2.0.0", "1.x", False, False),
    ("1.2.9", "1.2", False, True),
    ("1.3.0", "1.2.*", False, False),
    ("1.3.0", ">1.2", False, True),
    ("1.2.9", ">1.2", False, False),
    ("1.9.9", ">1", False, False),
    ("2.0.0", ">1", False, True),
    ("1.2.0", ">=1.2", False, True),
    ("1.1.9", "<1.2", False, True),
    ("1.2.0", "<1.2", False, False),
    ("1.2.9", "<=1.2", False, True),
    ("1.3.0", "<=1.2", False, False),
    ("1.9.9", "<=1", False, True),
    ("2.0.0", "<=1", False, False),
    ("9.9.9", ">*", False, False),
    ("0.0.0", "<*", False, False),
    ("9.9.9", ">=*", False, True),
    ("1.2.9", "~1.2", False, True),
    ("1.9.0", "~1", False, True),
    ("0.2.9", "~0.2.3", False, True),
    ("0.3.0", "~0.2.3", False, False),
    ("0.2.9", "^0.2.3", False, True),
    ("0.3.0", "^0.2.3", False, False),
    ("0.0.3", "^0.0.3", False, True),
    ("0.0.4", "^0.0.3", False, False),
    ("0.0.9", "^0.0", False, True),
    ("0.1.0", "^0.0", False, False),
    ("0.9.9", "^0", False, True),
    ("1.0.0", "^0", False, False),
    ("1.9.0", "^1.2", False, True),
    ("2.3.9", "1.2 - 2.3", False, True),
    ("2.4.0", "1.2 - 2.3", False, False),
    ("1.1.9", "1.2 - 2.3", False, False),
    ("2.9.9", "1 - 2", False, True),
    ("2.3.4", "1.2.3 - 2.3.4", False, True),
    ("2.3.5", "1.2.3 - 2.3.4", False, False),
    ("2.0.0-rc.1", "^1.2.3", False, False),
    ("2.0.0-rc.1", "^1.2.3", True, False),          # upper bound excludes its own pre-releases even with include_pre
    ("2.0.0-rc.1", "<2.0.0", True, False),          # user-written < too
    ("1.9.9-rc.1", "<2.0.0", True, True),
    ("1.2.3-rc.2", ">=1.2.3-rc.1", False, True),
    ("1.2.3-rc.2", ">=1.2.2", False, False),
    ("1.2.4-rc.1", ">=1.2.3-rc.1", False, False),   # different tuple
    ("1.2.4-rc.1", ">=1.2.3-rc.1", True, True),
    ("1.2.3-beta.3", "^1.2.3-beta.2", False, True),
    ("1.2.3-beta.1", "^1.2.3-beta.2", False, False),
    ("1.2.3-beta.2", "~1.2.3-beta.2", False, True),
    ("1.2.3-rc.1", ">=1.2.3-rc.1 || >=9.0.0", False, True),
    ("1.2.3-rc.2", "<1.2.3-rc.5 >1.0.0", False, False),  # pre comparator in set has same tuple? <1.2.3-rc.5 does -> True actually
    ("1.2.3", ">= 1.2.3", False, True),
    ("1.2.3+build.9", "=1.2.3", False, True),
    ("1.2.3", "=1.2.3+other", False, True),
    ("1.5.0", "1.x.3", False, True),
    ("3.4.5", "x.2.3", False, True),
    ("1.2.3", "v1.2.3", False, True),
    ("1.2.3", "1.2.3 ||", False, True),
    ("5.0.0", "|| 1.2.3", False, True),
    ("1.2.3", "1.2.3-2.3.4", False, False),         # no spaces: that is a pre-release, not a hyphen range
    ("1.2.3-2.3.4", "1.2.3-2.3.4", False, True),
    ("1.2.3", ">1.2.3", False, False),
    ("1.2.4", ">1.2.3 <1.2.5", False, True),
    ("1.2.5", ">1.2.3 <1.2.5", False, False),
    ("0.0.1", "* - 2", False, True),
]
# fix the one deliberately-reasoned case: candidate 1.2.3-rc.2, set has <1.2.3-rc.5 (same tuple, pre) -> allowed;
# 1.2.3-rc.2 < 1.2.3-rc.5 and > 1.0.0 -> True
SAT = [(v, r, p, True) if (v, r) == ("1.2.3-rc.2", "<1.2.3-rc.5 >1.0.0") else (v, r, p, e) for v, r, p, e in SAT]

@pytest.mark.parametrize("v,r,p,e", SAT, ids=[f"{v}|{r}|{p}" for v, r, p, _ in SAT])
def test_satisfies(v, r, p, e):
    assert S.satisfies(v, r, include_pre=p) is e

CMP = [
    ("1.0.0", "2.0.0", -1), ("2.0.0", "2.0.0", 0), ("2.1.0", "2.0.9", 1),
    ("1.0.0-alpha", "1.0.0", -1), ("1.0.0-alpha", "1.0.0-alpha.1", -1), ("1.0.0-alpha.1", "1.0.0-alpha.beta", -1),
    ("1.0.0-alpha.beta", "1.0.0-beta", -1), ("1.0.0-beta.2", "1.0.0-beta.11", -1), ("1.0.0-beta.11", "1.0.0-rc.1", -1),
    ("1.0.0-rc.1", "1.0.0", -1), ("1.0.0+a", "1.0.0+b", 0), ("10.0.0", "9.0.0", 1), ("1.0.0-1", "1.0.0-a", -1),
    ("1.0.0-B", "1.0.0-a", -1),
]

@pytest.mark.parametrize("a,b,e", CMP)
def test_compare(a, b, e):
    assert S.compare(a, b) == e

BAD_V = ["1.2", "01.2.3", "1.02.3", "1.2.3-", "1.2.3-01", "1.2.3+", "1.2.3-a..b", "a.b.c", "1.2.3.4", "", "vv1.2.3",
         "1.2.3-a_b"]

@pytest.mark.parametrize("s", BAD_V)
def test_bad_version(s):
    with pytest.raises(ValueError):
        S.parse_version(s)

def test_version_fields():
    v = S.parse_version(" v1.2.3-rc.1+b5 ")
    assert (v.major, v.minor, v.patch) == (1, 2, 3)
    assert v.pre == ("rc", 1) and v.build == ("b5",)
    assert str(v) == "1.2.3-rc.1+b5"
    assert S.parse_version("1.2.3-007a").pre == ("007a",)
    assert S.parse_version("1.0.0+001").build == ("001",)

def test_version_ops():
    a, b = S.parse_version("1.0.0-rc.1"), S.parse_version("1.0.0")
    assert a < b and b > a and a <= b and a != b
    assert S.parse_version("1.0.0+x") == S.parse_version("1.0.0+y")

BAD_R = [">=1.2.3.4", "~>1", "1.2.3 -", "a.b.c", ">=", "1.2-rc"]  # only cases the spec states

@pytest.mark.parametrize("r", BAD_R)
def test_bad_range(r):
    with pytest.raises(ValueError):
        S.satisfies("1.2.3", r)

def test_max_satisfying():
    assert S.max_satisfying(["1.2.3", "1.2.4-rc.1", "1.2.4", "bogus"], "~1.2") == "1.2.4"
    assert S.max_satisfying(["1.2.3", "1.2.4-rc.1", "bogus"], "~1.2") == "1.2.3"
    assert S.max_satisfying(["1.2.3", "1.2.4-rc.1"], "~1.2", include_pre=True) == "1.2.4-rc.1"
    assert S.max_satisfying([" v2.0.0 ", "1.9.9"], "*") == " v2.0.0 "
    assert S.max_satisfying(["3.0.0"], "^1") is None
    assert S.max_satisfying([], "*") is None
    with pytest.raises(ValueError):
        S.max_satisfying(["1.0.0"], "~>1")
