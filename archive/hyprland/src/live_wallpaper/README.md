# luminos-live-wallpaper

Native C live wallpaper renderer for Luminos OS. Renders GLSL shader presets on the desktop background via the wlr-layer-shell Wayland protocol, integrated with Hyprland.

Runs exclusively on the AMD RDNA3 iGPU. NVIDIA dGPU is never used.

## Dependencies

All available via pacman on Arch Linux:

```
sudo pacman -S wayland wayland-protocols mesa libdrm libxkbcommon
```

Build tools:

```
sudo pacman -S gcc pkgconf wayland-scanner
```

## Build

```
cd src/live_wallpaper
make
```

## Install

```
sudo make install
```

Installs the binary to `/usr/local/bin/luminos-live-wallpaper` and shader presets to `/usr/share/luminos/live-wallpaper/presets/`.

## Usage

```
./luminos-live-wallpaper --preset particles --intensity medium
```

### Arguments

| Flag | Values | Default |
|------|--------|---------|
| `--preset` | `particles`, `aurora`, `geometric` | `particles` |
| `--intensity` | `low`, `medium`, `high` | `medium` |
| `--output` | Wayland output name | primary |
| `--socket` | Unix socket path | `/tmp/luminos-wallpaper.sock` |

## Control via Socket

The wallpaper manager (`wallpaper_manager.py`) controls the renderer via a Unix socket at `/tmp/luminos-wallpaper.sock`. Commands are newline-terminated JSON:

```json
{"cmd": "set_preset", "preset": "aurora", "intensity": "high"}
{"cmd": "set_intensity", "intensity": "low"}
{"cmd": "pause"}
{"cmd": "resume"}
{"cmd": "suspend"}
{"cmd": "resume_from_suspend"}
{"cmd": "status"}
{"cmd": "quit"}
```

### Manual test with socat

```
echo '{"cmd": "status"}' | socat - UNIX-CONNECT:/tmp/luminos-wallpaper.sock
```

## Signal handling

- `SIGTERM` / `SIGINT` — clean exit
- `SIGUSR1` — pause rendering (sent by power manager)
- `SIGUSR2` — resume rendering

## Architecture

```
main.c       — entry point, argument parsing, main loop, signal handling
wayland.c/h  — Wayland connection, wlr-layer-shell surface setup
egl.c/h      — EGL context on AMD iGPU via DRM device selection
renderer.c/h — OpenGL ES 2.0 render loop, shader management
input.c/h    — Wayland pointer + keyboard event handling
socket.c/h   — Unix socket server for control commands
power.c/h    — Battery/AC detection, auto pause/resume
presets/     — GLSL ES 2.0 fragment shaders
```

## Presets

- **particles** — floating particle field with connections, mouse repulsion, keypress scatter
- **aurora** — flowing northern lights bands, mouse hue shift, amplitude control
- **geometric** — dot grid with proximity glow, keypress ripple wave, idle breathing
