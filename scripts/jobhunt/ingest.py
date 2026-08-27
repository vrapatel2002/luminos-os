#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-05]
# ============================================
# Job ingest — pulls worldwide work-from-home postings into SQLite.
# PURPOSE: Build the widest legitimate pool of remote roles that can actually
#          hire a Canada-resident, from official ATS APIs and remote-native
#          boards. No scraping, no login, no captcha, no ToS grey area.
# SOURCES: Greenhouse / Lever / Ashby (official public board APIs),
#          Remotive / RemoteOK / Himalayas / Arbeitnow / WeWorkRemotely.
# STORE:   ~/.local/share/luminos/jobhunt.db
# DEPS:    stdlib only — NO pip packages.
# USAGE:   ./ingest.py            # crawl everything
#          ./ingest.py --only remotive,remoteok
#          ./ingest.py --stats    # what is in the db
# ============================================

import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from locations import classify, is_remote, OPEN_BUCKETS  # noqa: E402

DB_PATH = os.path.expanduser("~/.local/share/luminos/jobhunt.db")
UA = "Mozilla/5.0 (X11; Linux x86_64) luminos-jobhunt/1.0"
MAX_DESC = 20000

# Seed boards. open_rate measured 2026-08-05 — the crawler keeps this current
# in the `boards` table so we can prioritise the ones that actually hire here.
GREENHOUSE = [
    "instacart", "affirm", "gitlab", "stripe", "asana", "samsara", "reddit",
    "elastic", "robinhood", "mongodb", "twilio", "discord", "databricks",
    "flexport", "dropbox", "airtable", "anthropic", "cloudflare", "figma",
    "doximity", "grafanalabs", "planetscale", "cockroachlabs", "circleci",
    "datadog", "okta", "gusto", "webflow", "calendly", "typeform", "coursera",
    "udemy", "duolingo", "wikimedia", "mozilla", "canonical", "contentful",
    "algolia", "amplitude", "mixpanel", "launchdarkly", "chainguard",
    "tailscale", "clickhouse", "axiom", "gocardless", "monzo", "truelayer",
]
LEVER = [
    "wealthsimple", "plusgrade", "aircall", "neon", "ledger",
]
ASHBY = [
    "posthog", "linear", "oyster", "ramp", "vanta", "replit", "openai", "warp",
    "zapier", "buffer", "close", "hopper", "1password", "supabase", "render",
    "temporal", "confluent", "notion", "miro", "strava", "railway", "incident",
    "knowunity", "paddle", "primer", "alan",
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(url, raw=False, tries=2):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            data = urllib.request.urlopen(req, timeout=25).read()
            return data if raw else json.loads(data)
        except Exception as exc:  # noqa: BLE001 - any source may be down; keep going
            last = exc
            if attempt + 1 < tries:
                time.sleep(1.5)
    raise last


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:MAX_DESC]


def job_id(source, company, title, url):
    key = "|".join((source, (company or "").lower(), (title or "").lower(), url or ""))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


_NOISE = re.compile(r"\(.*?\)|\[.*?\]|[^a-z0-9 ]", re.I)

# [CHANGE: claude-code | 2026-08-27] BUG-141.
# Legal suffixes, stripped from the END of a company name before it becomes part
# of a role's identity. One employer writes itself differently on each board it
# posts to — "Canonical" on its own ATS, "Canonical Ltd." on an aggregator — and
# without this the same job counts twice, is scored twice, and would be APPLIED
# TO twice, which is the exact thing dedup_key exists to prevent.
_LEGAL_SUFFIX = {
    "inc", "llc", "llp", "lp", "ltd", "limited", "corp", "corporation", "co",
    "plc", "gmbh", "ag", "bv", "nv", "sa", "sarl", "srl", "spa", "ab", "oy",
    "as", "pty", "pte", "kk",
}


def _norm(s):
    return re.sub(r"\s+", " ", _NOISE.sub(" ", (s or "").lower())).strip()


def norm_company(s):
    """Company name reduced to the part that identifies the employer.

    Strips trailing legal suffixes, but never the last word — a firm whose whole
    name normalises to a suffix keeps it rather than becoming the empty string.
    """
    w = _norm(s).split()
    while len(w) > 1 and w[-1] in _LEGAL_SUFFIX:
        w.pop()
    return " ".join(w)


def dedup_key(company, title):
    """Identity of the underlying ROLE, independent of which board carried it.

    The same job is routinely listed on the company's own ATS and on two or
    three aggregators. Applying three times looks like spam to the recruiter
    and burns the one impression you get.
    """
    return hashlib.sha1(
        f"{norm_company(company)}|{_norm(title)}".encode()).hexdigest()[:16]


