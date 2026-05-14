# BUG-050 — Battery Life 3-4hr (Expected 8-10hr)

- **Status:** INVESTIGATING
- **Severity:** CRITICAL
- **Component:** System-wide power management
- **Date Found:** 2026-05-14
- **Date Fixed:** —
- **Agent:** claude-code

## Description
Battery life on Luminos OS is only 3-4 hours even on Quiet profile with light-medium workload.
Reference baselines:
- Windows (same hardware, heavy multitasking): 4-6hr
- Ubuntu (same hardware, light use): 8-10hr
- Expected Luminos target: 7-8hr (light), 5-6hr (medium)

We are currently **worse than Windows** and roughly half of Ubuntu.
The power profile/algorithm is NOT the root cause — the system has unmanaged subsystems
draining power that no daemon or config is currently addressing.

---

## Suspected Causes (13 total — all unverified, need diagnostics)

### CAUSE-01 — NVIDIA Not Reaching D3cold on Battery
- **Impact:** HIGH (5–12W constant drain if true)
- **Status:** UNVERIFIED
- **Theory:** `NVreg_DynamicPowerManagement=0x02` is configured (BUG-047 fix) but
  the actual runtime power state on battery is unknown. May be stuck in D3hot
  (suspended but still drawing power) rather than D3cold (rail fully off).
- **Note:** We want NVIDIA available on-demand for HIVE/Forex — goal is D3cold idle,
  not disabling it. D3cold + dynamic PM gives us 0W idle with ~500ms wake time.
- **Diagnostic:**
  ```bash
  cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status
  cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_suspended_time
  cat /sys/bus/pci/devices/0000:01:00.0/power/control
  ```
- **Fix if confirmed:** Verify udev rules are applying on battery plug/unplug events.
  May need `RuntimePM` kernel parameter or manual D3cold force.

---

### CAUSE-02 — AMD P-State EPP Stuck on Performance/Balance-Performance
- **Impact:** HIGH (1–3W constant, prevents deep CPU idle)
- **Status:** UNVERIFIED
- **Theory:** Ryzen 8845HS uses `amd_pstate_epp` driver. EPP (Energy Performance
  Preference) tells the CPU firmware how aggressively to trade power for speed.
  Values: `performance` > `balance_performance` > `balance_power` > `power`.
  Ubuntu auto-switches to `power` on battery. Arch does not auto-switch.
  If stuck on `balance_performance`, CPU never fully clocks down between bursts —
  costing 1-3W even at idle.
- **Diagnostic:**
  ```bash
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
  cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
  cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences
  ```
- **Fix if confirmed:** `luminos-power` daemon sets EPP via sysfs on battery plug/unplug.
  Battery → `power`, AC light → `balance_power`, AC heavy → `balance_performance`.

---

### CAUSE-03 — PCIe ASPM Disabled or Not Enforced
- **Impact:** HIGH (2–4W constant)
- **Status:** UNVERIFIED
- **Theory:** ASPM (Active State Power Management) allows PCIe devices (NVMe SSD,
  WiFi chip, NVIDIA PCIe slot) to enter low-power link states when idle.
  If ASPM policy is `off` or BIOS forces it off, all PCIe devices stay at full link
  power — NVMe alone draws 1.5W instead of 0.1W at idle.
- **Diagnostic:**
  ```bash
  cat /sys/module/pcie_aspm/parameters/policy
  sudo lspci -vv | grep -i aspm
  dmesg | grep -i aspm
  ```
- **Fix if confirmed:** Kernel parameter `pcie_aspm=force` or set policy to
  `powersupersave` via `/sys/module/pcie_aspm/parameters/policy`.

---

### CAUSE-04 — Luminos Daemons Preventing Deep CPU C-States (2s Polling)
- **Impact:** MEDIUM-HIGH (1–2W, prevents C8/C10 sleep)
- **Status:** UNVERIFIED
- **Theory:** `luminos-power`, `luminos-ram`, `luminos-sentinel` all poll on 2-second
  tickers. Each tick wakes the CPU from idle. The problem isn't the work done —
  it's that the CPU can't enter C8/C10 deep sleep states (which save 0.8–1.5W)
  if it wakes every 2 seconds. Ubuntu has no equivalent constant-polling daemons.
- **Diagnostic:**
  ```bash
  sudo powertop --time=10 2>/dev/null | head -60
  # Look for: C-state residency — want >80% time in C8/C10
  # Look for: wakeup sources — our daemons will appear
  ```
- **Fix if confirmed:** On battery, increase poll interval to 10–30s. The 2s interval
  is unnecessary for power management decisions.

---

