# LUMINOS OS — SERVICE & OPERATIONS HANDBOOK
*Last Updated: 2026-05-21 | Hardware: ASUS ROG G14 GA403UU | OS: Arch Linux + KDE Plasma 6.6.4*

---

## PART 0 — HOW TO USE THIS HANDBOOK

### Reading Commit References
Every commit reference in this document is a real SHA from this repository. Inspect any of them with:
```bash
git -C ~/luminos-os show HASH
git -C ~/luminos-os show HASH --stat   # files changed only
```
Example: `git -C ~/luminos-os show 385f1302` shows the fan curve revert in full diff.

### Reading Code References
Code references use the shorthand `filename:LINE`. The filename is always relative to the repo root at `~/luminos-os/`. Examples:
- `main.go:726` → `~/luminos-os/cmd/luminos-power/main.go` line 726
- `kcm_luminos_keyboard.cpp:191` → `~/luminos-os/src/kcms/kcm_luminos_keyboard/kcm_luminos_keyboard.cpp` line 191

### How to Use the Emergency Card
The Emergency Card (below) is designed for fast triage under pressure. Find your symptom in the left column, run the command in the middle column, then jump to the section referenced. Do not read the rest of the handbook first — fix the immediate problem, then understand it.

### Quick Navigation
- Something is on fire → Emergency Card immediately below
- Hardware facts → Part 1
- Why things are the way they are → Part 2 (git timeline) + Part 15 (decisions)
- Power / fan / thermal → Part 4
- GPU / NVIDIA won't sleep → Part 5
- Keyboard backlight → Part 6
- HIVE AI / models → Part 7
- Display / Hz / sharpness → Part 8
- RAM / memory → Part 9
- Touchpad → Part 10
- Chrome → Part 11
- App launcher → Part 12
- All bugs → Part 13
- Config file values → Part 14
- Scripts reference → Appendix A
- All commits by component → Appendix B
- Socket IPC protocol → Appendix C
- One-liners → Appendix D
- Glossary → Appendix E

---

## EMERGENCY CARD

| Symptom | Immediate Command | Root Cause | See Section |
|---------|------------------|------------|-------------|
| Fans silent at 70°C+ | `sudo systemctl restart luminos-power` | luminos-power crashed or not running | Part 4 |
| Temp oscillating 60–88°C in logs | `sudo journalctl -u luminos-power -n 50` — look for rapid zone changes | No hysteresis or wrong thresholds (BUG-048 pattern) | Part 4.8 |
| Panel broken / white after theme change | `systemctl --user restart plasma-plasmashell` | plasmashell lost state; also: `kquitapp6 plasmashell && kstart plasmashell` | Part 8.4 |
| HIVE not responding (SUPER+SPACE) | `pkill -f hive-daemon.py; pkill -f llama-server; SUPER+SPACE again` | Daemon lock file stale or llama-server crashed | Part 7.6 |
| NVIDIA GPU won't sleep (stays at 8W) | `cat /etc/environment` — verify `__EGL_VENDOR_LIBRARY_FILENAMES=...50_mesa.json` present | EGL defaulting to NVIDIA for session apps (BUG-050) | Part 5.4 |
| Chrome 90–95% CPU on page load | `cat /usr/local/bin/chrome-luminos` — verify no `--use-gl=angle` flag | ANGLE/Vulkan overhead on AMD path (BUG-046 pattern) | Part 11 |
| App launcher shows blank / empty | `kwriteconfig6 --file plasma-org.kde.plasma.desktop-appletsrc --group 'Applet-*' --key applicationsDisplay 1 && systemctl --user restart plasma-plasmashell` | applicationsDisplay=0 (shows Favorites, which is empty) — BUG-052 | Part 12 |
| Keyboard light not restoring after sleep | `cat ~/.config/luminos-keyboard.conf && systemctl --user status luminos-keyboard.service` | Service failed to restart; or sysfs write permission | Part 6.7 |
| KDE System Settings can't find HIVE | `kbuildsycoca6 --noincremental` | sycoca index stale after plugin install | Part 7.1 |
| Display stuck at wrong Hz after AC plug | `luminos-120hz` or `luminos-60hz` | kscreen-doctor failed silently in setDisplayHz() | Part 8.2 |

---

## PART 1 — HARDWARE PROFILE

### 1.1 Complete Specification

| Component | Specification | Notes |
|-----------|--------------|-------|
| System | ASUS ROG G14 GA403UU | 14-inch gaming ultrabook |
| CPU | AMD Ryzen 9 8845HS | 8 cores / 16 threads, Zen 4 |
| CPU TJmax | 105°C | Safe operating limit; emergency threshold set at 85°C (non-gaming) |
| CPU Max Boost | 5.137 GHz | Read from `/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq` at daemon startup (main.go:529) |
| iGPU | AMD Radeon 780M | RDNA3, always-on, `/dev/dri/card2`, renderD128 — drives KWin compositor |
| dGPU | NVIDIA RTX 4050 6GB | `/dev/dri/card1`, renderD129 — power-gated when idle |
| NPU | AMD XDNA (accel0) | 16 TOPS, ONNX/HATS only — NOT ROCm, NOT iGPU |
| Display | Samsung eDP-2 | 2880×1800, 120Hz cap, integer 2× HiDPI scale |
| RAM | 16GB LPDDR5x | Shared between CPU, iGPU, and OS |
| Storage | NVMe SSD | Triple-boot (Windows, recovery, Arch) |
| WiFi | Intel AX (assumed) | Managed by luminos-power: power_save off on AC, on on battery |

### 1.2 GPU Topology — PRIME, Not MUX Switch

The GA403UU uses NVIDIA PRIME render offload, not a MUX (multiplexer) switch. This distinction is critical:

**MUX switch** (not present): A hardware switch that physically routes display signals to either GPU. Switching requires logout. Either GPU drives the panel directly.

**PRIME render offload** (what we have): The iGPU (Radeon 780M) always drives the display and runs the compositor (KWin). The NVIDIA GPU renders frames offscreen when explicitly requested, then hands them back to the iGPU compositor via DMA-BUF. This means:
- iGPU is always `/dev/dri/card2` and always the compositor's GPU
- NVIDIA can be power-gated to D3cold when no app is using it (saves ~8W idle)
- Activating NVIDIA for an app requires explicit environment variables: `DRI_PRIME=1`, `__NV_PRIME_RENDER_OFFLOAD=1`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`
- The `KWIN_DRM_DEVICES=/dev/dri/card2` environment variable in `/etc/environment` ensures KWin never accidentally opens the NVIDIA device

**Why card2 is AMD despite numbering**: DRM device numbering is assigned by the kernel in PCIe bus enumeration order. On this system, NVIDIA enumerates first (card1/renderD129) and AMD second (card2/renderD128). This is counterintuitive. Do not assume card0/card1 ordering.

### 1.3 VRAM Budget

Total NVIDIA VRAM: 6144 MB (6GB)
Driver/firmware overhead: ~1,400 MB (reserved at boot, unavailable for models)
**Safe allocation for HIVE models: 4,600 MB (4.6GB)**

This budget is why only one HIVE model loads at a time. A Q4_K_M quantization of an 8B model occupies approximately 4.1–4.5GB depending on the architecture. Loading two would exceed the safe limit and cause OOM evictions during inference.

VRAM/RAM split penalty: -1.8 TPS per layer offloaded to system RAM. With 4.6GB budget, all layers of a 7–8B Q4 model fit on GPU, achieving peak performance (36–38 TPS).

### 1.4 Display — Why Integer 2× Is the Best Case

The Samsung eDP-2 panel is 2880×1800. KDE runs at scale factor 2, giving a logical resolution of 1440×900. Integer scaling is the best possible HiDPI scenario because:
- Every logical pixel maps to exactly 4 physical pixels (2×2 block) — no fractional interpolation
- Text and UI are perfectly sharp with zero antialiasing artifacts
- The compositor does not need to scale anything; it renders at logical resolution and the display hardware handles the pixel doubling
- Fractional scaling (e.g., 1.5×, 1.75×) would require the compositor to render at higher resolution and downsample, causing blur

The VRR policy is currently `"Never"` (user-intentional, reverted after BUG-051 fix). The panel supports VRR but the user experienced stutter after enabling `"Automatic"` and manually reverted. See Part 8.3.

---

## PART 2 — OS EVOLUTION (GIT TIMELINE)

### Era 1 — Ubuntu ISO Build (2026-03-22 to 2026-03-31)
**First commit**: `3b8a95aa` (2026-03-22) "Luminos OS v0.1.0-alpha - all phases complete"

The project started as a custom Ubuntu 24.04 ISO built via `smart_build.sh` and `build_iso.sh`. The goal was a distributable OS image. This era produced the bulk of BUG-011 through BUG-037 — all squashfs, GRUB, live-boot, and build system issues.

| Bug Range | Category |
|-----------|----------|
| BUG-011 | Wine gecko/mono manual download |
| BUG-012 | rm -rf at build start — data loss risk |
| BUG-013 | update-desktop-database fallback |
| BUG-014 | proc/sys/dev in squashfs |
| BUG-015 | debootstrap cache reuse |
| BUG-016 | grub.cfg inline fallback |
| BUG-017 | kernel missing in chroot |
| BUG-018 | SKIP_STAGE1 for existing chroot |
| BUG-020 | useradd check if user exists |
| BUG-021 | lupin-casper removed from Ubuntu 24.04 |
| BUG-022 | casper live-boot packages + initrd regen |
| BUG-023 | initrd must regen AFTER live-boot install |
| BUG-025 | GRUB embedded config ignores grub.cfg |
| BUG-026 | use grub-mkrescue for ISO creation |
| BUG-027 | squashfs root filesystem structure |
| BUG-028 | auto-login + sway auto-start |
| BUG-029 through BUG-033 | macOS Sequoia styling with sway/waybar/wofi |
| BUG-035 | Hyprland build from source in chroot |
| BUG-037 | CMake 3.30+ required for Hyprland |

All Ubuntu-era bugs are resolved. The build system is archived. The OS is now a native Arch installation, not a built ISO.

**Arch migration commit**: `0974c05c` (2026-03-31) "Phase 1 complete — repo is 100% Arch native, zero Ubuntu refs"

### Era 2 — Hyprland + GTK4 Experiments (2026-03-31 to 2026-04-19)
After migrating to Arch, the project ran on Hyprland for approximately three weeks. The Python GTK4 UI was developed during this period. The Hyprland config lives in `archive/hyprland/`.

Key issues with Hyprland that drove the KDE decision:
- GTK4 Python UI required venv management and was fragile across updates
- Wayland protocol compatibility issues with some apps
- No native KCM system for settings integration
- Theming required WhiteSur/Kvantum hacks that broke frequently
- BUG-043 (HIVE popup crash) traced to a GTK4 Python script being exec'd from bash

**KDE decision commit**: `06bd740a` (2026-04-19) "docs(decision): permanent move to KDE Plasma"

### Era 3 — KDE Bootstrap + Go Daemons (2026-04-19 to 2026-04-27)
The KDE migration was immediate and permanent. Within one week:
- All Go daemons (luminos-power, luminos-sentinel, luminos-router, luminos-ai) were built: `ebf11916` (2026-04-20) "feat(daemons): Phase 1 Go foundation complete"
- HATS NPU architecture adopted: `5ef0e7e6` (2026-04-22) "feat(ai): adopt HATS architecture..."
- Keyboard backlight KCM built as a native C++/QML KDE System Settings plugin: `842ded7d` (2026-04-26)
- HIVE popup rebuilt as native QML6 chat UI: `51c2676b` (2026-04-27) "feat(hive): rebuild popup as native QML6 Claude.ai-style chat UI"

The GTK4 Python UI was archived to `archive/gtk4-ui/`. This was the last Python UI component.

### Era 4 — Stabilization + HIVE Maturity (2026-04-28 to 2026-05-09)
This era focused on making the HIVE UI production-quality and stabilizing the power system.

HIVE UI rewrite history (all in this era):
1. **kdialog loop** — original bash popup using kdialog for text input, no streaming
2. **QML6 native** (`51c2676b`, 2026-04-27) — full chat window with history sidebar, LocalStorage persistence, dark/light theme detection, chip-based model routing
3. **Flask+HTML** (`ec2255408`, 2026-05-08) — attempted web UI via Flask server in browser; abandoned because browser adds compositor overhead and XWayland path
4. **PyQt6 native window** (`080067a66`, 2026-05-08) — replaced Flask; better than browser but still a heavy Python dep
5. **Back to QML6** — PyQt6 retired, QML6 restored as primary (the architecture it is today)

hive-swap-server.py (port 8079) was retired at `45f6bee5` (2026-05-03): all swap/routing logic was merged into hive-daemon.py (port 8078).

RAM management evolved from basic ZRAM/KSM (`0eb5dd6e`, 2026-05-06) to the full LIRS v3 algorithm (`fa5eadf0`, 2026-05-08).

Tahoe macOS theme was installed (`c0e11c63`, 2026-05-10), caused white panel bugs, and was fully reverted to Breeze at `f81b0cd9` (2026-05-11): "feat(visual): revert Tahoe theme and restore Breeze defaults". The Tahoe theme is archived. Do not restore it.

### Era 5 — GPU, Power, Display, and Session 2 (2026-05-10 to 2026-05-21, current)
BUG-046, BUG-047, BUG-050 (GPU/NVIDIA) were diagnosed and fixed in a concentrated debugging session starting 2026-05-14. The fixes landed in `b7139d30` and `9c6a161e`.

luminos-power went through rapid iteration:
- v3.0 EPP-based control: `810ec387` (2026-05-14)
- v3.1 beast mode + thermal tuning: `df2bf467` (2026-05-17)
- Fan curve early ramp: `c34f41fb` (2026-05-19)
- Fan curve v3.2 (WRONG — silent below 44°C, caused high temps): `febd312a` (2026-05-21)
- Governor v3.3 (WRONG — 12°C hysteresis caused oscillation): `8faeef7d` (2026-05-21)
- **Revert to working state**: `385f1302` (2026-05-21) — current production config

Session 2 (2026-05-21) added: universal GPU launcher, Chrome Wayland mode, display Hz toggle, display sharpness, BUG-052 fix (launcher empty).

---

## PART 3 — SYSTEM ARCHITECTURE

### 3.1 Daemon Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER / KDE PLASMA / Qt APPS                 │
└──────────────┬──────────────────────────────────────────────────┘
               │ Unix socket (JSON)
               ▼
┌─────────────────────────────────────────────────────────────────┐
│              luminos-ai  (Go)  /run/luminos/ai.sock             │
│  Main daemon: request routing, session mgmt, health checks      │
│  Spawns / supervises all sub-daemons on startup                 │
└────┬──────────────┬──────────────┬──────────────┬──────────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐
│luminos- │  │luminos-  │  │luminos-  │  │luminos-    │
│power    │  │sentinel  │  │router    │  │ram         │
│(Go)     │  │(Go)      │  │(Go)      │  │(Go)        │
│         │  │          │  │          │  │            │
│sysfs:   │  │/proc     │  │PE header │  │LIRS IRR    │
│governor │  │scanner   │  │rules     │  │HotSet N=8  │
│NVIDIA   │  │kill proc │  │cache     │  │KWin D-Bus  │
│asusctl  │  │notify    │  │          │  │CDP port    │
└─────────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘
                  │              │               │
         Unix socket    Unix socket      Unix socket
                  │              │               │
                  ▼              ▼               ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ luminos-npu  │ │ luminos-     │ │ llama-server │
        │ (Python)     │ │ classifier   │ │ (Python)     │
        │              │ │ (Python)     │ │              │
        │ ONNX/VitisAI │ │ ONNX model   │ │ llama-cpp-   │
        │ NPU sentinel │ │ edge-case    │ │ python       │
        │ AMD XDNA     │ │ routing      │ │ HIVE agents  │
        │ /dev/accel0  │ │ CPU-based    │ │ NVIDIA dGPU  │
        └──────────────┘ └──────────────┘ └──────────────┘
```

