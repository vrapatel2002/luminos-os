# LUMINOS OS — PROJECT SCOPE DOCUMENT
# Version: 2.0 — Arch Decision Locked
# This file is the single source of truth for all agents (Claude Code, Antigravity, etc.)
# EVERY code change, feature, or decision MUST align with this document.
# If something contradicts this document, this document wins.
# For WHY we made these decisions, read: LUMINOS_DECISIONS.md

---

## ONE LINE MISSION
A privacy-first Windows alternative for the ASUS ROG G14 that runs everything
Windows can, but smarter, cleaner, and with AI woven into its core.

---

## WHAT THIS IS
- A complete desktop operating system
- Primary goal: run ALL Windows apps and games automatically
- Secondary goal: AI native at every layer
- Target user: someone who wants to leave Windows but not lose anything

## WHAT THIS IS NOT
- Not a Linux distro with a pretty face
- Not Ubuntu with Hyprland slapped on
- Not an AI assistant OS (AI is infrastructure, not the product)
- Not complicated — no manual tuning required from the user ever

---

## TARGET HARDWARE (Locked — Build For This, Nothing Else)
```
Device:  ASUS ROG G14
CPU:     AMD Ryzen AI (XDNA NPU built in, 16 TFLOPS)
GPU:     NVIDIA RTX 4050 6GB (dGPU) + AMD RDNA3 (iGPU)
RAM:     16GB
Storage: NVMe SSD
```

---

## BASE OS (LOCKED — DO NOT CHANGE)
```
Base:          Arch Linux
Compositor:    Hyprland
Login Manager: greetd (custom Luminos theme)
Shell:         bash / zsh
Package Mgr:   pacman + AUR (yay or paru)
GPU Control:   supergfxctl (always hybrid, never changed)
Fan/Power:     asusctl
AI Runtime:    llama.cpp via Unix socket daemon
Security:      Sentinel on NPU
```

## TECH STACK (LOCKED — April 2026)
```
Bar + Dock:              AGS (Astal) + JavaScript + CSS
Settings + Login Screen: Go + GTK4 + libadwaita + CSS
AI Daemon / NPU / Compat Router: Go
Window Manager:          Hyprland (locked forever)
Drawing Engine:          GTK4 (locked forever)
Styling:                 CSS + libadwaita
```

### Legacy / Deprecated
```
Python GTK4:  DEPRECATED for all UI work. Existing Python bar/dock code
              is being migrated to AGS/JS. No new Python UI code allowed.
              Python remains acceptable for build scripts and tooling only.
```

### Why Arch (Short Version)
- No Casper, no hardcoded usernames, no Ubuntu bloat
- Hyprland, asusctl, supergfxctl all native in AUR
- Rolling release — NPU drivers, NVIDIA, ML packages always current
- SteamOS (best gaming Linux) is also Arch-based
- Full reasoning in LUMINOS_DECISIONS.md

### What Was Abandoned
- Ubuntu 24.04 base — caused 6+ boot errors, fought the project at every step
- Full reasoning in LUMINOS_DECISIONS.md

---

## FEATURE 1 — WINDOWS COMPATIBILITY STACK (Highest Priority)

### Three Layers (In Order Of Preference)
```
Layer 1: Proton / Wine / Lutris
  Use when:    App works with these tools
  Performance: Near native, no VM overhead
  Best for:    Most Windows games and apps

Layer 2: Firecracker microVM
  Use when:    Wine/Proton cannot handle the app
  Performance: Lightweight VM, low overhead
  Best for:    Apps needing Windows APIs Wine doesn't support

Layer 3: Full KVM/QEMU VM
  Use when:    Nothing else works
  Performance: Full VM, GPU passthrough via RTX 4050
  Best for:    Anticheat games, enterprise apps, absolute last resort
```

