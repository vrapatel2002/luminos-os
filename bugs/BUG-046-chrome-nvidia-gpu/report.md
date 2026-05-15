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
then passes `--render-node-override` to its own GPU subprocess.

Fix: added `--render-node-override` explicitly to the wrapper so Chrome's outer
process locks the GPU before Chrome's internal detection runs. GPU selector dialog
added via kdialog.

## Hotfix (2026-05-15, claude-code) — render-node assignment was reversed
The 2026-05-14 re-fix had the render nodes backwards, causing Chrome to crash
with Signal 5 (TRAP) in libzypak whenever AMD was selected.

**Root cause:** NVIDIA (pci 01:00.0) has a lower PCI bus number than AMD (pci 65:00.0),
so the kernel probes NVIDIA first and assigns it renderD128. AMD gets renderD129.

```
/dev/dri/renderD128 → pci-0000:01:00.0 → NVIDIA RTX 4050
/dev/dri/renderD129 → pci-0000:65:00.0 → AMD Radeon 780M
```

The 2026-05-14 fix incorrectly set:
- AMD mode → `--render-node-override=/dev/dri/renderD128` (was NVIDIA!)
- NVIDIA mode → `--render-node-override=/dev/dri/renderD129` (was AMD!)

Chrome received conflicting signals (AMD env vars + NVIDIA render node) and
libzypak's sandbox setup assertion fired → SIGTRAP crash.

**Fix:** swapped the render node assignments:
- AMD mode → `--render-node-override=/dev/dri/renderD129` ✓
- NVIDIA mode → `--render-node-override=/dev/dri/renderD128` ✓

## Files Changed
- `/usr/local/bin/chrome-luminos`
