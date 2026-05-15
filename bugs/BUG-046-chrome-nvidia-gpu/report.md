# BUG-046 — Chrome Using NVIDIA GPU

- **Status:** FIXED
- **Severity:** HIGH
- **Component:** `/usr/local/bin/chrome-luminos`
- **Date Found:** 2026-05-10
- **Date Fixed:** 2026-05-10
- **Agent:** gemini-cli

## Description
Chrome was activating the NVIDIA dGPU during all browsing sessions, wasting 8-15W
and preventing NVIDIA from power-gating.

## Root Cause
The `chrome-luminos` wrapper script had `--render-node-override=/dev/dri/renderD129`
which explicitly points to the NVIDIA render node.

## Fix Applied (2026-05-10, gemini-cli)
- Removed `--render-node-override=/dev/dri/renderD129` from the wrapper
- `DRI_PRIME=0` added to force AMD iGPU for Mesa
- Added explicit `VK_ICD_FILENAMES` pointing to radeon_icd to block Vulkan on NVIDIA

## Re-Fix (2026-05-14, claude-code)
The 2026-05-10 fix was incomplete. Chrome Flatpak runs its own GPU enumeration
inside the sandbox — it ignores `DRI_PRIME` and re-selects NVIDIA independently,
then passes `--render-node-override=/dev/dri/renderD129` to its own GPU subprocess.

Confirmed via: `cat /proc/<chrome-gpu-pid>/cmdline | grep render-node`

Fix: added `--render-node-override=/dev/dri/renderD128` explicitly to the wrapper
so Chrome's outer process sets AMD before Chrome's internal GPU detection runs.

## Files Changed
- `/usr/local/bin/chrome-luminos`
