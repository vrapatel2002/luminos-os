#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-26]
"""tailor.py — Phase 3. Turn one shortlisted posting into an application packet.

WHAT THIS DOES
    Reads a job out of the DB and `profile.yaml`, asks a model to pick the most
    relevant bullets FROM THE BULLET BANK BY ID, reorder them, and rewrite the
    summary and a short cover letter in the posting's own vocabulary. Then it
    checks the model's homework, renders a one-page PDF with pdflatex, and reads
    the PDF back with pdftotext to prove the words actually landed on the page.

THE ONE RULE THAT MATTERS
    A model asked to "tailor a resume" will invent. Not maliciously — it is
    doing what the words mean. Ask it to make a candidate look good for a role
    wanting five years of Kubernetes and it will produce five years of
    Kubernetes, in the candidate's voice, formatted beautifully. That document
    ends a career, not starts one.

    So the model here is NOT trusted to state facts. It is trusted to SELECT and
    to REPHRASE. Every bullet it emits must resolve to a `bullet_bank` id, and
    the rephrased text is diffed against the source entry: any number, any
    technology, any employer, any date that is not already in the source is a
    violation, and a violation rejects the whole packet. This is the same
    finding as BUG-109 wearing different clothes — an LLM is a reliable reader
    and an unreliable judge, so it reads the posting and rearranges known-true
    sentences, and it is never the source of a fact.

WHY pdflatex AND NOT TYPST (a deliberate deviation from PLAN.md)
    PLAN.md specifies Typst. Typst is not installed; pdflatex is, along with
    texlive-latex{,extra,recommended}, and it was verified end to end on this
    machine before this file was written — one page, clean pdftotext round-trip,
    every LaTeX metacharacter surviving intact. Adding a package to get a second
    way to do a thing that already works is the wrong trade. Swapping later is
    cheap: `render()` and `TEMPLATE` are the only two places that know.

    (xelatex is present too and is a TRAP — the binary exists but its format
    file does not, so it fails at run time with `I can't find the format file`.
    Installed is not the same as working. Do not "fix" this file by switching
    to xelatex or fontspec.)

USAGE
    ./tailor.py --list                 what is waiting, best first
    ./tailor.py --job <id>             tailor exactly one
    ./tailor.py --top 5                the best 5 not yet tailored
    ./tailor.py --top 5 --dry-run      everything except writing files
    ./tailor.py --job <id> --force     redo one that was already tailored
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Reused rather than re-implemented. score.py does no work at import time and
# has a __main__ guard, so importing it is free. cli_env() in particular is
# load-bearing and subtle (it strips the variables Cowork injects, which would
# otherwise point `claude` at a local gateway) — a second copy of that logic
# would rot out of step with the first.
import score  # noqa: E402
from score import CLI_BACKENDS, cli_env, extract_json  # noqa: E402

DB_PATH = score.DB_PATH
TARGETS = score.TARGETS
PROFILE = os.path.join(HERE, "profile.yaml")
OUT_ROOT = os.path.expanduser("~/.local/share/luminos/jobhunt/applications")


# ---------------------------------------------------------------------------
# What we ask for, and what we will accept back
# ---------------------------------------------------------------------------

# Written out in the prompt rather than enforced by a grammar, because no CLI
# backend accepts a grammar — that is BUG-140's lesson applied in advance
# instead of discovered again. Say the shape, say it is JSON, say it is not
# YAML, and parse defensively anyway.
FORMAT_SUFFIX = """

OUTPUT FORMAT — this overrides any other formatting habit you have.
Reply with ONE raw JSON object and nothing else. Not YAML. No markdown fence,
no commentary, no text before or after it. Exactly these five keys:

{"headline": "", "summary": "", "bullets": [{"id": "", "text": ""}],
 "cover_letter": "", "why_these": ""}
"""

PROMPT = """You are preparing a job application for a real person. Everything you
write will be checked against a fixed list of true statements, and anything you
add that is not on that list will be rejected automatically.

You may NOT state any fact of your own. You have exactly two jobs:
  1. CHOOSE which of the candidate's existing bullets are most relevant here.
  2. REPHRASE the ones you choose to use the posting's own vocabulary.

Rephrasing means changing the wording. It does not mean changing the content.
If a bullet says "5 Go daemons", you may write "five Go services" — you may NOT
write "8 Go daemons", and you may NOT add a number, a company, a tool, or a
date that is not already in that same bullet. If the posting wants something the
candidate has not done, the correct response is to leave it out, not to imply it.

=== THE POSTING ===
Company: {company}
Title: {title}
Location: {location}

{description}

=== THE CANDIDATE ===
{summary}