### CAUSE-05 — No Comprehensive Power Manager (TLP/power-profiles-daemon Gap)
- **Impact:** MEDIUM-HIGH (cumulative 2–4W from multiple unmanaged subsystems)
- **Status:** LIKELY TRUE
- **Theory:** Ubuntu uses `power-profiles-daemon` or TLP which configures dozens of
  power optimizations automatically. We have `asusctl` for ACPI profiles only.
  The following are almost certainly at power-hungry defaults:
  - USB autosuspend: OFF (default)
  - WiFi power save: OFF (default for reliability)
  - Audio codec (snd_hda_intel) power_save: 0 (default)
  - NVMe APST: may be disabled
  - Runtime PM for PCI devices: OFF (default)
  - SATA link power management: max_performance (default)
- **Diagnostic:**
  ```bash
  cat /sys/module/snd_hda_intel/parameters/power_save
  iwconfig 2>/dev/null | grep Power
  cat /sys/bus/pci/devices/*/power/control 2>/dev/null | sort | uniq -c
  ```
- **Fix if confirmed:** Install TLP or write a battery-event script that sets all
  these when unplugged. Do NOT install power-profiles-daemon — conflicts with asusctl.

---

### CAUSE-06 — Continuous Telemetry Logging Preventing NVMe Sleep
- **Impact:** MEDIUM (0.5–1.5W, NVMe can't enter APST)
- **Status:** LIKELY TRUE
- **Theory:** `/var/log/luminos-telemetry.csv` is described as "continuous logging."
  NVMe APST (Autonomous Power State Transitions) works by sleeping the drive after
  ~8ms of inactivity. Constant writes reset this timer — NVMe never sleeps.
  At idle, NVMe in APST saves ~1.2W.
- **Diagnostic:**
  ```bash
  sudo nvme get-feature /dev/nvme0 -f 0x0c -H
  # Check write frequency:
  iostat -x 2 5 | grep nvme
  ```
- **Fix if confirmed:** On battery, pause telemetry logging or batch writes every 60s.

---

### CAUSE-07 — KSM Always Running on Battery
- **Impact:** MEDIUM (0.5–1W of CPU busy time)
- **Status:** LIKELY TRUE
- **Theory:** KSM (Kernel Samepage Merging) continuously scans RAM for duplicate
  pages to merge. We enabled this for RAM efficiency. On battery, this is wasted
  CPU work that keeps the processor warm and prevents deep idle.
- **Diagnostic:**
  ```bash
  cat /sys/kernel/mm/ksm/run
  cat /sys/kernel/mm/ksm/pages_shared
  cat /sys/kernel/mm/ksm/pages_unshared
  ```
- **Fix if confirmed:** Disable KSM on battery: `echo 0 > /sys/kernel/mm/ksm/run`
  Re-enable on AC: `echo 1 > /sys/kernel/mm/ksm/run`

---

### CAUSE-08 — Display Stays at 120Hz on Battery
- **Impact:** MEDIUM (1.5–2.5W)
- **Status:** UNVERIFIED
- **Theory:** The 2560×1600 OLED panel draws measurably more power at 120Hz vs 60Hz.
  Ubuntu/Windows both auto-switch to 60Hz on battery. No such logic exists in Luminos.
- **Diagnostic:**
  ```bash
  kscreen-doctor -o 2>/dev/null | grep -i refresh
  # or
  xrandr 2>/dev/null | grep '*'
  ```
- **Fix if confirmed:** KDE power management → "on battery: switch to 60Hz" OR
  wired into `luminos-power` battery event handler via `kscreen-doctor` call.

---

### CAUSE-09 — WiFi Power Management Disabled
- **Impact:** LOW-MEDIUM (0.3–0.8W)
- **Status:** LIKELY TRUE
- **Theory:** WiFi drivers default to `power_save = off` for connection stability.
  On battery, enabling WiFi power management saves ~0.5W with negligible latency impact.
- **Diagnostic:**
  ```bash
  iwconfig 2>/dev/null | grep -i power
  iw dev wlan0 get power_save 2>/dev/null
  ```
- **Fix if confirmed:** `iwconfig wlan0 power on` on battery.
  Or via NetworkManager: `nmcli connection modify <conn> 802-11-wireless.powersave 3`

---

### CAUSE-10 — Audio Codec Always Powered
- **Impact:** LOW (0.1–0.3W)
- **Status:** LIKELY TRUE
- **Theory:** `snd_hda_intel power_save` defaults to 0 (never sleep). When set to 1,
  the audio codec powers down after 1 second of inactivity.
- **Diagnostic:**
  ```bash
  cat /sys/module/snd_hda_intel/parameters/power_save
  cat /sys/module/snd_hda_intel/parameters/power_save_controller
  ```
- **Fix if confirmed:** `/etc/modprobe.d/audio-power.conf`: `options snd_hda_intel power_save=1`

---

### CAUSE-11 — USB Devices Not Autosuspending
- **Impact:** LOW (0.1–0.5W per device)
- **Status:** UNVERIFIED
- **Theory:** USB devices (keyboard receiver, USB-C hub, etc.) keep their bus active
  unless autosuspend is configured. Each unsuspended device draws idle power.
- **Diagnostic:**
  ```bash
  cat /sys/bus/usb/devices/*/power/runtime_status 2>/dev/null | sort | uniq -c
  cat /sys/bus/usb/devices/*/power/control 2>/dev/null | sort | uniq -c
  ```
- **Fix if confirmed:** `echo auto > /sys/bus/usb/devices/*/power/control` on battery.
  TLP handles this automatically — another reason to add a battery-event script.

---

### CAUSE-12 — Bluetooth Scanning / Active
- **Impact:** LOW (0.1–0.3W)
- **Status:** UNVERIFIED
- **Theory:** If Bluetooth is powered on and in discoverable/scanning mode, it draws
  steady power and generates CPU wakeups.
- **Diagnostic:**
  ```bash
  bluetoothctl show | grep -i powered
  hciconfig hci0 2>/dev/null
  ```
- **Fix if confirmed:** Disable Bluetooth on battery if not in use.

---

### CAUSE-13 — Screen Brightness Not Auto-Reduced on Battery
- **Impact:** VARIABLE (0.5–3W depending on brightness level)
- **Status:** UNVERIFIED
- **Theory:** OLED display power scales roughly linearly with brightness.
  No auto-dim or brightness reduction on unplug event in current Luminos setup.
  Windows and Ubuntu both reduce brightness on battery by default.
- **Diagnostic:**
  ```bash
  cat /sys/class/backlight/*/brightness
  cat /sys/class/backlight/*/max_brightness
  ```
- **Fix if confirmed:** Add to battery event handler: reduce brightness to 60% on unplug,
  restore on plug-in. KDE has this built-in under Power Management settings.

---

## Summary Table

| # | Cause | Impact | Confidence | Status |
|---|---|---|---|---|
| 01 | NVIDIA not in D3cold on battery | HIGH 5-12W | Medium | UNVERIFIED |
| 02 | AMD P-State EPP wrong | HIGH 1-3W | High | UNVERIFIED |
| 03 | PCIe ASPM disabled | HIGH 2-4W | Medium | UNVERIFIED |
| 04 | Daemon 2s polling kills C-states | MED-HIGH 1-2W | High | UNVERIFIED |
| 05 | No TLP / unmanaged subsystems | MED-HIGH 2-4W | LIKELY TRUE | UNVERIFIED |
| 06 | Continuous telemetry writes | MEDIUM 0.5-1.5W | LIKELY TRUE | UNVERIFIED |
| 07 | KSM always on | MEDIUM 0.5-1W | LIKELY TRUE | UNVERIFIED |
| 08 | Display at 120Hz on battery | MEDIUM 1.5-2.5W | Medium | UNVERIFIED |
| 09 | WiFi power save off | LOW-MED 0.3-0.8W | LIKELY TRUE | UNVERIFIED |
| 10 | Audio codec always on | LOW 0.1-0.3W | LIKELY TRUE | UNVERIFIED |
| 11 | USB no autosuspend | LOW 0.1-0.5W | Medium | UNVERIFIED |
| 12 | Bluetooth scanning | LOW 0.1-0.3W | Low | UNVERIFIED |
| 13 | Brightness not auto-reduced | VARIABLE 0.5-3W | Medium | UNVERIFIED |

**Worst-case total if all true: ~15–35W extra drain**
**Best-case if top 5 fixed: likely 4–6hr gain → reaching 7-8hr target**

---

## Debug Plan (Run Before Any Fixes)

### Step 1 — Measure baseline
```bash
# Current power draw in watts
cat /sys/class/power_supply/BAT0/power_now
# or
cat /sys/class/power_supply/BAT0/current_now
cat /sys/class/power_supply/BAT0/voltage_now
# watts = (current_now * voltage_now) / 1e12
```

### Step 2 — NVIDIA state
```bash
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_suspended_time
```

### Step 3 — CPU driver and EPP
```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
```

### Step 4 — ASPM
```bash
cat /sys/module/pcie_aspm/parameters/policy
```

### Step 5 — Full powertop snapshot
```bash
sudo powertop --time=15 --html=/tmp/powertop.html
# Open in browser for full breakdown
```

### Step 6 — C-state residency
```bash
sudo turbostat --interval 5 --quiet 2>/dev/null | head -20
```

---

## Fix Log (append as fixes are applied)

| Date | Agent | Cause Fixed | Result |
|---|---|---|---|
| — | — | — | — |
