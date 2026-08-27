# Jobhunt — how to actually use it

<!-- [CHANGE: claude-code | 2026-08-06] -->

**PLAN.md is the design. This is the manual.** If you only read one section,
read *The one command you need* and *The two things only you can do*.

---

## The one command you need

```bash
cd ~/luminos-os/scripts/jobhunt
./status.py
```

That is the whole "just look at progress" surface. It prints, in order:

- **PIPELINE** — is the nightly run scheduled, is the Control UI up, how old is
  the data. If a line is red it prints the exact command that fixes it.
- **FUNNEL** — how ~9,800 raw postings became a short list, and where the losses
  happened.
- **BEST MATCHES** — the actual jobs, best first, each with a one-line reason.

Everything below is detail you only need when you want to change something.

---

## How the thing works, in plain terms

Four stages. Each one is cheaper than the one after it, which is the entire
design principle.

```
  ingest.py    crawl six job boards          ~9,800 postings
     |                                          free
  score.py     stage 1: the free filter      ->   192 roles
     |         regex + location rules           free, ~1 second
     |
  score.py     stage 2: the local model      ->  ranked 0-100
     |        gemma-4-E4B on the RTX 4050       free, ~7s per job
     |
  status.py    you read the list             ->  you decide
                                                 free
```

### Why it filters before it thinks

You told me to use the cheapest model for bulk work. **The cheapest model is
not calling a model at all.** Measured on the real database:

| approach | tokens the model reads |
|---|---|
| show every posting to an LLM | ~18,200,000 |
| filter first, then show survivors | ~367,000 |

That is **50× less work** for the same answer, because nothing about "is this
US-only", "is it remote", or "does the title say Senior" needs a language
model. Those are string comparisons. They are exact, they are instant, and they
are free.

What survives the filter goes to **gemma-4-E4B running on your own RTX 4050**. No
API key, no per-token bill, no data leaving the laptop. A cloud model gets
involved only in Phase 3, when it writes a tailored resume for one specific job
— a handful of calls where quality actually changes an outcome.

### The GPU does not stay awake

`score.py` starts the model service, uses it, and **stops it again**. An idle
llama server pins ~4.6 GB of VRAM and holds the dGPU out of sleep forever —
that was BUG-103, and re-creating it would cost you battery for nothing.

`status.py` reports `local model  inactive  idle (correct — GPU asleep)`. Green
means off. That is not a fault.

---

## Changing what it hunts for

**One file: `targets.yaml`.** Nothing else needs touching, ever.

Open it, edit it, then:

```bash
./score.py --rules-only
```

That re-runs the free filter over the entire database and reprints the funnel in
about a second. No GPU, no cost. Do it as many times as you like. Only when the
survivor count looks right do you spend the model on them:

```bash
./score.py
```

### Adding a kind of job

Add a line to `include_titles`. Want technical writing roles?

```yaml
include_titles:
  - \b(technical writer|documentation)\b     # <- already there
  - \b(content|copywriter)\b                 # <- your new line
```

### Removing a kind of job

Two ways, and they mean different things:

- Delete the line from `include_titles` — "stop looking for these".
- Add a line to `exclude_titles` — "kill these even if something else matches".

Use `exclude_titles` when a word keeps dragging in junk. `Senior Sales Engineer`
matches `engineer`, so `sales` lives on the exclude list to kill it first.

### Seeing what got thrown away

This is the important habit. A filter you never audit quietly stops working.

```bash
./status.py --rejects
```

Samples what each rule cut, grouped by reason. If you see a job in there you
wanted, that is a `targets.yaml` edit — not a code change.

### As you gain experience

```yaml
max_years_experience: 2    # raise this as you get hired
```

Then:

```bash
./score.py --recompute
```

Takes about a second and **does not touch the GPU**. The model reports what each
posting demands as a plain number; the ranking arithmetic happens in Python. So
re-tuning is instant instead of another 25-minute pass.

---

## Reading a score

```bash
./status.py --why 0c2dcdfc     # the model's full reasoning
./browse.py --show 0c2dcdfc    # the original posting
```