def redup(conn):
    """Recompute every row's dedup_key from the CURRENT rule.

    Same reasoning as score.py recomputing `bucket` on every rules pass
    (BUG-107): a key baked in at crawl time freezes whatever bug existed that
    night. Cheap — a few thousand sha1s — and it means a dedup fix lands on the
    whole history without re-crawling 12,000 postings.
    """
    changed = 0
    for jid, co, ti, old in conn.execute(
            "SELECT id, company, title, dedup_key FROM jobs").fetchall():
        new = dedup_key(co, ti)
        if new != old:
            conn.execute("UPDATE jobs SET dedup_key=? WHERE id=?", (new, jid))
            changed += 1
    conn.commit()
    return changed


def mk(source, company, title, url, location, posted_at=None, description=""):
    return {
        "source": source,
        "company": (company or "").strip(),
        "title": (title or "").strip(),
        "url": url or "",
        "location": (location or "").strip(),
        "posted_at": posted_at,
        "description": strip_html(description),
    }


# ── Sources ────────────────────────────────────────────────────────────────────

def src_greenhouse(token):
    d = fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    for j in d.get("jobs", []):
        yield mk("greenhouse", token, j.get("title"), j.get("absolute_url"),
                 (j.get("location") or {}).get("name"), j.get("updated_at"),
                 j.get("content", ""))


def src_lever(token):
    d = fetch(f"https://api.lever.co/v0/postings/{token}?mode=json")
    for j in d if isinstance(d, list) else []:
        cats = j.get("categories") or {}
        ts = j.get("createdAt")
        posted = datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat() if ts else None
        yield mk("lever", token, j.get("text"), j.get("hostedUrl"),
                 cats.get("location"), posted,
                 j.get("descriptionPlain") or j.get("description", ""))


def src_ashby(token):
    d = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
    for j in d.get("jobs", []):
        locs = [j.get("location", "")] + [
            s.get("location", "") for s in (j.get("secondaryLocations") or [])
        ]
        yield mk("ashby", token, j.get("title"), j.get("jobUrl"),
                 " | ".join(x for x in locs if x), j.get("publishedAt"),
                 j.get("descriptionPlain") or j.get("descriptionHtml", ""))


def src_remotive():
    d = fetch("https://remotive.com/api/remote-jobs")
    for j in d.get("jobs", []):
        yield mk("remotive", j.get("company_name"), j.get("title"), j.get("url"),
                 j.get("candidate_required_location"), j.get("publication_date"),
                 j.get("description", ""))


def src_remoteok():
    d = fetch("https://remoteok.com/api")
    for j in d if isinstance(d, list) else []:
        if not isinstance(j, dict) or not j.get("position"):
            continue
        loc = j.get("location") or ""
        # RemoteOK leaves location blank or writes "Worldwide" for open roles.
        if not loc.strip():
            loc = "Worldwide"
        yield mk("remoteok", j.get("company"), j.get("position"), j.get("url"),
                 loc, j.get("date"), j.get("description", ""))


def src_himalayas():
    seen = 0
    for offset in range(0, 400, 100):
        d = fetch(f"https://himalayas.app/jobs/api?limit=100&offset={offset}")
        jobs = d.get("jobs") or []
        if not jobs:
            break
        for j in jobs:
            restr = j.get("locationRestrictions")
            loc = ", ".join(restr) if isinstance(restr, list) and restr else "Worldwide"
            yield mk("himalayas", j.get("companyName"), j.get("title"),
                     j.get("applicationLink") or j.get("guid"), loc,
                     j.get("pubDate"), j.get("description", ""))
        seen += len(jobs)
        if len(jobs) < 100:
            break


