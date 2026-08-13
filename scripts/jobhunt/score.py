#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-06]
# ============================================
# Score the job pool. Two passes: free rules, then the local GPU model.
# PURPOSE: Turn ~9,800 raw postings into a short list worth a human's attention,
#          spending as close to zero as possible to get there.
# DEPS: stdlib + PyYAML (system python3 has it).
# USAGE:
#   ./score.py --rules-only     # free pass only, prints the funnel (~2s)
#   ./score.py                  # free pass, then model-score the survivors
#   ./score.py --limit 20       # model-score only the first 20 (for testing)
#   ./score.py --rescore        # re-score jobs already scored
#   ./score.py --dry-run        # show one prompt and exit, call nothing
# ============================================
#
# ── WHY TWO PASSES: THE WHOLE COST ARGUMENT ─────────────────────────────────
# The design instruction was "use cheapest model for bulk applying". The cheapest
# model is not calling a model. Measured on the real database, 2026-08-06:
#
#   read all 9,788 descriptions with an LLM   ~18,220,000 tokens
#   read only the rule survivors              ~367,000 tokens      50x less
#
# Nothing about "is this US-only", "is this remote", "does the title say
# Senior" needs a language model. Those are string matches, they are exact, and
# they are free. So the rules pass runs first and kills ~97% of the pool with
# regexes; the model only ever sees what survives.
#
# The model that does see them is Qwen3-4B on the RTX 4050 — local, so the
# marginal cost of a scoring run is electricity. No API key is involved and no
# token is billed. Cloud models are reserved for Phase 3 (writing a tailored
# resume for a specific posting), where there are a handful of calls and the
# quality actually decides an outcome.
#
# ── WHY IT STOPS THE MODEL SERVER AFTERWARDS ────────────────────────────────
# An idle llama server holds ~4.6 GB of VRAM and keeps the dGPU out of its
# suspended state forever. BUG-103 was exactly that class of bug. So this
# script starts jobhunt-llm.service if it is down, and stops it again on the
# way out UNLESS it was already running when we arrived — if the operator started it
# by hand for something else, taking it away from him would be rude.
#
# ── WHY A JSON SCHEMA AND NOT A PROMPT INSTRUCTION ──────────────────────────
# "Reply with JSON only" is a request. A 4B model honours it most of the time,
# and "most of the time" over 250 jobs is a guaranteed handful of crashes at
# 3am. Passing `response_format.schema` makes llama.cpp compile the schema into
# a GBNF grammar and constrain sampling, so a token that would break the JSON
# is never even a candidate. Malformed output stops being unlikely and starts
# being impossible. PLAN.md Phase 2 requires this; it is not an optimisation.

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from locations import classify  # noqa: E402

DB_PATH = os.path.expanduser("~/.local/share/luminos/jobhunt.db")
TARGETS = os.path.join(HERE, "targets.yaml")

# Statuses this script writes into jobs.status.
#   new        never filtered (ingest.py's default)
#   filtered   a free rule rejected it; jobs.filter_reason says which
#   pool       survived the rules, waiting on the model
#   scored     the model looked at it and it came in under shortlist_min
#   shortlist  the model looked at it and it is worth your time
# 'applied' is written later by Phase 5 and is never touched here.
TERMINAL = ("applied",)


# ── the free pass ───────────────────────────────────────────────────────────

class Rules:
    """Compiled form of targets.yaml. Compiling once matters: this runs 9,788
    times, and re.compile inside the loop was measurably the slow part."""

    def __init__(self, cfg):
        self.buckets = tuple(cfg.get("location_buckets") or ())
        self.require_remote = bool(cfg.get("require_remote", True))
        self.exclude = [re.compile(p, re.I) for p in cfg.get("exclude_titles") or []]
        self.use_seniority = bool(cfg.get("exclude_seniority", True))
        self.seniority = [re.compile(p, re.I) for p in cfg.get("seniority_patterns") or []]
        # Kept as (source_text, compiled) so the funnel can name the lane that
        # let a job in. A single fused regex would be faster and would tell you
        # nothing about why your shortlist looks the way it does.
        self.include = [(p, re.compile(p, re.I)) for p in cfg.get("include_titles") or []]

    def judge(self, title, bucket, remote):
        """Return (verdict, reason, lane). verdict is 'pool' or 'filtered'.

        Order is cheapest-and-most-certain first, and the FIRST failure is the
        recorded reason — so the funnel counts are a partition, not overlapping
        sets, and they add up to the total."""
        title = title or ""
        if bucket not in self.buckets:
            return "filtered", f"location:{bucket or 'unknown'}", None
        if self.require_remote and not remote:
            return "filtered", "not-remote", None
        for rx in self.exclude:
            if rx.search(title):
                return "filtered", "excluded-title", None
        if self.use_seniority:
            for rx in self.seniority:
                if rx.search(title):
                    return "filtered", "too-senior", None
        for src, rx in self.include:
            if rx.search(title):
                return "pool", None, src
        return "filtered", "no-lane-matched", None


