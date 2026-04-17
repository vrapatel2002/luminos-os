# Luminos System Status
Last updated: 2026-04-17

## Environment
- Machine: ASUS ROG G14
- OS: Arch Linux
- Hyprland: installed and running

## Task Tracker
| Task | Status | Notes |
|------|--------|-------|
| Install waybar | ✅ | v0.15.0 via pacman (reference only — luminos-bar used instead) |
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
| Install systemd services (user) | ✅ | luminos-bar + luminos-dock + luminos-wallpaper enabled and running |
| Rewrite hyprland.conf | ✅ | Luminos theme, ROG keys, touchpad gestures, layerules for blur |
| Hyprland blur layerules | ✅ | luminos-bar/dock/quick-settings/calendar blur via layerrule — synced to repo + compositor_config.py |
| Set supergfxctl Hybrid | ✅ | asusd + supergfxd enabled; mode confirmed Hybrid |
| Set up greetd login screen | ✅ | greetd enabled; luminos-greeter via cage; GTK4+python-gobject installed |
| MemPalace installed | ✅ | Python 3.12 venv (uv-managed), MCP registered, 2544 drawers indexed |
| code-review-graph installed | ✅ | MCP registered, graph built (2518 nodes, 17246 edges, 182 files) |
| Push all changes to git | ✅ | Unblocked — all commits pushed to main |
| WhiteSur icon + cursor themes | ✅ | whitesur-icon-theme-git + whitesur-cursor-theme-git installed; gsettings applied |
| WhiteSur GTK theme | ✅ | whitesur-gtk-theme-git installed (PKGBUILD patched for missing plank/firefox dirs); gsettings applied |
| macOS-style Hyprland aesthetics | ✅ | macOS bezier, popin 80% animations, blur passes=3+noise+contrast+brightness, shadow rgba(00000066), gtk4-layer-shell layerrules |
| Bar/dock positioning (anchors) | ✅ | AGS bar: Astal.Exclusivity.EXCLUSIVE; dock: Layer.TOP+exclusive_zone |
| AGS (aylurs-gtk-shell) installed | ✅ | v3.1.0 via yay; libastal-battery/network/hyprland/wireplumber/tray/notifd |
| AGS bar — basic render | ✅ | Bar.tsx + app.ts + style.scss; workspace dots, clock, system tray |
| AGS bar — rich popovers | ✅ | Vol/brightness sliders, Wi-Fi SSID, battery details with time remaining |
| AGS bar wired into Hyprland | ✅ | exec-once ags run in hyprland.conf; old Python service disabled |
| macOS deco buttons | ✅ | Traffic-light close/min/max overlay; polls activewindow, repositions |
| Bar/dock auto-hide | ✅ | Opacity fade on mouse leave/enter; exclusive_zone stays constant |
| Bar icons and widgets | ✅ | Phosphor SVG icons in bar — quick-settings popup working |
| Login screen | 🔲 | Not started |
| Settings accent color swatches | 🔲 | Not rendering — not started |

## Active Bugs
| Bug | Status |
|-----|--------|
| Bar shifting to right side on reboot | ✅ Fixed — AGS bar uses Astal anchors (TOP|LEFT|RIGHT) |
| Blur lost on reboot | ✅ Fixed — layerules now in repo + compositor_config.py |
| Dock below windows (Layer.BOTTOM) | ✅ Fixed — changed to Layer.TOP |
| Dock exclusive_zone=-1 | ✅ Fixed — auto_exclusive_zone_enable |
| Settings accent swatches not rendering | 🔲 Not started |

## Current Phase: Stack Migration
| Migration Task | Status | Notes |
|----------------|--------|-------|
| Python bar → AGS/JavaScript | ✅ | Bar migrated — AGS bar with popovers, sliders, workspace dots |
| Python dock → AGS/JavaScript | 🔲 | PLANNED — dock still runs as Python GTK4 |
| Python settings → Go + libadwaita | 🔲 | PLANNED |
| Python login screen → Go + libadwaita | 🔲 | PLANNED |
| Go daemons for NPU/AI/compat | 🔲 | PLANNED — replacing Python daemon code with Go single binaries |

## Legend
🔲 Not started | 🔄 In progress | ✅ Done | ❌ Blocked