Scores are computed, not guessed by the model. Roughly:

| what | effect |
|---|---|
| subject matter fits well | starts at 88 |
| adjacent field | starts at 70 |
| each year of experience demanded above yours | −12, then −8, then −5 each |
| five or more required skills you lack | capped at 55 |
| US-only, clearance, wrong country | capped at 25 |

**Why arithmetic instead of asking the model for a number:** I asked it for a
0-100 rating first. On a sample of five, **four came back as exactly 40** — not
because it was confused, its written reasoning was correct every time, but
because it parked on the floor of a rubric band. A ranking where everything
shares one value is not a ranking.

The rebuild is the useful lesson: **the model is a reliable reader and an
unreliable judge.** It now reports facts — how many years the posting demands,
which skills it names, whether it is US-only — and Python does the ranking. That
also made two more bugs visible that a single opaque number had hidden:

- A Twilio listing came back `fit_signal: strong` while listing **thirteen**
  required technologies you do not have. The prose said so; the label did not.
  Now a long `missing_skills` list overrides the label.
- A `Remote - US` posting reached the shortlist. Its Canadian twin had been
  scored, and the database write splattered that score across every listing
  sharing the same role — including the US-only one the filter had correctly
  rejected.

---

## The two things only you can do

Everything else is built and running. These two are not, and I cannot do either.

### 1. Log in to Claude Code

```bash
claude          # then type: /login
```

Your stored token expired **2026-05-27**. You use the desktop app and Cowork, so
the npm CLI's own credential file went stale unnoticed. The OpenClaw agent
(Phase 5, the part that fills in application forms) shells out to that CLI and
fails with `OAuth access token has expired` until you do this.

An environment variable set in some other terminal does **not** count — the
gateway logs `cli env auth: child=none`, meaning the child process reads only
`~/.claude/.credentials.json`. This is why `claude -p` can work in one window
while OpenClaw still fails.

Nothing above Phase 5 needs this. Scoring and browsing work fine without it.

### 2. Write your `profile.yaml`

**This is the real blocker, and it gates everything that produces an
application.**

```bash
cp scripts/jobhunt/profile.example.yaml scripts/jobhunt/profile.yaml
```

Then fill it in. The template documents every field and, more importantly, the
rule that makes the whole thing safe: **Phase 3 may only use lines from
`bullet_bank`**, so a claim that is not in that file cannot reach an employer.

`profile.yaml` is **gitignored** — it holds your real name, location, education
and employment history, and this repository is public. Only the `.example` file
is tracked. Verify rather than assume:

```bash
git check-ignore -v scripts/jobhunt/profile.yaml
```

Until that file exists the model scores against a *placeholder*: "recent CS/IT
grad, 0-2 years, knows Python, Linux, SQL, Git". `score.py` says so on every
run. The rankings are directionally useful and **not** final, because the model
is comparing postings against a person nobody has met.

With a real profile in place:

- scores compare against **you**, not a guess
- Phase 3 writes a resume tailored per posting, using only bullets that are
  actually true — the validator enforces that, so it cannot invent a fact even
  if the model tries
- Phase 4/5 can fill applications

---

## Command reference

```bash
# looking
./status.py                    # the dashboard
./status.py --top 40           # more matches
./status.py --why <id>         # full reasoning for one job
./status.py --rejects          # audit what the filter cut
./status.py --short            # one line, for a status bar
./browse.py --show <id>        # the original posting
./browse.py --companies        # who is hiring

# changing
$EDITOR targets.yaml           # the only file you edit
./score.py --rules-only        # re-filter, ~1s, free
./score.py --recompute         # re-rank from stored answers, ~1s, no GPU
./score.py                     # filter, then model-score the new survivors
./score.py --limit 20          # score only 20 (try a change cheaply)
./score.py --rescore           # re-score everything from scratch (~25 min)
./score.py --dry-run           # print one prompt, call nothing

# services
systemctl --user list-timers jobhunt-pipeline.timer
systemctl --user start jobhunt-pipeline.service     # run the nightly job now
journalctl --user -u jobhunt-pipeline -n 50         # what happened last night
./install-services.sh                               # re-link units after edits
```

