# Luminos OS — Bug Tracker
Last Updated: 2026-05-10

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

### BUG-049 — Claude Desktop Memory Leak
- Status: MONITORING
- Severity: MEDIUM
- Component: Claude Desktop (Electron)
- Description: Electron renderer running 101+ hours. Memory grows from 300MB to 2.1GB over time.
- Root Cause: All Electron apps exhibit this growth pattern.
- Fix Applied: [Workaround] Restart Claude Desktop daily. Added background leak detection to `luminos-ram` (v3.1) to alert on future occurrences.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10 (Monitoring)

### BUG-048 — luminos-power Thermal Oscillation
- Status: OPEN (PENDING FIX)
- Severity: HIGH
- Component: cmd/luminos-power
- Description: CPU temperature oscillating between 60-88°C constantly.
- Root Cause: Profile switching thresholds have no hysteresis, causing switches every 2-4 seconds. Performance mode raises TDP, making heat worse.
- Planned Fix: Remove auto-Performance switching; stay in Balanced with aggressive fan curve.
- Date Found: 2026-05-10

### BUG-047 — NVIDIA GPU Always Active
- Status: FIXED
- Severity: MEDIUM
- Component: NVIDIA Driver / Power Management
- Description: NVIDIA GPU wasting ~8W constantly by staying in D0 state.
- Root Cause: No power gating configured.
- Fix Applied: Implemented udev rules for auto power gating and enabled `NVreg_DynamicPowerManagement=0x02` in modprobe.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-046 — Chrome Using NVIDIA GPU
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/chrome-luminos
- Description: NVIDIA GPU active during all browsing, wasting 8-15W.
- Root Cause: Wrapper had `--render-node-override=/dev/dri/renderD129` (NVIDIA).
- Fix Applied: Removed render-node-override. `DRI_PRIME=0` correctly forces AMD iGPU.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-046b — luminos-ram "blind" to user desktop session
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-ram, systemd/luminos-ram.service
- Description: The RAM management daemon was not tracking any active windows.
- Root Cause: The daemon was running as `root` and could not connect to user D-Bus.
- Fix Applied: Updated service to run as `User=shawn` with `CAP_SYS_PTRACE`.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-045 — Touchpad Input Lag / Jump Detection
- Status: FIXED
- Severity: MEDIUM
- Component: /etc/libinput/local-overrides.quirks
- Description: Input lag during browsing; stuttery scrolling.
- Root Cause: libinput discarding "touch jump" events on G14 touchpad.
- Fix Applied: libinput quirks + schedutil CPU governor.
- Date Found: 2026-05-09
- Date Fixed: 2026-05-09

### BUG-043 — HIVE popup crash (import: command not found)
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/luminos-hive-popup
- Description: SUPER+SPACE launch crash.
- Root Cause: Agent wrote GTK4 Python script for a bash-executed shortcut.
- Fix Applied: Rewrote to native bash + kdialog.
- Date Found: 2026-04-26
- Date Fixed: 2026-04-26
