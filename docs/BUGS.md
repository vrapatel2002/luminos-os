# Luminos OS — Bug Tracker
Last Updated: 2026-05-24

## Fixed Bugs (new)

### BUG-053 — Thermal zone 1↔2 oscillation every 2s / Chrome rendering stutter
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-power/main.go — applyThermalGovernor()
- Description: Thermal zone bounced between 1 and 2 every 2-4 seconds under load. Caused visible Chrome tab stutter.
- Root Cause: The 4.0GHz freq cap (applied at zone 2 entry, 72°C) cools the CPU from ~75°C to ~64°C in a single 2s tick, which crosses the 67°C exit threshold (72-5°C hysteresis). The cap is immediately removed, CPU boosts back to 5.1GHz, reheats in 2 seconds → repeat indefinitely. The 5°C hysteresis was on the temperature, not on time. One tick below the threshold was enough to remove the cap.
- Fix Applied: Added `thermalDownholdTick` counter. Zone downgrades now require `thermalDowngradeHoldTicks=5` consecutive ticks (10 seconds on AC) below the exit threshold. Zone upgrades remain immediate. Counter resets on AC transition and beast mode entry/exit.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

### BUG-054 — Chrome tab stutter on AMD iGPU path (--enable-zero-copy)
- Status: FIXED
- Severity: MEDIUM
- Component: /usr/local/bin/chrome-luminos
- Description: Tab scrolling and rendering hitches on AMD iGPU path.
- Root Cause: `--enable-zero-copy` causes intermittent rendering hitches with AMD Mesa on Wayland. Also compounded by BUG-053 CPU freq oscillation.
- Fix Applied: Removed `--enable-zero-copy` from the AMD (igpu) path in chrome-luminos. NVIDIA path keeps it (works correctly with desktop GL). Added `--enable-features=MemorySaver` to both paths to enable tab sleeping.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

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

### BUG-052 — Kickoff Launcher Empty / Chrome Not Searchable
- Status: FIXED
- Severity: HIGH
- Component: ~/.config/plasma-org.kde.plasma.desktop-appletsrc, ~/.local/share/applications/com.google.Chrome.desktop
- Description: Opening the Start button showed a blank screen. Searching "chrome" returned nothing.
- Root Cause 1: `applicationsDisplay=0` — Kickoff defaults to Favorites tab. No apps were pinned to Favorites, so the launcher appeared empty. The All Applications tab existed but user had no way to know.
- Root Cause 2: Chrome desktop file Exec line had `@@u %U @@` — Flatpak-specific URL forwarding syntax that is invalid for a plain wrapper script. Caused incorrect desktop file parsing.
- Fix Applied: Set `applicationsDisplay=1` in plasma-org.kde.plasma.desktop-appletsrc (Kickoff opens to All Applications by default). Fixed Exec to `Exec=/usr/local/bin/chrome-luminos %U`. Rebuilt sycoca index via `kbuildsycoca6 --noincremental`. Restarted plasmashell via `systemctl --user restart plasma-plasmashell`.
- Date Found: 2026-05-21
- Date Fixed: 2026-05-21

### BUG-051 — Display Stutter / 120Hz Compositing Lag
- Status: FIXED
- Severity: MEDIUM
- Component: ~/.config/kwinoutputconfig.json, ~/.config/kwinrc
- Description: Desktop felt unsmooth/stuttery at 120Hz. Fans spinning without reason. kwin_wayland at 19% CPU idle.
- Root Cause: `vrrPolicy` was `"Never"` — compositor locked to hard 120Hz deadline every 8.33ms. Any frame taking slightly longer caused a dropped frame. Also: `GLPreferBufferSwap=a` (auto) and no latency policy set, both leaving performance on the table.
- Fix Applied: Set `vrrPolicy: "Automatic"` in kwinoutputconfig.json. Set `LatencyPolicy=Low` and `GLPreferBufferSwap=e` in kwinrc. KWin reloaded via `qdbus6 org.kde.KWin /KWin reconfigure`.
- Date Found: 2026-05-21
- Date Fixed: 2026-05-21

### BUG-050 — System Processes Keeping NVIDIA dGPU in D0 State
- Status: FIXED
- Severity: HIGH
- Component: /etc/environment
- Description: NVIDIA GPU staying awake (D0, ~8W) even when idle. KDE system processes (ksecretd, plasmashell, Xwayland, baloorunner) were opening NVIDIA EGL by default.
- Root Cause: No EGL vendor preference set — libEGL defaulted to NVIDIA (60_nvidia.json) for all processes. KWin also advertising renderD129 (NVIDIA) to Wayland clients via linux-dmabuf protocol.
- Fix Applied: Added to /etc/environment: `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json` (force AMD Mesa EGL for all session apps) and `KWIN_DRM_DEVICES=/dev/dri/card2` (restrict KWin to AMD DRM only). PRIME render offload for games still works.
- Date Found: 2026-05-14
- Date Fixed: 2026-05-14

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
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-power
- Description: CPU temperature oscillating between 60-88°C constantly.
- Root Cause: Profile switching thresholds had no hysteresis and no hold time, causing rapid toggling between Balanced and Performance. Performance mode raised TDP, causing more heat.
- Fix Applied: Removed auto-Performance switching. System stays in Balanced on AC with an aggressive fan curve (100% at 80°C). Added 30s hold time between profile changes and hysteresis for emergency Quiet mode (>85°C to enter, <75°C to exit).
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

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
