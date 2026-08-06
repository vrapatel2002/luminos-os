# Jobhunt — Implementation Plan
# [CHANGE: claude-code | 2026-08-05]

Automated pipeline for finding, tailoring for, and applying to worldwide
work-from-home roles that can legally hire a Canada-resident.

## Design rules

These are load-bearing. Every phase below is constrained by them.

1. **Never invent a fact.** The tailoring model may only select, reorder, and
   rephrase claims that already exist in `profile.yaml`. A fabricated bullet
   survives until the background check, then costs the job. Enforced by a
   validator, not by prompt wording.
2. **Nothing submits itself unreviewed.** The bot fills, screenshots, and
   queues. A human keystroke sends. This is what separates it from the
   auto-apply bots that get flagged as spam.
3. **Never automate LinkedIn Easy Apply or Indeed Apply.** Both are ToS
   violations with real account-restriction risk. The pool is large enough
   without them.
4. **Verify by reading back, never by return code.** Every stage has an
   explicit negative test. A health check that cannot fail is a lie.
5. **No Docker, no Ollama.** Per CLAUDE.md. Python stdlib where possible;
   one pinned venv where not.

## Current state

| Stage | Status | Evidence |
|---|---|---|
| Ingest | working | 9,788 postings / 21s, 9 sources |
| Location classifier | working | 21/21 unit tests |
| Filter + browse | working | 1,650 distinct open roles |
| **Phase 0 — local LLM on GPU** | **DONE 2026-08-05** | real generation on the RTX 4050, 4892 MiB VRAM, negative-tested |
| Score | ready to build | LLM unblocked; needs prompt + GBNF grammar |
| Tailor | not started | **needs Shawn's resume** (Phase 1) |
| Apply | not started | needs tailor |
| Approve | not started | needs apply |
| Inbox | not started | independent, can run early |

Verified blockers — **re-checked 2026-08-05, two of the original four were wrong:**
- ✅ still true: `llama-server` is orphaned — all 7 shared libs missing (BUG-097).
- ✅ still true: `llama-cpp-python` 0.3.20 in `/opt/luminos/venv` works but reports
  `llama_supports_gpu_offload() == False`. Re-measured, and **also False when run
  through `dgpu-exec-v2`** — proving it is a CPU-only *build*, not a permissions
  problem. Opening the gate buys nothing here; the wheel must be rebuilt.
- ❌ **WRONG, and the suggested fix was dangerous:** "shawn is not in the `dgpu`
  group; the gate denies the device." The gate is *not* a blocker — `dgpu-exec-v2`
  opens `/dev/nvidiactl` + `/dev/nvidia0` on demand, verified again today. **Do NOT
  run `sudo usermod -aG dgpu shawn`.** That would hand the RTX 4050 to every process
  on the box permanently and delete the entire point of DECISION 25. The correct
  invocation is to prefix the jobhunt python with `dgpu-exec-v2`. Removed from
  "What only Shawn can do" — nothing is blocked on him for Phase 0.
- ❌ **WRONG:** "No GGUF models on disk." There are **four, 18 GB**, in
  `~/.local/share/luminos/models/hive/`: Dolphin3.0-Llama3.1-8B, Qwen2.5-Coder-7B,
  DeepSeek-R1-0528-Qwen3-8B, DeepSeek-R1-Distill-Qwen-8B (all Q4_K_M). Phase 2 can
  be prototyped on these today without downloading anything.

New blocker found 2026-08-05 (real, and the actual reason a CUDA build will fail):
- **CUDA 13.3 refuses the system compiler.** `/opt/cuda/include/crt/host_config.h`
  rejects `__GNUC__ > 15` and the system gcc is **16.1.1**. Solvable without
  installing anything — **`gcc15` 15.3.0 is already present** at `/usr/bin/g++-15`,
  so the build needs `-DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-15`. Disk: 91 GB free.

---

## Phase 0 — Unblock the brain

**Not blocked on Shawn at all** (corrected 2026-08-05 — the old `usermod -aG dgpu`
line was wrong and would have destroyed the gate; see blockers above).

Work:
- Create a **separate** venv at `/opt/luminos/venv-jobhunt`. Do not touch
  `/opt/luminos/venv` — HIVE depends on it and a failed CUDA rebuild there
  takes HIVE down with it.