Skills he has, by honesty tier (do not claim anything outside these):
  strong:   {strong}
  working:  {working}
  familiar: {familiar}
  NOT YET (never claim these, not even softly): {not_yet}

Positioning he has already decided on, which you must follow:
{angle}

=== THE BULLET BANK — the only sentences you may draw from ===
{bank}

=== WHAT TO RETURN ===
headline      One line under his name, e.g. "Linux Systems Engineer" — it should
              echo the posting's title where that is honest, and must not claim
              seniority he does not have.
summary       2-3 sentences. Written for THIS posting. Same rules: no new facts.
bullets       6 to 10 entries, best first. Each is an id copied EXACTLY from the
              bank above, plus your rephrased text of that same bullet. Do not
              merge two bullets into one. Do not split one into two.
cover_letter  120-200 words, plain prose, no greeting and no sign-off (those get
              added when it is sent). Say why this role, using only facts from
              the bank. Be direct about having no professional employment yet
              rather than dancing around it — the posting's reader will find out
              in ninety seconds and would rather be told.

              You may name the company and the role title. Do NOT name the
              company's products, or any tool, technology, standard or
              framework that is not already in the candidate's skills or
              bullet bank above — not even admiringly. A checker cannot tell
              "I admire your work on X" from "I have used X", so it rejects
              both. Write about what HE has done.
why_these     One sentence, for the human reviewing this, on why you picked
              these bullets. This is not sent to the employer.
