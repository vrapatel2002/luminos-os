#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-08-27]
"""apply.py — Phase 4. Read the real application form, answer what can be
answered honestly, and refuse the rest.

WHY THIS READS AN API AND NOT A BROWSER
---------------------------------------
Both ATSs we can actually reach hand over the whole form as JSON, over a plain
unauthenticated read:

  Greenhouse  GET  boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?questions=true
  Ashby       POST jobs.ashbyhq.com/api/non-user-graphql   (ApiJobPosting)

Both include the field list, the labels, the option lists, and — the part that
matters — which fields are REQUIRED. So the question "can this application be
completed truthfully" is answerable for all 39 roles in 39 HTTP gets, with no
browser, no login and nothing written anywhere. Checking first and submitting
second is not caution for its own sake: a half-filled application cannot be
withdrawn and re-sent, so the only safe moment to discover an unanswerable
question is BEFORE the form is open.

THE ONE RULE
------------
**A field is answered from an explicit mapping or it is not answered.** No
inference, no LLM, no "probably". Same rule as DECISION 83 and for the same
reason, only harder here, because a resume bullet is a claim about the past and
a screening answer is a claim the employer will act on immediately.

If a REQUIRED field has no mapping, the role is BLOCKED and says why. Blocked is
a normal outcome, not an error.

WHAT THAT COSTS, STATED PLAINLY
-------------------------------
Some employers ask required free-text questions ("what kind of products have you
sold to engineers?"). Those have no honest automatic answer and never will. Those
roles need Shawn. `--check` counts them so the size of that pile is a measured
number rather than a guess.

USAGE
    ./apply.py --check              # every shortlisted role: ready or blocked, and why
    ./apply.py --check --limit 5
    ./apply.py --form <id>          # the full form for one role, field by field
    ./apply.py --apply              # open + fill each ready role. SENDS NOTHING.
    ./apply.py --apply --submit     # ...and press Submit. Cannot be undone.

--apply needs the venv interpreter, because playwright lives there:
    /opt/luminos/venv-jobhunt/bin/python apply.py --apply
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track  # noqa: E402  (DB path, colours, dedup-key helpers)

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(HERE, "profile.yaml")

UA = "Mozilla/5.0 (X11; Linux x86_64) jobhunt/1.0"
TIMEOUT = 25

BOLD, DIM, RESET = track.BOLD, track.DIM, track.RESET
GREEN, YELLOW, RED, CYAN = track.GREEN, track.YELLOW, track.RED, track.CYAN


# ---------------------------------------------------------------------------
# A field, in the one shape the rest of the file understands.
#
# `kind` is normalised across the two ATSs so the answering rules are written
# once. An ATS type we have never seen maps to "unknown", which BLOCKS if the
# field is required — a type we cannot fill is not a type we may guess at.
# ---------------------------------------------------------------------------
class Field:
    __slots__ = ("path", "label", "kind", "required", "options", "raw_type")

    def __init__(self, path, label, kind, required, options=None, raw_type=""):
        self.path = path
        self.label = " ".join((label or "").split())
        self.kind = kind
        self.required = bool(required)
        self.options = options or []          # list of str, the visible labels
        self.raw_type = raw_type

    def __repr__(self):
        return f"<Field {self.path} {self.kind} req={self.required}>"


GH_TYPES = {
    "input_text": "text",
    "textarea": "longtext",
    "input_file": "file",
    "multi_value_single_select": "select",
    "multi_value_multi_select": "multiselect",
    "input_hidden": "hidden",
}

ASHBY_TYPES = {
    "String": "text",
    "Email": "email",
    "Phone": "phone",
    "Number": "number",
    "LongText": "longtext",
    "File": "file",
    "Boolean": "boolean",
    "Date": "date",
    "ValueSelect": "select",
    "MultiValueSelect": "multiselect",
    "SocialLink": "text",
    "Score": "number",
    "Location": "text",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _post(url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------
GH_URL = re.compile(
    r"https?://(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/([^/]+)/jobs/(\d+)")


def greenhouse_form(url):
    m = GH_URL.search(url)
    if not m:
        raise ValueError(f"not a greenhouse job url: {url}")
    board, jid = m.group(1), m.group(2)
    api = (f"https://boards-api.greenhouse.io/v1/boards/{board}"
           f"/jobs/{jid}?questions=true")
    d = _get(api)

    fields = []
    for q in d.get("questions", []):
        label = q.get("label") or ""
        req = q.get("required")
        # A Greenhouse "question" can carry several input fields — resume is
        # {input_file, textarea}, meaning "upload OR paste". They are
        # alternatives, so requiredness belongs to the question, not to each
        # field, and filling either one satisfies it.
        alts = q.get("fields", [])
        for f in alts:
            fields.append(Field(
                path=f.get("name", ""),
                label=label,
                kind=GH_TYPES.get(f.get("type", ""), "unknown"),
                # only the FIRST alternative carries the requirement, or a
                # resume upload would look like it also needs pasted text
                required=req and f is alts[0],
                options=[v.get("label") for v in (f.get("values") or [])],
                raw_type=f.get("type", ""),
            ))
    return fields, d.get("title") or "", d.get("company_name") or ""


# ---------------------------------------------------------------------------
# Ashby
#
# GraphQL, introspection disabled — but its validation errors name the types, so
# the query below was derived from the server rather than guessed. `field` comes
# back as raw JSON, which is why the option list is dug out by hand.
# ---------------------------------------------------------------------------
ASHBY_URL = re.compile(r"https?://jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})")

ASHBY_QUERY = """
query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) {
  jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName,
             jobPostingId: $jobPostingId) {
    id title
    applicationForm { sections { title fieldEntries { isRequired field } } }
  }
}"""


def ashby_form(url):
    m = ASHBY_URL.search(url)
    if not m:
        raise ValueError(f"not an ashby job url: {url}")
    org, pid = m.group(1), m.group(2)
    d = _post("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting", {
        "operationName": "ApiJobPosting",
        "variables": {"organizationHostedJobsPageName": org, "jobPostingId": pid},
        "query": ASHBY_QUERY,
    })
    if d.get("errors"):
        raise RuntimeError(d["errors"][0].get("message", "graphql error"))
    post = (d.get("data") or {}).get("jobPosting")
    if not post:
        raise RuntimeError("posting not found (withdrawn or renamed?)")

    fields = []
    for sec in post["applicationForm"]["sections"]:
        for e in sec.get("fieldEntries", []):
            f = e.get("field") or {}
            vals = f.get("selectableValues") or []
            fields.append(Field(
                path=f.get("path", ""),
                label=f.get("title") or "",
                kind=ASHBY_TYPES.get(f.get("type", ""), "unknown"),
                required=e.get("isRequired"),
                options=[v.get("label") for v in vals if isinstance(v, dict)],
                raw_type=f.get("type", ""),
            ))
    return fields, post.get("title") or "", org


ADAPTERS = (("greenhouse", GH_URL, greenhouse_form),
            ("ashby", ASHBY_URL, ashby_form))


# [CHANGE: claude-code | 2026-08-27] Forms are cached on disk for a day.
# `--check` is 64 requests to two companies' APIs, and it is the command that
# gets run repeatedly while the answering rules are being written. Re-fetching
# an unchanged form to re-run a regex is rude to them and slow for us. A day is
# short enough that a withdrawn posting is noticed quickly; `--fresh` skips it.
CACHE_DIR = os.path.expanduser("~/.cache/luminos/jobhunt-forms")
CACHE_TTL = 24 * 3600


def _cache_path(url):
    return os.path.join(CACHE_DIR, re.sub(r"[^a-zA-Z0-9]", "_", url)[-120:] + ".json")


def fetch_form(url, fresh=False):
    """(fields, title, company, ats) for a URL we have an adapter for."""
    import time
    cp = _cache_path(url)
    if not fresh and os.path.exists(cp) and time.time() - os.path.getmtime(cp) < CACHE_TTL:
        with open(cp) as fh:
            d = json.load(fh)
        # A cached ERROR is cached too — a 404 is a fact about the posting, and
        # re-asking sixty times per run for a job that no longer exists is the
        # same waste as re-fetching a live one.
        if d.get("error"):
            raise RuntimeError(d["error"])
        return ([Field(**f) for f in d["fields"]], d["title"], d["company"],
                d["ats"])

    for name, pat, fn in ADAPTERS:
        if pat.search(url or ""):
            os.makedirs(CACHE_DIR, exist_ok=True)
            try:
                fields, title, company = fn(url)
            except Exception as e:                        # noqa: BLE001
                with open(cp, "w") as fh:
                    json.dump({"error": f"{type(e).__name__}: {e}"}, fh)
                raise
            with open(cp, "w") as fh:
                json.dump({"title": title, "company": company, "ats": name,
                           "fields": [{s: getattr(f, s) for s in Field.__slots__}
                                      for f in fields]}, fh)
            return fields, title, company, name
    raise ValueError("no adapter for this url")


# ---------------------------------------------------------------------------
# Answering.
#
# Every rule is a function that returns (value, why) or (None, why-not). The
# `why` is kept and printed, because "it filled the form" is not something
# anyone should have to take on trust.
# ---------------------------------------------------------------------------
def load_profile():
    with open(PROFILE_PATH) as fh:
        return yaml.safe_load(fh)


NO = (None, "")          # not applicable — let a later rule try


def pick_option(options, *wanted):
    """Exactly one option matching one of `wanted`, or None.

    Ambiguity is a refusal, not a coin flip. Two options that both match means
    the question is asking something more specific than we understood, and
    picking either one would be inventing an answer.
    """
    if not options:
        return None
    for w in wanted:
        w = w.strip().lower()
        exact = [o for o in options if (o or "").strip().lower() == w]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return None
    for w in wanted:
        w = w.strip().lower()
        part = [o for o in options if w in (o or "").lower()]
        if len(part) == 1:
            return part[0]
    return None


def _country(label):
    """Which country's work-authorisation is this question about?

    This is not pedantry. Affirm asks 'Do you require immigration sponsorship to
    work for Affirm IN THE UNITED STATES?' — and the profile's sponsorship field
    is about CANADA. Answering a US question with a Canadian fact is a false
    statement on a legal screening question, and it is the single easiest way
    for an automated applicant to do real damage. When the country is not named,
    the answer is his own working country, because 'your desired location' is
    Ontario.
    """
    lab = label.lower()
    if re.search(r"\bunited states\b|\bu\.?s\.?a?\b|\bamerica\b", lab):
        return "us"
    if re.search(r"\bcanada\b|\bcanadian\b", lab):
        return "ca"
    if re.search(r"\buk\b|united kingdom|\beu\b|europe|\bindia\b|australia", lab):
        return "other"
    return "ca"


def answer_for(f, p, band=None):
    """(value, why) or (None, reason it cannot be answered)."""
    ident = p.get("identity", {})
    con = p.get("contact", {})
    ans = p.get("application_answers", {})
    lab = f.label.lower()
    path = (f.path or "").lower()
    full = ident.get("application_name") or ident.get("legal_name") or ""
    first, _, last = full.partition(" ")

    # ---- system fields, matched on path so a renamed label cannot break them
    if path in ("_systemfield_name",):
        return full, "application_name"
    if path == "first_name" or re.fullmatch(r"first\s*name", lab):
        return first, "application_name"
    if path == "last_name" or re.fullmatch(r"last\s*name", lab):
        return last, "application_name"
    if f.kind == "email" or path in ("email", "_systemfield_email") \
            or re.fullmatch(r"e-?mail(\s*address)?", lab):
        return con.get("email"), "contact.email"
    if f.kind == "phone" or path in ("phone", "_systemfield_phone") \
            or re.search(r"\bphone\b|mobile number", lab):
        v = con.get("phone")
        return (v, "contact.phone") if v else (
            None, "contact.phone is empty in profile.yaml")
    # [CHANGE: claude-code | 2026-08-27] Cover letter FIRST. Greenhouse gives the
    # cover letter its own input_file, and the generic `kind == "file"` test used
    # to swallow it — so the form was filled with the resume uploaded twice, once
    # under a label saying it was a cover letter. It filled every field and it
    # was wrong, which is the failure mode that does not announce itself.
    if re.search(r"cover letter", lab):
        # tailor.py writes cover_letter.txt, not a PDF, so there is nothing to
        # upload. Greenhouse offers a textarea alongside the upload and either
        # satisfies the question, so say so rather than name a file that does
        # not exist and discover it at submit time.
        if f.kind == "file":
            return None, "the packet has cover_letter.txt, not a PDF to upload"
        return "<cover_letter>", "the tailored packet"
    if f.kind == "file" or path in ("resume", "_systemfield_resume"):
        return "<resume.pdf>", "the tailored packet"

    # ---- links
    if re.search(r"linkedin", lab):
        v = con.get("linkedin")
        return (v, "contact.linkedin") if v else (
            None, "contact.linkedin is empty in profile.yaml")
    if re.search(r"github", lab):
        return con.get("github"), "contact.github"
    if re.search(r"portfolio|personal (web)?site|\bwebsite\b", lab):
        v = con.get("website")
        return (v, "contact.website") if v else (None, "no website in profile")

    # ---- names he is called
    if re.search(r"preferred (first )?name|what should we call you|nickname", lab):
        return ident.get("known_as") or first, "identity.known_as"
    if re.search(r"name pronunciation|pronounce", lab):
        return None, "not in profile (optional almost everywhere)"

    # ---- legal agreements and attestations.
    # [CHANGE: claude-code | 2026-08-27] These are NEVER auto-answered, and that
    # is a rule rather than a missing feature. Canonical, GitLab, 1Password and
    # Tailscale all put a binding agreement in the middle of the form —
    # arbitration agreements, background-check consent, "I certify that the
    # information in this application is true". Ticking one of those on Shawn's
    # behalf is agreeing to a contract for him, and an arbitration clause signs
    # away the right to sue. He has to read those himself. Deliberately checked
    # BEFORE the yes/no rules below, or a plain "Yes/No" agreement would fall
    # through to something that answers it.
    if re.search(r"\barbitrat|i certify|i agree|do you agree|please confirm that "
                 r"you have (read|reviewed)|read and (agree|understand|accept)"
                 r"|terms (and conditions|of use)|privacy (notice|policy)"
                 r"|background check|consent to|acknowledge/confirm"
                 r"|i understand that", lab):
        return None, "a legal agreement — only Shawn can accept this"

    # ---- nationality.
    # Still never DERIVED — being authorised to work somewhere says nothing about
    # citizenship, and a permanent resident is authorised and is not a citizen.
    # [CHANGE: claude-code | 2026-08-27] But it is now STATED: Shawn gave it
    # directly on 2026-08-27, so the 31 refusals across Canonical and Supabase
    # have a real answer. A PASSPORT question stays refused — it asks for a
    # document number, which is a different thing from a nationality and is not
    # something this file should ever hold.
    # [CHANGE: claude-code | 2026-08-27] "Passport" splits two ways and the first
    # version of this rule refused both, costing 8 roles for nothing. Ashby asks
    # "Passport Country", which is a nationality question wearing a different hat
    # and is answerable. A passport NUMBER or expiry or a scan of the document is
    # a government identifier, and that does not belong in this file at all —
    # those stay refused permanently, not pending a CONFIRM.
    if re.search(r"passport", lab):
        if re.search(r"countr|nationalit|issu(ing|ed)|which country", lab):
            v = ident.get("citizenship")
            if not v:
                return None, "identity.citizenship is empty in profile.yaml"
            opt = pick_option(f.options, v) if f.options else v
            return (opt, "identity.citizenship") if opt else (
                None, f"no '{v}' option on this question")
        return None, ("asks for passport document details — a government "
                      "identifier, deliberately never stored here")
    if re.search(r"nationalit|citizenship|what is your citizen"
                 r"|country of citizen|citizen of which", lab):
        v = ident.get("citizenship")
        if not v:
            return None, ("nationality is not in profile.yaml and cannot be "
                          "inferred from work authorisation")
        opt = pick_option(f.options, v) if f.options else v
        return (opt, "identity.citizenship") if opt else (
            None, f"no '{v}' option on this question")

    # ---- self-identification.
    # He set gender / race / veteran / disability to "Decline to self-identify".
    # Pronouns is the same kind of question, so declining is his stated answer
    # rather than an assumption — but only if the form offers a decline option.
    if re.search(r"pronoun|gender|race|ethnicit|veteran|disabilit"
                 r"|hispanic|latino", lab):
        opt = pick_option(f.options, "I prefer not to say", "prefer not to say",
                          "Decline to self-identify", "I don't wish to answer",
                          "decline", "prefer not to disclose")
        return (opt, "declines to self-identify (profile)") if opt else (
            None, "no decline-to-answer option offered")

    # ---- work authorisation and sponsorship, split by country
    if re.search(r"sponsor", lab):
        c = _country(f.label)
        if c == "us":
            # [CHANGE: claude-code | 2026-08-27] Explicit field first. The open
            # permit is CANADIAN and buys nothing in the US, so this is Yes —
            # but state it from a field rather than deriving it from a different
            # question's answer.
            need = ans.get("requires_sponsorship_us")
            if need is None:
                need = not ans.get("authorized_to_work_in_us")
            v = "Yes" if need else "No"
            why = "requires_sponsorship_us (the permit is Canadian)"
        elif c == "other":
            return None, "asks about a country the profile says nothing about"
        else:
            v = ans.get("requires_sponsorship_canada")
            if v is None:
                return None, ("requires_sponsorship_canada is unset — it has no "
                              "default on purpose; being work-authorised now "
                              "does not answer whether sponsorship is needed later")
            # [CHANGE: claude-code | 2026-08-27] Answered No, on Shawn's own
            # words: an OPEN work permit means no employer sponsors anything to
            # hire him. Flagged separately when the question says "now or in the
            # FUTURE", because that wording is asking a different thing — the
            # permit has an expiry — and if he ever wants those 15 roles
            # answered the other way, this reason string is where to find them.
            why = ("requires_sponsorship_canada (note: asks about the future too)"
                   if re.search(r"future|continu|ongoing|any (time|point)", lab)
                   else "requires_sponsorship_canada (open work permit)")
            v = "Yes" if v else "No"
        opt = pick_option(f.options, v) if f.options else v
        return (opt, why) if opt else (None, f"no '{v}' option on this question")

    if re.search(r"authoriz|authoris|legally (able|entitled|eligible) to work"
                 r"|right to work|eligible to work", lab):
        c = _country(f.label)
        if c == "other":
            return None, "asks about a country the profile says nothing about"
        ok = ans.get("authorized_to_work_in_us") if c == "us" \
            else ans.get("authorized_to_work_in_canada")
        if ok is None:
            return None, "work authorisation for that country is unset"
        v = "Yes" if ok else "No"
        opt = pick_option(f.options, v) if f.options else v
        return (opt, f"authorized_to_work_in_{c}") if opt else (
            None, f"no '{v}' option on this question")

    # ---- where he is
    if re.search(r"state or (canadian )?province|which (state|province)"
                 r"|state/province|province of residence", lab):
        opt = pick_option(f.options, "Ontario") if f.options else "Ontario"
        return (opt, "identity.location") if opt else (
            None, "Ontario is not in the option list")
    if re.search(r"\bcountry\b", lab):
        # [CHANGE: claude-code | 2026-08-27] Canonical's country list has 314
        # entries and splits Canada by province — "Canada - Alberta",
        # "Canada - Ontario", and eleven more. Asking for "Canada" matched
        # thirteen options, so pick_option correctly refused rather than
        # guessing Alberta. Ask for the province first.
        opt = (pick_option(f.options, "Canada - Ontario", "Canada")
               if f.options else "Canada")
        return (opt, "identity.location") if opt else (
            None, "no unambiguous Canada option in the list")
    if re.search(r"time ?zone", lab):
        # [CHANGE: claude-code | 2026-08-27] Nobody offers "America/Toronto".
        # The three real shapes in these forms are "UTC-5: Eastern Time (US),
        # Colombia...", a bare "Eastern Time", and a continent-sized bucket
        # called "American Time Zones". Ontario is Eastern, so all three are
        # answerable — the profile value just is not what a dropdown says.
        tz = ident.get("timezone")
        if not f.options:
            return tz, "identity.timezone"
        opt = pick_option(f.options, "Eastern Time", "UTC-5",
                          "American Time Zones", "Eastern")
        return (opt, "Ontario is Eastern (identity.timezone)") if opt else (
            None, "no Eastern/Americas option in the list")

    # ---- "are you located in X?", and the ones that bundle relocation into it
    m_loc = re.search(r"(?:currently )?(?:located|based|reside|living|live) in"
                      r"(?: \(?or willing to relocate to\)?)?\s*\(?([^?]{2,90})",
                      lab)
    if m_loc and f.options:
        place = m_loc.group(1).lower()
        mine = (ident.get("location") or "").lower()
        here = any(tok in place for tok in
                   [t.strip() for t in mine.split(",") if len(t.strip()) > 3])
        if here:
            opt = pick_option(f.options, "Yes")
            return (opt, "identity.location") if opt else (
                None, "no 'Yes' option on this question")
        if "relocat" in lab and ans.get("willing_to_relocate"):
            return None, "willing to relocate — this needs a real answer"
        opt = pick_option(f.options, "No, and I am not willing", "No")
        return ((opt, f"not in {m_loc.group(1)[:22].strip()} "
                      f"(identity.location)") if opt else
                (None, "no 'No' option on this question"))

    # ---- "have you worked here before?"
    # profile.yaml is the whole of his history — the same assumption tailor.py
    # makes when it refuses to write a bullet that is not in the bank. If the
    # employer is nowhere in it, he did not work there.
    if re.search(r"(previously|ever) (been employed|worked)|worked at or "
                 r"consulted for|former(ly)? (an )?employee", lab):
        past = " ".join(
            [" ".join(str(e.get("institution", "")) for e in p.get("education") or [])]
            + [" ".join(str(b) for b in (v.get("bullets") or []))
               for v in (p.get("bullet_bank") or {}).values()]).lower()
        co_m = re.search(r"(?:employed at|worked at|consulted for|worked for)\s+"
                         r"([A-Za-z0-9&.\- ]{2,30})", f.label)
        who = (co_m.group(1).strip() if co_m else "").lower()
        if who and who in past:
            return None, f"profile mentions {who} — needs a real answer"
        opt = (pick_option(f.options, "I have not previously been employed",
                           "have not", "No") if f.options else "No")
        return (opt, "no such employer anywhere in profile.yaml") if opt else (
            None, "no clear 'never worked here' option")

    # [CHANGE: claude-code | 2026-08-27] Both of these were blocking real roles
    # and both are now stated facts rather than inferences — see profile.yaml.
    if re.search(r"over the age of 18|at least 18|18 years", lab):
        v = ans.get("over_18")
        if v is None:
            return None, "age is not in profile.yaml (add `over_18: true`)"
        v = "Yes" if v else "No"
        opt = pick_option(f.options, v) if f.options else v
        return (opt, "application_answers.over_18") if opt else (
            None, f"no '{v}' option on this question")
    if re.search(r"meet in person|travel .{0,20}(times?|days?) (a|per) year"
                 r"|willing to travel|in-person (event|meet)", lab):
        v = ans.get("willing_to_travel_occasionally")
        if v is None:
            return None, ("willingness to travel is not in profile.yaml "
                          "(add `willing_to_travel_occasionally`)")
        v = "Yes" if v else "No"
        opt = pick_option(f.options, v) if f.options else v
        return (opt, "willing_to_travel_occasionally") if opt else (
            None, f"no '{v}' option on this question")

    # [CHANGE: claude-code | 2026-08-27] Address, from the transcript. Matched
    # part by part: Greenhouse asks for one blob, Ashby asks for four fields, and
    # answering "395 Lake Street" into a box labelled "Postal code" would pass
    # validation on some forms and be wrong on all of them.
    addr = con.get("address") or {}
    if addr:
        if re.search(r"postal( |/)?code|zip ?code", lab):
            return addr.get("postal_code"), "contact.address.postal_code"
        if re.search(r"address line ?2|apt|suite|unit", lab):
            return "", "no second address line"
        if re.search(r"address line ?1|street address|^address$|mailing address",
                     lab):
            return addr.get("street"), "contact.address.street"
        if re.fullmatch(r"city|town|city/town", lab):
            return addr.get("city"), "contact.address.city"
    if re.search(r"address line|street address|postal( |/)?(code)?|zip ?code"
                 r"|^city$", lab):
        return None, "no street address in profile.yaml"
    if re.search(r"where are you (located|based)|current (city|location)"
                 r"|city of residence|location\?*$", lab):
        return ans.get("current_location"), "application_answers.current_location"
    if re.search(r"relocat", lab):
        v = "Yes" if ans.get("willing_to_relocate") else "No"
        opt = pick_option(f.options, v) if f.options else v
        return (opt, "willing_to_relocate") if opt else (
            None, f"no '{v}' option on this question")

    # ---- money and dates
    if re.search(r"salary|compensation expectation|expected (pay|rate)"
                 r"|desired (salary|compensation)", lab):
        floor = ans.get("salary_expectation_cad")
        if not floor:
            return None, "salary_expectation_cad is empty in profile.yaml"
        # [CHANGE: claude-code | 2026-08-27] Shawn is flexible and asked the
        # tool to decide. Where the employer published a band, this READS it —
        # a fact on the page, not a judgement — and answers inside it. Quoting
        # the floor at an employer who already said 133k would cost him real
        # money, so the floor only applies when nothing was published.
        if band:
            lo, hi = band
            ask = max(int(floor), lo)
            if f.kind in ("number",) or re.search(r"^\s*\d+\s*$", str(
                    f.raw_type or "")):
                return str(ask), f"inside the posted band {lo:,}-{hi:,}"
            if f.kind == "select" and f.options:
                return None, "salary asked as a picklist; bands do not map"
            return (f"{ask:,} CAD, flexible" if ans.get("salary_is_flexible")
                    else f"{ask:,} CAD"), f"posted band {lo:,}-{hi:,}"
        if f.kind == "number":
            return str(int(floor)), "salary_expectation_cad (nothing published)"
        return ((f"{int(floor):,} CAD, flexible"
                 if ans.get("salary_is_flexible") else f"{int(floor):,} CAD"),
                "salary_expectation_cad (nothing published)")
    if re.search(r"start date|available to start|when can you start"
                 r"|notice period", lab):
        v = ans.get("earliest_start_date") or ans.get("notice_period")
        return (str(v), "earliest_start_date / notice_period") if v else (
            None, "no start date in profile.yaml")

    # ---- background
    if re.search(r"years of (professional )?experience|how many years", lab):
        v = ans.get("years_professional_experience")
        return (str(v), "years_professional_experience") if v is not None else (
            None, "years_professional_experience is unset")
    # [CHANGE: claude-code | 2026-08-27] This rule used to match a bare "degree"
    # and it was WRONG TWICE on one Canonical form. It typed "Bachelor's Degree"
    # into *"What was your bachelor's university degree RESULT?"* — which asks
    # for a grade, so the form would have gone out carrying an answer that is
    # not an answer — and it fired again on *"...since you graduated your first
    # undergraduate degree, how many companies have you worked for?"*, where the
    # options were 0-10.
    #
    # Neither was a missing mapping. Both were this tool inventing an answer
    # because a keyword happened to appear, which is the exact failure the whole
    # file exists to prevent. The lesson is not "add two exceptions": a rule
    # that can fire on a question it has not understood has to be narrow, and
    # anything asking for a RESULT, a COUNT or a GRADE is a different question.
    if re.search(r"highest (level of )?education|education level"
                 r"|highest (degree|qualification)", lab) and not re.search(
                     r"result|grade|gpa|how many|classification|score", lab):
        v = ans.get("highest_education")
        opt = pick_option(f.options, v, "Bachelor") if f.options else v
        return (opt, "highest_education") if opt else (
            None, "no matching education option")

    # [CHANGE: claude-code | 2026-08-27] The RESULT question, which the rule above
    # deliberately refuses. Answerable now that the transcript is in the file.
    # Reported as a percentage plus the scale it came from, never converted into
    # a British honours class — Canonical is a UK company and its wording invites
    # "2:1"/"2:2", but a Canadian percentage does not map onto that cleanly, and
    # this is the one field an employer can check against an official document.
    if re.search(r"degree (result|classification|grade)"
                 r"|(result|classification|grade).{0,20}(of|for) your .{0,20}degree"
                 r"|what (was|is) your .{0,30}degree result"
                 r"|\bgpa\b|grade point average", lab):
        v = ans.get("degree_result")
        if not v:
            return None, "degree_result is empty in profile.yaml"
        if f.options:
            opt = pick_option(f.options, v)
            return (opt, "degree_result") if opt else (
                None, "degree result is a percentage; the options are a "
                      "different grading system")
        return v, "degree_result (from the transcript)"

    # ---- school grades. Canonical asks about MATHS and NATIVE LANGUAGE at
    # secondary school on 23 shortlisted roles. Nothing about school is in the
    # university transcript, so these stay refused until he fills them in — but
    # they are named separately from a generic "no rule" so the count is honest
    # about what it is waiting for.
    sch = p.get("secondary_school") or {}
    if re.search(r"(high ?school|secondary school|at school).{0,40}"
                 r"(math|maths|mathematics)"
                 r"|(math|maths|mathematics).{0,30}(at|in) (high ?school|school)",
                 lab):
        v = sch.get("maths_result")
        return (v, "secondary_school.maths_result") if v else (
            None, "school maths result is not in profile.yaml (CONFIRM)")
    if re.search(r"native language.{0,40}(high ?school|school)"
                 r"|(high ?school|school).{0,40}native language", lab):
        v = sch.get("native_language_result")
        return (v, "secondary_school.native_language_result") if v else (
            None, "school language result is not in profile.yaml (CONFIRM)")
    # [CHANGE: claude-code | 2026-08-27] A bare `|source` used to be the last
    # alternative here, and it matched "Have you made any OPEN SOURCE
    # contributions you'd like to tell us about?" — so Supabase's essay box got
    # filled with the words "Job board". It filled the field, printed a green +,
    # and was nonsense. Exactly the failure that does not announce itself.
    # The phrase now has to actually be about where he heard of the job.
    if re.search(r"how did you (first )?(hear|learn)"
                 r"|where did you (hear|find|see)"
                 r"|referral source|how you heard"
                 r"|(hear|heard|find|found) (about|out about) (this|the|our)"
                 r"\s*(role|job|position|vacancy|opening|opportunity)", lab):
        src = ans.get("referral_source") or ""
        if not f.options:
            return src, "referral_source"
        opt = pick_option(f.options, src, "Job Board", "Job boards")
        if opt:
            return opt, "referral_source"
        # Falling back to "Other" is not a dodge — he did find it on a job board,
        # and when the list has no job-board entry, Other is the true bucket.
        opt = pick_option(f.options, "Other")
        return (opt, "found on a job board; no job-board option, so Other") \
            if opt else (None, "no option matches 'Job board'")
    if re.search(r"referred by|employee referral|who referred", lab):
        return None, "not a referral"
    if re.search(r"current (company|employer)", lab):
        return None, "not in profile as a single field"

    return None, "no rule for this question"


# [CHANGE: claude-code | 2026-08-27] Blocked is not one thing, and treating it
# as one thing hides the only distinction that matters here:
#
#   gap   — the answer exists, Shawn just has not written it down yet. Five
#           lines of profile.yaml turn every one of these into a ready form.
#   essay — the employer asked an open question about his experience. There is
#           no honest automatic answer and there never will be, so counting
#           these as "not built yet" would be a lie about what is left to do.
#   consent — a legal agreement, or a protected attribute. Not a gap and not
#           work: a decision that is Shawn's to make and nobody else's.
#   rule  — a structured question this file simply has no mapping for. Real
#           work, and finishable.
#
# The four need completely different responses, so they get counted apart.
GAP_MARKERS = ("empty in profile.yaml", "is unset", "no start date",
               "unset on purpose", "no street address", "not in profile.yaml (add")
CONSENT_MARKERS = ("only Shawn can accept", "cannot be inferred")


# ---------------------------------------------------------------------------
# [CHANGE: claude-code | 2026-08-27] The rail that matters more than any other
# in this file.
#
# Canonical puts this in the middle of its application form, as a REQUIRED
# checkbox, on roughly a quarter of the shortlist:
#
#   "During this application process I agree to use only my own words. I
#    understand that plagiarism, the use of AI or other generated content will
#    disqualify my application."
#
# So on those forms, an automated answer is not merely a bad idea — ticking that
# box and then letting a tool write the prose is a false declaration, and the
# stated penalty is disqualification. Getting caught would not cost one
# application, it would burn the employer.
#
# This is checked at the FORM level, not the field level, because the clause
# poisons every other free-text box on the same page. A form that says this gets
# no generated content at all: apply.py will still read it and still fill the
# pure-fact fields (name, email, address — those are his own words in any
# meaningful sense), but it must never write an essay answer here and must never
# auto-submit. Shawn writes these himself or he does not apply.
#
# Broad on PROHIBITION wording, but it must actually be a prohibition. The first
# version of this regex matched a bare "use of AI" and flagged Tailscale, whose
# checkbox reads "I have read and understand Tailscale's Candidate Privacy Policy
# and AI Guidelines regarding ... use of AI tools in the hiring process". That is
# an acknowledgement pointing at a policy document, not a ban, and reporting it
# as "forbids AI-written answers outright" would have been a false statement in
# my own summary — the same category of error this file exists to avoid. It is
# still blocked, correctly, as a [consent] legal agreement.
#
# So: the label has to carry a prohibition, not merely mention AI.
AI_FORBIDDEN = re.compile(
    r"use only my own words|in my own words only|\bplagiaris"
    r"|(ai|artificial intelligence|chatgpt|llm|generated content|generative)"
    r"[^.]{0,80}(disqualif|prohibit|not permitted|not allowed|forbidden"
    r"|will not be considered|grounds for rejection|automatic rejection)"
    r"|(do not|don't|must not|may not) use[^.]{0,40}"
    r"(ai|chatgpt|llm|generative)", re.I)


def form_forbids_ai(fields):
    """Does this form declare that AI-generated answers are disqualifying?

    Form-level, not field-level: the clause poisons every free-text box on the
    same page, so one match condemns the whole application to being written by
    hand.
    """
    return any(AI_FORBIDDEN.search(f.label or "") for f in fields)


def blocker_kind(field, why):
    if any(m in why for m in CONSENT_MARKERS):
        return "consent"
    if any(m in why for m in GAP_MARKERS):
        return "gap"
    if why == "no rule for this question":
        # An open question, not a field with a missing mapping. Long-text always
        # counts; so does a short-text question phrased as a question, because
        # Canonical asks "What is the first thing you look at when a Linux
        # system is slow?" in a plain String field.
        if field.kind in ("longtext",) or (
                field.kind == "text" and not field.options
                and (field.label.endswith("?") or len(field.label) > 60)):
            return "essay"
        return "rule"
    return "rule"


# [CHANGE: claude-code | 2026-08-27] Deliberately a regex over the posting, not
# a model call. "What number is written here" is the cheapest possible question
# and an LLM adds only the risk of inventing one. Measured: 23 of 113
# shortlisted postings publish a band, so this fires about 20% of the time and
# the profile floor covers the rest.
# \s* not \s? around the separator: stripping HTML turns "<b>$140,000</b> -
# <b>$170,000</b>" into a run of several spaces, and a single optional space
# silently matched nothing. Found by testing it, not by reading it.
_BAND = re.compile(r"\$?\s*(\d{2,3}),?(\d{3})\s*(?:-|to|–|—)\s*"
                   r"\$?\s*(\d{2,3}),?(\d{3})")


# A number range is not a salary. "serving 50,000 - 90,000 requests per second"
# matches the shape perfectly, and quoting 50,000 as his expectation would cost
# him real money. So the range only counts as pay when pay is named right next
# to it. Same lesson as every other rule in this file: a rule that can fire on
# something it has not understood must be narrow.
_MONEY_CTX = re.compile(
    r"(salary|compensation|base pay|pay range|pay band|remuneration|\bCAD\b"
    r"|\bUSD\b|per year|annually|annual|\$)", re.I)


def posting_band(description):
    """(low, high) the employer published, or None. Never a guess."""
    if not description:
        return None
    text = re.sub(r"<[^>]+>", " ", description)
    for m in _BAND.finditer(text):
        lo = int(m.group(1) + m.group(2))
        hi = int(m.group(3) + m.group(4))
        # A plausible annual salary in CAD/USD. This window rejects the two
        # things that otherwise match: phone numbers and "2020-2024" style
        # date ranges, both of which appear in almost every posting.
        if not (40_000 <= lo <= 400_000 and lo < hi <= 600_000):
            continue
        # ...and the words around it have to be about money.
        near = text[max(0, m.start() - 90):m.end() + 40]
        if _MONEY_CTX.search(near):
            return lo, hi
    return None


# [CHANGE: claude-code | 2026-08-27] The rules above are FACT lookups: a name, a
# phone number, a yes/no about work authorisation. A long-text box is not a fact
# lookup, it is a question the employer wants prose for — and the one thing this
# file exists to guarantee is that prose is never invented.
#
# So an essay box may be filled by exactly one thing: the cover letter tailor.py
# wrote and validated against the bullet bank. Every other rule is refused there,
# whether it matched or not.
#
# This is a rail and not a fix. The `|source` bug it was written alongside is
# already fixed one function up; this is here so the NEXT over-broad regex writes
# nothing instead of writing two words into an essay. Allowlist, not blocklist —
# same choice as tailor.py's validator, for the same reason: a blocklist only
# stops the mistakes you already thought of.
LONGTEXT_ALLOWED = ("the tailored packet",)


def evaluate(fields, profile, band=None):
    """[(field, value, why, ok)], and whether the whole form can be completed.

    `band` is the (low, high) salary the POSTING published, or None. It is read
    off the job description, never guessed — see answer_for's salary rule.
    """
    out = []
    for f in fields:
        if f.kind == "hidden":
            continue
        v, why = answer_for(f, profile, band)
        if f.kind == "unknown" and f.required:
            v, why = None, f"unsupported field type '{f.raw_type}'"
        if f.kind == "longtext" and v is not None \
                and why not in LONGTEXT_ALLOWED:
            v, why = None, ("no rule for this question")
        out.append((f, v, why, v is not None))
    blocked = [(f, why) for f, v, why, ok in out if f.required and not ok]
    return out, blocked


# ---------------------------------------------------------------------------
# The roles worth asking about
# ---------------------------------------------------------------------------
def shortlist(conn):
    """One row per ROLE — dedup_key, never id. BUG-141."""
    rows = conn.execute(
        # `status`, not `bucket` — bucket is the LOCATION verdict (us_only,
        # canada, global). Matching tailor.py exactly, so the set of roles this
        # tool talks about is the same set that has a resume written for it.
        "SELECT dedup_key, MIN(id), MAX(company), MAX(title), MAX(score) "
        "FROM jobs WHERE status='shortlist' GROUP BY dedup_key "
        "ORDER BY MAX(score) DESC").fetchall()
    return rows


def cmd_check(conn, args):
    profile = load_profile()
    rows = shortlist(conn)
    ready, blocked_roles, noform, errors = [], [], [], []

    todo = []
    for dk, jid, co, ti, sc in rows:
        url, ats = track.apply_url(conn, dk)
        if not ats:
            noform.append((co, ti))
            continue
        # The posting's own text, so the salary rule can read a published band
        # instead of quoting the profile floor at an employer who already said
        # what the job pays.
        row = conn.execute(
            "SELECT description FROM jobs WHERE dedup_key=? "
            "AND description IS NOT NULL AND description != '' LIMIT 1",
            (dk,)).fetchone()
        todo.append((dk, jid, co, ti, sc, url, ats,
                     posting_band(row[0] if row else None)))
    if args.limit:
        todo = todo[:args.limit]

    print(f"\n{BOLD}  Reading {len(todo)} application forms{RESET}"
          f"  {DIM}(no browser, nothing submitted){RESET}\n")

    reasons = {}
    gap_only, essay_roles, rule_roles, consent_roles = [], [], [], []
    human_only = []
    for dk, jid, co, ti, sc, url, ats, band in todo:
        try:
            fields, _, _, _ = fetch_form(url, fresh=args.fresh)
        except Exception as e:                       # noqa: BLE001
            errors.append((co, ti, f"{type(e).__name__}: {e}"))
            print(f"  {RED}err {RESET} {(co or '')[:20]:20} {(ti or '')[:32]:32}"
                  f" {DIM}{str(e)[:28]}{RESET}")
            continue
        # [CHANGE: claude-code | 2026-08-27] Checked FIRST and reported apart.
        # This is not a blocker to be chipped away at like the others — it is
        # the employer saying an automated application is disqualifying. No
        # amount of profile.yaml or new rules moves a role out of this bucket.
        if form_forbids_ai(fields):
            human_only.append((co, ti))
            print(f"  {RED}human{RESET}{(co or '')[:20]:20} "
                  f"{(ti or '')[:32]:32} {DIM}form forbids AI-written answers"
                  f"{RESET}")
            continue
        _, blocked = evaluate(fields, profile, band)
        if not blocked:
            ready.append((jid, co, ti, sc, ats))
            print(f"  {GREEN}ok  {RESET} {(co or '')[:20]:20} "
                  f"{(ti or '')[:32]:32} {DIM}{ats}{RESET}")
        else:
            blocked_roles.append((jid, co, ti, blocked))
            first = blocked[0]
            kinds = {blocker_kind(bf, why) for bf, why in blocked}
            # Ordered by who has to act. A role needing an essay AND a missing
            # phone number is an essay role — filling the phone in does not
            # move it, so counting it as a gap would overstate what five lines
            # of profile.yaml buy.
            if kinds == {"gap"}:
                gap_only.append((co, ti))
            elif "essay" in kinds:
                essay_roles.append((co, ti))
            elif "consent" in kinds:
                consent_roles.append((co, ti))
            else:
                rule_roles.append((co, ti))
            for bf, why in blocked:
                # [CHANGE: claude-code | 2026-08-27] Count the QUESTION, not the
                # excuse. "no rule for this question" 25 times is not a finding —
                # it could be one recurring question or twenty-five different
                # ones, and those need completely different work. Keying on the
                # label turns the summary into a to-do list.
                bk = blocker_kind(bf, why)
                key = (f'[{bk}] "{bf.label[:52]}"'
                       if why == "no rule for this question"
                       else f"[{bk}] {why}")
                reasons[key] = reasons.get(key, 0) + 1
            print(f"  {YELLOW}wait{RESET} {(co or '')[:20]:20} "
                  f"{(ti or '')[:32]:32} {DIM}{first[1][:34]}{RESET}")

    print(f"\n  {BOLD}where the {len(rows)} shortlisted roles stand{RESET}")
    print("  " + "-" * 66)
    print(f"  {GREEN}{len(ready):3} ready to submit now{RESET}")
    print(f"  {CYAN}{len(gap_only):3} ready the moment profile.yaml is filled in"
          f"{RESET}  {DIM}nothing else blocks them{RESET}")
    print(f"  {YELLOW}{len(rule_roles):3} blocked on questions this tool cannot "
          f"map yet{RESET}  {DIM}my work{RESET}")
    print(f"  {RED}{len(essay_roles):3} ask required open questions{RESET}"
          f"  {DIM}no honest automatic answer exists{RESET}")
    print(f"  {RED}{len(consent_roles):3} need a legal agreement accepted{RESET}"
          f"  {DIM}yours to read and tick, not mine{RESET}")
    print(f"  {RED}{len(human_only):3} forbid AI-written answers outright{RESET}"
          f"  {DIM}you write these or you skip them{RESET}")
    print(f"  {DIM}{len(errors):3} unreadable (posting withdrawn or renamed)"
          f"{RESET}")
    print(f"  {DIM}{len(noform):3} have no application form found yet"
          f"  — Phase 4b{RESET}")
    if reasons and args.why:
        print(f"\n  {BOLD}what is blocking them{RESET}")
        for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"    {n:3}x  {why[:66]}")
    elif reasons:
        print(f"\n  {DIM}--why lists every blocking question{RESET}")
    print()
    return 0


def cmd_form(conn, args):
    profile = load_profile()
    dk, _full_id = track.key_for(conn, args.form)   # returns (key, id)
    if not dk:
        print(f"{RED}no such job id{RESET}")
        return 1
    url, ats = track.apply_url(conn, dk)
    if not ats:
        print(f"{YELLOW}no application form found for this role{RESET}  {url}")
        return 1
    fields, title, company, ats = fetch_form(url, fresh=args.fresh)
    print(f"\n{BOLD}  {company} — {title}{RESET}\n  {DIM}{ats}  {url}{RESET}\n")
    # [CHANGE: claude-code | 2026-08-27] Say it before the field list, not after.
    # This is the one thing on the page that changes what you are allowed to do,
    # and burying it under forty lines of answers is how it gets missed.
    if form_forbids_ai(fields):
        print(f"  {RED}{BOLD}This form forbids AI-written answers.{RESET}")
        for f in fields:
            if AI_FORBIDDEN.search(f.label or ""):
                print(f"  {DIM}{f.label[:200]}{RESET}")
                break
        print(f"  {YELLOW}apply.py will never submit this one. The fact fields "
              f"below are still\n  correct and safe to copy; the free-text "
              f"answers have to be yours.{RESET}\n")
    rows, blocked = evaluate(fields, profile)
    for f, v, why, ok in rows:
        mark = f"{GREEN}+{RESET}" if ok else (
            f"{RED}!{RESET}" if f.required else f"{DIM}-{RESET}")
        req = "req" if f.required else "   "
        print(f"  {mark} {DIM}{req}{RESET} {f.label[:46]:46} "
              f"{DIM}{f.kind}{RESET}")
        if ok:
            print(f"        {GREEN}{str(v)[:52]}{RESET}  {DIM}{why}{RESET}")
        else:
            print(f"        {DIM if not f.required else YELLOW}{why[:70]}{RESET}")
        if f.options and len(f.options) <= 12:
            print(f"        {DIM}options: "
                  f"{', '.join(str(o) for o in f.options)[:64]}{RESET}")
    print(f"\n  {'READY' if not blocked else str(len(blocked)) + ' REQUIRED '
                                            'FIELD(S) UNANSWERED'}\n")
    return 0


# ===========================================================================
# [CHANGE: claude-code | 2026-08-27] SUBMITTING — the half that cannot be undone.
#
# Everything above this line reads. Nothing above it writes to a company, to the
# database, or to disk. Below this line one action is irreversible: a submitted
# application cannot be recalled, edited or re-sent. So the rails here are not
# politeness, they are the whole design.
#
# WHY A REAL BROWSER AND NOT THE API
# -----------------------------------
# Greenhouse and Ashby both publish the form over an unauthenticated read, which
# is why --check needs no browser. Neither publishes a way to POST one. Both put
# INVISIBLE reCAPTCHA on the submit button — measured: Greenhouse ships
# GOOGLE_RECAPTCHA_INVISIBLE_KEY in its page source, and Ashby's /application
# page loads exactly one recaptcha iframe. Invisible reCAPTCHA does not show a
# puzzle; it scores the session and lets it through silently. A real Chromium
# doing real typing on a real display is the honest way to be scored well.
#
# WHAT THIS DELIBERATELY DOES NOT DO
# -----------------------------------
# No stealth flags. No --disable-blink-features=AutomationControlled, no patched
# navigator.webdriver, no CAPTCHA-solving service, no forged tokens. Two reasons,
# and the second one is the one that would actually cost Shawn something:
#
#   1. Solving or hiding from a CAPTCHA is defeating a control the employer put
#      there on purpose. Not our call to make on their site.
#   2. It is the losing move anyway. An application flagged as fraudulent does
#      not fail quietly — it can blacklist an email address across every company
#      on that ATS, and Greenhouse alone is thousands of employers. The downside
#      is not "this application fails", it is "all future applications fail".
#
# navigator.webdriver therefore reads True, and these forms are expected to
# accept that, because invisible reCAPTCHA weighs many signals and job boards
# tune it permissively (a false positive costs the employer a candidate). If a
# site disagrees and shows a real challenge, this program STOPS — see
# visible_challenge(). It never answers one.
#
# THE FIVE RAILS
# --------------
#   1. Dry run by DEFAULT. Filling happens; clicking Submit needs --submit.
#   2. Only roles --check calls READY. One unanswered required field, no send.
#   3. Never a form that forbids AI-written answers (form_forbids_ai).
#   4. Never twice. A recorded `submitted` event for that dedup_key skips it,
#      and the events table's UNIQUE constraint is the second line of defence.
#   5. A cap per run, so a bug costs a handful of applications and not 86.
#
# AND THE RULE THAT MATTERS MOST: this records `submitted` only when it has SEEN
# a confirmation. Anything else — a DOM field it could not locate, a challenge,
# a timeout, an ambiguous page — is `apply_failed` with a screenshot. A tracker
# that says "sent" about something that was not sent is worse than no tracker,
# because it stops him from applying himself.
# ===========================================================================

SUBMIT_DIR = os.path.expanduser("~/.local/share/luminos/jobhunt/submissions")
BROWSER_PROFILE = os.path.expanduser(
    "~/.local/share/luminos/jobhunt/browser-profile")
NOTIFY_PATH = os.path.expanduser("~/.local/share/luminos/jobhunt/needs-you.md")

# Chromium on this machine is a Wayland client. Without the ozone flags it picks
# X11, hits Xwayland's Xauthority check and dies with "Missing X server or
# $DISPLAY" — measured, not assumed.
CHROME_ARGS = ["--ozone-platform=wayland", "--enable-features=UseOzonePlatform"]


class FillError(Exception):
    """A field could not be located or set. Always a stop, never a guess."""


def ensure_display():
    """Point Chromium at the live Wayland session, or report that there is none.

    A systemd --user unit inherits XDG_RUNTIME_DIR but NOT WAYLAND_DISPLAY, so
    an unattended run would otherwise fall through to X11 and fail. Finding the
    socket ourselves is what makes the nightly timer able to submit; if there is
    no socket, nobody is logged in, and the honest answer is to skip rather than
    to launch a browser nothing can draw.
    """
    import glob
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    rt = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    for sock in sorted(glob.glob(os.path.join(rt, "wayland-*"))):
        if sock.endswith(".lock"):
            continue
        os.environ["WAYLAND_DISPLAY"] = os.path.basename(sock)
        os.environ["XDG_RUNTIME_DIR"] = rt
        return True
    return False


# A CAPTCHA the site is ASKING a human to solve, as opposed to the invisible one
# that scores every session. The distinction is the whole ethical line in this
# file: being scored is fine, being asked is a request for a human.
CHALLENGE_SEL = (
    "iframe[title*='recaptcha challenge' i]",
    "iframe[src*='hcaptcha.com']",
    "iframe[src*='turnstile']",
    "iframe[title*='challenge' i]",
)


def visible_challenge(page):
    """The title of a visible CAPTCHA challenge, or None.

    Checked on VISIBILITY, not presence: Google injects the challenge iframe
    into every page that loads reCAPTCHA and leaves it hidden until it decides
    the session needs proving. Testing for presence would abort all eight roles.
    """
    for sel in CHALLENGE_SEL:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1500):
                return sel
        except Exception:                                 # noqa: BLE001
            continue
    return None


def packet_files(packet_dir):
    """(resume_pdf, cover_letter_text) from a tailor.py packet, or (None, None).

    No packet means no application: sending an untailored generic resume is a
    different act from the one Phase 3 was built to do, and doing it silently
    because a file was missing is exactly the kind of quiet substitution this
    pipeline is supposed to refuse.
    """
    if not packet_dir or not os.path.isdir(packet_dir):
        return None, None
    pdf = os.path.join(packet_dir, "resume.pdf")
    txt = os.path.join(packet_dir, "cover_letter.txt")
    cover = None
    if os.path.exists(txt):
        with open(txt) as fh:
            cover = fh.read().strip()
    return (pdf if os.path.exists(pdf) else None), cover


def _resolve(value, pdf, cover):
    """Turn answer_for's placeholders into the real thing."""
    if value == "<resume.pdf>":
        return pdf
    if value == "<cover_letter>":
        return cover
    return value


