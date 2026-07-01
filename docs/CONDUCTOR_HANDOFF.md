# CONDUCTOR_HANDOFF.md — pick-up briefing for a new chat
# [CHANGE: claude-code | 2026-06-30]
# [CHANGE: claude-code | 2026-07-01] Phase 4 landed — see §0/§4. Next up: Phase 5 (NPU model, deferred).

> Paste-and-go context for continuing the Conductor work in a fresh session.
> Read this first, then `docs/CONDUCTOR_DESIGN.md` (full design) and
> `LUMINOS_DECISIONS.md` → DECISION 24 (the ratified decision).

---

## 0. TL;DR — where we are

We are re-architecting the Luminos OS power/thermal daemon so components are
controlled **independently under one policy engine** — the **Conductor** — instead
of one coarse `asusctl` profile dragging every knob up together.

**Phases 0-4 are DONE.** Phases 0-3 committed+pushed earlier (`19fbedbd`); Phase 4
(intent broadcast + ram coordination + telemetry) landed 2026-07-01. The code is
**wired into the live loop but GATED OFF by default** behind the env var
`LUMINOS_CONDUCTOR=1`. With the var unset (default), nothing about live cooling
changed — the old asusctl curves + thermal burst still run, and the Conductor never
broadcasts.

**Next up: Phase 5 (NPU/LLM policy model) — DEFERRED per user ("heuristics first").**
The Phase 4 telemetry corpus (`<logdir>/conductor-telemetry.jsonl`, one sensor→action
row per tick) is now being logged so the dataset exists when Phase 5 begins.
Refine-later: PID gains (Kp14/Ki0.6/Kd8) + classifier thresholds vs. real telemetry.

---

## 1. The user's three original pains (and the correct diagnosis)

1. **No per-component control.** One `asusctl profile` (Quiet/Balanced/Performance)
   moved every knob at once. User wants "unlock PCIe but keep the rest normal."
2. **PCIe capped during training.** ⚠️ IMPORTANT CORRECTION: the laptop was **always
   on the 180W AC brick, NEVER battery.** Root cause is `DPM=0x02`
   (`NVreg_DynamicPowerManagement`, AGENTS.md §9) parking the *unpinned* dGPU in its
   lowest P-state → downtrains the PCIe link to Gen1 **even on AC**. The old daemon
   never recognized the training job as GPU-busy, so it never pinned P0. Do NOT design
   this as a battery-mode fix — it is **workload-aware**.
3. **Open-loop cooling, still hot.** Fan was a static table handed to the EC once, plus
   a 52°C burst panic-button. No real-time feedback; the 45-55°C mid-band stayed hot.

### The two hard user preferences (these are load-bearing — don't regress them)
- **Fan target is WORKLOAD-AWARE, not a fixed number.** Light load (browsing/idle):
  47°C is reachable → hold it gently. Heavy load (4K video, training, gaming): 47°C is
  physically impossible → hold a *fair higher ceiling* (~55-65°C) efficiently. Use the
  **least** PWM that holds the fair target. **Maxing the fan at 50-55°C is a rejected
  design** — user called it a waste of power and noise.
- **PCIe/GPU pin uses persistence + `lock-gpu-clocks`, NEVER `nvidia-smi -pl`** — `-pl`
  is a confirmed no-op on the RTX 4050 Mobile (BUG-069, power.limit reads `[N/A]`).

---

## 2. What was built (Phases 0-3)

