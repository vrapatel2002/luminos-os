# CONDUCTOR_DESIGN.md — Unified Per-Component Power Policy
# Proposal for DECISION 24 | Draft by: claude-code | 2026-06-30
# Status: APPROVED — Phases 0-4 landed & wired (gated OFF by default), Phase 5 deferred
# [CHANGE: claude-code | 2026-06-30]
# [CHANGE: claude-code | 2026-07-01] Phase 4 complete — intent broadcast + ram coordination + telemetry corpus.

> Approved by user 2026-06-30. The NPU/LLM policy-model layer (Phase 5) is deferred —
> heuristic brain first. Phases 1-3 are now wired into monitorLoop but **gated OFF by
> default** behind `LUMINOS_CONDUCTOR=1`: committing, pushing, or restarting the daemon
> does NOT change live cooling. The Conductor only owns the fan + PCIe levers when the
> user deliberately sets that env var and watches it, because the daemon actively manages
> a hot machine (probed at 83.5°C). Until then monitorLoop behaves exactly as before.

---

## Progress Tracker

| Phase | Status | Notes |
|---|---|---|
| 0 — Hardware probe | ✅ done | Findings below. |
| 1 — PCIe lever + read-back | ✅ done | `pcieLever` in `conductor.go` reuses `applyOffloadPin` P0 mechanism; fires on training/heavy-GPU (AC only); `verifyPCIeLinkSpeed` reads back `current_link_speed`/`width`. Defers if a real offload session owns the pin. |
| 2 — PID fan controller | ✅ wired | `fan_control.go` PID + `fanLever` in `conductor.go`, wired into `monitorLoop`. Legacy `applyAggressiveFanCurve`/`applyBurstFanCurve` no-op when `conductorOwnsFan()` (single writer). Gated OFF by default. |
| 3 — Lever abstraction + Intent | ✅ done | `Intent`, `Signals`, `Lever` interface + `Conductor` in `conductor.go`. Sense→classify→Intent→drive levers; fan PID every tick. |
| 4 — Classifier + intent broadcast | ✅ done | Heuristic `classify()` + broadcast landed. Conductor writes `/run/luminos/intent.json` (atomic) + socket-pushes `intent` to ram+ai on change. `luminos-ram` reacts (heavy→lower swappiness via single-writer `reconcileSwappinessLocked`, offload>intent precedence) and now pushes `report_ram` to ai. Per-tick `conductor-telemetry.jsonl` corpus (sensor vector→action) logged for Phase 5. `[CHANGE: claude-code | 2026-07-01]` |
| 5 — NPU policy model | ⏸ deferred | Per user — heuristics first. Training corpus now being logged from day one (`conductor-telemetry.jsonl`). |

### Phase 0 hardware probe — findings (real G14, 2026-06-30, on AC)
- **Fan actuator = direct sysfs.** `hwmon` named `asus_custom_fan_curve` exposes writable 8-point curves per fan (`pwmN_auto_pointM_{temp,pwm}`, root-writable, temp °C, pwm 0-255). cpu=ch1, gpu=ch2, mid=ch3. **Decision: write a flat-duty curve with a baked-in failsafe ramp ≥70°C** — direct PWM authority + hardware self-protection if the daemon dies. No asusctl subprocess needed. (hwmon index is unstable → discover by name.)
- **PCIe confirmed P-state-driven.** Idle reading: `current_link_speed=2.5 GT/s` (Gen1), GPU `pstate=P8`, `max=16 GT/s` (Gen4). Pin P0 (persistence + `lock-gpu-clocks`, already in `applyOffloadPin`) → link trains up. **Verify** via `current_link_speed` read-back.
- **BUG-069 confirmed empirically:** `nvidia-smi` power.limit reads `[N/A]` on this RTX 4050 Mobile → `-pl` is a true no-op. PCIe/GPU levers must use persistence + clock-lock, never `-pl`.
- Observed during probe: CPU at 83.5°C with fans already maxed (6800 RPM) — confirms the open-loop curve reacts at the top end; the user's pain is the lazy 45–55°C mid-band, which the PID targets.

---

## 0. The three problems (grounded in the current code)