# ---------------------------------------------------------------------------
# Locating a field in the DOM.
#
# Verified against live forms rather than reasoned about: Greenhouse renders the
# API's `first_name` as `#first_name`, and Ashby renders `_systemfield_name` as
# `[name="_systemfield_name"]`. So the API path IS the selector on both, which
# is the single fact that makes this driver short enough to trust.
#
# Ashby's ValueSelect comes back as radios whose ids are `<path>_<optionId>-...`,
# and its Boolean comes back as a pair of Yes/No BUTTONS sharing a parent div
# with a hidden `input[name=<path>][type=checkbox]`. Both were read off the page,
# because both are invisible in the API response.
# ---------------------------------------------------------------------------
def _css_id(path):
    """CSS-escape an id. Ashby's field paths are bare UUIDs, and a CSS id that
    starts with a digit is invalid — `#50708872-d452-...` silently selects
    nothing. Attribute form sidesteps the whole question."""
    return '[id="{}"]'.format(path.replace('"', '\\"'))


def _reveal_textarea(page, path):
    """Greenhouse hides the paste-it-in box behind a button. Click it.

    A Greenhouse resume/cover-letter question is one question with two fields —
    `cover_letter` (a file input) and `cover_letter_text` (a textarea) — and only
    the file input is rendered. The textarea does not exist in the DOM until
    "Enter manually" is clicked, so looking for it first and giving up is what
    the first version of this did. Found by running it, not by reading the page.
    """
    if not path.endswith("_text"):
        return False
    base = path[:-5]
    anchor = page.locator(f'input[type=file]{_css_id(base)}').first
    if not anchor.count():
        return False
    # The NEAREST ancestor that actually contains the button. Scoping to the
    # file input's own div was the first attempt and it found nothing: Greenhouse
    # hides the input inside a wrapper and puts Attach / Dropbox / Google Drive /
    # Enter manually a few levels up. There are two such buttons on the page
    # (resume and cover letter), so an unscoped search would click the wrong one.
    btn = anchor.locator(
        'xpath=ancestor::div[.//button[contains(normalize-space(.),'
        '"Enter manually")]][1]'
    ).get_by_role("button", name=re.compile(r"enter manually", re.I)).first
    if not btn.count():
        return False
    btn.click(timeout=5000)
    page.wait_for_timeout(600)
    return True