Additionally, `hive-daemon.py` (port 8078, HTTP) sits outside this Go socket tree, managing model lifecycle and routing for the QML HIVE popup independently.

### 3.2 Socket Paths

| Service | Socket Path | Protocol | Owner |
|---------|------------|----------|-------|
| luminos-ai | `/run/luminos/ai.sock` | JSON, one request/response | root |
| luminos-power | `/run/luminos/power.sock` | JSON | root |
| luminos-sentinel | `/run/luminos/sentinel.sock` | JSON | root |
| luminos-router | `$XDG_RUNTIME_DIR/luminos-router.sock` | newline-delimited JSON | user |
| luminos-npu (Python) | `/run/luminos/npu.sock` | JSON | root |
| luminos-classifier (Python) | `/run/luminos/classifier.sock` | JSON | root |
| llama-server (Python) | HTTP on `127.0.0.1:8080` | OpenAI-compatible REST | user |
| hive-daemon (Python) | HTTP on `127.0.0.1:8078` | HTTP JSON | user |

### 3.3 Go vs Python Split Rule

The governing rule (Decision 13, commit `39beedd5`):
- **If a daemon touches ONNX, VitisAI, llama.cpp, or numpy → Python**
- **Everything else → Go**

Rationale: Go produces single static binaries with no venv, no pip, no Python version fragility. Fast startup, low memory. Goroutine concurrency maps perfectly to socket servers and polling loops. Python is unavoidable only where ML library bindings have no Go equivalent.

### 3.4 Service Startup Order

Phase 1 (Go only — AI not required):
```
1. luminos-power    → applies initial AC/battery power mode
2. luminos-sentinel → starts /proc scanner (rules-only mode until NPU ready)
3. luminos-router   → starts PE rule engine + cache
4. luminos-ai       → opens main Unix socket, routes to sub-services
```

Phase 2+ (Python inference):
```
5. luminos-npu (Python)        → loads ONNX onto /dev/accel0
6. luminos-classifier (Python) → loads edge-case model (CPU)
7. llama-server (Python)       → lazy — loads first HIVE model on first request
8. hive-daemon.py              → starts on SUPER+SPACE, killed on popup close
```

### 3.5 What Breaks When Each Service Dies

| Service | Immediate Effect | Cascading Effect |
|---------|-----------------|------------------|
| luminos-power | No thermal management, no fan curves applied | CPU can overheat; asusctl defaults take over (may be incorrect profile) |
| luminos-sentinel | No process security scanning | No threat detection; system otherwise normal |
| luminos-router | .exe files use rule-only classification | 20% of edge-case .exe files may be misclassified |
| luminos-ram | No background memory management | RAM fills normally; no compression or freezing of background apps |
| hive-daemon.py | HIVE popup gets no responses | SUPER+SPACE opens but shows "no response" or hangs |
| llama-server | All HIVE AI inference fails | hive-daemon.py will attempt to restart via hive-start-model.sh |
| KWin | Desktop compositor crash — blank screen | `kwin_wayland --replace &` to recover |
| plasmashell | Panel and desktop disappear | `systemctl --user restart plasma-plasmashell` |

---

## PART 4 — POWER & THERMAL MANAGEMENT

### 4.1 Overview

luminos-power is a Go daemon (`cmd/luminos-power/main.go`) running as a systemd root service (`/etc/systemd/system/luminos-power.service`). It is the single source of truth for:
- CPU scaling governor
- Energy Performance Preference (EPP)
- CPU frequency cap
- WiFi power save mode
- KSM (Kernel Samepage Merging)
- Display Hz (via kscreen-doctor)
- asusctl power profile (Quiet/Balanced/Performance)
- ASUS fan curves (via asusctl fan-curve)

The binary lives at `/usr/local/bin/luminos-power`. The source is `cmd/luminos-power/main.go`. Entry point is `main()` at line 112. The monitoring loop is `monitorLoop()` at line 177.

### 4.2 The Three Profiles

asusctl manages three hardware TDP profiles: Quiet, Balanced, and Performance. luminos-power decides which one to use and when to switch.

**Quiet** (low TDP):
- Default on battery (applied at AC unplug, main.go:301)
- Also applied during thermal emergency (main.go:258)
- EPP: `power` (targets 45°C idle)

**Balanced** (medium TDP):
- Default on AC (applied at AC plug, main.go:289)
- Restored after beast mode exit (main.go:232)
- EPP: `power`

**Performance** (high TDP, full boost):
- Only entered automatically via beast mode triggers
- AC only — never triggered on battery
- EPP: `performance`
- No frequency cap; full 5.137 GHz boost allowed
- See Section 4.5 for triggers

### 4.3 AC Plug / Unplug — All 6 Side Effects

The full set of changes applied on AC state change is in `applyACTransition()` at main.go:278.

**On AC plug** (main.go:283–294):
1. CPU scaling governor → `powersave` (allows full boost under load while saving when idle)
2. WiFi power save → **OFF** (`iw dev <iface> set power_save off`)
3. KSM → **ON** (`/sys/kernel/mm/ksm/run` = 1)
4. Display Hz → **120Hz** (via `kscreen-doctor output.eDP-2.mode.2880x1800@120`)
5. asusctl profile → **Balanced**
6. EPP → **power** (written after 350ms sleep to avoid asusd race — see 4.4)

**On AC unplug** (main.go:295–305):
1. CPU scaling governor → `powersave`
2. WiFi power save → **ON** (`iw dev <iface> set power_save on`)
3. KSM → **OFF** (`/sys/kernel/mm/ksm/run` = 0)
4. Display Hz → **60Hz** (via kscreen-doctor)
5. asusctl profile → **Quiet**
6. EPP → **power**

Note: EPP is `power` in both AC and battery states. This is intentional — `power` tells the CPU firmware to target low temperature via P-state selection, not max frequency. The distinction between AC and battery power is handled by the asusctl profile TDP settings, not EPP.

### 4.4 EPP — What It Is and How It's Written

EPP (Energy Performance Preference) is a per-core hint written to `/sys/devices/system/cpu/cpuN/cpufreq/energy_performance_preference`. The AMD P-state driver reads this to bias P-state selection.

Valid values (from conservative to aggressive):
`power` → `balance_power` → `balance_performance` → `performance`

On this system, `power` is used in all non-gaming states. This tells the firmware to choose P-states that minimize power/heat rather than maximize frequency. The AMD SMU (System Management Unit) implements this internally.

The `setAllEPP()` function (main.go:490–506) writes to all 16 EPP sysfs paths in a glob loop:
```
/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```

**Critical implementation detail** (main.go:465–471): asusctl applies its own EPP when setting a profile, doing so asynchronously via D-Bus ~100–300ms after `asusctl profile set` returns. If luminos-power writes EPP immediately after calling asusctl, asusd's delayed write will overwrite it. The `setEPPAfterAsusctl()` function inserts a 350ms sleep before writing EPP to win the race consistently.

### 4.5 Beast Mode — Auto Performance on AC

Beast mode automatically escalates to the Performance profile when sustained load is detected. It only activates on AC power and only when the current profile is not already Performance.

**GPU trigger** (gaming detection, main.go:313–334):
- Entry: GPU load > 80% for 30 seconds (15 ticks at 2s poll)
- Exit: GPU load < 20% AND CPU load < 25% for 60 seconds (30 ticks at 2s poll)

**CPU trigger** (compilation/ML detection, main.go:338–370):
- Entry: CPU load > 75% for 20 seconds (10 ticks at 2s poll)
- Exit: same as GPU exit — both CPU and GPU must be idle

When either trigger fires (main.go:211–225):
1. `asusctl profile set Performance`
2. EPP → `performance`
3. `setAllMaxFreq(0)` — removes any thermal frequency cap, allows full 5.137 GHz boost
4. `currentThermalZone` reset to `ZoneCool` — thermal governor starts clean
5. Daemon skips thermal governor for remainder of beast mode

When both triggers show idle for 60s (main.go:227–237):
1. `asusctl profile set Balanced`
2. `setAllMaxFreq(0)` — clears any emergency freq cap applied during beast mode
3. `currentThermalZone` reset to `ZoneCool`
4. EPP → `power` — back to cool target

### 4.6 Thermal Governor — 4 Zones, Hysteresis, AC vs Battery

The thermal governor runs inside `monitorLoop()` whenever the profile is NOT Performance. It is called in `applyThermalGovernor()` at main.go:396–462.

The thermal constants are defined at main.go:63–81:
```go
thermalHysteresisC = 5.0  // 5°C hysteresis on zone exit
thermalEmergencyC  = 85.0 // emergency threshold (non-Performance)
```

**AC Thermal Zones** (main.go:73–75):
| Zone | Entry Temp | Exit Temp (with 5°C hysteresis) | Freq Cap | EPP |
|------|-----------|--------------------------------|----------|-----|
| ZoneCool | < 60°C | always | none | power |
| ZoneMild | 60°C | < 55°C | none | power |
| ZoneWarm | 72°C | < 67°C | 4.0 GHz | power |
| ZoneHot  | 80°C | < 75°C | 3.0 GHz | power |
| Emergency | 85°C | — | 2.0 GHz + Quiet | power |

**Battery Thermal Zones** (main.go:78–80):
| Zone | Entry Temp | Exit Temp | Freq Cap | EPP |
|------|-----------|-----------|----------|-----|
| ZoneCool | < 50°C | always | none | power |
| ZoneMild | 50°C | < 45°C | none | power |
| ZoneWarm | 62°C | < 57°C | 3.5 GHz | power |
| ZoneHot  | 72°C | < 67°C | 2.5 GHz | power |

Zone enum (main.go:83–91): `ZoneCool=0`, `ZoneMild=1`, `ZoneWarm=2`, `ZoneHot=3`

