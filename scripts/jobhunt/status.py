#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-06]
# ============================================
# The dashboard. One screen that answers "is this thing working?"
# PURPOSE: a "just look at progress" surface. This is that surface.
# DEPS: stdlib only.
# USAGE:
#   ./status.py              # everything: health, funnel, top matches
#   ./status.py --top 25     # more of the shortlist
#   ./status.py --why <id>   # what the model actually thought about one job
#   ./status.py --rejects    # a sample of what the filter threw away
#   ./status.py --short      # two lines, for a status bar or a cron mail
# ============================================
#
# WHY THIS IS READ-ONLY: it must be safe to run at any moment, including while
# the nightly pipeline is mid-scoring. It opens the database in read-only mode
# so it physically cannot take a write lock and stall the run it is reporting on.

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta

DB_PATH = os.path.expanduser("~/.local/share/luminos/jobhunt.db")

UNITS = [
    ("jobhunt-pipeline.timer", "nightly run",
     "systemctl --user enable --now jobhunt-pipeline.timer"),
    ("openclaw-gateway.service", "control UI",
     "systemctl --user enable --now openclaw-gateway"),
    ("jobhunt-llm.service", "local model",
     "(on demand — idle is correct)"),
]

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")
if not sys.stdout.isatty():
    BOLD = DIM = GREEN = YELLOW = RED = RESET = ""


