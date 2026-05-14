# BUG-046b — luminos-ram Blind to Desktop Session

- **Status:** FIXED
- **Severity:** HIGH
- **Component:** `cmd/luminos-ram`, `systemd/luminos-ram.service`
- **Date Found:** 2026-05-10
- **Date Fixed:** 2026-05-10
- **Agent:** gemini-cli

## Description
The RAM management daemon was not tracking any active windows or KDE desktop session.
Hot/warm/cold set logic was operating blind — it could not see which apps were on screen.

## Root Cause
The daemon was running as `root` and could not connect to the user D-Bus session.
KDE/Wayland window tracking requires access to the user session bus (`DBUS_SESSION_BUS_ADDRESS`).

## Fix Applied
- Updated `luminos-ram.service` to run as `User=shawn`
- Added `CAP_SYS_PTRACE` capability for process inspection
- Wired D-Bus session environment variables into the service unit

## Files Changed
- `~/.config/systemd/user/luminos-ram.service` (or `/etc/systemd/system/luminos-ram.service`)
