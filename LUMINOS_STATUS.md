# LUMINOS_STATUS.md — Current State of All Components

> Updated by every agent after every task. If you're an agent, update this before committing.
> Format: component name, status emoji, last updated, brief notes.

**Status key:** ✅ Working | 🔧 In Progress | ❌ Broken | 📋 Not Started | ⚠️ Working with caveats

---

## Core System

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Arch Linux base | ✅ Working | — | Triple boot on G14 alongside Windows + default Arch |
| Hyprland 0.54.3 | 🚫 Uninstalled | 2026-04-19 | [CHANGE: gemini-cli | 2026-04-19] Fully uninstalled per Decision 12. |
| swww-daemon | 🚫 Uninstalled | 2026-04-19 | [CHANGE: gemini-cli | 2026-04-19] Fully uninstalled. |
| Triple boot | ✅ Working | — | GRUB boots all three. GPT mismatch warning on boot (cosmetic, auto-corrects) |
| KDE Plasma (Wayland) | ✅ Working (6.6.4) | 2026-04-19 | [CHANGE: gemini-cli | 2026-04-19] Installed, SDDM enabled, and verified working. |

---

## GUI Components

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| HyprPanel (bar+dock) | 🚫 Uninstalled | 2026-04-19 | [CHANGE: gemini-cli | 2026-04-19] Fully uninstalled. |
| GTK4 UI (all) | 🚫 Uninstalled | 2026-04-19 | [CHANGE: gemini-cli | 2026-04-19] GTK4 UI stack retired; packages removed where safe. |
| KDE Plasma desktop | ✅ Working | 2026-04-20 | [CHANGE: gemini-cli | 2026-04-20] Fixed bottom dock (Panel 4) opacity and floating state to match top bar (Panel 2). |
| SDDM login screen | 🔧 In Progress | 2026-04-19 | [CHANGE: gemini-cli | 2026-04-19] SDDM enabled. Replaced greetd. Needs Luminos theme. |
| Settings app | 📋 Not Started | — | Qt/QML + Go backend. |
| Zone indicator widget | 📋 Not Started | — | KDE Plasma widget dot on window corner (blue/orange/red/none per zone). |
| App launcher | ✅ Working | 2026-04-20 | [CHANGE: gemini-cli | 2026-04-20] Set launcher to Application Dashboard (kickerdash) with view-app-grid icon. |
| KDE config persistence | ✅ Working | 2026-04-20 | [CHANGE: claude-code | 2026-04-20] kdeglobals, kwinrc, plasmashellrc, appletsrc saved to repo. Auto-apply script runs on login via KDE autostart. |

---

## Environment & Tooling

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| asusctl + supergfxctl | ✅ Working | 2026-04-17 | asusd + supergfxd enabled; mode confirmed Hybrid |
| greetd | 🚫 Retired | 2026-04-19 | Replaced by SDDM with KDE Plasma. |
| MemPalace | ✅ Working | 2026-04-19 | Fixed: Python 3.12 venv at ~/.mempalace-venv, chromadb 0.6.3, mempalace 3.3.1. MCP registered. Activate venv before use. |
| code-review-graph | ✅ Working | 2026-04-19 | MCP registered, graph built (2593 nodes, 17829 edges, 189 files) |
| nm-applet | ✅ Working | 2026-04-18 | Will be replaced by KDE plasma-nm |
| pipewire-pulse | ✅ Working | 2026-04-18 | Compatible with KDE audio (plasma-pa) |

---

## Boot & System Issues

| Issue | Status | Notes |
|-------|--------|-------|
| GPT mismatch warning | ⚠️ Known/cosmetic | Auto-corrects on boot. Not urgent. |
| greetd GTK4 gl module error | 🚫 Retired/Resolved | greetd replaced by SDDM. GTK4 retired entirely. |

---

## Stack Migration Status

