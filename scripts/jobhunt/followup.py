#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-27]
"""followup.py — read employer replies, decide what they mean, answer them.

Phase 5. Reads mail, works out which messages are about applications we actually
sent, records what happened into `track.py`'s event log, drafts the reply where a
reply is wanted, and **stops and notifies Shawn when a company wants to schedule
an interview** — which is the one outcome the whole pipeline exists to produce
and the one thing it is not allowed to handle by itself.

WHAT THIS WAS BUILT AGAINST
---------------------------
Not guessed phrasing. The rules below come from reading ~400 days of the real
inbox, and the real inbox is much less cooperative than a design doc:

  * The real Walmart rejection has the subject **"Thank you for your interest"**
    and contains *"This isn't the end, though! ... we may contact you"*. A
    keyword classifier reads that as encouraging. It is a rejection.
  * A Temu marketing mail is titled **"Congrats! Vratik Patel"**. Another says
    **"Thank you for your purchase!"**. A car-loan company sent
    **"(Next Steps) We've received your application"** — job-application
    vocabulary, for a vehicle.
  * Searching 400 days for `subject:(interview OR "next steps" OR "selected
    for")` returned **two hits, both false positives** — a Randstad newsletter
    about interview technique, and that car loan.
  * A real employer (Sault Area Hospital) replies from
    `sah.subscriptions@gmail.com` — a plain Gmail address. **An ATS-domain
    allowlist alone silently drops real replies.**
  * One thread is `Automatic reply: DATA SYSTEMS SPECIALIST` — an Outlook
    out-of-office. Nobody read anything. It is not an acknowledgement.

SO: PROVENANCE FIRST, MEANING SECOND
------------------------------------
The gate is not "does this email sound like a job reply". It is "can this be
tied to an application we have a record of sending". We know who we applied to
and when, because `track.py` wrote it down. Everything that cannot be tied to a
sent application is dropped before a single word of it is interpreted. That
turns an open-vocabulary problem into a closed one, and it is why the Temu
"Congrats!" never gets a vote.

WHEN UNSURE, ESCALATE — NEVER GUESS
-----------------------------------
`rejected` is terminal in the event log. A rejection that is really an interview
invitation ends the role permanently and Shawn never hears about it. That is the
single most expensive mistake this program can make, so:

  * A decisive rejection phrase and a decisive interview phrase in the same
    message is **not** resolved by precedence. It becomes `needs_review`.
  * Anything the rules cannot place decisively becomes `needs_review`.
  * `needs_review` is recorded as a `note` and surfaced to Shawn. It is never
    quietly filed as a rejection to keep the board tidy.

And there is a real asymmetry worth stating plainly: there are about ten genuine
rejections in the archive to test the rejection path against, and **zero genuine
interview invitations**. The branch that matters most is the branch that cannot
be validated on historical mail. That is the reason for the caution above, and
for `track.py`'s "CLOSED, BUT REACHED YOU FIRST" section.

REPLYING
--------
Shawn asked for replies to be handled without him. Reading the archive, almost
nothing actually wants a reply: rejections and acknowledgements are sent from
no-reply addresses and say *"This is an automated email - Please do not
respond."* So the reply path is narrow on purpose:

  * Never reply to a no-reply sender. Detected from the address AND the body.
  * Never auto-reply to an interview invitation. He asked to be stopped there,
    and picking a time on someone's behalf is not a thing to do from a template.
  * Reply from templates, not from a model writing prose in his name. Same
    reasoning as DECISION 83: a generated reply can state a fact about him that
    is not true, and unlike a resume bullet, nobody proofreads an email that was
    already sent.

Sending needs Gmail OAuth (`gmail.compose`). Until that exists this drafts and
shows; `--send` refuses with an explanation rather than pretending.

USAGE
    ./followup.py --from-json mail.json      # classify a file of messages
    ./followup.py --from-json mail.json -v   # show why each was classified
    ./followup.py --scan                     # read Gmail (needs OAuth)
    ./followup.py --explain "some text"      # classify one blob of text
    ./followup.py --self-test                # the real archive examples
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track
import ingest

OAUTH_PATH = os.path.expanduser("~/.config/luminos/jobhunt-gmail.json")
NOTIFY_PATH = os.path.expanduser("~/.local/share/luminos/jobhunt/needs-you.md")

# ---------------------------------------------------------------- provenance

# Applicant tracking systems seen in the real archive, plus the ones apply.py
# will be submitting through. Presence here is evidence FOR a message being a
# real reply. Absence is not evidence against it — see sah.subscriptions@gmail.
ATS_DOMAINS = (
    "myworkday.com", "successfactors.com", "dayforce.com", "greenhouse.io",
    "ashbyhq.com", "lever.co", "workable.com", "smartrecruiters.com",
    "icims.com", "jobvite.com", "bamboohr.com", "recruitee.com", "teamtailor.com",
    "breezy.hr", "rippling.com", "gusto.com", "hire.google.com", "taleo.net",
)

# Bulk senders that use application vocabulary and mean none of it. These are
# dropped before classification, never after.
NOISE_SENDERS = (
    "jobalert.indeed.com", "alert.indeed.com", "bebee.com", "linkedin.com",
    "ziprecruiter.com", "glassdoor.com", "monster.com", "randstad.ca",
    "temuemail.com", "temuofficial.com", "affirm.ca", "splitwise.com",
    "quora.com", "samsung.com", "puma.com", "2k.com",
)

NOISE_SUBJECT = re.compile(
    r"and \d+ more new jobs"          # Indeed digest
    r"|^automatic reply:"             # Outlook out-of-office — nobody read it
    r"|^out of office"
    r"|unsubscribe",
    re.I)

# A reply is pointless and slightly embarrassing when sent to one of these.
NOREPLY_ADDR = re.compile(r"(no-?reply|donot-?reply|notify@|system@|automated)", re.I)
NOREPLY_BODY = re.compile(
    r"this is an automated (e-?mail|message)"
    r"|please do not respond"
    r"|do not reply to this (e-?mail|message)"
    r"|unmonitored (mailbox|inbox)",
    re.I)

# ------------------------------------------------------------- what it means

# Ordered, and each entry is (kind, regex, decisive).
#
# DECISIVE means the phrase settles the message on its own. Non-decisive phrases
# only break ties, because on their own they are exactly the words that appear
# in the consolation paragraph of a rejection ("we may contact you", "keep an
# eye on our career site") and in Temu's "Congrats!".
RULES = [
    # --- interview: the outcome that matters, so the patterns are specific ---
    ("interview", r"\b(selected|shortlisted) for an? (interview|phone screen)\b", True),
    ("interview", r"\b(invite|inviting) you (to|for) an? (interview|call|chat)\b", True),
    ("interview", r"\b(schedule|set ?up|book|arrange) (an?|your|a time for an?)\s*"
                  r"(interview|phone screen|call|chat|conversation)\b", True),
    ("interview", r"\b(interview|phone screen) (invitation|invite|request)\b", True),
    ("interview", r"\b(would like|we'?d like|like) to (schedule|set ?up|arrange)\b", True),
    ("interview", r"\bavailability (for|to) (an?|the) (interview|call|chat)\b", True),
    ("interview", r"\b(calendly|savvycal|book a time|pick a time|choose a time)\b", False),
    ("interview", r"\bnext (round|stage|step) (is|will be) an? interview\b", True),

    ("offer",     r"\b(pleased|delighted|happy) to (offer|extend)\b", True),
    ("offer",     r"\b(offer of employment|employment offer|job offer)\b", True),

    ("assessment", r"\b(take[- ]home|coding (challenge|test|exercise)|technical "
                   r"(assessment|screen|test))\b", True),
    ("assessment", r"\b(hackerrank|codility|codesignal|karat|coderpad|woven)\b", True),
    ("assessment", r"\bcomplete (an?|the) (assessment|challenge|exercise)\b", True),

    ("recruiter_interest", r"\bscreening call\b", True),
    ("recruiter_interest", r"\b(are|if) you (still )?(interested|available)\b", False),
    ("recruiter_interest", r"\b(learn more about|discuss) your (background|experience)\b", False),

    # --- rejection: many real examples, so these are the best-tested rules ---
    ("rejected", r"\bdecided not to (move|go) forward\b", True),
    ("rejected", r"\bnot (be )?(moving|going|progressing) forward\b", True),
    ("rejected", r"\bwill not be (moving|progressing|proceeding)\b", True),
    ("rejected", r"\bmade the decision not to\b", True),
    ("rejected", r"\b(pursue|pursuing|selected|chosen|moving forward with) "
                 r"(other|another|different) (candidate|applicant)", True),
    ("rejected", r"\bno longer under consideration\b", True),
    ("rejected", r"\bnot (been )?(selected|successful)\b", True),
    ("rejected", r"\b(position|role|posting) (has been|was) (filled|closed)\b", True),
    ("rejected", r"\bwe (have )?(decided|elected) to (pursue|proceed with) other\b", True),
    ("rejected", r"\bunfortunately\b", False),
    ("rejected", r"\bwish you (all the best|the best|success)\b", False),

    # --- acknowledgement: high volume, zero action needed ---
    ("acknowledged", r"\b(application|resume|cv) (has been|was) received\b", True),
    ("acknowledged", r"\bwe('ve| have) received your (application|resume|cv)\b", True),
    ("acknowledged", r"\bthank you for (applying|your application|completing your "
                     r"application|submitting)\b", True),
    ("acknowledged", r"\b(currently )?under review by\b", True),
    ("acknowledged", r"\byour application is (now )?(being processed|in review)\b", True),
]

# Which kinds are decisive-conflicting: a message carrying decisive evidence for
# two of these at once is not something to resolve by precedence.
POLARITY = {"interview": +1, "offer": +1, "assessment": +1,
            "recruiter_interest": +1, "rejected": -1, "acknowledged": 0}


def strip_quoted(body):
    """Drop quoted history so last month's rejection cannot classify this reply.

    A threaded reply carries the whole conversation underneath it. Without this,
    an interview invitation sent in the same thread as an earlier automated
    acknowledgement inherits every phrase that acknowledgement contained.
    """
    out = []
    for line in (body or "").splitlines():
        s = line.strip()
        if s.startswith(">"):
            continue
        if re.match(r"^-{2,}\s*(original message|forwarded message)", s, re.I):
            break
        if re.match(r"^on .{5,80}\bwrote:$", s, re.I):
            break
        if re.match(r"^from:\s", s, re.I) and out:
            break
        out.append(line)
    return "\n".join(out)


def is_noise(msg):
    """Bulk mail that borrows the vocabulary. Dropped before interpretation."""
    sender = (msg.get("sender") or "").lower()
    subject = msg.get("subject") or ""
    for d in NOISE_SENDERS:
        if d in sender:
            return f"bulk sender ({d})"
    if NOISE_SUBJECT.search(subject):
        return "bulk/auto subject"
    return None


def sender_domain(sender):
    m = re.search(r"[\w.+-]+@([\w.-]+)", sender or "")
    return (m.group(1) if m else "").lower()


def provenance(conn, msg):
    """Tie a message to an application we have a record of sending.

    Returns (dedup_key, why) or (None, why-not). This runs BEFORE any reading of
    what the message says, and it is the reason a marketing mail titled
    "Congrats! Vratik Patel" never reaches the classifier.

    Three ways in, in descending order of confidence:
      1. the sender's domain belongs to a company we applied to
      2. the sender is a known ATS *and* the text names a role we applied to
      3. the text names both a company we applied to and its role title
    """
    dom = sender_domain(msg.get("sender"))
    blob = f"{msg.get('subject','')}\n{strip_quoted(msg.get('body',''))}".lower()

    applied = conn.execute(
        "SELECT DISTINCT e.dedup_key, j.company, j.title FROM events e"
        " JOIN jobs j ON j.dedup_key = e.dedup_key"
        " WHERE e.kind IN ('submitted','apply_ready','tailored')").fetchall()
    if not applied:
        return None, "no applications recorded yet"

    seen = {}
    for dk, company, title in applied:
        seen.setdefault(dk, (company or "", title or ""))

    # 1. company domain
    # [CHANGE: claude-code | 2026-08-27] norm_company(), not the raw name —
    # "Canonical Ltd." slugs to `canonicalltd`, which does not appear in
    # `canonical.com`, so the legal suffix would silently break the strongest
    # provenance check for every employer that writes one. BUG-141 again, in a
    # different tool.
    flat = dom.replace(".", "")
    for dk, (company, title) in seen.items():
        slug = re.sub(r"[^a-z0-9]", "", ingest.norm_company(company))
        if slug and len(slug) >= 4 and slug in flat:
            return dk, f"sender domain matches {company}"

    is_ats = any(a in dom for a in ATS_DOMAINS)

    # 2/3. the text names a role we applied to
    for dk, (company, title) in seen.items():
        t = (title or "").lower().strip()
        c = (company or "").lower().strip()
        title_hit = len(t) > 6 and t in blob
        comp_hit = len(c) > 3 and c in blob
        if title_hit and (is_ats or comp_hit):
            return dk, (f"names the role we applied to"
                        f"{' via ' + dom if is_ats else ''}")

    if is_ats:
        return None, f"known ATS ({dom}) but names no role we applied to"
    return None, f"cannot tie {dom or 'sender'} to any application we sent"


# [CHANGE: claude-code | 2026-08-27] A decisive phrase inside a conditional is
# not decisive. This is not hypothetical grammar-lawyering — it is the real
# Sault Area Hospital acknowledgement, which reads:
#
#   "your application has been received. You will be contacted by the
#    Recruitment Team IF YOU ARE SELECTED FOR AN INTERVIEW."
#
# That sentence describes a thing that has not happened. Without this guard it
# was classified `interview` and would have fired a critical notification about
# an interview nobody offered. Crying wolf on the single alert Shawn actually
# cares about is worse than a missed acknowledgement, because it teaches him to
# ignore the notification that matters.
#
# Only text BEFORE the match counts: "we'd like to schedule a call if you're
# available" is a real invitation with a trailing conditional, and must survive.
CONDITIONAL = re.compile(
    r"\b(if|should you|unless|in the event|in case|whether|would you be|"
    r"were you to|may be|might be|could be)\b[^.!?]{0,60}$", re.I)


def _conditional(text, match):
    """True when the phrase sits inside an 'if ...' clause in the same sentence."""
    before = text[:match.start()]
    before = re.split(r"[.!?]\s", before)[-1]   # this sentence only
    return bool(CONDITIONAL.search(before))


def classify(text):
    """What the message says happened. Returns (kind, decisive, why).

    kind is `needs_review` whenever the evidence is absent or contradictory. It
    is never a best guess, because the caller writes the answer into a log where
    `rejected` is terminal.
    """
    t = " ".join((text or "").split())
    hits = {}
    for kind, pattern, decisive in RULES:
        m = re.search(pattern, t, re.I)
        if not m:
            continue
        if decisive and _conditional(t, m):
            decisive = False        # "if you are selected for an interview"
        cur = hits.get(kind)
        if cur is None or (decisive and not cur[0]):
            hits[kind] = (decisive, m.group(0))

    decisive_kinds = [k for k, (d, _) in hits.items() if d]

    if not decisive_kinds:
        if not hits:
            return "needs_review", False, "no phrase matched"
        # Only soft evidence. "unfortunately" alone is not a rejection, and
        # "are you still interested" alone is not a recruiter reaching out.
        soft = ", ".join(f"{k}:{v[1]!r}" for k, v in hits.items())
        return "needs_review", False, f"only weak signals ({soft})"

    polarities = {POLARITY.get(k, 0) for k in decisive_kinds}
    if +1 in polarities and -1 in polarities:
        why = "; ".join(f"{k}:{hits[k][1]!r}" for k in decisive_kinds)
        return "needs_review", False, f"contradictory decisive evidence — {why}"

    # Furthest along wins among agreeing kinds: an invitation that also confirms
    # receipt is an invitation.
    best = max(decisive_kinds, key=lambda k: track.KINDS[k][0])
    return best, True, f"{hits[best][1]!r}"


def is_noreply(msg):
    if NOREPLY_ADDR.search(msg.get("sender") or ""):
        return "no-reply address"
    if NOREPLY_BODY.search(msg.get("body") or ""):
        return "body says not to respond"
    return None


# ----------------------------------------------------------------- answering

# Templates, not generated prose. A model writing in Shawn's name can assert a
# fact about him that is not true, and an email cannot be un-sent. Same rule as
# DECISION 83, with less margin for error.
TEMPLATES = {
    "recruiter_interest": (
        "Hi {first},\n\n"
        "Thanks for getting back to me — yes, I'm still interested in the "
        "{title} role.\n\n"
        "I'm available to talk on short notice and can work with whatever time "
        "suits your team. Happy to answer anything else you need in the "
        "meantime.\n\n"
        "Best,\nVratik Patel"
    ),
    "assessment": (
        "Hi {first},\n\n"
        "Thanks for sending the assessment for the {title} role. I'll complete "
        "it and return it before the deadline.\n\n"
        "Best,\nVratik Patel"
    ),
}

# Deliberately absent: `interview`, `offer`, `rejected`, `acknowledged`.
#   interview / offer — Shawn asked to be stopped here, and a template cannot
#                       know his calendar.
#   rejected          — nothing to say, and the sender is a no-reply robot.
#   acknowledged      — replying to a receipt confirmation is noise.


def draft_reply(kind, msg, title):
    if kind not in TEMPLATES:
        return None
    first = "there"
    m = re.match(r"\s*\"?([A-Z][a-z]+)", msg.get("sender_name") or "")
    if m:
        first = m.group(1)
    # [CHANGE: claude-code | 2026-08-27] Job-board titles carry the whole
    # posting headline — "Graduate Software Engineer, Open Source and Linux,
    # Canonical Ubuntu". Quoting that back reads like a bot pasting a database
    # field, so keep the part before the first comma, which is the actual role.
    short = (title or "").split(",")[0].strip()
    return TEMPLATES[kind].format(first=first, title=short or "the role")


# ---------------------------------------------------------------- notifying

def notify(lines):
    """Put what needs him in front of him, in two places that survive a reboot."""
    if not lines:
        return
    os.makedirs(os.path.dirname(NOTIFY_PATH), exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with open(NOTIFY_PATH, "a") as f:
        f.write(f"\n## {stamp}\n")
        for l in lines:
            f.write(f"- {l}\n")
    try:
        subprocess.run(
            ["notify-send", "-u", "critical", "-a", "jobhunt",
             f"{len(lines)} job thing(s) need you",
             "\n".join(lines[:4]) + "\n\n./track.py"],
            timeout=5, check=False)
    except Exception:
        pass  # a missing notifier must not lose the written record above


# -------------------------------------------------------------- mail readers

def read_json(path):
    """Messages from a file. This is how the classifier gets tested on real mail
    before Gmail OAuth exists — export threads, run them through, read the
    verdicts. Accepts either a bare list or the MCP `{"threads": [...]}` shape."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        msgs = []
        for t in data.get("threads", data.get("messages", [])):
            msgs.extend(t.get("messages", [t]) if isinstance(t, dict) else [])
        data = msgs
    out = []
    for m in data:
        out.append({
            "id": m.get("id") or m.get("messageId") or "",
            "sender": m.get("sender") or m.get("from") or "",
            "sender_name": m.get("sender_name") or "",
            "subject": m.get("subject") or "",
            "body": m.get("plaintextBody") or m.get("body") or m.get("snippet") or "",
            "date": m.get("date") or "",
        })
    return out


