# Luminos System Status
Last updated: 2026-04-18

## Environment
- Machine: ASUS ROG G14
- OS: Arch Linux
- Hyprland: installed and running

## Task Tracker
| Task | Status | Notes |
|------|--------|-------|
| Install waybar | ✅ | v0.15.0 — Windows 11 style taskbar (bottom, height 41, accent #0080FF) |
| Install swww | ✅ | v0.12.0 via pacman |
| Install brightnessctl | ✅ | v0.5.1 via pacman |
| Install playerctl | ✅ | v2.4.1 via pacman |
| Install greetd | ✅ | v0.10.3 via pacman |
| Install asusctl (AUR) | ✅ | via yay |
| Install supergfxctl (AUR) | ✅ | via yay |
| Install Python deps | ✅ | venv at /opt/luminos/venv — llama-cpp-python 0.3.20, onnxruntime 1.24.4, psutil 7.2.2 |
| venv system site-packages fix | ✅ | include-system-site-packages = true — GTK4/PyGObject now visible in venv |
| Deploy code to /opt/luminos | ✅ | /opt/luminos/src symlinked → ~/luminos-os/src (always in sync) |
| Install scripts to PATH | ✅ | luminos-launcher-toggle + luminos-quick-settings-toggle → /usr/local/bin |
| Install systemd services (system) | ✅ | luminos-ai + luminos-sentinel enabled |
| Rewrite hyprland.conf | ✅ | Luminos theme, ROG keys, touchpad gestures, waybar blur layerrules |
| Hyprland blur layerules | ✅ | waybar blur via layerrule — synced to repo |
| Set supergfxctl Hybrid | ✅ | asusd + supergfxd enabled; mode confirmed Hybrid |
| Set up greetd login screen | ✅ | greetd enabled; luminos-greeter via cage; GTK4+python-gobject installed |
| MemPalace installed | ✅ | Python 3.12 venv (uv-managed), MCP registered, 2544 drawers indexed |
| code-review-graph installed | ✅ | MCP registered, graph built (2560 nodes, 17478 edges, 187 files) |
| Push all changes to git | ✅ | Unblocked — all commits pushed to main |
| WhiteSur icon + cursor themes | ✅ | whitesur-icon-theme-git + whitesur-cursor-theme-git installed; gsettings applied |
| WhiteSur GTK theme | ✅ | whitesur-gtk-theme-git installed; gsettings applied |
| macOS-style Hyprland aesthetics | ✅ | macOS bezier, popin 95% animations, shadow rgba(00000066) |
| Hyprbars traffic light buttons | ✅ | Red/yellow/green window buttons via hyprbars plugin |
| Windows 11 waybar | ✅ | Win10-style-waybar config, bottom taskbar, #0080FF accent, blur |
| Login screen | 🔲 | Not started |
| Settings accent color swatches | 🔲 | Not rendering — not started |

## Active Bugs
| Bug | Status |
|-----|--------|
| Bar shifting to right side on reboot | ✅ Fixed — replaced with waybar |
| Blur lost on reboot | ✅ Fixed — layerules in hyprland.conf |
| Settings accent swatches not rendering | 🔲 Not started |

## Current Phase: Stack Migration
| Migration Task | Status | Notes |
|----------------|--------|-------|
| Python bar → Waybar | ✅ | Windows 11 style waybar replaces both AGS and Python bar |
| Python dock → Waybar taskbar | ✅ | wlr/taskbar module in waybar replaces Python dock |
| AGS bar → Waybar | ✅ | AGS bar retired — waybar is the single bar solution |
| Python settings → Go + libadwaita | 🔲 | PLANNED |
| Python login screen → Go + libadwaita | 🔲 | PLANNED |
| Go daemons for NPU/AI/compat | 🔲 | PLANNED — replacing Python daemon code with Go single binaries |

## Retired Components
| Component | Replaced By | Date |
|-----------|------------|------|
| Python bar (bar_app.py) | Waybar | 2026-04-17 |
| Python dock (dock_app.py) | Waybar wlr/taskbar | 2026-04-17 |
| AGS bar (Bar.tsx) | Waybar | 2026-04-17 |
| luminos-bar.service | waybar exec-once | 2026-04-17 |
| luminos-dock.service | waybar exec-once | 2026-04-17 |
| luminos-deco.service | hyprbars plugin | 2026-04-17 |

## Legend
🔲 Not started | 🔄 In progress | ✅ Done | ❌ Blocked