| Migration Task | Status | Notes |
|----------------|--------|-------|
| Python bar → HyprPanel | ✅ | Complete — both now retired (see below) |
| Python dock → HyprPanel taskbar | ✅ | Complete — both now retired |
| AGS bar → HyprPanel | ✅ | Complete — both now retired |
| Waybar → HyprPanel | ✅ | Complete — both now retired |
| Hyprland+GTK4+HyprPanel → KDE Plasma | ✅ | [CHANGE: gemini-cli | 2026-04-19] Installed KDE and SDDM. Next: Theme and widgets. |
| Python settings → Qt/QML + Go | 📋 | After KDE install |
| Python login → SDDM theme | 🔧 | [CHANGE: gemini-cli | 2026-04-19] In progress. |
| Go daemons for NPU/AI/compat | 🔧 | Phase 1 complete. Phase 2 (ONNX classifier), Phase 3 (NPU), Phase 4 (HIVE) pending. |

---

## Retired / Uninstalled Components

| Component | Status | Date |
|-----------|--------|------|
| Python bar (bar_app.py) | 🚫 Uninstalled | 2026-04-19 |
| Python dock (dock_app.py) | 🚫 Uninstalled | 2026-04-19 |
| AGS bar (Bar.tsx) | 🚫 Uninstalled | 2026-04-19 |
| Waybar | 🚫 Uninstalled | 2026-04-19 |
| HyprPanel | 🚫 Uninstalled | 2026-04-19 |
| Hyprland | 🚫 Uninstalled | 2026-04-19 |
| GTK4 / PyGObject / Python UI | 🚫 Retired/Cleaned | 2026-04-19 |
| gtk4-layer-shell | 🚫 Retired/Cleaned | 2026-04-19 |
| greetd / hyprlock / swww | 🚫 Uninstalled | 2026-04-19 |
| dunst | 🚫 Uninstalled | 2026-04-19 |
| wofi / luminos-launcher-toggle | 🚫 Uninstalled | 2026-04-19 |

---

## Daemon Development

Architecture locked per Decision 13 (Go/Python split, April 2026).
See docs/DAEMON_ARCHITECTURE.md for full technical blueprint.

| Component | Status | Notes |
|-----------|--------|-------|
| Architecture design | ✅ Done | Decision 13 — Go/Python split. Unix sockets for IPC. |
| Phase 1 — Go foundation | ✅ Verified and running in production | [CHANGE: gemini-cli | 2026-04-20] All 4 Go daemons (ai, power, sentinel, router) verified and responding. |
| Phase 2 — Compat Router + AI | ✅ Done | [CHANGE: gemini-cli | 2026-04-20] Rule-based Python classifier (Phase 3 AI stub) wired to Go router. .exe association and Wine launcher working. |
| Phase 3 — NPU + Sentinel ML | ⚠️ Partial | [CHANGE: gemini-cli | 2026-04-21] NPU persistence fixed via udev/systemd. VitisAI EP missing in ONNX Runtime (needs specific AMD wheels). NPU confirmed active via xrt-smi. |
| Phase 4 — HIVE + llama.cpp | 📋 Planned | llama-cpp-python server. Go model manager. Nexus/Bolt/Nova/Eye agents. |

---

## Active Bugs

| Bug | Status |
|-----|--------|
| GPT mismatch warning | ⚠️ Known/cosmetic |

---

## Agent Activity Log