"""

FIX_HINT = ("\nYour previous reply was rejected. Reasons:\n{why}\n"
            "Return the raw JSON object only, and this time use ONLY facts "
            "already present in the bullet you are rephrasing.\n")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_profile():
    with open(PROFILE) as fh:
        p = yaml.safe_load(fh)
    ident = p.get("identity") or {}
    contact = p.get("contact") or {}

    # Fail loudly and early, per PLAN.md. A resume that renders with a blank
    # contact line looks fine in a PDF viewer and is worthless in an inbox.
    name = (ident.get("application_name") or "").strip()
    if not name:
        sys.exit("profile.yaml: identity.application_name is empty. Applications "
                 "must go out under the name on the ID and the degree.")
    if not (contact.get("email") or "").strip():
        sys.exit("profile.yaml: contact.email is empty. Refusing to render a "
                 "resume nobody can reply to. Add it and re-run.")

    # The one name that must never reach a document. It is in the file on
    # purpose (it is what he is called), which is exactly why it needs a guard.
    p["_forbidden_names"] = [n for n in [(ident.get("known_as") or "").strip()]
                             if n and n.lower() != name.lower()]
    return p


def flatten_bank(profile):
    """bullet_bank -> {"project.N": {...}} with the id the model will quote."""
    bank = {}
    for proj, body in (profile.get("bullet_bank") or {}).items():
        context = (body or {}).get("context") or ""
        for i, text in enumerate((body or {}).get("bullets") or [], 1):
            bid = f"{proj}.{i}"
            bank[bid] = {
                "id": bid,
                "project": proj,
                "context": " ".join(str(context).split()),
                "text": " ".join(str(text).split()),
            }
    if not bank:
        sys.exit("profile.yaml: bullet_bank is empty — nothing to tailor from.")
    return bank


def render_bank_for_prompt(bank):
    out = []
    seen = set()
    for b in bank.values():
        if b["project"] not in seen:
            seen.add(b["project"])
            out.append(f"\n[{b['project']}] {b['context']}")
        out.append(f"  {b['id']}: {b['text']}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# THE VALIDATOR — the reason this file exists
# ---------------------------------------------------------------------------

# A "claim token" is a word that carries a checkable fact. Ordinary English
# carries none and is free to change; these are not.
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#./_-]*")

# Words that look like proper nouns but are just sentence-initial or ordinary
# English. Without this list every rewrite starting with "The" is a violation.
_STOP = {
    "a", "an", "and", "as", "at", "built", "but", "by", "designed", "for",
    "from", "his", "i", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "then", "this", "to", "was", "were", "when", "which",
    "while", "with", "work", "worked", "you", "your", "my", "we", "our",
    "he", "she", "they", "them", "their", "there", "here", "not", "no",
    "so", "if", "than", "over", "under", "after", "before", "each", "both",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "first", "second", "role", "team", "company", "position", "job",
}


def norm(tok):
    return tok.lower().strip(".,;:()[]\"'").rstrip("s")


def variants(n):
    """A token and its plausible stems.

    There is no wordlist on this machine (`/usr/share/dict` does not exist), so
    matching is done on stems instead. Rephrasing legitimately turns
    "systems engineering" into "systems engineer" and "diagnosed" into
    "diagnosis"; without this, honest rewrites get rejected as inventions. The
    floor of 4 characters stops "led" collapsing to "l"."""
    out = {n}
    for suf in ("ings", "ing", "ers", "er", "ions", "ion", "ed", "es", "s", "d"):
        if n.endswith(suf) and len(n) - len(suf) >= 4:
            out.add(n[:-len(suf)])
    return out


def claim_tokens(text):
    """Numbers, and anything that looks like a named thing.

    Two signals, and the second one is fussier than it first appears:

      techy   contains a digit or one of + # . / _  — catches C++, C#, Node.js,
              llama.cpp, tensor_buft_overrides, IQ4_XS, 6GB. The hyphen is
              deliberately NOT in that set: hyphens are ordinary English
              ("self-directed", "root-caused") and including them flagged
              honest rewrites.

      proper  capitalised AND NOT at the start of a sentence. That second half
              is the whole trick. "Build and maintain..." starts with a capital
              because sentences do, not because Build is a company — the first
              version of this check rejected every honest rewrite for exactly
              that reason. A capital in the MIDDLE of a sentence is a name.

    Absolute on numbers, because numbers are where the lies live. A false
    positive costs one retry; a false negative puts a lie on a resume."""
    nums = set(_NUM.findall(text))
    names = set()
    for m in _WORD.finditer(text):
        # rstrip first, or sentence-final punctuation is read as technology:
        # "problems." ends in a dot, and a dot is what makes "llama.cpp" and
        # "Node.js" count as names. Without this, the last word of every
        # sentence was flagged as an invented term.
        w = m.group(0).rstrip("./-_")
        n = norm(w)
        if not n or n in _STOP:
            continue
        if not (any(c in w for c in "+#./_") or any(c.isdigit() for c in w)):
            if not (w[0].isupper() or w.isupper()):
                continue
            before = text[:m.start()].rstrip()
            if not before or before[-1] in ".!?:;•-–—\n":
                continue
        names.add(n)
    return nums, names


def vocab(text):
    """EVERY word of a true text, stemmed — the permitted vocabulary.

    Note the asymmetry with claim_tokens(), and it is the point. What we CHECK
    is narrow (numbers and names only, because that is where a lie can hide).
    What we PERMIT is wide (every word he has truthfully written), because
    rephrasing is the job — "hard problems" becoming "difficult problems" is
    the model doing what it was asked. Building the allowlist out of claim
    tokens instead of all words rejected honest rewrites for using the ordinary
    English already sitting in the profile."""
    nums = set(_NUM.findall(text))
    words = set()
    for m in _WORD.finditer(text):
        w = m.group(0).rstrip("./-_")
        # Split hyphenated compounds as well as keeping them whole. The bank
        # says "STREAM-style benchmark"; an honest rewrite says "a STREAM
        # benchmark". Without the split, the allowlist holds "stream-style"
        # only and the word STREAM reads as an invention.
        for piece in [w] + w.split("-"):
            n = norm(piece)
            if n:
                words |= variants(n)
    return nums, words


def build_allowlist(profile, bank):
    """Everything true about the candidate, as tokens.

    Used for the summary and the cover letter, which are allowed to draw on the
    whole profile. Individual BULLETS get a far tighter allowlist — only their
    own source entry — because a true fact attached to the wrong claim is still
    a false claim."""
    parts = [profile.get("summary") or ""]
    ident = profile.get("identity") or {}
    parts += [str(v) for v in ident.values() if isinstance(v, (str, int))]
    for tier, vals in (profile.get("skills") or {}).items():
        # `not_yet` is EXCLUDED on purpose, and getting this wrong would have
        # quietly defeated the whole file: it lists Kubernetes, Docker and the
        # cloud providers, so folding it in here would have made every one of
        # them an approved word to write on a resume. The skills he does not
        # have must not be reachable from the allowlist.
        if tier == "not_yet":
            continue
        parts += [str(s) for s in (vals or [])]
    for e in (profile.get("education") or []):
        parts += [str(v) for v in (e or {}).values()]
    for b in bank.values():
        parts += [b["text"], b["context"]]
    parts.append((profile.get("positioning") or {}).get("angle") or "")
    return vocab("\n".join(parts))


def not_yet_hits(text, profile):
    """Anything from skills.not_yet, named anywhere, in any case.

    Belt and braces over the allowlist. The allowlist catches an unknown word;
    this catches a KNOWN word he specifically said he cannot claim, even when
    it appears lowercase mid-sentence where the proper-noun rule would not
    look at it."""
    hits = []
    for entry in (profile.get("skills") or {}).get("not_yet") or []:
        for term in re.split(r"[/(),]", str(entry)):
            term = term.strip()
            if len(term) < 3:
                continue
            if re.search(rf"\b{re.escape(term)}\b", text, re.I):
                hits.append(term)
    return hits


# Things the profile explicitly says never to claim, checked as phrases rather
# than tokens because "no Kubernetes" is about meaning, not vocabulary.
_BANNED_PHRASES = [
    (re.compile(r"\b\d+\+?\s*years?\s+(of\s+)?(professional|industry|commercial|"
                r"paid|full[- ]time)\b", re.I),
     "claims professional years of employment"),
    (re.compile(r"\b(led|managed|mentored)\s+a\s+team\b", re.I),
     "claims having led a team"),
    (re.compile(r"\bin\s+production\s+at\s+scale\b", re.I),
     "claims production ownership"),
]


def check_text(text, allow_nums, allow_names, where):
    """`allow_names` must already be variant-expanded; each found token is
    matched on ANY of its stems, so only one side needs expanding at compare
    time."""
    bad = []
    nums, names = claim_tokens(text)
    for n in sorted(nums - allow_nums):
        bad.append(f"{where}: invented number {n!r}")
    for n in sorted(names):
        if not (variants(n) & allow_names):
            bad.append(f"{where}: invented term {n!r}")
    return bad


def validate(packet, profile, bank, posting=("", "")):
    """Return a list of violations. Empty list means the packet may be rendered."""
    bad = []
    all_nums, all_names = build_allowlist(profile, bank)
    # The prose fields may also use the employer's name and the role title —
    # a cover letter that cannot say "Canonical" or "Graduate Software
    # Engineer" is not a cover letter.
    #
    # DELIBERATELY NARROW, and this is the honest limitation of this file: the
    # rest of the posting's vocabulary stays banned. That means the letter
    # cannot name the company's PRODUCTS either — no "Ubuntu" in a Canonical
    # letter. Widening it to the whole description would let the posting
    # supply technology names, and "I have deep Rust experience" would then
    # validate cleanly because the posting said Rust. Losing a product name is
    # a small cost; a resume that passes validation while lying is not.
    _, post_names = vocab(" ".join(str(x or "") for x in posting))
    prose_names = all_names | post_names

    bullets = packet.get("bullets") or []
    if not isinstance(bullets, list) or not bullets:
        return ["no bullets returned"]
    if len(bullets) < 4:
        bad.append(f"only {len(bullets)} bullets — asked for 6 to 10")

    seen = set()
    for i, b in enumerate(bullets, 1):
        if not isinstance(b, dict):
            bad.append(f"bullet {i} is not an object")
            continue
        bid = str(b.get("id") or "").strip()
        text = " ".join(str(b.get("text") or "").split())
        if bid not in bank:
            # The headline failure this whole file exists to prevent: a bullet
            # that traces to nothing.
            bad.append(f"bullet {i}: id {bid!r} is not in the bullet bank")
            continue
        if bid in seen:
            bad.append(f"bullet {i}: id {bid!r} used twice")
        seen.add(bid)
        if not text:
            bad.append(f"bullet {i} ({bid}): empty text")
            continue
        # TIGHT allowlist — this bullet's own source entry and its project
        # context, and nothing else in the profile.
        src = bank[bid]
        s_nums, s_names = vocab(src["text"] + " " + src["context"])
        bad += check_text(text, s_nums, s_names, f"bullet {i} ({bid})")
        for term in not_yet_hits(text, profile):
            bad.append(f"bullet {i} ({bid}): claims {term!r}, which the profile "
                       f"lists under not_yet")
        # A rewrite that is three times the source is not a rewrite.
        if len(text) > max(240, len(src["text"]) * 2):
            bad.append(f"bullet {i} ({bid}): rewrite is far longer than the source")

    for field in ("headline", "summary", "cover_letter"):
        text = " ".join(str(packet.get(field) or "").split())
        if not text:
            bad.append(f"{field} is empty")
            continue
        bad += check_text(text, all_nums, prose_names, field)
        for term in not_yet_hits(text, profile):
            bad.append(f"{field}: claims {term!r}, which the profile lists "
                       f"under not_yet")
        for rx, why in _BANNED_PHRASES:
            if rx.search(text):
                bad.append(f"{field}: {why}")
        for name in profile.get("_forbidden_names", []):
            if re.search(rf"\b{re.escape(name)}\b", text, re.I):
                bad.append(f"{field}: contains {name!r} — documents use the "
                           f"legal name only")
    return bad


# ---------------------------------------------------------------------------
# Talking to the model
# ---------------------------------------------------------------------------

def clean(s):
    """Normalise the model's text ONCE, before anything else touches it.

    The alternative — fixing typography separately in the renderer and in the
    verifier — is how you get a bullet that is printed on the page and reported
    as missing from it. Backticks are dropped rather than quoted: the bullet
    bank uses them as code markers, LaTeX reads a bare backtick as an OPENING
    quote, and the result was a mismatched pair (’tensor_buft_overrides’) on an
    otherwise clean resume. Normalise the input, not the two outputs."""
    s = str(s or "")
    for a, b in (("`", ""), ("\u2019", "'"), ("\u2018", "'"),
                 ("\u201c", '"'), ("\u201d", '"'), ("\u00a0", " ")):
        s = s.replace(a, b)
    return " ".join(s.split())


def coerce_packet(d):
    if not isinstance(d, dict):
        raise ValueError("reply was not an object")
    out = {}
    for k in ("headline", "summary", "cover_letter", "why_these"):
        out[k] = clean(d.get(k))
    raw = d.get("bullets") or []
    if isinstance(raw, dict):            # {"id": "text"} instead of a list
        raw = [{"id": k, "text": v} for k, v in raw.items()]
    bl = []
    for b in raw if isinstance(raw, list) else []:
        if isinstance(b, str):           # a bare id with no rewrite
            bl.append({"id": b.strip(), "text": ""})
        elif isinstance(b, dict):
            bl.append({"id": str(b.get("id") or "").strip(),
                       "text": clean(b.get("text"))})
    out["bullets"] = bl[:10]
    return out


def ask(cmd, prompt, profile, bank, timeout, attempts=3, posting=("", "")):
    """Ask, validate, and on violation tell it exactly what it got wrong.

    Three attempts, not two: unlike scoring, this is a handful of calls per
    night rather than 321, and the failure it is retrying is a substantive one
    the model can actually act on when shown the list."""
    last = None
    for n in range(attempts):
        p = prompt + FORMAT_SUFFIX
        if last:
            p += FIX_HINT.format(why="\n".join(f"  - {x}" for x in last[:12]))
        try:
            r = subprocess.run(cmd + [p], capture_output=True, text=True,
                               timeout=timeout, env=cli_env(), cwd="/tmp")
        except subprocess.TimeoutExpired:
            last = [f"{cmd[0]} exceeded {timeout}s"]
            continue
        if r.returncode != 0:
            last = [f"{cmd[0]} exit {r.returncode}: "
                    f"{(r.stderr or r.stdout or '').strip()[:200]}"]
            continue
        try:
            packet = coerce_packet(extract_json(r.stdout))
        except (ValueError, json.JSONDecodeError) as e:
            last = [f"unparseable reply: {e}"]
            continue
        bad = validate(packet, profile, bank, posting)
        if not bad:
            return packet, n + 1
        last = bad
    raise RuntimeError("packet rejected after "
                       f"{attempts} attempts:\n  " + "\n  ".join(last or []))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        # The bullet bank uses backticks as code markers (`cudaHostRegister`).
        # A bare backtick is LaTeX's OPENING QUOTE, so it silently rendered as
        # ‘ — which looked wrong on the page and, worse, made verify_pdf report
        # the bullet as missing from a page it was printed on. A plain quote is
        # what belongs on a resume anyway.
        "`": "'"}


def tex(s):
    """Escape for LaTeX. Backslash must go first or it re-escapes its own output."""
    s = str(s or "")
    out = []
    for ch in s:
        out.append(_TEX.get(ch, ch))
    return "".join(out)


TEMPLATE = r"""\documentclass[10pt]{article}
\usepackage[margin=0.55in,letterpaper]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\titleformat{\section}{\large\bfseries}{}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{7pt}{3pt}
\begin{document}
\begin{center}
{\LARGE\bfseries %(name)s}\\[2pt]
{\normalsize %(headline)s}\\[3pt]
%(contact)s
\end{center}

