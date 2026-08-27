#!/usr/bin/env python3
"""Phase 5 — the tracker. What went out, what came back, what is waiting on you.
[CHANGE: claude-code | 2026-08-27]

WHAT THIS IS
------------
An append-only event log, one row per thing that happened to an application,
plus the views that read it. `apply.py` writes `submitted` events into it and
`followup.py` writes `rejected` / `interview` / `acknowledged` events into it.
Neither of them owns the history; this file does.

WHY AN EVENT LOG AND NOT A STATUS COLUMN
----------------------------------------
A status column holds one value, so every update destroys the previous one, and
you can never answer "how long did Canonical sit silent before they replied" or
"did we apply twice". This project already has a documented habit of scripts
reporting success while doing nothing (BUG-088, BUG-089, BUG-104), and the only
defence that has ever worked here is keeping the evidence rather than a summary
of it. So: nothing is ever overwritten. The current stage is DERIVED by asking
which is the furthest-along event, and if that derivation is ever wrong the raw
history is still sitting there to prove it.

The corollary is that every event carries `evidence` — a packet directory, a
screenshot path, a Gmail message id. An event with no evidence is an assertion,
and assertions are what this codebase keeps getting burned by.

IDEMPOTENCY, WHICH IS NOT OPTIONAL HERE
---------------------------------------
`followup.py` runs nightly and re-reads the same inbox every time. It WILL see
the same rejection email on twenty consecutive nights. `UNIQUE(dedup_key, kind,
evidence)` makes recording it the twentieth time a silent no-op, so the log
stays a history of what happened rather than a history of how often we looked.

KEYED ON dedup_key, NOT id — see BUG-141
----------------------------------------
One role carried by three boards is three `jobs` rows. Tracking per row would
report three applications to Canonical when one was sent. Everything here is
keyed on the role.

Usage:
  ./track.py                  the board — funnel, what needs you, what is silent
  ./track.py --show <id>      one application in full: resume, timeline, replies
  ./track.py --silent 14      applied 14+ days ago, still nothing back
  ./track.py --stage interview
  ./track.py --log <id> interview "phone screen Tue 10am" --evidence <msg-id>
  ./track.py --history <id>   raw event rows, nothing derived
"""
import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# [CHANGE: claude-code | 2026-08-27] Env-overridable so the stages that have not
# happened yet (submitted, rejected, interview) can be exercised against a COPY
# of the database. Testing a state machine by writing fake events into the real
# job history is how the history stops being trustworthy.
#   JOBHUNT_DB=/tmp/copy.db ./track.py
DB_PATH = os.environ.get(
    "JOBHUNT_DB", os.path.expanduser("~/.local/share/luminos/jobhunt.db"))

# ---------------------------------------------------------------------------
# The vocabulary. Adding a kind means deciding where it sits in the funnel, so
# the list and the order live together and there is no way to add one without
# answering that question.
#
# `rank` is how far along the application is. The current stage of a role is the
# highest rank it has ever reached — an interview invite followed by an
# automated "we received your application" does not move it backwards.
# ---------------------------------------------------------------------------
KINDS = {
    #  kind                rank  label                       terminal
    "tailored":           (1,  "resume written",             False),
    "apply_ready":        (2,  "form filled, not sent",      False),
    "submitted":          (3,  "application sent",           False),
    "acknowledged":       (4,  "employer confirmed receipt", False),
    "assessment":         (5,  "take-home / test sent",      False),
    "recruiter_interest": (6,  "recruiter made contact",     False),
    "interview":          (7,  "INTERVIEW",                  False),
    "offer":              (8,  "OFFER",                      False),
    # Terminal. These end the application wherever it had got to.
    "rejected":           (0,  "rejected",                   True),
    "withdrawn":          (0,  "withdrawn",                  True),
    # Not a stage — a thing that failed and needs a human. Deliberately ranked
    # below `submitted` so a failed attempt never looks like a sent application.
    "apply_failed":       (2,  "could not apply",            False),
    # Bookkeeping.
    "followed_up":        (0,  "nudge sent",                 False),
    "note":               (0,  "note",                       False),
}

