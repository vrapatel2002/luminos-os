# LUMINOS OS — ROADMAP
(Moved from LUMINOS_PHASES_5_TO_6.md on 2026-04-19)

# Phases 5.x TO 6 ROADMAP
# Version: 1.1 — NPU corrections, display smart switching, wallpaper split
# Everything that needs to be done before ISO build.
# Status: [ ] Not started  [~] In progress  [x] Done

---

## CRITICAL HARDWARE RULES (Read Before Every Phase)
# These are locked. No exceptions. No fallbacks.

```
NPU (AMD XDNA — 16 TFLOPS AI cores):
  → Compatibility Router ONLY runs here
  → Sentinel security ONLY runs here
  → If NPU unavailable: these features wait. No fallback to anything else.
  → Never share NPU between Router and Sentinel simultaneously — queue them

GPU (RTX 4050):
  → Games, rendering, heavy graphics ONLY
  → Never used for AI routing or Sentinel
  → Always Hybrid mode via supergfxctl — never changed

CPU (general cores):
  → Regular OS tasks, apps, everything else
  → Never used for AI inference
  → Never used as fallback for NPU tasks
```

---

## PHASE 5.1 — UI/UX Complete Redesign
Reference: LUMINOS_DESIGN_SYSTEM.md for every visual decision

```
[ ] Create luminos_theme.py — single source of all colors/fonts/spacing
[ ] Redesign Dock — frosted glass pill, centered, hover effects, active dot
[ ] Redesign Top Bar — minimal, clock center, workspace dots, system tray
[ ] Redesign Window decorations — 12px floating, 0px maximized, blue border
[ ] Redesign Login screen — big clock, date, slide-up password field
[ ] Apply Inter font everywhere
[ ] Apply #0A0A0F base color everywhere
[ ] No hardcoded colors anywhere in codebase after this phase
```

---

## PHASE 5.2 — Settings App Full Redesign
Reference: LUMINOS_DESIGN_SYSTEM.md components section

```
[ ] Redesign sidebar — 220px, dark glass, active item has blue left border
[ ] Redesign Appearance panel — theme toggle, accent color picker (blue default)
[ ] Build Wallpaper panel — see Phase 5.3 for full spec
[ ] Build Display panel — resolution, refresh rate (smart — see below), brightness
[ ] Build Sound panel — volume slider, output selector, input selector
[ ] Build Network panel — wifi list, connect/disconnect, status
[ ] Build Notifications panel — app notification toggles, do not disturb
[ ] Build Privacy panel — app permissions, camera/mic access list
[ ] Update Power panel — keep manual option, show current auto mode status
[ ] Update Zones panel — compatibility layer status, per-app overrides later
[ ] Update AI & HIVE panel — live status of NPU, sentinel, router
[ ] Update About panel — Luminos version, hardware info, kernel version
```

---

## PHASE 5.3 — Wallpaper System
# Two completely different wallpaper types — both supported

### Type 1: Video Wallpaper
```
What it is:
  A video file that loops on the desktop background
  No interaction — just plays
  Good for: cinematic loops, 4K nature, abstract motion

Tech:
  mpvpaper handles playback
  Loops seamlessly
  Pauses automatically when on battery to save power
  Resumes when plugged in

Supported formats: mp4, webm, gif
```

### Type 2: Live Wallpaper
```
What it is:
  A wallpaper that REACTS to what you are doing
  Feels alive — not just playing

Behavior:
  Mouse moves    → elements follow, ripple, shift in response
  Key pressed    → pulse or burst effect near cursor
  Typing fast    → more energy, faster movement
  Idle (30 sec)  → slows down, breathes gently
  Idle (2 min)   → goes very minimal, almost still

Examples of live wallpaper types to support:
  Particle field — dots connected by lines, follow mouse
  Aurora — flowing light waves that respond to movement
  Geometric — shapes that shift and react to input
  Water — ripple effect on mouse click/move

Tech:
  Custom renderer or existing tools like shadertoy shaders via glsl-shaders
  Runs on GPU (light workload — this is fine for desktop compositor)
  Falls back to static if GPU is under heavy load (gaming)
  Automatically suspends during gaming — never compete with games

Settings for live wallpaper:
  Intensity slider: Low / Medium / High (how reactive it is)
  That is all — nothing else
```

### Wallpaper Settings Panel (Simple — No Exceptions)
```
Layout:        Grid of thumbnails — 3 columns
Thumbnail:     Fit grid, maintain aspect ratio, video shows animated preview
Click:         Applies immediately — no confirm needed
Add own:       Single "+" card at end of grid, opens file picker
Filter tabs:   Static | Video | Live  (3 tabs at top, that is all)
Live options:  Intensity slider only (Low/Medium/High)
No:            Blur sliders, stretch modes, per-monitor, fit/fill options
```

