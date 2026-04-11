# Luminos System Status
Last updated: 2026-04-11 (packages + deploy + services)

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
| Rewrite hyprland.conf | 🔲 | |
| Create waybar config | 🔲 | |
| Set supergfxctl Hybrid | 🔲 | |
| Set up greetd login screen | 🔲 | |
| Push all changes to git | 🔲 | |

## Legend
🔲 Not started | 🔄 In progress | ✅ Done | ❌ Blocked