def open_ro(path):
    # mode=ro via URI. Passing the plain path would open read-write and could
    # block the pipeline; this cannot.
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def unit_state(unit):
    r = subprocess.run(["systemctl", "--user", "is-active", unit],
                       capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def counts(conn):
    # One role, one row in the funnel. A dedup group can legitimately hold two
    # statuses at once — Twilio posting the same job for Canada and for the US
    # means the Canadian row is scored while its us_only twin stays filtered.
    # Counting DISTINCT dedup_key per status counted that group twice, so the
    # funnel summed to more than the crawl total. Collapse each group to its
    # furthest-along status instead, so the columns actually add up.
    #
    # This leans on a documented SQLite behaviour: in a query whose only
    # aggregate is a single MIN()/MAX(), a bare column takes its value from the
    # row that produced that min. So `s` is the status of the best-ranked row in
    # the group. This is NOT portable to other databases — if this ever moves
    # off SQLite, rewrite it as a window function.
    out = {}
    for status, n in conn.execute(
            "SELECT s, COUNT(*) FROM ("
            "  SELECT dedup_key, MIN(CASE COALESCE(status,'new')"
            "      WHEN 'applied'   THEN 1 WHEN 'shortlist' THEN 2"
            "      WHEN 'scored'    THEN 3 WHEN 'pool'      THEN 4"
            "      WHEN 'filtered'  THEN 5 ELSE 6 END) AS rank,"
            "    COALESCE(status,'new') AS s"
            "  FROM jobs GROUP BY dedup_key) GROUP BY s", ):
        out[status] = n
    return out


def health(conn):
    print(f"\n{BOLD}  PIPELINE{RESET}")
    print("  " + "-" * 66)

    # Freshness first — a healthy-looking service list means nothing if the
    # data behind it is three weeks old.
    last = conn.execute("SELECT MAX(last_seen) FROM jobs").fetchone()[0]
    if last:
        try:
            # ingest.py writes timezone-AWARE stamps ("...+00:00"); score.py
            # writes naive local ones. Subtracting one from the other raises.
            # Normalise to aware-UTC rather than stripping the offset, so the
            # "hours ago" number stays right instead of quietly drifting by
            # however far Ontario is from UTC.
            when = datetime.fromisoformat(last)
            if when.tzinfo is None:
                when = when.astimezone()
            age = datetime.now().astimezone() - when
            hrs = age.total_seconds() / 3600
            mark = GREEN + "ok" if hrs < 36 else (YELLOW + "stale" if hrs < 24 * 7
                                                  else RED + "STALE")
            print(f"  {'jobs last fetched':<28}{mark}{RESET}  "
                  f"{last[:16].replace('T', ' ')}  ({hrs:.0f}h ago)")
        except ValueError:
            print(f"  {'jobs last fetched':<28}{last}")

    scored = conn.execute("SELECT MAX(scored_at) FROM jobs"
                          " WHERE scored_at IS NOT NULL").fetchone()[0]
    # Slice only a real timestamp. Slicing the fallback too chopped the advice
    # to "never — run ./score", which is not a command anyone can run.
    print(f"  {'last scored':<28}"
          f"{scored[:19].replace('T', ' ') if scored else 'never — run ./score.py'}")

    for unit, label, fix in UNITS:
        st = unit_state(unit)
        if unit == "jobhunt-llm.service":
            # Inactive is the GOOD state here. This unit holds 4.6 GB of VRAM and
            # keeps the dGPU awake; score.py starts and stops it around a run.
            colour = GREEN if st == "inactive" else YELLOW
            note = "idle (correct — GPU asleep)" if st == "inactive" else "running"
            print(f"  {label:<28}{colour}{st:<10}{RESET}{DIM}{note}{RESET}")
            continue
        colour = GREEN if st == "active" else RED
        print(f"  {label:<28}{colour}{st:<10}{RESET}"
              f"{'' if st == 'active' else DIM + fix + RESET}")


def funnel(conn, c):
    total = conn.execute("SELECT COUNT(DISTINCT dedup_key) FROM jobs").fetchone()[0]
    print(f"\n{BOLD}  FUNNEL{RESET}  {DIM}(distinct roles — the same job on three "
          f"boards counts once){RESET}")
    print("  " + "-" * 66)
    rows = [
        ("crawled", total, "everything ingest.py has ever seen"),
        ("not yet filtered", c.get("new", 0), "run ./score.py --rules-only"),
        ("cut by free rules", c.get("filtered", 0), "cost nothing — see --rejects"),
        ("waiting on the model", c.get("pool", 0), "run ./score.py"),
        ("scored, below the bar", c.get("scored", 0), ""),
        ("SHORTLIST", c.get("shortlist", 0), "worth your time"),
        ("applied", c.get("applied", 0), ""),
    ]
    for label, n, note in rows:
        if n == 0 and label in ("not yet filtered", "applied"):
            continue
        hl = BOLD + GREEN if label == "SHORTLIST" else ""
        print(f"  {hl}{label:<24}{n:>7,}{RESET}  {DIM}{note}{RESET}")

    if c.get("filtered") and not c.get("scored") and not c.get("shortlist"):
        print(f"\n  {DIM}nothing scored yet — the free pass has run, the model "
              f"has not{RESET}")


def shortlist(conn, n):
    rows = conn.execute(
        "SELECT id, score, company, title, location, score_reason FROM jobs"
        " WHERE status IN ('shortlist','scored') AND score IS NOT NULL"
        " GROUP BY dedup_key ORDER BY score DESC, first_seen DESC LIMIT ?",
        (n,)).fetchall()
    if not rows:
        return
    print(f"\n{BOLD}  BEST MATCHES{RESET}")
    print("  " + "-" * 92)
    print(f"  {'id':10}{'fit':>4}  {'company':20}{'title':40}{'why'}")
    for jid, score, company, title, loc, reason in rows:
        why = ""
        try:
            why = (json.loads(reason) or {}).get("one_line_why", "")
        except (TypeError, ValueError):
            why = (reason or "")[:40]
        colour = GREEN if score >= 75 else (YELLOW if score >= 60 else DIM)
        print(f"  {jid[:8]:10}{colour}{score:>4}{RESET}  {(company or '?')[:19]:20}"
              f"{(title or '?')[:39]:40}{DIM}{why[:44]}{RESET}")
    print(f"\n  {DIM}./status.py --why <id>   full reasoning for one job{RESET}")
    print(f"  {DIM}./browse.py --show <id>  the original posting{RESET}")


def why(conn, jid):
    r = conn.execute(
        "SELECT company,title,location,url,score,score_reason,status,"
        "filter_reason,lane FROM jobs WHERE id LIKE ?", (jid + "%",)).fetchone()
    if not r:
        sys.exit(f"no job matching {jid}")
    company, title, loc, url, score, reason, status, frs, lane = r
    print(f"\n{BOLD}  {title}{RESET}\n  {company}  |  {loc}\n  {url}")
    print(f"\n  status   {status}")
    if frs:
        print(f"  cut by   {frs}   {DIM}(a free rule — no model involved){RESET}")
        print(f"\n  {DIM}to stop cutting jobs like this, edit targets.yaml and "
              f"re-run ./score.py --rules-only{RESET}\n")
        return
    if lane:
        print(f"  lane     {lane}")
    if score is None:
        print("\n  not scored yet — run ./score.py\n")
        return
    print(f"  fit      {score}/100\n")
    try:
        d = json.loads(reason)
    except (TypeError, ValueError):
        print(f"  {reason}\n")
        return
    print(f"  {d.get('one_line_why', '')}\n")
    # Show the model's raw findings next to the derived score, so "why is this
    # a 58" is answerable without re-running the GPU. These are the inputs to
    # compute_score() in score.py — if the score looks wrong, one of these is
    # the reason, and the fix is usually a targets.yaml number rather than code.
    yrs = d.get("years_required")
    print(f"  subject-matter fit   {d.get('fit_signal', '?')}")
    print(f"  years demanded       {'not stated' if not yrs else yrs}")
    print(f"  degree required      {'yes' if d.get('degree_required') else 'no'}"
          f"{DIM}  (you have one — costs nothing){RESET}")
    if d.get("hard_blocker"):
        print(f"  {RED}hard blocker         yes — capped at 25{RESET}")
    for label, key in (("knockout risks", "knockout_risks"),
                       ("missing skills", "missing_skills")):
        items = d.get(key) or []
        print(f"\n  {label}" + ("" if items else f"  {DIM}none{RESET}"))
        for it in items:
            print(f"    - {it}")
    print()


def rejects(conn, n):
    print(f"\n{BOLD}  WHAT THE FILTER THREW AWAY{RESET}  "
          f"{DIM}(sample — check this before trusting the shortlist){RESET}")
    print("  " + "-" * 86)
    for reason, in conn.execute(
            "SELECT DISTINCT filter_reason FROM jobs WHERE filter_reason"
            " IS NOT NULL ORDER BY 1"):
        rows = conn.execute(
            "SELECT company,title FROM jobs WHERE filter_reason=?"
            " GROUP BY dedup_key ORDER BY RANDOM() LIMIT ?", (reason, n)).fetchall()
        tot = conn.execute("SELECT COUNT(DISTINCT dedup_key) FROM jobs"
                           " WHERE filter_reason=?", (reason,)).fetchone()[0]
        print(f"\n  {BOLD}{reason}{RESET}  {DIM}{tot:,} roles{RESET}")
        for co, ti in rows:
            print(f"    {(co or '?')[:20]:22}{(ti or '?')[:58]}")
    print(f"\n  {DIM}see something here you WANTED? that is a targets.yaml "
          f"edit, not a code change{RESET}\n")


def short(conn, c):
    total = conn.execute("SELECT COUNT(DISTINCT dedup_key) FROM jobs").fetchone()[0]
    print(f"jobhunt: {total:,} crawled | {c.get('pool', 0):,} to score | "
          f"{c.get('shortlist', 0):,} shortlisted | {c.get('applied', 0):,} applied")


def main():
    ap = argparse.ArgumentParser(description="Jobhunt pipeline status")
    ap.add_argument("--top", type=int, default=15, help="how many matches to show")
    ap.add_argument("--why", metavar="ID", help="full reasoning for one job")
    ap.add_argument("--rejects", action="store_true", help="sample the rejects")
    ap.add_argument("-n", type=int, default=4, help="rejects sampled per reason")
    ap.add_argument("--short", action="store_true", help="one line")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit("no database yet — run ./ingest.py first")
    conn = open_ro(DB_PATH)
    # Older databases predate score.py's columns; asking for them would throw.
    have = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    if "filter_reason" not in have:
        sys.exit("this database has not been through score.py yet — "
                 "run ./score.py --rules-only first")

    if args.why:
        return why(conn, args.why)
    c = counts(conn)
    if args.short:
        return short(conn, c)
    if args.rejects:
        return rejects(conn, args.n)
    health(conn)
    funnel(conn, c)
    shortlist(conn, args.top)
    print()


if __name__ == "__main__":
    main()