---

## PHASE 5.3b — NPU Abstraction Interface
# Build this before Phase 5.4 hardware testing

```
[ ] Create src/npu/npu_interface.py with these methods:
      npu_interface.run_sentinel(data) → classification result
      npu_interface.run_router(exe_data) → layer decision
      npu_interface.status() → NPU available / busy / unavailable
      npu_interface.queue(task) → adds task to NPU queue

[ ] Queue logic:
      Sentinel runs continuously at low priority
      Router request comes in → pause sentinel → run router → resume sentinel
      If NPU busy for more than 5 seconds → log warning, keep waiting

[ ] Driver handling inside npu_interface.py only:
      Detect xdna-driver is loaded
      Load ONNX runtime for XDNA
      Handle driver errors gracefully — log, do not crash OS

[ ] Nothing outside npu_interface.py ever touches NPU directly
[ ] Sentinel imports npu_interface — does not call XDNA directly
[ ] Router imports npu_interface — does not call XDNA directly
[ ] Test interface with mock NPU before real hardware testing
```

---

## PHASE 5.4 — ASUS ROG Hardware Integration

### Keyboard
```
[x] Backlight brightness control (Fn keys working)
[x] Backlight auto-off on idle — KDE KCM + Smart power daemon
[x] Per-key RGB via asusctl — basic color setting in KDE KCM
[x] Aura sync profiles (Solid / Breathing / Reactive / 4 more) — 7 modes total
[x] Fn key combinations all working (media keys, volume, brightness)
[x] Keyboard setting in KDE System Settings (kcm_luminos_keyboard.so installed)
```

### Touchpad
```
[x] 2-finger scroll — natural direction, libinput quirks applied (BUG-045)
[x] Tap to click enabled by default
[x] Palm rejection working (AttrPalmSizeThreshold=14)
[ ] 3-finger swipe left/right → switch workspace (KDE default gesture — verify)
[ ] 3-finger swipe up → show open windows overview
[ ] Pinch to zoom in supported apps
```

### Display
```
[x] 120Hz enabled — Samsung eDP-2 2880×1800 @ 120Hz
[x] Adaptive sync (VRR) enabled — Automatic policy (BUG-051 fix)
[x] Brightness control via Fn keys working
[ ] Smart refresh rate auto-switching (60Hz battery / 120Hz performance)
[ ] External display hotplug detection and auto-configure
[ ] User display lock setting in Settings (Always 60 / Always 120 / Auto)
```

### Battery & Charging
```
[x] Battery percentage in top bar visible
[x] Charging indicator icon changes when plugged in
[x] Battery charge limit via asusctl (supported by asusctl rog-bios)
[ ] Charge limit UI in Settings > Power (60% / 80% / 100%)
[ ] Low battery notification at 20%
[ ] Critical battery notification at 10%
[ ] Auto suspend at 5%
```

### Audio
```
[x] ROG audio device detected and set as default
[x] Headphone jack hotplug — auto switch output
[x] Microphone working
[x] Volume keys working
[x] Mute key working
[ ] Audio output switcher in quick settings panel
```

---

## PHASE 5.5 — Power & Thermal Wiring
```
[x] Unplug detected → switch to battery mode immediately (luminos-power v3.1)
[x] Plug in detected → AC mode immediately (EPP=power on AC)
[x] Fan curves configured via asusctl (luminos-power v3.1 early ramp, 50°C target):
      30C  → 0%    (silent)
      40C  → 40%   (early ramp to prevent temp climb)
      45C  → 62%
      50C  → 80%
      60C  → 95%
      70C+ → 100%
[x] All three sensors monitored: CPU temp via /sys, ACPI thermal zones
[x] Thermal throttle prevention — EPP-based governor, hysteresis (BUG-048 fix)
[x] supergfxctl Hybrid confirmed on every boot (luminos-power startup assertion)
[x] Beast mode — explicit EPP=performance when triggered (AC only)
[ ] Video wallpaper pauses on battery, resumes on AC
[ ] Live wallpaper suspends during gaming
[ ] Battery charge limit applied on every boot (reads user setting)
[ ] Smart refresh rate respects power mode (60Hz battery / 120Hz performance)
```

---

## PHASE 5.6 — Quick Settings Panel
```
[ ] Opens when clicking top bar right side
[ ] Frosted glass dropdown — 320px wide, 12px radius
[ ] Contents:
      Wifi toggle + tap to see network list
      Bluetooth toggle
      Volume slider with icon
      Brightness slider with icon
      Battery percentage + status (charging/discharging)
      Current power mode (Battery / Performance) — read only
      GPU mode indicator — always shows "Hybrid" — read only
      Do Not Disturb toggle
      Night light toggle
      Settings button → opens full settings app
[ ] Keyboard shortcut to open: Super + S or click tray
```