def ensure_columns(conn):
    """Add our two columns if this database predates them.

    Written as an idempotent check rather than a migration file because the
    database is a local cache — if it were ever lost, ingest.py rebuilds it,
    and a migrations table would be more machinery than the problem deserves."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    for col in ("filter_reason", "lane", "scored_at"):
        if col not in have:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
    conn.commit()


def run_rules(conn, rules, verbose=True):
    """Re-judge every non-applied job. Returns the funnel counts.

    This deliberately re-judges jobs it has already judged. targets.yaml is
    meant to be edited, and a filter that only ever looked at new rows would
    mean editing the file did nothing until the next crawl — the single most
    confusing thing this pipeline could do."""
    rows = conn.execute(
        "SELECT id, title, bucket, remote, status, location FROM jobs"
        " WHERE status IS NULL OR status NOT IN (%s)"
        % ",".join("?" * len(TERMINAL)), TERMINAL).fetchall()

    counts = {}
    lanes = {}
    updates = []
    rebucketed = []
    for jid, title, bucket, remote, status, location in rows:
        # Recompute the bucket rather than trusting what ingest.py stored.
        # The bucket is DERIVED data, and locations.py gets fixed — the
        # "Anywhere in France" bug put 16 European roles in the Canadian pool,
        # and if this trusted the stored value the only way to clear them would
        # be a full re-crawl of every board. Reclassifying here costs about a
        # tenth of a second and means a classifier fix lands immediately.
        fresh = classify(location, title or "")
        if fresh != bucket:
            rebucketed.append((fresh, jid))
            bucket = fresh
        verdict, reason, lane = rules.judge(title, bucket, remote)
        counts[reason or "pool"] = counts.get(reason or "pool", 0) + 1
        if verdict == "pool":
            lanes[lane] = lanes.get(lane, 0) + 1
            # Do not demote a job the model has already scored back to 'pool' —
            # that would throw away work and re-spend the GPU on every run.
            new_status = status if status in ("scored", "shortlist") else "pool"
            updates.append((new_status, None, lane, jid))
        else:
            # A job that used to be in the shortlist and now fails a rule DOES
            # get demoted. That is the point of editing targets.yaml.
            updates.append(("filtered", reason, None, jid))

    if rebucketed:
        conn.executemany("UPDATE jobs SET bucket=? WHERE id=?", rebucketed)
    conn.executemany(
        "UPDATE jobs SET status=?, filter_reason=?, lane=? WHERE id=?", updates)
    conn.commit()

    if verbose:
        if rebucketed:
            print(f"\n  reclassified {len(rebucketed):,} locations "
                  f"(locations.py changed since the last crawl)")
        print_funnel(conn, counts, lanes, len(rows))
    return counts


def print_funnel(conn, counts, lanes, total):
    print(f"\n  {total:,} jobs judged by the free rules\n")
    order = ["location:", "not-remote", "excluded-title", "too-senior", "no-lane-matched"]
    shown = set()
    print(f"  {'rejected because':<34}{'jobs':>8}")
    print("  " + "-" * 42)
    # Location reasons are per-bucket, so roll them up but keep the breakdown.
    loc = {k: v for k, v in counts.items() if k and k.startswith("location:")}
    if loc:
        print(f"  {'wrong location':<34}{sum(loc.values()):>8,}")
        for k in sorted(loc, key=lambda x: -loc[x]):
            print(f"     {k.split(':', 1)[1]:<31}{loc[k]:>8,}")
        shown |= set(loc)
    for key in order[1:]:
        if key in counts:
            label = {"not-remote": "not remote", "excluded-title": "title on exclude list",
                     "too-senior": "too senior", "no-lane-matched": "not a lane I want"}[key]
            print(f"  {label:<34}{counts[key]:>8,}")
            shown.add(key)
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        if k not in shown and k != "pool":
            print(f"  {str(k):<34}{v:>8,}")

    pool = counts.get("pool", 0)
    print("  " + "-" * 42)
    print(f"  {'SURVIVED -> worth the model':<34}{pool:>8,}")
    uniq = conn.execute(
        "SELECT COUNT(DISTINCT dedup_key) FROM jobs WHERE status IN"
        " ('pool','scored','shortlist')").fetchone()[0]
    print(f"  {'…of which distinct roles':<34}{uniq:>8,}")
    if lanes:
        print("\n  which lane let them in")
        print("  " + "-" * 60)
        for k, v in sorted(lanes.items(), key=lambda kv: -kv[1])[:12]:
            print(f"  {v:>6,}  {k[:52]}")
    print()


# ── the model pass ──────────────────────────────────────────────────────────

# The shape every reply must have. llama.cpp turns this into a grammar, so
# these field names and types are enforced by sampling, not by hope.
#
# ── WHY THE MODEL NO LONGER PICKS THE FINAL NUMBER ──────────────────────────
# The first version asked for a 0-100 `fit` against a banded rubric
# (0-39 / 40-59 / 60-79 / 80-100). Measured on a real sample of five: FOUR came
# back at exactly 40. Not because the model was confused — its prose was right
# every time, correctly spotting "requires 7 years", "requires 5+ years",
# "requires 2+ years". It simply parked on the floor of a band. A ranking where
# most rows share one value is not a ranking.
#
# So the split is now: the MODEL REPORTS FACTS, PYTHON DOES THE ARITHMETIC.
# `years_required` is the clearest case — the model reads it out of the posting
# accurately and it is an objective number, so a rule can act on it. Deciding
# the weight in Python also means retuning is instant and free, instead of
# another GPU pass over the whole pool.
#
# `fit_signal` is still the model's own judgement, but it now answers a
# narrower question ("how well does the SUBJECT MATTER line up") where there is
# no band structure to anchor to.
SCHEMA = {
    "type": "object",
    "properties": {
        # Smallest number of years the posting demands. 0 when it does not say.
        # -1 is not allowed: an unstated requirement and a stated zero should
        # both mean "no barrier", and giving the model a third option invites it
        # to reach for the hedge, which is how seniority_match became "unclear"
        # on 5 out of 5.
        "years_required": {"type": "integer"},
        "degree_required": {"type": "boolean"},
        # Does the posting demand US work authorisation, a clearance, a
        # specific city, or a timezone the candidate cannot hold?
        "hard_blocker": {"type": "boolean"},
        "fit_signal": {"type": "string",
                       "enum": ["strong", "decent", "weak", "wrong_field"]},
        # maxItems IS LOAD-BEARING, not tidiness. A grammar guarantees the reply
        # is SHAPED like valid JSON; it does not guarantee the model finishes
        # before max_tokens. Three of 192 jobs died with
        # `JSONDecodeError: Unterminated string` — the model was still happily
        # emitting a fourteenth knockout risk when the budget ran out, leaving a
        # half-written string with no closing quote. Capping the arrays in the
        # grammar makes the reply structurally unable to run long, which is a
        # better fix than raising max_tokens and hoping.
        "knockout_risks": {"type": "array", "items": {"type": "string"},
                           "maxItems": 5},
        "missing_skills": {"type": "array", "items": {"type": "string"},
                           "maxItems": 8},
        "one_line_why": {"type": "string"},
    },
    "required": ["years_required", "degree_required", "hard_blocker",
                 "fit_signal", "knockout_risks", "missing_skills",
                 "one_line_why"],
}

# Base score by subject-matter fit, then adjusted. These numbers are the whole
# ranking policy and they live here, in one readable place, on purpose — tuning
# them is a text edit and a re-run of the arithmetic, not another GPU pass.
FIT_BASE = {"strong": 88, "decent": 70, "weak": 45, "wrong_field": 15}


def compute_score(res, max_years=2):
    """Turn the model's findings into one number. Pure function, no I/O.

    max_years is what the candidate can credibly claim. Everything above it is
    penalised, steeply at first and then flattening: the gap between "wants 2
    years" and "wants 4" decides whether you are read at all, while the gap
    between "wants 8" and "wants 12" is academic — you are out either way."""
    score = FIT_BASE.get(res.get("fit_signal"), 45)

    yrs = res.get("years_required") or 0
    over = max(0, int(yrs) - max_years)
    # 12 for the first year over, 8 for the next, 5 for each after, capped.
    penalty = min(45, sum((12, 8)[min(i, 1)] if i < 2 else 5 for i in range(over)))
    score -= penalty

    # ── THE SELF-CONTRADICTION CORRECTION ───────────────────────────────────
    # Measured on the Twilio ML Engineer posting: the model returned
    # fit_signal="strong" while simultaneously listing THIRTEEN required
    # technologies the candidate does not have, and writing a one_line_why that
    # said so in plain English. The prose was right; the label was not.
    #
    # This is the same lesson as years_required, one layer up — the model is a
    # reliable READER and an unreliable JUDGE. missing_skills is a reading, so
    # it gets to override fit_signal, which is a judgement. Five or more missing
    # requirements is not a strong match no matter what the label says.
    missing = len(res.get("missing_skills") or [])
    if missing >= 5:
        score = min(score, 55)
    score -= min(15, max(0, missing - 2) * 3)

    # A hard blocker is not a penalty, it is a wall. US-only authorisation or a
    # clearance means the application cannot succeed no matter how good the fit,
    # so it must land below any plausible shortlist threshold rather than merely
    # docking a few points off a strong match.
    if res.get("hard_blocker"):
        score = min(score, 25)

    # A required degree is NOT a blocker — he has a CS degree. It is only worth
    # noting, so it costs nothing. Kept in the schema because it is one of the
    # things worth SEEING in the report.
    return max(0, min(100, score))

# NO RESUME EXISTS YET. Until profile.yaml lands (PLAN.md Phase 1) the model is
# told who the candidate is in general terms only. This is stated plainly in
# the prompt rather than faked, because a model given an invented background
# will confidently score against that invention and the numbers will look
# perfectly reasonable while meaning nothing.
CANDIDATE_FALLBACK = """\
Recent Computer Science / IT graduate based in Ontario, Canada.
Roughly 0-2 years of professional experience. Comfortable with Python, Linux,
SQL, Git and general software fundamentals. Legally able to work in Canada;
NOT authorised to work in the United States. Needs a fully remote role.
"""

PROMPT = """\
You are screening job postings for one specific candidate.