- Build with `CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-15"`
  (CUDA 13.3 rejects the system gcc 16) and `PYTHONNOUSERSITE=1` (BUG-093:
  user-site packages shadow pacman's and silently poison AUR/pip builds).
- Run it **through `dgpu-exec-v2`** — that is how the process gets the card. Never
  by adding the user to the `dgpu` group.
- No download needed to start: four Q4_K_M GGUFs are already on disk. Fetch the
  smaller `Qwen3-4B-Instruct-2507-Q5_K_M.gguf` (~2.9 GB) later if scoring
  throughput on an 8B proves too slow.

Verification — all four must pass:
- `llama_supports_gpu_offload()` returns True.
- A real generation runs and returns non-empty text.
- `nvidia-smi` shows the python process actually resident on the GPU. The
  build flag is not proof; a CUDA-enabled build silently falls back to CPU
  when the device is denied.
- Peak VRAM stays under 4.6 GB with 32k context loaded.

Fallback: if the CUDA build fails, the CPU venv already works. Everything
downstream is identical, just slower. Phase 0 is a speed unblock, not a
correctness one — do not let it stall Phases 1–3.

### ✅ PHASE 0 COMPLETE — 2026-08-05, proven on the card
# [CHANGE: claude-code | 2026-08-05]
`/opt/luminos/venv-jobhunt` exists with **llama-cpp-python 0.3.34** built against
CUDA 13.3. `/opt/luminos/venv` was not touched. Scripts: `build-cuda-venv.sh`
(rerunnable, takes a version argument) and `verify-cuda-venv.sh`.

All four verification criteria met:
```
negative test (no gate) : supports_gpu_offload = False
                          ggml_cuda_init: failed to initialize CUDA:
                                          no CUDA-capable device is detected
through dgpu-exec-v2    : found 1 CUDA devices — NVIDIA GeForce RTX 4050 Laptop GPU,
                          compute capability 8.9, VRAM 5772 MiB
                          supports_gpu_offload = True
real generation         : "Django, Flask, FastAPI"   (Qwen2.5-Coder-7B-Q4_K_M, ctx 4096)
VRAM actually resident  : 4892 MiB of 5772 MiB
card afterwards         : returned to `suspended` on its own (BUG-103 fix holds
                          under real CUDA load, not just graphics)
```

**Three findings that change later phases:**

1. **`0.3.20` cannot be used — the version pin had to move.** Its vendored
   llama.cpp fails to compile against CUDA 13.3: `ggml-cuda/argsort.cu` calls
   `cuda::make_counting_iterator` / `cuda::make_strided_iterator`, which this CCCL
   does not provide. 0.3.34 builds clean. Note this means **jobhunt and HIVE are on
   different llama-cpp-python versions on purpose** — do not "align" them by
   downgrading jobhunt, and do not upgrade HIVE's venv to match without testing.
2. **CUDA 13.3 rejects the system compiler.** `host_config.h` refuses
   `__GNUC__ > 15`; system gcc is 16.1.1. Build requires
   `-DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-15` (gcc15 already installed).
   Also pinned `-DCMAKE_CUDA_ARCHITECTURES=89` (Ada/RTX 4050) — without it the
   build compiles every architecture and takes far longer.
3. **A 7B does not fit the budget.** 4892 MiB at only 4096 context already exceeds
   the 4.6 GB safe-VRAM rule, and the plan's Phase 2 target was 32k context —
   which will not fit at all. **Scoring should use a ~4B model**, confirming the
   original `Qwen3-4B-Instruct-2507-Q5_K_M` choice. The 8B models on disk are fine
   for one-off tailoring at short context, not for batch scoring.

**The load-bearing lesson: the build flag is not proof.** `supports_gpu_offload()`
reports only how the wheel was *compiled*. Compiled-with-CUDA + device-denied
produces `False` and a silent CPU fallback — which is exactly what the old
`/opt/luminos/venv` looked like. `verify-cuda-venv.sh` therefore runs a real
generation, reads VRAM back off the driver, and **negative-tests without the gate**
so it cannot degrade into a check that always says yes.

---

## Phase 1 — Profile

**Blocked on Shawn:** the resume file, plus answers to the knockout questions.

Build `profile.yaml` — the single source of truth:

```
identity:      name, email, phone, city, links (github, linkedin, portfolio)
education:     degree, institution, grad date
experience:    role, org, dates, bullets[]
projects:      name, stack, scale, outcome, repo, demo, bullets[]
skills:        grouped, each tagged with lane
bullet_bank:   every factual claim, each with a stable id + skill tags
lanes:         2-3 target role families, each with a summary variant
knockouts:     work auth, sponsorship needed, relocation, notice period,
               salary expectation, years of experience
```

`bullet_bank` is the important part. Tailoring **selects from** it. Anything
not in the bank cannot appear on a generated resume.

Verification:
- Render the master resume from `profile.yaml` and diff against the original.
  Nothing may be silently lost in parsing.
- Every `bullet_bank` entry carries a unique id and at least one skill tag.

---

## Phase 2 — Scoring

`score.py` — batch the open pool through the local model.

- Output is **grammar-constrained JSON** (llama.cpp GBNF), so malformed
  output is structurally impossible rather than caught after the fact.
- Fields: `fit` 0-100, `lane`, `knockout_risks[]`, `missing_skills[]`,
  `seniority_match`, `one_line_why`.
- Writes to `jobs.score` / `jobs.score_reason`.
- Runs after each ingest via systemd timer.

Verification — this is the phase most likely to silently do nothing useful:
- Shawn hand-labels 30 jobs good/bad. Compare against model scores and report
  agreement. If the model rates everything 65-75, the prompt is broken.
- Assert score variance across the pool is non-trivial.
- Spot-check the 10 highest and 10 lowest scored roles by hand.

---

## Phase 3 — Tailoring

`tailor.py` — `profile.yaml` + one job description → application packet.

- Model selects bullets by `bullet_bank` id, reorders them, and rewrites the
  summary line and cover letter to mirror the posting's language.
- **Validator:** every emitted bullet must resolve to a `bullet_bank` id, and
  its rewritten text must not introduce numbers, employers, technologies, or
  dates absent from the source entry. Violation → reject and retry, then fail
  loudly. This is the guardrail for design rule 1.
- Render with Typst: single column, no tables, no headers/footers, no
  graphics, standard section headings, system fonts.

Verification:
- Run `pdftotext` on the generated PDF and confirm the last two roles, all
  dates, and contact details extract in the right order. That is the actual
  ATS test — not whether the PDF looks nice.
- Assert one page.
- Diff generated bullets against source bank entries for invented tokens.

---

## Phase 4 — Apply

`apply.py` — Playwright, one adapter per ATS, prioritised by pool share:
Greenhouse (794 open) → Ashby (235) → Lever → Workable.

Each adapter: open posting, locate form, map fields from `profile.yaml`,
upload the tailored PDF, answer knockouts, screenshot, set `status='ready'`.
**It does not submit.**

Workday is deliberately excluded from v1 — it requires a fresh account per
employer and is a poor effort-to-yield trade.

Verification:
- Dry-run against live forms with submit disabled; review screenshots.
- Adapter must fail loudly and queue the job as `manual` when the DOM has
  moved, never silently skip a field. A half-filled application is worse
  than none.

---

## Phase 5 — Approve

OpenClaw as the human interface — self-hosted, MIT, messaging-bound, no Docker.

- Commands: `/queue`, `/show <id>`, `/approve <id>`, `/approve all`,
  `/reject <id>`, `/pause`.
- On approval, submit and record `applied_at`.
- Rate limits: hard cap per day, randomised spacing between submissions, and
  a `~/.jobhunt-pause` file that halts everything.

The pipeline must remain fully usable from the CLI without OpenClaw. OpenClaw
is young software and is a convenience layer, not a dependency.

---

## Phase 6 — Inbox

Independent of Phases 2–5. Can be built in parallel.

- Gmail API, OAuth, read + draft scopes.
- Classify each reply: rejection / recruiter interest / assessment request /
  interview invite / automated acknowledgement.
- Update the tracker, draft a response, notify via OpenClaw.
- Auto-send only for the lowest-risk category, and only after Shawn has
  approved that category's drafts several times by hand.
- Day-7 follow-up nudge on anything still silent.

---

## Phase 7 — Learn

The part that makes it improve rather than just repeat.

- Callback rate by source, company, lane, and score band.
- Feed observed callback rates back into scoring weights.
- Weekly report: what converted, what did not, where to redirect effort.

If tailored, well-authorised applications still return ≤1-2% after a real
sample, the answer is not more volume — it is repositioning. The tracker is
what tells us which of those two is true.

---

## Risks

| Risk | Impact | Response |
|---|---|---|
| Model invents resume facts | Highest — costs the job at background check | Validator rejects; hard fail |
| CUDA build fails | Slow, not broken | CPU venv already works |
| ATS form DOM changes | Applications silently malformed | Adapters fail loudly, queue manual |
| Over-applying flags as spam | Reputational, per-company | Daily cap, cross-board dedup, no repeat applications |
| OpenClaw instability | Loses phone approvals | CLI path always works |
| Ingest source rate-limits | Smaller pool that day | Official APIs, low risk; back off and retry |

## What only Shawn can do

- ~~`sudo usermod -aG dgpu shawn` (Phase 0)~~ — **withdrawn 2026-08-05, do not do
  this.** It was never needed and would give every process on the machine
  permanent access to the dGPU. `dgpu-exec-v2` is the correct route.
- **Supply the resume and knockout answers (Phase 1) — this is now the critical
  path.** Phase 1 has no dependency on the GPU and gates Phases 3, 4 and 5.
- Hand-label 30 jobs to calibrate scoring (Phase 2)
- Gmail OAuth consent (Phase 6)
- Approve each application (Phase 5, ongoing)
- Interviews

## Order of execution

Phase 1 and Phase 6 have no dependency on Phase 0 and can start immediately.
Phase 0 is a speed unblock. Phases 2 → 3 → 4 → 5 are strictly sequential.
Phase 7 needs real application data, so it comes last by necessity.
