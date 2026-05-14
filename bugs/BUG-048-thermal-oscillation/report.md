# BUG-048 — luminos-power Thermal Oscillation

- **Status:** FIXED
- **Severity:** HIGH
- **Component:** `cmd/luminos-power/main.go`
- **Date Found:** 2026-05-10
- **Date Fixed:** 2026-05-10
- **Agent:** gemini-cli

## Description
CPU temperature was oscillating between 60–88°C constantly.
System kept switching between Balanced and Performance profiles rapidly.

## Root Cause
Profile switching thresholds had no hysteresis and no hold time.
Sequence: Performance → more heat → switch to Quiet → CPU throttles → load climbs
→ switch to Performance → more heat → (loop forever)

## Fix Applied
- Removed automatic Performance switching entirely for CPU load triggers
- Added 30-second hold time between any profile change
- Added hysteresis for emergency Quiet: enter at >85°C, exit only when <75°C
- Applied aggressive fan curves to all profiles (100% at 80°C)
  - Fan handles heat independently of profile switching

## Files Changed
- `cmd/luminos-power/main.go` (v2.1)