---

## PHASE 5.7 — Notifications System
```
[ ] Toast notifications top right — frosted glass pill, 5 sec auto dismiss
[ ] Notification center — click bell icon to open, shows history
[ ] Per-app notification toggles in Settings > Notifications
[ ] Do Not Disturb — suppresses all toasts, still logs to center
[ ] System notifications:
      Battery low (20%, 10%, 5%)
      Wifi connected / disconnected
      Bluetooth device connected / disconnected
      App failed to launch (compatibility layer error)
      Sentinel flagged something suspicious
      Luminos update available (future)
```

---

## PHASE 5.8 — App Launcher
```
[ ] Opens with Super key
[ ] Frosted glass overlay — full screen or centered panel
[ ] Search bar — type instantly filters
[ ] Shows all installed apps with icons
[ ] Includes Windows apps that have been run (pulled from router cache)
[ ] Sections: Recents (last 8) / All Apps / Windows Apps / Games
[ ] Keyboard navigation: arrows + Enter to launch, ESC to close
[ ] App icons extracted from .exe automatically (stored in cache)
```

---

## PHASE 5.9 — First Run Experience
```
[ ] Screen 1: Welcome — Luminos logo, "Your new OS." button to continue
[ ] Screen 2: Create user — name input, password (or skip)
[ ] Screen 3: Pick wallpaper — default set shown as grid
[ ] Screen 4: One liner tour:
      "Your Windows apps open automatically in the right layer."
      "AI runs underneath — not on top."
      "You're ready."
[ ] Launch button → goes to desktop
[ ] Skip button on every screen
[ ] Never shows again after first completion
[ ] Accent color stays blue — no picker in first run (keep it simple)
```

---

## PHASE 5.10 — Compatibility Stack Polish
```
[ ] Test with real Windows apps:
      A game via Proton (Steam)
      A .NET app via Wine
      A DirectX 12 game
      An anticheat game (KVM path)
[ ] Error handling — user sees clear message if app fails, not a crash
[ ] Retry logic — if Layer 1 fails, offer Layer 2 automatically
[ ] Per-app layer override — user can force a specific layer
[ ] App icon extracted from .exe shown in dock and launcher
[ ] Progress shown while router analyzes (spinner, under 3 seconds)
[ ] Subtle badge on app window: "Windows app" indicator
[ ] Router result always logged for debugging
```

---

## PHASE 5.11 — Security & Privacy Polish
```
[ ] Sentinel logs visible in Settings > Privacy
[ ] Clear log button
[ ] Toast notification when Sentinel flags something
[ ] App permissions UI — camera, mic, location per app
[ ] Network activity monitor — which apps are calling home
[ ] "Zero telemetry. Always." shown in Settings > Privacy
[ ] No outbound connections from Luminos OS itself — ever
```

---

## PHASE 5.12 — Performance & Stability
```
[ ] Idle RAM target: under 1.5GB
[ ] Startup time target: under 10 seconds to desktop
[ ] All daemons have restart policies in systemd
[ ] Crash recovery — Hyprland crash restores session
[ ] Log rotation — /var/log/luminos/* capped at 100MB total
[ ] llama.cpp unloads model when router idle for 5 minutes
[ ] Live wallpaper automatically suspends during gaming
[ ] Memory audit report — document what is running at idle
```

---

## THINGS TO DECIDE BEFORE PHASE 6

```
[ ] Default wallpaper — what does the Luminos default wallpaper look like?
[ ] Pre-installed apps — browser, file manager, terminal, text editor?
[ ] Luminos logo — is there a final logo?
[ ] Version number — what is v1.0?
[ ] Install process — how does a user install from ISO?
[ ] Update system — how does Luminos update after install?
[ ] App store — do we have one or just pacman/AUR exposed simply?
```

---

## PHASE SUMMARY TABLE

| Phase | What | Priority |
|-------|------|----------|
| 5.1 | UI/UX redesign | 🔴 First |
| 5.2 | Settings app redesign | 🔴 First |
| 5.3 | Wallpaper — video + live (reactive) | 🔴 First |
| 5.4 | ASUS hardware — keyboard, touchpad, display, battery | 🔴 Critical |
| 5.5 | Power and thermal wiring | 🔴 Critical |
| 5.6 | Quick settings panel | 🟠 High |
| 5.7 | Notifications | 🟠 High |
| 5.8 | App launcher | 🟠 High |
| 5.9 | First run experience | 🟠 High |
| 5.10 | Compatibility stack polish | 🟡 Medium |
| 5.11 | Security and privacy polish | 🟡 Medium |
| 5.12 | Performance and stability | 🟡 Medium |
| 6 | ISO build | 🟢 Last |
