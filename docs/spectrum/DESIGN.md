# DESIGN — continuous power spectrum for luminos-power
# [CHANGE: claude-code | 2026-10-15]

Inputs to this design: `docs/spectrum/HARDWARE.md` (measured knobs, 2026-10-15, including the 19:40 finding that a
platform-profile change silently RESETS the PPT limits while the read-back still shows our value),
`docs/spectrum/CURRENT.md` (map of the daemon as it stands), `cmd/luminos-power/main.go` (adaptive governor,
writers, sensors), `cmd/luminos-power/fan_control.go` (Conductor PID — gated OFF in production, no
`LUMINOS_CONDUCTOR` in the service environment), `AGENTS.md` §5, §11, §12, BUG-198 addendum, BUG-200.
Nothing in this file has been implemented. It specifies ONE new file of pure Go plus a thin I/O layer, and
names what is deleted. Every number has a unit and a reason; numbers that are guesses say so and have a
measurement in §7 that replaces them.

---

## 0. Plain-English summary (read this even if you read nothing else)

1. Today the power manager is three light switches — Quiet, Balanced, Performance — plus a panic button
   (emergency) and a fan blast (burst). Every flick is a jump, every jump wakes the NVIDIA chip for ~20 s,
   and a switch can stick (BUG-200). Most of the bugs in CURRENT.md §7 are switches fighting each other.
2. The redesign replaces the switches with **one dimmer**: a single number, 0–100 %, that the daemon nudges a
   little every second. There are no modes, so there is nothing to enter, exit, flap between, or get stuck in.
3. The dimmer turns a dial the laptop's firmware really has: **how many watts the CPU may burn** (15–45 W,
   `ppt_*` files). We measured it: it is smooth, costs 33 ms per turn, and does **not** wake the NVIDIA chip.
4. Two hands rest on the dimmer. **Demand** pushes it up when programs are busy — at most 6 W per second, so
   power *grows* like a dimmer being turned, never flicked. **Heat** pulls it down as the chip nears 88 °C,
   settling at whatever wattage the cooling can actually carry away.
5. Whichever hand asks for less wins, and the result may move by only a few watts per second. Plugging in or
   unplugging the charger, or the NVIDIA GPU starting a game, just moves the *top end* of the dimmer — the
   level glides there, it does not jump.
6. **Fans are never touched by the daemon.** A gentle temperature→speed curve is stored in the laptop's
   embedded controller once, at install time: quiet below 55 °C, full speed only near 90 °C. The dimmer is
   what keeps the chip away from those temperatures unless it is genuinely working hard — that is how "least
   fan that holds it" is met without a fan controller that would wake the GPU on every write.
7. On battery the top of the dimmer is 25 W and slides lower as the battery drains; while the RTX 4050 is busy
   the CPU's top end drops to 30 W so the shared heatsink serves the GPU.
8. Nothing can overheat if the daemon crashes or hangs: the firmware's own 95 °C limit is independent of us,
   our dial only ever *reduces* power, and systemd restarts the daemon in seconds, after which it re-asserts.
9. Because a profile change silently resets the watt dial (measured today) and the read-back lies, the daemon
   rewrites the dial every 60 s and immediately after any profile / AC / resume event. It never reads it back.
10. The cost, from HARDWARE.md's table: 35 W gives 3.59 GHz at 87 °C versus 3.62 GHz at 41 W pinned on the
    95 °C limit — about 1 % sustained performance for 8 °C cooler and far less fan. That is the trade this
    design makes on purpose, and §6 says how it is proven rather than asserted.

---

## 1. Requirements (from Shawn, HARDWARE.md and the bug history)

| # | Requirement | Where it comes from |
|---|---|---|
| R1 | One continuous level; no discrete power states, no entry/exit thresholds, no counters | Shawn: "continuous spectrum … like a gradient"; BUG-161/200, NEW-1..3 |
| R2 | The daemon causes **zero** dGPU wakes (no profile writes, no fan-curve writes, no nvidia-smi at startup) | Shawn hates wakes; BUG-198 addendum, NEW-9 |
| R3 | Fan: light load ≈ 47 °C with little fan; heavier load → a higher *fair* ceiling; least fan that holds it; never high fan at 50–55 °C | Shawn's standing preference (memory) |
| R4 | Proven by measurement with thresholds stated in advance; old vs new A/B | Shawn; feedback_prove_dont_assert |
| R5 | Fixed sampling cadence (the variable tick broke every tick-counted hysteresis) | CURRENT.md §1, NEW-3 |
| R6 | PPT must be re-asserted on a timer and after resume/profile/AC events; never trust `ppt_*` read-back | HARDWARE.md 19:40 measurement |
| R7 | External interfaces in CURRENT.md §5 keep working; `PowerState` reports the level | task brief |
| R8 | Pure, property-testable core; ≤ ~350 lines of new Go | task brief; CURRENT.md §8 (zero tests today) |
| R9 | Read dGPU state only via `runtime_status`; never nvidia-smi while suspended; single writer per knob | BUG-078/160/182, DECISION 24 |

---

## 2. Brainstorm — fifteen genuinely different ways to make power continuous on this hardware

Scoring at the end of each idea: **S** = no discrete switches, **W** = no dGPU wakes, **F** = fan preferences (R3).
✓ satisfies, ~ partly, ✗ fails.

1. **Single scalar level, open-loop tables ("pure dimmer").** `L` from demand only; PPT, freq cap and EPP are
   lookup functions of `L`. Drives `ppt_*`, `scaling_max_freq`, EPP. Pros: trivially continuous, ~80 lines, no
   tuning. Cons: no thermal shaping — a sustained load pins the firmware's 95 °C limit with max fan, exactly
   the "beast" experience without the switch. Failure mode: none dangerous (firmware limit), but R3 fails under
   load. S✓ W✓ F✗.