| # | What you said | What the code actually does today | File |
|---|---|---|---|
| 1 | "everything controlled by single code making same power level for all components… I want to control each component individually but under single rule" | A single coarse `asusctl profile` (Quiet/Balanced/Performance) moves **every knob together**. There is no way to bump one lever (PCIe) while leaving the rest normal. | `cmd/luminos-power/main.go:451-470` (beast mode flips the whole profile) |
| 2 | "my PCIe was stuck when I trained my model" (machine was on the 180W brick — **never** battery; cap came from the older power daemon) | PCIe is **deliberately never touched**. `DPM=0x02` parks the dGPU in its lowest P-state when it doesn't look busy, which downtrains the link to Gen1 **even on AC**. The daemon never recognized the training job as "GPU busy," so it never pinned the GPU to P0 → link stayed narrow. Not a battery issue. | `cmd/luminos-power/main.go:1351-1353`; DPM note in AGENTS.md §9 |
| 3 | "ram manager and cooling… still hot and fan ain't spinning… I want it smart enough to spin the fan just enough to maintain a certain temp under pressure" | Fan control is **open-loop**: a static lookup table is handed to the EC firmware once (`asusctl fan-curve`), then the daemon walks away. No real-time temp→PWM feedback. The only active piece is a 52 °C panic button (burst → 100 %). | `cmd/luminos-power/main.go:1616-1653` |

**Root cause shared by all three:** policy and actuation are fused, levers are bundled into one profile, and the "smart" parts are delegated to firmware that the daemon can't see or correct.

---

## 1. Core idea — separate the **brain** from the **levers**

```
                 ┌──────────────────────────────────────────────┐
                 │            CONDUCTOR (the one rule)            │
                 │                                                │
   sensors ───▶  │  SENSE → CLASSIFY workload → DECIDE per-lever  │  ───▶ levers
   (temp, load,  │            (intent, not profile)               │      (independent)
    AC, PCIe,    │                                                │
    RAM, PSI)    └──────────────────────────────────────────────┘
```

One brain, many **independent levers**. The brain decides *intent* ("this is a training run → I need PCIe Gen4 + RAM headroom, CPU/GPU can stay normal") and each lever is actuated on its own. No more "one profile for everything."

### Where it lives
**Extend `luminos-power`, don't add a new daemon.** It already owns the control loop, the sensors, and most levers (CPU, GPU TGP, EPP, fan). Adding PCIe + a real fan loop + a workload classifier *inside* the existing `monitorLoop` keeps everything single-writer (no cross-process races on sysfs) and reuses the PSI-driven wake strategy. The other daemons (ram, ai) coordinate via a lightweight intent broadcast (§5).

> Rename note: internally we can call the policy core "Conductor" but the binary/service
> stays `luminos-power` to avoid touching systemd units, sockets, and §9 config.

---

## 2. The lever model

Each lever is a small interface: read current value, compute desired value from the active **intent**, write it, and **revert cleanly**. Levers are independent — the brain sets each one separately.

| Lever | Mechanism / sysfs | Today | Under Conductor |
|---|---|---|---|
| **PCIe link** | dGPU `…/power/control`, P-state pin, ASPM policy | uncontrolled | battery-aware: force Gen4 when a bandwidth-bound workload is active (§4) |
| **GPU TGP** | `nvidia-smi -pl` | per-profile + offload pin | per-intent, thermal-gated (keep existing logic) |
| **GPU clock** | `nvidia-smi --lock-gpu-clocks` | offload pin only | per-intent |
| **CPU EPP** | `…/cpufreq/energy_performance_preference` | per-profile | per-intent |
| **CPU freq cap** | `…/cpufreq/scaling_max_freq` | adaptive (keep) | adaptive (keep) |
| **Fan PWM** | direct PWM **or** narrow asusctl curve | open-loop EC table | **closed-loop PID** (§3) |
| **RAM swappiness / pageout** | `vm.swappiness`, `MADV_PAGEOUT` exempt | offload-only (ram daemon) | per-intent, via intent broadcast (§5) |

Key principle: **a lever moves only when the intent requires it.** "Unlock PCIe but keep the rest normal" becomes a first-class outcome, not a side effect of a profile flip.

---

## 3. Closed-loop PID fan controller (your "just enough fan to hold a temp")

Replaces the static curve with a real feedback controller — but the setpoint is **not fixed**.
It **floats with workload**. Two stages per tick:

```
STAGE 1 — pick a FAIR target temp for the current workload (from the Intent):
    idle / browsing   → 47°C   (reachable → hold it gently)
    media / 4K video  → ~55°C  (47 impossible → don't waste fan chasing it)
    training / gaming  → ~58-60°C (heavy → fair ceiling, hold efficiently)

STAGE 2 — use the LEAST fan that holds that fair target:
    error = temp − fairTarget
    PID:  pwm += Kp·error + Ki·∫error·dt + Kd·d(error)/dt
    clamp [floor, ceiling], slew-limit, write PWM
```