### The Compatibility Router
```
What it is:
  Sub 1GB quantized AI model (Phi-3-mini Q4 or smaller)
  Runs on CPU — Ryzen AI at 16 TFLOPS handles this easily
  NOT on NPU, NOT on GPU

What it does:
  User double clicks any .exe
  Router analyzes it in under 3 seconds
  Decides which layer automatically
  User never chooses manually — ever

What it analyzes:
  PE headers of the .exe
  Windows APIs it calls
  DirectX version required
  Anticheat presence (EAC, BattlEye, etc.)
  Kernel-level access requirements
  .NET / Visual C++ runtime dependencies

Decision logic:
  Rule-based handles 80% of cases (fast, deterministic)
  AI model handles remaining 20% edge cases
  AI never overrides rules — rules are always guardrails
  Results cached per app — analysis runs once per new app

Runs as:
  Lightweight daemon
  Communicates via Unix socket
```

### AI Native In Each Layer
```
Proton layer:
  Monitors translation quality
  Detects and patches common glitches on the fly

Firecracker layer:
  Manages microVM resource allocation dynamically
  Suspends VM when app backgrounded

KVM/QEMU layer:
  Decides GPU passthrough allocation in real time
  Auto-saves VM state when user switches tasks
```

---

## FEATURE 2 — POWER MANAGEMENT (Simple By Design)

### Two Modes Only — Both Automatic
```
UNPLUGGED → Max Battery (triggers automatically on unplug)
  CPU:      Capped to efficient range
  GPU:      AMD RDNA3 iGPU only
  NVIDIA:   Powered down completely
  Tasks:    Background tasks minimized
  Fan:      Quiet/efficient curve

PLUGGED IN → Performance (triggers automatically on plug in)
  CPU:      Full power
  GPU:      Always Hybrid (AMD + NVIDIA both active)
  Tasks:    Normal
  Fan:      Thermal-based (see Feature 3)
```

### Hard Rules For Power Code
```
NEVER expose manual power profile switching to user
NEVER allow iGPU-only or dGPU-only while plugged in
NEVER require user action — detect plug state and switch automatically
Settings app MUST NOT have a power profiles dropdown
```

---

## FEATURE 3 — GPU (Always Hybrid, Always)

### The Rule (Never Break This)
```
supergfxctl mode = Hybrid
Set at install, never changed by OS or user
```

### What Hybrid Means
```
AMD RDNA3:       Desktop, UI, Hyprland, video, light tasks
NVIDIA RTX 4050: Games, AI inference, rendering, GPU-heavy tasks
OS decides routing automatically — user never sees a GPU switcher
```

### What To Never Do
```
NEVER set supergfxctl to Integrated
NEVER set supergfxctl to NVidia only
NEVER expose GPU mode switching anywhere in UI
```

---

## FEATURE 4 — THERMAL & FAN MANAGEMENT

### Fan Curve Via asusctl
```
Below 60C  → Silent, minimal fan
60C-75C    → Gradual ramp up
75C-85C    → Aggressive cooling
Above 85C  → Max fan + throttle CPU/GPU to protect hardware
```

### Thermal Rules For Code
```
Monitor all three: CPU temp, GPU temp, battery temp
If any hits 85C: throttle before hardware does it itself
Never let thermal throttle happen during gaming
If temps spike: AI Router delays heavy tasks until temps drop
```

---

## FEATURE 5 — AI LAYER (Infrastructure, Not Product)

### Hardware Assignment (Locked — No Fallbacks, No Exceptions)
```
CPU (AMD x86 general cores):
  OS, apps, file manager, terminal, settings, everything normal
  Kept FREE for actual user work — this is the goal
  NEVER used for AI inference
  NEVER used as fallback for NPU tasks

iGPU (AMD RDNA3 — integrated):
  Hyprland compositor — all desktop rendering
  UI animations, dock, bar, panels, settings
  Video playback
  Live wallpaper (light shader workload)
  Everything visual that is not a game or heavy task
  Frees the NVIDIA for real work

NPU (AMD XDNA — 16 TFLOPS dedicated AI cores):
  Sentinel security — always on, continuous, low intensity
  Compatibility Router — burst on demand, then idle
  Both share NPU via queue:
    Sentinel runs continuously at low priority
    Router needs NPU → Sentinel pauses 2-3 seconds
    Router finishes → Sentinel resumes immediately
  If NPU unavailable: Router and Sentinel WAIT
  NEVER reroute to CPU or GPU — no fallbacks ever

dGPU (NVIDIA RTX 4050 6GB):
  Games
  HIVE agents (Nexus, Bolt, Nova, Eye)
  Heavy AI inference
  Coding and dev GPU tasks
  Video encoding
  Anything iGPU or NPU cannot handle
  Only wakes up for real heavy tasks — idle otherwise
```