The state machine logic (main.go:405–426) only advances or retreats one zone per tick and only exits a zone if the temperature drops below the entry threshold minus 5°C. This prevents the oscillation bug (BUG-048) where rapid zone changes would cause the profile to flip repeatedly.

**Emergency path** (main.go:251–261, outside thermal governor):
- In non-Performance mode: > 85°C → Quiet + 2.0 GHz cap
- In Performance/beast mode: > 95°C → 3.5 GHz cap (no profile exit — TJmax is 105°C)

### 4.7 Fan Curve — Complete Version History

All fan curves are applied via `applyAggressiveFanCurve()` (main.go:726–738) using `asusctl fan-curve`. The function applies to both `balanced` and `quiet` profiles at daemon startup.

**Fan curve syntax** (asusctl): `"TEMP:PCT,TEMP:PCT,..."` where TEMP is Celsius and PCT is fan percentage.

#### Version History

**v1 — Silent curve (pre-2026-05-14)**:
Silent below 60°C, gradual ramp. Exact values not recorded. Caused temperatures to climb to 70°C+ before fans engaged meaningfully.

**v2 — Early ramp (c34f41fb, 2026-05-19)**:
The first intentional design: ramp fans hard before 50°C so the heat never climbs past 50°C.
- cpuGpuCurve: `"30c:0%,40c:40%,45c:62%,50c:80%,60c:95%,70c:100%,80c:100%,90c:100%"`
- midCurve: `"30c:0%,40c:30%,45c:52%,50c:72%,60c:88%,70c:100%,80c:100%,90c:100%"`
**This is the current working curve (restored at 385f1302).**

**v3.2 — WRONG (febd312a, 2026-05-21)**:
Attempted to reduce fan noise by targeting 47–49°C with silence below 44°C. The curve was:
- cpuGpuCurve: silent at 44°C, 20% at 47°C
This was too late — by 47°C the heat was already climbing and the fans could not pull it back fast enough, resulting in temps drifting to 55–65°C.

**v3.3 — WRONG (8faeef7d, 2026-05-21)**:
Attempted to fix oscillation with 12°C hysteresis in the thermal governor. The hysteresis was too large — once the zone changed, it could not exit for a long time, causing the system to stay in a throttled state longer than necessary.

**Revert (385f1302, 2026-05-21)**:
Reverted to the working early-ramp curve (v2 above). This is the current production fan curve.

#### Why Early Ramp Beats Silent Curve (Physics)

The key insight: a fan running at 62% at 45°C can hold the temperature at 45°C. A fan that only starts ramping at 50°C cannot — by the time it reaches useful speed, the CPU has already accumulated thermal mass and temperature is still climbing. Early ramp exploits the thermodynamics: it is much cheaper to prevent heat accumulation than to remove accumulated heat.

At 45°C: cpu/gpu fan = 62%, mid fan = 52%. These speeds are audible but not disruptive.
At 40°C: cpu/gpu fan = 40%, mid fan = 30%. Spinning but quiet.
At 30°C: fans off (0%). Completely silent at idle.

### 4.8 Poll Rate and Why

Poll rate is controlled by `batteryInterval()` (main.go:372–377):
- AC: 2 seconds — faster response to load spikes and thermal events
- Battery: 10 seconds — reduce CPU wake cycles to extend battery

The ticker is reset immediately when AC state changes (main.go:199–204), so the poll rate adjusts without waiting for the next tick.

### 4.9 Live Diagnosis Commands

```bash
# Current profile, EPP, and thermal zone from logs
sudo journalctl -u luminos-power -f

# Check all 16 core EPP values
cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c

# Check max freq cap on all cores
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq | sort | uniq -c

# Current CPU temperature (all hwmon sensors)
sensors 2>/dev/null | grep -E 'temp|Tctl|Tdie'

# GPU load (AMD iGPU)
cat /sys/class/drm/card*/device/gpu_busy_percent

# AC state
cat /sys/class/power_supply/*/online

# Fan curve status
asusctl fan-curve -m balanced

# Current asusctl profile
asusctl profile -p
```

### 4.10 Common Thermal Bug Patterns

**Pattern: Rapid zone changes in logs**
Log signature: `thermal zone 0→1` followed immediately by `thermal zone 1→0` within 1–2 ticks.
Cause: hysteresis is set too small, or emergency threshold is firing repeatedly.
Fix: Check `thermalHysteresisC` (main.go:70) — should be 5.0. Check that emergency threshold at main.go:247 is 85.0.

**Pattern: Temperature stuck at 80°C despite fans at 100%**
Cause: Fan curves were not applied at daemon startup, or asusctl fan-curve command failed.
Diagnosis: `sudo journalctl -u luminos-power | grep "Applying fan curve"` — should appear twice at startup.
Fix: `sudo systemctl restart luminos-power`, then verify with `asusctl fan-curve -m balanced`.

**Pattern: Temperature climbs from 45°C to 65°C under light load**
Cause: Silent fan curve (v3.2 regression) — fans not ramping until 47°C+.
Fix: Verify `cpuGpuCurve` at main.go:732 starts with `40c:40%,45c:62%`.

---

## PART 5 — GPU MANAGEMENT

### 5.1 PRIME Topology

See Part 1.2 for the detailed PRIME explanation. Summary for this section:
- iGPU (AMD Radeon 780M) = `/dev/dri/card2`, renderD128 — always-on, drives KWin
- dGPU (NVIDIA RTX 4050) = `/dev/dri/card1`, renderD129 — power-gated when idle
- Apps use NVIDIA only when explicitly given PRIME env vars
- KWin is locked to card2 via `KWIN_DRM_DEVICES=/dev/dri/card2` in `/etc/environment`

### 5.2 NVIDIA Power States

The RTX 4050 uses D3cold power gating when idle. This requires:
1. NVIDIA driver module parameter: `NVreg_DynamicPowerManagement=0x02` in `/etc/modprobe.d/nvidia.conf`
2. udev rules to enable runtime PM
3. No process holding an open EGL context on NVIDIA

The EGL vendor override in `/etc/environment`:
```
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
```
Forces all session processes to use AMD Mesa EGL by default. Without this, libEGL scans both `50_mesa.json` and `60_nvidia.json` and defaults to NVIDIA (higher priority number), keeping the dGPU in D0 constantly.

Power states:
- D0 (active) = ~8W idle draw — bad
- D3cold (gate) = ~0W — correct idle state

Verify current state:
```bash
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status
# Should be "suspended" when idle
nvidia-smi --query-gpu=power.draw --format=csv,noheader
# Should return error or 0W when in D3cold
```

### 5.3 Universal GPU Launcher

Source: `scripts/luminos-gpu-launch`
Installed: `/usr/local/bin/luminos-gpu-launch`

Usage:
```bash
luminos-gpu-launch blender
luminos-gpu-launch flatpak run com.valvesoftware.Steam
```

Shows a kdialog menu: "AMD Radeon 780M · Battery Saver" or "NVIDIA RTX 4050 · High Performance". On NVIDIA selection, writes `"on"` to `/sys/bus/pci/devices/0000:01:00.0/power/control` to wake the GPU from D3cold before setting PRIME env vars.

**Per-App GPU Defaults** (based on workload type):

| App | Default GPU | Reason |
|-----|------------|--------|
| Chrome | AMD (DRI_PRIME=0) | Daily browsing; NVIDIA wastes 8–15W |
| Wine apps (Forex bot, MT5) | AMD | Low GPU demand; NVIDIA overkill |
| Blender render | NVIDIA | CUDA acceleration; render speed |
| Games (Steam) | NVIDIA | Full RTX 4050 for gaming performance |
| HIVE AI models | NVIDIA | llama.cpp CUDA backend |
| KWin compositor | AMD (always) | iGPU drives display |

### 5.4 BUG-046/047/050 History

**BUG-047** (2026-05-10): NVIDIA GPU always active (~8W idle).
Root cause: No power gating configured.
Fix: `NVreg_DynamicPowerManagement=0x02` in modprobe + udev rules.
Commit: `b7139d30`

**BUG-046** (2026-05-10): Chrome using NVIDIA GPU.
Root cause 1: `chrome-luminos` wrapper had `--render-node-override=/dev/dri/renderD129` — hardcoded NVIDIA.
Root cause 2: render nodes were reversed (renderD128 and renderD129 confused) causing AMD Signal 5 crash.
Fix: Removed render-node-override. `DRI_PRIME=0` correctly forces AMD.
Commit: `9e12186f`

**BUG-050** (2026-05-14): System processes (ksecretd, plasmashell, Xwayland, baloorunner) keeping NVIDIA in D0.
Root cause: No EGL vendor preference — libEGL defaulted to `60_nvidia.json` for all processes. KWin also advertised renderD129 via linux-dmabuf.
Fix: Added both `__EGL_VENDOR_LIBRARY_FILENAMES` and `KWIN_DRM_DEVICES` to `/etc/environment`.
Commit: `b7139d30`

### 5.5 luminos-nvidia-run

Source: `scripts/luminos-nvidia-run`
Installed: `/usr/local/bin/luminos-nvidia-run`

Purpose: Wakes NVIDIA from PCI power gate then executes an app with PRIME env vars. Used by the Dolphin KDE service menu for right-click "Run on NVIDIA RTX 4050" actions.

The 0.3s sleep after writing `"on"` to the power control sysfs is intentional — the GPU needs ~200ms to exit D3cold before EGL/CUDA contexts can be created.

### 5.6 Dolphin Service Menus

Two KDE service menus in `~/.local/share/kio/servicemenus/`:

`luminos-gpu-select.desktop` — right-click on executables/ELF binaries:
- "Ask GPU..." → runs `luminos-gpu-launch`
- "Run on AMD Radeon" → `DRI_PRIME=0` inline
- "Run on NVIDIA RTX 4050" → `luminos-nvidia-run`

`luminos-app-gpu.desktop` — right-click on `.desktop` files:
- Extracts the `Exec=` line from the .desktop file and passes it to `luminos-gpu-launch`

---

## PART 6 — KEYBOARD BACKLIGHT (DEEP DIVE)

### 6.1 Where to Find It in KDE

**KDE System Settings → Hardware → Keyboard Backlight**

The plugin `.so` is at: `/usr/lib/qt6/plugins/plasma/kcms/systemsettings/kcm_luminos_keyboard.so`

If it does not appear, run `kbuildsycoca6 --noincremental` to rebuild the sycoca index, then restart System Settings.

### 6.2 All 8 Modes

As defined in the Mode ComboBox (main.qml:140–149):

| Mode | Value | Description | Controls |
|------|-------|-------------|----------|
| Static | `static` | Solid single color. Pairs with Auto Color Cycle. | Color |
| Pulse | `pulse` | Single color pulses in a rhythm | Color |
| Breathe | `breathe` | Color fades in and out. Dual mode: two-color crossfade. | Color, optional Color2, Speed |
| Highlight | `highlight` | Keys light up with a highlight effect | Color |
| Laser | `laser` | Laser sweep effect across keys | Color |
| Rainbow Cycle | `rainbow-cycle` | Continuous rainbow across keyboard | Speed |
| Rainbow Wave | `rainbow-wave` | Rainbow wave with direction control | Speed, Direction |
| Off | `none` | Backlight off | — |

The effect type lists (kcm_luminos_keyboard.cpp:16–18):
```cpp
COLOR_ONLY_EFFECTS = {"static", "pulse", "highlight", "laser"}
SPEED_ONLY_EFFECTS = {"rainbow-cycle"}
FULL_EFFECTS       = {"breathe", "rainbow-wave"}
```

### 6.3 How Color Change Works — Complete Code Path

1. **User clicks a preset swatch** in the 6×2 color grid (main.qml:62–77)
2. `onPicked` signal fires → `kcm.color = hex; kcm.preview()` (main.qml:213)
3. `preview()` is an `Q_INVOKABLE` method in C++ that calls `applyToHardware()` immediately (kcm_luminos_keyboard.cpp:79)
4. `applyToHardware()` (cpp:191–223) builds the asusctl argument list:
   - Static/Pulse: `asusctl aura effect static -c <hex>` (cpp:202–203)
   - Breathe dual: `asusctl aura effect breathe --colour <hex> --colour2 <hex2> --speed med` (cpp:194–198)
   - Highlight/Laser: `asusctl aura effect highlight -c <hex>` (cpp:199–201) — no `--speed` flag
   - Rainbow Cycle: `asusctl aura effect rainbow-cycle --speed med` (cpp:204–205)
   - Rainbow Wave: `asusctl aura effect rainbow-wave --speed med --direction right` (cpp:206–209)
5. `QProcess::startDetached("asusctl", args)` — fires and forgets
6. Brightness is written separately: `QFile sysfs("/sys/class/leds/asus::kbd_backlight/brightness")` (cpp:214–222) — direct sysfs write as the current user. Falls back to `sudo tee` if sysfs write fails.

