#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-05]
# ============================================
# Browse the ingested job pool.
# PURPOSE: Read-only queries over jobhunt.db so you can see what the crawler
#          found before any scoring or applying happens.
# DEPS: stdlib only.
# USAGE:
#   ./browse.py                        # open roles, newest first
#   ./browse.py -q "python|backend"    # regex on title
#   ./browse.py --junior               # filter out senior/staff/principal
#   ./browse.py --company canonical
#   ./browse.py --all                  # include roles that cannot hire you
#   ./browse.py --show <id>            # full description of one posting
#   ./browse.py --companies            # which employers have open roles
# ============================================

import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from locations import OPEN_BUCKETS  # noqa: E402

DB_PATH = os.path.expanduser("~/.local/share/luminos/jobhunt.db")

SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|head of|director|vp|vice president"
    r"|manager|architect|distinguished|fellow|chief|iii|iv)\b"
    r"|\b([4-9]|1[0-9])\s*\+?\s*(yoe|years?)\b"          # "8+ YOE", "5 years"
    r"|\blevel\s*[3-9]\b|\bL[4-9]\b", re.I)
TECH = re.compile(
    r"\b(engineer|developer|programmer|software|backend|back-end|frontend"
    r"|front-end|full ?stack|devops|sre|platform|infrastructure|data|analyst"
    r"|analytics|ml|machine learning|ai|cloud|security|qa|test|support"
    r"|technical|it |sysadmin|systems|python|golang|go\b|java|node|react)\b", re.I)


def rows(conn, args):
    where, params = [], []
    if not args.all:
        where.append(f"bucket IN {OPEN_BUCKETS}")
    if args.company:
        where.append("LOWER(company) LIKE ?")
        params.append(f"%{args.company.lower()}%")
    if args.source:
        where.append("source = ?")
        params.append(args.source)
    sql = "SELECT id,company,title,location,bucket,source,url,first_seen FROM jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    # One row per underlying role — the same job on three boards is one job.
    sql += " GROUP BY dedup_key ORDER BY first_seen DESC, company"
    out = []
    for r in conn.execute(sql, params):
        title = r[2]
        if args.q and not re.search(args.q, title, re.I):
            continue
        if args.junior and SENIOR.search(title):
            continue
        if args.tech and not TECH.search(title):
            continue
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(description="Browse ingested job postings")
    ap.add_argument("-q", help="regex to match against job title")
    ap.add_argument("--company", help="filter by employer name")
    ap.add_argument("--source", help="filter by source board")
    ap.add_argument("--junior", action="store_true", help="drop senior/staff/lead titles")
    ap.add_argument("--tech", action="store_true", help="tech/IT titles only")
    ap.add_argument("--all", action="store_true", help="include roles that cannot hire you")
    ap.add_argument("--companies", action="store_true", help="group by employer")
    ap.add_argument("--show", metavar="ID", help="print one posting in full")
    ap.add_argument("-n", type=int, default=40, help="max rows (default 40)")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit("no db yet — run ./ingest.py first")
    conn = sqlite3.connect(DB_PATH)

    if args.show:
        r = conn.execute(
            "SELECT company,title,location,bucket,source,url,posted_at,description"
            " FROM jobs WHERE id LIKE ?", (args.show + "%",)).fetchone()
        if not r:
            sys.exit(f"no posting matching {args.show}")
        print(f"\n{r[1]}\n{r[0]}  |  {r[2]}  [{r[3]}]  via {r[4]}")
        print(f"{r[5]}\nposted: {r[6] or 'unknown'}\n")
        print(r[7] or "(no description captured)")
        return

    if args.companies:
        sql = (f"SELECT company, COUNT(DISTINCT dedup_key) n FROM jobs"
               f" WHERE bucket IN {OPEN_BUCKETS} GROUP BY LOWER(company)"
               f" ORDER BY n DESC LIMIT ?")
        print(f"\n{'employer':28}{'open roles':>11}")
        for c, n in conn.execute(sql, (args.n,)):
            print(f"{(c or '?')[:27]:28}{n:>11}")
        return

    found = rows(conn, args)
    print(f"\n{len(found)} matching roles (showing {min(len(found), args.n)})\n")
    print(f"{'id':10}{'company':20}{'title':46}{'where':22}{'src'}")
    print("-" * 112)
    for r in found[:args.n]:
        print(f"{r[0][:8]:10}{(r[1] or '?')[:19]:20}{(r[2] or '?')[:45]:46}"
              f"{(r[3] or '?')[:21]:22}{r[5][:12]}")
    if len(found) > args.n:
        print(f"\n… {len(found)-args.n} more — raise with -n")


if __name__ == "__main__":
    main()