---

## What runs on its own

| unit | when | what it does |
|---|---|---|
| `jobhunt-pipeline.timer` | 03:30 daily | crawl, then score |
| `openclaw-gateway.service` | always | Control UI on 127.0.0.1:18789 |
| `jobhunt-llm.service` | on demand | the model — started and stopped by `score.py` |
| `jobhunt-toolproxy.service` | on demand | tool-call translator, only for the agent |

The timer is `Persistent=true`, which matters on a laptop: if the machine is
asleep at 03:30 the run is not skipped, it fires on the next resume.

`jobhunt-llm.service` is **deliberately not enabled at boot**. Enabling it would
hold the dGPU awake permanently.

### Things that will bite

- **Never point an agent at port 8081.** Use 8082. 8081 gives working chat and
  *silently broken* tool calls — the worst kind of failure, because everything
  looks fine.
- **`systemctl --user` units do not start until you log in.** If you want the
  nightly run on a headless boot, that needs lingering enabled, which is a
  separate decision.
- **The scores are provisional until there is a `profile.yaml`.** Do not read
  the current ordering as gospel.

---

## Phase 3 — tailoring, and the one rule that makes it safe
<!-- [CHANGE: claude-code | 2026-08-26] -->

```bash
./tailor.py --list             # what is shortlisted, best first (* = done)
./tailor.py --top 3            # tailor the best 3 not yet done
./tailor.py --job 4f5ce37d     # one job (an id prefix is enough)
./tailor.py --top 3 --dry-run  # ask and check, write nothing
./tailor.py --job 4f5ce37d --force   # redo one
```

Each finished job becomes a directory under
`~/.local/share/luminos/jobhunt/applications/`:

| file | what it is |
|---|---|
| `resume.pdf` | one page, ready to attach |
| `resume.tex` | the source, if you want to hand-edit |
| `resume.txt` | what a parser sees — read this, not the PDF |
| `cover_letter.txt` | 120-200 words, no greeting or sign-off |
| `packet.json` | the model's output AND the source bullet for every line |

**`packet.json` is the receipt.** Its `sources` block maps every bullet on the
resume back to the exact `bullet_bank` entry it came from. If a line ever looks
too good, that file tells you in one look whether it was earned or invented.

**The model cannot state a fact.** It picks bullets by id and rephrases them.
Anything it adds that is not in the source bullet — any number, any tool, any
employer, any date — is rejected automatically and it is told why, up to three
tries. Two things follow that are worth knowing:

- **A rejection is normal.** Most jobs take two attempts. The first draft
  reaches, the second one behaves. Only a third failure is a real problem.
- **The cover letter cannot name the company's products.** It can say
  "Canonical" and it can say the job title, but not "Ubuntu". That is on
  purpose — see DECISION 83. If it mattered, you would add the word to
  `profile.yaml` yourself, which is the correct place for a true thing.

Everything on the resume comes from `profile.yaml`. **To change what it can
say, change that file** — there is nowhere else for a claim to come from.

---

## Phase 3.5 — tracking what happened
<!-- [CHANGE: claude-code | 2026-08-27] -->

```bash
./track.py                     # the board: funnel, rates, what needs you
./track.py --show 4f5ce37d     # one application, in full
./track.py --history 4f5ce37d  # the raw event rows
./track.py --silent 21         # sent 21+ days ago, still nothing back
./track.py --stage interview   # every role at one stage
./track.py --kinds             # the event vocabulary
```

`apply.py` and `followup.py` both write into this. It is the shared spine, which
is why it was built first.

### It is an event log, not a status column

Nothing is ever overwritten. Every state change appends a row to `events`, and
the current stage is *derived* by reading the whole history back. A status column
would have been less code, and it was rejected on purpose:

- **This codebase has a documented habit of reporting success while doing
  nothing** — BUG-088, BUG-089, BUG-104. A status column that says `submitted`
  is a claim. An event row carrying a screenshot path is evidence.
