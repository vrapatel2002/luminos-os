# Luminos dGPU Access Gate (DECISION 25)

Makes the discrete NVIDIA RTX 4050 **default-deny**: unknown apps can no longer grab
the dGPU. Only apps launched through the GPU picker (`luminos-gpu-launch`) reach it.

## Why

The NVIDIA driver creates `/dev/nvidia*` world-open (`0666`), so **any** process could
open the dGPU with zero permission check. That is why `claude-desktop`, `antigravity`,
etc. hold the card awake even though they render on the AMD iGPU — they merely *probe*
every GPU at startup. This gate closes that hole.

## Mechanism (works even though everything runs as user `shawn`)

1. **`dgpu` system group** — `shawn` is deliberately **not** a member.
2. **udev rule** `70-luminos-dgpu-access.rules` → `/dev/nvidia*` become `root:dgpu 0660`
   (default-deny for normal apps).
3. **`dgpu-exec`** — a tiny **setgid `dgpu`** helper (`2755 root:dgpu`). Apps launched
   through it inherit `egid=dgpu` and can open the device. Everything else is denied and
   silently falls back to the iGPU.
4. `luminos-gpu-launch` (the styled QML picker) routes the NVIDIA choice through
   `dgpu-exec`, so **the picker is the only door to the dGPU**.

Root services (`nvidia-powerd`, `luminos-power`/Conductor) bypass DAC and are unaffected.
The desktop is driven by the AMD iGPU, so blocking the dGPU nodes does not touch display.

## Install

```bash
sudo scripts/dgpu-gate/install-dgpu-gate.sh
```

Applies live **without revoking already-open FDs** — running apps keep working; the gate
takes full effect on their next launch.

## Allowlisting an app

Launch it through the picker:

```bash
luminos-gpu-launch <command> [args...]     # choose "NVIDIA" in the dialog
```

For headless / scripted jobs (e.g. the forex training bot), wrap the command:

```bash
dgpu-exec <command> [args...]
```

## Kill switch

```bash
sudo chmod 0666 /dev/nvidia*                 # instant restore of world-open behavior
sudo rm /etc/udev/rules.d/70-luminos-dgpu-access.rules && sudo udevadm control --reload   # permanent disable
```

## v2 (not yet built)

A true kernel gate via **BPF-LSM** (`CONFIG_BPF_LSM=y`, `bpf` is in the active LSM list)
that allow-lists apps by binary path/hash and denies at `open()` — bypass-proof even
against a hostile process that tries to call `dgpu-exec` itself. v1 above covers the
"unknown app accidentally grabs the dGPU" threat model; v2 covers the adversarial one.