# The stages that mean the ball is in HIS court, not the employer's.
NEEDS_HUMAN = ("interview", "offer", "assessment", "apply_failed")

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, YELLOW, RED, CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY,
  dedup_key  TEXT NOT NULL,
  job_id     TEXT,
  at         TEXT NOT NULL,
  kind       TEXT NOT NULL,
  detail     TEXT,
  evidence   TEXT,
  UNIQUE(dedup_key, kind, evidence)
);
CREATE INDEX IF NOT EXISTS idx_events_key  ON events(dedup_key);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
"""


def db_retry(fn, what, wait=300):
    """Poll for the instant between score.py's commits.

    score.py commits every ten jobs, so during a run it holds a write lock for
    ~3 minutes at a stretch and releases it momentarily. busy_timeout does not
    help — it expires inside a single stretch. Lifted from tailor.py, where this
    exact problem cost a rendered PDF its database row.
    """
    deadline = time.time() + wait
    told = False
    while True:
        try:
            r = fn()
            if told:
                print("  ...database free, written")
            return r
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or time.time() > deadline:
                raise
            if not told:
                told = True
                print(f"  waiting for the database to {what} (score.py is mid-run)...")
            time.sleep(0.25)


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    db_retry(lambda: conn.executescript(SCHEMA), "create the events table")
    return conn


def key_for(conn, job_id):
    """dedup_key for a job id or id prefix. Prefix, because every view here
    prints a shortened id and a printed id that cannot be pasted back is
    useless (the same defect tailor.py --list had)."""
    row = conn.execute(
        "SELECT dedup_key, id FROM jobs WHERE id=? OR id LIKE ? LIMIT 1",
        (job_id, job_id + "%")).fetchone()
    return row if row else (None, None)


def record(conn, job_id, kind, detail="", evidence=None, at=None):
    """Append one event. Returns True if it was new, False if already known.

    `evidence` participates in the uniqueness constraint, so re-reading the same
    email or re-running the same submission is a no-op rather than a duplicate.
    A None evidence is stored as '' so SQLite's "NULLs are all distinct" rule
    does not quietly let duplicates through — that would defeat the whole point.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown event kind {kind!r}; known: {sorted(KINDS)}")
    dk, full_id = key_for(conn, job_id)
    if dk is None:
        raise ValueError(f"no job whose id starts with {job_id!r}")

    def go():
        cur = conn.execute(
            "INSERT OR IGNORE INTO events (dedup_key, job_id, at, kind, detail, evidence)"
            " VALUES (?,?,?,?,?,?)",
            (dk, full_id, at or now(), kind, detail, evidence or ""))
        conn.commit()
        return cur.rowcount > 0
    return db_retry(go, f"record the {kind} event")


def stage_of(events):
    """Derive the current stage from a role's whole history.

    Terminal events win outright — a rejection after an interview means
    rejected. Otherwise the furthest-along event wins, so a late automated
    acknowledgement cannot drag an interview backwards.
    """
    if not events:
        return None

    # [CHANGE: claude-code | 2026-08-27] A terminal event only closes the role if
    # nothing needing a human happened AFTER it. This used to return terminal
    # regardless of when it arrived, which is wrong in a case that really
    # happens: rejected for the role on Monday, recruiter comes back Tuesday
    # offering an interview. The truth on Wednesday is "interview". Reading it
    # as "rejected" would park a live interview in the closed pile.
    #
    # `events` is ordered oldest-first by `load()`, so the last terminal index
    # is simply the highest one.
    last_terminal = None
    for i, e in enumerate(events):
        if KINDS[e["kind"]][2]:
            last_terminal = i
    if last_terminal is not None:
        after = [e for e in events[last_terminal + 1:]
                 if e["kind"] in NEEDS_HUMAN]
        if not after:
            return events[last_terminal]["kind"]
        return max(after, key=lambda e: KINDS[e["kind"]][0])["kind"]

    return max(events, key=lambda e: KINDS[e["kind"]][0])["kind"]


