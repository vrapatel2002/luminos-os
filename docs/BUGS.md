# Luminos OS — Bug Tracker
Last Updated: 2026-06-12 (BUG-065/066/067 ACTIVE after post-training daemon restart; BUG-069 workaround reverted, luminos-train-mode created)

## Open Bugs

### BUG-069 — luminos-power v4.2 GPU TGP switching is a silent no-op: `nvidia-smi -pl` unsupported on mobile but exits 0
<!-- [CHANGE: claude-code | 2026-06-11] -->
- Status: OPEN (code fix pending; workaround reverted 2026-06-12 — nvidia-powerd re-masked. Reusable interim: `scripts/luminos-train-mode` on/off wraps nvidia-powerd + 100% fan pin for training runs)
- Severity: HIGH
- Component: cmd/luminos-power/main.go (setGPUTGP, line ~1304)
- Description: The v4.2 "GPU TGP dynamic switching" feature (55W↔90W, shipped 2026-06-03) never changed the GPU power limit once. `nvidia-smi -pl 90` on the mobile RTX 4050 prints "Changing power management limit is not supported … Treating as warning and moving on" and **exits 0**, so `runCmd` sees success and the daemon logs "GPU TGP → 90W" while hardware stays at 55W. All TGP log lines since 2026-06-03 are fiction; the daemon's internal state (`currentGPUTGPW=90`) diverges from reality, which also suppresses retry attempts. Discovered during HOPE training: GPU pegged at 55.0W/55W limit, P0, 92% util, clocks 2385/3105 MHz.
- Root Cause: nvidia-smi treats the unsupported -pl operation as a warning, not an error (exit 0). On Ada laptops TGP above base is controlled by Dynamic Boost (`nvidia-powerd`) or ASUS `nv_dynamic_boost` firmware attribute — `asus-armoury` reports nv_dynamic_boost/nv_temp_target "unavailable" on GA403UU, so nvidia-powerd is the only working mechanism. It was masked (BUG-047 idle-drain era, unmask undocumented).
- Workaround Applied (2026-06-11, temporary): unmasked + started `nvidia-powerd` → limit rose 55→88W dynamically, clocks 2385→2655 MHz (+11%) at 71°C with flat-100% fan curves. Revert steps in PENDING_RESTART.md.
- Proper Fix (after training): in setGPUTGP, parse nvidia-smi output for "not supported" OR read back `power.limit` after write and compare; manage Dynamic Boost via nvidia-powerd lifecycle instead of -pl; decide nvidia-powerd policy (idle drain vs boost) in LUMINOS_DECISIONS.md.
- Date Found: 2026-06-11

## Fixed Bugs (new)

### BUG-068 — Incomplete Tahoe revert: GTK ran WhiteSur-Dark + Kvantum pinned to MacTahoe for a month
<!-- [CHANGE: claude-code | 2026-06-11] -->
- Status: FIXED
- Severity: MEDIUM
- Component: GTK settings.ini, ~/.config/Kvantum, kwinrc, AUR whitesur-* packages
- Description: The 2026-05-11 Tahoe revert ("restored clean KDE Plasma Breeze Dark state") only reverted Plasma-side settings. Left behind: GTK3/4 `gtk-theme-name=WhiteSur-Dark` (GTK apps rendered macOS-style while Qt rendered Breeze), `~/.config/Kvantum/kvantum.kvconfig` still `theme=MacTahoe`, legacy `AnimationSpeed=3` in kwinrc [Compositing] (set by apply-tahoe-theme.sh; conflicts with Plasma 6 `AnimationDurationFactor=1.0`), 6× MacTahoe GTK themes in ~/.themes, MacTahoe icons/aurorae decorations/desktoptheme/wallpapers in ~/.local/share, and 3 AUR packages (whitesur-gtk/icon/cursor-theme-git). Net effect: a three-way Breeze/WhiteSur/MacTahoe hybrid — the "stitched-together" UI feel.
- Root Cause: Revert only undid kwriteconfig6/Plasma changes; never touched GTK configs, Kvantum, ~/.themes, ~/.local/share assets, or pacman packages installed for Tahoe.
- Fix Applied: GTK3/4 → `Breeze-Dark`; deleted ~/.config/Kvantum, ~/.themes/MacTahoe-*, MacTahoe icons/aurorae/desktoptheme/wallpapers (incl. TahoeDusk.webp — verified not referenced by desktop or lockscreen); removed `AnimationSpeed` key from kwinrc; `pacman -Rns whitesur-{gtk,icon,cursor}-theme-git`; KWin reconfigured. Verified zero mac/tahoe/whitesur remnants on disk.
- Date Found: 2026-06-11
- Date Fixed: 2026-06-11

