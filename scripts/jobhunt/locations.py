#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-05]
# ============================================
# Location classifier for remote job postings.
# PURPOSE: Decide whether a posting can actually put a Canada-resident on payroll.
#          "Remote" is not a location. "Remote - US" cannot hire you; "Remote -
#          Worldwide" can. This single function is the whole funnel.
# DEPS: stdlib only.
# ============================================

import re

# Buckets, best -> worst. OPEN_BUCKETS are the ones worth an application.
CANADA = "canada"
GLOBAL = "global"
AMERICAS = "americas"
US_ONLY = "us_only"
OTHER_COUNTRY = "other_country"
ONSITE = "onsite"
UNKNOWN = "unknown"

OPEN_BUCKETS = (CANADA, GLOBAL, AMERICAS)

_CANADA = re.compile(
    r"\bcanada\b|\bcanadian\b|\bontario\b|\bquebec\b|\bqu[ée]bec\b|\balberta\b"
    r"|\bmanitoba\b|\bsaskatchewan\b|\bnova scotia\b|\bnew brunswick\b"
    r"|\bnewfoundland\b|british columbia|\bbc\b|\bon, ca\b"
    r"|\btoronto\b|\bottawa\b|\bmontreal\b|\bmontr[ée]al\b|\bvancouver\b"
    r"|\bcalgary\b|\bedmonton\b|\bwaterloo\b|\bkitchener\b|\bmississauga\b"
    r"|\bhamilton\b|\bwinnipeg\b|\bhalifax\b|\bvictoria, bc\b|\bburnaby\b"
    # [CHANGE: claude-code | 2026-08-26] His own city. Without it
    # "Sault Ste Marie, ON" matched no country at all and fell through to
    # ONSITE — the single place on earth where an on-site job costs him no
    # move was the one the filter threw away. Bare "ON" is deliberately not a
    # Canada token (too many false hits on the English word), so the city has
    # to be named. Must stay in step with profile.yaml `identity.location`.
    r"|sault\s+ste?\.?\s+marie|sault\s+sainte\s+marie",
    re.I,
)

# "Anywhere", "Worldwide", "Global", or a bare "Remote" with no country qualifier.
_GLOBAL = re.compile(
    r"\banywhere\b|\bworld\s*wide\b|\bworldwide\b|\bglobal\b|\bany location\b"
    r"|\bfully remote\b|\blocation:?\s*flexible\b|\bno location\b|\bemea/amer\b",
    re.I,
)
_BARE_REMOTE = re.compile(r"^\s*(100%\s*)?remote\s*$", re.I)

# [CHANGE: claude-code | 2026-08-06] "Anywhere IN <somewhere>" is a scope, not a
# lack of one. WeWorkRemotely writes "Anywhere in France, Belgium, Spain" and the
# bare \banywhere\b in _GLOBAL above matched it, so 16 European-only roles landed
# in the Canadian pool and got scored on the GPU. Caught by reading the pool's
# location column, not by a test — the unit tests all passed.
#
# The negative lookahead is what keeps "Anywhere in the World" global. Note this
# deliberately does NOT catch "Worldwide (excl. China)": an exclusion list is
# still worldwide, and treating a named country as a scope there would be the
# same bug pointing the other way.
_SCOPED_ANYWHERE = re.compile(r"\banywhere\s+in\s+(?!the\s+world\b)", re.I)

_AMERICAS = re.compile(r"\bamericas\b|north america|\blatam\b|latin america", re.I)

_US = re.compile(
    r"united states|\bu\.?s\.?a\.?\b|\bus\b|\busa\b|\bstateside\b"
    r"|new york|san francisco|\bseattle\b|\baustin\b|\bboston\b|\bchicago\b"
    r"|\bdenver\b|\batlanta\b|los angeles|\bnyc\b|\bsf\b|bay area|\bmiami\b"
    r"|\bportland\b|\bdallas\b|\bhouston\b|\bphoenix\b|san jose|\bwashington\b"
    r"|\bvirginia\b|\bcalifornia\b|\btexas\b|\bflorida\b|\bcolorado\b",
    re.I,
)

