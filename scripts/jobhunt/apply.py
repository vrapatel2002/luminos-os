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
"""

import argparse
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


def answer_for(f, p):
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
        v = ans.get("salary_expectation_cad")
        return (str(v), "salary_expectation_cad") if v else (
            None, "salary_expectation_cad is empty in profile.yaml")
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
    if re.search(r"how did you (first )?(hear|learn)|where did you (hear|find)"
                 r"|referral source|source", lab):
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


def evaluate(fields, profile):
    """[(field, value, why, ok)], and whether the whole form can be completed."""
    out = []
    for f in fields:
        if f.kind == "hidden":
            continue
        v, why = answer_for(f, profile)
        if f.kind == "unknown" and f.required:
            v, why = None, f"unsupported field type '{f.raw_type}'"
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
        todo.append((dk, jid, co, ti, sc, url, ats))
    if args.limit:
        todo = todo[:args.limit]

    print(f"\n{BOLD}  Reading {len(todo)} application forms{RESET}"
          f"  {DIM}(no browser, nothing submitted){RESET}\n")

    reasons = {}
    gap_only, essay_roles, rule_roles, consent_roles = [], [], [], []
    human_only = []
    for dk, jid, co, ti, sc, url, ats in todo:
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
        _, blocked = evaluate(fields, profile)
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
    args = ap.parse_args()

    if not os.path.exists(PROFILE_PATH):
        print(f"{RED}no profile.yaml{RESET}")
        return 1
    conn = track.connect()
    if args.form:
        return cmd_form(conn, args)
    if args.check:
        return cmd_check(conn, args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