### BUG-067 — Shared RuntimeDirectory: restarting one daemon unlinks every other daemon's socket
- Status: FIXED — ACTIVE (one-time daemon restart done 2026-06-12; all /run/luminos sockets rebound and verified)
- Severity: HIGH
- Component: systemd units — luminos-ai, luminos-power, luminos-router, luminos-sentinel, luminos-ram
- Description: All daemons share `RuntimeDirectory=luminos` (/run/luminos). When luminos-power restarted on 2026-06-08 07:07, systemd removed and recreated /run/luminos, unlinking ai.sock, sentinel.sock, and ram.sock. The daemons kept listening on unlinked inodes (visible in `ss -xl`), but any client connecting by path got ENOENT. Sentinel→AI threat reports and the RAM widget were silently dead for 2 days.
- Root Cause: systemd removes a RuntimeDirectory on service stop by default. With a SHARED directory, the first service to stop destroys every sibling's socket. luminos-ram additionally never declared RuntimeDirectory at all — it depended on the other units creating the dir first.
- Fix Applied: `RuntimeDirectoryPreserve=yes` added to all five units (repo `systemd/` + `/etc/systemd/system/`), and `RuntimeDirectory=luminos` added to luminos-ram so it is self-sufficient. `systemctl daemon-reload` done. NOT restarted (HOPE model training in progress) — see PENDING_RESTART.md.
- Date Found: 2026-06-10
- Date Fixed: 2026-06-10

