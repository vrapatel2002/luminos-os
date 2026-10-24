# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-24 02:05 — Response 20 (Max-window chat "Biggest local LLM model")

Previous handoff (VisionQuest DV P5 sweep / MW4 / GLM window) is in git: `git show c5ac3e61:HANDOFF.md`. Nothing from it
was touched; its open items are listed under "Still open from before".

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — G14 desktop/AI stack + the separate media server — fixing
what Shawn reports, and never leaving a change undocumented.

## Aim right now — luminos-coder (DECISION 157): local Qwen3.6 writer + Qwen3.8 reviewer inside Claude Desktop
Shawn: "3.8 as reviewer … make a system and test it. give a task that is completely out of 3.6 reach and under 3.8 reach …
take care of the power usage … make sure the gpu is running at full power … run these on chat mode on claude desktop app.
do not stop until this things system is completed." No cloud backup.

## Why / motivation
Best coder that runs on the G14 (6 GB RTX 4050, 15.6 GiB RAM), long context, usable from the Claude Desktop UI, with a
smarter model cross-checking. DeepSeek V4 needs ≥62 GB — not local.

## Process / approach being used
Gateway pattern from DECISION 156 (GLM window). Measure everything first (tests/coder/RESULTS.md); prove the reviewer's
value with hidden tests (tests/coder/proof/); drive the real Desktop app with ydotool + screenshots for the end-to-end.

## State — what is DONE
- System built and running: `scripts/luminos-coder-gateway` (:4142, user unit `luminos-coder-gateway.service`, env
  CODER_WRITER_CTX=131072), `scripts/luminos-coder-review-mcp` (MCP `luminos-coder`, registered in the Local app config
  AND `~/.claude/settings.json`, backup `.bak-coder-20261024`, luminos-verify --mcp PASS), `scripts/luminos-claude-local`
  + KDE menu "Claude (Local Qwen)". Models in `~/.local/share/luminos/models/coder/`.
- Power: nvidia-powerd unmasked/started on model load, stopped+MASKED after 15 min idle; dGPU `suspended` verified.
- Measured: writer 328 prompt t/s / 18.7 gen at 32K, ~280 / ~9 at 128K; reviewer (Q2_K_XL, mlock) 272 / ~2.4.
- Proof (same start 91/107): re-check 95, self-review 92–93, Qwen3.8 free-form 86 (worse), Qwen3.8 quote-grounded 95.
  Honest verdict in RESULTS.md: the Qwen3.8 that fits this RAM is not a reliably better reviewer.
- Desktop: no Chat tab in 3P (Cowork + Code). Cowork fails while the Max app's Cowork VM holds vsock 51234. **Code tab works
  end-to-end**: Qwen3.6 wrote tests/coder/demo/duration.py + test_duration.py, ran `run_tests` (MCP, 7/7 pass), called
  `review_start` → gateway swapped to Qwen3.8 (02:00:47, ready 19.6 s).
- Gateway fixes found by the Desktop run: SSE `ping` keep-alive (Claude Code drops a stream silent ~90 s; first turn needed
  21 pings / 363 s), HEAD → 200, 74K-token Claude Code requests → 128K ctx.
- BUG-212 FIXED (hive-idle-watchdog killed every llama-server). BUG-213 OPEN (train-mode restores fan v5).
- Docs: DECISION 157 (LUMINOS_DECISIONS.md), STATUS row, AGENTS §3 + §10, BUGS 212/213, tests/coder/RESULTS.md.

- **Desktop end-to-end PASSED** (01:34–02:31, commit a578b3d4): write → run_tests 3/7 → fix → 7/7 → review_start
  (Qwen3.8, 1024 s, "no verified defects" + dead-code note) → review_wait → cleanup → 7/7 → final answer;
  my independent 22-case check 22/22. ydotoold stopped, socket removed.

## State — what is IN PROGRESS (and where exactly it was left off)
Nothing running except the idle gateway (it unloads the writer 15 min after the last request, masks nvidia-powerd and
the dGPU suspends). The "Claude (Local Qwen)" window was left open on the finished session.

## Next steps (ordered)
1. Shawn's call: free RAM for a better reviewer quant (baloo 2 GB; or the 32 GB SPD mod) and re-run tests/coder/proof.
2. Optional: re-launch the Local app once so `API_TIMEOUT_MS=3600000` takes effect (exported by the launcher).
3. `main` is ahead of origin by these commits too — push is Shawn's call.

## Key decisions & constraints so far
- One model on the GPU at a time; a swap costs ~20–40 s. Writer ctx 128K (Claude Code needs ~74K just to start).
- Reviewer must use `-lm mlock` and Q2_K_XL (Q3_K_XL OOM-killed at load; unlocked = NVMe thrash < 1 t/s).
- Thinking budgets: writer 8192, reviewer 2048; `--presence-penalty 1.5` server-wide (per-request value is dropped by
  /v1/messages). Reviewer must quote the task; unverifiable claims are dropped in code.
- Do not use `luminos-train-mode` for this (fan 100 % pin + stale v5 curve, BUG-213).

## Gotchas / dead-ends / things NOT to redo
- host-shell bridge cuts any call at 60 s → long jobs via `systemd-run --user`, poll files.
- device_commit_files does not overwrite an existing device file and caches by source path → commit to a NEW path from a
  NEW source filename, `mv` into place, verify sha256.
- `llama-server … cleaning up before exit` = SIGTERM from outside (was BUG-212), not a crash.
- MoE prompt speed needs big `-ub` (512 → 86 t/s, 4096 → 328 t/s).
- ydotool on KDE: absolute moves clamp to 1,1; use relative moves + KWin-script read-back (`~/.local/state/luminos/coder/clickat.sh X Y click`, logical coords = screenshot px × 0.75).

## Still open from before (untouched this turn)
VisionQuest DV P5 sweep verification (BUG-207/DECISION 156 server); MW4 BUG-209 + mw4-cdn-watch; server OpenCL build;
BUG-199 lock-screen repro; spectrum/nvdefer tests needing Shawn; `main` ahead of origin (push is Shawn's call).

## Files touched / relevant files
New: scripts/luminos-coder-gateway, scripts/luminos-coder-review-mcp, scripts/luminos-claude-local,
systemd/luminos-coder-gateway.service, config/luminos-claude-local.desktop, tests/coder/{bench.py,bench-run.sh,
gw-smoke.py,RESULTS.md}, tests/coder/proof/{TASK.md,reference.py,test_hidden.py,proof.py}, tests/coder/demo/ (model output).
Changed: scripts/hive-idle-watchdog.sh, docs/BUGS.md, LUMINOS_DECISIONS.md, LUMINOS_STATUS.md, AGENTS.md, HANDOFF.md.
Outside repo: ~/.config/systemd/user/luminos-coder-gateway.service, ~/.local/share/applications/luminos-claude-local.desktop,
~/.config/Claude-local{,-3p}, ~/.config/luminos/coder.env, ~/.claude/settings.json (+luminos-coder),
~/.local/share/luminos/{models/coder,coder-venv}, ~/.local/state/luminos/coder/. No /etc change.