def buried_human_stage(events):
    """A NEEDS_HUMAN stage this role reached before something terminal closed it.

    [CHANGE: claude-code | 2026-08-27] followup.py classifies email without
    asking. The one misclassification that actually costs Shawn something is
    reading an interview invitation as a rejection: `rejected` is terminal, it
    wins outright, and the role would drop off WAITING ON YOU forever. His whole
    stated goal is to get to interviews, so that single bug would silently
    delete the output of the entire pipeline.

    This does not overrule the rejection — the stage stays `rejected`, because
    the log records what arrived. It only refuses to let a terminal event hide
    the fact that a human-facing stage was reached, so a wrong call is visible
    instead of invisible. Removing a safety net is not on the table; this adds
    one that costs a dict lookup.
    """
    if not events or not KINDS[stage_of(events)][2]:
        return None
    reached = [e["kind"] for e in events if e["kind"] in NEEDS_HUMAN]
    if not reached:
        return None
    return max(reached, key=lambda k: KINDS[k][0])


def load(conn, where="", params=()):
    """Every tracked role, with its events, newest event last."""
    rows = conn.execute(
        "SELECT dedup_key, job_id, at, kind, detail, evidence FROM events "
        + where + " ORDER BY at", params).fetchall()
    by_key = {}
    for dk, jid, at, kind, detail, ev in rows:
        by_key.setdefault(dk, []).append(
            {"job_id": jid, "at": at, "kind": kind, "detail": detail, "evidence": ev})
    out = []
    for dk, evs in by_key.items():
        job = conn.execute(
            "SELECT id, company, title, location, url, score FROM jobs"
            " WHERE dedup_key=? AND status IN ('shortlist','applied')"
            " ORDER BY score DESC LIMIT 1", (dk,)).fetchone()
        if job is None:
            job = conn.execute(
                "SELECT id, company, title, location, url, score FROM jobs"
                " WHERE dedup_key=? LIMIT 1", (dk,)).fetchone()
        if job is None:
            continue          # the posting was purged; the history is orphaned
        out.append({"key": dk, "job": job, "events": evs, "stage": stage_of(evs)})
    return out


def days_since(iso):
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then.astimezone(timezone.utc)).days


def last_of(rec, kinds):
    hits = [e for e in rec["events"] if e["kind"] in kinds]
    return hits[-1] if hits else None


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def board(conn):
    recs = load(conn)
    shortlist = conn.execute(
        "SELECT COUNT(DISTINCT dedup_key) FROM jobs WHERE status='shortlist'"
    ).fetchone()[0]

    print(f"\n{BOLD}  APPLICATIONS{RESET}  {DIM}(one row per role, "
          f"not per job board){RESET}")
    print("  " + "-" * 66)
    if not recs:
        print(f"  {DIM}nothing tracked yet — {shortlist} roles shortlisted, "
              f"none applied to.{RESET}")
        print(f"  {DIM}run ./tailor.py then ./apply.py{RESET}\n")
        return

    counts = {}
    for r in recs:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
    order = sorted(counts, key=lambda k: -KINDS[k][0])
    for kind in order:
        label = KINDS[kind][1]
        col = (GREEN if kind in ("interview", "offer") else
               RED if kind == "rejected" else
               YELLOW if kind in ("assessment", "apply_failed") else "")
        print(f"  {col}{label:<34}{counts[kind]:>6}{RESET}")
    sent = sum(1 for r in recs if last_of(r, ("submitted",)))
    print("  " + "-" * 66)
    print(f"  {'applications sent':<34}{sent:>6}")
    print(f"  {'still shortlisted, not sent':<34}{shortlist - sent:>6}")

    # The rate that actually matters, and the reason the tracker exists.
    if sent:
        replied = sum(1 for r in recs
                      if last_of(r, ("acknowledged", "rejected", "assessment",
                                     "recruiter_interest", "interview", "offer")))
        invited = sum(1 for r in recs if last_of(r, ("interview", "offer")))
        print(f"\n  {'reply rate':<34}{replied}/{sent}"
              f"  ({100*replied/sent:.0f}%)")
        print(f"  {'interview rate':<34}{invited}/{sent}"
              f"  ({100*invited/sent:.0f}%)")

    needs = [r for r in recs if r["stage"] in NEEDS_HUMAN]
    if needs:
        print(f"\n{BOLD}{GREEN}  WAITING ON YOU{RESET}")
        print("  " + "-" * 66)
        for r in needs:
            jid, co, ti, _, _, _ = r["job"]
            e = last_of(r, (r["stage"],))
            d = days_since(e["at"])
            print(f"  {jid[:12]}  {(co or '')[:18]:18} {(ti or '')[:28]:28}"
                  f"  {KINDS[r['stage']][1]}")
            if e["detail"]:
                print(f"                {DIM}{e['detail'][:60]}{RESET}")
            print(f"                {DIM}{d} day(s) ago{RESET}")

    # [CHANGE: claude-code | 2026-08-27] Closed, but it had reached a stage that
    # needed a human first. Either a real rejection after a real interview (worth
    # knowing) or followup.py misread the email (worth knowing more). Shown
    # separately rather than mixed into WAITING ON YOU, because the pipeline's
    # own belief is that these are finished.
    buried = [(r, b) for r in recs
              for b in [buried_human_stage(r["events"])] if b]
    if buried:
        print(f"\n{BOLD}{YELLOW}  CLOSED, BUT REACHED YOU FIRST{RESET}  "
              f"{DIM}check these — a misread email looks exactly like this"
              f"{RESET}")
        print("  " + "-" * 66)
        for r, b in buried:
            jid, co, ti, _, _, _ = r["job"]
            print(f"  {jid[:12]}  {(co or '')[:18]:18} {(ti or '')[:28]:28}"
                  f"  {KINDS[r['stage']][1]} after {KINDS[b][1]}")

    silent = silent_list(recs, 14)
    if silent:
        print(f"\n{BOLD}  SILENT 14+ DAYS{RESET}  {DIM}{len(silent)} "
              f"application(s){RESET}")
        print("  " + "-" * 66)
        for r, d in silent[:8]:
            jid, co, ti, _, _, _ = r["job"]
            print(f"  {jid[:12]}  {(co or '')[:18]:18} {(ti or '')[:28]:28}  {d}d")
        if len(silent) > 8:
            print(f"  {DIM}...and {len(silent)-8} more — ./track.py --silent{RESET}")

    print(f"\n  {DIM}./track.py --show <id>   one application in full{RESET}\n")