def _set_text(page, f, value):
    sel = f'{_css_id(f.path)}, [name="{f.path}"]'
    el = page.locator(sel).first
    if not el.count() and _reveal_textarea(page, f.path):
        el = page.locator(sel).first
    if not el.count():
        raise FillError(f"no input for {f.path!r} ({f.label[:40]})")
    el.scroll_into_view_if_needed(timeout=5000)
    # type=, not fill=: these forms are React-controlled and a few of them ignore
    # a value set without keystrokes. It is also what a person does, which is the
    # signal invisible reCAPTCHA is actually reading.
    el.click(timeout=5000)
    el.press_sequentially(str(value), delay=18, timeout=30000)


def _set_file(page, f, path_on_disk):
    if not path_on_disk or not os.path.exists(path_on_disk):
        raise FillError(f"{f.label[:40]}: no file to upload")
    el = page.locator(
        f'input[type=file]{_css_id(f.path)}, '
        f'input[type=file][name="{f.path}"]').first
    if not el.count():
        el = page.locator("input[type=file]").first
        if not el.count():
            raise FillError(f"no file input for {f.label[:40]}")
    el.set_input_files(path_on_disk, timeout=30000)


def _set_choice(page, f, value):
    """One option, matched on its visible label, across four widget shapes."""
    want = str(value).strip()

    # 1. a real <select>
    sel = page.locator(f'select{_css_id(f.path)}, select[name="{f.path}"]').first
    if sel.count():
        sel.select_option(label=want, timeout=10000)
        return

    # 2. Ashby radios. The id is "<parentId>_<path>-labeled-radio-N" — the field
    # path is in the MIDDLE, not at the start, so a ^= selector matched nothing
    # and the question silently went unanswered. Read off a live form after the
    # first version quietly skipped Supabase's "where did you hear" question.
    radios = page.locator(f'input[type=radio][id*="{f.path}"]')
    if radios.count():
        for i in range(radios.count()):
            r = radios.nth(i)
            rid = r.get_attribute("id") or ""
            lab = page.locator(f'label[for="{rid}"]').first
            if lab.count() and lab.inner_text().strip().lower() == want.lower():
                lab.scroll_into_view_if_needed(timeout=5000)
                lab.click(timeout=5000)
                return
        raise FillError(f"{f.label[:40]}: no radio labelled {want!r}")

    # 3. Ashby Yes/No: buttons sharing the innermost div with a hidden checkbox
    #    named for the field. `.last` is that innermost div — document order puts
    #    the deepest matching ancestor last.
    box = page.locator(f'input[name="{f.path}"]')
    if box.count():
        holder = page.locator(f'div:has(> input[name="{f.path}"])').last
        if holder.count():
            btn = holder.get_by_role("button", name=want, exact=True).first
            if btn.count():
                btn.scroll_into_view_if_needed(timeout=5000)
                btn.click(timeout=5000)
                return

    # 4. Greenhouse: a typeahead combobox that opens a listbox of options
    combo = page.locator(
        f'input[role=combobox]{_css_id(f.path)}, '
        f'input[role=combobox][name="{f.path}"]').first
    if combo.count():
        combo.scroll_into_view_if_needed(timeout=5000)
        combo.click(timeout=5000)
        combo.press_sequentially(want[:24], delay=25, timeout=20000)
        page.wait_for_timeout(700)
        opt = page.get_by_role("option", name=want, exact=True).first
        if not opt.count():
            opt = page.get_by_role("option", name=want).first
        if not opt.count():
            raise FillError(f"{f.label[:40]}: no option {want!r} in the list")
        opt.click(timeout=8000)
        return

    raise FillError(f"{f.label[:40]}: cannot find a control for {f.path!r}")