- **Workload sets the target, not a single number.** The brain answers "is this temp normal *for what you're doing*?" — 55 °C while training is fine (low fan); 55 °C while browsing is wrong (bump fan). Same temp, different response.
- **Minimum-effort fan.** It uses the *quietest* PWM that holds the fair target. It does **NOT** max the fan at 50–55 °C just because temp is above 47 — that wastes power and noise for nothing. Full blast is reserved for genuine danger (temp climbing past the fair ceiling toward the hot zones).
- **Three inputs, like the user wants:** workload + current heat + trend (rising/falling, via the PID's derivative term — lets it pre-empt a spike instead of reacting late).
- **Anti-windup + slew limiting** so the fan doesn't oscillate or surge audibly.
- **Safety floors win:** hard PWM floor by temp band (e.g. ≥80 °C forces ≥80 % regardless of PID), and the existing 92 °C emergency override is untouched. Watchdog: if the loop ever stalls, fall back to the v5 curve so fans are never left silent at high temp.

### ⚠️ The one hardware unknown to verify first
The G14's fans may only be reachable through `asusctl`'s EC curve interface, **not** a writable `/sys/class/hwmon/hwmonX/pwm1`. Two actuation paths, pick based on what the hardware exposes:
- **A (preferred): direct PWM** — if `pwm1_enable=1` + `pwm1` are writable, the PID writes PWM directly every tick. Cleanest.
- **B (fallback): virtual PWM via asusctl** — each tick, collapse the fan-curve into a near-flat line around the current temp so the EC's effective duty equals the PID output. Works through the existing interface, slightly coarser.

**This is the #1 thing I'll probe on-hardware before committing to A vs B.** Both are reversible.

---

## 4. PCIe fix (your training blocker — fixable independently, first)

The training stall is the most concrete, isolated problem, so it can ship before the rest.
**Important correction:** the machine was on the 180W brick the whole time — this is **not**
a battery issue. The cap is `DPM=0x02` parking the dGPU in its lowest P-state because the
old daemon never flagged the training job as "GPU busy"; the narrow link is a *symptom* of
the unpinned P-state, on AC.

- **Detect** the bandwidth-bound workload (training / weight-offload / llama-server) via the classifier (§5) or the existing `offload_start` signal — this is the piece that was missing.
- **Force the link up**: pin the dGPU to P0 (persistence + clock lock — *already done* in `applyOffloadPin`, just needs to fire for training too), which stops `DPM=0x02` from downtraining the link. If P0 alone isn't enough, the lever also writes the dGPU `power/control` → `on` and relaxes ASPM for that device for the session.
- **Read-back verify**: poll `current_link_speed` and log actual vs expected — no more "fiction" logs like BUG-069's `nvidia-smi -pl` no-op. If the link won't train up, say so loudly instead of pretending.
- **Revert** fully on stop: restore `power/control`, ASPM, P-state — nothing permanent, no `/etc`, mirroring the `luminos-train-mode` philosophy.

This directly retires the "blocked on hardware verification" caveat in the DECISION 23 comment, because we *measure* the link instead of assuming.

---

## 5. The "smart" part — workload classifier + intent broadcast

You asked for it to be "smart out of the box… ML/AI level." Here's the honest, layered answer:

### Today (heuristic core — ships first)
The exec watcher already detects app launches (`newExecWatcher`, `knownApps` map). Extend it from a CPU-prealloc hint into a **workload classifier** that emits an **Intent**:

```
Intent {
  name        // "training", "gaming", "llm-inference", "browsing", "idle"
  pcie        // gen4 | normal
  gpu         // boost | normal | gated
  cpu         // boost | normal | quiet
  fanTarget   // setpoint °C + pwm ceiling
  ramReserve  // MB to protect + swappiness
}
```
Classified from signals you already collect: process name/cmdline (python+torch, llama-server, a game exe via the router's zone), dGPU vs iGPU load split, sustained PCIe traffic, RAM pressure, AC state. Rules are transparent and debuggable.

### Later (the real intelligence — designed-in, not bolted-on)
The classifier is a **pluggable interface**. You already have an idle **XDNA NPU** and a planned **MobileLLM-R1-140M Sentinel** (AGENTS.md §4, Open Task 0a). The same NPU can run a tiny always-on policy model that takes the sensor vector → intent, learning your actual usage instead of following hand-written rules. The heuristic version is the fallback the model degrades to. **This is the upgrade path that makes "ML-level smart" real** — and it reuses infra you're already building for Sentinel.

#### How the policy model is trained
The task is *small numbers in → simple action out*, so the model is tiny (a small MLP / INT8 net, far smaller than an 8B chat model — NPU-friendly). Training pipeline:

1. **Rules generate the dataset.** Run the heuristic version and log one row per tick:
   `(sensors: temp, cpu/dgpu/igpu load, fan%, power, RAM free, app) → action taken → outcome (temp +5s later, fan power burned, did link stay up)`. This is the same `.jsonl` pattern as `nexus_*.jsonl` / `sentinel_*.jsonl`, but rows are numeric sensor vectors instead of chat.
2. **Imitation first.** Train the model to copy the *good* rows — it reproduces the rules' sensible decisions.
3. **Outcome scoring beats the teacher.** Score each decision: held the fair target temp **using the least fan power**, kept PCIe up when needed, no overshoot. Reward good, penalize wasteful (e.g. max fan at 55 °C) — this is where it learns user-specific patterns the rules miss (4K-video spikes ~30 s in, etc.).
4. **Quantize → NPU.** Compress to INT8, load via the Sentinel/HATS ONNX path. Model drives; rules stay as the safety net.

Bootstrapping note: Phase 4 must log this dataset from day one so that by Phase 5 there's already weeks of *your* real usage to train on. No separate data-collection effort.

### Intent broadcast (this is the inter-daemon coordination you want)
When the brain picks an intent, it broadcasts it. Daemons subscribe and each reacts to *its* slice:
- `luminos-ram` ← `ramReserve` (it already has the swappiness + pageout-exempt machinery from the offload work — generalize `offload.active` into a small intent file or socket push).
- `luminos-power` (self) ← pcie/gpu/cpu/fan levers.
- `luminos-ai` ← informed for status/telemetry.

Mechanism: extend the existing `/run/luminos/offload.active` file pattern into `/run/luminos/intent.json` (atomic write + inotify), **or** a one-line socket push to each daemon. The file approach reuses what's proven and needs no new socket plumbing — recommended for v1.

---

## 6. Phased build plan (each phase independently shippable & revertible)

| Phase | Deliverable | Why this order |
|---|---|---|
| **0** | Hardware probe: can we write PWM directly? Does pinning the dGPU to P0 raise `current_link_speed` on the brick? | De-risks §3 (A vs B) and §4 before writing logic. Pure measurement, no changes. |
| **1** | **PCIe lever + read-back verify** — fixes the training blocker. | Most concrete pain, isolated, immediately useful to you. |
| **2** | **Closed-loop PID fan** with setpoint + safety floors + curve fallback. | Fixes "hot and fan not spinning." High daily-life value. |
| **3** | **Lever abstraction + Intent struct** — refactor existing knobs into independent levers behind the brain. | Internal refactor; behavior-preserving, sets up per-component control. |
| **4** | **Heuristic workload classifier + intent broadcast** — ram/power react together. | Delivers "daemons work together under one rule." |
| **5** | **NPU classifier plug-in** (optional, after Sentinel NPU lands). | The "real ML smart" upgrade, on infra you're already building. |

You can stop after any phase and still have shipped a real improvement.

---

## 7. Safety, reversibility, and the rules

- **Single-writer**: all sysfs writes stay inside `luminos-power`'s loop — no cross-daemon races (same discipline as the current TGP single-writer note at line 384).
- **Fully revertible**: every lever restores prior state on intent-exit and on daemon stop. No `/etc`, no fstab, no sysctl.d — same philosophy as `luminos-train-mode` / `luminos-train-ram`.
- **Fail-safe fan**: PID watchdog falls back to the v5 curve; emergency thermal override (92 °C) is never bypassed.
- **Doc obligations** when built: AGENTS.md §9 (if any `/etc` or udev for PCIe/ASPM ends up needed), §12 (fan policy change), LUMINOS_DECISIONS.md (this becomes DECISION 24), docs/BUGS.md (retire BUG-069 fiction logging; the battery-PCIe assumption bug), CODE_REFERENCE.md.
- **MCP rituals** before touching Go: `code-review-graph` on `cmd/luminos-power/main.go` + `mempalace_search` — I'll run these at implementation time (they weren't needed for this read-only design pass; flagging that I have not yet run them).

---

## 8. Open questions for you

1. **Setpoints**: what target temps do you actually want — e.g. idle ≤47 °C silent, sustained load hold ~60 °C, hard ceiling where noise stops mattering ~80 °C? Or should the load target be tunable live from a widget?
2. **PCIe scope**: only force Gen4 for ML/training, or also for any sustained GPU-bandwidth workload (e.g. external-GPU-like transfers, large model loads in Chrome)?
3. **Battery aggressiveness**: when on battery and you start a training run, is full performance (Gen4 + GPU boost + fans up) acceptable even at the battery-drain cost, or should it ask first?
4. **Intent override**: do you want a manual "force intent X" escape hatch (CLI/widget), or fully automatic?

---

*Next step on approval: Phase 0 hardware probe (read-only), then Phase 1 PCIe lever.*
