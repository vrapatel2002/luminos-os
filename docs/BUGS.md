# Luminos OS — Bug Tracker
Last Updated: 2026-03-29

## Format
Each bug entry:
### BUG-XXX — Short title
- Status: OPEN / FIXED / WONTFIX
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Component: which file/module affected
- Description: what happens
- Root Cause: why it happens
- Fix Applied: what was changed
- Date Found: date
- Date Fixed: date

---

## Fixed Bugs

### BUG-046 — luminos-ram "blind" to user desktop session
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-ram, systemd/luminos-ram.service
- Description: The RAM management daemon was not tracking any active windows (Hot/Cold sets always 0), despite windows being open and focused.
- Root Cause: The daemon was running as `root` in a system-level service. It could not connect to the user's D-Bus session bus or access KWin's window state information on Wayland.
- Fix Applied: 1. Updated `luminos-ram.service` to run as `User=shawn`. 2. Used `setcap` to grant `CAP_SYS_PTRACE` directly to the binary so it can still perform `madvise(MADV_PAGEOUT)` on other processes. 3. Ensured the user-session D-Bus socket is accessible.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-045 — Touchpad Input Lag / Jump Detection
- Status: FIXED
- Severity: MEDIUM
- Component: /etc/libinput/local-overrides.quirks, /etc/udev/rules.d/99-cpu-governor.rules
- Description: Input lag during browsing, typing and scrolling felt stuttery, especially on heavy JS sites.
- Root Cause: libinput detecting erratic touchpad hardware events on ASUS ROG G14 (ASUP1208). Kernel logged "Touch jump detected and discarded" at a rate exceeding limits, causing many dropped events.
- Fix Applied: 1. Created /etc/libinput/local-overrides.quirks with AttrTouchSizeRange and AttrPalmSizeThreshold tuned for G14. 2. Changed CPU governor from powersave to schedutil via udev rule.
- Date Found: 2026-05-09
- Date Fixed: 2026-05-09

### BUG-043 — HIVE popup crash (import: command not found)
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/luminos-hive-popup
- Description: Pressing SUPER+SPACE to launch HIVE popup crashes with bash syntax errors like "import: command not found".
- Root Cause: An agent rewrote the popup script as a Python script using GTK4 (which is banned), but the global shortcut was executing it via `bash -x`.
- Fix Applied: Rewrote the script to a native bash script using `kdialog` for UI and `llama-cli` for inference, matching project rules.
- Date Found: 2026-04-26
- Date Fixed: 2026-04-26