### 6.4 The 12 Color Presets

Defined in main.qml:15–18 as a `readonly property var presets`:
```
#ffffff (white), #ffcc88 (warm white), #ff0000 (red), #ff6600 (orange),
#ffff00 (yellow), #00ff00 (green), #00ffff (cyan), #0066ff (blue),
#8800ff (purple), #ff00ff (magenta), #ff0055 (hot pink), #000000 (black/off)
```

### 6.5 Dual Breathe Mode

The Dual color checkbox (main.qml:191–197) is only visible when `kcm.mode === "breathe"`. When enabled, it sets `kcm.breatheDual = true`, which changes the asusctl command to pass both `--colour` and `--colour2` parameters (cpp:194–198). When disabled, `--colour2` is set to the same value as `--colour` (single-color breathe).

### 6.6 Speed Control

The Speed slider (main.qml:248–261) has values 0=Slow, 1=Med, 2=Fast. The `speedName()` helper (cpp:187–189) maps these to the asusctl string values `"low"`, `"med"`, `"high"`.

Speed is visible only when `kcm.hasSpeed` is true — i.e., when mode is `breathe`, `rainbow-cycle`, or `rainbow-wave`.

### 6.7 Rainbow Wave Direction

The Direction ComboBox (main.qml:174–188) is only visible when `kcm.hasDirection` is true (mode = `rainbow-wave`). Options: `Right`, `Left`, `Up`, `Down`. Passed to asusctl as `--direction right` (lowercased at cpp:208).

### 6.8 Auto Color Cycle

The Auto Color Cycle section (main.qml:294–375) adds a timer-based color rotation to Static and other single-color modes.

In C++ (cpp:225–240):
- `updateAutoTimer()` starts or stops a `QTimer` based on `m_autoEnabled` and whether `m_autoColors` is non-empty
- Timer interval = `m_autoInterval * 1000` milliseconds
- `cycleAutoColor()` increments `m_autoColorIndex` modulo the list size, sets `m_color`, emits `colorChanged()`, and calls `applyToHardware()`

The auto colors list (cpp:251) defaults to: `ff0000, 00ff00, 0000ff, ffff00, ff00ff, 00ffff` (red, green, blue, yellow, magenta, cyan).

The interval slider (main.qml:315–330) ranges from 1 to 60 seconds.

Add/remove colors via the flow layout at main.qml:332–375. The red ×-badge on each swatch calls `kcm.removeAutoColor(index)`. The + swatch opens `autoColorDialog`.

### 6.9 Config File Format

Config file: `~/.config/luminos-keyboard.conf`

All 10 keys:
```ini
KB_COLOR="ffffff"          # Primary color, 6-char hex, no #
KB_COLOR2="0000ff"         # Secondary color (breathe dual only)
KB_BRIGHTNESS="3"          # 1=low, 2=mid, 3=max
KB_MODE="static"           # static|pulse|breathe|highlight|laser|rainbow-cycle|rainbow-wave|none
KB_SPEED="1"               # 0=low, 1=med, 2=high
KB_DIRECTION="Right"       # Right|Left|Up|Down (rainbow-wave only)
KB_AUTO_ENABLED="false"    # true|false
KB_AUTO_INTERVAL="5"       # seconds, 1–60
KB_AUTO_COLORS="ff0000,00ff00,0000ff,ffff00,ff00ff,00ffff"  # comma-separated hex list
KB_BREATHE_DUAL="false"    # true|false
```

Parsing is in `load()` (cpp:97–134). The regex `^([\w]+)="?([^"]*)"?$` strips surrounding quotes. All values are loaded into class members. Guards at cpp:121–127 apply defaults for missing or out-of-range values.

**Defaults** (cpp:243–244):
- `m_color = "ffffff"` (white)
- `m_color2 = "0000ff"` (blue)
- `m_brightness = 3`
- `m_speed = 1` (med)
- `m_direction = "Right"`

### 6.10 Save and Startup Restore

`save()` (cpp:136–158) is called when the user clicks Apply in System Settings. It:
1. Stops the auto timer
2. Calls `applyToHardware()` immediately
3. Writes all 10 keys to `~/.config/luminos-keyboard.conf`
4. Restarts `luminos-keyboard.service` via `systemctl --user restart`

The `luminos-keyboard.service` (user systemd unit) calls `scripts/luminos-keyboard-smart` on startup, which reads the config file and applies the saved settings to hardware. This is how backlight settings survive sleep/hibernate.

---

## PART 7 — HIVE AI STACK

### 7.1 Where to Find Settings in KDE

**KDE System Settings → System Administration → HIVE AI Settings**

Parent category: `system-administration` (defined in `kcm_luminos_hive.json:12`).

Plugin source: `src/kcms/kcm_luminos_hive/`
Installed `.so`: `/usr/lib/qt6/plugins/plasma/kcms/systemsettings/kcm_luminos_hive.so`
JSON metadata: `src/kcms/kcm_luminos_hive/kcm_luminos_hive.json`

If not visible: `kbuildsycoca6 --noincremental`

### 7.2 Model Roster

| Alias | Model File | Location | Role | Backend | Performance |
|-------|-----------|----------|------|---------|-------------|
| Nexus | Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf | `/opt/luminos/models/` | Coordinator (uncensored) | GPU (CUDA) | 36.3 TPS |
| Bolt | Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf | `/opt/luminos/models/` | Coding specialist | GPU (CUDA) | 38.6 TPS |
| Nova | DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf | `/opt/luminos/models/` | Deep reasoning | CPU/GPU | 10.3 TPS (CPU) |
| Sentinel | MobileLLM-R1-140M-INT8.onnx | NPU models dir | OS security | NPU (HATS) | <22ms inference |
| Eye | Qwen2.5-VL-7B-Q4_K_M.gguf | pending download | Vision | GPU | PENDING |

VRAM budget: 4.6GB safe. One model loaded at a time. Eye pending download.

### 7.3 hive-daemon.py Endpoints

Source: `scripts/hive-daemon.py`
Binds: `127.0.0.1:8078`
Log: `/tmp/hive-daemon.log`
Lock: `/tmp/hive-daemon.lock`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat` | POST | Main chat entry — routing + inference |
| `/state` | GET | Current model + ready status |
| `/health` | GET | Daemon liveness check |
| `/copy` | POST | Clipboard copy via wl-copy |

Startup: reads `ACTIVE_MODEL_FILE` (`/tmp/hive-active-model`) to bootstrap state if llama-server is already running from a previous popup.

### 7.4 Routing Logic

hive-daemon.py routes messages to one of three models: Nexus, Bolt, or Nova.

**Priority 1: Explicit chip selection** (hive-daemon.py:49–55)
The QML UI shows 5 chips: Code→bolt, Learn→nova, Strategize→nova, Write→nexus, System→nexus.

**Priority 2: Route tag in message** (hive-daemon.py:57–58)
Any message containing `[ROUTE:BOLT]`, `[ROUTE:NOVA]`, or `[ROUTE:NEXUS]` routes to that model.

**Priority 3: Intent detection** (hive-daemon.py:61–87)
`detect_intent()` scans for code keywords (python/bash/javascript/debug/fix/API/etc.) → routes to Bolt.
Reasoning keywords (explain why/step-by-step/compare/analyze/math) → routes to Nova.
No match → Nexus (default coordinator).

### 7.5 HIVE UI Files

| File | Purpose |
|------|---------|
| `src/hive/HiveChat.qml` | Main chat window — 820×620px, dark/light theme, LocalStorage history, chip routing |
| `src/hive/HistorySidebar.qml` | Collapsible sidebar showing past conversations with relative timestamps |
| `scripts/hive-daemon.py` | HTTP orchestration server on port 8078 |
| `scripts/luminos-hive-popup` | Bash launcher — sets Wayland env, starts llama-server + hive-daemon, launches qml6 |
| `/usr/local/bin/luminos-hive-popup` | Installed copy of the above |

### 7.6 HIVE UI Rewrite History

1. **kdialog loop** (pre-2026-04-26): `kdialog --inputbox` in a bash loop. Text only, no streaming, no history.
2. **QML6 native** (`51c2676b`, 2026-04-27): Full Claude.ai-style chat window — first real UI. LocalStorage persistence. Dark/light theme auto-detection via `SystemPalette`.
3. **Flask+HTML** (`ec2255408`, 2026-05-08): Tried a web UI served by Flask in the user's browser. Abandoned: adds XWayland overhead, browser itself uses resources, no Wayland integration.
4. **PyQt6 native** (`080067a66`, 2026-05-08): Replaced Flask with a PyQt6 native window. Better than browser but introduces PyQt6 as a dependency and is slower to start than QML.
5. **QML6 restored** (current): PyQt6 abandoned. QML6 is the correct architecture — native KDE, instant startup, no extra deps.

**hive-swap-server.py retired** (`45f6bee5`, 2026-05-03): Port 8079 functionality (model swapping, routing) merged into hive-daemon.py (port 8078). The swap server file still exists as archive.

### 7.7 SUPER+SPACE Shortcut

The shortcut is configured in KDE Global Shortcuts pointing to `/usr/local/bin/luminos-hive-popup`.

The launcher script (`scripts/luminos-hive-popup`) handles a critical KDE Wayland problem: kglobalaccel launches processes without inheriting `WAYLAND_DISPLAY`, `DBUS_SESSION_BUS_ADDRESS`, or `XDG_RUNTIME_DIR`. The first 65 lines of the script reconstruct these variables from `/run/user/$(id -u)/` before any kdialog or qml6 call can succeed.

Toggle behavior (lines 86–97): if `/tmp/luminos-hive-popup.lock` exists and contains a live PID, sends SIGTERM to close the popup. Otherwise creates the lock and opens the popup.

On exit, the trap (line 97) removes the lockfile, kills hive-daemon.py, and kills any background llama-server start process.

### 7.8 Debugging HIVE

```bash
# Check if hive-daemon is running
pgrep -a -f hive-daemon.py

# Check health
curl -s http://127.0.0.1:8078/health

# Check current model state
curl -s http://127.0.0.1:8078/state | python3 -m json.tool

# Tail the daemon log
tail -f /tmp/hive-daemon.log

# Check llama-server
pgrep -a llama-server
curl -s http://127.0.0.1:8080/v1/models

# Check active model file
cat /tmp/hive-active-model

