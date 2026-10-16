# HARDWARE — what this G14 (GA403UU, Ryzen 9 8845HS, kernel 7.0.5) can actually turn, measured 2026-10-15
# [CHANGE: claude-code | 2026-10-15]

## Continuous knobs (true dials)
| Knob | Path | Range | Cost per write | Wakes dGPU? |
|---|---|---|---|---|
| CPU package power limits (sustained / slow / fast) | `/sys/devices/platform/asus-nb-wmi/ppt_pl1_spl`, `ppt_pl2_sppt`, `ppt_fppt` (W, integer) | tested 15–65 W | ~33 ms per write (WMI DEVS 0x1200A3 / 0x1200A0 / 0x1200C1 → ALIB) | **NO** — 12 writes, 0 ACPI notifies, 0 rpm_resume (kprobes) |
| CPU frequency ceiling | `/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq` (kHz) | 419 421 – 5 137 904 | µs, kernel only | no |
| CPU frequency floor | `scaling_min_freq` | ≥ 419 421 (now 1 100 980 = lowest_nonlinear) | µs | no |
Read-back of ppt_* returns the driver's cached last write ("5" = never written since boot), NOT the firmware's live limit.
asus-armoury `firmware-attributes` ppt_* return ENODEV (custom tuning group disabled) — use the asus-nb-wmi files.

### Measured: full 16-thread load vs PPT limit (luminos-power stopped, profile performance)
| limit | package W | Tctl | avg clock |
|---|---|---|---|
| 15 W | 13.4 | 59.8 °C | 1.41 GHz |
| 20 W | 22.4 | 65.9 °C | 2.69 GHz |
| 30 W | 33.7 | 81.4 °C | 2.92 GHz |
| 35 W | 39.5 | 86.9 °C | 3.59 GHz (profile flipped mid-run by beast mode — dirty) |
| 45 W | 41.4 | 95.0 °C | 3.62 GHz |
| 65 W | 36.1 | 95.0 °C | 3.54 GHz |
| firmware default (balanced, luminos cap lifted) | 44.0 | 93.4 °C | 3.72 GHz |
Above ~40 W the chip sits on its 95 °C limit: cooling, not the limit, is binding. Idle ≈ 6–10 W.

## Stepped knobs (switches) — keep their changes rare
| Knob | Steps | Cost |
|---|---|---|
| EPP `energy_performance_preference` | 5 strings (default/performance/balance_performance/balance_power/power); numeric → EINVAL | cheap, no BIOS |
| ASUS platform profile (`platform-profile-1` asus-wmi / `/sys/firmware/acpi/platform_profile`) | quiet / balanced / performance | **wakes dGPU every time** (Notify NPCF 0xC0 ×2 + EC _QD9 → PEGP 0xC0); asusd writes 0x120075 up to 7× per change; also rewrites fan curves |
| AMD PMF profile (`platform-profile-0`) | low-power / balanced / performance | not tested |
| Fan curves (hwmon8 `pwm{1,2,3}_auto_point{1..8}_{temp,pwm}` / asusctl) | 8 points per fan — the curve itself IS a continuous temp→duty map run by the EC | **wakes dGPU** on enable (WMNB 0x00110024 → Notify NPCF) |
| Fan direct duty | none: `pwm*_enable` only full-speed / auto | — |
| iGPU | `power_dpm_force_performance_level` auto/low/high/manual; no power cap | not tested |

## Firmware behaviour that matters
- Every BIOS call that changes profile, fan curve, NV dynamic boost (0x00120098) or NV temp target (0x001200C0), and EC queries
  _QD9/_QD4/_QA8, recompute the GPU power share → `Notify(.. , 0xC0)` → nvidia 610 wakes the card ~20 s (BUG-198, NVIDIA #1300).
- EC also sent `Notify(PEGP, 0xD1/0xD2)` (D-notifier power levels) under sustained heavy CPU load.
- PPT writes go to AMD ALIB (`ALIB(0x0C, UTDP)`), no NVIDIA notify in that path (DSDT WMNB branches 0x1200A0/A3/C1).

## Measured 2026-10-15 19:40 — a platform-profile change RESETS the PPT limits
PPT set to 15 W → full load 12.1 W / 52.6 °C. Then platform_profile quiet → balanced → same load 51.7 W / 95 °C, while
`ppt_pl1_spl` still read back "15" (driver cache). So: any profile change (asusd, firmware, a user pressing the ROG key, resume?)
silently restores the firmware's PPT table, and the read-back cannot detect it. A controller that owns PPT must re-assert it
(cheap: no dGPU wake) on a timer and after resume/profile-change events, and must not trust the read-back.

## Measured 2026-10-15 20:40 — pre-build checks (kprobes on asus_wmi_evaluate_method3 + acpi notify + rpm_resume)
- Q2: 10× read of /sys/firmware/acpi/platform_profile + hwmon8 pwm1_auto_point1_pwm → 0 BIOS calls. Free.
- Q5: 10× read of hwmon7 fan1_input → 10 BIOS calls (DSTS), 0 notifies. Not a wake, but the daemon must not poll it.
- Q12: 15× write of ppt_pl1_spl at 1 Hz → 15 BIOS calls, 0 notifies, 0 dGPU wakes. The 60 s refresh is safe.
- Q4: package power readable: /sys/class/powercap/intel-rapl:0/energy_uj ("package-0", root-only) — 7 W vs sensors PPT 6.1 W at idle.
- Q14: /etc/asusd/asusd.ron has change_platform_profile_on_ac: true (→ Performance) and _on_battery: true (→ Quiet) and
  platform_profile_linked_epp: true — every cable event = profile change = dGPU wake + PPT reset. Must be set false.
- Q16: 780M = card2 (vendor 0x1002, gpu_busy_percent present), k10temp = hwmon6 (temp1_label Tctl), asus fan curve = hwmon8.
- Q13: EPP choices: default performance balance_performance balance_power power.
- No stress-ng / sysbench on the box → the A/B uses our own Go load+benchmark tool.