def silent_list(recs, days):
    """Sent, nothing back, and long enough ago to mean something."""
    out = []
    for r in recs:
        sub = last_of(r, ("submitted",))
        if not sub or r["stage"] != "submitted":
            continue
        d = days_since(sub["at"])
        if d is not None and d >= days:
            out.append((r, d))
    return sorted(out, key=lambda t: -t[1])


# [CHANGE: claude-code | 2026-08-27] Which host a URL can actually be applied
# through, in preference order. An aggregator listing is a description of a job;
# only these are a form you can submit.
ATS_HOSTS = (
    ("greenhouse", "greenhouse.io"),
    ("ashby",      "ashbyhq.com"),
    ("lever",      "lever.co"),
    ("workday",    "myworkdayjobs.com"),
)


def apply_url(conn, dedup_key):
    """The URL of the role that can be APPLIED to, not merely the top-scoring row.

    A role carried by several boards has several URLs, and they are not
    interchangeable: jobicy.com/jobs/149581 is an article about the job, while
    job-boards.greenhouse.io/canonical/jobs/8055009 is the form. `show()` used to
    print whichever row scored highest, which for the Canonical role meant
    showing the aggregator while two real Greenhouse links sat in the same dedup
    group unused.

    Returns (url, ats_name). ats_name is None when nothing in the group is a
    form — those are the roles that still need resolving before apply.py can do
    anything with them, and it is honest for it to say so.
    """
    urls = [r[0] for r in conn.execute(
        "SELECT url FROM jobs WHERE dedup_key=? AND url IS NOT NULL",
        (dedup_key,)).fetchall()]
    for name, host in ATS_HOSTS:
        for u in urls:
            if host in u:
                return u, name
    return (urls[0] if urls else None), None