# Full restart
pkill -f hive-daemon.py
pkill -f llama-server
# Then press SUPER+SPACE
```

---

## PART 8 — DISPLAY & VISUAL

### 8.1 Display Hz Toggle

**In KDE**: KDE System Settings → Hardware → Display Refresh Rate
(Installed via `~/.local/share/applications/luminos-display-hz.desktop`, Category=HardwareSettings)

The `luminos-display-hz` script (`scripts/luminos-display-hz`, installed at `/usr/local/bin/luminos-display-hz`) reads the current refresh rate from `~/.config/kwinoutputconfig.json`, shows a kdialog radiolist, then calls `luminos-60hz` or `luminos-120hz`.

The `luminos-60hz` and `luminos-120hz` scripts (both installed under `/usr/local/bin/`) use a two-method approach:
1. Primary: `kscreen-doctor output.1.mode.2880x1800@60` with correct Wayland env vars
2. Fallback: Direct JSON edit of `kwinoutputconfig.json` followed by `qdbus6 org.kde.KWin /KWin reconfigure`

**Auto-switch by AC state** (main.go:284,300):
- AC plug → 120Hz
- AC unplug → 60Hz

This is applied by `setDisplayHz()` (main.go:577–597) which calls `kscreen-doctor` as the display user via `runuser`, passing the correct `WAYLAND_DISPLAY` and `DBUS_SESSION_BUS_ADDRESS` resolved from the user's runtime directory.

### 8.2 kwinoutputconfig.json Field Reference

Location: `~/.config/kwinoutputconfig.json`

Key fields (current values):
```json
{
  "connectorName": "eDP-2",
  "mode": { "refreshRate": 60001 },
  "scale": 2,
  "vrrPolicy": "Never",
  "brightness": 0.3
}
```

Note: `refreshRate` uses millihertz internally — 60001 = 60Hz, 120001 = 120Hz. The scripts set 60000 and 120000 (without the 1) when editing the JSON directly; KWin normalizes on reconfigure.

KWin sharpness is set separately via the `sharpness` property of the output: `"sharpness": 0.35`.

### 8.3 VRR History

BUG-051 (2026-05-21): Desktop felt stuttery at 120Hz; KWin was consuming 19% CPU idle because `vrrPolicy: "Never"` locked the compositor to a hard 120Hz deadline (8.33ms per frame). Any frame that ran slightly long caused a visible dropped frame.

Fix applied: `vrrPolicy: "Automatic"`, `LatencyPolicy=Low`, `GLPreferBufferSwap=e` in kwinrc.

**User reverted**: After applying the VRR fix, the user experienced a different kind of visual issue and manually set `vrrPolicy` back to `"Never"`. This is intentional and documented. Status: `Display VRR: Disabled (user intentional)`.

Current state: `"Never"`. If you want to re-enable VRR: edit `~/.config/kwinoutputconfig.json`, set `"vrrPolicy": "Automatic"`, then `qdbus6 org.kde.KWin /KWin reconfigure`.

### 8.4 Display Sharpness

KWin applies a sharpening filter in the AMD display pipeline. Set via `kwinoutputconfig.json` as `"sharpness": 0.35`.

Value 0.0 = no sharpening. Value 1.0 = maximum. 0.35 was chosen as a perceptually pleasing value that enhances text clarity without making images look harsh. This applies to all content including video and UI.

To change: edit `~/.config/kwinoutputconfig.json` and set the `sharpness` field. The change takes effect on next `qdbus6 org.kde.KWin /KWin reconfigure` or on recompose.

### 8.5 Power Widget

Source: `src/widgets/org.luminos.powerwidget/contents/ui/main.qml`

The panel widget shows: current profile (Quiet/Balanced/Performance), CPU temperature with red warning above 70°C, fan RPM, and an orange NVIDIA awake dot.

Data is fetched by polling `journalctl -u luminos-power` for profile, `sensors` for temp/fan, and `nvidia-smi` for power draw — all via the Plasma `DataSource` executable engine at 5-second intervals.

**Warning**: The Hz toggle was added to the power widget popup at commit `f3e95811`. If you modify the power widget, do not add buttons that pop up OS-level dialogs (`kdialog --menu`) from within the plasmoid context — this can freeze plasmashell. Use `QProcess::startDetached` or `kstart` to launch dialogs independently.

### 8.6 Tahoe Theme History

Three commits tell the full story:
- `c0e11c63` (2026-05-10): Tahoe macOS theme installed
- `adce1e68`, `ff82c759` (2026-05-10): Fought white panel bug (panel background rendering white over content)
- `f81b0cd9` (2026-05-11): "feat(visual): revert Tahoe theme and restore Breeze defaults"

The Tahoe theme applied window decorations (Aurorae), icon themes (WhiteSur), and Kvantum widget styles. Each of these has edge cases with KDE Plasma 6 that caused the white panel issue where the panel background color was transparent but the SVG rendering of the plasmoid backgrounds still painted white.

**Current state**: Breeze defaults. Aurorae: Breeze. Icons: Breeze. Kvantum: not active. Do not re-install Tahoe without extensive testing.

---

## PART 9 — RAM MANAGEMENT

### 9.1 luminos-ram v3 Algorithm

Source: `cmd/luminos-ram/`
Architecture documented: `docs/LUMINOS_RAM_ARCHITECTURE.md`

The algorithm is LIRS (Low Inter-Reference Recency Set) adapted for desktop window management:

**Hot Set** (LIR — Low Inter-Reference Recency):
- Capacity: N=8 windows
- Sorted by IRR score (Inter-Reference Recency = number of unique other windows focused between two consecutive focuses of this window)
- Low IRR = frequently used = stays in Hot Set
- When Hot Set exceeds N=8: highest-IRR window moves to Cold Set
- Bottom tier (positions 6–8): if idle >10 min and not OnScreen: `MADV_PAGEOUT` (compress to ZRAM) but stay in Hot Set

**Cold Set** (HIR — High Inter-Reference Recency):
- Entry: immediate `MADV_PAGEOUT`
- 15-minute rule: browser tabs → CDP discard (100% free); native apps → `SIGSTOP` (frozen in RAM/ZRAM)
- 2-hour rule: non-essential apps → `SIGKILL`

**OnScreen Absolute Protection Rule**:
Before any action (MADV_PAGEOUT, SIGSTOP, SIGKILL):
```
if (focused OR (visible AND focused_within_60s)) → SKIP
```
This ensures the current window and all recently used visible windows (side-by-side work) are never touched.

**Safety Checks** before SIGSTOP/SIGKILL: audio (PipeWire/ALSA fd), network (established TCP/UDP), listen sockets, disk write >1MB/s, CPU >5%, active download heuristic.

**Restore speed optimizations** (v3.1):
- `MADV_WILLNEED` prefetch before `SIGCONT` to warm ZRAM pages
- 200ms staged thaw for processes >500MB
- `nice -10` priority boost for 5s on focus
- `vm.page-cluster=3` (8 pages per fault instead of 1)

KWin integration: subscribes to `activeWindowChanged`, `windowMinimized`, `windowUnminimized` via `org.kde.KWin` D-Bus.

Browser integration: CDP on port 9222 (Chrome `--remote-debugging-port=9222`) for tab discard without SIGKILL.

### 9.2 ZRAM

ZRAM creates a compressed in-memory swap device. Compressed pages use ~30–50% of their original size. This allows the 16GB physical RAM to effectively behave as ~22–24GB for background-process page storage.

ZRAM is configured separately from luminos-ram (via systemd or `/etc/fstab`). luminos-ram uses `MADV_PAGEOUT` to proactively push cold pages to ZRAM before the kernel does so reactively.

### 9.3 KSM (Kernel Samepage Merging)

KSM scans anonymous memory pages and deduplicates identical ones. Useful when multiple instances of the same app are running (e.g., multiple Chrome renderer processes with identical code pages).

luminos-power controls KSM based on AC state:
- AC: `echo 1 > /sys/kernel/mm/ksm/run` — ON
- Battery: `echo 0 > /sys/kernel/mm/ksm/run` — OFF

KSM is off on battery because the scanning CPU overhead costs more power than the RAM savings are worth.

### 9.4 earlyoom

earlyoom provides emergency OOM killing when the kernel's built-in OOM killer would otherwise stall the system. It is configured to trigger at lower memory pressure thresholds than the kernel default, preventing the "system freezes for 30 seconds then kills something random" behavior.

### 9.5 BUG-049 — Claude Desktop Memory Leak (MONITORING)

Electron renderer process running 101+ hours grows from 300MB to 2.1GB. This is a known Electron behavior pattern — V8 heap fragmentation and cached DOM trees are not aggressively collected.

Current mitigation: restart Claude Desktop daily. luminos-ram v3.1 includes background leak detection to alert when any process exceeds a growth threshold. Status: MONITORING.

---

## PART 10 — INPUT & PERIPHERALS

### 10.1 Touchpad ASUP1208 — Touch Jump Bug

The ASUS G14 touchpad (ASUP1208:00 093A:3011) has a hardware quirk: it occasionally reports coordinate jumps (large instantaneous position deltas) that are not caused by physical finger movement.

**Two separate symptoms and fixes:**

**Symptom 1 — Input lag / stuttery scrolling** (BUG-045):
Root cause: libinput was discarding touch jump events but still processing the surrounding events with added latency.
Fix: `/etc/libinput/local-overrides.quirks`:
```ini
[Luminos Touchpad Fix]
MatchName=ASUP1208:00 093A:3011 Touchpad
AttrTouchSizeRange=10:8
AttrPalmSizeThreshold=14
```
The `AttrTouchSizeRange` and `AttrPalmSizeThreshold` values tune the touch size detection thresholds. `schedutil` CPU governor was also contributing to input latency (power-saving P-state changes during touch events) — switching to `powersave` governor resolved this.
Commit: `496855d8`

**Symptom 2 — Log spam** (addressed in `/etc/environment`):
The kernel/libinput reports `"Touch jump detected"` warnings continuously via kwin_libinput. These flood the journal and can slow KDE logging subsystem.
Fix: `QT_LOGGING_RULES=kwin_libinput.warning=false` in `/etc/environment`.
This suppresses the log messages. The underlying hardware behavior is unchanged — libinput still handles it correctly.

### 10.2 Keyboard Backlight

See Part 6 for the complete deep dive. Summary:
- Controlled via KDE System Settings → Hardware → Keyboard Backlight
- 8 modes including Auto Color Cycle
- Config: `~/.config/luminos-keyboard.conf`
- Sysfs: `/sys/class/leds/asus::kbd_backlight/brightness`

---

## PART 11 — CHROME & BROWSER

### 11.1 Complete Launch Stack

1. KDE app launcher or `.desktop` file calls `/usr/local/bin/chrome-luminos`
2. `chrome-luminos` sets GPU env vars and calls `flatpak run com.google.Chrome`
3. Chrome reads per-user flags from `~/.var/app/com.google.Chrome/config/chrome-flags.conf`
4. Chrome starts on Wayland with AMD GPU

### 11.2 chrome-luminos Wrapper (Current)

Source: `scripts/chrome-luminos`, installed at `/usr/local/bin/chrome-luminos`

```bash
export DRI_PRIME=0
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json
exec /usr/bin/flatpak run com.google.Chrome \
  --ozone-platform=wayland \
  --enable-gpu-rasterization \
  --enable-zero-copy \
  --process-per-site \
  --renderer-process-limit=8 \
  --remote-debugging-port=9222 \
  "$@"
