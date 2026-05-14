# BUG-050 — Battery Life 3-4hr (Expected 8-10hr)

- **Status:** DIAGNOSED — READY TO FIX
- **Severity:** CRITICAL
- **Component:** System-wide power management
- **Date Found:** 2026-05-14
- **Diagnosed:** 2026-05-14
- **Date Fixed:** —
- **Agent:** claude-code

## Description
Battery life on Luminos OS is only 3-4 hours even on Quiet profile with light-medium workload.
Reference baselines:
- Windows (same hardware, heavy multitasking): 4-6hr
- Ubuntu (same hardware, light use): 8-10hr
- Expected Luminos target: 7-8hr (light), 5-6hr (medium)

Currently worse than Windows and roughly half of Ubuntu.

---

## Confirmed Root Causes (ordered by impact)

---

### ROOT-01 — nvidia-powerd holding GPU in D0 forever [CRITICAL — ~3-7W]

**Diagnostic output:**
```
/sys/bus/pci/devices/0000:01:00.0/power/runtime_status:       active
/sys/bus/pci/devices/0000:01:00.0/power/runtime_suspended_time: 0
/sys/bus/pci/devices/0000:01:00.0/power_state:                 D0
nvidia-smi: 1.89W draw, P8 state, 0% utilization
```

**What's happening:**
`nvidia-powerd` (PID 771) holds 10 open file descriptors on `/dev/nvidia0`.
Any open FD on that device prevents `NVreg_DynamicPowerManagement=0x02` from
power-gating the GPU. The GPU has been in D0 (fully active) for 100% of uptime —
`runtime_suspended_time = 0` means it has NEVER suspended, not even for 1ms.

`nvidia-powerd` is NVIDIA's Dynamic Boost daemon (designed for gaming TDP redistribution).
The service is marked `disabled` (should not start at boot) but is running — started by
something at boot. Its own log reports:
`ERROR! Client (presumably SBIOS) has requested to disable Dynamic Boost DC controller`
It's broken, does nothing useful on this hardware, and keeps the GPU awake 24/7.

**Actual power impact:**
- nvidia-smi reports 1.89W GPU draw (P8 minimum state)
- In D3cold: 0W
- Additional hidden cost: D0 keeps PCIe lanes + clock domains active → real system delta ~3-7W

**Note:** We DO want NVIDIA available on-demand for HIVE/Forex.
D3cold + dynamic PM gives exactly that: 0W idle, ~500ms wake when needed.
The `NVreg_DynamicPowerManagement=0x02` config is already correct.
Just need nvidia-powerd out of the way.

**Fix:**
```bash
sudo systemctl stop nvidia-powerd
sudo systemctl disable nvidia-powerd
sudo systemctl mask nvidia-powerd     # prevent anything from starting it
```
After masking, the NVIDIA driver's own DPM handles wake/sleep automatically.

---

### ROOT-02 — AMD P-State EPP stuck on `performance` always [CRITICAL — ~1-3W]

**Diagnostic output:**
```
scaling_driver:   amd-pstate-epp     ← correct driver
scaling_governor: performance        ← WRONG
EPP (cpu0-cpu14): performance        ← all 16 cores, always
```

**What's happening:**
The `performance` governor overrides all EPP hints. It tells the CPU "always target
maximum frequency." The CPU never enters low-power states between work bursts.
Ubuntu on battery sets governor=`powersave` + EPP=`power`, which hands control to
the CPU's SMU firmware — far smarter than any userspace decision.

**Why EPP is the right approach (replaces app/window tracking):**
The Ryzen 8845HS SMU has real-time per-core voltage, current, temperature, and power
data. It makes frequency decisions in microseconds with information no OS daemon can
access. With the right EPP hint:
- `power`: CPU SMU maximizes efficiency, clocks only what's needed
- `balance_power`: headroom for responsiveness, still conservative
- `balance_performance`: good for development/AI work
- `performance`: only for gaming/benchmarks

