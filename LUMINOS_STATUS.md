# LUMINOS_STATUS.md — Current State of All Components

> Updated by every agent after every task. If you're an agent, update this before committing.
> Format: component name, status emoji, last updated, brief notes.

**Status key:** ✅ Working | 🔧 In Progress | ❌ Broken | 📋 Not Started | ⚠️ Working with caveats

---

## Core System

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Arch Linux base | ✅ Working | — | Triple boot on G14 alongside Windows + default Arch |
| Hyprland 0.54.3 | ✅ Working | 2026-04-19 | Config errors fixed. windowrulev2 migrated to block-style. Window decorations (hyprbars) removed in favor of native GTK decorations. Added robust window controls. |
| swww-daemon | ⚠️ Partial | 2026-04-12 | Autostart via exec-once works. Wallpaper not set on boot. |
| Triple boot | ✅ Working | — | GRUB boots all three. GPT mismatch warning on boot (cosmetic, auto-corrects) |

---

## GUI Components

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| HyprPanel (bar+dock) | ✅ Working | 2026-04-19 | Replaces Python bar, waybar, AGS. Taskbar minimize-on-click enabled. |
| HyprPanel right-side layout | 🔧 In Progress | 2026-04-18 | Audio+battery grouped in systray, clock time-over-date — needs reboot verify |
| Login screen | 📋 Not Started | — | Design: fullscreen, big clock+date, Enter → password or desktop. greetd backend planned. |
| Settings app | 📋 Not Started | — | Go + GTK4 + libadwaita. Python settings code exists but deprecated. |
| App launcher | ⚠️ Partial | 2026-04-18 | wofi toggle via keybind, pinned in HyprPanel taskbar |

---

## Environment & Tooling

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| asusctl + supergfxctl | ✅ Working | 2026-04-17 | asusd + supergfxd enabled; mode confirmed Hybrid |
| greetd | ✅ Installed | 2026-04-17 | greetd enabled; luminos-greeter via cage |
| MemPalace | ✅ Available | 2026-04-18 | Python 3.12 venv (uv-managed), MCP registered, 2544 drawers |
| code-review-graph | ✅ Available | 2026-04-18 | MCP registered, graph built (2560 nodes, 17478 edges, 187 files) |
| nm-applet | ✅ Working | 2026-04-18 | network-manager-applet for wifi systray icon |
| pipewire-pulse | ✅ Working | 2026-04-18 | Installed for HyprPanel audio support |

---

## Boot & System Issues

| Issue | Status | Notes |
|-------|--------|-------|
| GPT mismatch warning | ⚠️ Known/cosmetic | Auto-corrects on boot. Not urgent. |
| greetd GTK4 gl module error | ❌ Blocking login screen | GTK4 renderer fails in greetd environment. Needs investigation. |

---

## Stack Migration Status

| Migration Task | Status | Notes |
|----------------|--------|-------|
| Python bar → HyprPanel | ✅ | HyprPanel replaces Python bar, waybar, and AGS |
| Python dock → HyprPanel taskbar | ✅ | HyprPanel taskbar module replaces Python dock |
| AGS bar → HyprPanel | ✅ | AGS bar retired |
| Waybar → HyprPanel | ✅ | Waybar retired |
| Python settings → Go + libadwaita | 📋 | PLANNED |
| Python login screen → Go + libadwaita | 📋 | PLANNED |
| Go daemons for NPU/AI/compat | 📋 | PLANNED |

---

## Retired Components

| Component | Replaced By | Date |
|-----------|------------|------|
| Python bar (bar_app.py) | Waybar → HyprPanel | 2026-04-17 |
| Python dock (dock_app.py) | Waybar → HyprPanel | 2026-04-17 |
| AGS bar (Bar.tsx) | HyprPanel | 2026-04-17 |
| Waybar | HyprPanel | 2026-04-18 |
| dunst | HyprPanel notifications | 2026-04-18 |
| luminos-launcher-toggle (Python) | wofi via keybind | 2026-04-18 |

---

## Active Bugs

| Bug | Status |
|-----|--------|
| Settings accent swatches not rendering | 📋 Not started |
| HyprPanel right-side icons misaligned | 🔧 CSS fixes applied — needs reboot verify |

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