CANDIDATE
{candidate}

POSTING
Title: {title}
Company: {company}
Location: {location}

{description}

TASK
Report what this posting actually requires. Do not rate the candidate overall —
that is computed from your answers. Judge only what the posting says. If the
posting does not mention something, that is not a requirement.

years_required
  The smallest number of years of experience the posting demands. Read the
  requirements section. "2+ years" -> 2. "3-5 years" -> 3. "5 or more" -> 5.
  If no number appears anywhere, answer 0.

degree_required
  true only if a degree is stated as required, not "preferred" or "or
  equivalent experience".

hard_blocker
  true if the posting demands something this candidate cannot obtain: US work
  authorisation or a US-only hiring policy, a security clearance, a
  professional licence, residence in a specific city or country other than
  Canada, or a working timezone far from Eastern Time. Otherwise false.

fit_signal
  How well the SUBJECT MATTER lines up with what the candidate knows. Ignore
  years of experience here — that is counted separately, and counting it twice
  is the most common way this goes wrong.
    strong       squarely the work they can do
    decent       adjacent; they would need to pick some things up
    weak         same industry, quite different job
    wrong_field  not really a match for this background at all

knockout_risks
  Short phrases only, one per risk. Quote the posting where you can.

missing_skills
  Named tools or technologies the posting requires that the candidate profile
  does not mention. Names only, no sentences.