# Countries that are neither Canada nor US. A "Remote - Germany" role needs
# German work authorisation and German payroll; it is not open to you.
_OTHER = re.compile(
    r"\bindia\b|\bgermany\b|\bfrance\b|\bspain\b|\bportugal\b|\bpoland\b"
    r"|\bnetherlands\b|\bireland\b|\bunited kingdom\b|\bu\.?k\.?\b|\blondon\b"
    r"|\bberlin\b|\bparis\b|\bmadrid\b|\bamsterdam\b|\bdublin\b|\bwarsaw\b"
    r"|\blisbon\b|\bbangalore\b|\bbengaluru\b|\bmumbai\b|\bdelhi\b|\bpune\b"
    r"|\bhyderabad\b|\bsingapore\b|\bjapan\b|\btokyo\b|\bchina\b|\bbeijing\b"
    r"|\bshanghai\b|\baustralia\b|\bsydney\b|\bmelbourne\b|\bbrazil\b"
    r"|\bmexico\b|\bargentina\b|\bcolombia\b|\bisrael\b|\btel aviv\b"
    r"|\bemea\b|\bapac\b|\beurope\b|\beuropean union\b|\beu\b|\bnordics\b"
    r"|\bswitzerland\b|\bzurich\b|\bsweden\b|\bstockholm\b|\bkorea\b|\bseoul\b"
    r"|\btaiwan\b|\bvietnam\b|\bphilippines\b|\bindonesia\b|\bnigeria\b"
    r"|\bkenya\b|\bsouth africa\b|\begypt\b|\bturkey\b|\bdubai\b|\buae\b",
    re.I,
)

_REMOTE_HINT = re.compile(r"\bremote\b|\banywhere\b|\bwork from home\b|\bwfh\b|\bdistributed\b", re.I)

# [CHANGE: claude-code | 2026-08-26] BUG-139. HYBRID WAS NEVER FILTERED.
#
# `_CANADA` matched first and returned CANADA immediately, so "Hybrid - Toronto,
# ON" came back `canada`, `is_open=True`, and went into the pool to be scored.
# The profile says `remote_required: true`; the classifier did not implement it.
# This is a rules bug, so it costs nothing to fix and nothing to re-crawl —
# score.py recomputes the bucket every rules pass (the BUG-107 consequence).
#
# Found by TESTING THE CLAIM, not by a failing test: I had told Shawn that
# locations.py "kills hybrid", then ran classify() on five hybrid strings and
# all five came back open. The 17 built-in unit tests passed throughout, because
# none of them contained the word "hybrid" — the same shape as BUG-107.
# `in-person` is DELIBERATELY NOT HERE. It caught "Remote (Canada) - occasional
# in-person offsites", which is a fully remote job with a team retreat. The
# asymmetry decides it: a false accept wastes one 8-second scoring call, a false
# reject silently deletes a job he could have had. When in doubt, keep it and
# let the model read the requirements.
_HYBRID = re.compile(
    r"\bhybrid\b|\bon[\s-]?site\b|\bin[\s-]?office\b"
    r"|\d\s*days?\s*(a|per)\s*week\s*in\b|\brelocation\s*(is\s*)?required\b"
    r"|\bmust\s+relocate\b",
    re.I,
)

# The ONE exception, confirmed by Shawn 2026-08-26: he will take a hybrid role
# in his own city, because that involves no move. Anywhere else, hybrid means
# relocating, which is the thing he is explicitly not doing.
#
# HARDCODED ON PURPOSE, and this is the haste decision: the honest version reads
# `identity.location` out of profile.yaml, but classify() is called from both
# ingest.py and score.py and neither carries the profile, so plumbing it through
# is two signature changes to save one line. If Shawn moves, edit this regex —
# it must stay in step with profile.yaml's `identity.location`.
_LOCAL_CITY = re.compile(r"sault\s+ste?\.?\s+marie|sault\s+sainte\s+marie", re.I)


def is_remote(location, title="", extra=""):
    """True if the posting looks like a work-from-home role."""
    return bool(_REMOTE_HINT.search(" ".join(filter(None, (location, title, extra)))))


