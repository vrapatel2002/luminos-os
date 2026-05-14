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

## Fix Applied
- Removed `--render-node-override` flag from the wrapper
- `DRI_PRIME=0` now correctly forces AMD iGPU (renderD128) for all Chrome rendering
- Added explicit `VK_ICD_FILENAMES` pointing to radeon_icd to block Vulkan on NVIDIA

## Files Changed
- `/usr/local/bin/chrome-luminos`