def fill_form(page, rows, pdf, cover, log):
    """Set every answerable field. Raises FillError on a REQUIRED field it
    cannot set — an unfillable required field is a stop, and the form is left on
    screen exactly as far as it got so a human can finish it."""
    filled, skipped = 0, 0
    for f, v, why, ok in rows:
        if not ok or v is None:
            skipped += 1
            continue
        val = _resolve(v, pdf, cover)
        if val is None or val == "":
            if f.required:
                raise FillError(f"{f.label[:40]}: the packet has no {v}")
            skipped += 1
            continue
        try:
            if f.kind == "file":
                _set_file(page, f, val)
            elif f.kind in ("select", "multiselect", "boolean"):
                _set_choice(page, f, val)
            else:
                _set_text(page, f, val)
            filled += 1
            log.append(f"    + {f.label[:44]:44} {str(val)[:36]}")
        except Exception as e:                            # noqa: BLE001
            # [CHANGE: claude-code | 2026-08-27] REQUIRED decides whether this
            # stops, not the exception type. The first version re-raised every
            # FillError and an optional Greenhouse cover-letter box that simply
            # is not in the DOM killed the whole run — a rail firing on something
            # that was never a problem. A field the employer did not ask for
            # cannot be a reason to abandon an application.
            if f.required:
                msg = (str(e) if isinstance(e, FillError) else
                       f"{f.label[:40]}: {type(e).__name__}: "
                       f"{str(e).splitlines()[0][:60]}")
                raise FillError(msg)
            skipped += 1
            log.append(f"    {DIM}- {f.label[:44]:44} optional, could not set"
                       f"{RESET}")
    return filled, skipped


