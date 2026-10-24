# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-23 23:40 — VisionQuest E01+E02 converted + verified (BUG-207 fixed); 5 future-proof fixes offered, waiting on Shawn

Previous handoff (VisionQuest DV P5 sweep / MW4 / GLM window) is in git: `git show c5ac3e61:HANDOFF.md`. Nothing from it
was touched this turn; its open items are copied to "Still open from before" below.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — G14 desktop/AI stack + the separate media server — fixing
what Shawn reports, and never leaving a change undocumented.

## Aim right now — luminos-coder (DECISION 157): local Qwen3.6 writer + Qwen3.8 reviewer inside Claude Desktop Chat
Shawn: "3.8 as reviewer … make a system and test it. give a task that is completely out of 3.6 reach and under 3.8 reach …
take care of the power usage … make sure the gpu is running at full power … run these on chat mode on claude desktop app.
do not stop until this things system is completed." No cloud backup.

## Why / motivation
Shawn wants the best coder that runs on the G14 (6 GB RTX 4050, 15.6 GiB RAM), long context, usable from the Claude
Desktop UI, with a smarter model cross-checking. Qwen3.6-35B-A3B (MoE, fast) writes; Qwen3.8-27B (dense, smarter, slow
here) reviews. DeepSeek V4 needs ≥62 GB — not local.

## Process / approach being used
Gateway pattern copied from DECISION 156 (GLM window): a separate Desktop profile in 3P gateway mode → a local
name-translating gateway → llama-server. Measure everything (tests/coder/RESULTS.md) before choosing settings; prove the
reviewer's value with hidden tests (tests/coder/proof/).

## State — what is DONE
- Models in `~/.local/share/luminos/models/coder/` (home is timeshift-excluded): Qwen3.6-35B-A3B-UD-Q3_K_XL (writer),
  Qwen3.8-27B UD-Q2_K_XL (reviewer, chosen) + UD-IQ3_XXS / UD-IQ4_XS / UD-Q3_K_XL / MTP (benchmark leftovers — delete
  the ones not used if disk matters, ~37 GB).
- No llama.cpp rebuild needed: packaged `llama.cpp-cuda b10452` (`/usr/bin/llama-server`) has draft-mtp, router mode and
  the Anthropic `/v1/messages` API. CUDA only through `dgpu-exec-v2` (shawn not in `dgpu`, by design).
- `scripts/luminos-coder-gateway` (+ `systemd/luminos-coder-gateway.service`, installed to `~/.config/systemd/user/`,
  started, NOT enabled at boot — `luminos-claude-local` starts it): :4142 → one llama-server on :8093; sonnet/haiku →
  writer, opus → reviewer; power hooks; 15 min idle unload. Verified: non-stream + SSE stream, powerd on with model,
  powerd masked + dGPU `suspended` after stop.
- `scripts/luminos-coder-review-mcp` (MCP `luminos-coder`: review_start / review_wait / run_python / run_tests) —
  handshake + run_tests verified. pytest lives in `~/.local/share/luminos/coder-venv` (brain-safe override logged: the
  known false-NO banner).
- `scripts/luminos-claude-local` + `~/.local/share/applications/luminos-claude-local.desktop` ("Claude (Local Qwen)",
  repo copy `config/luminos-claude-local.desktop`): profile `~/.config/Claude-local`, 3P cfg `~/.config/Claude-local-3p`,
  token in `~/.config/luminos/coder.env`. `setup` run; app NOT yet opened.
- BUG-212 FIXED: `scripts/hive-idle-watchdog.sh` killed every llama-server; now only `--port 8080`. BUG-213 OPEN
  (train-mode restores fan v5).
- Proof run A so far: Qwen3.6 alone 91/107 hidden tests; Qwen3.6 re-check 95/107.

## State — what is IN PROGRESS (and where exactly it was left off)
1. `coder-proof.service` (user, transient) running `tests/coder/proof/proof.py runA` then `runB`; results append to
   `~/.local/state/luminos/coder/proof-results.jsonl` (ends with PROOF-DONE). Arms: initial, solo2, self, cross.
2. Then: end-to-end in the Claude (Local Qwen) **Chat** tab (open app → send the TASK.md task → writer calls
   review_start/review_wait → check gateway log shows writer→reviewer→writer swaps and tests ran).
3. Docs: DECISION 157 text drafted (append to LUMINOS_DECISIONS.md), STATUS row, RESULTS.md proof table, notes, brain,
   MemPalace drawer, commit (name paths — another chat has uncommitted edits in docs/BUGS.md, config/, server/).

## Next steps (ordered)
1. Read proof results; if cross ≤ self, try reviewer UD-IQ3_XXS (`CODER_REVIEWER_GGUF`) or more thinking budget.
2. Desktop Chat end-to-end (above). 3. Docs + commit. 4. Tell Shawn the trade-offs (reviewer 2.4 t/s, desktop swaps
   while it is loaded).

## Key decisions & constraints so far
- One model on the GPU at a time; switching costs ~20–40 s load. Writer ctx 64K default (128K works but gen halves).
- Reviewer must use `-lm mlock` (else NVMe thrash) and Q2_K_XL (Q3_K_XL OOM-killed at load).
- Thinking budgets: writer 8192, reviewer 1024 (`--reasoning-budget`); unbounded writer thought 16K+ tokens.
- Do not use `luminos-train-mode` for this (fan 100 % pin + stale v5 curve, BUG-213).

## Gotchas / dead-ends / things NOT to redo
- **host-shell bridge cuts any call at 60 s** — run long jobs with `systemd-run --user` and poll files.
- **device_commit_files does not overwrite an existing device file and caches by source path** — commit to a NEW
  path from a NEW source filename, `mv` into place, verify sha256.
- `llama-server` "operator(): cleaning up before exit" = it got SIGTERM (it was BUG-212), not a crash.
- MoE prompt speed needs big `-ub` (512 → 86 t/s, 4096 → 328 t/s).
- `nvidia-smi` via `dgpu-exec-v2` only when the card is already active (BUG-078).

## Still open from before (untouched this turn)
VisionQuest DV P5 sweep verification (BUG-207/DECISION 156 server); MW4 BUG-209 + mw4-cdn-watch; server OpenCL build;
BUG-199 lock-screen repro; spectrum/nvdefer tests needing Shawn; `main` ahead of origin (push is Shawn's call).

## Files touched / relevant files
New: scripts/luminos-coder-gateway, scripts/luminos-coder-review-mcp, scripts/luminos-claude-local,
systemd/luminos-coder-gateway.service, config/luminos-claude-local.desktop, tests/coder/{bench.py,bench-run.sh,
gw-smoke.py,RESULTS.md}, tests/coder/proof/{TASK.md,reference.py,test_hidden.py,proof.py}.
Changed: scripts/hive-idle-watchdog.sh (BUG-212), docs/BUGS.md (212, 213), HANDOFF.md.
Outside repo: ~/.config/systemd/user/luminos-coder-gateway.service, ~/.local/share/applications/luminos-claude-local.desktop,
~/.config/Claude-local{,-3p}, ~/.config/luminos/coder.env, ~/.local/share/luminos/{models/coder,coder-venv},
~/.local/state/luminos/coder/. No /etc change. nvidia-powerd ends masked.