```

`DRI_PRIME=0` forces the AMD iGPU. `VK_ICD_FILENAMES` forces the AMD Vulkan ICD. `--ozone-platform=wayland` activates the native Wayland backend (avoids XWayland overhead). `--remote-debugging-port=9222` enables CDP for luminos-ram tab management.

### 11.3 Chrome Flags (chrome-flags.conf)

Location: `~/.var/app/com.google.Chrome/config/chrome-flags.conf`

Current active flags:
```
--ozone-platform=wayland
```

This is applied globally (all Chrome instances). The XWayland path was the root cause of the 95% CPU issue — Chrome was competing with KWin for X11 event processing.

### 11.4 Why ANGLE Was Wrong

A previous configuration had `--use-gl=angle --use-angle=vulkan`. ANGLE is an OpenGL-to-Vulkan translation layer optimized for NVIDIA/Windows. On AMD iGPU with Mesa:
- Mesa's native EGL/GL path is already optimized for RDNA3
- ANGLE adds a translation layer that duplicates work Mesa already does correctly
- Vulkan on RDNA3 via ANGLE has higher driver overhead than native Mesa EGL

Decision 17 (`aaacdbff`) established: AMD branch uses `--use-gl=egl` (Mesa EGL, no translation), NVIDIA branch uses `--use-gl=desktop` (native NVIDIA GL). The `--use-gl` flag is not currently set in `chrome-luminos` — Chrome defaults to EGL on Wayland when `ozone-platform=wayland` is set, which is correct.

### 11.5 Chrome GPU History

- BUG-046: Chrome wrapper had hardcoded `renderD129` (NVIDIA). Fixed by removing render-node-override and setting `DRI_PRIME=0`.
- Commit `9e12186f` was the hotfix where render nodes had been swapped — `renderD128` was incorrectly labeled NVIDIA in the wrapper, causing AMD Signal 5 crash.
- Current state: No render-node-override at all. `DRI_PRIME=0` + AMD VK ICD is sufficient.

### 11.6 Desktop File

`~/.local/share/applications/com.google.Chrome.desktop`

The `Exec=` line was fixed at BUG-052 (`fc828d13`):
- Before: `Exec=/usr/local/bin/chrome-luminos @@u %U @@` (Flatpak URL forwarding syntax — invalid for wrapper)
- After: `Exec=/usr/local/bin/chrome-luminos %U`

After fixing, `kbuildsycoca6 --noincremental` was run to update the sycoca index so KDE search could find Chrome.

---

## PART 12 — APP LAUNCHER (KICKOFF)

### 12.1 How Kickoff Works

Kickoff is the KDE application launcher (the "Start button"). It has two display modes controlled by `applicationsDisplay`:
- `applicationsDisplay=0` — Favorites tab (shows only pinned apps)
- `applicationsDisplay=1` — All Applications tab (shows all installed apps)

Config file: `~/.config/plasma-org.kde.plasma.desktop-appletsrc`

The relevant section is whichever `[Applet-N]` group contains `plugin=org.kde.plasma.kickoff`. Within that group, under `[Configuration][General]`, set `applicationsDisplay=1`.

### 12.2 BUG-052 and Fix

BUG-052 (2026-05-21, commit `fc828d13`):

**Root cause 1**: `applicationsDisplay=0` was set. No apps were pinned to Favorites. Opening the launcher showed a blank screen with no indication that All Applications was a click away.

**Root cause 2**: Chrome's `.desktop` file had `@@u %U @@` in the Exec line — Flatpak-specific URL forwarding syntax. KDE's desktop file parser choked on `@@u`, making Chrome invisible to app search even though the file existed.

**Fix**:
1. `applicationsDisplay=1` → Kickoff opens to All Applications by default
2. Fixed Exec line in Chrome `.desktop`: `Exec=/usr/local/bin/chrome-luminos %U`
3. `kbuildsycoca6 --noincremental` → rebuilt sycoca/desktop database
4. `systemctl --user restart plasma-plasmashell` → reloaded the panel

### 12.3 Managing Favorites and Search

To pin an app to Favorites: right-click its entry in Kickoff → "Add to Favorites".
To search: type in the Kickoff search bar. Apps must have a valid `.desktop` file in `~/.local/share/applications/` or `/usr/share/applications/` and must be indexed in sycoca.

If an app doesn't appear in search after adding a `.desktop` file:
```bash
kbuildsycoca6 --noincremental
# Wait 2-3 seconds
# Search again in Kickoff
```

---

## PART 13 — BUG TRACKER

### 13.1 Full Bug Table

| ID | Title | Status | Severity | Fix Commit | Date Fixed |
|----|-------|--------|----------|-----------|-----------|
| BUG-052 | Kickoff empty + Chrome not searchable | FIXED | HIGH | fc828d13 | 2026-05-21 |
| BUG-051 | 120Hz stutter | FIXED (VRR user-reverted) | MEDIUM | (manual edit) | 2026-05-21 |
| BUG-050 | System processes keeping NVIDIA in D0 | FIXED | HIGH | b7139d30 | 2026-05-14 |
| BUG-049 | Claude Desktop memory leak | MONITORING | MEDIUM | workaround | 2026-05-10 |
| BUG-048 | luminos-power thermal oscillation | FIXED | HIGH | df2bf467 + 385f1302 | 2026-05-17 |
| BUG-047 | NVIDIA GPU always active | FIXED | MEDIUM | b7139d30 | 2026-05-14 |
| BUG-046b | luminos-ram blind to desktop session | FIXED | HIGH | (service fix) | 2026-05-10 |
| BUG-046 | Chrome using NVIDIA GPU | FIXED | HIGH | 9e12186f | 2026-05-14 |
| BUG-045 | Touchpad input lag / jump detection | FIXED | MEDIUM | 496855d8 | 2026-05-09 |
| BUG-043 | HIVE popup crash (import not found) | FIXED | HIGH | 70be6c3c | 2026-04-26 |
| BUG-037 | CMake 3.30+ required for Hyprland | FIXED (Ubuntu era) | MEDIUM | bf1333418 | 2026-03-28 |
| BUG-035 | Hyprland build from source in chroot | FIXED (Ubuntu era) | HIGH | 6f541214 | 2026-03-28 |
| BUG-033 | macOS Sequoia visual styling | FIXED (Ubuntu era) | LOW | 643f270 | 2026-03-27 |
| BUG-032 | Hyprland with blur/animations | FIXED (Ubuntu era) | MEDIUM | 0f107bd4 | 2026-03-27 |
| BUG-031 | sway errors + waybar | FIXED (Ubuntu era) | HIGH | 40885990 | 2026-03-27 |
| BUG-029/030 | macOS UX animations, switcher, dock | FIXED (Ubuntu era) | LOW | 07c0a6ce | 2026-03-27 |
| BUG-028 | auto-login + sway autostart | FIXED (Ubuntu era) | HIGH | 4b2b3f3b | 2026-03-27 |
| BUG-027 | squashfs root filesystem structure | FIXED (Ubuntu era) | HIGH | 55674146 | 2026-03-27 |
| BUG-026 | grub-mkrescue for ISO | FIXED (Ubuntu era) | HIGH | fcd92b7d | 2026-03-27 |
| BUG-025 | GRUB embedded config ignores grub.cfg | FIXED (Ubuntu era) | HIGH | 3e184d9e | 2026-03-27 |
| BUG-023 | initrd must regen after live-boot | FIXED (Ubuntu era) | HIGH | 0c4d4241 | 2026-03-27 |
| BUG-022 | casper live-boot + initrd regen | FIXED (Ubuntu era) | HIGH | c76b0872 | 2026-03-27 |
| BUG-021 | lupin-casper removed from Ubuntu 24.04 | FIXED (Ubuntu era) | HIGH | dc2970d1 | 2026-03-25 |
| BUG-020 | useradd check if user exists | FIXED (Ubuntu era) | MEDIUM | 521ee4d7 | 2026-03-25 |
| BUG-018 | SKIP_STAGE1 for existing chroot | FIXED (Ubuntu era) | MEDIUM | 149b9ab6 | 2026-03-25 |
| BUG-017 | kernel missing in chroot | FIXED (Ubuntu era) | HIGH | 57d7ddf4 | 2026-03-25 |
| BUG-016 | grub.cfg inline fallback | FIXED (Ubuntu era) | HIGH | 57d7ddf4 | 2026-03-25 |
| BUG-015 | debootstrap cache reuse | FIXED (Ubuntu era) | MEDIUM | 8874773a | 2026-03-25 |
| BUG-014 | proc/sys/dev in squashfs | FIXED (Ubuntu era) | HIGH | 2551280c | 2026-03-25 |
| BUG-013 | update-desktop-database fallback | FIXED (Ubuntu era) | LOW | c0a18ff6 | 2026-03-25 |
| BUG-012 | rm -rf at build start | FIXED (Ubuntu era) | CRITICAL | 797c6e56 | 2026-03-25 |
| BUG-011 | Wine gecko/mono download | FIXED (Ubuntu era) | MEDIUM | b07732cb | 2026-03-25 |

### 13.2 Active / Monitoring

| ID | Status | Watching for |
|----|--------|-------------|
| BUG-049 | MONITORING | Claude Desktop RSS >1.5GB (daily restart workaround active) |
| BUG-051 | User-reverted | If user re-enables VRR and stutters return, see kwinrc `GLPreferBufferSwap` setting |

### 13.3 Recurring Diagnostic Patterns

**Pattern: "Something is making NVIDIA stay awake"**
Check: `cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status`
If `active`: `cat /proc/$(pgrep -f chrome)/maps | grep nvidia` — find the process holding NVIDIA.
Root cause historically: EGL vendor default was NVIDIA. Check `/etc/environment` has the mesa EGL line.

**Pattern: "Power daemon looks fine but thermals are bad"**
The daemon may be running but the fan curves may not have been applied to hardware. Check: `asusctl fan-curve -m balanced`. If it shows the factory default (silent until 70°C), the fan-curve apply at startup failed.
Fix: `sudo systemctl restart luminos-power` (it applies fan curves at startup).

**Pattern: "KDE search doesn't find an app I just installed"**
sycoca index is stale. Fix: `kbuildsycoca6 --noincremental`. This rebuilds the entire desktop database from scratch (the `--noincremental` flag is important — incremental updates sometimes miss new entries).

---

## PART 14 — CONFIGURATION FILE REFERENCE

### 14.1 Master Config File Table

| File | Owner | Purpose |
|------|-------|---------|
| `/etc/environment` | root | System-wide env vars; EGL vendor, KWin DRM, Qt logging |
| `~/.config/kwinoutputconfig.json` | user | Display: Hz, sharpness, VRR, brightness, scale |
| `~/.config/luminos-keyboard.conf` | user | Keyboard backlight: mode, color, speed, auto-cycle |
| `~/.config/plasma-org.kde.plasma.desktop-appletsrc` | user | Panel/desktop applet config including Kickoff display mode |
| `~/.config/kwinrc` | user | KWin compositor settings |
| `~/.var/app/com.google.Chrome/config/chrome-flags.conf` | user | Chrome launch flags |
| `~/.local/share/applications/com.google.Chrome.desktop` | user | Chrome .desktop file for KDE launcher |
| `/etc/libinput/local-overrides.quirks` | root | Touchpad quirks for ASUP1208 |
| `/etc/systemd/system/luminos-power.service` | root | luminos-power systemd unit |
| `~/.local/share/kio/servicemenus/luminos-gpu-select.desktop` | user | Dolphin right-click GPU selector (executables) |
| `~/.local/share/kio/servicemenus/luminos-app-gpu.desktop` | user | Dolphin right-click GPU selector (.desktop files) |

### 14.2 /etc/environment — Annotated

```bash
# Force Mesa (AMD) EGL for all session processes.
# Prevents NVIDIA staying in D0 from system processes (BUG-050).
# Override for NVIDIA apps: export __EGL_VENDOR_LIBRARY_FILENAMES=...60_nvidia.json
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json

# Lock KWin compositor to AMD DRM device only.
# card2 = AMD Radeon 780M on this system (counterintuitive — see Part 1.2).
# Prevents KWin advertising renderD129 (NVIDIA) via linux-dmabuf to Wayland clients.
KWIN_DRM_DEVICES=/dev/dri/card2

# Suppress ASUS G14 ASUP1208 touchpad "Touch jump" log spam.
# Hardware reports spurious coordinate jumps. libinput handles them; this silences logs.
QT_LOGGING_RULES=kwin_libinput.warning=false
```

### 14.3 kwinoutputconfig.json Field Reference

| Field | Current Value | Notes |
|-------|--------------|-------|
| `connectorName` | `"eDP-2"` | Display connector name |
| `mode.refreshRate` | `60001` | Millihertz: 60001=60Hz, 120001=120Hz |
| `scale` | `2` | Integer 2× HiDPI |
| `vrrPolicy` | `"Never"` | Disabled (user-intentional); options: Never, Automatic, Always |
| `sharpness` | `0.35` | AMD display sharpening, 0.0–1.0 |
| `brightness` | `0.3` | Display brightness (0.0–1.0) |

### 14.4 asusctl Fan Curve Syntax

Format: `"TEMP:PCT,TEMP:PCT,..."` — comma-separated pairs of temperature (°C) and fan speed (%).

Rules:
- Must have at least 8 points
- Temperature must be monotonically increasing
- First point should be 30°C or lower
- Last point should be 90°C or higher
- 100% at the high end is safe and recommended

Current working curve (as of `385f1302`):
```
CPU/GPU fan: "30c:0%,40c:40%,45c:62%,50c:80%,60c:95%,70c:100%,80c:100%,90c:100%"
Mid fan:     "30c:0%,40c:30%,45c:52%,50c:72%,60c:88%,70c:100%,80c:100%,90c:100%"
```

Apply command:
```bash
asusctl fan-curve --mod-profile balanced --fan cpu --data "30c:0%,40c:40%,45c:62%,50c:80%,60c:95%,70c:100%,80c:100%,90c:100%"
asusctl fan-curve --mod-profile balanced --fan gpu --data "30c:0%,40c:40%,45c:62%,50c:80%,60c:95%,70c:100%,80c:100%,90c:100%"
asusctl fan-curve --mod-profile balanced --fan mid --data "30c:0%,40c:30%,45c:52%,50c:72%,60c:88%,70c:100%,80c:100%,90c:100%"
asusctl fan-curve --mod-profile balanced --enable-fan-curves true
```

### 14.5 luminos-keyboard.conf All 10 Keys

See Part 6.9 for the full annotated config. Current live values from `~/.config/luminos-keyboard.conf`:
```ini
KB_COLOR="ff0000"
KB_COLOR2="00ff00"
KB_BRIGHTNESS="2"
KB_MODE="rainbow-wave"
KB_SPEED="1"
KB_DIRECTION="Up"
KB_AUTO_ENABLED="false"
KB_AUTO_INTERVAL="3"
KB_AUTO_COLORS="ff0000,00ff00,0000ff,ffff00,ff00ff,00ffff"
KB_BREATHE_DUAL="false"
```

---

## PART 15 — ARCHITECTURAL DECISIONS

### D13 — Go/Python Split Architecture
Commit: `39beedd5` | Date: April 2026

**Decision**: Go for all system daemons; Python only where ML library bindings are unavoidable.

**Rationale**: Go produces static binaries with no venv/pip fragility. Goroutines map naturally to socket servers and polling loops. Python is required only for ONNX/VitisAI (no Go bindings), llama-cpp-python (no Go equivalent), and numpy tensor operations.

**What was rejected**: All-Python (fragile at scale, slow startup, venv management); all-Go (no llama.cpp or ONNX bindings available).

See `LUMINOS_DECISIONS.md` and `docs/DAEMON_ARCHITECTURE.md` for full rationale table.

### D15 — HATS NPU Architecture
Commit: `5ef0e7e6` | Date: 2026-04-22

**Decision**: Use Triton-XDNA for NPU inference (AMD XDNA accel0), not ROCm iGPU. Model: MobileLLM-R1-140M INT8 ONNX (64MB weights). Budget: 300MB soft / 800MB hard.

**Rationale**: NPU is dedicated silicon sitting idle — HATS puts it to work for Sentinel inference without competing with KWin (iGPU) or consuming VRAM (dGPU). Triton-XDNA removes the VitisAI VOE compiler black box.

**What was rejected**: ROCm on iGPU — competes with desktop compositor and increases thermal pressure on the shared heatpipe. GGUF on NPU — llama.cpp has no NPU backend.

**Implementation status**: Triton-XDNA installed, aie.xclbin compiled, MobileLLM quantized. NPU silicon path requires on-device XRT BO validation — currently running on CPU torch backend as fallback.

### D16 — GPU-Per-App via Env Vars
Commit: `aaacdbff` | Date: 2026-05-21

**Decision**: Universal GPU launcher via environment variable injection. Two tools: `luminos-gpu-launch` (interactive picker) and `luminos-nvidia-run` (direct NVIDIA launch). Dolphin service menus wire these to right-click for any app.

**Rationale**: PRIME render offload works via env vars for native Wayland apps without system-level changes. Dolphin service menus cover any app without per-app wrappers. NVIDIA requires explicit PCI power gate wake before use — `luminos-nvidia-run` handles this.

**What was rejected**: System-wide NVIDIA default (increases VRAM pressure and heat at idle); per-app wrappers for every binary (unmaintainable at scale); GPU selector widget in panel (breaks panel when clicked — proven during development session).

### D17 — Chrome Wayland Mode + GPU-Specific GL
Commit: `aaacdbff` | Date: 2026-05-21

**Decision**: `--ozone-platform=wayland` globally. AMD path: Mesa EGL (no ANGLE). NVIDIA path: `--use-gl=desktop`. Removed all `--use-gl=angle --use-angle=vulkan` flags.

**Rationale**: ANGLE+Vulkan was a Windows/NVIDIA optimization. On AMD iGPU, Mesa EGL is the native path — adding ANGLE is pure overhead. XWayland caused 95% CPU competing with KWin for X11 event processing.

**What was rejected**: Global `--use-gl=egl` (breaks NVIDIA path); NIS upscaling on Wayland PRIME (compositor owns framebuffer — not possible); persisting ANGLE flags (high CPU on AMD, no benefit).

---

## PART 16 — MAINTENANCE PROCEDURES

### 16.1 Update luminos-power Binary

The binary must be installed with pkexec (or sudo) because it runs as root and writes to root-owned sysfs paths.

```bash
cd ~/luminos-os
go build -o /tmp/luminos-power-new ./cmd/luminos-power/
sudo cp /tmp/luminos-power-new /usr/local/bin/luminos-power
sudo systemctl restart luminos-power
sudo systemctl status luminos-power  # verify it started
sudo journalctl -u luminos-power -n 20  # check startup log
```

Do not use `go install` — it installs to `~/go/bin/` which is not the service path.

### 16.2 Change Fan Curves Safely

1. Edit the curve strings in `cmd/luminos-power/main.go` at lines 732–733
2. Rebuild and install (see 16.1)
3. Verify immediately: `asusctl fan-curve -m balanced`
4. Monitor temperature under load: `watch -n 1 sensors`
5. If temperature climbs past 65°C under normal workload, the curve is too gentle — increase the intermediate points

**Safe rule**: Never set a point at 45°C lower than 50% CPU fan. The early-ramp principle (Part 4.7) is essential for the 50°C target.

### 16.3 Add a HIVE Model

1. Download the GGUF file to `/opt/luminos/models/`
2. Add the model alias to `ALLOWED_MODELS` in `scripts/hive-daemon.py:45`
3. Add a chip mapping in `CHIP_TO_MODEL` (hive-daemon.py:49–55) or add keyword patterns to `detect_intent()`
4. Create a system prompt file at `/home/shawn/luminos-os/config/prompts/<alias>.txt`
5. Update `scripts/hive-start-model.sh` with the model filename
6. Update `LUMINOS_STATUS.md` with the new model's TPS benchmark
7. Test: `curl -s -X POST http://127.0.0.1:8078/chat -H 'Content-Type: application/json' -d '{"message":"hello","model":"<alias>"}'`

