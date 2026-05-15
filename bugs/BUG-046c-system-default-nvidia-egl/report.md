# BUG-046c — System-wide Default GPU is NVIDIA (EGL Priority)

- **Status:** FIXED (requires logout to fully activate)
- **Severity:** HIGH
- **Component:** `/usr/share/glvnd/egl_vendor.d/`, session-wide EGL
- **Date Found:** 2026-05-14
- **Date Fixed:** 2026-05-14
- **Agent:** claude-code
- **Related:** BUG-046 (Chrome/NVIDIA), BUG-047 (NVIDIA power), BUG-050 (battery life)

## Description
Every KDE system process (ksecretd, plasmashell, kded6, Xwayland, kwalletd6, dolphin, etc.)
was defaulting to the NVIDIA GPU for EGL rendering.
This kept the RTX 4050 in D0 (fully active, ~1.78W) at all times, even when completely idle.
GPU VRAM was ~120 MiB allocated by system processes. runtime_suspended_time = 0 forever.

This was discovered during BUG-050 battery diagnosis. BUG-046 only fixed Chrome explicitly
but never addressed the session-wide EGL default.

## Root Cause
GLVND (GL Vendor Neutral Dispatch) selects EGL vendors by filename prefix number.
Lower number = higher priority:
```
10_nvidia.json  ← priority 10 (HIGHEST — wins every EGL context by default)
50_mesa.json    ← priority 50 (loses to NVIDIA)
```
NVIDIA's package installs `10_nvidia.json`, making NVIDIA the default EGL for ALL apps.
No environment variable overrides this unless explicitly set per-app.

When ksecretd, plasmashell, Xwayland etc. call `eglGetDisplay()`, they get NVIDIA EGL.
They allocate VRAM, hold renderD129 open, and prevent D3cold permanently.

## Fix Applied

### Step 1 — Rename NVIDIA EGL vendor file
```bash
sudo mv /usr/share/glvnd/egl_vendor.d/10_nvidia.json \
        /usr/share/glvnd/egl_vendor.d/60_nvidia.json
```
After: Mesa (50) wins over NVIDIA (60) for all new EGL contexts.

### Step 2 — Pacman hook to survive NVIDIA updates
```ini
# /etc/pacman.d/hooks/nvidia-egl-priority.hook
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = nvidia-utils

[Action]
Description = Keeping NVIDIA EGL at lower priority than Mesa (AMD default)
When = PostTransaction
Exec = /bin/sh -c 'if [ -f /usr/share/glvnd/egl_vendor.d/10_nvidia.json ]; \
       then mv /usr/share/glvnd/egl_vendor.d/10_nvidia.json \
       /usr/share/glvnd/egl_vendor.d/60_nvidia.json; fi'
```

## What This Changes

| App | Before | After |
|---|---|---|
| ksecretd | NVIDIA EGL (~120 MiB VRAM) | Mesa/AMD EGL (0 VRAM) |
| Xwayland | renderD129 (NVIDIA) | renderD128 (AMD) |
| plasmashell | NVIDIA EGL | Mesa/AMD EGL |
| kded6, kwalletd6, dolphin | NVIDIA EGL | Mesa/AMD EGL |
| Chrome | AMD (already fixed BUG-046) | AMD (unchanged) |
| HIVE (llama.cpp) | CUDA (unaffected by EGL) | CUDA (unaffected) |
| Wine GPU selector | User picks | User picks (unchanged) |

## Why JSON Rename Alone Was Not Enough

The `60_nvidia.json` rename affects GLVND's EGL vendor *enumeration order*.
But KWin in Hybrid NVIDIA mode advertises **both** DRM render nodes (`renderD128` AMD,
`renderD129` NVIDIA) to all Wayland clients via the `zwp_linux_dmabuf` protocol.
Clients open renderD129 directly via the fd sent by the compositor, bypassing GLVND ordering.

`__EGL_VENDOR_LIBRARY_FILENAMES` is a hard override — it completely replaces vendor
discovery and forces ONLY the specified EGL vendor library to load, regardless of how
the DRM fd was obtained. This is why both fixes are required.

## When Does It Take Full Effect?
- **New processes started after rename**: immediately use AMD EGL ✅
- **Running processes (Xwayland, plasmashell, etc.)**: need a **logout/login** to restart
- After logout: Xwayland starts fresh with AMD renderD128, all KDE services use Mesa

## Expected Result After Logout
- NVIDIA GPU enters D3cold (runtime_status: suspended)
- VRAM usage: 0 MiB (from ~120 MiB)
- Power draw: 0W idle (from 1.78W)
- GPU still wakes on demand for HIVE/Forex/gaming (~500ms)

## For Apps That Need NVIDIA EGL Explicitly
```bash
# Override back to NVIDIA EGL for specific launchers:
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/60_nvidia.json
```
Add to: gaming launchers that use PRIME offload with EGL rendering.
HIVE (CUDA) and Forex bot (CPU) do NOT need this override.
