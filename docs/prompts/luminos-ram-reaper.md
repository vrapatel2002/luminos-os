# Prompt — luminos-ram "if it's not live, it's not in RAM" (app reaper)
<!-- [CHANGE: claude-code | 2026-10-24] written for Shawn; paste into a Claude Code session in ~/luminos-os -->

Paste everything in the block below into a fresh Claude Code session (Max, Opus). It is self-contained.

```
You are working on Luminos OS (~/luminos-os) on the ASUS ROG G14 GA403UU (16 GB soldered RAM, zram 8G +
/swapfile.luminos, Radeon 780M iGPU takes RAM, RTX 4050 6 GB).

MANDATORY first: read AGENTS.md completely and HANDOFF.md, follow both STRICTLY (Response counter, HANDOFF
overwrite, REPLY TO MANAGEMENT block, [CHANGE: claude-code | date] tags, `luminos-brain safe` before any
python/package action, never `git add -A`, never broad `pkill -f`). Then read docs/LUMINOS_RAM_ARCHITECTURE.md,
cmd/luminos-ram/main.go (whole file) and scripts/luminos-mem-report.
Shawn has EXPLICITLY authorised changes to cmd/luminos-ram for this task (AGENTS: cmd/ only when instructed).

## The goal, in Shawn's words
"Make sure that apps close completely and processes like Chrome and MW4 and VPN and openclaw and more things are
out of RAM if they are not being used. We are not using the VPN, so out of RAM; same with openclaw; Wine too, no
matter what it is. If the app/software/code is not live and working, remove it from RAM. Stop wasting RAM. Do not
keep leftovers in RAM: when a process/app dies, get out, remove everything related to it."

## What was measured on 2026-10-24 (zram held 5.7 GB of data in 2.0 GB of RAM) — the cases you must cover
1. Duplicate MCP servers per Claude client (~1.35 GB) — ALREADY FIXED by DECISION 159 (scripts/luminos-mcp-share:
   one shared copy, idle-stops itself). Do NOT reap the brokers `luminos-mcp-share-*` user units; they manage
   their own idle. Do reap a mempalace / code-review-graph / host-shell process whose Claude client is gone.
2. Orphaned Wine from MW4 runs: services.exe, plugplay.exe, svchost.exe, rpcss.exe, explorer.exe /desktop with
   PPID 1 and NO wineserver alive, started two days earlier. Two prefixes.
3. /tmp is tmpfs = RAM: /tmp/mw4-syswine.log 352 MB + /tmp/mw4.core 224 MB left by debugging.
4. proton.vpn.daemon (system unit proton.VPN.service, enabled) running with no VPN connected (~85 MB swapped).
5. openclaw-gateway (user-manager child, PPID = user systemd) idle (~86 MB swapped).
6. Three Claude Desktop instances open at once (Max ~/.config/Claude, GLM ~/.config/Claude-glm, Local
   ~/.config/Claude-local) — 2.3 GB RSS + 1 GB swapped.
7. Chrome / Electron helpers (crashpad handlers, renderers, GPU process) that can outlive their window.

## Design rules (non-negotiable)
- "Live" is MEASURED, never guessed from names. A process group is live if ANY of: it has a visible window
  (KWin D-Bus, already wired in main.go), it is the focused app or was in the last N minutes, active audio
  (hasActiveAudio), an ESTABLISHED network connection carrying traffic, an open listen socket that has had a
  client in the last N minutes, CPU > 2 % or disk I/O > 1 MB/s averaged over the window, a GPU client
  (/proc/<pid>/fd → /dev/nvidia* or render node with recent activity), or it is on the keep-list.
- Group by APP, not by process: use the systemd unit / cgroup (KDE launches apps in app-*.scope / app-*.service
  under the user manager; services are their own units). Plus: Wine = everything sharing one WINEPREFIX
  (/proc/<pid>/environ) or one wineserver; Electron/Chrome = the process tree under the main browser pid.
- Gradient, not modes (Shawn's standing rule, same as power): the idle time an app is allowed before it is reaped
  shrinks smoothly as MemAvailable falls, e.g. idle_allowed = lerp(60 min @ ≥ 6 GB available → 2 min @ ≤ 1 GB).
  No "aggressive mode" switch.
- Reaping an app = stop its UNIT (systemctl [--user] stop) when it has one, so every child goes with it; else
  SIGTERM the whole group, wait 5 s, SIGKILL survivors. Then verify by pid that nothing of that group is left,
  and log: app, reason ("no window 31 min, 0 % CPU, no net"), pids, PSS+swap freed (MB).
- Leftovers after death: when an app's main process exits, within 10 s reap everything that belonged to it —
  orphans (PPID 1) still in its cgroup or WINEPREFIX, crashpad/zygote helpers of a dead browser, `wineserver -k`
  (with that WINEPREFIX) for a prefix whose last real .exe is gone, MCP server copies whose client is gone.
- tmpfs: files in /tmp and /dev/shm owned by shawn, > 50 MB, not open by any process (scan /proc/*/fd), not
  modified for > 30 min → delete, log name + size. Core dumps must not land in /tmp (route MW4/Wine scripts to
  ~/.local/state/... and leave cores to systemd-coredump with its own size cap).
- Services Shawn does not use: proton.VPN.service → stop it when no VPN tunnel is up (no tun*/wg*/proton*
  interface, Proton GUI not open); ask Shawn ONCE whether to also `disable` it at boot (system unit = /etc
  change → AGENTS §9 + DECISIONS). openclaw-gateway → stop its user unit after N idle minutes with no client
  connection; prefer socket activation so it comes back by itself on first use (check how it is installed first).
- Claude Desktop: NEVER reap the Max app (~/.config/Claude) — it hosts the Cowork VM (qemu) and remote/bridge
  sessions even with no window. The extra profiles (GLM, Local, any --user-data-dir other than ~/.config/Claude)
  are reaped like any app: no window + idle past the gradient threshold → stop. Never kill the qemu Cowork VM
  directly.
- Chrome: closing the last window must end Chrome. Check chrome://settings "Continue running background apps"
  equivalent in Preferences (background_mode.enabled) and turn it off; then the reaper handles stragglers. Keep
  the existing tab-discard/CDP logic and isProtectedMedia untouched.
- Protected, never touched: everything in isProtectedAlways (luminos-*, kwin, plasmashell, pipewire, systemd,
  dbus, Xwayland) plus sshd, tailscaled, NetworkManager, sddm, the earlyoom process, terminals/shells with a
  foreground job (tmux/konsole/bash children doing work), the coder gateway and its llama-server (own 15 min idle,
  DECISION 157), HIVE (hive-idle-watchdog owns it), anything the offload pid points to, active downloads
  (hasActiveDownload), Steam while a game runs, and a user keep-list in the daemon config file.
- Dry-run first: a `reap_mode = "log"` config value (default for the first install) logs exactly what WOULD be
  reaped; switch to "act" only after Shawn has seen a day of the log. A `/reap` request on /run/luminos/ram.sock
  returns the current candidates with reasons and sizes (so the dock/CLI can show them).
- Keep the existing LIRS/HotSet/madvise algorithm intact — this is an ADDITION (new file cmd/luminos-ram/reap.go
  + small hooks), not a rewrite.

## Tests (Shawn's rule: prove it end-to-end, do not assert from config)
- Go unit tests (fake /proc trees in testdata): live/idle decision for each signal, gradient threshold maths,
  grouping by cgroup and by WINEPREFIX, protected list, keep-list, tmpfs candidate rules (open file is never
  deleted). Include negative tests for every protected class.
- Integration on the real machine (run long steps via `systemd-run --user`, poll results — the host-shell bridge
  cuts calls at 60 s):
  a) fake app: `systemd-run --user --scope` a parent with 3 children + 1 double-forked orphan; kill the parent →
     all 4 gone within 10 s, log line present.
  b) fake Wine leftover: run a tiny .exe with a throwaway WINEPREFIX under /tmp, kill wineserver → services.exe
     & co. reaped, prefix's processes = 0.
  c) idle app: open a window-less idle process tree → reaped after the gradient threshold (use a test override
     for minutes), NOT reaped while it plays audio / holds an ESTABLISHED connection / uses CPU.
  d) tmpfs: 60 MB file in /tmp held open by `tail -f` → kept; closed + aged → deleted.
  e) protected: kwin/plasmashell/pipewire/sshd/Max Claude app/coder gateway survive a forced reap pass.
  f) Before/after numbers from scripts/luminos-mem-report (PSS + zram) on the real desktop, in the result doc.
- `cd cmd/luminos-ram && go test ./...` all green; rebuild/install exactly as AGENTS.md documents for
  luminos-ram (backup the old binary to ~/.luminos-backups first; the daemon sleeps 30 s before listening).

## Docs + finish
DECISION (next number) in LUMINOS_DECISIONS.md with the measured before/after, docs/LUMINOS_RAM_ARCHITECTURE.md
section "Reaper", AGENTS.md install table row, LUMINOS_STATUS.md row, docs/BUGS.md for anything found, HANDOFF.md
overwrite, MemPalace drawer (read it back). Commit with named paths. Push is Shawn's call.

Done when:
- [ ] Each of the 7 measured cases above is covered by code AND a passing test
- [ ] One day of dry-run log reviewed with Shawn, then "act" mode on
- [ ] Before/after RAM numbers recorded
- [ ] Docs + commit done
```
