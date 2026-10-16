# CURRENT — how luminos-power decides today
# [CHANGE: claude-code | 2026-10-15]

Read-only map of `cmd/luminos-power/` as it stands on 2026-10-15 (main.go 2238 lines, conductor.go 498,
fan_control.go 340). Purpose: let the "power spectrum" redesign replace the decision logic without
losing an external interface or re-introducing a fixed bug. Every claim cites file:line.
`UNCONFIRMED` = inferred from code reading only, not measured on the machine.
`NEW` = a defect found while writing this map that is not yet in docs/BUGS.md.

Abbreviations: `m:` = `cmd/luminos-power/main.go`, `c:` = `conductor.go`, `f:` = `fan_control.go`.

---

## 1. Main loop

**Startup (`main`, m:324-383), in order:**
1. `config.Load()` from `/etc/luminos/config.toml` (internal/config/config.go:54-58); logger to
   `<log.dir>/power.log` + stdout/journal (m:332; log dir default `/var/log/luminos`, config.go:93).
2. `cpuHardwareMaxFreq = readCPUHardwareMax()` — `cpu0/cpufreq/cpuinfo_max_freq`, fallback 5137904 kHz (m:338, m:1443-1453).
3. Listen on `cfg.Sockets.Power` = `/run/luminos/power.sock` (m:350, config.go:77).
4. `applyAggressiveFanCurve("balanced")` and `("quiet")` (m:359-360) → 8 asusctl calls, 2× `--enable-fan-curves true` → **2 firmware notifies / dGPU wakes on every daemon start** (BUG-198 addendum).
5. `initGPUTGP()` (m:363, m:1937) → `nvidia-smi -q -d POWER` → wakes the dGPU on every start (BUG-198 addendum: "luminos-power restart → its startup nvidia-smi woke the card").
6. `applyACTransition(readACState())` (m:366-367) → governor, wifi, KSM, display Hz, **setProfile**, EPP (see §3).
7. If `LUMINOS_CONDUCTOR=1`: `NewConductor()` + deferred `Revert()` (m:372-376, c:32).
8. `go monitorLoop(ctx)`; `socket.Serve` blocks (m:378-379).

**Cadence — there is no fixed poll interval.** `cfg.Power.PollIntervalSecs` (config.go:35, default 2 at config.go:84)
is **never read** by luminos-power (grep: no reference in cmd/luminos-power). Every tick ends in
`sleepAdaptive(ctx, psiFile, load, igpuLoad)` (m:1065-1088):

| `max(load, igpuLoad)` | sleep |
|---|---|
| < 20 % | PSI `poll(POLLPRI)` on `/proc/pressure/cpu`, timeout 10 s (m:1069-1070, m:1079-1081, m:1114-1122) |
| 20–60 % | `time.After(2s)` (m:1071-1072) |
| ≥ 60 % | `time.After(500ms)` (m:1073-1074) |

PSI trigger armed once: `"some 70000 1000000"` = 70 ms stall per 1 s window (m:1105). `waitPSI` ignores
ctx, so shutdown can lag ≤10 s (m:1114-1121, UNCONFIRMED impact).
`load` at the bottom of a normal tick = `demand = max(smoothedCPULoad, smoothedMaxCore)` (m:734, m:821),
forced ≥60 while interactive boost is active (m:822-824). Early-`continue` paths pass `smoothedCPULoad`
instead (m:598, 613, 629, 642, 728).

**Consequence that matters for the redesign:** every "N ticks = X seconds" constant assumes 2 s ticks,
but the real tick is 0.5 s – 10 s. E.g. CPU beast entry `cpuHighThreshTicks=10` "20s" (m:122) actually fires
after ~5 s at >60 % load (500 ms ticks); quiet entry `quietIdleTicks=30` "60s" (m:131) can take up to
300 s at idle (10 s PSI ticks); beast exit 30 ticks "60s" (m:83, m:124) likewise up to 300 s. The TGP
revert log even prints `gpuTGPDownTicks*2` as seconds (m:2013). Only the Conductor PID uses real wall-clock
`dt` (c:277-282).

**Per-tick order of operations (`monitorLoop`, m:428-826):**

| # | Step | Lines |
|---|---|---|
| 0 | once: open PSI watcher, start exec watcher goroutine (1 s /proc scan), optional input watcher | m:431-447 |
| 1 | SENSE: `readACState`, `readCPUTemp`, `readIGPULoad` | m:457-459 |
| 2 | dGPU sense **only if** `offloadActive` or (`!dgpuRuntimeSuspended()` && `dgpuHasClients()`): `readGPUStats` then offload TGP pin (m:493-501) or `manageGPUTGP` (m:503) | m:475-505 |
| 3 | `readCPULoad` (avg + busiest core) → EMA α=0.3 on both | m:509-522 |
| 4 | Conductor `Tick` (if enabled) | m:528-538 |
| 5 | drain exec events → `preAllocBonus`; expire after 30 s | m:542-559 |
| 6 | `interactiveBoost()` (inert unless `LUMINOS_INTERACTIVE=1`) | m:565 |
| 7 | AC transition → `applyACTransition`, reset counters/EMA/cap | m:568-576 |
| 8 | BEAST MODE enter (→`continue`) / exit (→`continue`) | m:581-616 |
| 9 | QUIET IDLE enter (→`continue`) / exit (→`continue`) | m:620-645 |
| 10 | THERMAL BURST start / re-apply / end / cancel | m:658-707 |
| 11 | EMERGENCY (→`continue`) | m:711-730 |
| 12 | ADAPTIVE GOVERNOR (non-Performance): zone, effective load, RAM bonus, cap, write | m:739-801 |
| 13 | `updateState(...)` — in-memory only | m:803 |
| 14 | SPI log line if SPI>60 or burst | m:808-815 |
| 15 | `sleepAdaptive` | m:821-825 |