def src_arbeitnow():
    for page in range(1, 6):
        d = fetch(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        rows = d.get("data") or []
        if not rows:
            break
        for j in rows:
            if not j.get("remote"):
                continue
            yield mk("arbeitnow", j.get("company_name"), j.get("title"), j.get("url"),
                     j.get("location"), None, j.get("description", ""))


def src_jobicy():
    # geo=anywhere is the worldwide pool; canada catches Canada-pegged remote.
    for geo in ("anywhere", "canada", "usa"):
        try:
            d = fetch(f"https://jobicy.com/api/v2/remote-jobs?count=100&geo={geo}")
        except Exception:
            continue
        for j in d.get("jobs", []):
            yield mk("jobicy", j.get("companyName"), j.get("jobTitle"),
                     j.get("url"), j.get("jobGeo") or "Anywhere",
                     j.get("pubDate"), j.get("jobExcerpt", ""))


WWR_FEEDS = [
    "",  # the firehose feed — all categories, ~100 newest
    "categories/remote-programming-jobs",
    "categories/remote-devops-sysadmin-jobs",
    "categories/remote-back-end-programming-jobs",
    "categories/remote-front-end-programming-jobs",
    "categories/remote-full-stack-programming-jobs",
    "categories/remote-customer-support-jobs",
    "categories/remote-design-jobs",
    "categories/remote-product-jobs",
    "categories/remote-management-and-finance-jobs",
    "categories/remote-sales-and-marketing-jobs",
    "categories/all-other-remote-jobs",
]


def src_wwr():
    for feed in WWR_FEEDS:
        path = f"{feed}.rss" if feed else "remote-jobs.rss"
        try:
            xml = fetch(f"https://weworkremotely.com/{path}", raw=True).decode("utf-8", "replace")
        except Exception:
            continue
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
            def tag(name):
                m = re.search(rf"<{name}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{name}>", item, re.S)
                return html.unescape(m.group(1)).strip() if m else ""
            title = tag("title")
            company, _, role = title.partition(":")
            yield mk("weworkremotely", company.strip(), (role or title).strip(),
                     tag("link"), tag("region") or "Worldwide", tag("pubDate"),
                     tag("description"))


# ── Storage ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  dedup_key TEXT,
  source TEXT NOT NULL,
  company TEXT,
  title TEXT,
  url TEXT,
  location TEXT,
  bucket TEXT,
  remote INTEGER DEFAULT 0,
  posted_at TEXT,
  first_seen TEXT,
  last_seen TEXT,
  seen_count INTEGER DEFAULT 1,
  description TEXT,
  status TEXT DEFAULT 'new',
  score INTEGER,
  score_reason TEXT,
  applied_at TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_dedup ON jobs(dedup_key);
CREATE INDEX IF NOT EXISTS idx_jobs_bucket ON jobs(bucket);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_seen ON jobs(first_seen);
CREATE TABLE IF NOT EXISTS boards (
  token TEXT, ats TEXT, jobs INTEGER, open_jobs INTEGER,
  open_rate REAL, last_crawl TEXT, error TEXT,
  PRIMARY KEY (token, ats)
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def upsert(conn, rows):
    """Insert new postings; bump last_seen/seen_count on ones we already have.

    seen_count is the ghost-job tell: a posting still live after weeks of
    crawling is either evergreen hiring or was never real.
    """
    ts = now()
    new = dup = 0
    for r in rows:
        bucket = classify(r["location"], r["title"], r["description"][:400])
        jid = job_id(r["source"], r["company"], r["title"], r["url"])
        cur = conn.execute(
            "UPDATE jobs SET last_seen=?, seen_count=seen_count+1 WHERE id=?", (ts, jid)
        )
        if cur.rowcount:
            dup += 1
            continue
        conn.execute(
            "INSERT INTO jobs (id,dedup_key,source,company,title,url,location,bucket,"
            "remote,posted_at,first_seen,last_seen,description)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (jid, dedup_key(r["company"], r["title"]), r["source"], r["company"],
             r["title"], r["url"], r["location"], bucket,
             int(is_remote(r["location"], r["title"])), r["posted_at"],
             ts, ts, r["description"]),
        )
        new += 1
    conn.commit()
    return new, dup


def record_board(conn, token, ats, total, open_n, error=None):
    conn.execute(
        "INSERT OR REPLACE INTO boards (token,ats,jobs,open_jobs,open_rate,last_crawl,error)"
        " VALUES (?,?,?,?,?,?,?)",
        (token, ats, total, open_n, round(100 * open_n / total, 1) if total else 0.0,
         now(), error),
    )
    conn.commit()


# ── Crawl ──────────────────────────────────────────────────────────────────────

def run_board(ats, token):
    fn = {"greenhouse": src_greenhouse, "lever": src_lever, "ashby": src_ashby}[ats]
    try:
        rows = list(fn(token))
        return ats, token, rows, None
    except Exception as exc:  # noqa: BLE001
        return ats, token, [], f"{type(exc).__name__}: {exc}"


def crawl(conn, only=None):
    only = set(only) if only else None
    totals = {}

    boards = ([("greenhouse", t) for t in GREENHOUSE]
              + [("lever", t) for t in LEVER]
              + [("ashby", t) for t in ASHBY])
    boards = [(a, t) for a, t in boards if not only or a in only]

    if boards:
        print(f"→ {len(boards)} company boards")
        with cf.ThreadPoolExecutor(12) as ex:
            for ats, token, rows, err in ex.map(lambda b: run_board(*b), boards):
                if err:
                    record_board(conn, token, ats, 0, 0, err)
                    print(f"  !! {ats}/{token}: {err[:60]}")
                    continue
                open_n = sum(1 for r in rows
                             if classify(r["location"], r["title"]) in OPEN_BUCKETS)
                new, dup = upsert(conn, rows)
                record_board(conn, token, ats, len(rows), open_n)
                totals[ats] = totals.get(ats, 0) + new
                if rows:
                    print(f"  {ats:11} {token:14} {len(rows):4} jobs  {open_n:3} open  (+{new} new)")

    feeds = {"remotive": src_remotive, "remoteok": src_remoteok,
             "himalayas": src_himalayas, "arbeitnow": src_arbeitnow,
             "jobicy": src_jobicy, "weworkremotely": src_wwr}
    feeds = {k: v for k, v in feeds.items() if not only or k in only}
    if feeds:
        print(f"→ {len(feeds)} remote boards")
        for name, fn in feeds.items():
            try:
                rows = list(fn())
            except Exception as exc:  # noqa: BLE001
                print(f"  !! {name}: {type(exc).__name__}: {exc}")
                continue
            open_n = sum(1 for r in rows
                         if classify(r["location"], r["title"]) in OPEN_BUCKETS)
            new, dup = upsert(conn, rows)
            totals[name] = totals.get(name, 0) + new
            print(f"  {name:15} {len(rows):4} jobs  {open_n:3} open  (+{new} new)")

    return totals


def stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    if not total:
        print("empty db — run ingest first")
        return
    print(f"\n{total} postings stored\n")
    print("  by hireability")
    for bucket, n in conn.execute(
        "SELECT bucket, COUNT(*) FROM jobs GROUP BY bucket ORDER BY COUNT(*) DESC"
    ):
        mark = "<-- open to you" if bucket in OPEN_BUCKETS else ""
        print(f"    {bucket:16}{n:6}  {100*n/total:5.1f}%  {mark}")

    open_n = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE bucket IN {OPEN_BUCKETS}"
    ).fetchone()[0]
    uniq = conn.execute(
        f"SELECT COUNT(DISTINCT dedup_key) FROM jobs WHERE bucket IN {OPEN_BUCKETS}"
    ).fetchone()[0]
    print(f"\n  OPEN POOL: {open_n} ({100*open_n/total:.1f}%)"
          f" — {uniq} distinct roles after cross-board dedup")

    print("\n  by source")
    for s, n, o in conn.execute(
        f"SELECT source, COUNT(*), SUM(bucket IN {OPEN_BUCKETS}) FROM jobs"
        " GROUP BY source ORDER BY 3 DESC"
    ):
        print(f"    {s:16}{n:6} jobs  {o or 0:5} open")

    print("\n  best boards (open rate, min 15 jobs)")
    for t, a, j, o, r in conn.execute(
        "SELECT token,ats,jobs,open_jobs,open_rate FROM boards"
        " WHERE jobs>=15 ORDER BY open_rate DESC LIMIT 12"
    ):
        print(f"    {t:15}{a:11}{j:5} jobs  {o:4} open  {r:5.1f}%")


def main():
    ap = argparse.ArgumentParser(description="Ingest worldwide remote job postings")
    ap.add_argument("--only", help="comma-separated sources to crawl")
    ap.add_argument("--stats", action="store_true", help="show db summary and exit")
    ap.add_argument("--redup", action="store_true",
                    help="recompute dedup keys on existing rows and exit")
    args = ap.parse_args()

    conn = connect()
    if args.stats:
        stats(conn)
        return
    if args.redup:
        print(f"  {redup(conn):,} rows re-keyed")
        stats(conn)
        return

    t0 = time.time()
    # [CHANGE: claude-code | 2026-08-27] BUG-141 — before, not after: the crawl's
    # own duplicate check reads these keys.
    n = redup(conn)
    if n:
        print(f"  {n:,} rows re-keyed under the current dedup rule")
    crawl(conn, args.only.split(",") if args.only else None)
    print(f"\ndone in {time.time()-t0:.1f}s")
    stats(conn)


if __name__ == "__main__":
    main()
