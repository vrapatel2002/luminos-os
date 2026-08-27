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