def read_gmail(days):
    """Unattended read over Gmail OAuth.

    Not the MCP connector: that is authorised inside a chat session and a 03:30
    systemd timer has no session. This is the reason OAuth is on Shawn's list.
    """
    if not os.path.exists(OAUTH_PATH):
        sys.exit(
            f"\n  no Gmail credentials at {OAUTH_PATH}\n\n"
            "  This needs a Google Cloud OAuth client — scopes gmail.readonly\n"
            "  and gmail.compose (NOT gmail.send). Until then:\n\n"
            "    ./followup.py --from-json <exported-messages.json>\n")
    try:
        from google.oauth2.credentials import Credentials       # noqa: F401
        from googleapiclient.discovery import build             # noqa: F401
    except ImportError:
        sys.exit("\n  google-api-python-client is not installed in this venv.\n"
                 "  /opt/luminos/venv-jobhunt/bin/pip install "
                 "google-api-python-client google-auth-oauthlib\n")
    sys.exit("\n  --scan is not wired up yet: the credentials file has never\n"
             "  existed, so this path has never been run against real Gmail and\n"
             "  shipping it untested would be a claim, not a feature.\n"
             "  Use --from-json today.\n")


# --------------------------------------------------------------------- main

def process(conn, msgs, verbose=False, dry=True):
    """Gate, classify, record, draft. Returns (rows, escalations)."""
    rows, escalate = [], []
    for m in msgs:
        why_noise = is_noise(m)
        if why_noise:
            if verbose:
                rows.append(("drop", m, "noise", why_noise, None))
            continue

        dk, why_prov = provenance(conn, m)
        if dk is None:
            if verbose:
                rows.append(("drop", m, "unrelated", why_prov, None))
            continue

        body = strip_quoted(m.get("body", ""))
        kind, decisive, why = classify(f"{m.get('subject','')}\n{body}")

        job = conn.execute(
            "SELECT id, company, title FROM jobs WHERE dedup_key=? LIMIT 1",
            (dk,)).fetchone()
        jid, company, title = job if job else ("", "", "")

        reply = None
        if kind == "needs_review":
            escalate.append(f"{company} — {title}: could not classify a reply "
                            f"({why}). ./track.py --show {jid[:12]}")
        elif kind in ("interview", "offer"):
            escalate.append(f"{company} — {title}: {track.KINDS[kind][1]}. "
                            f"{m.get('subject','')}")
        else:
            blocked = is_noreply(m)
            if not blocked:
                reply = draft_reply(kind, m, title)
            # [CHANGE: claude-code | 2026-08-27] An assessment gets BOTH a reply
            # and an escalation. The template says "I'll complete it and return
            # it before the deadline" — that is a commitment to do work, and
            # making a commitment on his behalf without telling him is the exact
            # over-eager failure this pipeline has to avoid. Same for a screening
            # call: something is expected of a human within days.
            if kind in ("assessment", "recruiter_interest"):
                escalate.append(
                    f"{company} — {title}: {track.KINDS[kind][1]}"
                    f"{' — replied, and it needs doing' if reply else ''}. "
                    f"{m.get('subject','')}")

        if not dry:
            record_kind = "note" if kind == "needs_review" else kind
            detail = (m.get("subject") or "")[:200]
            if kind == "needs_review":
                detail = f"UNCLASSIFIED REPLY: {detail} ({why})"
            track.record(conn, jid, record_kind, detail,
                         evidence=f"gmail:{m['id']}", at=m.get("date") or None)

        rows.append(("keep", m, kind, f"{why_prov}; {why}", reply))
    return rows, escalate


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--from-json", metavar="FILE", help="messages exported to JSON")
    ap.add_argument("--scan", action="store_true", help="read Gmail (needs OAuth)")
    ap.add_argument("--days", type=int, default=30, help="how far back to read")
    ap.add_argument("--explain", metavar="TEXT", help="classify one blob of text")
    ap.add_argument("--self-test", action="store_true",
                    help="run the real archive examples through the classifier")
    ap.add_argument("--apply", action="store_true",
                    help="actually write events (default is a dry run)")
    ap.add_argument("--send", action="store_true", help="send the drafted replies")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="also show what was dropped, and why")
    args = ap.parse_args()

    if args.explain:
        kind, decisive, why = classify(args.explain)
        print(f"\n  {kind}  {'(decisive)' if decisive else '(NOT decisive)'}"
              f"\n  {why}\n")
        return

    if args.self_test:
        return self_test()

    if args.send:
        sys.exit("\n  --send needs Gmail OAuth (gmail.compose) and there are no\n"
                 f"  credentials at {OAUTH_PATH}. Drafts print without it.\n")

    if args.scan:
        msgs = read_gmail(args.days)
    elif args.from_json:
        msgs = read_json(args.from_json)
    else:
        sys.exit("\n  need --from-json FILE, --scan, --explain or --self-test\n")

    conn = track.connect()
    rows, escalate = process(conn, msgs, args.verbose, dry=not args.apply)

    kept = [r for r in rows if r[0] == "keep"]
    print(f"\n  {len(msgs)} message(s) in, {len(kept)} about our applications")
    print("  " + "-" * 66)
    for state, m, kind, why, reply in rows:
        if state == "drop":
            print(f"  {track.DIM}drop  {(m['subject'] or '')[:44]:44} {why}"
                  f"{track.RESET}")
            continue
        colour = (track.GREEN if kind in ("interview", "offer") else
                  track.YELLOW if kind == "needs_review" else
                  track.RED if kind == "rejected" else "")
        print(f"  {colour}{kind:<18}{track.RESET} {(m['subject'] or '')[:44]}")
        if args.verbose:
            print(f"                     {track.DIM}{why}{track.RESET}")
        if reply:
            # [CHANGE: claude-code | 2026-08-27] Print the whole draft, not a
            # character count. Nobody should be asked to enable --send on the
            # strength of "drafted reply (198 chars)" — the only useful review
            # of an outgoing email is reading it.
            print(f"                     {track.DIM}would reply:{track.RESET}")
            for line in reply.splitlines():
                print(f"                     {track.DIM}| {line}{track.RESET}")

    if escalate:
        print(f"\n{track.BOLD}{track.GREEN}  NEEDS YOU{track.RESET}")
        print("  " + "-" * 66)
        for e in escalate:
            print(f"  {e}")
        if args.apply:
            notify(escalate)

    if not args.apply:
        print(f"\n  {track.DIM}dry run — nothing recorded. --apply to write "
              f"events.{track.RESET}")
    print()