VRAM check before adding: ensure the Q4_K_M GGUF size + ~400MB overhead is under 4.6GB.

### 16.4 After KDE Update Checklist

```bash
# Check if KCM plugins still load
systemsettings6 &
# Navigate to Hardware → Keyboard Backlight
# Navigate to System Administration → HIVE AI Settings
# If either is missing:
kbuildsycoca6 --noincremental

# Check power widget still shows in panel
# Right-click panel → Configure Panel → Add Widgets → search "luminos"

# Verify SUPER+SPACE still works
# If not: System Settings → Shortcuts → Global Shortcuts → search "hive"
# Re-set to /usr/local/bin/luminos-hive-popup

# Check Wayland session type
echo $XDG_SESSION_TYPE  # should be "wayland"

# Check EGL vendor override survived
grep EGL /etc/environment  # must still be there
```

### 16.5 After Kernel Update Checklist

```bash
# Rebuild NVIDIA dkms module for new kernel
sudo dkms autoinstall
# or
sudo mkinitcpio -P

# Verify NVIDIA module loaded
lsmod | grep nvidia

# Check NPU still accessible
ls /dev/accel0

# Restart luminos-power (reads sysfs at startup — kernel paths may have changed)
sudo systemctl restart luminos-power

# Check fan curves applied
asusctl fan-curve -m balanced

# Check touchpad quirks still applied
sudo libinput list-devices | grep -A 5 ASUP1208
```

---

## APPENDIX A — SCRIPT REFERENCE

### /usr/local/bin/luminos-power
Go daemon binary. Not a script. See Part 4.
Start: `sudo systemctl start luminos-power`
Logs: `sudo journalctl -u luminos-power -f`

### /usr/local/bin/luminos-hive-popup
Source: `scripts/luminos-hive-popup`
Purpose: Toggle HIVE chat window via SUPER+SPACE. Sets Wayland env, starts llama-server and hive-daemon.py, launches `qml6 src/hive/HiveChat.qml`.
Key lines: Lock logic (86–97), llama-server start (107–118), daemon start (124–129), keep-alive loop (137–144), qml6 launch (152).

### /usr/local/bin/luminos-gpu-launch
Source: `scripts/luminos-gpu-launch`
Purpose: Interactive GPU picker for any command. Shows kdialog menu, sets AMD or NVIDIA env vars, execs the command.
Usage: `luminos-gpu-launch blender` or `luminos-gpu-launch flatpak run com.valvesoftware.Steam`

### /usr/local/bin/luminos-nvidia-run
Source: `scripts/luminos-nvidia-run`
Purpose: Wake NVIDIA from D3cold, set PRIME env vars, exec the command. Used by Dolphin service menus.
Key detail: Writes `"on"` to `/sys/bus/pci/devices/0000:01:00.0/power/control`, sleeps 0.3s, then execs.
Usage: `luminos-nvidia-run blender`

### /usr/local/bin/luminos-display-hz
Source: `scripts/luminos-display-hz`
Purpose: Interactive Hz selector. Reads current rate from kwinoutputconfig.json, shows kdialog radiolist, calls luminos-60hz or luminos-120hz.
Used by: KDE System Settings entry (`luminos-display-hz.desktop`).

### /usr/local/bin/luminos-60hz
Source: `scripts/luminos-60hz`
Purpose: Switch display to 60Hz. Primary: kscreen-doctor. Fallback: direct JSON edit + qdbus6 reconfigure.
Usage: `luminos-60hz` (also called by luminos-power on AC unplug)

### /usr/local/bin/luminos-120hz
Source: `scripts/luminos-120hz`
Purpose: Switch display to 120Hz. Same mechanism as luminos-60hz.
Usage: `luminos-120hz` (also called by luminos-power on AC plug)

### /usr/local/bin/chrome-luminos
Source: `scripts/chrome-luminos`
Purpose: Chrome wrapper. Sets AMD GPU env vars, adds Wayland and GPU flags, launches Flatpak Chrome.
Key flags: `--ozone-platform=wayland`, `--remote-debugging-port=9222`, `--renderer-process-limit=8`

### scripts/luminos-keyboard-smart
Purpose: Smart keyboard backlight daemon. Reads `~/.config/luminos-keyboard.conf` and applies settings. Called by `luminos-keyboard.service` on start and wake.

### scripts/luminos-notes.sh
Purpose: SQLite-backed notes system (replaced MemPalace). Used by agents to index and search project knowledge.
Usage: `~/luminos-os/scripts/luminos-notes.sh search "topic"` and `~/luminos-os/scripts/luminos-notes.sh add [TAG] "summary"`

---

## APPENDIX B — GIT COMMIT INDEX

Total commits: 322 (as of 2026-05-21)

### Power Management
| Hash | Date | Summary |
|------|------|---------|
| 385f1302 | 2026-05-21 | fix(power): revert to working fan curve + thermal governor |
| 8faeef7d | 2026-05-21 | fix(power): thermal governor v3.3 — WRONG, do not use |
| febd312a | 2026-05-21 | fix(power): fan curve v3.2 — WRONG, do not use |
| c34f41fb | 2026-05-19 | fix(power): fan curve early ramp — 50°C target |
| df2bf467 | 2026-05-17 | fix(power): luminos-power v3.1 — beast mode, thermal tuning |
| 413ff77b | 2026-05-17 | fix(power): beast mode exit clears freq cap |
| e8c81de5 | 2026-05-17 | fix(power): EPP=power on AC, 45°C target |
| 810ec387 | 2026-05-14 | fix(power): ROOT-02 EPP-based control replaces load-tracking |
| b5821507 | 2026-05-15 | fix(power): v3.1 thermal governor targeting 45°C |
| f5a3664b | 2026-05-07 | fix(power): lower temp thresholds for 50°C target |
| 5ac89de8 | 2026-05-08 | fix(power): restore brightness and keyboard on wake |
| 374fdd3d | 2026-05-10 | fix(power+ram): BUG-048 thermal + Chrome compression |
| f7f29d54 | 2026-05-10 | feat(power+ram+kwin): quiet default + video + maximize |
| 83d45443 | 2026-05-10 | feat(power): smart mode switching + startup health |
| ebf11916 | 2026-04-20 | feat(daemons): Phase 1 Go foundation complete |

### GPU Management
| Hash | Date | Summary |
|------|------|---------|
| aaacdbff | 2026-05-21 | feat(gpu+power+display): universal GPU launch, fan curve, Hz toggle, sharpness |
| 9e12186f | 2026-05-15 | fix(gpu): BUG-046 hotfix — render nodes reversed |
| 81bef374 | 2026-05-14 | fix(gpu): BUG-046 re-fix — render-node-override |
| 9c6a161e | 2026-05-14 | fix(gpu): EGL vendor hard override + Wine launcher |
| b7139d30 | 2026-05-14 | fix(gpu): ROOT-01 nvidia-powerd masked + EGL priority |
| becce2d3 | 2026-05-12 | feat(gpu+widget): Wine GPU selector + power widget |
| 38b585e4 | 2026-05-11 | fix(gpu): Wine/MT5 AMD only |
| f77317c5 | 2026-05-10 | fix(gpu+power): Chrome AMD only + NVIDIA power gating |

### HIVE AI
| Hash | Date | Summary |
|------|------|---------|
| 45f6bee5 | 2026-05-03 | chore(hive): retire hive-swap-server.py |
| 9b25851e | 2026-05-09 | fix(hive): update hive-brain.md after audit |
| 0600a3a4 | 2026-05-09 | feat(hive): terminal watcher + crash analyzer |
| 0fe6acbe | 2026-05-09 | feat(hive): stdio MCP wrapper for all agents |
| 080067a6 | 2026-05-08 | fix(hive): replace Flask+browser with PyQt6 |
| ec225540 | 2026-05-08 | feat(hive): popup v4 Flask+HTML |
| 825287ec | 2026-05-09 | fix(hive): UI adjustments |
| 51c2676b | 2026-04-27 | feat(hive): rebuild popup as native QML6 |
| 5ef0e7e6 | 2026-04-22 | feat(ai): adopt HATS architecture |
| b4964.. | 2026-05-04 | fix(hive): sidebar scroll, timestamps, layout (multiple) |

### RAM Management
| Hash | Date | Summary |
|------|------|---------|
| fa5eadf0 | 2026-05-08 | feat(ram): v3.0 precise hot/cold window algorithm |
| 2cabf3d6 | 2026-05-08 | feat(ram): LIRS v2.0 complete RAM architecture |
| 9416f714 | 2026-05-07 | feat(ram): KWin focus-based activity tracking |
| 1db2912a | 2026-05-07 | feat(ram): luminos-ram installed and tested |
| eeeebcc0 | 2026-05-10 | feat(ram): macOS-style silent process restart |
| 0eb5dd6e | 2026-05-06 | feat(ram): ZRAM + KSM + earlyoom + Chrome limits |
| e2615990 | 2026-05-08 | docs: RAM management Phase 3 |

### Display
| Hash | Date | Summary |
|------|------|---------|
| aaacdbff | 2026-05-21 | feat(gpu+power+display): Hz toggle, display sharpness |
| f3e95811 | 2026-05-21 | feat(widget): Hz toggle in power widget popup |
| be7615c9 | 2026-05-21 | fix(power): fan curve v3.2 (see also febd312a) |

### Input
| Hash | Date | Summary |
|------|------|---------|
| fc828d13 | 2026-05-21 | fix(launcher): Kickoff empty + Chrome not searchable |
| 496855d8 | 2026-05-09 | fix(input): touchpad jump threshold + schedutil governor |
| ad7097ad | 2026-05-09 | fix(chrome): remove experimental Vulkan flags |

