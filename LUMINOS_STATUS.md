# LUMINOS_STATUS.md — Current State of All Components

> Updated by every agent after every task. If you're an agent, update this before committing.
> Format: component name, status emoji, last updated, brief notes.

**Status key:** ✅ Working | 🔧 In Progress | ❌ Broken | 📋 Not Started | ⚠️ Working with caveats

---

## Core System

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Arch Linux base | ✅ Working | — | Triple boot on G14 alongside Windows + default Arch |
| Hyprland 0.54.3 | 🚫 Retired | 2026-04-19 | Permanently retired. Replaced by KDE Plasma. See Decision 12. |
| swww-daemon | 🚫 Retired | 2026-04-19 | Replaced by KDE wallpaper manager. |
| Triple boot | ✅ Working | — | GRUB boots all three. GPT mismatch warning on boot (cosmetic, auto-corrects) |
| KDE Plasma (Wayland) | 📋 Next Task | 2026-04-19 | Install: plasma-desktop plasma-wayland-session sddm kde-gtk-config |

---

## GUI Components

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| HyprPanel (bar+dock) | 🚫 Retired | 2026-04-19 | Permanently retired with Hyprland. See Decision 12. |
| GTK4 UI (all) | 🚫 Retired | 2026-04-19 | GTK4/PyGObject/Python UI retired permanently. New stack: Qt/QML. |
| KDE Plasma desktop | 📋 Next Task | 2026-04-19 | Install KDE, configure SDDM, set Luminos theme. |
| SDDM login screen | 📋 Next Task | — | KDE theme for SDDM. Replaces greetd. |
| Settings app | 📋 Not Started | — | Qt/QML + Go backend. |
| Zone indicator widget | 📋 Not Started | — | KDE Plasma widget dot on window corner (blue/orange/red/none per zone). |
| App launcher | 📋 Not Started | — | KDE built-in launcher. |

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
| Hyprland+GTK4+HyprPanel → KDE Plasma | 📋 **NEXT TASK** | Install KDE Plasma, SDDM, configure Luminos theme |
| Python settings → Qt/QML + Go | 📋 | After KDE install |
| Python login → SDDM theme | 📋 | After KDE install |
| Go daemons for NPU/AI/compat | 📋 | After KDE install |

---

## Retired Components

| Component | Replaced By | Date |
|-----------|------------|------|
| Python bar (bar_app.py) | KDE Plasma taskbar | 2026-04-19 |
| Python dock (dock_app.py) | KDE Plasma taskbar | 2026-04-19 |
| AGS bar (Bar.tsx) | KDE Plasma | 2026-04-19 |
| Waybar | KDE Plasma | 2026-04-19 |
| HyprPanel | KDE Plasma | 2026-04-19 |
| Hyprland | KDE Plasma + KWin | 2026-04-19 |
| GTK4 / PyGObject / Python UI | Qt/QML + Go | 2026-04-19 |
| gtk4-layer-shell | KDE native layer handling | 2026-04-19 |
| greetd / hyprlock / swww | SDDM + KDE | 2026-04-19 |
| dunst | KDE notification system | 2026-04-19 |
| wofi / luminos-launcher-toggle | KDE built-in launcher | 2026-04-19 |

---

## Active Bugs

| Bug | Status |
|-----|--------|
| KDE Plasma not yet installed | 📋 Next Task — see Stack Migration |

---

## Agent Activity Log

| Date | Agent | Task | Outcome |
|------|-------|------|---------|
| 2026-04-12 | claude-code | Fix socket PermissionError in bar/dock | ✅ os.access() fix applied |
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