Note steps 8, 9 and 11 `continue` — a profile change on a tick skips burst, emergency and the governor for
that tick. Step 9 runs **before** step 11 (see §7 NEW-1).

---

## 2. Inputs

| Input | Source | Units / transform | When |
|---|---|---|---|
| AC online | glob `/sys/class/power_supply/*/type` == `Mains` → sibling `online`=="1"; default `true` if none found | bool | every tick (m:1543-1553) |
| "CPU temp" | **max of every** `/sys/class/hwmon/hwmon*/temp*_input` (all sensors: k10temp, amdgpu, nvme, acpitz, wifi, …) | m°C/1000 → °C | every tick (m:1555-1566). Not Tctl-specific — UNCONFIRMED which sensor usually wins |
| iGPU load (780M) | `/sys/class/drm/card2/device/gpu_busy_percent` (hard-coded card2; errors → 0) | % | every tick (m:1624-1628). Card numbering is enumeration order (memory: renderD numbering differs per boot/box) — UNCONFIRMED stable |
| dGPU suspended? | `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status` == `suspended` (wake-free) | bool | every tick (m:1586-1592) |
| dGPU has clients? | walk `/proc/*/fd`, readlink starts with `/dev/nvidia` | bool | every tick while dGPU awake (m:1602-1621) |
| dGPU power, temp | `nvidia-smi --query-gpu=power.draw,temperature.gpu` dropped to uid 65534 / gid dgpu; >110 W discarded | W, °C | every tick while awake+clients or offload (m:1790-1801, m:1690-1712) |
| dGPU util | second `nvidia-smi --query-gpu=utilization.gpu`, only if power ≥ `dgpuActiveW`=10 W | % | same (m:1802-1806, m:118) |
| dGPU power limit | `nvidia-smi -q -d POWER` "Current Power Limit" | W | startup only (m:1914-1946) |
| dGPU max gfx clock | `nvidia-smi --query-gpu=clocks.max.graphics` | MHz | on offload/pin start (m:1842-1852) |
| CPU load | `/proc/stat` deltas: aggregate avg + busiest single core; first call (0,0) | % | every tick (m:2028-2098) |
| RAM | `/proc/meminfo` MemAvailable/MemTotal | fraction | **twice** per governor tick (m:773, m:809) |
| CPU pressure | `/proc/pressure/cpu` POLLPRI | event | idle sleep (m:1098-1122) |
| App launches | `/proc/*/comm` of new PIDs vs `knownApps` (m:243-254) | name | 1 s ticker goroutine (m:1146-1207) |
| User input | `/dev/input/eventN` (keyboard/pointer from `/proc/bus/input/devices`) timestamps | ns | only if `LUMINOS_INTERACTIVE=1` (m:289, m:1238-1319) |
| Current platform profile | `/sys/firmware/acpi/platform_profile` | string | inside every `setProfile` call (m:1349) |
| PCIe link | `current_link_speed`, `current_link_width` of 01:00.0 | — | after Conductor P0 pin only, log only (c:242-252) |
| fan hwmon | `/sys/class/hwmon/*/name` == `asus_custom_fan_curve` | path | Conductor start (f:44-59) |

Not read at all: battery %, battery discharge watts, CPU package power (no RAPL/amd_energy), fan RPM, PPT
limits, `nv_dynamic_boost`, the profile asusd reports. `prevState` is **not** restored from any file — the
comment at m:1340-1342 and DECISION 109 say it is; no such code exists (grep `prevState`: m:269, 390, 862, 2149, 2226 only).

---

## 3. Outputs / knobs

"BIOS?" = does the write reach the ASUS firmware (→ ACPI NVPCF/PEGP notify → RTX 4050 wakes ~20 s, BUG-161, BUG-198 addendum).

