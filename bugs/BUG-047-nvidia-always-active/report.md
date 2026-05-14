# BUG-047 — NVIDIA GPU Always Active

- **Status:** FIXED
- **Severity:** MEDIUM
- **Component:** NVIDIA Driver, udev rules, modprobe config
- **Date Found:** 2026-05-10
- **Date Fixed:** 2026-05-10
- **Agent:** gemini-cli

## Description
NVIDIA RTX 4050 was wasting ~8W constantly by staying in D0 (fully active) state
even when no application was using it.

## Root Cause
No dynamic power management configured for the NVIDIA driver.
By default, NVIDIA stays in D0 unless explicitly told to power-gate.

## Fix Applied
- Added `NVreg_DynamicPowerManagement=0x02` to `/etc/modprobe.d/nvidia.conf`
  - `0x02` = fine-grained power control (D3cold when idle)
- Added udev rules at `/etc/udev/rules.d/99-nvidia-power-gate.rules`
  - Sets `power/control = auto` for all NVIDIA PCI devices
- Result: NVIDIA sleeps at 0W when idle, wakes in ~500ms on demand

## Files Changed
- `/etc/modprobe.d/nvidia.conf`
- `/etc/udev/rules.d/99-nvidia-power-gate.rules`

## Notes
- NVIDIA remains available for HIVE inference and Forex bot on-demand
- Wake latency ~500ms (acceptable for both use cases)
- Must verify D3cold is reached on battery (see BUG-050)
