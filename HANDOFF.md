# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-24 10:55 — Response 25 (DECISION 159 shared MCP servers built + tested + switched; luminos-ram reaper prompt written) (Max-window chat "Biggest local LLM model")

Previous handoff (VisionQuest DV P5 sweep / MW4 / GLM window) is in git: `git show c5ac3e61:HANDOFF.md`. Nothing from it
was touched; its open items are listed under "Still open from before".

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — G14 desktop/AI stack + the separate media server — fixing
what Shawn reports, and never leaving a change undocumented.

## Aim right now — stop wasting RAM (DECISION 159 done; luminos-ram reaper = prompt only)
Shawn: "make a detailed prompt for luminos-ram … apps close completely … Chrome, MW4, VPN, openclaw, Wine … if it is not
live working remove it from RAM … no leftovers … and for you to do: the same tool servers started over and over."
Measured (Response 24): zram 5.7 GB → 2.0 GB; biggest cause 6 × mempalace + 6 × code-review-graph (~1.35 GB swapped).

## Why / motivation
16 GB soldered RAM; the local Qwen3.8 reviewer needs 6.3 GB pinned and the desktop was already in swap.

## State — what is DONE
- **DECISION 159**: `scripts/luminos-mcp-share` (broker + socat stub). Configs switched (backups `*.bak-mcpshare-20261024`):
  Max `~/.config/Claude/claude_desktop_config.json`, `~/.config/Claude-glm-3p/…`, `~/.config/Claude-local-3p/…`,
  `~/.claude/settings.json`, `~/.config/Antigravity/User/mcp.json`. host-shell deliberately NOT shared.
- `tests/mcp-share/test_share.py` 17/17 (log in tests/mcp-share/RESULTS.txt). Real "Claude (Local Qwen)" app: 2 socat
  stubs, no private copies; closed → stubs gone.
- `scripts/luminos-verify` unwraps the wrapper (`unwrap_shared`); installed to /usr/local/bin (backup
  `~/.luminos-backups/luminos-verify.bak-pre-mcpshare-20261024`); `luminos-verify --mcp` PASS, 0 warnings.
- `docs/prompts/luminos-ram-reaper.md` — Shawn's prompt for the app reaper (cases: orphan Wine, /tmp files, proton VPN,
  openclaw, extra Claude apps, Chrome stragglers; dry-run first; gradient threshold; tests). NOT built.
- Earlier this chat: DECISION 157 coder pair (Desktop Code tab end-to-end PASSED), DECISION 158 Baloo off, BUG-212 fixed.

## State — what is IN PROGRESS (and where exactly it was left off)
Shared brokers `luminos-mcp-share-mempalace` and `luminos-mcp-share-crg-luminos-os-0f9dba` running (they stop by
themselves when idle). **The Max app still runs its 2 OLD copies of mempalace + code-review-graph (~560 MB swapped)**
until Shawn restarts it — not done by me because this chat runs through that app.

## Next steps (ordered)
1. Shawn: restart the Max Claude app when convenient → then `luminos-mcp-share status` should show it as a client and
   `pgrep -af mempalace.mcp_server` only the broker's one copy.
2. Shawn: run docs/prompts/luminos-ram-reaper.md in a new session (or tell me to). Quick wins it covers that Shawn may
   want right away: delete /tmp/mw4-syswine.log + /tmp/mw4.core (576 MB), kill orphan Wine (PIDs 69xxx/85xxx, PPID 1).
3. Coder: test pruned models (Qwen3.8-20B-Minitron needs GGUF conversion; Qwen3.6-28B-REAP20) with tests/coder/proof.
4. `main` is ahead of origin — push is Shawn's call.

## Key decisions & constraints so far
- MCP configs must use the wrapper form `luminos-mcp-share client <name> -- <cmd>`; code-review-graph uses `crg@auto`
  (+ `--repo` for GUI clients). Brokers: server idle 600 s, broker idle 120 s (`MCP_SHARE_*_IDLE_S`).
- Coder: one model on the GPU at a time; reviewer Q2_K_XL + mlock; do not use luminos-train-mode (BUG-213).

## Gotchas / dead-ends / things NOT to redo
- host-shell bridge cuts any call at 60 s → long jobs via `systemd-run --user`, poll files. Its shell has NO
  XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS → export them (`/run/user/1000`) before `systemctl --user`.
- device_commit_files does not overwrite and caches by source path → NEW source filename to a NEW path, `mv`, sha256.
- luminos-verify is bash with embedded Python — `py_compile` on it fails falsely; run it instead.
- The broker's own cmdline contains the server command — count real servers excluding `luminos-mcp-share` pids.
- `llama-server … cleaning up before exit` = SIGTERM from outside (was BUG-212), not a crash.

## Still open from before (untouched this turn)
VisionQuest DV P5 sweep verification (BUG-207/DECISION 156 server); MW4 BUG-209 + mw4-cdn-watch; server OpenCL build;
BUG-199 lock-screen repro; spectrum/nvdefer tests needing Shawn; BUG-213; `main` ahead of origin.

## Files touched / relevant files
This turn — New: scripts/luminos-mcp-share, tests/mcp-share/{test_share.py,RESULTS.txt}, docs/prompts/luminos-ram-reaper.md.
Changed: scripts/luminos-verify, LUMINOS_DECISIONS.md (159), LUMINOS_STATUS.md, AGENTS.md (MCP section + file map), HANDOFF.md.
Outside repo: the 5 MCP configs above (+ backups), /usr/local/bin/luminos-verify, ~/.cache/luminos/mcp-share/,
$XDG_RUNTIME_DIR/luminos-mcp-share/. No /etc change.
Earlier (DECISION 157/158): see `git log` a578b3d4..9ea054a6.