### NPU Abstraction Layer (Implementation Approach)
```
Why:
  XDNA driver on Linux is still maturing (2025)
  Direct NPU calls scattered everywhere = hard to fix if driver changes
  Abstract it = fix one place, everything works

How:
  All NPU calls go through a single interface: npu_interface.py
  Sentinel calls: npu_interface.run_sentinel(data)
  Router calls:   npu_interface.run_router(exe_data)
  Interface handles: driver loading, ONNX runtime, memory management
  If driver API changes: update npu_interface.py only
  Nothing else in the codebase knows how the NPU works internally

Test in Phase 5.4 on actual G14 hardware before depending on it
```

### Sentinel Security (Core — Always Running)
```
Runs on NPU, passive, always on
Model: SmolLM2-360M or DistilBERT (fits NPU budget)
Monitors: All system calls
Action: Classifies normal / suspicious / block
Wine/Proton apps: Cannot touch real home directory
Firecracker apps: Fully isolated by default
```

### HIVE Agents (Optional — Not Required For OS To Function)
```
Nexus  → Planning and coordination
Bolt   → Code and automation
Nova   → Research and knowledge
Eye    → Vision and screen understanding
All local, no cloud, no API calls
```

---

## FEATURE 6 — UI & DESKTOP

### Login Screen (To Be Built)
```
Big clock center screen
Date below clock
Press Enter → password field if account has password
Press Enter → straight to desktop if no password
No username list visible
Dark, minimal, clean
```

### Settings App
```
Keep:   Appearance, Wallpaper, Display, Power, Sound, Network, Privacy, About
Add:    Zones (compatibility layer management), AI and HIVE
Remove: Any Ubuntu/Canonical specific settings
```

### Desktop
```
Hyprland compositor
macOS-inspired, not a copy
Center bottom dock
Top bar: clock, system tray, status
No Windows-style taskbar
```

---

## ACTIVE BUGS (Fix Before Any New Features)

### Hyprland Config
```
decoration:drop_shadow deprecated     → Move to shadow {} block
decoration:shadow_range deprecated    → Move to shadow {} block
decoration:shadow_render_power        → Move to shadow {} block
decoration:col.shadow deprecated      → Move to shadow {} block
```

### UI
```
Login screen missing
Dock alignment issues
Settings accent color swatches not rendering
Floating dock not centered properly
```

---

## RULES FOR ALL AGENTS (Claude Code, Antigravity, etc.)

```
1.  Read this document fully before writing any code
2.  Read LUMINOS_DECISIONS.md to understand why things are the way they are
3.  Base OS is Arch Linux — never write Ubuntu/Debian specific code
4.  Use pacman/AUR — never apt, never snap, never flatpak unless Sam says so
5.  Never expose manual GPU switching to user
6.  Never add more than two power modes
7.  Compatibility router runs on CPU — never move it to GPU or NPU
8.  AI is infrastructure — never make it the visible product
9.  supergfxctl must always be Hybrid — never change this
10. Fix bugs in ACTIVE BUGS before adding new features
11. If a decision is not in this document — stop and ask Sam
12. No Ubuntu branding, tools, or patterns anywhere in the codebase
13. Every feature must be automatic — never require manual user action
14. When in doubt: simpler is better
```

---

## THE PITCH (What Makes Luminos Different)

| Feature | Windows | macOS | Ubuntu | SteamOS | Luminos |
|---------|---------|-------|--------|---------|---------|
| Runs Windows apps | YES | NO | Partial | Games only | YES auto |
| AI routes compatibility | NO | NO | NO | NO | YES |
| Always hybrid GPU | NO | NO | NO | NO | YES |
| Privacy by default | NO | Partial | Partial | Partial | YES |
| Smart thermals | Partial | YES | NO | Partial | YES |
| No manual tuning | NO | YES | NO | Partial | YES |
| Gaming | YES | NO | Partial | YES | YES |
| Open source | NO | NO | YES | YES | YES |
| ROG hardware native | YES | NO | NO | NO | YES |
