# Luminos System Status
Last updated: 2026-04-11 (all tasks complete except greetd login screen)

## Environment
- Machine: ASUS ROG G14
- OS: Arch Linux
- Hyprland: installed and running

## Task Tracker
| Task | Status | Notes |
|------|--------|-------|
| Install waybar | ✅ | v0.15.0 via pacman |
| Install swww | ✅ | v0.12.0 via pacman |
| Install brightnessctl | ✅ | v0.5.1 via pacman |
| Install playerctl | ✅ | v2.4.1 via pacman |
| Install greetd | ✅ | v0.10.3 via pacman |
| Install asusctl (AUR) | ✅ | via yay |
| Install supergfxctl (AUR) | ✅ | via yay |
| Install Python deps | ✅ | venv at /opt/luminos/venv — llama-cpp-python 0.3.20, onnxruntime 1.24.4, psutil 7.2.2 |
| Deploy code to /opt/luminos | ✅ | src/ copied; venv created |
| Install scripts to PATH | ✅ | luminos-launcher-toggle + luminos-quick-settings-toggle → /usr/local/bin |
| Install systemd services | ✅ | luminos-ai + luminos-sentinel enabled (system); luminos-wallpaper enabled (user) |
| Rewrite hyprland.conf | ✅ | Luminos theme, Luminos colors, ROG keys, touchpad gestures, autostart bar+dock+swww |
| Create waybar config | ✅ | Bar is Luminos GTK4 app (luminos-bar) — waybar not used; luminos-bar + luminos-dock scripts installed |
| Set supergfxctl Hybrid | ✅ | asusd + supergfxd enabled; mode confirmed Hybrid |
| Set up greetd login screen | 🔲 | greetd installed; login screen UI not wired yet |
| Push all changes to git | 🔄 | Blocked on GitHub auth — commit exists locally (4f3eb89) |

## Legend
🔲 Not started | 🔄 In progress | ✅ Done | ❌ Blocked