\section{Summary}
%(summary)s

\section{Selected Work}
%(sections)s

\section{Skills}
%(skills)s

\section{Education}
%(education)s
\end{document}
"""


def build_tex(packet, profile, bank, job):
    ident = profile["identity"]
    contact = profile.get("contact") or {}
    bits = [contact.get("email"), contact.get("phone"), contact.get("github"),
            contact.get("linkedin"), ident.get("location")]
    contact_line = r" \textbullet{} ".join(tex(b) for b in bits if b)

    # Group the chosen bullets under their project, preserving the model's
    # ordering — the first bullet it picked decides which project leads.
    order, groups = [], {}
    for b in packet["bullets"]:
        proj = bank[b["id"]]["project"]
        if proj not in groups:
            groups[proj] = []
            order.append(proj)
        groups[proj].append(b["text"])

    titles = {v["project"]: v["project"].replace("_", " ").title()
              for v in bank.values()}
    titles.update({"luminos_os": "Luminos OS — custom Linux distribution",
                   "gpu_ml_infrastructure": "GPU / ML infrastructure",
                   "jobhunt_pipeline": "Automated job-search pipeline",
                   "forex_bot": "Algorithmic trading system",
                   "ears": "EARS — full-stack hiring application",
                   "employment": "Employment"})

    secs = []
    for proj in order:
        secs.append(r"\textbf{%s}" % tex(titles.get(proj, proj)))
        secs.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt,"
                    r"parsep=0pt]")
        for t in groups[proj]:
            secs.append(r"\item %s" % tex(t))
        secs.append(r"\end{itemize}")

    sk = profile.get("skills") or {}
    skill_lines = []
    for tier, label in (("strong", "Strong"), ("working", "Working"),
                        ("familiar", "Familiar")):
        vals = sk.get(tier) or []
        if vals:
            skill_lines.append(r"\textbf{%s:} %s\\" %
                               (tex(label), tex(", ".join(map(str, vals)))))

    edu = []
    for e in (profile.get("education") or []):
        edu.append(r"%s, %s \hfill %s\\" % (
            tex(e.get("degree")), tex(e.get("institution")),
            tex(str(e.get("graduated") or ""))))

    return TEMPLATE % {
        "name": tex(ident["application_name"]),
        "headline": tex(packet["headline"]),
        "contact": contact_line,
        "summary": tex(packet["summary"]),
        "sections": "\n".join(secs),
        "skills": "\n".join(skill_lines),
        "education": "\n".join(edu),
    }


def render(tex_src, outdir):
    """pdflatex, then read the PDF back. Rendering is not proof; reading is."""
    if not shutil.which("pdflatex"):
        sys.exit("pdflatex not found — install texlive-latex, or point render() "
                 "at another engine.")
    src = os.path.join(outdir, "resume.tex")
    with open(src, "w") as fh:
        fh.write(tex_src)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                        "-output-directory", outdir, src],
                       capture_output=True, text=True, timeout=120)
    pdf = os.path.join(outdir, "resume.pdf")
    if r.returncode != 0 or not os.path.exists(pdf):
        errs = [l for l in (r.stdout or "").splitlines() if l.startswith("!")]
        raise RuntimeError("pdflatex failed: " + ("; ".join(errs[:3]) or
                                                  (r.stdout or "")[-300:]))
    for junk in ("resume.aux", "resume.log", "resume.out"):
        try:
            os.remove(os.path.join(outdir, junk))
        except OSError:
            pass
    return pdf


# LaTeX is a typesetter: it turns ' into ’ and -- into –. Comparing the text we
# sent against the text that comes back therefore needs both sides flattened to
# ASCII first, or every bullet containing an apostrophe reports as missing from
# a page it is plainly printed on. (It did.)
_TYPO = {"\u2019": "'", "\u2018": "'", "`": "'", "\u201c": '"', "\u201d": '"',
         "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ",
         "\ufb01": "fi", "\ufb02": "fl"}


def _cmp(s):
    for a, b in _TYPO.items():
        s = s.replace(a, b)
    return " ".join(s.split()).lower()


def verify_pdf(pdf, packet, profile):
    """Prove the words are on the page, and that it is one page.

    A LaTeX run can succeed and still silently drop content (an unbalanced group
    swallows the rest of a paragraph). The only honest check is to read the
    artifact back the way an employer's parser will."""
    problems = []
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
        m = re.search(r"^Pages:\s*(\d+)", info.stdout, re.M)
        if m and int(m.group(1)) != 1:
            problems.append(f"resume is {m.group(1)} pages — must be 1")
    if not shutil.which("pdftotext"):
        problems.append("pdftotext missing — could not verify the text landed")
        return problems, ""
    txt = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True).stdout
    flat = _cmp(txt)

    name = profile["identity"]["application_name"]
    if name.lower() not in flat:
        problems.append(f"{name!r} is not in the rendered PDF")
    email = (profile.get("contact") or {}).get("email") or ""
    if email and email.lower() not in flat:
        problems.append("the email address is not in the rendered PDF")
    for n in profile.get("_forbidden_names", []):
        if re.search(rf"\b{re.escape(n.lower())}\b", flat):
            problems.append(f"the rendered PDF contains {n!r}")
    # Every bullet must actually be there. Compare on a distinctive slice
    # rather than the whole string, since pdftotext reflows whitespace.
    for b in packet["bullets"]:
        probe = _cmp(b["text"])[:40]
        if probe and probe not in flat:
            problems.append(f"bullet {b['id']} did not reach the page")
    return problems, txt