# The page after a successful send. Checked as TEXT the employer chose to show,
# not as a URL pattern, because both ATSs render confirmation in place without
# navigating and a URL check would report every send as a failure.
SUCCESS_TEXT = re.compile(
    r"thank you for applying|application (has been )?(was )?(submitted|received)"
    r"|thanks for applying|we('| ha)ve received your application"
    r"|your application (has been sent|was sent|is in)"
    r"|submitted your application|application complete", re.I)


def submitted_ok(page):
    """Did the employer say it landed? Returns the sentence, or None."""
    for _ in range(20):                       # ~20s, these pages POST then swap
        try:
            body = page.inner_text("body", timeout=4000)
        except Exception:                                 # noqa: BLE001
            body = ""
        m = SUCCESS_TEXT.search(body or "")
        if m:
            return m.group(0)[:80]
        page.wait_for_timeout(1000)
    return None


def apply_page_url(url, ats):
    """Ashby keeps the form at /application; Greenhouse's job URL IS the form."""
    if ats == "ashby" and not url.rstrip("/").endswith("/application"):
        return url.rstrip("/") + "/application"
    return url


def notify(lines):
    """Append to the same file followup.py writes. One place he has to look."""
    try:
        os.makedirs(os.path.dirname(NOTIFY_PATH), exist_ok=True)
        with open(NOTIFY_PATH, "a") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def submit_one(ctx, conn, role, profile, args):
    """One role, start to finish. Returns (outcome, detail).

    outcome is 'submitted', 'filled' (dry run), 'skipped' or 'failed'. Only
    'submitted' ever writes a submitted event, and only after submitted_ok().
    """
    dk, jid, co, ti, url, ats, band, packet_dir = role
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shots = os.path.join(SUBMIT_DIR, f"{dk[:12]}-{stamp}")
    os.makedirs(shots, exist_ok=True)

    # Order matters for the REASON, not for safety — all four of these are
    # stops. A role that is blocked on a required question AND has no resume
    # yet should say it is blocked, because that is the thing that has to be
    # fixed first; reporting "no resume" would send someone off to run tailor.py
    # for nothing.
    fields, _, _, _ = fetch_form(url, fresh=args.fresh)
    if form_forbids_ai(fields):
        return "skipped", "form forbids AI-written answers"
    rows, blocked = evaluate(fields, profile, band)
    if blocked:
        return "skipped", (f"{len(blocked)} required field(s) unanswered — "
                           f"{blocked[0][1][:40]}")
    pdf, cover = packet_files(packet_dir)
    if not pdf:
        return "skipped", "no tailored resume yet — run tailor.py first"

    page = ctx.new_page()
    log = []
    try:
        page.goto(apply_page_url(url, ats), timeout=90000,
                  wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        ch = visible_challenge(page)
        if ch:
            page.screenshot(path=os.path.join(shots, "challenge.png"),
                            full_page=True)
            return "failed", f"a CAPTCHA challenge is on the page ({ch})"

        filled, skipped = fill_form(page, rows, pdf, cover, log)
        page.screenshot(path=os.path.join(shots, "filled.png"), full_page=True)
        for line in log:
            print(line)
        print(f"    {DIM}{filled} filled, {skipped} left blank — "
              f"{shots}/filled.png{RESET}")

        if not args.submit:
            # The window stays open on purpose in dry run: the point is that he
            # can look at a real filled form before ever letting it be sent.
            return "filled", f"dry run — nothing sent ({filled} fields)"

        btn = page.get_by_role(
            "button", name=re.compile(r"^submit application$", re.I)).first
        if not btn.count():
            btn = page.locator(
                "button[type=submit]:has-text('Submit'), "
                "input[type=submit]").first
        if not btn.count():
            page.screenshot(path=os.path.join(shots, "no-button.png"),
                            full_page=True)
            return "failed", "no Submit button found on the page"

        btn.scroll_into_view_if_needed(timeout=5000)
        page.wait_for_timeout(800)
        btn.click(timeout=20000)

        # Invisible reCAPTCHA runs HERE. If it decided the session needs proving,
        # the challenge appears after the click, not before it.
        page.wait_for_timeout(3500)
        ch = visible_challenge(page)
        if ch:
            page.screenshot(path=os.path.join(shots, "challenge.png"),
                            full_page=True)
            return "failed", ("a CAPTCHA challenge appeared on submit — the "
                              "form is filled and waiting for you")

        said = submitted_ok(page)
        page.screenshot(path=os.path.join(shots, "after.png"), full_page=True)
        if not said:
            # Filled, clicked, and no confirmation seen. It may well have gone
            # through — which is exactly why this is not recorded as sent. He
            # checks the screenshot and decides; the tool does not decide for him.
            return "failed", ("clicked Submit but saw no confirmation — check "
                              f"{shots}/after.png before re-sending")
        return "submitted", said
    finally:
        if args.submit:
            page.close()


def cmd_submit(conn, args):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"{RED}playwright is not importable from this interpreter{RESET}")
        print(f"  {DIM}run it with /opt/luminos/venv-jobhunt/bin/python{RESET}")
        return 1
    if not ensure_display():
        print(f"{YELLOW}no Wayland session — nobody is logged in, so there is "
              f"no screen\n  to draw a browser on. Skipping (the timer retries "
              f"tomorrow).{RESET}")
        return 0

    profile = load_profile()
    rows = shortlist(conn)
    done = {r[0] for r in conn.execute(
        "SELECT dedup_key FROM events WHERE kind='submitted'")}
    # Three failures on one role is a pattern, not bad luck. Stop re-opening it.
    tried = {}
    for r in conn.execute("SELECT dedup_key, COUNT(*) FROM events "
                          "WHERE kind='apply_failed' GROUP BY dedup_key"):
        tried[r[0]] = r[1]

    # [CHANGE: claude-code | 2026-08-27] Decide READY first, cap second. The
    # first version capped the highest-scoring roles at --max and then checked
    # them, so `--apply --max 8` spent the whole budget on eight roles that were
    # all blocked or AI-forbidden and opened nothing. --max is a blast radius,
    # not a queue length: it has to count applications actually attempted.
    #
    # Re-reading the forms here is nearly free — fetch_form serves them from the
    # day-old disk cache, and it is the same read cmd_check does.
    todo, why_not = [], {}
    for dk, jid, co, ti, sc in rows:
        if args.only and args.only.lower() not in (co or "").lower() \
                and not dk.startswith(args.only) \
                and not jid.startswith(args.only):
            continue
        if dk in done:
            why_not["already submitted"] = why_not.get("already submitted", 0) + 1
            continue
        # Three failures on one role is a pattern, not bad luck.
        if tried.get(dk, 0) >= 3:
            why_not["failed 3 times already"] = \
                why_not.get("failed 3 times already", 0) + 1
            continue
        url, ats = track.apply_url(conn, dk)
        if not ats:
            why_not["no application form found"] = \
                why_not.get("no application form found", 0) + 1
            continue
        try:
            fields, _, _, _ = fetch_form(url, fresh=args.fresh)
        except Exception:                                 # noqa: BLE001
            # A withdrawn or renamed posting. Not our failure and not something
            # to record against the role — there is no form to fail at.
            why_not["posting unreadable"] = why_not.get("posting unreadable", 0) + 1
            continue
        if form_forbids_ai(fields):
            why_not["form forbids AI-written answers"] = \
                why_not.get("form forbids AI-written answers", 0) + 1
            continue
        row = conn.execute(
            "SELECT description, packet_dir FROM jobs WHERE dedup_key=? "
            "AND packet_dir IS NOT NULL LIMIT 1", (dk,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT description, packet_dir FROM jobs WHERE dedup_key=? "
                "LIMIT 1", (dk,)).fetchone()
        desc, packet_dir = (row or (None, None))
        _, blocked = evaluate(fields, profile, posting_band(desc))
        if blocked:
            why_not["a required question has no honest answer"] = \
                why_not.get("a required question has no honest answer", 0) + 1
            continue
        if not packet_files(packet_dir)[0]:
            why_not["no tailored resume yet (run tailor.py)"] = \
                why_not.get("no tailored resume yet (run tailor.py)", 0) + 1
            continue
        todo.append((dk, jid, co, ti, url, ats, posting_band(desc), packet_dir))
    eligible = len(todo)
    todo = todo[:max(1, args.max)]

    mode = (f"{RED}{BOLD}LIVE — applications will be sent{RESET}" if args.submit
            else f"{GREEN}dry run — fills the form, sends nothing{RESET}")
    print(f"\n{BOLD}  {len(todo)} of {eligible} ready role(s){RESET}   {mode}")
    if why_not:
        print(f"  {DIM}not attempted: " + ", ".join(
            f"{n} {k}" for k, n in sorted(why_not.items(), key=lambda kv: -kv[1])
        )[:150] + f"{RESET}")
    print()
    if not todo:
        return 0

    counts = {"submitted": 0, "filled": 0, "skipped": 0, "failed": 0}
    needs_you = []
    with sync_playwright() as pw:
        # A PERSISTENT profile, not a fresh incognito each time. A browser with
        # no history and no cookies is itself an automation signal, and this also
        # means a cookie banner dismissed once stays dismissed.
        os.makedirs(BROWSER_PROFILE, exist_ok=True)
        ctx = pw.chromium.launch_persistent_context(
            BROWSER_PROFILE, headless=False, args=CHROME_ARGS,
            viewport={"width": 1400, "height": 1000},
            accept_downloads=False)
        try:
            for role in todo:
                dk, jid, co, ti = role[0], role[1], role[2], role[3]
                print(f"  {BOLD}{(co or '')[:24]}{RESET} — {(ti or '')[:44]}")
                try:
                    outcome, detail = submit_one(ctx, conn, role, profile, args)
                except FillError as e:
                    outcome, detail = "failed", str(e)
                except Exception as e:                    # noqa: BLE001
                    outcome, detail = "failed", (f"{type(e).__name__}: "
                                                 f"{str(e).splitlines()[0][:70]}")
                counts[outcome] += 1
                colour = {"submitted": GREEN, "filled": CYAN,
                          "skipped": DIM, "failed": RED}[outcome]
                print(f"    {colour}{outcome}{RESET}  {DIM}{detail[:70]}{RESET}\n")

                if outcome == "submitted":
                    track.record(conn, jid, "submitted", detail=detail,
                                 evidence=url_of(conn, dk))
                elif outcome == "failed" and args.submit:
                    track.record(conn, jid, "apply_failed", detail=detail[:200],
                                 evidence=f"{track.now()[:19]}")
                    needs_you.append(f"- **{co} — {ti}**  {detail}")
        finally:
            if args.submit:
                ctx.close()
            else:
                print(f"  {DIM}browser left open so you can look at the filled "
                      f"forms. Close it when done.{RESET}")
                try:
                    input("  press Enter to close the browser... ")
                except EOFError:
                    pass
                ctx.close()

    print(f"  {BOLD}{counts['submitted']} sent, {counts['filled']} filled, "
          f"{counts['skipped']} skipped, {counts['failed']} failed{RESET}\n")
    if needs_you:
        notify([f"\n## applications that stopped and need you "
                f"({track.now()[:16]})"] + needs_you)
        print(f"  {YELLOW}{len(needs_you)} need you — written to "
              f"{NOTIFY_PATH}{RESET}\n")
    return 0


def url_of(conn, dk):
    u, _ = track.apply_url(conn, dk)
    return u or dk


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="read every shortlisted form, report ready vs blocked")
    ap.add_argument("--form", metavar="ID",
                    help="show the full form for one role")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--fresh", action="store_true",
                    help="ignore the cached copy of each form")
    ap.add_argument("--why", action="store_true",
                    help="with --check, list every blocking question")
    # [CHANGE: claude-code | 2026-08-27] --apply fills, --submit sends. Two flags
    # and not one, because the dangerous thing must be the thing you typed on
    # purpose. `--apply` alone is always safe to run and always shows you a real
    # filled form; there is no combination of a typo and a default that sends an
    # application.
    ap.add_argument("--apply", action="store_true",
                    help="open each ready role in a real browser and fill it in")
    ap.add_argument("--submit", action="store_true",
                    help="with --apply, actually press Submit. IRREVERSIBLE.")
    ap.add_argument("--max", type=int, default=3,
                    help="how many roles per run (default 3)")
    ap.add_argument("--only", metavar="ID|COMPANY",
                    help="restrict to one role, by job id or company name")
    args = ap.parse_args()

    if not os.path.exists(PROFILE_PATH):
        print(f"{RED}no profile.yaml{RESET}")
        return 1
    conn = track.connect()
    if args.form:
        return cmd_form(conn, args)
    if args.apply:
        return cmd_submit(conn, args)
    if args.submit:
        print(f"{YELLOW}--submit does nothing on its own; it is a modifier on "
              f"--apply.{RESET}\n  {DIM}./apply.py --apply           fill, send "
              f"nothing\n  ./apply.py --apply --submit  fill and send{RESET}")
        return 1
    if args.check:
        return cmd_check(conn, args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