def classify(location, title="", extra=""):
    """Map a free-text location to a hireability bucket.

    Returns one of CANADA, GLOBAL, AMERICAS, US_ONLY, OTHER_COUNTRY, ONSITE, UNKNOWN.

    Order matters. Canada wins outright: a "Remote - US, Canada" posting is open
    to you even though it also names the US. Global beats a country mention for
    the same reason -- "Worldwide (excl. China)" is still worldwide.
    """
    loc = (location or "").strip()
    if not loc:
        # Some boards leave location blank on remote-native listings.
        return GLOBAL if _GLOBAL.search(title or "") or _BARE_REMOTE.search(title or "") else UNKNOWN

    # [CHANGE: claude-code | 2026-08-26] BUG-139. This must run BEFORE the
    # country checks, because _CANADA matches "Hybrid - Toronto" and returns
    # CANADA on the spot. A desk requirement is a harder constraint than a
    # country: being allowed to work in Ontario does not mean being able to
    # drive to Toronto.
    #
    # Checked against loc AND title because boards split it both ways —
    # Greenhouse puts "Hybrid" in the location, Lever often in the title.
    if _HYBRID.search(loc) or _HYBRID.search(title or ""):
        # His own city is the exception: hybrid here means no move at all.
        if _LOCAL_CITY.search(loc):
            return CANADA
        return ONSITE

    if _CANADA.search(loc):
        return CANADA
    # "Anywhere in France, Belgium, Spain" reads as global to a bare keyword
    # match and is not. Skip the global branch entirely so the country checks
    # below get their turn. Canada was already checked above, so a listing that
    # names Canada among its scopes has already been kept.
    if _SCOPED_ANYWHERE.search(loc):
        if _OTHER.search(loc):
            return OTHER_COUNTRY
        if _US.search(loc):
            return US_ONLY
    elif _GLOBAL.search(loc) or _BARE_REMOTE.search(loc):
        # Aggregators (notably WeWorkRemotely) stamp "Anywhere in the World" on
        # the feed even when the posting itself is pinned to one country. Trust
        # a hard constraint in the title over the board's generic label.
        t = title or ""
        if _CANADA.search(t):
            return CANADA
        if _OTHER.search(t):
            return OTHER_COUNTRY
        if _US.search(t):
            return US_ONLY
        return GLOBAL
    if _AMERICAS.search(loc):
        return AMERICAS
    if _US.search(loc):
        return US_ONLY
    if _OTHER.search(loc):
        return OTHER_COUNTRY

    # Named somewhere we do not recognise. If it reads remote, keep it for review
    # rather than silently discarding a possible match.
    return UNKNOWN if is_remote(loc, title, extra) else ONSITE


def is_open(location, title="", extra=""):
    """True if this posting can plausibly hire a Canada-resident."""
    return classify(location, title, extra) in OPEN_BUCKETS


if __name__ == "__main__":
    CASES = [
        ("Toronto, Canada", CANADA),
        ("Remote - Canada", CANADA),
        ("Remote - US, Canada", CANADA),
        ("Ottawa, ON", CANADA),
        ("Remote - Worldwide", GLOBAL),
        ("Anywhere", GLOBAL),
        ("Remote", GLOBAL),
        ("Worldwide (excl. China)", GLOBAL),
        # [CHANGE: claude-code | 2026-08-06] the scoped-anywhere regressions.
        # All four of these were classified GLOBAL before the fix.
        ("Anywhere in the World", GLOBAL),
        ("Anywhere in France, Belgium, Spain", OTHER_COUNTRY),
        ("Anywhere in France", OTHER_COUNTRY),
        ("Anywhere in France, Belgium, Spain | Toronto, ON, Canada", CANADA),
        ("Anywhere in the US", US_ONLY),
        ("Americas, Europe, Asia, Africa, Oceania", AMERICAS),
        ("North America", AMERICAS),
        ("United States", US_ONLY),
        ("Remote - US", US_ONLY),
        ("San Francisco, CA", US_ONLY),
        ("Berlin, Germany", OTHER_COUNTRY),
        ("Remote - India", OTHER_COUNTRY),
        ("London, United Kingdom", OTHER_COUNTRY),
        ("", UNKNOWN),
    ]
    # Aggregator says "anywhere" but the title pins a country.
    TITLED = [
        ("Anywhere in the World", "Customer Engineer, India (Based in Mumbai)", OTHER_COUNTRY),
        ("Anywhere in the World", "Account Executive, US Federal", US_ONLY),
        ("Anywhere in the World", "Backend Engineer, Toronto", CANADA),
        ("Anywhere in the World", "Senior Backend Engineer", GLOBAL),
    ]
    bad = 0
    for loc, want in CASES:
        got = classify(loc)
        flag = "ok " if got == want else "FAIL"
        if got != want:
            bad += 1
        print(f"  {flag} {loc!r:45} -> {got:14} (want {want})")
    for loc, title, want in TITLED:
        got = classify(loc, title)
        flag = "ok " if got == want else "FAIL"
        if got != want:
            bad += 1
        print(f"  {flag} {title[:45]!r:47} -> {got:14} (want {want})")
    total = len(CASES) + len(TITLED)
    print(f"\n{total - bad}/{total} passed")
    raise SystemExit(1 if bad else 0)