| Knob | Mechanism | Values actually used | Callers | How often in practice | BIOS? |
|---|---|---|---|---|---|
| Platform profile | `setProfile` m:1348 → no-op if `/sys/firmware/acpi/platform_profile` already matches (EqualFold) else `asusctl profile set <Name>` + `noteProfileChange` (warn >4/10 min, m:1362-1375) | Quiet, Balanced, Performance | m:590 beast in, 606 beast out, 626 →Quiet idle, 639 Quiet→Balanced, 722 emergency, 844 AC plug, 856 AC unplug | 19 changes in 27 h (BUG-198 addendum); one change = asusd wrote 0x120075 five times | **YES — wake** |
| Fan curve v5 | `applyAggressiveFanCurve` m:2159-2187: 3× `asusctl fan-curve --mod-profile <p> --fan cpu/gpu/mid --data …` + `--enable-fan-curves true`. No-op if Conductor owns fan (m:2162) | cpu/gpu `30c:0%,40c:5%,45c:22%,50c:55%,60c:88%,70c:100%,80c:100%,90c:100%`; mid `30c:0%,40c:0%,45c:15%,50c:37%,60c:59%,70c:70%,80c:88%,90c:100%` (m:2181-2182) | startup m:359-360 (balanced+quiet), m:607, 627, 640 (after every Balanced/Quiet profile change — "asusctl loses custom curve on profile switch"), `restoreBurstProfiles` m:2191-2196 (from m:697, 706) | 11 applies in 27 h (BUG-198) | **YES — `--enable-fan-curves true` wakes even with no change** (BUG-198 addendum) |
| Burst fan curve | `applyBurstFanCurve` m:2202-2215, same 4 asusctl calls; no-op if Conductor owns fan | cpu/gpu 100 % from 40 °C; mid 88 % (m:2209-2210) | m:671 start, m:682 profile changed mid-burst | 6 bursts in 27 h (BUG-198) | **YES** |
| EPP | `setAllEPP` m:1404 → glob `/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference`; `setEPPAfterAsusctl` m:1382 sleeps 350 ms first (asusd rewrites EPP asynchronously after a profile set, m:1379-1381) — sleeps even if setProfile was a no-op | `power` (default everywhere), `performance` (beast), `balance_performance` (interactive only, m:185) | m:591, 611, 723, 760, 763, 847, 857 | on profile events only | no (but asusd's own EPP write after a profile change clobbers it) |
| CPU freq cap | `setAllMaxFreq(kHz)` m:1421 → glob `cpu*/cpufreq/scaling_max_freq`; 0 = `cpuHardwareMaxFreq` | 1.8 GHz…hw max (adaptive), 3.5/3.0/2.5 GHz (zones), 2.0 GHz (emergency), 3.5 GHz (beast emergency) | m:592 beast 0, 718 beast >95 °C, 724 emergency, 796 adaptive, 836 AC transition 0 | adaptive only when smoothed cap moves >150 MHz (m:795) | no |
| Governor | `setAllGovernor("powersave")` glob `scaling_governor` m:1389 | `powersave` always | m:840, 852 | AC transitions | no |
| Wi-Fi PS | `/usr/bin/iw dev wlp3s0 set power_save on|off` m:1467 | off on AC / on on battery | m:841, 853 | AC transitions | no |
| KSM | `/sys/kernel/mm/ksm/run` m:1479 | 1 AC / 0 battery | m:842, 854 | AC transitions | no |
| Display Hz | `runuser -u <user> -- env WAYLAND_DISPLAY=… kscreen-doctor output.1.mode.2880x1800@{120,60}` m:1491-1511 | 120 AC / 60 battery | m:843, 855 | AC transitions | no. KDE-only tool; under Hyprland — UNCONFIRMED (probably fails, logged as warn) |
| dGPU TGP | `setGPUTGP` m:1951 → `nvidiaCtl("-pl", W)` (root nvidia-smi + `regateUVM`, m:1760-1764) | 55 / 90 W | offload m:497/500, `manageGPUTGP` m:1978/1993/2003/2014, `initGPUTGP` m:1945 | only while dGPU awake with clients | no BIOS, but **BUG-069 (OPEN): `-pl` is unsupported on the mobile 4050 and exits 0 — the write is a no-op and `currentGPUTGPW` is fiction**; DECISION 24 says "never -pl". Root nvidia-smi also implicated in BUG-182 (D0 pin) |
| dGPU P0 pin | `applyOffloadPin` m:1869: `nvidia-smi -pm 1`, `--lock-gpu-clocks=<max>`; stop: `--reset-gpu-clocks` (persistence **not** turned off — UNCONFIRMED whether `-pm 1` then blocks RTD3) + `/run/luminos/offload.active` file | — | socket `offload_start/stop` m:401/404; Conductor pcie lever c:223/227/234 | per offload session / gaming-training intent | no |
| UVM gate | `regateUVM` chown root:dgpu, chmod 0660 `/dev/nvidia-uvm{,-tools}` m:1738-1755 | — | after every `nvidiaCtl` | — | no |
| Conductor fan (gated OFF) | `setAllFansDuty` f:120 → `writeFanDuty` f:92: for cpu(1), mid(3) [cpu duty], gpu(2): 8× `pwmN_auto_pointX_temp` + 8× `_pwm` + **`pwmN_enable=1` every tick** on `asus_custom_fan_curve` hwmon (51 sysfs writes/tick), failsafe floor `{0,0,0,0,0,120,210,255}` (f:40) | PWM 0–255 | c:172 every tick when enabled | every tick | bypasses asusd, but `pwmN_enable` is the kernel asus-wmi fan-curve-enable WMI call — the same devid (0x00110024 CPU fan curve, BUG-198 addendum) that fired NPCF notifies when asusd did it. **UNCONFIRMED but likely a per-tick dGPU wake source if the Conductor is turned on** |
| Intent broadcast (gated OFF) | atomic write `/run/luminos/intent.json`; socket `intent` to `/run/luminos/ram.sock` + ai sock (c:321-373) | classes idle/light/media/compute/gaming/training | on intent change | — | no |
| Telemetry (gated OFF) | append `<logdir>/conductor-telemetry.jsonl`, rotate at 64 MiB (c:377-408) | — | every tick | — | no |
| PSI trigger | write to `/proc/pressure/cpu` (m:1105) | — | startup | — | no |
| report to ai | `report_power` → `cfg.Sockets.AI` (m:2225-2228) | `PowerState` | **only from `applyACTransition` (m:863)** | AC plug/unplug + startup | no |

Not touched by the daemon: `nvidia-powerd` (owned by `scripts/luminos-game-mode`, `scripts/luminos-train-mode`;
masked per DECISION 126), ASUS PPT/armoury attributes (unreadable, ENODEV, BUG-157), platform_profile sysfs
directly, PCIe ASPM, amdgpu DPM.

---

## 4. Discrete states, thresholds, hysteresis

### 4.1 Platform profile (Quiet / Balanced / Performance)
- AC plug → Balanced + EPP power; unplug → Quiet + EPP power (m:838-859).
- Quiet-idle (AC, from Balanced): `cpuLoad<25 && igpu<15 && dgpu<5` (raw avg, not EMA) for `quietIdleTicks=30` consecutive ticks → Quiet + re-apply quiet v5 curve (m:128-131, m:620-634). Any tick failing resets the counter (m:633).
- Quiet exit (AC): `cpu≥40 || igpu≥30 || dgpu≥10` on **one** tick → Balanced + re-apply curve (m:147-149, m:635-644). Deadband added by BUG-161/DECISION 109.
- No Quiet-idle logic on battery (profile stays Quiet, m:620/635 require onAC).

### 4.2 Beast mode (AC only, → Performance)
- Entry, evaluated only when `onAC && Profile != "Performance"` (m:581): either
  - GPU: `dgpuLoad > 80` for `gpuHighThreshTicks=15` (m:80-81, m:868-882), or
  - CPU: `cpuLoad > 75` (raw avg) for `cpuHighThreshTicks=10` (m:121-122, m:893-907).
  - Action: setProfile Performance, EPP performance (+350 ms), `setAllMaxFreq(0)`, zone→Cool, `continue` (m:589-599). No fan-curve call (Performance runs whatever curve firmware/asusd holds for that profile — UNCONFIRMED which).
- Exit (m:601-615): `applyGamingDetection(...)=="Balanced" && applyCPUBeastDetection(...)=="Balanced"` **on the same tick**. Each returns Balanced only on the single tick its low counter reaches 30 (`gpuLowThreshPct=20`, `cpuLowThreshPct=25`, m:82-83, 123-124), then resets to 0 (m:884-887, 909-912). CPU low counter is also reset by any tick with 25≤cpu≤75 (m:900-903). → **BUG-200: exit can be missed forever.** Exit does setProfile Balanced + balanced curve + EPP power; it does **not** call `setAllMaxFreq(0)` (handbook 4.5 says it does — doc drift).
- While in Performance: burst disabled (m:658), adaptive governor disabled (m:739), emergency threshold 95 °C instead of 92 °C and action = 3.5 GHz cap only (m:712-719); that cap is never lifted until beast exit (NEW-2, §7).

### 4.3 Thermal zones (`advanceThermalZone`, m:937-994; caps `thermalCapForCurrentZone`, m:999-1014)
Evaluated only on the governor path (non-Performance, non-emergency tick, m:740). Upgrades are one zone per tick
when `temp ≥ entry`; downgrades need `temp < entry − 5 °C` (`thermalHysteresisC`, m:192) for 5 consecutive
ticks (`thermalDowngradeHoldTicks`, m:193). Zone reset to Cool on AC transition, beast in/out (m:594, 608, 833).

| Zone | AC entry (m:199-201) | AC cap | Battery entry (m:204-206) | Battery cap |
|---|---|---|---|---|
| Cool | — | none | — | none (adaptive max 3.5 GHz) |
| Mild | 60 °C | none | 50 °C | none |
| Warm | 72 °C | none (BUG-055) | 62 °C | 3.5 GHz |
| Hot | 87 °C | 3.0 GHz | 72 °C | 2.5 GHz |

Final cap = `min(adaptiveCap, zoneCap)` then smoothed 70/30 (m:785-792) — so zone caps are applied gradually, not as a step.

### 4.4 Emergency (m:711-730)
`temp > 92 °C` (`thermalEmergencyC`, m:152) when not Performance → setProfile Quiet, EPP power (immediate, no 350 ms wait), cap 2.0 GHz, `continue`. No hysteresis and no exit action: next tick ≤92 °C simply falls into the governor, whose 70/30 smoothing walks the cap back up from 2.0 GHz. Profile stays Quiet until Quiet-exit (AC) — see NEW-1.

### 4.5 Thermal burst (m:658-707; constants m:221-224)
Not in Performance, temp < 92 °C. Start: `temp ≥ 52 °C` and ≥30 min since last burst end → burst curve on current profile (lower-case), remember profile in `thermalBurstProfiles`. End: `temp ≤ 48 °C` or 2 min elapsed → `restoreBurstProfiles()` (v5 on every touched profile, BUG-190). Cancelled when beast mode starts (m:700-707). Applies on battery too. `time.Since` is monotonic and excludes suspend (BUG-190 note). Docs drift: AGENTS.md §12 says exit 45 °C, LUMINOS_STATUS.md:150 says 40 °C; code is 48 °C (m:222).

### 4.6 Adaptive governor v4.1 (continuous — m:739-801, m:1029-1057)
```
demand        = max(EMA0.3(avgLoad), EMA0.3(busiestCoreLoad))                 m:513-522, m:734
effectiveLoad = min(demand + preAllocBonus, 100)                                 m:747  (preAlloc 5–20 %, 30 s, m:173, m:243-254)
              + interactive bonus ≤45 % decaying linearly over 1.5 s (gated)     m:183-184, m:755-757, m:1220-1234
              + RAM bonus min((0.20 − availFrac)·200, 30) if avail<20 % && temp>45 °C   m:229, m:773-779
cap           = 1.8 GHz + effectiveLoad/100 · (maxCap − 1.8 GHz)                 m:1036
                maxCap = hw max on AC, 3.5 GHz on battery                         m:168-170, m:1030-1033
              − min((igpu − effectiveLoad)·12 MHz, 300 MHz) if igpu − effectiveLoad > 20   m:175-176, m:1040-1047
              clamp [1.8 GHz, maxCap]                                             m:1050-1055
finalCap      = min(cap, zoneCap if >0)                                           m:785-789
applied       = 0.7·prevApplied + 0.3·finalCap; written only if |Δ|>150 MHz       m:792-800
```
EPP is not part of it (stays `power`).

### 4.7 GPU TGP manager (m:1973-2019, constants m:88-118)
AC only (battery → force 55 W, m:1975-1982). At 55 W: uplift to 90 W if draw ≥47 W && GPU temp <82 °C && ≥60 s since last switch. At 90 W: drop if temp ≥87 °C (&& 60 s); else drop after 30 ticks of draw<15 W && util<20 %. Offload session: hold 90 W, drop at ≥87 °C, re-raise <82 °C (m:493-501). Effectively inert — BUG-069.

### 4.8 Conductor (gated OFF by `LUMINOS_CONDUCTOR=1`, c:32)
- Classifier `classify` c:433-467 (raw, unsmoothed `cpuLoad`, `dgpuLoad`, `igpuLoad`, `gpuPowerW`):
  dGPU≥60 % or ≥40 W → `training` if cpu≥50 else `gaming` (pin P0 on AC); igpu≥40 && cpu<40 → `media`; cpu≥50 → `compute`; cpu≥15 || dgpu≥10 → `light`; else `idle`.
- Per class: FanTarget 47 (idle/light) / 55 (media) / 60 (compute/gaming/training) / 52 default (f:319-330); GPUTarget 55 / 65 (c:491-498); FanFloor PWM 0 / 60 / 80 / 110 (c:475-486).
- Switch rule `shouldSwitch` c:307-315: immediate if FanTarget drops ≥5 °C or pin newly needed; otherwise only after `minIntentDwell=12s` (c:51). Each switch `Reset()`s both PIDs (c:186-187, f:304-312).
- PID `FanController.Update` f:204-300: EMA temp α=0.30; slam to 255 at raw ≥85 °C; feed-forward Kff=30 PWM per °C/s rise; deadband ±2 °C; Kp=8 Ki=0.5 Kd=8; back-calc anti-windup Kbc=0.5; in-band integral leak ×0.90; clamp ±120; slew +60/−18 per tick (f:180-195). Uses real `dt`.
- Header comment f:15-16 "NOT yet wired into monitorLoop" is stale (it is wired, m:528-538).

### 4.9 Other gates
Interactive boost (`LUMINOS_INTERACTIVE=1`, m:289): EPP flips to `balance_performance` while input within 1.5 s (m:758-766). Exec pre-alloc table m:243-254. SPI index, log-only (m:2136-2144).

---

## 5. External interfaces to preserve

**Socket `/run/luminos/power.sock`** (config.go:77, root, line-JSON one request/one reply, 5 s deadline — internal/socket/socket.go:79-106). Envelope `{"type","payload","timestamp","source"}` (socket.go:21-25). Handled types (m:385-411):

| request `type` | reply `type` | payload |
|---|---|---|
| `ping` | `ping_response` | `{"pong":"ok","daemon":"luminos-power"}` |
| `status` | `status_response` | `PowerState` (below) |
| `offload_start` | `offload_start_response` | `{"offload":"started","tgp_target_w":90}` |
| `offload_stop` | `offload_stop_response` | `{"offload":"stopped"}` |
| `offload_status` | `offload_status_response` | `{"active":bool}` |
| other | `error` | `{"error":"unknown type: …"}` |

`PowerState` (m:66-73): `{"on_ac":bool,"cpu_temp_c":float,"gpu_load":float,"epp":string,"profile":string,"updated_at":RFC3339}`. `profile` ∈ Quiet/Balanced/Performance, `epp` ∈ power/performance. Note `epp` is `prevState.EPP` and is not updated by interactive flips.

**Outbound:** `report_power` (same `PowerState`) to luminos-ai socket only on AC transitions (m:863, m:2225); luminos-ai stores it verbatim and serves it inside its own `status` under `"power"` (cmd/luminos-ai/main.go:101-117). So luminos-ai's copy is stale between AC events. Conductor `intent` message `IntentBroadcast` `{"name","fan_target_c","gpu_target_c","pin_gpu_p0","swappiness","on_ac","source","timestamp"}` (c:82-91) → luminos-ram (cmd/luminos-ram/main.go:1018ff, sets swappiness 10 for gaming/training/compute/heavy) and luminos-ai (cmd/luminos-ai/main.go:142-148).

**Files:** `/run/luminos/offload.active` (m:1838; read by luminos-ram, cmd/luminos-ram/main.go:48-50); `/run/luminos/intent.json` (c:41); `/var/log/luminos/power.log` (m:332); `/var/log/luminos/conductor-telemetry.jsonl` (c:378).

**Log/journal consumers:**
- Plasma power widget `src/widgets/org.luminos.powerwidget/contents/ui/main.qml:72-78` runs `journalctl -u luminos-power -n 1 | grep -oE 'profile=[A-Za-z]+'` every 5 s. The daemon only prints `profile=` in the burst-start line (m:669), so the widget shows "Quiet" almost always — already broken; any new log format should either emit `profile=` deliberately or the widget should move to the socket.
- `scripts/luminos-verify:39,161-164` checks service active + socket present.
- `scripts/luminos-session-recorder:135`, `scripts/hive-crash-analyzer:31`, `scripts/hive_context.py:39` read service state/journal.
- Docs/runbooks grep these log strings: `beast mode → Performance`, `beast mode exit`, `idle → Quiet`, `load → Balanced`, `thermal burst START/DONE/TIMEOUT`, `adaptive cap →`, `thermal zone`, `GPU TGP`, `profile flapping` (handbook §4.9-4.10, BUGS.md). Quickshell/Caelestia dashboards live outside the repo — UNCONFIRMED whether they read power.sock (repo grep finds none).

**External scripts that fight the same knobs:** `scripts/luminos-train-mode:31-35` writes asusctl fan curves on `balanced` every 60 s ("because luminos-power re-applies fan curve v5 on profile/thermal-zone transitions", :6-8) and unmasks nvidia-powerd; `scripts/luminos-game-mode:74-108` unmasks/re-masks nvidia-powerd.

**Env flags (no CLI flags exist):** `LUMINOS_CONDUCTOR=1` (c:32), `LUMINOS_INTERACTIVE=1` (m:289). Both default off; no drop-in sets them in the repo.

**systemd:** `systemd/luminos-power.service` — `Type=simple`, `ExecStart=/usr/local/bin/luminos-power`, `Restart=always`, `RestartSec=3`, `Before=luminos-ai.service`, `RuntimeDirectory=luminos` + `RuntimeDirectoryPreserve=yes` (shared /run/luminos), runs as root.

**Config:** `/etc/luminos/config.toml` `[sockets] power/ai`, `[log] dir`; `[power] poll_interval_secs` exists but is unused.

**Invariants other code relies on:** single writer of `scaling_max_freq`/EPP/fan curve (DECISION 24); every profile write through `setProfile` (DECISION 109, AGENTS.md §12); all root nvidia-smi through `nvidiaCtl` + `regateUVM`, all reads through `nvidiaRead` (BUG-146); never touch the dGPU while `runtime_status=suspended` and never poll utilisation unless ≥10 W (BUG-078, BUG-160); EPP written 350 ms after any asusctl profile set (AGENTS.md §12).

---

## 6. Continuous pieces vs discrete switches

**Already continuous:**
- Adaptive CPU cap (§4.6): linear in effective load, double-smoothed (EMA on load, 70/30 on cap), 150 MHz write threshold. This is the closest thing to a spectrum today.
- Interactive bonus (linear decay), pre-alloc bonus (step on, step off after 30 s), RAM bonus (linear), iGPU-dominance penalty (linear, capped).
- Conductor fan PID (continuous duty, real dt) — but its setpoint and floor are stepped per discrete class.
- Fan curve v5 itself is a continuous temp→% map executed by the EC.

**Discrete switches layered on top, and where they fight:**
1. **Profile is the biggest step and it is the expensive one.** Balanced↔Quiet↔Performance changes firmware PPT/TDP (values not visible to us — asus-armoury ENODEV, BUG-157) in one jump, and every change costs a dGPU wake plus a mandatory fan-curve re-apply (another wake). The adaptive cap cannot see the profile's TDP ceiling, so the "continuous" cap is moving inside a box whose walls jump.
2. **Beast mode suspends the continuous governor entirely** (m:739 guard) and jumps cap→hw max, EPP power→performance, profile→Performance on one tick (m:590-592). On exit the cap restarts from wherever it was and walks down via 70/30.
3. **EPP is binary** (`power` vs `performance`) and is the strongest per-core lever; the redesign could make it a graded output (power → balance_power → balance_performance → performance) with no BIOS cost.
4. **Thermal zones** step the cap ceiling (3.0/2.5/3.5 GHz) with a 5 °C/5-tick hysteresis; they are softened by the 70/30 smoothing but still bang-bang. History of oscillation from exactly this: BUG-048, BUG-053, BUG-055.
5. **Emergency** is an unsmoothed step to 2.0 GHz + Quiet (+wake), with no hysteresis.
6. **Burst** is bang-bang 100 % fan with a 30-min lockout — it overrides the continuous v5 curve and costs 2 wakes (start + restore) per cycle.
7. **Quiet-idle** is a 3-signal AND with a tick-count timer whose real duration varies 15 s–300 s.
8. **Conductor classes** (idle/light/media/compute/gaming/training) step FanTarget 47→55→60 and FanFloor 0→110 and `Reset()` the PID on each switch — discrete on top of a continuous controller (cause of BUG-079 flaps; mitigated by 12 s dwell).
9. **Tick-count timers vs adaptive tick period** (§1): every hysteresis that counts ticks has a duration that depends on load, so "60 s" means 15 s at high load and 300 s at idle.
10. **Two fan writers outside the daemon** (train-mode keep-alive) plus the daemon's own re-apply after each profile change — three ways for the curve to change, each a wake.

---

## 7. Known bugs / conflicts relevant to a redesign

From the docs:
- **BUG-198 + addendum (2026-10-15)** — any profile change and any `asusctl fan-curve … --enable-fan-curves true` (even with no change) → BIOS → `Notify(NPCF/PEGP,0xC0)` → NVIDIA driver wakes the 4050 ~20 s. 27 h: 19 profile changes + 11 curve applies + 6 bursts ≈ 19 min awake. Idle with no writes: 0 notifies. Also seen: a wake with no profile change logged as CPU went 74→86 °C (cause not attributed in code).
- **BUG-161 / DECISION 109** — same mechanism; profile flap Quiet↔Balanced; fixed by deadband + `setProfile` idempotence; explicitly **no rate limiter** because callers `continue` and never retry.
- **BUG-200 (OPEN)** — beast exit requires two independent counters to hit 30 on the same tick (m:601-604); can stick in Performance indefinitely.
- **BUG-190** — burst curve leaked onto Balanced after a mid-burst profile switch; fixed with `thermalBurstProfiles` (m:309, m:2191).
- **BUG-157 / DECISION 102** — dGPU load was hard-wired 0 (amdgpu-only sysfs); TGP thermal latch at 83 °C; TGP power limit unreadable via `--query-gpu`; Dynamic Boost SBIOS handshake failures.
- **BUG-160** — utilisation query forces D0; split into 2 queries gated by ≥10 W.
- **BUG-078** — any nvidia-smi takes a runtime-PM ref; use `runtime_status`.
- **BUG-069 (OPEN)** — `nvidia-smi -pl` silently unsupported on mobile → the whole TGP manager (m:1951-2019) is a no-op; real TGP mover is nvidia-powerd (DECISION 126 keeps it masked; game/train scripts unmask).
- **BUG-182 (OPEN, investigation)** — a root `nvidia-smi` pins the dGPU in D0 with no client and reopens the UVM gate.
- **BUG-146** — root nvidia-smi reopens UVM nodes; hence `nvidiaRead`/`nvidiaCtl`/`regateUVM`.
- **BUG-079** — Conductor PID hunting; retuned; Conductor still gated OFF (DECISION 24 addenda).
- **BUG-055 / BUG-053 / BUG-048** — any hard freq cap or no-hysteresis profile switch oscillates; the reason AC zones Mild/Warm have no cap and why entry/exit thresholds must differ.
- **DECISION 4** (two power modes only, AC vs battery; "no profiles") and **DECISION 4b** (45 °C target, EPP=power default, caps only as last resort) — the spectrum is arguably a return to these.
- **DECISION 23** (offload pin, cross-daemon), **DECISION 24** (Conductor, single-writer, independent levers), **DECISION 126** (nvidia-powerd masked at idle).
- Memory note (user preference): fan target floats with workload — 47 °C light, higher fair ceiling heavy; use least fan; never max fan at 50-55 °C.

NEW — found while mapping, not in BUGS.md, all from code reading (UNCONFIRMED live):
- **NEW-1 Emergency ↔ Quiet-exit flap on AC.** Emergency (m:722) sets Quiet. Next tick, the Quiet-exit block (m:635-644) runs **before** the emergency check (m:711) and, with any real load (cpu≥40 or igpu≥30 or dgpu≥10 — near-certain at >92 °C), sets Balanced + re-applies the fan curve and `continue`s. The tick after, emergency sets Quiet again. While the machine stays >92 °C under load this alternates every tick (500 ms at high load): 2 profile writes + 4 asusctl fan-curve calls per cycle, each a dGPU wake, at the hottest moment. Bounded only if CPU >75 % triggers beast mode after ~10 ticks; a GPU-heavy load with CPU 40–75 % never escapes. `noteProfileChange` would log "profile flapping".
- **NEW-2 Beast-mode emergency cap sticks.** In Performance >95 °C → `setAllMaxFreq(3500000)` (m:718); nothing raises it again while in Performance (governor skipped, m:739), and beast exit (m:604-614) does not reset it. Combined with BUG-200, the box can sit in Performance profile + EPP performance + 3.5 GHz cap.
- **NEW-3 Tick-count timers are not time-based** (§1). Beast CPU entry ≈5 s not 20 s; quiet entry / beast exit up to 300 s; TGP idle revert log lies about seconds (m:2013).
- **NEW-4 "CPU temp" is the max of every hwmon sensor** (m:1555-1566), not Tctl — any hot sensor (NVMe, battery, amdgpu edge) drives zones, burst and emergency.
- **NEW-5 luminos-ai's power state is stale** — `reportToAI` only on AC transitions (m:863); the doc string at cmd/luminos-ai/main.go:112 says "on every change".
- **NEW-6 Plasma widget profile parse is broken** — greps `profile=` that the daemon almost never logs (§5).
- **NEW-7 Conductor per-tick `pwmN_enable=1`** (f:110-113) is likely itself a BIOS/WMI call and possibly a per-tick dGPU wake if the Conductor is enabled — must be measured with the BUG-198 kprobe method before any design relies on direct hwmon fan writes.
- **NEW-8 Offload stop leaves persistence mode on** (m:1891-1898 has no `-pm 0`) — UNCONFIRMED whether that holds the card out of RTD3.
- **NEW-9 Startup costs 3 wakes**: 2× `--enable-fan-curves` (m:359-360) + `nvidia-smi -q` (m:363), plus a possible profile write (m:844/856) — every `systemctl restart luminos-power` (the documented relief for BUG-190/200) wakes the dGPU.
- Dead/stale code: `eppForProfile` (m:916-925) has no callers; `PollIntervalSecs` unused; f:15-16 header stale; DECISION 109's "prevState restored from a file" has no code.
- Doc drift: burst exit 48 °C in code vs 45 °C (AGENTS.md §12) vs 40 °C (LUMINOS_STATUS.md:150); handbook §4.2-4.7 line numbers are from a much older main.go; handbook §4.5 says beast exit calls `setAllMaxFreq(0)` (it does not); handbook §4.3 says `output.eDP-2`, code uses `output.1` (m:78).

---

## 8. Tests and build

- **No `_test.go` in `cmd/luminos-power/`.** The only Go test in `cmd/` + `internal/` is `cmd/luminos-ram/tabs_test.go`. `tests/` holds Python tests (test_daemon.py etc.) that do not reference luminos-power. Zero coverage for the classifier, governor formula, hysteresis, PID, or the profile choke point. Pure functions that are trivially testable today: `computeAdaptiveCap` (m:1029), `advanceThermalZone`+`thermalCapForCurrentZone` (global state, m:937/999), `applyGamingDetection`/`applyCPUBeastDetection` (m:868/893 — a 60-tick table test would reproduce BUG-200), `systemPressureIndex` (m:2136), `FanController.Update` (f:204), `classify`/`shouldSwitch` (c:433/307), `interactiveBoost` (m:1220).
- **Build:** `go build -o /tmp/luminos-power ./cmd/luminos-power` from repo root (`scripts/install-daemons.sh:16-20`); module path `github.com/luminos-os/luminos` (imports m:59-62); deps `internal/config`, `internal/logger`, `internal/socket`, `golang.org/x/sys/unix`, `BurntSushi/toml`.
- **Install:** `sudo install -m 755 /tmp/luminos-power /usr/local/bin/luminos-power` (install-daemons.sh:34; `BINDIR=/usr/local/bin`, :10); unit `sudo install -m 644 systemd/luminos-power.service /etc/systemd/system/` (:45); `systemctl enable --now luminos-power.service` (:55). A prebuilt copy also sits at `bin/luminos-power` in the repo.
- **Service name:** `luminos-power.service`, SyslogIdentifier `luminos-power`; logs in journal + `/var/log/luminos/power.log`.
- **Rollback convention seen in BUGS.md:** binary backups at `~/.luminos-backups/luminos-power.bak-<tag>` + `install` + restart (BUG-190).
- Repo rule: `cmd/` changes need Shawn's go (BUG-200 text, AGENTS.md §11).