- **A rejection three days after an interview is information.** A status column
  destroys the interview when it writes the rejection.

Every event carries `evidence`: a packet directory, a screenshot, a Gmail message
id. An event with no evidence is an assertion, and assertions are what went
wrong last time.

### Recording the same thing twice is a no-op

`followup.py` re-reads the same inbox every night, so it will hand over the same
rejection email twenty times. `UNIQUE(dedup_key, kind, evidence)` makes the
nineteen repeats silently do nothing. **This is why evidence must be stable** —
a Gmail message id is stable, a timestamp is not.

### Keyed on `dedup_key`, never on `id`

One role carried by three boards is three `jobs` rows. Tracking per row would
re-import BUG-141 into the tracker. `--show 4f5ce37d` takes an id prefix and
resolves it to the role.

### A rejection is not allowed to hide an interview

`rejected` is terminal and beats every other stage, so a role that reached
`interview` and was then rejected shows as `rejected`. That is correct when the
email was read correctly — and it is a disaster when it was not, because
`followup.py` classifies mail without asking, and the whole point of the pipeline
is to produce interviews.

So the board has a **CLOSED, BUT REACHED YOU FIRST** section. It does not
overrule the rejection. It just refuses to let a terminal event make an interview
invisible, so a misread email is something you can see instead of something you
cannot.

### `apply at` is not always the URL that was crawled

A role listed on both jobicy and Greenhouse has two URLs, and they are not
interchangeable — one is an article about the job, the other is the form. `--show`
picks the applyable one out of the whole dedup group and labels the other `also
listed`. Where no form exists anywhere in the group it says so in yellow rather
than pretending the aggregator link will work.

Right now, of 86 shortlisted roles: **22 Greenhouse, 17 Ashby, 47 with no form
found yet.** Those 47 are the Phase 4 problem.

### Testing against a copy

```bash
cp ~/.local/share/luminos/jobhunt.db /tmp/t.db
JOBHUNT_DB=/tmp/t.db ./track.py --log <id> interview --at 2026-08-26T08:00:00
```

`JOBHUNT_DB` exists so the stages that have not happened yet can be exercised
without writing invented events into the real job history.

---

## Phase 5 — reading the replies

`followup.py` reads the inbox, decides what each message means, records it as an
event, and drafts a reply where a reply is safe. It is **built and tested but
read-only**: it cannot reach Gmail yet, and `--send` refuses.

```bash
./followup.py --self-test          # 12 real archive cases through the classifier
./followup.py --explain "we'd like to schedule a call"
./followup.py --from-json mail.json        # dry run, prints what it WOULD do
./followup.py --from-json mail.json --apply    # write the events
./followup.py --scan --days 30 --apply         # needs OAuth (see below)
```

### Provenance before meaning

Nothing is interpreted until it can be tied to an application we recorded
sending. That order is not fussiness — it is what the real inbox does to a
keyword search. A naive search over 400 days returned **2 hits, both false**:

- **Temu**: "Congrats! Vratik Patel" and "Thank you for your purchase!"
- **a car loan**: "(Next Steps) We've received your application"

Both read exactly like a recruiter. Neither is one. So the sender's domain must
match a company we applied to, or be a known ATS, or the thread must trace back
to a `submitted` event — otherwise the message is dropped before a single word
is classified.

The domain match runs through `norm_company()`, the same function BUG-141 was
about. "Canonical Ltd." flattens to `canonicalltd`, which is not in
`canonical.com`, so without stripping the legal suffix the strongest provenance
check would have quietly failed for every employer that writes one.

Provenance is not enough on its own: **`sah.subscriptions@gmail.com` is a real
employer on plain Gmail**, and Outlook out-of-office autoreplies
(`Automatic reply: DATA SYSTEMS SPECIALIST`) come from the right domain and mean
nothing. Both are handled explicitly.

### Decisive vs weak evidence