"""


def service_active(unit):
    return subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit]).returncode == 0


def wait_for_model(endpoint, timeout=240):
    """Poll /models until the server answers.

    Loading a 4B onto the GPU takes 10-25 seconds; systemd says the unit is
    'active' the moment the process exists, which is long before the model is
    resident. Trusting systemd here produces a connection-refused that looks
    like a broken service and is really just impatience."""
    deadline = time.time() + timeout
    url = endpoint.rstrip("/") + "/models"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    return False


def call_model(endpoint, model, prompt, timeout=180):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        # Low but not zero. Deterministic scoring is what you want for a
        # ranking; 0.0 on a small model tends to collapse onto a couple of
        # round numbers and flatten the ordering.
        "temperature": 0.2,
        # 400 was not enough for the wordiest 1.5% of postings. Raised with the
        # array caps above rather than instead of them — the caps stop the
        # rambling, this leaves room for the ones that legitimately need it.
        "max_tokens": 700,
        "response_format": {"type": "json_object", "schema": SCHEMA},
    }).encode()
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return json.loads(data["choices"][0]["message"]["content"])


def load_candidate():
    """Use profile.yaml the moment it exists, otherwise say so out loud."""
    prof = os.path.join(HERE, "profile.yaml")
    if os.path.exists(prof):
        with open(prof) as f:
            p = yaml.safe_load(f) or {}
        return p.get("summary") or yaml.safe_dump(p, sort_keys=False)
    return None


def run_model_pass(conn, cfg, limit=None, rescore=False, dry_run=False):
    sc = cfg.get("scoring") or {}
    endpoint = sc.get("endpoint", "http://127.0.0.1:8081/v1")
    model = sc.get("model", "luminos-local")
    unit = sc.get("service", "jobhunt-llm.service")
    maxchars = int(sc.get("description_chars", 6000))
    shortlist_min = int(sc.get("shortlist_min", 60))
    max_per_run = int(sc.get("max_per_run", 400))
    max_years = int(sc.get("max_years_experience", 2))

    candidate = load_candidate()
    if candidate is None:
        candidate = CANDIDATE_FALLBACK
        print("  NOTE: no profile.yaml yet — scoring against a generic recent-grad")
        print("        profile. Scores are directionally useful, not final.\n")

    want = ("pool", "scored", "shortlist") if rescore else ("pool",)
    sql = ("SELECT id, title, company, location, description FROM jobs"
           " WHERE status IN (%s)" % ",".join("?" * len(want)) +
           " GROUP BY dedup_key ORDER BY first_seen DESC")
    rows = conn.execute(sql, want).fetchall()
    if limit:
        rows = rows[:limit]

    if not rows:
        print("  nothing to score — the pool is empty")
        return 0

    if dry_run:
        jid, title, company, location, desc = rows[0]
        print(PROMPT.format(candidate=candidate, title=title, company=company,
                            location=location, description=(desc or "")[:maxchars]))
        print(f"\n[dry run] would score {len(rows)} jobs")
        return 0

    if len(rows) > max_per_run:
        print(f"  REFUSING: {len(rows):,} jobs to score exceeds max_per_run "
              f"({max_per_run}).\n  Tighten targets.yaml, or raise max_per_run "
              f"if you meant it, or use --limit.")
        return 0

    started_by_us = False
    if not wait_for_model(endpoint, timeout=3):
        print(f"  starting {unit} …")
        subprocess.run(["systemctl", "--user", "start", unit], check=True)
        started_by_us = True
        if not wait_for_model(endpoint):
            subprocess.run(["systemctl", "--user", "stop", unit])
            sys.exit(f"  FAIL: {unit} started but never answered on {endpoint}\n"
                     f"  check: journalctl --user -u {unit} -n 40")
    print(f"  model up — scoring {len(rows):,} jobs\n")

    ok = fail = short = 0
    t0 = time.time()
    try:
        for i, (jid, title, company, location, desc) in enumerate(rows, 1):
            prompt = PROMPT.format(
                candidate=candidate, title=title or "?", company=company or "?",
                location=location or "?", description=(desc or "")[:maxchars])
            try:
                res = call_model(endpoint, model, prompt)
            except Exception as e:
                fail += 1
                print(f"  [{i}/{len(rows)}] FAIL {(title or '?')[:44]}: "
                      f"{type(e).__name__}: {e}")
                continue
            fit = compute_score(res, max_years=max_years)
            # Keep the derived number next to the findings it came from. Six
            # weeks from now "why is this a 58" is only answerable if both are
            # on the row.
            res["fit"] = fit
            status = "shortlist" if fit >= shortlist_min else "scored"
            if status == "shortlist":
                short += 1
            # The whole JSON goes in, not just the number. When a score looks
            # wrong six weeks from now, "why" is the only thing that helps, and
            # re-running the model to find out costs another GPU hour.
            # Write the score to every listing of the SAME ROLE — one job posted
            # on three boards is one job, and scoring it three times would waste
            # the GPU. But only to listings still IN THE POOL.
            #
            # The "AND status IN" clause is not defensive noise: without it this
            # statement promoted rows the rules had correctly filtered. Twilio's
            # ML Engineer is posted for both Canada and the US under one
            # dedup_key; the Canadian row was judged, and the unqualified UPDATE
            # dragged the us_only row out of 'filtered' and into the shortlist,
            # where status.py then displayed its "Remote - US" location. The
            # score looked fine. The row underneath it was wrong.
            conn.execute(
                "UPDATE jobs SET score=?, score_reason=?, status=?, scored_at=?"
                " WHERE dedup_key=(SELECT dedup_key FROM jobs WHERE id=?)"
                "   AND status IN ('pool','scored','shortlist')",
                (fit, json.dumps(res, ensure_ascii=False), status,
                 time.strftime("%Y-%m-%dT%H:%M:%S"), jid))
            ok += 1
            if ok % 10 == 0:
                conn.commit()
            rate = i / max(time.time() - t0, 1e-6)
            eta = (len(rows) - i) / max(rate, 1e-6)
            mark = "*" if status == "shortlist" else " "
            print(f"  [{i}/{len(rows)}]{mark}{fit:>4}  {(company or '?')[:18]:19}"
                  f"{(title or '?')[:42]:43} eta {eta/60:4.1f}m")
    except KeyboardInterrupt:
        print("\n  interrupted — progress so far is saved")
    finally:
        conn.commit()
        if started_by_us:
            print(f"\n  stopping {unit} so the dGPU can sleep")
            subprocess.run(["systemctl", "--user", "stop", unit])

    dt = time.time() - t0
    print(f"\n  scored {ok:,} ({fail} failed) in {dt/60:.1f} min — "
          f"{short:,} made the shortlist (>= {shortlist_min})")
    return ok


def recompute(conn, cfg):
    """Re-rank from answers already stored, without calling the model at all.

    This is the payoff for having the model report facts instead of a verdict:
    changing max_years_experience, or the FIT_BASE weights, re-ranks the whole
    pool in about a second and costs nothing. Under the old design the same
    change meant another full GPU pass."""
    sc = cfg.get("scoring") or {}
    shortlist_min = int(sc.get("shortlist_min", 60))
    max_years = int(sc.get("max_years_experience", 2))
    rows = conn.execute(
        "SELECT id, score_reason FROM jobs WHERE score_reason IS NOT NULL"
        " AND status IN ('scored','shortlist')").fetchall()
    n = short = skipped = 0
    for jid, reason in rows:
        try:
            res = json.loads(reason)
        except (TypeError, ValueError):
            skipped += 1
            continue
        # Rows scored by the OLD prompt have no fit_signal and cannot be
        # recomputed — they only ever stored a verdict. Leave them alone and
        # say so, rather than silently scoring them all 45 by default.
        if "fit_signal" not in res:
            skipped += 1
            continue
        fit = compute_score(res, max_years=max_years)
        res["fit"] = fit
        status = "shortlist" if fit >= shortlist_min else "scored"
        short += status == "shortlist"
        conn.execute("UPDATE jobs SET score=?, score_reason=?, status=? WHERE id=?",
                     (fit, json.dumps(res, ensure_ascii=False), status, jid))
        n += 1
    conn.commit()
    print(f"  re-ranked {n:,} jobs from stored answers — {short:,} shortlisted "
          f"(>= {shortlist_min}, max_years={max_years})")
    if skipped:
        print(f"  {skipped:,} skipped — scored by an older prompt; "
              f"re-run ./score.py --rescore to refresh them")


def main():
    ap = argparse.ArgumentParser(description="Score the job pool")
    ap.add_argument("--rules-only", action="store_true",
                    help="free pass only — no model, no GPU (~2s)")
    ap.add_argument("--limit", type=int, help="score at most N jobs")
    ap.add_argument("--rescore", action="store_true",
                    help="re-score jobs the model has already seen")
    ap.add_argument("--recompute", action="store_true",
                    help="re-rank from stored answers — no model, no GPU (~1s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print one prompt and exit without calling anything")
    ap.add_argument("--quiet", action="store_true", help="skip the funnel table")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit("no database yet — run ./ingest.py first")
    with open(TARGETS) as f:
        cfg = yaml.safe_load(f)

    conn = sqlite3.connect(DB_PATH)
    ensure_columns(conn)
    if args.recompute:
        return recompute(conn, cfg)
    run_rules(conn, Rules(cfg), verbose=not args.quiet)
    if args.rules_only:
        return
    run_model_pass(conn, cfg, limit=args.limit, rescore=args.rescore,
                   dry_run=args.dry_run)


if __name__ == "__main__":
    main()
