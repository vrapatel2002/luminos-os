#!/bin/bash
# install-dgpu-gate.sh — install the Luminos dGPU access gate (DECISION 25).
# [CHANGE: claude-code | 2026-07-03]
#
# Idempotent. Safe to re-run. Applies the perm change LIVE without revoking any
# already-open file descriptors (running apps keep working; the gate takes full
# effect on their next launch).
#
# KILL SWITCH (instant restore): sudo chmod 0666 /dev/nvidia*
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_SRC="$REPO_DIR/../../config/udev/70-luminos-dgpu-access.rules"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

echo "[1/7] Ensure 'dgpu' system group exists (shawn deliberately NOT a member)..."
getent group dgpu >/dev/null || groupadd --system dgpu
DGPU_GID="$(getent group dgpu | cut -d: -f3)"
echo "      dgpu gid=$DGPU_GID"

echo "[2/7] Install NVIDIA driver param (authoritative gate — survives wake/reboot)..."
# nvidia-modprobe recreates /dev/nvidia* at 0666 on every wake; only the driver params
# below make the restricted perms stick. GID is written to match the real dgpu group.
cat > /etc/modprobe.d/luminos-dgpu-gate.conf <<EOF
# [CHANGE: claude-code | 2026-07-03] DECISION 25 — dGPU access gate (authoritative layer)
# See scripts/dgpu-gate/README.md. KILL SWITCH:
#   sudo rm /etc/modprobe.d/luminos-dgpu-gate.conf && sudo mkinitcpio -P && reboot
options nvidia NVreg_DeviceFileUID=0 NVreg_DeviceFileGID=$DGPU_GID NVreg_DeviceFileMode=0660
EOF
echo "      wrote /etc/modprobe.d/luminos-dgpu-gate.conf (GID=$DGPU_GID)"

echo "[3/7] Compile + install setgid helpers /usr/local/bin/dgpu-exec{,-v2} ..."
# [CHANGE: claude-code | 2026-08-28] v2 was built by hand on 2026-08-05 and never added
# here, so a rebuilt machine got v1 only — and v1 is the one that drops the group at the
# first shell wrapper (BUG-102). Build both; v2 is what everything should call.
# NOTE: do not build into /tmp — it is nosuid here, and the setgid bit is silently
# ignored there, which makes a correct binary look broken.
for v in "dgpu-exec:dgpu-exec.c" "dgpu-exec-v2:dgpu-exec-v2.c"; do
  bin="/usr/local/bin/${v%%:*}"; src="$REPO_DIR/${v##*:}"
  cc -O2 -Wall -Wextra -o "$bin" "$src"
  chown root:dgpu "$bin"
  chmod 2755 "$bin"                        # setgid dgpu
  ls -l "$bin"
done

echo "[4/7] Install udev rule ..."
# HONESTY NOTE [claude-code | 2026-08-28]: this rule has never actually fired. The NVIDIA
# nodes are created by nvidia-modprobe with mknod(2), not by the kernel device model, so
# `udevadm info /dev/nvidia0` reports "Unknown device" and no rule ever matches them. The
# ONLY thing enforcing DECISION 25 is the NVreg_DeviceFile* driver param in step 2. The
# rule is kept because it costs nothing and would apply if NVIDIA ever switches to proper
# device registration — but do NOT count it as a second layer. It is not one. See BUG-146.
install -m 0644 "$UDEV_SRC" /etc/udev/rules.d/70-luminos-dgpu-access.rules
udevadm control --reload

echo "[5/7] Install the GPU launcher + styled picker (single launch path) ..."
install -m 0755 "$REPO_DIR/../luminos-gpu-launch" /usr/local/bin/luminos-gpu-launch
install -d -m 0755 /usr/local/share/luminos
install -m 0644 "$REPO_DIR/luminos-gpu-picker.qml" /usr/local/share/luminos/luminos-gpu-picker.qml

echo "[6/7] Rebuild initramfs so the driver param loads at early boot ..."
# nvidia is in mkinitcpio MODULES=(...), so the module param must be baked into initramfs.
mkinitcpio -P

echo "[7/7] Apply LIVE to existing nodes (best-effort; a wake may reset until reboot) ..."
# BUG-146: the two UVM nodes below are gated HERE and then quietly un-gated on the next
# reboot. NVreg_DeviceFileGID (step 2) governs the `nvidia` module's own nodes only;
# nvidia_uvm has no equivalent parameter, so nvidia-modprobe recreates /dev/nvidia-uvm
# and /dev/nvidia-uvm-tools as root:root 0666 every boot and nothing puts them back.
# Verified 2026-08-28: post-boot they were 0666 root:root while nvidia0/nvidiactl were
# correctly 0660 root:dgpu. Not a bypass — CUDA also needs nvidiactl and nvidia0, which
# stay tight, so `nvidia-smi` outside the gate still fails with "Insufficient
# Permissions" — but it does contradict the stated default-deny posture.
shopt -s nullglob
for n in /dev/nvidiactl /dev/nvidia[0-9]* /dev/nvidia-modeset /dev/nvidia-uvm /dev/nvidia-uvm-tools; do
  chgrp dgpu "$n" && chmod 0660 "$n" && echo "      gated $n -> $(stat -c '%U:%G %a' "$n")"
done
echo "      (verify any time with: dgpu-exec-v2 --check)"

echo
echo "Done. The AUTHORITATIVE gate (driver param) takes full effect on next REBOOT."
echo "--- device perms now (may show 0666 until reboot if the card woke) ---"
ls -l /dev/nvidia* 2>/dev/null | grep -v nvidia-caps || true
echo "--- KILL SWITCH: sudo chmod 0666 /dev/nvidia*   (temporary)"
echo "--- PERMANENT OFF: sudo rm /etc/modprobe.d/luminos-dgpu-gate.conf /etc/udev/rules.d/70-luminos-dgpu-access.rules && sudo mkinitcpio -P"
