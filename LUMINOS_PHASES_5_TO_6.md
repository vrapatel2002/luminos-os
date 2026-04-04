# LUMINOS OS — PHASES 5.x TO 6 ROADMAP
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
[ ] Backlight brightness control (Fn keys working)
[ ] Backlight auto-off on idle — default 30 seconds, user can change
[ ] Per-key RGB via asusctl — basic color setting in Settings
[ ] Aura sync profiles (simple: Solid / Breathing / Reactive)
[ ] Reactive mode: keys light up brighter when pressed, fade out
[ ] Fn key combinations all working (media keys, volume, brightness)
[ ] Keyboard setting in Settings app:
      - Brightness slider
      - On/Off toggle
      - Effect selector (Solid / Breathing / Reactive)
      - Color picker (uses accent color by default)
```

### Touchpad
```
[ ] 3-finger swipe left/right → switch workspace
[ ] 3-finger swipe up → show open windows overview
[ ] 2-finger scroll → natural direction (content moves with fingers)
[ ] Pinch to zoom in supported apps
[ ] Tap to click enabled by default
[ ] Palm rejection working
```

### Display
```
Smart refresh rate (not manual toggle everywhere):
[ ] Default: 60Hz — desktop, light use, battery mode
[ ] Auto switch to 120Hz when: game launches, video plays full screen
[ ] Auto switch back to 60Hz when: game/video closes
[ ] User can LOCK it in Display settings:
      - "Auto (recommended)" — smart switching as above
      - "Always 60Hz" — saves battery
      - "Always 120Hz" — user preference
[ ] G14 max: 120Hz — do not expose or attempt 144Hz or 165Hz
[ ] Adaptive sync enabled (FreeSync) when supported
[ ] Brightness control via Fn keys working
[ ] External display hotplug detection and auto-configure
```

### Battery & Charging
```
[ ] Battery charge limit setting in Settings > Power:
      60% — maximum battery longevity (travel, always plugged in)
      80% — balanced (recommended default)
      100% — full charge (when you need it)
[ ] Battery percentage in top bar always visible
[ ] Low battery notification at 20%
[ ] Critical battery notification at 10%
[ ] Auto suspend at 5% (configurable — user can turn off)
[ ] Charging indicator icon changes when plugged in
```

### Audio
```
[ ] ROG audio device detected and set as default
[ ] Headphone jack hotplug — auto switch output
[ ] Microphone working
[ ] Volume keys working
[ ] Mute key working (shows muted indicator in top bar)
[ ] Audio output switcher in quick settings
```

---

## PHASE 5.5 — Power & Thermal Wiring
```
[ ] Unplug detected → switch to battery mode immediately (no delay)
[ ] Plug in detected → switch to performance mode immediately (no delay)
[ ] Video wallpaper pauses on battery, resumes on AC
[ ] Live wallpaper suspends during gaming always regardless of power mode
[ ] Fan curves configured via asusctl:
      Below 60C  → silent
      60C-75C    → gradual ramp
      75C-85C    → aggressive
      Above 85C  → max fan + CPU/GPU throttle
[ ] All three sensors monitored: CPU temp, GPU temp, battery temp
[ ] Thermal throttle never happens from hardware — OS does it first at 85C
[ ] supergfxctl Hybrid confirmed on every boot (startup assertion)
[ ] Battery charge limit applied on every boot (reads user setting)
[ ] Smart refresh rate respects power mode:
      Battery mode  → 60Hz always (overrides auto)
      Performance   → smart switching active
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