def show(conn, job_id):
    dk, full = key_for(conn, job_id)
    if dk is None:
        sys.exit(f"\n  no job whose id starts with {job_id!r}\n")
    recs = load(conn, "WHERE dedup_key=?", (dk,))
    job = conn.execute(
        "SELECT id, company, title, location, url, score, score_reason,"
        " status, tailored_at, packet_dir, description FROM jobs"
        " WHERE dedup_key=? ORDER BY score DESC LIMIT 1", (dk,)).fetchone()
    if job is None:
        sys.exit(f"\n  {job_id!r} is not in the jobs table\n")
    (jid, co, ti, loc, url, score, reason, status,
     tailored, pdir, desc) = job

    print(f"\n{BOLD}  {co} — {ti}{RESET}")
    print("  " + "=" * 66)
    print(f"  {'id':<14}{jid}")
    print(f"  {'fit score':<14}{score}")
    print(f"  {'location':<14}{loc}")
    print(f"  {'pipeline':<14}{status}")
    aurl, ats = apply_url(conn, dk)
    if ats:
        print(f"  {'apply at':<14}{aurl}  {DIM}({ats}){RESET}")
        if aurl != url:
            print(f"  {'also listed':<14}{DIM}{url}{RESET}")
    else:
        print(f"  {'url':<14}{url}")
        print(f"  {'':<14}{YELLOW}aggregator listing — no application form "
              f"found yet{RESET}")

    # How many boards carried this one role. Non-obvious, and it is the number
    # that BUG-141 was hiding.
    # [CHANGE: claude-code | 2026-08-27] This said "3 boards (greenhouse,jobicy)"
    # — COUNT(*) is postings, not boards, and a board can carry the same role
    # twice on its own. Printing a row count under a label that says "boards" is
    # precisely the mistake BUG-141 was, so it does not get to survive in the
    # tool built to expose it. Both numbers are real; print both.
    rows, boards, srcs = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT source), GROUP_CONCAT(DISTINCT source)"
        " FROM jobs WHERE dedup_key=?", (dk,)).fetchone()
    if rows > 1:
        dup = f", {rows} postings" if rows != boards else ""
        print(f"  {'seen on':<14}{boards} board{'s' if boards > 1 else ''} "
              f"({srcs}{dup})")

    if reason:
        import json
        try:
            r = json.loads(reason)
            print(f"\n{BOLD}  WHY IT SCORED{RESET}")
            print("  " + "-" * 66)
            for k in ("summary", "fit_signal", "years_required", "hard_blocker"):
                if r.get(k) not in (None, ""):
                    print(f"  {k:<18}{r[k]}")
            if r.get("missing_skills"):
                print(f"  {'missing':<18}{', '.join(r['missing_skills'][:8])}")
        except Exception:
            pass

    if pdir and os.path.isdir(pdir):
        print(f"\n{BOLD}  WHAT THE RESUME SAID{RESET}  {DIM}{pdir}{RESET}")
        print("  " + "-" * 66)
        import json
        pj = os.path.join(pdir, "packet.json")
        if os.path.exists(pj):
            p = json.load(open(pj))
            pk = p.get("packet", {})
            print(f"  headline   {pk.get('headline','')}")
            for b in pk.get("bullets", []):
                print(f"  {DIM}·{RESET} {b['text'][:64]}")
                print(f"    {DIM}from {b['id']}{RESET}")
        for f in sorted(os.listdir(pdir)):
            print(f"  {DIM}{f}{RESET}")

    print(f"\n{BOLD}  TIMELINE{RESET}")
    print("  " + "-" * 66)
    if not recs:
        print(f"  {DIM}nothing has happened yet{RESET}")
    else:
        for e in recs[0]["events"]:
            rank, label, terminal = KINDS[e["kind"]]
            col = (GREEN if e["kind"] in ("interview", "offer") else
                   RED if terminal else "")
            when = e["at"][:16].replace("T", " ")
            d = days_since(e["at"])
            print(f"  {when}  {col}{label:<28}{RESET}{DIM}{d}d ago{RESET}")
            if e["detail"]:
                print(f"                     {e['detail'][:58]}")
            if e["evidence"]:
                print(f"                     {DIM}{e['evidence'][:58]}{RESET}")
        print(f"\n  {BOLD}now:{RESET} {KINDS[recs[0]['stage']][1]}")
        b = buried_human_stage(recs[0]["events"])
        if b:
            print(f"  {YELLOW}reached {KINDS[b][1]} before it closed — if that "
                  f"was misread, this is where it shows{RESET}")

    if desc:
        print(f"\n{BOLD}  THE POSTING{RESET}  {DIM}first 500 chars — "
              f"./browse.py --show {jid[:12]} for all of it{RESET}")
        print("  " + "-" * 66)
        # [CHANGE: claude-code | 2026-08-27] textwrap, not a fixed slice — the
        # slice cut words in half ("operat / ing systems"), which makes a job
        # description read as garbled and is the kind of thing that gets a
        # working tool distrusted.
        import textwrap
        body = " ".join(desc.split())[:500]
        for line in textwrap.wrap(body, 66):
            print(f"  {line}")
    print()