This completely replaces the 3-minute CPU load tracking in luminos-power v2.1.
No window counting, no load averages — just set the hint based on AC state and let
the hardware handle everything.

**Fix:**
Change governor to `powersave` on all cores and set EPP by AC state:
```bash
# On battery:
echo powersave | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo power | tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference

# On AC (normal work):
echo powersave | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo balance_performance | tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```
Wire this into luminos-power on AC plug/unplug events.

---

### ROOT-03 — PCIe ASPM on `default` policy, most devices disabled [HIGH — ~1-3W]

**Diagnostic output:**
```
/sys/module/pcie_aspm/parameters/policy: [default]
lspci output: "ASPM Disabled" appears 8+ times
              "ASPM L1 Enabled" only on internal AMD fabric links
```

**What's happening:**
ASPM `default` means BIOS decides. The ASUS ROG BIOS disables ASPM on external
PCIe devices (NVMe, WiFi, NVIDIA slot) for maximum performance/stability.
Without ASPM:
- NVMe SSD stays at full PCIe link power (~1.5W) instead of APST sleep (~0.1W)
- WiFi PCIe link stays active
- NVIDIA PCIe slot link stays at full power

**Fix:**
Add kernel parameter to force ASPM:
```
# /etc/kernel/cmdline or GRUB config — add:
pcie_aspm=force
```
Or set at runtime:
```bash
echo powersupersave > /sys/module/pcie_aspm/parameters/policy
```
Note: Some ASUS ROG BIOSes re-disable specific slots. Test for stability.

---

### ROOT-04 — No battery-event power manager [HIGH — cumulative ~1-2W]

**Diagnostic output:**
```
TLP:                    not installed
power-profiles-daemon:  not installed
thermald:               not installed
WiFi power save:        off (wlp3s0 — no power save configured)
USB ITE devices:        control=on (correct — these are ASUS EC)
USB others:             auto (correct)
Audio:                  power_save=10 (already fine)
```

**What's happening:**
No power manager applies battery-specific settings on unplug. Ubuntu/TLP handle
a dozen small optimizations automatically. We need a single udev-triggered script.

Items confirmed needing a fix:
- **WiFi power save**: off. Should enable on battery. (~0.3-0.8W)
- **KSM on battery**: enabled, 0 pages shared (doing nothing useful on battery)
- **Bluetooth**: powered on when not in use

Items that are already fine (do NOT touch):
- Audio codec: power_save=10 already set ✅
- USB autosuspend: default=2s, most devices on auto ✅
- ITE Device(8910) USB entries: ASUS embedded controller, must stay `on` ✅
- Telemetry: 30s interval, fine for NVMe APST ✅

**Fix:**
Create `/usr/local/bin/luminos-battery-event` script called by udev on
`ACAD online` change. Sets WiFi power save, KSM, Bluetooth, and triggers
luminos-power EPP update.

---

### ROOT-05 — 2s daemon polling rate [MEDIUM — ~0.5-1W]

**Diagnostic output:**
```
luminos-power: time.NewTicker(2 * time.Second)
luminos-ram:   time.NewTicker(3 * time.Second)
CPU C-states:  C1(1μs), C2(18μs), C3(350μs max)
```

**What's happening:**
Every 2-3 seconds all daemons wake up. This prevents the CPU package from
staying in C3 (deepest available state at 350μs latency) for more than ~2 seconds.
The overhead of the wake itself costs power. On battery, power management decisions
don't need 2s resolution — 10s is more than sufficient.

**Fix:**
In luminos-power and luminos-ram: when on battery, use a 10s ticker instead of 2s.
Add AC-state awareness to the monitor loop.

---

### ROOT-06 — Display at 120Hz (no battery switch) [MEDIUM — ~1-2W]

**Diagnostic output:**
```
card2-eDP-2: connected, 2880x1800
Mode #0 (preferred): 2880x1800 @ 120Hz
Mode #1:             2880x1800 @ 60Hz
KDE power management: no refresh rate switching configured
```