# ---------------------------------------------------------------------------
# Driving
# ---------------------------------------------------------------------------

def slug(s, n=40):
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(s or "")).strip("-").lower()
    return (s[:n] or "x").strip("-")


def db_retry(fn, what, wait=300):
    """Run a write, waiting out a concurrent score.py rather than dying on it.

    SQLite's own busy_timeout is not enough here and it is worth being precise
    about why: score.py commits once every ten jobs, and at roughly 17 seconds
    a job that is a held write lock for about three minutes at a time. A 60
    second busy_timeout simply expires inside one of those stretches. What
    works is polling for the instant between a commit and the next UPDATE.

    Both callers matter. The schema change is at startup, but the row update
    happens AFTER a 40-second model call and a PDF render — losing it there
    means the packet exists on disk with nothing in the database pointing at
    it, which is precisely the kind of quiet inconsistency that shows up a week
    later as "why did it tailor this one twice"."""
    deadline = time.time() + wait
    told = False
    while True:
        try:
            r = fn()
            if told:
                print("        ...database free, written")
            return r
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or time.time() > deadline:
                raise
            if not told:
                told = True
                print(f"        waiting for the database to {what} "
                      f"(score.py is mid-run)...")
            time.sleep(0.25)


def ensure_columns(conn, wait=300):
    """Add the two columns Phase 3 needs, working around a running score.py.

    score.py commits once every ten jobs, so during a run it holds a write
    transaction for roughly three minutes at a stretch and releases it for an
    instant. `ALTER TABLE` is a writer and cannot share that, and SQLite's
    busy_timeout did not help — it waited the full timeout and then failed,
    because the lock is not briefly contended, it is almost continuously held.

    So: poll for the gap. Short sleeps, a long ceiling, and a message that says
    what is actually happening instead of a raw "database is locked" traceback
    that makes it look like corruption."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    missing = [c for c in ("tailored_at", "packet_dir") if c not in have]
    if not missing:
        return
    def add():
        for col in missing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
        conn.commit()
    try:
        db_retry(add, "add the Phase 3 columns", wait)
    except sqlite3.OperationalError as e:
        sys.exit(f"\n  cannot add the Phase 3 columns: {e}\n"
                 f"  score.py is probably mid-run and holding the database "
                 f"for longer than {wait}s. Let it finish, then re-run.\n")


def pick_jobs(conn, args):
    if args.job:
        # Prefix match, because --list prints a shortened id and the whole
        # point of printing an id is that it can be pasted back in.
        rows = conn.execute(
            "SELECT id,company,title,location,url,score,description,tailored_at "
            "FROM jobs WHERE id=? OR id LIKE ?",
            (args.job, args.job + "%")).fetchall()
        if not rows:
            sys.exit(f"no job whose id starts with {args.job!r}")
        return rows
    q = ("SELECT id,company,title,location,url,score,description,tailored_at "
         "FROM jobs WHERE status='shortlist' ")
    if not args.force:
        q += "AND (tailored_at IS NULL OR tailored_at='') "
    q += "ORDER BY score DESC, company LIMIT ?"
    return conn.execute(q, (args.top,)).fetchall()


def main():
    ap = argparse.ArgumentParser(
        description="Phase 3 — tailor a resume per posting, from the bullet bank only.")
    ap.add_argument("--job", help="one job id")
    ap.add_argument("--top", type=int, default=3,
                    help="how many shortlisted jobs to do (default 3)")
    ap.add_argument("--list", action="store_true",
                    help="show what is waiting and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="ask and validate, but write nothing")
    ap.add_argument("--force", action="store_true",
                    help="redo jobs already tailored")
    ap.add_argument("--backend", help="override targets.yaml (agy|claude)")
    ap.add_argument("--out", default=OUT_ROOT)
    args = ap.parse_args()

    with open(TARGETS) as fh:
        cfg = yaml.safe_load(fh) or {}
    sc = cfg.get("scoring") or {}
    backend = (args.backend or sc.get("backend") or "agy").strip().lower()
    if backend == "local":
        sys.exit("tailor.py has no local path yet. Phase 3 is a handful of calls "
                 "where writing quality decides the outcome, so it uses a "
                 "subscription CLI: --backend agy or --backend claude.")
    if backend not in CLI_BACKENDS:
        sys.exit(f"unknown backend {backend!r} — one of {sorted(CLI_BACKENDS)}")
    cmd = list(CLI_BACKENDS[backend])

    profile = load_profile()
    bank = flatten_bank(profile)

    # timeout, not the default 5 seconds: score.py holds the DB in short bursts
    # for the length of a whole run, and the 03:30 timer can overlap a hand-run.
    # Without this, `ALTER TABLE` loses the race and the tool dies with
    # "database is locked" — which is what happened the first time it was run.
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    ensure_columns(conn)

    if args.list:
        rows = conn.execute(
            "SELECT id,score,company,title,tailored_at FROM jobs "
            "WHERE status='shortlist' ORDER BY score DESC LIMIT 40").fetchall()
        print(f"\n  {len(rows)} shortlisted, best first "
              f"(* = already tailored)\n")
        for r in rows:
            mark = "*" if r[4] else " "
            print(f"  {mark} {r[1] or 0:3}  {r[0][:12]:12}  {(r[2] or '')[:20]:20} "
                  f"{(r[3] or '')[:46]}")
        print()
        return

    jobs = pick_jobs(conn, args)
    if not jobs:
        print("\n  nothing waiting — every shortlisted job is already tailored.\n"
              "  (./tailor.py --list to see them, --force to redo one)\n")
        return

    print(f"\n  backend {backend} ({cmd[0]}) — tailoring {len(jobs)} job(s) "
          f"from {len(bank)} bank bullets\n")

    ok = fail = 0
    for jid, company, title, location, url, jscore, desc, done in jobs:
        label = f"{(company or '?')[:18]:18} {(title or '?')[:44]}"
        prompt = PROMPT.format(
            company=company or "", title=title or "", location=location or "",
            description=(desc or "")[:int(sc.get("description_chars", 6000))],
            summary=profile.get("summary") or "",
            strong=", ".join((profile.get("skills") or {}).get("strong") or []),
            working=", ".join((profile.get("skills") or {}).get("working") or []),
            familiar=", ".join((profile.get("skills") or {}).get("familiar") or []),
            not_yet=", ".join((profile.get("skills") or {}).get("not_yet") or []),
            angle=(profile.get("positioning") or {}).get("angle") or "",
            bank=render_bank_for_prompt(bank),
        )
        t0 = datetime.datetime.now()
        try:
            packet, tries = ask(cmd, prompt, profile, bank, timeout=420,
                                posting=(company, title))
        except Exception as e:
            fail += 1
            print(f"  FAIL  {label}\n        {e}\n")
            continue
        secs = (datetime.datetime.now() - t0).total_seconds()

        if args.dry_run:
            ok += 1
            print(f"  DRY   {label}  ({secs:.0f}s, {tries} attempt(s))")
            print(f"        headline: {packet['headline']}")
            print(f"        bullets : {', '.join(b['id'] for b in packet['bullets'])}")
            print(f"        why     : {packet['why_these']}\n")
            continue

        outdir = os.path.join(args.out, f"{slug(company,24)}-{slug(title,32)}-{jid[:8]}")
        os.makedirs(outdir, exist_ok=True)
        try:
            pdf = render(build_tex(packet, profile, bank, (company, title)), outdir)
            problems, txt = verify_pdf(pdf, packet, profile)
        except Exception as e:
            fail += 1
            print(f"  FAIL  {label}\n        render: {e}\n")
            continue
        if problems:
            fail += 1
            print(f"  FAIL  {label}\n        the PDF rendered but did not verify:")
            for p in problems[:6]:
                print(f"          - {p}")
            print()
            continue

        with open(os.path.join(outdir, "cover_letter.txt"), "w") as fh:
            fh.write(textwrap.fill(packet["cover_letter"], 88) + "\n")
        with open(os.path.join(outdir, "resume.txt"), "w") as fh:
            fh.write(txt)
        with open(os.path.join(outdir, "packet.json"), "w") as fh:
            json.dump({"job": {"id": jid, "company": company, "title": title,
                               "location": location, "url": url,
                               "score": jscore},
                       "backend": backend, "attempts": tries,
                       "seconds": round(secs, 1),
                       "tailored_at": t0.isoformat(timespec="seconds"),
                       "packet": packet,
                       "sources": {b["id"]: bank[b["id"]]["text"]
                                   for b in packet["bullets"]}},
                      fh, indent=2)
        def mark():
            conn.execute("UPDATE jobs SET tailored_at=?, packet_dir=? WHERE id=?",
                         (t0.isoformat(timespec="seconds"), outdir, jid))
            conn.commit()
        db_retry(mark, "record the packet")
        ok += 1
        print(f"  OK    {label}  ({secs:.0f}s, {tries} attempt(s), "
              f"{len(packet['bullets'])} bullets)")
        print(f"        {outdir}")

    print(f"\n  {ok} tailored, {fail} failed\n")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