### New files
- **`cmd/luminos-power/conductor.go`** — the policy engine. Contains:
  - `conductorEnabled` (`= os.Getenv("LUMINOS_CONDUCTOR") == "1"`) and `conductor *Conductor` (nil until enabled).
  - `conductorOwnsFan()` — the single-writer guard the legacy fan writers check.
  - `Intent{Name, FanTarget, GPUTarget, PinGPUP0}` — per-workload posture; each lever reads only its fields.
  - `Signals{OnAC, CPUTempC, GPUTempC, CPULoad, DGPULoad, IGPULoad, GPUPowerW}` — sensed state (filled from monitorLoop's existing reads, no extra sysfs).
  - `Lever` interface (`Name/Apply/Revert`).
  - `fanLever` — two `FanController`s (cpu/chassis + gpu). `tick()` runs the PID every loop; `Apply()` resets integrators on intent change; bound to the hwmon or no-ops if not found.
  - `pcieLever` — `Apply()` reuses `applyOffloadPin(true)` to pin P0, calls `verifyPCIeLinkSpeed()`, and **defers if `offloadActive.Load()`** (a real offload session already owns the pin). `Revert()` only un-pins what it pinned.
  - `verifyPCIeLinkSpeed(when)` — reads `/sys/bus/pci/devices/0000:01:00.0/current_link_speed` + `_width` and logs them.
  - `Conductor.Tick(Signals)` — sense → `classify()` → on intent-name change call `Apply` on every lever → run fan PID every tick. `Revert()` on shutdown.
  - `classify(Signals) Intent` — heuristic seed: dGPU≥60% or GPUpower≥40W → gaming (or training if CPU≥50% too) + pin P0 (AC only); iGPU≥40% → media; CPU≥50% → compute; else light/idle.
  - `gpuFairTarget(class)` — GPU-fan counterpart to `fairTargetForWorkload`.

- **`cmd/luminos-power/fan_control.go`** — the PID (landed earlier, now wired). Key parts:
  - `fanCurveHwmonPath()` discovers `asus_custom_fan_curve` **by name** (hwmon index is unstable across boots).
  - `fanCurveTempAnchors = [8]{30,40,45,50,60,70,80,90}`; `fanFailsafeFloorPWM = [8]{0,0,0,0,0,120,210,255}` — the EC-level failsafe ramp ≥70°C baked into every curve write, so the fan self-protects even if the daemon dies.
  - `writeFanDuty` / `setAllFansDuty` — flat duty across the normal band + failsafe ramp; cpu+mid share `cpuDuty`, gpu gets `gpuDuty`.
  - `FanController` — positional PID, `err = temp − setpoint`, anti-windup clamp, **asymmetric slew (fast up, gentle down)**. `NewFanController()` defaults: Kp14 Ki0.6 Kd8, MaxStepUp60/Down18.
  - `fairTargetForWorkload(class)` — idle/light 47, media 55, gaming/training/compute/heavy 60, default 52.

### Edits to `cmd/luminos-power/main.go`
- `main()`: after `applyACTransition(onAC)`, if `conductorEnabled` → `conductor = NewConductor()` + `defer conductor.Revert()`.
- `monitorLoop()`: after the EMA-smoothing block (~line 415), `if conductorEnabled && conductor != nil { conductor.Tick(Signals{…}) }`.
- `applyAggressiveFanCurve` and `applyBurstFanCurve`: early `if conductorOwnsFan() { return }` — single-writer discipline so the PID and the asusctl curve never fight over the same hwmon points.

### Docs updated
- `LUMINOS_DECISIONS.md` → **DECISION 24** (full rationale + Rule-11 both-sides conflict).
- `docs/CONDUCTOR_DESIGN.md` → progress tracker (Phases 0-3 ✅, Phase 4 🟡, Phase 5 ⏸), status line, Phase 0 probe findings.
- `LUMINOS_STATUS.md` → luminos-power row + date.

---

## 3. How the gating works (why committing was safe)

- `LUMINOS_CONDUCTOR` unset → `conductorEnabled=false` → `conductor` stays nil → the
  `Tick` call is skipped, `conductorOwnsFan()` returns false, the legacy curves run
  unchanged. **Live cooling is identical to before.**
- `LUMINOS_CONDUCTOR=1` → Conductor builds, binds the fan hwmon, and OWNS the fan +
  PCIe levers. The legacy fan writers no-op. Emergency 92°C CPU-cap path is retained.
- Rationale: the machine was probed at **83.5°C**; handing fan control to brand-new
  code on a hot laptop is risky, so the user enables it deliberately and watches it.

### How to enable + watch (for the user)
```bash
# run the daemon (systemd unit or directly) with the env var set, e.g.:
sudo LUMINOS_CONDUCTOR=1 /path/to/luminos-power
# watch the fan PID + PCIe pin:
tail -f <logdir>/power.log            # look for "conductor: intent …", fan writes
watch -n1 'cat /sys/bus/pci/devices/0000:01:00.0/current_link_speed'  # PCIe verify
nvidia-smi -q -d PERFORMANCE          # P-state / clock lock check
```

---

## 4. Phase 4 — DONE (2026-07-01), and what's beyond

Phase 4 = **workload classifier + intent broadcast** — all four TODOs landed:
1. ✅ **Broadcast the Intent.** On intent *change* the Conductor (`conductor.go`
   `broadcast()`) writes `/run/luminos/intent.json` atomically (temp+rename, generalises
   the old `offload.active` signal) AND socket-pushes an `intent` message to
   `/run/luminos/ram.sock` + `cfg.Sockets.AI` (`pushIntent()`, off-loop goroutine so a
   slow peer can't stall the PID).
2. ✅ **`report_ram` added to luminos-ai** — new `case "report_ram"` caches ram state;
   also new `case "intent"` caches the broadcast; both surfaced in `status`.
3. ✅ **ram reacts to the Intent** — new `case "intent"` → `handleIntent()`: heavy class
   (training/gaming/compute/heavy) lowers `vm.swappiness`, light/idle restores baseline.
   The SOFT reaction only — it does NOT fabricate a reservation (that hard number still
   comes from a real `offload_start`). Precedence **offload > intent** enforced by the new
   single-writer `reconcileSwappinessLocked()` (fixes a latent baseline-corruption bug
   where intent lowering swappiness before `offload_start` could poison the saved 60).
   ram pushes `report_ram` to ai on every state change.
4. ✅ **Telemetry corpus** — `logTelemetry()` appends one `telemetryRow` per tick to
   `<logdir>/conductor-telemetry.jsonl` (numeric sensor vector → action: fair targets,
   resulting fan duties, pin decision), rotates past 64 MiB.

Files: `cmd/luminos-power/conductor.go`, `cmd/luminos-ram/main.go`, `cmd/luminos-ai/main.go`.

**Phase 5 = NPU/LLM policy model — DEFERRED per user ("heuristics first").** The corpus
above is the dataset. Refine-later: PID gains (Kp14/Ki0.6/Kd8 are starting values, tune
against real telemetry); the classifier thresholds are coarse heuristics.

---

## 5. Integration gotchas / risks to keep in mind

- **Single-writer is sacred.** Only ONE code path may write `asus_custom_fan_curve`.
  If you add any new fan write, gate it behind `conductorOwnsFan()`.
- **PCIe lever vs. real offload sessions.** `pcieLever` defers when `offloadActive` is
  already set so it doesn't double-manage the pin. But note `applyOffloadPin` ALSO
  writes `/run/luminos/offload.active` and flips `offloadActive` — if the Conductor
  pins for training, monitorLoop will treat it like an offload session (TGP→90W), which
  is desired for training but worth remembering.
- **Emergency thermal path (92°C region) is retained** and still caps CPU freq; it sets
  profile=Quiet via asusctl which could reset the custom curve, but the PID re-writes
  every tick (~2s) and the EC failsafe ramp ≥70°C covers the gap.
- **Battery:** the PCIe pin only fires on AC (`pin && s.OnAC`) — on battery we WANT the
  dGPU parked. Keep it that way.

---

## 6. Mandatory project rituals (from AGENTS.md / CLAUDE.md) — DON'T skip

- **Read `AGENTS.md` fully at the start** of the session — it's the constitution
  (identity tags, minimal-change Rule 1, §11 don't-touch-cmd-daemons-unless-instructed,
  §9 DPM note, §12 fan curve, §14 open tasks, §16 reply format).
- **Identity tags mandatory** on every change: `[CHANGE: claude-code | YYYY-MM-DD]`.
- **NO DOCKER, NO OLLAMA.** HIVE models are llama.cpp GGUF.
- Before a task: `~/luminos-os/scripts/luminos-notes.sh search "<topic>"`.
- After a task: `~/luminos-os/scripts/luminos-notes.sh add [TAG] "summary"`,
  `luminos-brain log "summary"`, update relevant docs (STATUS/DECISIONS/BUGS/
  CODE_REFERENCE), then `git add -A && git commit && git push origin main`.
- Commit message trailer style used here:
  `Agent: claude-code` / `Task: …` / `Co-Authored-By: Claude Opus 4 <noreply@anthropic.com>`.
- **Watch for build artifacts:** `go build ./cmd/luminos-power/` drops a `luminos-power`
  binary in the repo root — do NOT commit it (stage files explicitly, not `git add -A`
  blindly). Also there are dirty `research/turboquant/repo-*` submodules that are NOT
  ours — leave them unstaged.

---

## 7. Hardware quick-reference (ASUS ROG G14)

- Ryzen 9 8845HS (TJmax 105°C), RTX 4050 Mobile dGPU (`card1`, PCI `0000:01:00.0`),
  Radeon 780M iGPU (`card2`), AMD XDNA NPU (16 TOPS), 16GB RAM, 6GB VRAM (4.6GB safe).
- 5 Go daemons: luminos-ai (passive status aggregator), luminos-power (thermal/power
  brain — where the Conductor lives), luminos-ram (LIRS memory mgr), luminos-sentinel
  (/proc security scanner), luminos-router (.exe zone classifier).
- IPC: Unix sockets in `/run/luminos/`, JSON `Message{Type, Payload, Timestamp, Source}`,
  `socket.Send(path, msg)` for any-to-any dial.

### Phase 0 probe findings (real hardware, 2026-06-30, on AC)
- Fan actuator = direct sysfs to `asus_custom_fan_curve` (cpu=ch1, gpu=ch2, mid=ch3).
- PCIe idle: `current_link_speed=2.5 GT/s` (Gen1), GPU `pstate=P8`, max 16 GT/s (Gen4).
  Pin P0 → link trains up; verify via read-back.
- BUG-069 confirmed: `-pl` is a no-op → use persistence + `lock-gpu-clocks`.
- CPU hit 83.5°C with fans already maxed → confirms the open-loop curve reacts at the
  top end; the pain is the lazy 45-55°C mid-band the PID now targets.