# ------------------------------------------------------------------ self test

# Verbatim from the real archive, plus the adversarial cases it actually
# contains. `expect` is what a correct classifier must say — note that several
# of these are things a keyword matcher gets wrong.
CASES = [
    ("rejected", "Thank you for your interest",
     "Hi Vratik Thank you for your interest. We appreciate the time you took to "
     "apply with us. At this time we have decided not to move forward with your "
     "application for our BAKERY ASSOCIATE position. This isn't the end, though! "
     "If a position opens that closely matches your skills and experience, we may "
     "contact you as we have new positions that open all the time. We wish you all "
     "the best! Your Walmart Hiring Team"),

    ("rejected", "Your application for Inside Sales Representative",
     "Hi Vratik, Thank you for your interest in the Inside Sales Representative "
     "role at Wolseley Canada and for the time you invested in our process. After "
     "careful consideration, we've made the decision not to move forward with your "
     "application at this time."),

    ("acknowledged", "Application Received",
     "Dear VRATIK, Thank you for completing your application submission to Req ID "
     "54305- Nuclear Operator in Training - TERM. Our Recruitment team will be "
     "reviewing your application."),

    ("acknowledged", "Thank you for Applying",
     "Thank you Vratik for applying to Data Coordinator at Sault Area Hospital; "
     "your application has been received. You will be contacted by the Recruitment "
     "Team if you are selected for an interview."),

    ("recruiter_interest", "Final Reminder - Screening Call Required",
     "Hi Vratik, We noticed you haven't completed the screening call yet. If you're "
     "still interested in the position, please call +1 587-317-5629 today."),

    ("interview", "Next steps for your application",
     "Hi Vratik, we were impressed with your background and would like to schedule "
     "a 30 minute phone screen this week. Are you free Tuesday?"),

    ("interview", "Interview invitation",
     "We'd like to invite you to interview for the Graduate Software Engineer role. "
     "Please pick a time using the link below."),

    ("assessment", "Take-home exercise",
     "As the next step we'd like you to complete a take-home exercise. You'll have "
     "one week; the link is below."),

    ("offer", "Offer",
     "We are delighted to offer you the position of Software Engineer."),

    # The one that must NOT be read as encouraging: an acknowledgement that
    # mentions interviews as a hypothetical.
    ("acknowledged", "Thank you for Applying",
     "your application has been received. You will be contacted if you are "
     "selected for an interview."),

    # Contradictory decisive evidence -> must escalate, must not pick a side.
    ("needs_review", "Update",
     "We have decided not to move forward with this role, however we would like to "
     "schedule a call about a different opening."),

    # Soft signals only -> must escalate.
    ("needs_review", "Update on your application",
     "Unfortunately there have been some delays on our side. We wish you the best "
     "over the holidays."),
]


def self_test():
    print(f"\n  {len(CASES)} case(s) from the real archive\n  " + "-" * 66)
    bad = 0
    for expect, subject, body in CASES:
        got, decisive, why = classify(f"{subject}\n{body}")
        ok = got == expect
        bad += not ok
        mark = f"{track.GREEN}ok  {track.RESET}" if ok else f"{track.RED}FAIL{track.RESET}"
        print(f"  {mark} {expect:<18} {subject[:40]}")
        if not ok:
            print(f"       {track.RED}got {got!r} — {why}{track.RESET}")
        elif os.environ.get("VERBOSE"):
            print(f"       {track.DIM}{why}{track.RESET}")
    print(f"\n  {len(CASES) - bad}/{len(CASES)} correct\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