| Date | Agent | Task | Outcome |
|------|-------|------|---------|
| 2026-04-21 | gemini-cli | Fix NPU persistence & verify VitisAI EP | ✅ /dev/accel0 persistent; ❌ VitisAI EP missing |
| 2026-04-20 | claude-code | Fix socket PermissionError in bar/dock | ✅ os.access() fix applied |
| 2026-04-12 | claude-code | Autostart bar + dock via exec-once | ✅ Working with env vars |
| 2026-04-12 | claude-chat | Debug Hyprland 0.54.3 windowrule syntax | ✅ Migrated to block-style |
| 2026-04-17 | claude-code | Replace Python bar/dock with Waybar | ✅ Waybar working |
| 2026-04-18 | claude-code | Replace Waybar with HyprPanel | ✅ HyprPanel verified after reboot |
| 2026-04-18 | claude-code | HyprPanel floating bar + CSS + systray | ✅ Grouped wifi/vol/bat |
| 2026-04-19 | claude-chat | Design multi-agent workflow | ✅ AGENTS.md, WORKFLOW.md, PROMPTS.md |
| 2026-04-19 | claude-code | Full docs reorganization | ✅ Merged/archived/deleted obsolete docs |
| 2026-04-19 | antigravity | Fix MemPalace Python 3.14 incompatibility | ✅ pyenv + Python 3.12 venv, chromadb 0.6.3, mempalace 3.3.1 |
| 2026-04-19 | antigravity | Fix HyprPanel taskbar input | 🔧 xray=true layerrule, removed orphaned plugin config — needs reboot verify |
| 2026-04-19 | gemini-cli | Fix HyprPanel input & window buttons | ✅ Removed hyprbars, added interactivity layerrule, disabled kitty CSD |
| 2026-04-19 | gemini-cli | Fix HyprPanel crash & Aura backlight | ✅ Fixed config.json invalid schema keys, added asusctl exec-once |
| 2026-04-19 | gemini-cli | Fix HyprPanel taskbar click passthrough | ✅ Corrected layerrule syntax, ignore_alpha 0.5, and enabled xray on |
| 2026-04-19 | gemini-cli | Uninstall Hyprland and GTK4 UI | ✅ Removed packages and configs per Decision 12 |
| 2026-04-20 | claude-code | Save KDE config to repo + autostart | ✅ Config files saved, apply-kde-config.sh created, wallpaper applied |
| 2026-04-20 | claude-code | Daemon architecture planning | ✅ Decision 13 written, DAEMON_ARCHITECTURE.md created, all docs updated |
| 2026-04-20 | claude-code | Phase 1 Go daemon foundation | ✅ luminos-ai, luminos-power, luminos-sentinel, luminos-router — all compile + go vet clean. Binaries: 4.3–4.7MB each. |
| 2026-04-20 | gemini-cli | Fix luminos-power asusctl syntax | ✅ Updated to asusctl 6.3.6 'profile set' syntax, consolidated fan logic. |
| 2026-04-20 | gemini-cli | Phase 2 Compatibility Router | ✅ Python rule-based classifier, Go router integration, .exe association. |
| 2026-04-20 | gemini-cli | Enable AMD XDNA NPU | ✅ Kernel check, XRT stack install, render group, IOMMU GRUB config. |

---

## Historical Notes (from STATE.md)

The following is preserved from the original `docs/STATE.md` (last updated 2026-03-21) which tracked
development during the Ubuntu/Firebase Studio era. This code was written on a Windows 11 dev machine
before the project migrated to Arch Linux on the actual ROG G14 hardware.

### Pre-Migration Development Summary (March 2026)
- All phases 0–9 were completed on Ubuntu LTS base (757/757 tests passing)
- ISO build scripts were created for Ubuntu (now obsolete — Arch uses archiso)
- Development machine was Windows 11 with Firebase Studio (browser IDE)
- Architecture decisions at that time used Ubuntu LTS as base (since changed to Arch)
- AI daemon, classifier, sentinel, zone2/zone3, GPU manager, power manager, compositor,
  theme, bar, dock, launcher, quick settings, notifications, wallpaper, lock screen,
  store, settings, first run wizard, and wine/proton integration were all built in Python
- All Python GUI code is now deprecated in favor of Go + GTK4 + libadwaita (settings/login)
  and HyprPanel (bar/dock)

### Key Architecture Notes from Ubuntu Era
- AI inference: llama.cpp direct (no Ollama), CUDA + Vulkan + ONNX backends
- IPC: Unix socket at /run/luminos/ai.sock
- Zone 3 VM: Firecracker microVM (not QEMU)
- NPU: ONNX Runtime VitisAI provider (untested on real hardware)
- All 757 tests were pure Python headless tests — no display server required

---

## Legend
📋 Not started | 🔧 In Progress | ✅ Done | ❌ Blocked | ⚠️ Partial
 ❌ Blocked | ⚠️ Partial
