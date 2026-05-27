# Luminos OS — Bug Tracker
Last Updated: 2026-05-24 (BUG-055: ZoneWarm/ZoneHot freq cap oscillation + YT stutter)

## Fixed Bugs (new)

### BUG-057 — Chrome --use-gl=disabled on AMD Wayland Flatpak path
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos
- Description: Chrome GPU process ran with `--use-gl=disabled` — entire browser rendered in software (CPU only). No GPU compositing, no hardware acceleration, severe Chrome lag.
- Root Cause: `--render-node-override=/dev/dri/renderD129` was passed to Chrome Flatpak on AMD path. On Wayland, Chrome gets its EGL context from KWin (the Wayland compositor), not by directly opening a DRM render node. The forced render node bypassed the Wayland EGL path, causing EGL initialization failure. Chrome then disabled GL entirely for the session. Second issue: `DRI_PRIME=0` and `VK_ICD_FILENAMES` were set via shell `export` before `flatpak run` — Flatpak sandbox does not inherit parent shell exports; they must be passed via `--env=` to `flatpak run`.
- Fix Applied: Removed `--render-node-override` from AMD path entirely. Moved `DRI_PRIME`, `VK_ICD_FILENAMES`, and `LIBVA_DRIVER_NAME` from shell exports to `--env=` arguments on `flatpak run`. NVIDIA path retains `--render-node-override=/dev/dri/renderD128` (correct for PRIME offload with desktop GL).
- Date Found: 2026-05-26
- Date Fixed: 2026-05-26

### BUG-056 — Chrome YouTube stutter — VAAPI not enabled on AMD path
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/chrome-luminos
- Description: Chrome video (YouTube) stuttered on AMD iGPU path.
- Root Cause: `radeonsi_drv_video.so` (Mesa VAAPI driver) is present at `/usr/lib/dri/` and supports H264/HEVC/VP9/AV1, but `LIBVA_DRIVER_NAME` was not passed into the Flatpak sandbox. Chrome couldn't discover the VAAPI driver → fell back to software video decode → CPU doing all decode work → GPU compositor sync stalls → stutter.
- Fix Applied: Added `--env=LIBVA_DRIVER_NAME=radeonsi` to `flatpak run` in chrome-luminos AMD path. Added `--enable-features=VaapiVideoDecodeLinuxGL,VaapiVideoEncoder` and `--ignore-gpu-blocklist` to Chrome flags. YouTube VP9+AV1 decode now hardware-accelerated on AMD 780M.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

### BUG-055 — Thermal zone oscillation + YT stutter (ZoneWarm/ZoneHot freq caps)
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-power/main.go — applyThermalGovernor(), thermalACZone3C
- Description: YouTube video stuttered. Logs showed zone 1↔2 oscillating every 12s (was 2s after BUG-053 hold-ticks fix), and then zone 2↔3 oscillating every 10s. Every zone transition changed max_freq (5.1→4.0→5.1 GHz or 5.1→3.0→5.1 GHz), causing renderer hitches.
- Root Cause: Any hard freq cap creates a self-defeating cooling loop: cap → CPU cools → cap removed → CPU boosts → reheats → cap reapplied. BUG-053's hold ticks extended the period but did not break the loop. Two issues: (1) ZoneWarm (72°C) had a 4.0GHz cap despite fans running at 100% above 70°C; (2) ZoneHot threshold was 80°C — too conservative for 8845HS (TJmax 105°C) during YouTube.
- Fix Applied: (1) Removed the 4.0GHz AC cap from ZoneWarm — fans at 100% handle cooling above 70°C without a hard cap. Battery path keeps 3.5GHz cap (correct behavior). (2) Raised thermalACZone3C from 80°C→87°C and thermalEmergencyC from 85°C→92°C. YouTube at 82°C stays in ZoneWarm with no cap. ZoneHot (3.0GHz) only triggers at genuine overheating (87°C+).
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

### BUG-053 — Thermal zone 1↔2 oscillation every 2s / Chrome rendering stutter
- Status: SUPERSEDED by BUG-055
- Severity: HIGH
- Component: cmd/luminos-power/main.go — applyThermalGovernor()
- Description: Thermal zone bounced between 1 and 2 every 2-4 seconds under load. Caused visible Chrome tab stutter.
- Root Cause: The 4.0GHz freq cap (applied at zone 2 entry, 72°C) cools the CPU from ~75°C to ~64°C in a single 2s tick, which crosses the 67°C exit threshold. Cap removed, CPU boosts, reheats → loop.
- Fix Applied (partial): Added `thermalDownholdTick` counter requiring 5 consecutive ticks below exit threshold before downgrading. Extended period to 12s but did not break the loop. Full fix in BUG-055: remove cap entirely from ZoneWarm on AC.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24 (fully resolved by BUG-055)

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