**What's happening:**
KDE Power Management does not have a "switch to 60Hz on battery" rule.
The panel stays at 120Hz on battery. Difference is approximately 1-2W.

**Fix:**
Add to KDE Power Management OR add to battery event script:
```bash
# On battery:
kscreen-doctor output.2.mode.2880x1800@60
# On AC:
kscreen-doctor output.2.mode.2880x1800@120
```

---

## Causes That Are NOT Issues (do not touch)

| # | Cause | Finding |
|---|---|---|
| 06 | Telemetry writes | 30s interval — NVMe APST needs 8ms idle, 30s is fine |
| 10 | Audio codec | power_save=10 already set — codec sleeps after 10s |
| 11 | USB autosuspend | Default=2s, most devices already on auto. ITE EC devices must stay `on` |
| 13 | Screen brightness | Already at 30% (119701/399000) |

---

## Estimated Gains Per Fix

| Fix | Estimated Saving | Confidence |
|---|---|---|
| Stop nvidia-powerd (ROOT-01) | 3-7W | HIGH |
| Fix EPP governor (ROOT-02) | 1-3W | HIGH |
| Force PCIe ASPM (ROOT-03) | 1-3W | MEDIUM |
| Battery event script (ROOT-04) | 0.5-1.5W | HIGH |
| Daemon poll rate (ROOT-05) | 0.5-1W | MEDIUM |
| 60Hz on battery (ROOT-06) | 1-2W | MEDIUM |
| **Total** | **7-17.5W** | — |

At current 40Wh usable capacity:
- Current draw (estimated): ~12-15W average → 3-4hr
- After fixes (estimated): ~5-7W average → 6-8hr ✅

---

## Fix Plan (in order — do not skip steps)

1. **Stop nvidia-powerd** → retest battery drain → should drop 3-7W immediately
2. **Fix EPP** → add to luminos-power AC/battery event handler
3. **Force PCIe ASPM** → kernel parameter + test for stability
4. **Battery event script** → WiFi power save + KSM + 60Hz
5. **Daemon poll rate** → modify luminos-power + luminos-ram to slow down on battery

---

## Fix Log (append as fixes applied)

| Date | Agent | Root Cause Fixed | Measured Impact |
|---|---|---|---|
| 2026-05-14 | claude-code | ROOT-01a: Stopped + masked nvidia-powerd | GPU no longer blocked by daemon |
| 2026-05-14 | claude-code | ROOT-01b: EGL priority flipped (10→60_nvidia) + pacman hook | KDE system apps drop NVIDIA EGL on next login |
| — | — | ROOT-02: EPP governor fix | — |
| — | — | ROOT-03: PCIe ASPM | — |
| — | — | ROOT-04: Battery event script | — |
| — | — | ROOT-05: Daemon poll rate | — |
| — | — | ROOT-06: 60Hz on battery | — |

---

## New luminos-power Architecture (post-fix)

Replace the current load-tracking algorithm entirely with EPP-based control:

```
Battery plug-out:
  → EPP = power (all cores)
  → governor = powersave
  → WiFi power save = on
  → KSM = off
  → Display = 60Hz
  → Daemon poll = 10s

Battery plug-in (AC):
  → EPP = balance_performance (all cores)
  → governor = powersave
  → WiFi power save = off
  → KSM = on
  → Display = 120Hz
  → Daemon poll = 2s

GPU gaming detected (GPU > 80% for 30s on AC):
  → EPP = performance
  → asusctl profile set Performance
  → (existing fan curve logic unchanged)

GPU idle after gaming (GPU < 20% for 60s):
  → EPP = balance_performance
  → asusctl profile set Balanced

Emergency thermal (>85°C):
  → EPP = power (instant, no delay)
  → asusctl profile set Quiet
```

The CPU P-state/frequency decisions are entirely removed from luminos-power.
The Ryzen 8845HS SMU handles all of that better than any 2s polling loop.
```