### UX / Theme
| Hash | Date | Summary |
|------|------|---------|
| f81b0cd9 | 2026-05-11 | feat(visual): revert Tahoe theme, restore Breeze |
| a2ec7eec | 2026-05-10 | fix(desktop): instant wake + white panel fix |
| adce1e68 | 2026-05-10 | fix(theme): white panel + fullscreen + icon corners |
| ff82c759 | 2026-05-10 | feat(theme): fully automated Tahoe theme apply |
| c0e11c63 | 2026-05-10 | feat(theme): Tahoe macOS theme installed |

### KDE / KCM / Keyboard
| Hash | Date | Summary |
|------|------|---------|
| 842ded7d | 2026-04-26 | feat(ux): keyboard backlight as real KDE KCM |
| 7b8330e0 | 2026-04-26 | fix(ux): keyboard always on + settings in KDE |
| 79c85df2 | 2026-04-25 | feat(ux): keyboard backlight KDE settings integration |
| 06bd740a | 2026-04-19 | docs(decision): permanent move to KDE Plasma |
| baffe29f | 2026-04-20 | feat(kde): save KDE config, auto-apply on login |

### Docs / Architecture
| Hash | Date | Summary |
|------|------|---------|
| 18b3d8cf | 2026-05-21 | docs: session 2 doc refresh |
| 0db2b26f | 2026-05-21 | docs: full project refresh May 2026 |
| 9a4a8f48 | 2026-05-09 | docs: full Luminos OS guide + HIVE override protocol |
| 06bd740a | 2026-04-19 | docs(decision): permanent move to KDE Plasma |

### Compat / Wine / VM
| Hash | Date | Summary |
|------|------|---------|
| 38b585e4 | 2026-05-11 | fix(gpu): Wine/MT5 AMD only |
| f27fc821 | 2026-05-09 | fix(chrome): correct wrapper flags |
| 28974fe6 | 2026-05-10 | fix(chrome): remove persistent unstable flags |

### OS Foundation (Ubuntu/Arch era)
| Hash | Date | Summary |
|------|------|---------|
| 3b8a95aa | 2026-03-22 | Luminos OS v0.1.0-alpha - all phases complete |
| 0974c05c | 2026-03-31 | Phase 1 complete — repo 100% Arch native |
| f0112b6e | 2026-03-31 | Ubuntu build final state — before Arch migration |

---

## APPENDIX C — SOCKET IPC REFERENCE

### Protocol Standard

All Go daemon sockets use newline-delimited JSON. Each request/response is a single JSON object followed by `\n`. The standard message envelope:

```json
{
  "type": "ping",
  "source": "client-name",
  "timestamp": "2026-05-21T12:00:00Z",
  "payload": {}
}
```

Response envelope:
```json
{
  "type": "ping_response",
  "source": "luminos-power",
  "timestamp": "2026-05-21T12:00:00Z",
  "payload": {"status": "ok"}
}
```

### luminos-power — /run/luminos/power.sock

| Message Type | Direction | Payload | Response |
|-------------|-----------|---------|----------|
| `ping` | client→daemon | {} | `{status:"ok"}` |
| `status` | client→daemon | {} | PowerState struct |
| `set_profile` | client→daemon | `{profile:"Balanced"}` | `{status:"ok"}` |
| `report_power` | daemon→ai | PowerState struct | none (fire and forget) |

PowerState struct fields: `on_ac`, `cpu_temp_c`, `gpu_load`, `epp`, `profile`, `updated_at`

### luminos-ai — /run/luminos/ai.sock

| Message Type | Direction | Payload |
|-------------|-----------|---------|
| `ping` | client→daemon | {} |
| `status` | client→daemon | {} |
| `model_request` | client→daemon | `{model:"bolt"}` |
| `gaming_mode` | client→daemon | `{active:true}` |
| `report_power` | power→ai | PowerState |

### luminos-sentinel — /run/luminos/sentinel.sock

| Message Type | Payload |
|-------------|---------|
| `ping` | {} |
| `status` | {} |
| `classify_process` | `{pid:1234, name:"foo"}` |

### hive-daemon.py — HTTP 127.0.0.1:8078

| Endpoint | Method | Request Body | Response Body |
|----------|--------|-------------|---------------|
| `/health` | GET | — | `{"status":"ok"}` |
| `/state` | GET | — | `{"model":"nexus","ready":true,"stage":"idle"}` |
| `/chat` | POST | `{"message":"...", "model":"nexus", "history":[...]}` | Streaming or JSON response |
| `/copy` | POST | `{"text":"..."}` | `{"status":"ok"}` |

---

## APPENDIX D — QUICK COMMANDS

### Power
```bash
# Current profile
asusctl profile -p

# Restart power daemon
sudo systemctl restart luminos-power

# Watch thermal logs live
sudo journalctl -u luminos-power -f

# Check EPP on all cores
cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c

# Force balanced profile manually
asusctl profile set Balanced

# Apply fan curve manually (if daemon failed)
asusctl fan-curve --mod-profile balanced --fan cpu --data "30c:0%,40c:40%,45c:62%,50c:80%,60c:95%,70c:100%,80c:100%,90c:100%" && asusctl fan-curve --mod-profile balanced --enable-fan-curves true
```

### GPU
```bash
# Check if NVIDIA is sleeping
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status

# Wake NVIDIA manually
echo "on" | sudo tee /sys/bus/pci/devices/0000:01:00.0/power/control

# Put NVIDIA back to sleep
echo "auto" | sudo tee /sys/bus/pci/devices/0000:01:00.0/power/control

# Check which GPU Chrome is using
cat /proc/$(pgrep -f chrome | head -1)/maps | grep -c nvidia
# 0 = AMD; >0 = NVIDIA (bad)

# Launch any app on NVIDIA
luminos-nvidia-run blender
```

### HIVE
```bash
# Health check
curl -s http://127.0.0.1:8078/health

# Current model
curl -s http://127.0.0.1:8078/state

# Full restart
pkill -f hive-daemon.py; pkill -f llama-server

# Test chat
curl -s -X POST http://127.0.0.1:8078/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello","model":"nexus"}' | python3 -m json.tool
```

### Display
```bash
# Switch to 60Hz
luminos-60hz

# Switch to 120Hz
luminos-120hz

# Current refresh rate
python3 -c "import json; d=json.load(open('/home/shawn/.config/kwinoutputconfig.json')); [print(o['mode']['refreshRate']//1000,'Hz') for item in d for o in item.get('data',[]) if 'mode' in o]"
```

### KDE
```bash
# Rebuild app database (fix missing apps in search)
kbuildsycoca6 --noincremental

# Restart panel/desktop
systemctl --user restart plasma-plasmashell

# Reload KWin compositor (no logout needed)
qdbus6 org.kde.KWin /KWin reconfigure

# Check KCM plugins are loaded
systemsettings6 &
```

### Diagnostics
```bash
# Full system temperature
sensors

# VRAM usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# All Luminos daemons status
for svc in luminos-power; do sudo systemctl status $svc --no-pager -l | head -3; done

# luminos-ram status
systemctl --user status luminos-ram

# Check touchpad quirks active
sudo libinput list-devices 2>/dev/null | grep -A 10 "ASUP1208"
```

---

## APPENDIX E — GLOSSARY

**asusctl**: ASUS Linux control tool. Sets profiles (Quiet/Balanced/Performance), fan curves, keyboard backlighting, and other ROG-specific hardware settings. The Go daemon calls `asusctl profile set` and `asusctl fan-curve` as subprocesses.

**Aurorae**: KDE window decoration engine. Renders window title bars and borders. Tahoe theme used Aurorae; Breeze (default) also uses Aurorae. A broken Aurorae theme causes the white panel bug.

**CDP (Chrome DevTools Protocol)**: The remote debugging API exposed by Chrome on port 9222 (via `--remote-debugging-port=9222`). luminos-ram uses CDP to discard cold browser tabs, which frees their full memory without killing the Chrome process.

**D3cold**: The deepest PCIe power state. NVIDIA GPU in D3cold consumes ~0W. Waking from D3cold requires writing `"on"` to the PCI `power/control` sysfs file and waiting ~200–300ms before the device is accessible.

**DRM (Direct Rendering Manager)**: The Linux kernel subsystem managing GPU hardware. DRM devices appear as `/dev/dri/cardN`. On this system: card1=NVIDIA, card2=AMD (counterintuitive due to PCIe enumeration order).

**earlyoom**: A userspace out-of-memory killer that monitors memory pressure and kills processes before the kernel OOM killer triggers. Avoids the 30-second system stall caused by kernel OOM.

**EGL**: The interface between OpenGL/ES and the native windowing system. On Linux, libEGL dispatches to either Mesa (AMD/Intel) or the NVIDIA proprietary driver based on `/usr/share/glvnd/egl_vendor.d/*.json` files. `__EGL_VENDOR_LIBRARY_FILENAMES` overrides this dispatch.

**EPP (Energy Performance Preference)**: A per-CPU-core hint to the AMD P-state driver. Values from most-conservative to most-aggressive: `power`, `balance_power`, `balance_performance`, `performance`. Written to `/sys/devices/system/cpu/cpuN/cpufreq/energy_performance_preference`.

**HATS (Host-Assisted Tile-Streaming)**: Luminos OS architecture for NPU inference. The CPU (host) manages XRT Buffer Object allocation and DMA scheduling; the AMD XDNA NPU tiles execute matrix operations. Used for Sentinel's MobileLLM-R1-140M inference on `/dev/accel0`.

**HotSet**: In luminos-ram LIRS algorithm, the set of N=8 most recently / frequently used windows. Windows in the HotSet are protected from compression; windows evicted from the HotSet enter the ColdSet.

**IRR (Inter-Reference Recency)**: The LIRS algorithm metric. IRR for a window = number of unique other windows focused between two consecutive focuses of that window. Low IRR = high relative usage frequency.

**kbuildsycoca6**: Rebuilds the KDE System Configuration Cache (sycoca) — the binary database of installed applications, KCM plugins, and service menus. Run after installing new `.desktop` files, KCMs, or service menus.

**KCM (KDE Control Module)**: A plugin for KDE System Settings. Each settings panel is a KCM. KCMs are `.so` files in `/usr/lib/qt6/plugins/plasma/kcms/systemsettings/`. The keyboard backlight and HIVE settings are custom Luminos KCMs.

**KSM (Kernel Samepage Merging)**: Kernel feature that deduplicates identical anonymous memory pages. Saves RAM when multiple processes have identical memory content (e.g., multiple instances of the same binary). Enabled on AC, disabled on battery.

**Kvantum**: A Qt widget style engine that applies SVG-based themes. Used by Tahoe theme. Not active in current Breeze default state.

**LIRS (Low Inter-Reference Recency Set)**: A cache replacement algorithm. Used by luminos-ram v3 to decide which background windows to compress/freeze. More accurate than LRU because it tracks relative use frequency rather than just time since last access.

**PRIME render offload**: The NVIDIA Linux feature where the dGPU renders frames offscreen and hands them to the iGPU compositor via DMA-BUF. Activated by setting `DRI_PRIME=1`, `__NV_PRIME_RENDER_OFFLOAD=1`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`. The iGPU always drives the display.

**plasmoid**: A KDE Plasma widget. The power widget (`org.luminos.powerwidget`) is a plasmoid. Plasmoids run inside `plasmashell` and can crash it if they open blocking dialogs from the main thread.

**sycoca**: The KDE System Configuration Cache. A binary database used by KDE to quickly find applications, plugins, service menus, and other installable components. Rebuilt by `kbuildsycoca6`.

**TurboQuant**: The llama.cpp quantization format used for HIVE models. `turbo4` uses `type_k=12, type_v=12` — a mixed-precision scheme that maintains accuracy in KV-cache while aggressively quantizing weights. Produces smaller models with better perplexity than standard Q4_K_M.

**VRR (Variable Refresh Rate)**: A display technology where the display's refresh rate follows the GPU's frame rate rather than a fixed interval. Reduces tearing and can reduce power consumption. Currently disabled (`vrrPolicy: "Never"`) after BUG-051 user revert.

**ZRAM**: A kernel virtual block device that uses RAM as a compressed swap device. Pages swapped to ZRAM are compressed (typically 2:1 to 3:1 ratio), allowing more "effective RAM" than physically available. luminos-ram uses `MADV_PAGEOUT` to proactively push cold pages to ZRAM.

**supergfxctl**: ASUS GPU management tool that controls the PRIME/hybrid mode. Currently locked to hybrid mode (iGPU always active, dGPU on-demand via PRIME). Do not switch to integrated-only (breaks HIVE) or NVIDIA-only (breaks sleep).

---

*End of Luminos OS Service & Operations Handbook*
*Last Updated: 2026-05-21*
*Maintained by: claude-code*
*Repository: ~/luminos-os*
*Git log: `git -C ~/luminos-os log --oneline` (322 commits)*
