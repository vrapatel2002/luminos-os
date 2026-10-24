# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-24 14:15 — Response 1 (luminos-ram app reaper built, tested, installed in LOG mode — DECISION 160) (cloud session linked to the G14)

Previous handoff (DECISION 159 shared MCP servers) is in git: `git show 9bafc74c:HANDOFF.md`.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — G14 desktop/AI stack + the separate media server — fixing
what Shawn reports, and never leaving a change undocumented.

## Aim right now — stop wasting RAM: apps that are not live leave RAM (docs/prompts/luminos-ram-reaper.md)
Built and installed. Running in **reap_mode = log** (dry run). Waiting on Shawn: read a day of
`~/.local/state/luminos/ram-reaper.log`, then switch to `act`.

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
Log mode is collecting. At 14:05 it lists: 2 orphaned Wine prefixes (pids 69xxx / 85xxx), /tmp/mw4.core 386 MB,
proton.VPN.service 85 MB (kept until 60 idle min since daemon start). /tmp/mw4-syswine.log (351 MB) will appear once the
orphaned explorer.exe that holds it is gone.

## Next steps (ordered)
1. Shawn: read `~/.local/state/luminos/ram-reaper.log` (or `luminos-mem-report`) after a day; add anything to
   `keep =` that must never go; then set `reap_mode = act` and `systemctl --user reload luminos-ram-reaper`.
2. Shawn's answer (asked once): also `systemctl disable proton.VPN.service` at boot? If yes → /etc change → AGENTS §9 +
   DECISIONS. (D-Bus activation file exists, so the Proton app would still start it on demand.)
3. Real-Chrome check: open Chrome, close the last window → `pgrep -c chrome` must reach 0 (not run — would open a
   browser on Shawn's screen).
4. BUG-214: feed the root LIRS half with the agent's window list, or move it user-side.
5. Optional: event-driven death detection (pidfds) would cut the agent's 0.8 % of a core further.
6. `main` ahead of origin — push is Shawn's call.

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
Changed: cmd/luminos-ram/main.go, scripts/jobhunt/{systemd/openclaw-gateway.service,install-services.sh,status.py},
scripts/luminos-mem-report, LUMINOS_DECISIONS.md, docs/BUGS.md, docs/LUMINOS_RAM_ARCHITECTURE.md, AGENTS.md,
LUMINOS_STATUS.md, docs/CODE_REFERENCE.md, HANDOFF.md.
Outside repo: /usr/local/bin/luminos-ram (+backup), ~/.config/luminos-ram-reaper.conf, ~/.config/systemd/user/
{luminos-ram-reaper.service, openclaw-gateway-proxy.*} links, ~/.config/google-chrome/Local State (+backup).
No /etc change.