2. **Temperature thermostat: PI/PID on Tctl with PPT as the actuator.** Hold a target temperature by
   modulating watts; demand ignored. Drives `ppt_*`. Pros: directly controls heat and therefore fan; the measured
   table says ~99 % of pinned performance at 88 °C; this is how AMD's own STAPM works, just with our target. Cons:
   at low load PPT sits at max, so a short burst gets 45 W instantly → die temperature spikes → EC fan reacts
   (noise on every burst); tuning; integral wind-up on cold days without anti-windup. Failure mode: hunting if the
   gain is too high (the Conductor's BUG-079, in watts instead of PWM). S✓ W✓ F~.
3. **Demand-following with slew limits ("ramp").** PPT follows CPU/iGPU utilisation with a bounded rate of
   change (W/s). Drives `ppt_*`, optionally freq cap. Pros: "gradually grows" literally; bursts stay quiet; cheap.
   Cons: open-loop thermally; utilisation is a weak proxy for the watts a workload needs (one thread at 100 %
   is 6 % average); the ramp delays throughput for the first seconds. Failure mode: a capped CPU reports higher
   utilisation → positive feedback (benign: it pushes the level up, settles at the mapping's fixed point —
   today's adaptive governor has the same loop and works). S✓ W✓ F~.
4. **Model-predictive control on the measured W→°C curve.** First-order thermal model (R_th ≈ 1.3 °C/W,
   intercept ≈ 42 °C from HARDWARE.md; τ to be measured); each tick pick the largest P whose predicted temperature
   stays under the ceiling over a 30 s horizon. Pros: anticipates instead of reacting; principled. Cons: the model
   drifts (ambient, dust, a different fan curve), needs online estimation, more code than the budget, and at 1 Hz
   with a firmware backstop it buys little over PI + feed-forward. Failure mode: a wrong model is confidently
   wrong. S✓ W✓ F~. → Used only as the *feed-forward term* of idea 2.
5. **Energy bucket (Intel PL1/PL2/tau emulation).** Keep a joule credit above a sustained level; burst while
   credit remains, drain at (P − P_sustained). Pros: deterministic burst length, no sensor dependence. Cons: ignores
   the actual temperature (dGPU heat, ambient), fixed tau mismatches the heatsink's real state, and "credit /
   no credit" is a phase unless smoothed. Also AMD's firmware already runs its own fast/slow PPT windows under our
   limits. S~ W✓ F~.
6. **Per-workload learned setpoints** (classify the process, remember the level it needed, apply at launch —
   today's `knownApps` pre-alloc table generalised). Pros: instant correct level for known apps. Cons: a
   classifier is a set of discrete classes = phases by another name (Conductor/BUG-079 heritage); tables rot; with
   a 5 s ramp the gain is a few seconds. S✗ W✓ F~.
7. **Fan-noise-aware objective.** Choose P to minimise perf-loss + λ·fan-duty using the curve's duty at each
   temperature. Pros: encodes "least fan" explicitly. Cons: needs an rpm/noise model; in practice the optimum is a
   constant temperature ceiling at the knee of the W→clock curve (1 % clock for the last 8 °C). → Used to
   *justify* the 88 °C ceiling, not as a runtime optimiser. S✓ W✓ F✓(as a constant).
8. **Battery-aware continuous ceiling.** `Pmax` and the frequency ceiling are smooth functions of state of
   charge (and could be of discharge rate). Pros: no "battery saver mode"; graceful. Cons: a ceiling only, not a
   controller; mild surprise ("slower at 20 %"). S✓ W✓ F– (orthogonal). → Adopted as a ceiling input.
9. **PSI / run-queue as the demand signal** instead of utilisation. `/proc/pressure/cpu some avg10` measures
   *starvation* (tasks waiting), which utilisation under a cap cannot distinguish from "busy and fine". Pros:
   robust to the cap-feedback of idea 3; free. Cons: avg10 lags ~10 s; reports waiting, not a single thread's
   wish for 5 GHz; needs a scale. S✓ W✓ F–. → Not in v1 (one more tuning knob); listed as the first v1.1 input.
10. **Soft-min (log-sum-exp / sigmoid) blend of the limits** instead of `min(demand, thermal, battery, dGPU)`,
    so the hand-over between which limit binds is itself smooth (C¹). Pros: no corners. Cons: a soft-min violates
    the binding constraint near the corner unless margin is added; at 1 Hz behind a slew limiter the corner is
    invisible anyway. S✓ W✓ F–. → Rejected: hard `min` + one slew limiter.
11. **Frequency-only continuous governor** (today's v4.1 extended: continuous cap + graded EPP, no PPT). Pros: no
    firmware writes at all. Cons: a frequency cap is a poor power proxy across thread counts (1.8 GHz × 16 threads
    ≈ 20 W, 5.1 GHz × 1 thread ≈ 15 W), starves single-thread work, and is the family that oscillated in
    BUG-048/053/055 because the firmware's PPT wall moved under it. S✓ W✓ F✗.
12. **Let the firmware do it**: one profile, stock STAPM, no daemon decisions. Pros: zero risk, zero wakes, zero
    code. Cons: no spectrum, no battery shaping, 95 °C pinned under load with stock fans. S✓ W✓ F✗. → Kept as the
    **control arm** of the A/B (§6): the new daemon must beat it, not just the old daemon.
13. **Closed-loop fan PID with direct duty writes (the Conductor).** The best possible answer to R3 on paper.
    Rejected by hardware: every duty write re-latches the EC curve via WMI devid 0x00110024, the same call that
    fires `Notify(NPCF,0xC0)` (HARDWARE.md, NEW-7) → one dGPU wake per tick. It is also disabled in production.
    S~ W✗ F✓.
14. **dGPU-aware budget share.** Treat the shared heatsink as one budget: `P_cpu_max = P_total − P_gpu`.
    Pros: addresses the real coupling (the EC sent PEGP 0xD1/0xD2 under sustained CPU load — the firmware itself
    renegotiates). Cons: GPU watts are unreadable without nvidia-smi (BUG-078/182), so the share must be a fixed
    yield, blended in over seconds. S✓ W✓ F✓. → Adopted with a fixed 30 W CPU ceiling while the dGPU is busy.
15. **Hysteresis-banded EPP on the level** (the 5 EPP strings chosen by `L` with wide bands and a dwell). Pros:
    uses the strongest free per-core lever. Cons: it *is* a step; invisible only if bands are wide and the two
    continuous dials dominate. S~ W✓ F–. → Specified in §3.6 as an optional, default-off extension.

**Decision:** combine **2 (thermal PI with the measured feed-forward) + 3 (demand-following with slew) + 8
(battery ceiling) + 14 (dGPU yield)** under a hard `min`, followed by ONE slew limiter that produces the single
continuous output `P_cmd` in watts. Fans: a static curve installed once (never written by the daemon). EPP:
fixed (15 is optional). Platform profile: never written. Idea 12 is the control arm. Everything else in CURRENT.md
§4 is deleted.

Why this combination and not thermostat-only (2): without the demand hand, every click would open the dial to
45 W instantly; the die (tiny thermal mass) spikes 20–30 °C in a second and the EC fan curve answers — that is the
fan noise Shawn complains about. Why not ramp-only (3): without the heat hand, sustained work pins 95 °C and max
fan. Together: short work stays quiet because the dial opens gradually; long work settles at the watts the cooler
can carry at 88 °C, which the table says costs ~1 % of clocks.

---

## 3. The design, precisely

### 3.1 Shape of the code

```
cmd/luminos-power/
  spectrum.go       pure core: Params, Inputs, State, Outputs, DefaultParams(), Step()   — no imports but math
  spectrum_test.go  property tests (§5)                                                   — new, required
  main.go           config, logger, socket, 1 Hz loop, sensors, writers, sd_notify         — slimmed from 2238 lines
  conductor.go      DELETED (gated off in production; references globals that go away)
  fan_control.go    DELETED (same; its PID cannot run without per-tick WMI writes — NEW-7)
scripts/luminos-fan-curve-install   one-time asusctl install of curve v6 on all three profiles (wakes once; run by a human)
scripts/spectrum-ab.sh              the A/B ladder + 1 Hz logger of §6
systemd/luminos-power.service       Type=notify, WatchdogSec=15, ExecStopPost fallback (§3.9)
```

`Step(p Params, s State, in Inputs) (State, Outputs)` is the whole decision. It allocates nothing, reads no
files, and knows no clock except `in.DT`. The I/O layer is: read sensors → `Step` → write what `Outputs` says
→ log/status. Target ≤ 180 lines for `spectrum.go`, ≤ 170 for the new parts of `main.go`.

### 3.2 Cadence

**Fixed 1.0 s `time.Ticker`.** No PSI poll, no 500 ms / 2 s / 10 s bands. Every constant below is per second
and the core uses real `in.DT` (monotonic clock), clamped to [0.5, 3] s so a late tick cannot produce a large
step; `in.DT > 5 s` means the machine slept (§3.8). Cost: six small reads and at most three WMI writes per
second — ~0.1 ms CPU plus ≤ 100 ms of blocking WMI time when the dial moves, nothing when it does not.
`cfg.Power.PollIntervalSecs` becomes honoured (clamped to [1, 2]); the recommended and default value is 1.

### 3.3 Inputs (I/O layer → `Inputs`)

| Field | Source | Unit | Notes |
|---|---|---|---|
| `DT` | monotonic time since the last tick | s | clamped in the core |
| `UtilAvg`, `UtilMax` | `/proc/stat` deltas over the tick (keep `readCPULoad`) | 0..1 | busiest single core is `UtilMax` |
| `IGPUBusy` | `/sys/class/drm/cardN/device/gpu_busy_percent` where `cardN/device/vendor == 0x1002` (resolved **once at startup by vendor**, never hard-coded card2) | 0..1 | the 780M shares the APU's PPT, so its demand must raise the budget |
| `TempC` | hwmon named `k10temp`, `temp1_input` (label `Tctl`), found by name at startup | °C | **not** the max of every hwmon (NEW-4) |
| `OnAC` | existing `readACState()` | bool | |
| `SOC` | `/sys/class/power_supply/BAT*/capacity` | 0..1 | 1.0 if unreadable or on AC |
| `DGPUBusy` | `runtime_status == "active"` **and** (`dgpuHasClients()` fd-walk **or** `offloadActive`) | bool | `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status`; the fd-walk runs only when active; never nvidia-smi |
| `PPTOwnerExternal` | `/run/systemd/units/invocation:nvidia-powerd.service` exists (one `stat`, no fork) | bool | game/train mode unmask nvidia-powerd, which negotiates CPU/GPU power through the SBIOS; two PPT writers would fight (§3.7) |
| `ProfileChanged` | `/sys/firmware/acpi/platform_profile` differs from last tick | bool | read is driver-cached, not a BIOS call — to be confirmed (§7 Q2) |
| `Resumed` | `/sys/power/suspend_stats/success` counter changed, or `DT > 5 s` | bool | |

Not read, deliberately: `ppt_*` (cache, lies — R6), fan rpm (asus-wmi DSTS call; the daemon does not need it),
nvidia-smi anything, RAM (luminos-ram's job), `/proc/*/comm` exec watching, input devices.

### 3.4 Core state, constants and equations

All constants live in `Params` (`DefaultParams()`), overridable from `[power]` in `/etc/luminos/config.toml`.

```
TickS           1.0   s     fixed loop period
PminW           15    W     lowest tested PPT; full load = 60 °C / 1.4 GHz — the quiet end of the dial
PmaxAcW         45    W     above ~40 W cooling binds (95 °C); 45 leaves burst room while the heatsink is cold
PmaxBatHiW      25    W     battery top at SOC ≥ 50 %: ~2.9 GHz all-core for ~55 % of the watts
PmaxBatLoW      15    W     battery top at SOC ≤ 15 %; linear in between (idea 8)
PmaxDgpuW       30    W     CPU top while the RTX 4050 is busy (idea 14): games rarely need more; heatsink to GPU
ThiAcC          88    °C    thermal ceiling on AC: 7 °C under the firmware limit; 35 W → 3.59 GHz = 99 % of pinned
ThiBatC         80    °C    battery ceiling (25 W settles ~75 °C by the model, so this rarely binds)
ThiDgpuC        85    °C    ceiling while the dGPU is busy (GPU heat raises Tctl for the same CPU watts)
T0C             42    °C    model intercept, measured 2026-10-15 (v5 curve, full load): T_ss ≈ T0 + Rth·P
RthCPerW        1.3   °C/W  model slope, same measurement; re-measure after curve v6 (§7 Q6)
KpWPerC         0.75  W/°C  proportional gain; fast loop gain Kp·R_jc ≈ 0.75·0.6 ≈ 0.45 → damped (R_jc = die→heatsink)
KiWPerCS        0.05  W/(°C·s)  integral: a 2 °C standing error moves 0.1 W/s; removes model/ambient error in ~minutes
IminW/ImaxW     −25/+10 W   integral clamp (anti-windup backstop)
IleakS          300   s     integral decays toward 0 whenever the thermal hand is not the one on the dial
TauTempS        2     s     Tctl EMA — per-core spikes are the firmware's problem, not ours
TauDemandS      6     s     demand peak-hold release: a 1 s-on/1 s-off workload holds its level
TauGpuS         5     s     dGPU busy/idle blended in over 5 s (no step when a game starts)
D0, D1          0.08, 0.80  demand → level map: below 8 % busy = floor, above 80 % = ceiling
SlewUpWS        6     W/s   "gradually grows": floor→AC ceiling in 5 s
SlewDownWS      3     W/s   release is slower than attack (intermittent work keeps its budget)
SlewDownHotWS   12    W/s   release rate at Thi+3 °C and beyond, linear between (continuous, not a mode)
WriteDeadbandW  2     W     do not write a PPT change smaller than this (firmware regulation is coarser)
RefreshS        60    s     unconditional PPT re-write period (R6: resets we cannot detect)
FreqBatFloorKHz 3000000     battery cap at level 0 (a click still gets 3 GHz on one core)
FreqBatCeilKHz  4000000     battery cap at the battery's top level (the last GHz costs ~50 % more energy per op)
FreqSlewKHzS    200000      cap glides ≤ 200 MHz/s (AC↔battery is a glide, not a jump)
FreqDeadbandKHz 100000      write threshold
EPP             "balance_power"  fixed for the whole spectrum (§3.6)
```

**State** (`State`, all floats unless noted): `TempS` (°C), `Demand` (0..1, peak-hold), `I` (W, integral),
`Gpu` (0..1 blend), `P` (W, the dial), `F` (kHz, battery cap glide), `PptWritten` (int W), `FreqWritten` (kHz),
`SinceRefreshS` (s), `Seeded` (bool).

**Step**, in order (dt already clamped; `lerp(a,b,x)=a+(b−a)·x`; `clamp01`):

```
0  if !Seeded || in.Resumed:  TempS=TempC; Demand=0; I=0; Gpu=DGPUBusy?1:0; if !Seeded {P=PminW; F=hwmax}
                              Seeded=true; force=true

1  TempS  += (1−exp(−dt/TauTempS))·(TempC − TempS)                                  // smoothed Tctl

2  dRaw    = max(UtilAvg, UtilMax/4, 0.8·IGPUBusy)                                   // 1 thread@100 % → 0.25 → ~22 W
   Demand  = max(dRaw, Demand·exp(−dt/TauDemandS));  if Demand < 0.005 {Demand = 0}  // peak-hold, exponential release
   Ldem    = clamp01((Demand − D0)/(D1 − D0))

3  Gpu    += (1−exp(−dt/TauGpuS))·((DGPUBusy?1:0) − Gpu)
   PmaxSrc = OnAC ? PmaxAcW : lerp(PmaxBatLoW, PmaxBatHiW, clamp01((SOC − 0.15)/0.35))
   Pmax    = lerp(PmaxSrc, min(PmaxSrc, PmaxDgpuW), Gpu)                              // dGPU yield, blended
   ThiSrc  = OnAC ? ThiAcC : ThiBatC
   Thi     = lerp(ThiSrc, min(ThiSrc, ThiDgpuC), Gpu)

4  e       = Thi − TempS                                                             // °C of headroom (+ = cool)
   Pff     = (Thi − T0C)/RthCPerW                                                    // 35.4 W at 88 °C — the model's answer
   PthRaw  = Pff + KpWPerC·e + I
   Pth     = clamp(PthRaw, PminW, Pmax)                                              // the heat hand

5  Pdem    = PminW + Ldem·(Pmax − PminW)                                             // the demand hand
   Ptarget = min(Pdem, Pth)
   binding = Pth <= Pdem ? "thermal" : "demand"   (+ "battery"/"dgpu" when Pmax < PmaxAcW and Ptarget == Pmax — display only)

6  // integral: conditional integration = anti-windup. Integrate only when the heat hand is on the dial (or we are
   // already too hot) AND the raw output is not pinned against a limit in the direction e would push it.
   if (Pth <= Pdem || e < 0) && (PthRaw < Pmax || e < 0) && (PthRaw > PminW || e > 0):
        I = clamp(I + KiWPerCS·e·dt, IminW, ImaxW)
   else: I *= exp(−dt/IleakS)

7  down    = SlewDownWS + (SlewDownHotWS − SlewDownWS)·clamp01((TempS − Thi)/3)      // 3 → 12 W/s smoothly
   P       = clamp(Ptarget, P − down·dt, P + SlewUpWS·dt)                             // ONE slew limiter → the dial
   // NOTE: P is not clamped to Pmax here on purpose: when Pmax drops (unplug, game start) P glides down at `down`.

8  Level   = (P − PminW)/(PmaxAcW − PminW)                                            // 0..1 on a FIXED scale; battery tops out ~0.33
   pptW    = round(P)
   Ftarget = OnAC ? hwmax : FreqBatFloorKHz + clamp01((P − PminW)/(PmaxSrc − PminW))·(FreqBatCeilKHz − FreqBatFloorKHz)
   F       = clamp(Ftarget, F − FreqSlewKHzS·dt, F + FreqSlewKHzS·dt)

9  SinceRefreshS += dt
   WritePPT  = force || in.ProfileChanged || SinceRefreshS >= RefreshS || |pptW − PptWritten| >= WriteDeadbandW
   if in.PPTOwnerExternal {WritePPT = false}                   // §3.7: yield the dial to nvidia-powerd, keep tracking
   WriteFreq = force || |F − FreqWritten| >= FreqDeadbandKHz
   WriteEPP  = force || in.ProfileChanged                      // asusd's linked-EPP rewrites EPP on a profile change
   if WritePPT {PptWritten = pptW; SinceRefreshS = 0};  if WriteFreq {FreqWritten = F}
   // when the external owner releases the dial, PptWritten is stale by design → the next refresh or delta re-asserts;
   // the I/O layer also sets force on the external→internal edge so it happens on the very next tick.
```

Outputs: `Level`, `PptW` (int; spl = sppt = fppt = PptW in v1 — see §7 Q9 for burst headroom), `FreqCapKHz`,
`EPP`, `WritePPT/WriteFreq/WriteEPP`, `Binding` (string, display only), `TargetTempC`, `PmaxW`, `Demand`.

Worked trajectories (model only; §6 measures them):
- *Idle desktop*: Util ≈ 0.05 → Demand ≈ 0.05 → Ldem = 0 → P = 15 W. Writes: one every 60 s. Tctl wherever
  curve v6 and ~8 W settle (expected 47–52 °C, §3.5). Firmware limit irrelevant.
- *Click / page load*: UtilMax 1.0 for 1 s → dRaw 0.25 → Ldem 0.24 → Pdem 22 W → P climbs 15→21 in 1 s, then
  releases over ~6 s. A single core at full boost needs ~10–15 W package, so the click is not starved; 16
  threads for one second get 21 W instead of 45 W — quieter, slightly slower, by design.
- *16-thread compile from cold*: P 15→45 W in 5 s (first 5 s average ~30 W ≈ 2.9 GHz vs 3.6 GHz: ~20 % slower for
  five seconds, ~2 % on a 60 s job). Tctl climbs; the heat hand starts at ~75 °C (Pth = 35.4 + 0.75·13 ≈ 45),
  is at 41 W by 80 °C, 38 W by 84 °C, 35 W at 88 °C; the integral then trims the last degrees over ~2 min.
  Expected peak ≤ 92 °C, steady ≤ 90 °C, fan ≤ ~97 % (v6 at 88 °C) — "fair ceiling under heavy load".
- *Unplug while compiling*: Pmax 45→25; P glides 45→25 at 3 W/s (7 s); F glides 5.14→4.0 GHz at 0.2 GHz/s.
- *Game starts on the RTX 4050*: Gpu blends 0→1 over 5 s; Pmax 45→30 and Thi 88→85 follow the blend; P glides.
- *ROG key pressed under load*: firmware resets PPT to its table (51.7 W measured); next tick `ProfileChanged`
  → PPT and EPP re-written; worst case 1 s at the firmware table plus the 60 s refresh for resets we cannot see.

### 3.5 Fans and the platform profile: set once, by a human, never by the daemon

- **Platform profile: the daemon never writes it.** Not at startup either: if the profile is already what the
  install step left (balanced), `setProfile` would be a no-op anyway; if a user changed it with the ROG key,
  writing it back would be a wake plus a PPT reset. The daemon reads it every tick only to detect a change
  (R6) and reports it in `PowerState.profile` (title-cased sysfs value, as today). `setProfile()` stays in the
  code as the single choke point (AGENTS.md §11) behind config `assert_profile = ""` (default: never); it is
  enabled only if §7 Q10 shows the Quiet profile clamps our PPT writes.
- **Install step (once, `scripts/luminos-fan-curve-install`, run by a person, 3 profiles × 4 asusctl calls, wakes
  the dGPU a few times — acceptable because it is manual and once):** write curve v6 to `quiet`, `balanced` and
  `performance` so a profile change by hand never changes fan behaviour (BUG-190's "stale curve on the other
  profile" class disappears), and set in `/etc/asusd/asusd.ron`: `change_platform_profile_on_ac: false`,
  `change_platform_profile_on_battery: false` (otherwise asusd itself flips the profile on every cable event =
  wake + PPT reset). This is an `/etc` change → AGENTS.md §9 table + LUMINOS_DECISIONS.md the same day (rule 10).
  asusd persists custom curves in `/etc/asusd/fan_curves.ron` and re-applies them per profile at boot.
- **Curve v6** (cpu and gpu fans; mid fan at ≈ 2/3 until the top), 8 EC points, duty in %:

  | °C | 30 | 40 | 50 | 60 | 70 | 80 | 85 | 90 |
  |---|---|---|---|---|---|---|---|---|
  | cpu / gpu | 0 | 10 | 20 | 35 | 52 | 72 | 88 | 100 |
  | mid | 0 | 5 | 13 | 23 | 35 | 48 | 70 | 100 |

  asusctl form: `--fan cpu --data 30c:0%,40c:10%,50c:20%,60c:35%,70c:52%,80c:72%,85c:88%,90c:100%`,
  same for `gpu`; `--fan mid --data 30c:0%,40c:5%,50c:13%,60c:23%,70c:35%,80c:48%,85c:70%,90c:100%`.
  How it meets R3 with no controller: a static temp→duty map *is* a floating target — the chip settles where
  heat in equals heat out at that duty. Light load (~8–10 W) settles low with little fan (v5 held 48–50 °C at
  ~2100 rpm in the BUG-079 test; v6 gives less duty at 47 °C than v5's 35 %, so expect 47–52 °C — the A/B
  threshold is ≤ 55 °C and the tuning rule is "+5 % on the 40/50 °C points per 2 °C over 52"). "Never high fan
  at 50–55 °C": v6 is 20–27.5 % there (v5 was 55–72 % and burst made it 100 %). "Fair ceiling under heavy load":
  the heat hand holds 88 °C where v6 is ~97 % — full fan only when the chip is truly at its sustained limit.
  "Least fan that holds it": below the ceiling the fan is whatever the curve gives at the settled temperature,
  which is the least duty consistent with that temperature by construction; the PPT dial, not the fan, does the
  holding. Burst mode, zones and the Conductor are gone: nothing else ever writes a curve (and
  `scripts/luminos-train-mode`'s 60 s asusctl keep-alive must be removed in the same change — with v6 on every
  profile it has nothing to protect and would be the last wake source left).
- Startup verification (read-only): the daemon reads `pwm1_auto_point{1..8}_pwm` on the `asus_custom_fan_curve`
  hwmon (found by name) once and logs `fan curve: v6 OK` or `fan curve: MISMATCH (run luminos-fan-curve-install)`.
  It never writes. (§7 Q2 confirms the read is cache-only.)

### 3.6 EPP — five strings, zero phases

v1: **fixed `balance_power` on AC and battery**, written at startup, after a profile change (asusd's
`platform_profile_linked_epp` rewrites it) and after resume. Reasoning: EPP is the one lever that cannot be made
continuous, so the only way it can never be a phase is to not move it. It sets the *floor* of per-core eagerness
(PPT and the cap only limit from above); `power` was measured sluggish enough that v4.4 grew an input watcher to
flip it. Energy cost at idle is near zero (C-states dominate) and the A/B's idle-watt threshold (§6) guards it.
`performance` is never used: the dial already gives performance.

Optional v1.1 (`epp_mode = "banded"`, default `"fixed"`): EPP = band(Level) with hysteresis 0.08 and a 15 s
dwell: `power` below 0.25, `balance_power` 0.25–0.60, `balance_performance` above 0.60 (entry thresholds; exit
thresholds 0.08 lower; a change is allowed only ≥ 15 s after the last one). Still no `performance`. Each change is
16 sysfs writes, no BIOS. It is a step, and it is off until the A/B shows a measurable gain for it.

### 3.7 dGPU interaction

- The only dGPU facts the daemon uses are `runtime_status` (free) and the fd-walk while active. `DGPUBusy`
  lowers `Pmax` to 30 W and `Thi` to 85 °C through a 5 s blend. When the card goes back to sleep the ceiling
  returns through the same blend; P follows at the slew rates.
- Startup makes **no** nvidia call (`initGPUTGP` is deleted; the TGP manager was a no-op anyway — BUG-069).
  `offload_start/stop` keep their nvidia-smi pin path unchanged (explicit request, DECISION 23) and set
  `offloadActive`, which counts as busy.
- **PPT ownership yields to nvidia-powerd.** While `PPTOwnerExternal` (game/train mode unmasked it) the core keeps
  computing but `WritePPT` is forced false, the status shows `ppt_owner: "nvidia-powerd"`, and the frequency cap
  keeps working. When powerd goes away, `force` re-asserts on the next tick. Single writer per knob (DECISION 24)
  is kept without a second controller and without a fight at the 60 s refresh.

### 3.8 Start-up, shutdown, crash, suspend

- **Start-up** (0 dGPU wakes — a stated A/B threshold, fixing NEW-9): resolve hwmon/DRM paths by name/vendor;
  governor `powersave` once; EPP; freq cap = hwmax; PPT = 15 W (the dial starts at the floor and the demand hand
  opens it — the same gradual behaviour at boot as always); verify the fan curve (read-only); read the profile;
  `sd_notify("READY=1")`; start the ticker. No profile write, no curve write, no nvidia-smi.
- **Every tick** ends with `sd_notify("WATCHDOG=1")`. Unit: `Type=notify`, `WatchdogSec=15`, `Restart=always`,
  `RestartSec=3` → a hung daemon is killed and restarted within 15 s and re-asserts everything (a ~12-line
  unixgram write to `$NOTIFY_SOCKET`, no dependency).
- **Clean shutdown (SIGTERM)**: write PPT 45 W to all three files = "wide open, stock-like" (the stock balanced
  table measured 44–52 W under load and is cooling-bound at 95 °C, so this loses nothing and is safe), cap →
  hwmax, EPP left as is, remove the socket. The *true* firmware table can only be restored by a profile write (one
  wake), which is left to a human: `asusctl profile set balanced`.
- **Crash (SIGKILL / panic)**: `ExecStopPost=/bin/sh -c 'for f in ppt_pl1_spl ppt_pl2_sppt ppt_fppt; do echo 45 >
  /sys/devices/platform/asus-nb-wmi/$f; done; for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
  cat ${c%scaling_max_freq}cpuinfo_max_freq > $c; done'` runs even on failure, so a dead daemon never leaves a
  15 W laptop; systemd then restarts it.
- **Why the CPU cannot cook**: the firmware's 95 °C limiter is independent of the daemon and was observed doing its
  job at every limit ≥ 45 W; our writes only ever *lower* the ceiling; the EC fan curve runs in the EC. The failure
  modes that remain are performance ones (stuck low until restart), bounded by the watchdog and `ExecStopPost`.
- **Suspend/resume**: `Resumed` re-seeds `TempS`, zeroes `Demand`, `I`, keeps `P`, and forces all writes (§7 Q3
  says whether the firmware resets PPT on resume; the design re-asserts regardless).

### 3.9 Write-rate limits (WMI hygiene)

PPT: at most one 3-file write per tick (1 Hz), only when `|Δ| ≥ 2 W`, on an event, or at the 60 s refresh;
each file write ≈ 33 ms (measured) and causes no notify (12 writes → 0 notifies, 0 rpm_resume). Expected budget:
refresh 180 calls/h + ramps ≈ ≤ 1 000 calls/h at busy mixed use ≈ 33 s/h of WMI time. Freq cap: ≤ 1 Hz, ≥ 100 MHz
delta. EPP: on events only. Profile / fan curve / nvidia-smi: **never** (except the explicit offload socket
request). The daemon exports `wmi_writes_total` in its status so §6 can compare it with the kprobe count.

### 3.10 What is deleted, what stays

**Deleted** (CURRENT.md references): beast mode (§4.2, BUG-200 with it), quiet-idle (§4.1), thermal zones (§4.3),
emergency (§4.4, NEW-1/2 with it), thermal burst (§4.5, BUG-190's class), GPU TGP manager (§4.7, BUG-069 no-op),
Conductor + fan PID + intent broadcast (§4.8; luminos-ram/ai keep their handlers — they simply receive nothing,
as today), interactive input watcher and exec/pre-alloc watcher (§4.9), RAM-pressure bonus, SPI index, PSI
sleep bands, `applyAggressiveFanCurve`/`applyBurstFanCurve`/`restoreBurstProfiles`, `initGPUTGP`, `eppForProfile`,
every tick-counter constant, `readCPUTemp` (max-of-everything), the `profile` writes in `applyACTransition`.

**Stays** (CURRENT.md §5): the socket and all five request types with identical reply shapes; `offload_*`
(`applyOffloadPin`, `nvidiaCtl`, `regateUVM`, `/run/luminos/offload.active`); `report_power` to luminos-ai — now
sent on every ≥ 5 % level change and at least every 60 s (fixes NEW-5); the non-power AC side effects (Wi-Fi
power save, KSM, display Hz) unchanged; `readACState`, `readCPULoad`, `setAllMaxFreq`, `setAllEPP`,
`setAllGovernor`, `writeSysfs`, `dgpuRuntimeSuspended`, `dgpuHasClients`; `/var/log/luminos/power.log`;
`setProfile` + `noteProfileChange` (unused by default).

**`PowerState`** keeps every existing key and adds the dial:
```json
{"on_ac":true,"cpu_temp_c":61.2,"gpu_load":0,"epp":"balance_power","profile":"Balanced","updated_at":"…",
 "level":0.42,"ppt_w":28,"ppt_target_w":28,"pmax_w":45,"temp_target_c":88,"demand":0.37,"binding":"demand",
 "freq_cap_khz":5137904,"dgpu":"suspended","ppt_owner":"luminos-power","wmi_writes_total":1234}
```
`gpu_load` is kept for consumers but is 0 (it came from nvidia-smi, which is gone); `profile` is whatever the
firmware reports; `epp` is the string actually written.

**Log line** (one per 30 s, plus one per event), greppable and keeping the Plasma widget alive (NEW-6):
`spectrum: level=42% ppt=28W tgt=28W pmax=45W temp=61.2C thi=88C demand=0.37 binding=demand dgpu=suspended
profile=Balanced epp=balance_power ac=1 writes=1234`. Old strings (`beast mode`, `thermal zone`, `adaptive cap →`,
`thermal burst`, `GPU TGP`, `idle → Quiet`) stop existing; the handbook §4 and BUGS.md runbooks that grep them need
a one-line note in the same change.

### 3.11 Config keys (`/etc/luminos/config.toml`, `[power]`, all optional, defaults = `DefaultParams()`)

`poll_interval_secs=1`, `pmin_w=15`, `pmax_ac_w=45`, `pmax_bat_hi_w=25`, `pmax_bat_lo_w=15`, `pmax_dgpu_w=30`,
`t_hi_ac_c=88`, `t_hi_bat_c=80`, `t_hi_dgpu_c=85`, `slew_up_w_s=6`, `slew_down_w_s=3`, `refresh_s=60`,
`epp="balance_power"`, `epp_mode="fixed"`, `freq_bat_floor_mhz=3000`, `freq_bat_ceil_mhz=4000`,
`assert_profile=""`, `ppt_burst_headroom_w=0` (§7 Q9).

---

## 4. Implementation notes for `spectrum.go` (what the implementer should not have to guess)

```go
type Params struct { TickS, PminW, PmaxAcW, PmaxBatHiW, PmaxBatLoW, PmaxDgpuW, ThiAcC, ThiBatC, ThiDgpuC,
    T0C, RthCPerW, KpWPerC, KiWPerCS, IminW, ImaxW, IleakS, TauTempS, TauDemandS, TauGpuS, D0, D1,
    SlewUpWS, SlewDownWS, SlewDownHotWS, WriteDeadbandW, RefreshS float64
    FreqBatFloorKHz, FreqBatCeilKHz, FreqSlewKHzS, FreqDeadbandKHz, HwMaxKHz int; EPP string }
type Inputs struct { DT, UtilAvg, UtilMax, IGPUBusy, TempC, SOC float64
    OnAC, DGPUBusy, PPTOwnerExternal, ProfileChanged, Resumed bool }
type State struct { TempS, Demand, I, Gpu, P, SinceRefreshS float64; F, PptWritten, FreqWritten int; Seeded bool }
type Outputs struct { Level, TargetTempC, PmaxW, Demand float64; PptW, FreqCapKHz int; EPP, Binding string
    WritePPT, WriteFreq, WriteEPP bool }
func DefaultParams(hwMaxKHz int) Params
func Step(p Params, s State, in Inputs) (State, Outputs)   // pure; State passed and returned by value
```
- Clamp `in.DT` to [0.5, 3] *inside* `Step`; detect `Resumed` *outside* (counter + gap) and pass it in.
- Use `math.Exp` for every time constant so dt-robustness (P12) holds; never "0.7·old + 0.3·new" per tick.
- Integer watts: `round` once, in step 8; compare written vs commanded in integers.
- The I/O layer writes in the order `ppt_pl1_spl`, `ppt_pl2_sppt`, `ppt_fppt` with the same value (v1), checks
  each `writeSysfs` error, logs a warn once per minute on failure, and counts successes in `wmi_writes_total`.
- Status snapshot behind a `sync.RWMutex`; the socket handler reads the snapshot, never the loop's state.
- `[CHANGE: claude-code | date]` tags on every new block (AGENTS.md §5.2); `cmd/` edits need Shawn's go (§11).

---

## 5. Verification plan A — properties of the pure core (must hold for ANY input)

Implemented in `spectrum_test.go` with a seeded PRNG: 10 000 random walks × 300 steps, inputs drawn from
Util ∈ [0,1], Temp ∈ [20,105] °C, SOC ∈ [0,1], random booleans, DT ∈ {0.5, 1, 1.7, 3, 7}; plus the targeted
scenarios. All tolerances 1e-6 unless stated.

| # | Property | Check |
|---|---|---|
| P1 | Bounded | `PminW ≤ P ≤ PmaxAcW` always; and `P ≤ Pmax_eff` **or** `P < P_prev` (gliding down after a ceiling drop) |
| P2 | Slew = continuity | `P_prev − down(T)·dt ≤ P ≤ P_prev + SlewUpWS·dt` with `down ≤ 12`; this is the formal "no switches" |
| P3 | Monotone in demand | same State, same Temp: increasing any of UtilAvg/UtilMax/IGPUBusy never lowers `Ptarget` or `P` |
| P4 | Monotone in temperature | same State, same demand: higher TempC never raises `Ptarget` |
| P5 | Idle fixed point | after ≥ 120 idle steps (Util 0, Temp 45) from any state: `P == PminW`, `I == 0 ± 1e-3`, and `WritePPT` true only on refresh ticks |
| P6 | Hot convergence | Temp = Thi + 5 held (no plant), Util 1: `P` reaches `PminW` within 90 steps and stays (the P term takes 3.75 W off at once; the integral at Ki·5 °C = 0.25 W/s needs ~67 s to pull `PthRaw` from 31.7 W to the floor — with a real plant the temperature falls long before that) |
| P7 | Write deadband | `WritePPT ⇒ force ∨ ProfileChanged ∨ refresh ∨ |PptW − PptWritten_prev| ≥ 2`; never true under `PPTOwnerExternal` |
| P8 | Purity | `Step(p,s,in)` twice → identical outputs; no global state (run tests with `-race`, parallel) |
| P9 | Events | `Resumed ∨ ProfileChanged ⇒ WritePPT ∧ WriteEPP` (unless external owner); `Resumed ⇒ Demand == 0 ∧ I == 0` |
| P10 | Frequency cap | on AC converges to hwmax; on battery monotone non-decreasing in `P`; `|ΔF| ≤ FreqSlewKHzS·dt`; floor ≤ F ≤ hwmax |
| P11 | Level | `Level == (P − PminW)/(PmaxAcW − PminW)` ∈ [0,1] |
| P12 | dt robustness | two steps of dt=0.5 vs one of dt=1 with constant inputs: `|ΔP| ≤ 0.5 W`, `|ΔTempS| ≤ 0.5 °C` |
| P13 | Ceiling change is a glide | flipping OnAC or DGPUBusy changes `P` by at most `down·dt` per step, never a jump |
| P14 | Anti-windup | with Temp = 20 °C held for 1 000 steps, `I ≤ ImaxW`; with Temp = 105 °C, `I ≥ IminW`; after returning to Thi, `|e|` is below 1 °C within 300 steps (model-perfect plant simulated by `T += dt/60·(T0 + Rth·P − T)`) |
| P15 | Battery taper | `Pmax_eff` is non-decreasing in SOC and continuous (|ΔPmax| ≤ 0.3 W per 1 % SOC) |

A simulated plant (P14) also gives a cheap regression test for the tuning: overshoot above Thi must be ≤ 4 °C
and settle within 180 s in simulation before anyone touches the laptop.

---

## 6. Verification plan B — live A/B on the G14, thresholds fixed before the first run

Three arms, identical script, same room, charger plugged, dGPU asleep, no browser: **A** = old daemon as shipped
(v5 curve), **B** = new daemon (v6 curve), **C** = control: no daemon, profile balanced, v6 curve (idea 12).
Optional **B′** = new daemon with v5, to separate controller from curve if B's temps surprise.

Script `scripts/spectrum-ab.sh` logs at 1 Hz: Tctl, package W (the same reader HARDWARE.md used — turbostat or
`/sys/class/powercap`, §7 Q4), fan1/2/3 rpm (only if §7 Q5 shows reads are free; else every 5 s), the three
`ppt_*` files, `runtime_status`, and `status` from the socket (level, ppt_w, binding, wmi_writes_total). In
parallel, the BUG-198 probes count `rpm_resume` on 0000:01:00.0 and `asus_wmi_evaluate_method3` calls.

**Ladder** (one run ≈ 28 min per arm): 5 min idle → `stress-ng --cpu 4 --cpu-method matrixprod` 2 min (≈25 %)
→ `--cpu 8` 2 min (≈50 %) → `--cpu 16` 5 min (100 %) → 5 min idle → bursts: 3× `sysbench cpu --threads=16
--time=10 run` from idle with 90 s gaps, 3× `--threads=1 --time=10`, then `--threads=16 --time=120` once.
Then the event tests: suspend 2 min + resume; ROG-key profile cycle under `--cpu 16`; `systemctl restart`
three times; unplug/replug twice; `kill -STOP` the daemon for 30 s (B only).

| Metric | How measured | Threshold for B | Why this number |
|---|---|---|---|
| dGPU wakes caused by the daemon | `rpm_resume` count on 01:00.0 over the whole run incl. 3 restarts, 2 cable events, 1 resume (no GPU clients) | **0** (A measured ≈ 1.1/h) | R2; every daemon-side cause is gone; a single wake means a path was missed |
| Firmware calls per hour | kprobe count ÷ hours; cross-check with `wmi_writes_total` | ≤ 1 500/h and **0** fan-curve (0x00110024) / profile (0x120075) calls | 60 s refresh = 180/h, ramps ≤ ~1 000/h; notifies come only from the forbidden devids |
| Idle package W (last 3 min of each idle stage) | package W median | B ≤ A + 0.5 W and B ≤ C + 0.5 W | the only new idle cost is EPP balance_power vs power; 0.5 W ≈ 5 % of idle platform draw and below brightness noise; if exceeded, idle EPP falls back to `power` |
| Idle Tctl / fan | median over the same window | Tctl ≤ 55 °C; fan ≤ 2 500 rpm | R3 "≈47 °C light load" with v6's lighter duty; 52–55 triggers the +5 % tuning rule of §3.5 |
| "Never high fan at 50–55 °C" | max fan rpm over all samples with Tctl ∈ [50,55] | ≤ 40 % of full-speed rpm (≤ 2 800 rpm if full = 7 000) | R3 verbatim; v6 gives 20–27.5 % duty there; A is expected to fail this |
| 16-thread sustained (last 60 s of the 5 min stage) | Tctl mean / peak; stress-ng bogo-ops/s | mean ≤ 90 °C, peak ≤ 93 °C; ops ≥ 0.95 × A and ≥ 0.95 × C | the table: 35 W ≈ 99 % of the 95 °C-pinned clock; 5 % covers run-to-run noise; A/C sit at 95 °C |
| 25 % / 50 % stages | Tctl mean, fan median | Tctl ≤ A + 5 °C; fan ≤ A | R3 trades a few degrees for less fan — but not more fan |
| Load-step response | time from `stress-ng` start to `ppt_w ≥ 0.9·pmax_w` in the log | ≤ 8 s | 5 s ramp + 1 s tick + margin; A reached beast after ~5 s + a wake |
| Short burst, 16 threads, 10 s | sysbench events/s, median of 3 | ≥ 0.90 × A | the 5 s ramp averages ~75 % of the ceiling → ≈ 92 % over 10 s; a bigger loss means the ramp is too slow (raise `slew_up_w_s`) |
| Short burst, 1 thread, 10 s | median of 3 | ≥ 1.00 × A | no freq cap on AC and EPP balance_power vs A's 1.8 GHz ramp at EPP power — must not regress |
| Sustained 120 s, 16 threads | events/s | ≥ 0.95 × A | same as the stage metric, via the benchmark |
| Continuity | from the 1 Hz log of `ppt_w` | max rise ≤ 6 W/s, max fall ≤ 12 W/s; journal contains no `beast`/`Quiet`/`zone`/`burst` strings | R1 as data |
| ROG key under load | journal + package W | `profile changed externally … re-asserted` within 2 s; package W back under `ppt_w`+3 within 5 s | R6 |
| Suspend/resume | journal + package W under a 30 s `--cpu 16` after resume | re-assert logged; W under `ppt_w`+3 | R6 |
| Restart / crash | `rpm_resume` during `systemctl restart` ×3; `kill -9` then watch | 0 wakes; recovery ≤ 5 s; `kill -STOP` → restarted ≤ 15 s (watchdog) | §3.8 |
| Stop | `systemctl stop` then `--cpu 16` 30 s | package W ≈ cooling-bound (≥ 38 W) — the laptop is not left slow | §3.8 |

A metric that fails is tuned (constants in §3.4 are the knobs) and the **whole** ladder re-run; the thresholds
do not move. B must beat A on wakes, fan and temperature and tie A on throughput; B must beat C on fan and
temperature at ≤ 5 % throughput cost, or the daemon is not earning its keep.

---

## 7. Risks and open questions — each with the one-line measurement that settles it

Replace `<pkgW>` with the package-power reader used for HARDWARE.md (Q4). `PPT=/sys/devices/platform/asus-nb-wmi`.

| # | Question / risk | Measure with | Design consequence |
|---|---|---|---|
| Q1 | **Profile change resets PPT — MEASURED YES (19:40).** Is it the ASUS firmware or `amd-pmf`'s static slider doing the reset? | `sudo modprobe -r amd_pmf; for f in ppt_pl1_spl ppt_pl2_sppt ppt_fppt; do echo 15 \| sudo tee $PPT/$f; done; stress-ng --cpu 16 -t 90 & sleep 20; <pkgW>; echo balanced \| sudo tee /sys/firmware/acpi/platform_profile; sleep 20; <pkgW>` | if the reset vanishes without amd_pmf, blacklisting `amd_pmf` (an `/etc` change, rule 10) removes a competing writer; refresh stays either way |
| Q2 | Are per-tick reads of `platform_profile` and the fan-curve hwmon points free of BIOS calls (DSTS)? | `sudo bpftrace -e 'kprobe:asus_wmi_evaluate_method3 { @[comm,kstack(2)] = count(); }' & for i in $(seq 60); do cat /sys/firmware/acpi/platform_profile /sys/class/hwmon/hwmon*/pwm1_auto_point1_pwm >/dev/null; sleep 1; done; kill %1` → expect 0 | if not free: detect profile changes via a `udev`/`acpi` netlink event instead of polling; read the curve never |
| Q3 | Does resume from suspend reset PPT? Does an AC plug/unplug (firmware, not asusd)? | set 15 W as in Q1; `systemctl suspend`; after resume `stress-ng --cpu 16 -t 30 & sleep 15; <pkgW>`; repeat with a cable pull instead of suspend | design re-asserts on both regardless; the answer sets expectations for the 1 s window |
| Q4 | Is package power readable without turbostat? | `ls /sys/class/powercap/; cat /sys/class/powercap/intel-rapl:0/name; a=$(cat /sys/class/powercap/intel-rapl:0/energy_uj); sleep 1; b=$(cat /sys/class/powercap/intel-rapl:0/energy_uj); echo $(( (b-a)/1000000 )) W` | if yes: the A/B logger uses it, and v1.1 can use measured watts as the demand signal (far better than utilisation) |
| Q5 | Do fan rpm reads (`fan1_input`) make BIOS calls or notifies? | the Q2 probe plus `kprobe:acpi_ev_queue_notify_request` while `for i in $(seq 60); do cat /sys/class/hwmon/hwmon*/fan1_input >/dev/null; sleep 1; done` | if they notify: the A/B harness samples rpm every 5 s only; the daemon never reads rpm (already true) |
| Q6 | Re-measure the W→°C line with curve v6 (R_th, T0) | after `luminos-fan-curve-install`: for L in 15 20 25 30 35 40; set all three to $L; `stress-ng --cpu 16 -t 180`; log Tctl and `<pkgW>` over the last 60 s | updates `T0C`/`RthCPerW` (the integral covers the rest) |
| Q7 | Does the EC interpolate the 8-point curve linearly or in steps, and is its temperature axis Tctl? | with v6 installed: `stress-ng --cpu 8 -t 240 & for i in $(seq 240); do echo $(date +%s) $(cat /sys/class/hwmon/<k10temp>/temp1_input) $(cat /sys/class/hwmon/<asus>/fan1_input); sleep 1; done` → rpm vs Tctl should be a smooth line with the knees at 50/60/70 °C | stepped EC → add intermediate points; axis offset → shift v6's temperatures by the offset |
| Q8 | Fan rpm vs duty % (needed to turn "least fan" into rpm thresholds) | once, during tuning (each is a wake): `for d in 20 40 60 80; do asusctl fan-curve --mod-profile balanced --fan cpu --data "30c:${d}%,40c:${d}%,50c:${d}%,60c:${d}%,70c:${d}%,80c:${d}%,85c:${d}%,90c:100%" --enable-fan-curves true; sleep 20; cat /sys/class/hwmon/<asus>/fan1_input; done` then reinstall v6 | sets the rpm numbers in §6 precisely; also tells whether 10 % at 40 °C spins at all |
| Q9 | Does sppt/fppt headroom above spl change burst behaviour? | `spl=25 sppt=35 fppt=35` vs all 25: `stress-ng --cpu 16 -t 20` with `<pkgW>` at 1 Hz; compare the first 10 s | if the firmware gives a useful 5–10 s burst above spl: `ppt_burst_headroom_w = 10` and the demand ramp can be slower (quieter) at equal responsiveness |
| Q10 | Does the Quiet profile clamp our PPT writes (i.e. is the profile a ceiling on the dial)? | `asusctl profile set quiet` (wake, once); set 45 W; `stress-ng --cpu 16 -t 60 & sleep 40; <pkgW>` → compare with balanced | if clamped: enable `assert_profile = "balanced"` (one wake at daemon start only when it differs) and document the Quiet ceiling |
| Q11 | Does nvidia-powerd rewrite the CPU PPT when unmasked (game mode)? | `luminos-game-mode` on; set 30 W; log `<pkgW>` at 1 Hz for 5 min under `stress-ng --cpu 8` and watch for excursions above 33 W | confirms §3.7's yield rule is needed; if powerd never touches PPT, the yield can be dropped |
| Q12 | Does writing the same PPT value every 2 s for 10 min cause any notify or wake? | `for i in $(seq 300); do echo 30 \| sudo tee $PPT/ppt_pl1_spl >/dev/null; sleep 2; done` with the BUG-198 probes on → expect 0 | the 60 s refresh is safe |
| Q13 | Is `balance_power` an accepted EPP, and does asusd rewrite EPP outside profile changes? | `cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences; grep linked_epp /etc/asusd/asusd.ron; for i in $(seq 120); do cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference; sleep 5; done \| uniq -c` | periodic rewrites → EPP joins the 60 s refresh |
| Q14 | Does asusd flip the profile on cable events today? | `grep -E 'change_platform_profile_on|platform_profile_on' /etc/asusd/asusd.ron` | both `change_*` must be `false` (install step) or every cable event is a wake + reset |
| Q15 | Does the GPU fan spin up under CPU-only load (shared heatsink)? | `stress-ng --cpu 16 -t 120 & sleep 100; cat /sys/class/hwmon/<asus>/fan2_input` while `runtime_status` is suspended | if it stays near idle, the cpu-fan and mid-fan v6 points carry all the cooling and may need +10 % at 70–85 °C |
| Q16 | Which DRM card is the 780M on this boot, and which hwmon is k10temp? | `for c in /sys/class/drm/card?/device/vendor; do echo $c $(cat $c); done; grep -l k10temp /sys/class/hwmon/hwmon*/name; cat /sys/class/hwmon/<k10temp>/temp1_label` | the daemon resolves both by vendor/name; this only confirms the lookup works |
| Q17 | Idle cost and single-thread gain of EPP `balance_power` vs `power` | two 5 min idle windows with `<pkgW>`; `sysbench cpu --threads=1 --time=10` ×3 under each (PPT 15 W, no cap) | decides §3.6's fixed value; feeds the ≤ 0.5 W threshold |
| Q18 | Does the systemd watchdog path work from Go without a library? | after the change: `systemctl show -p WatchdogTimestamp,NotifyAccess luminos-power; sudo kill -STOP $(pidof luminos-power); sleep 20; systemctl status luminos-power` | expect a restart ≤ 15 s |
| Q19 | Heatsink time constant (for the simulated plant in P14 and the horizon of any future MPC) | from Q6's 15→35 W step: time for Tctl to cover 63 % of its rise | tunes `KiWPerCS` if settling is slower than 3 min |

Known, not questions: `ppt_*` read-back is a cache (never read); any profile or fan-curve write wakes the dGPU
(never write); `nvidia-smi -pl` is a no-op on this card (deleted); the Conductor is off in production and its
per-tick `pwmN_enable` would wake the card (deleted).

---

## 8. One-paragraph decision record (for LUMINOS_DECISIONS.md)

luminos-power stops being a state machine. One continuous dial `P` (15–45 W CPU package power) is moved at most
6 W/s up and 3–12 W/s down toward `min(demand hand, heat hand)`, where the demand hand is a linear map of
smoothed CPU/iGPU busyness and the heat hand is a PI controller on Tctl with the measured feed-forward
`(88 °C − 42 °C)/1.3 °C/W ≈ 35 W`. Ceilings (AC/battery-SOC/dGPU-busy) are blended, not switched. Fans are a
static EC curve (v6) installed once by a human; the daemon never writes a profile, a fan curve or nvidia-smi, so
it causes zero dGPU wakes. PPT is re-asserted every 60 s and after profile/AC/resume events because a profile
change silently resets it and the read-back cannot tell. Safety rests on the firmware's 95 °C limit, the
reduce-only nature of our writes, a 15 s systemd watchdog and an `ExecStopPost` that opens the dial on any exit.
Acceptance is the §6 ladder with thresholds fixed in advance; the control arm (no daemon) must be beaten too.
