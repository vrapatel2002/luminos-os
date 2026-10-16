# BUILD_LOG — spectrum
# [CHANGE: claude-code | 2026-10-15]
- 19:08 Shawn: replace phased power profiles with a continuous spectrum. /build, brainstorm with Fable/Opus max effort.
- Discovery: Opus mapped the daemon (CURRENT.md); PM measured knobs (HARDWARE.md). PPT = smooth dial, no dGPU wake.
  Profile change resets PPT; read-back is a cache.
- Fable (max effort) wrote DESIGN.md: 15 ideas → chosen = demand ramp + thermal PI with feed-forward + battery/dGPU
  ceilings under a hard min and ONE slew limiter; fans static v6 curve; EPP fixed; never write profile/curves.
- 20:40 pre-build checks Q2/Q4/Q5/Q12/Q13/Q14/Q16 measured (HARDWARE.md bottom).
- Thresholds = DESIGN §6 table, frozen before any build.
- Core spectrum.go (Opus): 182 lines, max fn 23 lines. Tests spectrum_test.go (Opus): 948 lines, independent reference
  model + P1–P15 + trajectories; 9 mutants all caught; passes with -race (2 000 walks). Spec ambiguities C6/P5/P9 found by
  both workers independently → rulings added to CONTRACTS.md (spec fixed, not the code).
- Integrator (Fable): main.go 2238 → 1123, conductor.go + fan_control.go deleted. PM verified: build/vet/test -race OK,
  gofmt clean, file boundaries held, nvidia-smi only in offload_* path, setProfile only behind assert_profile (off).
  Over budget: new I/O ≈ 300 lines vs 250 target (config overrides + read-only fan-curve check) — accepted, logged.
- PM fix: ExecStopPost now writes 45/54/65 W like shutdown() (was 45/45/45).
- Arm A (old daemon, full 28 min ladder) done: 4 dGPU wakes, 7 profile writes, idle 49–55 °C / fan 2.8–3.0 k rpm,
  cpu16 held at 26 W / 84 °C / fan 5.6 k rpm / 6.68e9 ops/s. Results docs/spectrum/ab/A-*/summary.txt.
- Container restart killed the first reviewer mid-run; re-spawned (Fable). Laptop state unaffected (old daemon running).
- Arm C (no daemon, firmware + v6 curve): 0 wakes, but 95 °C pinned even at 4 threads (~30 W), fans 6.0–6.3 k rpm,
  idle 55–58 °C / 2.9–3.7 k rpm. Note: v6 at 50–55 °C still spins ~3 k rpm → fan minimum speed is high; Q8 needed.
- Independent review (Fable, re-spawned after container restart): no dGPU-wake path, no races. 2 CONFIRMED (ExecStopPost
  `%s` systemd specifier broke the cap restore; loop ran at 0.5 Hz from config default) + 7 PLAUSIBLE (PPT write
  failure not retried, linked EPP, AC side effects could block the loop → watchdog restart loop, fan-curve check at boot,
  override validation, dead code, scripts' tolerances). All routed back to the file owners.
- 22:37 new daemon installed (v6 curve + asusd.ron 3× false + unit + binary). Startup kprobe: 0 dGPU wakes, only PPT writes.
- Arm B (Thi 88): throughput ≥ A everywhere (burst1 +33 %, burst16 +10 %, sus16 +3 %, cpu16 −1 %), idle W 8.47 vs 8.28,
  less fan at cpu4/cpu8, cpu16 88 °C (C pinned 95). FAILS: 8 dGPU wakes — ALL inside a real 80 s charger dropout
  (23:06:50→23:08:10, asusd + daemon both logged it): firmware ACAD events + asusd re-writing fan curves on every AC/DC
  toggle (write_profile_curve_to_platform) → NPCF 0xC0. Daemon-caused wakes: 0. cpu4/cpu8 +7 °C vs A for +1–8 % ops;
  cpu16: 27 W/88 °C gave 6.62e9 vs A's 26 W/84 °C 6.68e9 → the last 4 °C buys nothing. Idle fan 2.9 k rpm = fan floor
  (A 2.8–3.0 k, C 2.9 k): threshold 2 500 assumed a lower minimum spin. Load-step "inf" at cpu16 = heat hand binding by
  design (stage starts hot); sus16 4 s PASS. ppt rise 7 W/s = 1 s-resolution timestamps in the logger (core P2-proven ≤ 6).
- Tuning (no code): /etc/luminos/config.toml `[power] t_hi_ac_c = 82` (file did not exist; loader merges over defaults).
  Found clamp regression from review fix #7 (bat-lo 15→20; my instruction) → sent back to integrator.
- 23:12 arm B2 (Thi 82) started, same thresholds.
- Arm B2 (Thi 82 via config.toml): 0 dGPU wakes, 0 notifies, 0 profile/curve writes, 742 PPT writes/h; idle 42 °C / 2.4 k rpm /
  8.32 W; cpu4 66 °C 3.6 k rpm; cpu8 79 °C 5.5 k rpm; cpu16 82 °C 36 W 7.60e9 ops (+14 % vs A); bursts +12 % / +36 %.
  19 of 22 thresholds PASS. FAIL by definition: fan max at 50–55 °C (cool-down samples, idle median 2.4 k), cpu16 load-step
  (heat hand binds, stage starts hot; sus16 5 s PASS), ppt rise 7 W/s (logger 1 s timestamps; core P2-proven ≤ 6).
  Thresholds NOT moved. Caveat: B2 ran in a cooler environment than B (idle 42 vs 55 °C).
- Clamp regression fixed (bat-lo 15 restored; defaults-drift check added). Installed.
- Event tests: 3× restart → 0 wakes, 0 notifies, only PPT writes. kill -STOP → watchdog kill at 14 s, restart, 0 wakes.
  NOT done: suspend/resume and ROG-key tests (would disrupt Shawn's session) — listed in HANDOFF.
- Not done (deliberately): luminos-train-mode's asusctl fan keep-alive (only runs during GPU training, when the dGPU is awake anyway).
- Docs: DECISION 146, BUG-203 (asusd curve rewrite on AC/DC toggle), BUG-198/200 status, AGENTS §9/§12/§15, STATUS, CODE_REFERENCE.