def history(conn, job_id):
    dk, _ = key_for(conn, job_id)
    if dk is None:
        sys.exit(f"\n  no job whose id starts with {job_id!r}\n")
    rows = conn.execute(
        "SELECT id, at, kind, detail, evidence, job_id FROM events"
        " WHERE dedup_key=? ORDER BY at", (dk,)).fetchall()
    print(f"\n  {len(rows)} raw event(s) for {dk}\n")
    for r in rows:
        print(f"  #{r[0]:<5} {r[1]}  {r[2]:<18} {r[3] or ''}")
        if r[4]:
            print(f"         {DIM}evidence: {r[4]}{RESET}")
    print()


def main():
    ap = argparse.ArgumentParser(
        description="Phase 5 — what went out, what came back, what needs you.")
    ap.add_argument("--show", metavar="ID", help="one application in full")
    ap.add_argument("--history", metavar="ID", help="raw event rows")
    ap.add_argument("--silent", type=int, nargs="?", const=14, metavar="DAYS",
                    help="sent N+ days ago with no reply (default 14)")
    ap.add_argument("--stage", help="list roles at one stage, e.g. interview")
    ap.add_argument("--log", nargs=2, metavar=("ID", "KIND"),
                    help="record an event by hand")
    ap.add_argument("--detail", default="", help="text for --log")
    ap.add_argument("--evidence", default="", help="evidence for --log")
    # [CHANGE: claude-code | 2026-08-27] The timestamp has to be settable, not
    # just defaulted to now(). An email that arrived on the 12th and is read on
    # the 27th is an event that HAPPENED on the 12th, and --silent / followup.py
    # both count days from the last event — stamping it today would silently
    # reset the follow-up clock every time the inbox is re-read.
    ap.add_argument("--at", default=None,
                    help="ISO timestamp for --log (default: now)")
    ap.add_argument("--kinds", action="store_true", help="list event kinds")
    args = ap.parse_args()

    if args.kinds:
        print()
        for k, (rank, label, term) in sorted(KINDS.items(), key=lambda t: -t[1][0]):
            print(f"  {k:<20} {label:<30}{'terminal' if term else ''}")
        print()
        return

    conn = connect()

    if args.log:
        jid, kind = args.log
        if kind not in KINDS:
            sys.exit(f"\n  unknown kind {kind!r}. ./track.py --kinds\n")
        new = record(conn, jid, kind, args.detail, args.evidence or None,
                     at=args.at)
        print(f"\n  {'recorded' if new else 'already recorded'}: "
              f"{kind} for {jid}\n")
        return

    if args.show:
        return show(conn, args.show)
    if args.history:
        return history(conn, args.history)

    if args.silent is not None:
        recs = load(conn)
        out = silent_list(recs, args.silent)
        print(f"\n  {len(out)} application(s) silent {args.silent}+ days\n")
        for r, d in out:
            jid, co, ti, _, _, _ = r["job"]
            print(f"  {jid[:12]}  {(co or '')[:20]:20} {(ti or '')[:32]:32}  {d}d")
        print()
        return

    if args.stage:
        if args.stage not in KINDS:
            sys.exit(f"\n  unknown stage {args.stage!r}. ./track.py --kinds\n")
        recs = [r for r in load(conn) if r["stage"] == args.stage]
        print(f"\n  {len(recs)} role(s) at stage {args.stage!r}\n")
        for r in recs:
            jid, co, ti, _, _, _ = r["job"]
            print(f"  {jid[:12]}  {(co or '')[:20]:20} {(ti or '')[:32]:32}")
        print()
        return

    board(conn)


if __name__ == "__main__":
    main()
