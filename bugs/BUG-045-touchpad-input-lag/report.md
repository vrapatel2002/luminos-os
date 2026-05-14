# BUG-045 — Touchpad Input Lag / Jump Detection

- **Status:** FIXED
- **Severity:** MEDIUM
- **Component:** `/etc/libinput/local-overrides.quirks`, CPU governor
- **Date Found:** 2026-05-09
- **Date Fixed:** 2026-05-09
- **Agent:** gemini-cli

## Description
Input lag during browsing; stuttery scrolling on the G14 touchpad under Wayland/KDE.

## Root Cause
libinput was discarding "touch jump" events on the G14 touchpad model.
CPU governor was set to `powersave`, causing delayed response to input bursts.

## Fix Applied
- Added libinput quirks override for the G14 touchpad
- Switched CPU governor to `schedutil` via permanent udev rule

## Files Changed
- `/etc/libinput/local-overrides.quirks`
- `/etc/udev/rules.d/` (CPU governor rule)
