# SPEC — continuous power spectrum for luminos-power
# [CHANGE: claude-code | 2026-10-15]

## In Shawn's words
"I want a smart power profile — what we have is very poor, it's in phases: low power, beast mode and more. I want a
continuous spectrum of power which gradually grows — think of a gradient in a colour/image. The switch thing is not
good and thus we have these bugs." (/build, brainstorm with Fable/Opus at max effort, check what the system can do.)

## What gets built (full detail: DESIGN.md — it is the spec of record; this file lists decisions and Done)
1. `cmd/luminos-power/spectrum.go` — pure core `Step()` per DESIGN §3.4/§4 (one continuous dial P = CPU PPT watts).
2. `cmd/luminos-power/spectrum_test.go` — properties P1–P15 + simulated plant (DESIGN §5).
3. `cmd/luminos-power/main.go` — becomes: config, socket, fixed 1 Hz loop, sensors, writers, sd_notify watchdog.
   Deletes beast mode, quiet-idle, thermal zones, emergency, burst, TGP manager, Conductor (conductor.go,
   fan_control.go), input watcher, exec/pre-alloc watcher, PSI sleep bands, every profile/fan-curve/nvidia-smi write
   at startup and in the loop. Keeps every external interface of CURRENT.md §5 (socket request types + reply shapes,
   offload_*, report_power, AC side effects Wi-Fi/KSM/Hz) and adds the dial fields to PowerState (DESIGN §3.10).
4. `systemd/luminos-power.service` (repo copy) — Type=notify, WatchdogSec=15, Restart=always, RestartSec=3,
   ExecStopPost opens the dial (DESIGN §3.8).
5. `scripts/luminos-fan-curve-install` — one-time, human-run: curve v6 on quiet/balanced/performance + asusd.ron
   `change_platform_profile_on_ac/battery: false`. Idempotent, backs up the .ron, prints what it changed.
6. `tests/spectrum/load/` — Go tool: N worker threads at a duty %, for T seconds; reports ops/s. Used as stress + bench.
7. `scripts/spectrum-ab.sh` — the §6 ladder + 1 Hz logger (Tctl, RAPL package W, ppt files, runtime_status, socket
   status), plus kprobe counters (rpm_resume on 01:00.0, asus_wmi_evaluate_method3 by devid). Writes CSV + summary.

## Assumptions / decisions (gaps filled)
- A1 DESIGN.md constants are v1 defaults; config.toml `[power]` may override (DESIGN §3.11).
- A2 Package watts for the A/B come from RAPL energy_uj (Q4 measured), not `sensors`.
- A3 The old binary is kept at /usr/local/bin/luminos-power.pre-spectrum for the A arm and for rollback.
- A4 EPP fixed `balance_power` (DESIGN §3.6); banded EPP not built in v1.
- A5 `luminos-train-mode`'s asusctl fan keep-alive is removed in the same change (DESIGN §3.5), as is the burst-related doc.
- A6 The daemon never reads fan rpm (Q5: each read is a BIOS call). The A/B harness reads rpm every 5 s only.
- A7 Install + /etc changes (unit file, asusd.ron, fan curves) are done by the PM after tests pass, documented in
  AGENTS.md §9 + LUMINOS_DECISIONS.md the same day.

## Done means
1. `go vet ./cmd/luminos-power && go test -race ./cmd/luminos-power` pass; properties P1–P15 pass.
2. `go build` produces the binary; `gofmt -l` clean on touched files.
3. Budgets: spectrum.go ≤ 200 lines, functions ≤ 40 lines, nesting ≤ 3; main.go net-shrinks (it is 2238 lines now);
   new I/O code in main.go ≤ 250 lines. No new dependencies.
4. Live A/B (DESIGN §6) thresholds met, measured on the G14. Thresholds are DESIGN §6's table, fixed now.
5. Zero dGPU wakes caused by the daemon over the whole B run (kprobe count), including restarts and cable events.