Each rule is marked decisive or not. `decided not to move forward` is decisive.
`unfortunately` is not — it appears in acknowledgements, delays and rejections
alike. A message that only trips weak rules becomes `needs_review` and lands on
your list rather than being guessed at.

If two **decisive** rules disagree in polarity — one says interview, one says
rejected — it does not pick a winner by precedence. It escalates. A message that
contradicts itself is exactly the message a human should read.

### The conditional guard

The single most important fix came from a real Sault Area Hospital
acknowledgement:

> your application has been received. You will be contacted by the Recruitment
> Team **if you are selected for an interview**.

That is not an interview invitation, and reading it as one would fire the one
alert you actually care about, for nothing. Crying wolf there is worse than
missing an acknowledgement, because it teaches you to ignore the notification
that matters.

So a decisive phrase inside a conditional is not decisive. Only the text
**before** the match in the same sentence is checked, which keeps "we'd like to
schedule a call **if you're available**" — a genuine invitation with a trailing
conditional — working. That change took the self-test from 10/12 to **12/12**.

### The asymmetry you should know about

The archive holds roughly **ten real rejections** and **zero genuine interview
invitations**. Every rejection rule is tested against real mail. The interview
rules are tested against constructed examples and the one near-miss above.

The branch that matters most is the branch with the least evidence behind it.
That is why the default is *escalate when unsure*, and why `track.py` has the
**CLOSED, BUT REACHED YOU FIRST** section — if this tool ever reads an interview
as a rejection, the role stays visible instead of vanishing into the closed pile.

### What it will and will not send

Replies are **templates, not generated prose** — same rule as Phase 3, with less
margin, because an email cannot be un-sent.

There are exactly two templates: `recruiter_interest` and `assessment`. There is
none for `interview` (you should write that yourself — it is the whole goal),
none for `offer`, none for `rejected`, none for `acknowledged`. It also never
replies to a no-reply sender, detected by address *and* by body text
("this is an automated message", "unmonitored mailbox").

An assessment gets both a reply **and** an escalation. The template commits you
to completing the work before the deadline, and making a commitment on your
behalf without telling you is precisely the over-eagerness this pipeline exists
to avoid.

### Gmail access — the second thing only you can do

`--scan` and `--send` need OAuth credentials at
`~/.config/luminos/jobhunt-gmail.json`. The MCP Gmail connector cannot be used:
it is session-scoped, and the 03:30 timer has no session.

Scopes: **`gmail.readonly` + `gmail.compose`**. Not `gmail.send` — compose can
only write drafts, so the worst case of a bug is a draft you delete.

In Google Cloud Console: new project → enable Gmail API → OAuth consent screen
(External) → **add yourself as a Test user**, which is the step everyone misses
and which makes login fail with a wall of text about unverified apps → Create
credentials → OAuth client ID → Desktop app → download the JSON to that path.

Until that file exists, `--scan` exits with an explanation and `--send` refuses.
`--from-json` works today and is how the whole classifier was tested.

---

## Phase 4 — filling the form

`apply.py` reads the real application form, works out which questions it can
answer honestly, and refuses the rest. The submitting half is **not built yet** —
right now it reads and reports, and writes nothing anywhere.

```bash
./apply.py --check              # every shortlisted role: ready or blocked
./apply.py --check --why        # ...and every question that blocks one
./apply.py --form <id>          # one role, field by field, with the answers
./apply.py --check --fresh      # ignore the cached copies
```

### It reads an API, not a screen

Both reachable ATSs hand over the whole form as JSON, unauthenticated:

| | |
|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?questions=true` |
| Ashby | `POST jobs.ashbyhq.com/api/non-user-graphql` (`ApiJobPosting`) |

Both include the labels, the option lists and — the part that matters — which
fields are **required**. So "can this application be completed truthfully" is
answerable for every role in one pass, with no browser and nothing submitted.
Checking first and submitting second is not fussiness: an application cannot be
withdrawn and re-sent, so the only safe moment to find an unanswerable question
is before the form is open.

Ashby's GraphQL has introspection disabled, but its **validation errors name the
types**, so the query was derived from the server one error at a time rather than
guessed. Forms are cached for a day (`~/.cache/luminos/jobhunt-forms`) — with the
cache a full `--check` takes 12 seconds instead of several minutes, and it does
not re-ask two companies' APIs sixty times every time a regex changes.

### The one rule

**A field is answered from an explicit mapping or it is not answered.** No
inference, no model, no "probably". Same rule as Phase 3, and harder here,
because a resume bullet is a claim about the past while a screening answer is
one the employer acts on immediately.

That rule earned its keep on the first real run. Three of *this tool's own rules*
filled in answers that were wrong:

- a rule matching the word `degree` typed **"Bachelor's Degree"** into
  *"What was your bachelor's university degree **result**?"* — a question asking
  for a grade
- the same rule fired on *"...since you graduated your first undergraduate
  degree, **how many companies** have you worked for?"*, where the options were
  0 to 10+
- the generic file-upload rule swallowed Greenhouse's separate **cover letter**
  upload, so the resume would have gone up twice, once labelled as a cover letter

None of those was a missing mapping. Each was the tool inventing an answer
because a keyword happened to appear, and each filled the field silently. The
lesson was not "add three exceptions" — it is that a rule which can fire on a
question it has not understood must be narrow.

A useful sign the guard works: Canonical's country list has 314 entries and
splits Canada by province, so asking for "Canada" matched thirteen options.
`pick_option()` refused rather than picking Alberta.

### Blocked is four different things

`--check` counts them apart, because they need completely different responses.

| | means |
|---|---|
| **gap** | the answer exists, it is just not written down — five lines of `profile.yaml` |
| **essay** | an open question about his experience. No honest automatic answer, ever |
| **consent** | a legal agreement, or a protected attribute. His decision, nobody else's |
| **rule** | a structured question with no mapping yet. Real work, and finishable |

Where the 86 shortlisted roles stand today:

```
  0 ready to submit now
  7 ready the moment profile.yaml is filled in
  6 blocked on questions this tool cannot map yet
 39 ask required open questions
  6 need a legal agreement accepted
  6 unreadable (posting withdrawn or renamed)
 22 have no application form found yet
```

**Say the uncomfortable part plainly: "auto-submit everything" is not reachable.**
Forty-five of these roles ask something only Shawn can answer. Canonical alone is
about two dozen of them and asks how he did in high-school mathematics, what his
degree result was, and his nationality. No amount of engineering makes those
automatic, and a tool that answered them anyway would be filling applications
with fiction under his name.

### Two things it will never do

**It never accepts a legal agreement.** Canonical, GitLab, 1Password and
Tailscale all put one mid-form — arbitration agreements, background-check
consent, "I certify that the information in this application is true". Ticking
one is agreeing to a contract on his behalf, and an arbitration clause signs away
the right to sue. Those are blocked by rule, not by omission.

**It never infers nationality or citizenship.** Being authorised to work
somewhere says nothing about it — a permanent resident is authorised and is not a
citizen. It is not in `profile.yaml` on purpose.

### Country is not one question

`Do you require immigration sponsorship to work for Affirm **in the United
States**?` and `...**in Canada**?` are different questions, and Affirm asks both
on the same form. The profile's sponsorship field is about Canada. Answering the
US question from it would be a false statement on a legal screening question, so
every authorisation rule works out which country is being asked about first and
refuses when the country is one the profile says nothing about.

`requires_sponsorship_canada` stays deliberately unset, and this is the reason it
has no default: being work-authorised **now** does not answer whether sponsorship
is needed **later**, which is exactly why Greenhouse asks the two separately.

### What would unblock the most, in order

1. `contact.phone` — 14 roles. Most ATSs mark it required, so an empty phone is
   not a skipped field, it is a form that cannot be submitted
2. `requires_sponsorship_canada` — 15 roles
3. `contact.linkedin` — 15 roles
4. `salary_expectation_cad` — 6 roles
5. `over_18`, `willing_to_travel_occasionally` — new fields the forms ask for