### BUG-066 — luminos-ram capability bounding set stripped CAP_KILL/CAP_SYS_NICE — freeze/kill/boost silently EPERM
- Status: FIXED — ACTIVE (daemon restart 2026-06-12; caps verified: cap_kill cap_sys_ptrace cap_sys_nice)
- Severity: HIGH
- Component: systemd/luminos-ram.service
- Description: The unit ran the daemon as root but with `CapabilityBoundingSet=CAP_SYS_PTRACE`, which strips ALL other capabilities — including CAP_KILL (SIGSTOP/SIGCONT/SIGKILL of other users' processes), CAP_SYS_NICE (setpriority boost AND process_madvise(MADV_PAGEOUT)). Every freeze/thaw/cold-kill/priority action failed with EPERM, and all those syscall errors were ignored in code (audit finding), so nothing was ever logged.
- Root Cause: Bounding set chosen when madvise() was still a stub (BUG-065) — nothing exercised the missing capabilities, so the gap was invisible.
- Fix Applied: `CapabilityBoundingSet=CAP_SYS_PTRACE CAP_SYS_NICE CAP_KILL` + matching AmbientCapabilities.
- Date Found: 2026-06-10
- Date Fixed: 2026-06-10

### BUG-065 — luminos-ram madvise() was a stub: every MADV_PAGEOUT in the eviction pipeline was a no-op
- Status: FIXED — ACTIVE (v3.5 binary running since 2026-06-12 restart)
- Severity: CRITICAL
- Component: cmd/luminos-ram/main.go
- Description: `madvise(pid, hint)` logged a debug line for MADV_WILLNEED and returned nil. All call sites — evictLast() hot→cold eviction, bottom-tier compression, Chrome renderer compression — did nothing. The madvPageoutCounter metric incremented anyway, so telemetry claimed compression was happening. The RAM manager's core memory-reclaim function never existed.
- Root Cause: Stub left in during v3.0 development; metric increments masked it.
- Fix Applied: Real `process_madvise(2)` implementation — `pidfd_open` on target, iovecs built from /proc/<pid>/maps (readable private mappings, kernel special mappings skipped), chunked at UIO_MAXIOV=1024. MADV_WILLNEED EINVAL treated as soft-miss for older kernels. Also fixed in same pass: D-Bus AddMatch errors now logged (silent focus-tracking death), session-bus connection cached instead of re-dialed every 3s tick, getChildPIDs() rewritten from full /proc/*/stat scan (O(all processes), direct children only — never found Chrome renderers, which hang off the zygote) to recursive /proc/<pid>/task/*/children walk (O(descendants), full tree).
- Verification: standalone test against a 64MB perl process — RSS 70,412 KB → 2,420 KB (68 MB reclaimed to zram) via the exact same code path.
- Date Found: 2026-06-10
- Date Fixed: 2026-06-10

### BUG-064 — MT5 KDE launcher waking NVIDIA GPU
- Status: FIXED
- Severity: MEDIUM
- Component: ~/.local/share/applications/wine/Programs/MetaTrader 5/MetaTrader 5.desktop
- Description: Launching MT5 via KDE app menu woke NVIDIA GPU because the .desktop Exec used plain `wine` with no GPU env vars. Without DRI_PRIME=0 and Mesa EGL/GLX/Vulkan overrides, Wine's GL falls back to the NVIDIA libGL (registered by nvidia-drm kernel module).
- Root Cause: The .desktop file was auto-generated by Wine install and not updated with the AMD-forcing env vars that mt5-luminos/luminos-wine-launcher had. Previous fix (gemini-cli 2026-05-11) created mt5-luminos but didn't wire it to the .desktop.
- Fix Applied: Created /usr/local/bin/luminos-mt5 — AMD forced (DRI_PRIME=0, __GLX_VENDOR_LIBRARY_NAME=mesa, 50_mesa.json EGL, radeon_icd Vulkan, radeonsi VAAPI). Desktop file Exec updated to luminos-mt5. Also adds market-closed warning (kdialog) on weekends. mt5-terminal.service updated with same env vars for headless service path.
- Date Found: 2026-05-30
- Date Fixed: 2026-05-30

### BUG-063 — HIVE web search returns "llama-server not running" error
- Status: FIXED
- Severity: HIGH
- Component: scripts/hive-daemon.py — _handle_chat
- Description: Web search queries always failed with "(llama-server not running — start it first)" even though web search doesn't need a model loaded.
- Root Cause: Web intent detection relied on Nexus routing (Path B). Path B calls `_swap_model("nexus")` immediately, which fails if llama-server isn't running. The [ROUTE:WEB] tag never reached the web handler.
- Fix Applied: Added early web intercept at the TOP of `_handle_chat`, before any `_swap_model` call. `detect_intent()` runs first — if result is "web", search runs immediately. If llama IS loaded, Nexus synthesizes the results. If llama is NOT loaded, raw formatted results are returned directly to the user.
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-062 — Chrome NVIDIA path: --ozone-platform=wayland + Vulkan crashes on PRIME offload
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos (NVIDIA path)
- Description: Selecting NVIDIA in the GPU picker caused Chrome to crash with SIGTRAP. Error: `'--ozone-platform=wayland' is not compatible with Vulkan` and `importing the supplied dmabufs failed (error 7)`.
- Root Cause: NVIDIA is a PRIME offload device — it renders offscreen and hands frames to the AMD KWin compositor via DMA-BUF. On Wayland + Vulkan, this cross-device DMA-BUF import between NVIDIA and AMD fails. Chrome's own Wayland platform code explicitly rejects this combination and crashes. AMD path is unaffected because AMD IS the KWin compositor (same device, no DMA-BUF handoff needed).
- Fix Applied: NVIDIA path switched from `--ozone-platform=wayland` to `--ozone-platform=x11` (XWayland). XWayland handles the NVIDIA→AMD frame handoff via X11 protocol instead of Wayland DMA-BUF — well-tested with NVIDIA PRIME. Also removed VAAPI feature flags from NVIDIA path (LIBVA_DRIVER_NAME=nvidia and VaapiVideoDecodeLinuxGL are non-functional on NVIDIA Linux; removing them avoids spurious init errors).
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-061 — Chrome AMD path: wrong Vulkan ICD filename → no AMD Vulkan device → SwiftShader CPU fallback → --use-gl=disabled
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos (AMD path)
- Description: After BUG-060 fix switched to --use-gl=angle --use-angle=vulkan, Chrome AMD path still landed on --use-gl=disabled. GPU process could not initialize Vulkan on AMD.
- Root Cause: BUG-060 fix set `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json` for the AMD path. This file does NOT exist on Arch Linux. Arch Mesa installs `radeon_icd.json` (no architecture suffix). Some other distros (Ubuntu, Fedora) install `radeon_icd.x86_64.json` — the Arch package does not. With a non-existent ICD path, the Vulkan loader finds no AMD ICD, enumerates only SwiftShader (CPU software Vulkan). ANGLE Vulkan then uses SwiftShader as its Vulkan device. Chrome detects software Vulkan and sets --use-gl=disabled to avoid software rendering overhead.
- Fix Applied: `radeon_icd.x86_64.json` → `radeon_icd.json` in chrome-luminos AMD path. Also cleared Chrome GPU/shader caches (GPUCache, GrShaderCache, ShaderCache) to remove stale --use-gl=disabled state from previous crash sessions.
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-060 — Chrome native: --use-gl=egl crashes GPU process → software rendering → YouTube stutter
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos
- Description: GPU process at 81.5% CPU, --use-gl=disabled, all GPU features disabled, YouTube stuttering on battery. chrome://gpu showed "GPU process was unable to boot: GPU access is disabled due to frequent crashes."
- Root Cause: Launcher passed --use-gl=egl which native Chrome 148 maps to gl=egl-gles2,angle=none. Native Chrome 148 only allows ANGLE backends: (gl=egl-angle,angle=opengl), (gl=egl-angle,angle=opengles), (gl=egl-angle,angle=vulkan). gl=egl-gles2 is not in the allowlist → GPU process exits immediately → Chrome retries 7 times → declares GPU broken → disables all hardware acceleration for the session. This happened on every Chrome launch since switching from Flatpak to native (BUG-059). On battery, software decode + luminos-power CPU cap = double throttle → severe stutter.
- Fix Applied: Changed --use-gl=egl to --use-gl=angle --use-angle=vulkan for both AMD and NVIDIA paths. AMD uses Mesa radv (VK_ICD_FILENAMES=radeon_icd.json), NVIDIA uses proprietary Vulkan (VK_ICD_FILENAMES=nvidia_icd.json). Cleared Chrome GPU/shader caches to remove stale crash state. Note: AMD ICD filename was still wrong at time of BUG-060 fix (see BUG-061).
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-059 — Chrome GPU subprocess --use-gl=disabled — three layered mistakes (corrected)
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos (AMD path), AGENTS.md section 2
- Description: Chrome GPU subprocess spawns with `--use-gl=disabled --render-node-override=/dev/dri/renderD129` even after BUG-057 and BUG-058 fixes. Software rendering, GPU process at 50%+ CPU, severe video stutter.
- Root Cause (confirmed via sysfs /sys/class/drm/renderD*/device/vendor):
  1. WRONG RENDER NODE DOCS: AGENTS.md section 2 had render nodes backwards. Actual mapping: renderD128=NVIDIA (0x10de, card1 pci 01:00.0), renderD129=AMD (0x1002, card2 pci 65:00.0). Chrome was correctly selecting renderD129 (AMD) all along. The problem was EGL init failure on AMD, not wrong device selection.
  2. WRONG EGL VENDOR PATH (BUG-059 first attempt): Set __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json — this path does NOT exist inside the Flatpak sandbox. File is actually at /usr/lib/x86_64-linux-gnu/GL/glvnd/egl_vendor.d/50_mesa.json. Setting a non-existent path causes GLVND to load zero EGL vendors → guaranteed EGL failure.
  3. WRONG GL BACKEND: --use-gl=egl uses Chrome's bundled ANGLE. Even though ANGLE bypasses GLVND for most operations, on Wayland it still uses system GLVND EGL for display backend selection. Inside the Flatpak, NVIDIA EGL vendors (09_nvidia_wayland2.json, 10_nvidia.json) have lower sort numbers than Mesa (50_mesa.json) and claim the Wayland EGL display first. NVIDIA EGL cannot drive AMD hardware (renderD129) → ANGLE EGL init fails → --use-gl=disabled.
- Fix Applied (final): Abandoned Flatpak Chrome entirely. Installed native google-chrome-stable 148.0.7778.178 via AUR (yay). The Flatpak Freedesktop SDK 25.08 runtime has the NVIDIA GL extension installed which injects NVIDIA EGL vendors (09_nvidia_wayland2, 10_nvidia) that sort before Mesa (50_mesa) — this is baked into the Flatpak runtime and cannot be overridden at the launcher flag level without removing the NVIDIA GL extension from the Flatpak runtime itself. Native Chrome inherits /etc/environment directly (includes __EGL_VENDOR_LIBRARY_FILENAMES=50_mesa.json), no GL layer indirection, no NVIDIA EGL contamination. chrome-luminos updated to use google-chrome-stable with env vars via exec env. Created ~/.config/chrome-flags.conf (--ozone-platform=wayland). AGENTS.md section 2 render node table corrected (renderD128=NVIDIA, renderD129=AMD).
- Date Found: 2026-05-27
- Date Fixed: 2026-05-27

### BUG-058 — Chrome --use-gl=disabled recurring — chrome-flags.conf injecting --enable-zero-copy globally
- Status: FIXED
- Severity: CRITICAL
- Component: ~/.var/app/com.google.Chrome/config/chrome-flags.conf
- Description: Chrome GPU process running at 51% CPU with `--use-gl=disabled` and `--render-node-override=/dev/dri/renderD129` again after BUG-057 fix. Identical symptom: software rendering, severe lag.
- Root Cause: `chrome-flags.conf` contained `--enable-zero-copy` as a global flag, applied to every Chrome launch before the per-GPU launcher flags. `--enable-zero-copy` forces Chrome to open a DRM render node directly for DMA-BUF buffer sharing. Inside the Flatpak sandbox, Chrome's zero-copy subsystem picks `renderD129` (NVIDIA — first DRM device enumerated) regardless of `DRI_PRIME=0`. This hits the same EGL init failure as BUG-057, producing `--use-gl=disabled` in the spawned GPU process. The chrome-luminos launcher had already removed `--enable-zero-copy` from its flags (BUG-054 fix), but the global conf file re-injected it on every launch.
- Fix Applied: Stripped `chrome-flags.conf` to only `--ozone-platform=wayland`. Removed `--enable-zero-copy`, `--enable-gpu-rasterization`, `CanvasOopRasterization`, `UseSkiaRenderer`. All GPU-specific flags now live exclusively in `/usr/local/bin/chrome-luminos` where they are controlled per-GPU choice.
- Date Found: 2026-05-27
- Date Fixed: 2026-05-27

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
