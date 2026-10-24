# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-24 14:35 — Response 2 (reaper switched to ACT mode; proton.VPN.service disabled at boot — DECISION 160) (cloud session linked to the G14)

Previous handoff (DECISION 159 shared MCP servers) is in git: `git show 9bafc74c:HANDOFF.md`.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — G14 desktop/AI stack + the separate media server — fixing
what Shawn reports, and never leaving a change undocumented.

## Aim right now — stop wasting RAM: apps that are not live leave RAM (docs/prompts/luminos-ram-reaper.md)
DONE. Running in **reap_mode = act** since 14:27 (Shawn: "yes to both"). First act: both orphaned MW4 Wine prefixes
reaped, /tmp/mw4.core + /tmp/mw4-syswine.log (737 MB) deleted, /tmp 584 → 85 MB; proton.VPN.service disabled + stopped
(85 MB, on-demand via D-Bus). zram stored 2.07 → 1.21 GB. Reaper report: 0 MB reapable.

## Why / motivation
16 GB soldered RAM; on 2026-10-24 zram held 5.7 GB. Measured leftovers: orphaned MW4 Wine, 737 MB of debug files in
/tmp (tmpfs = RAM), an idle Proton VPN daemon, the openclaw gateway, extra Claude profiles, Chrome stragglers.

## Process / approach being used
Same binary, two halves: root `luminos-ram.service` (unchanged unit) + user `luminos-ram reaper`
(`systemd/user/luminos-ram-reaper.service`). The root half cannot see the session — see DECISION 160 / BUG-214.

## State — what is DONE
- `cmd/luminos-ram/reap.go` (decisions), `reap_agent.go` (I/O), `reap_test.go` (fake /proc, 23 tests) + 3 hooks in
  main.go (`reaper` subcommand, `reap`/`reap_report` socket types, HTTP `/reap`). `go test ./...` 31 green.
- Installed `/usr/local/bin/luminos-ram` (backup `~/.luminos-backups/luminos-ram.bak-pre-reaper-20261024`), root
  daemon restarted; user unit linked + enabled (graphical-session.target), config `~/.config/luminos-ram-reaper.conf`
  (repo copy `config/luminos-ram-reaper.conf`), `reap_mode = log`.
- `tests/ram-reaper/integration.sh` on the real desktop: **19/19** (`RESULTS-integration.txt`, forced pass JSON).
- openclaw: socket-activated (`scripts/jobhunt/systemd/openclaw-gateway-proxy.{socket,service}`, gateway on 18790,
  StopWhenUnneeded, gateway unit disabled; install-services.sh + status.py updated). Tested: cold start 4.2 s, CLI OK,
  idle stop works.
- Chrome `Local State` background_mode.enabled=false (backup in ~/.luminos-backups).
- `scripts/luminos-mem-report` prints a "Reaper" section (reads :9091/reap).
- Docs: DECISION 160, BUG-214/215/216, RAM architecture "Reaper" section, AGENTS §9/§10, STATUS, CODE_REFERENCE.

## State — what is IN PROGRESS (and where exactly it was left off)
Nothing in flight. Watch `~/.local/state/luminos/ram-reaper.log` for REAPED lines on real apps over the next days —
first candidates at today's RAM are app.slice apps idle 60 min (Thunar daemon, Discover tray notifier).
Fixed after the switch: tmpfs report listed files it had just deleted (reap_agent.go `tmpfs()` returns only what is left).

## Next steps (ordered)
1. If the reaper takes something Shawn wanted kept: add it to `keep =` in ~/.config/luminos-ram-reaper.conf and
   `systemctl --user reload luminos-ram-reaper`. Back to dry run: `reap_mode = log`.
2. Real-Chrome check: open Chrome, close the last window → `pgrep -c chrome` must reach 0 (not run — would open a
   browser on Shawn's screen).
3. BUG-214: feed the root LIRS half with the agent's window list, or move it user-side.
4. Optional: event-driven death detection (pidfds) would cut the agent's 0.8 % of a core further.
5. `main` ahead of origin — push is Shawn's call.

## Key decisions & constraints so far
- Never reap: Claude Max app (default profile; hosts Cowork VM + bridge), qemu, session/luminos units, keep-list
  (built-in metatrader/terminal64.exe/metaeditor64.exe/xvfb), offload pid, tty/terminals, Steam while a game runs.
- No window list → no idle reaping. Leftovers are judged on fresh data (full collect every tick while pending).
- act_only + test_idle_s exist for tests only; integration.sh adds and removes them itself.

## Gotchas / dead-ends / things NOT to redo
- host-shell cuts calls at 60 s → long jobs via `systemd-run --user`, poll files; export XDG_RUNTIME_DIR /
  DBUS_SESSION_BUS_ADDRESS (`/run/user/1000`) before `systemctl --user`.
- device_commit_files never overwrites → commit to `.reaper-staging/rN/` then `cp` (that dir is untracked scratch).
- `systemctl --user disable` on a symlinked unit DELETES the symlink (BUG-216).
- Wine refuses a WINEPREFIX whose parent dir isn't yours (`/tmp/x` fails, `/tmp/dir/x` works).
- Wine orphans ignore SIGTERM — SIGKILL is required (BUG-215).
- `kill -0` on root processes = EPERM; check `/proc/<pid>/stat` instead.
- The reaper's own runner must not match `act_only` (integration.sh runs as `ramreaper-itest`).

## Still open from before (untouched this turn)
Max app still runs 2 old MCP copies until restarted (DECISION 159). VisionQuest DV P5 sweep verification (BUG-207/
DECISION 156 server); MW4 BUG-209 + mw4-cdn-watch; server OpenCL build; BUG-199 lock-screen repro; spectrum/nvdefer
tests needing Shawn; BUG-213; coder pruned-model tests.

## Files touched / relevant files
New: cmd/luminos-ram/{reap.go,reap_agent.go,reap_test.go}, systemd/user/luminos-ram-reaper.service,
config/luminos-ram-reaper.conf, tests/ram-reaper/{integration.sh,RESULTS-integration.txt,RESULTS-integration-forced-pass.json,
before-20261024.txt,after-20261024.txt}, scripts/jobhunt/systemd/openclaw-gateway-proxy.{socket,service}.
Changed: cmd/luminos-ram/main.go, tests/ram-reaper/after-act-20261024.txt (new), scripts/jobhunt/{systemd/openclaw-gateway.service,install-services.sh,status.py},
scripts/luminos-mem-report, LUMINOS_DECISIONS.md, docs/BUGS.md, docs/LUMINOS_RAM_ARCHITECTURE.md, AGENTS.md,
LUMINOS_STATUS.md, docs/CODE_REFERENCE.md, HANDOFF.md.
Outside repo: /usr/local/bin/luminos-ram (+backup), ~/.config/luminos-ram-reaper.conf, ~/.config/systemd/user/
{luminos-ram-reaper.service, openclaw-gateway-proxy.*} links, ~/.config/google-chrome/Local State (+backup).
/etc: proton.VPN.service disabled (multi-user.target.wants link removed) — AGENTS §9 row.
