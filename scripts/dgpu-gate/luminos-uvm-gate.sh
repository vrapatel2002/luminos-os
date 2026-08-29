#!/bin/sh
# luminos-uvm-gate — bring /dev/nvidia-uvm{,-tools} under DECISION 25.
# [CHANGE: claude-code | 2026-08-29] BUG-146
#
# WHY THIS EXISTS
# ---------------
# DECISION 25 says the dGPU is default-deny: /dev/nvidia* is root:dgpu 0660 and only
# setgid launchers (dgpu-exec / dgpu-exec-v2) may open it. That is enforced by exactly one
# mechanism, the nvidia module's NVreg_DeviceFileUID/GID/Mode parameters (see
# /etc/modprobe.d/luminos-dgpu-gate.conf).
#
# Those parameters do NOT cover the UVM nodes. Measured 2026-08-29:
#   - /sys/module/nvidia_uvm/parameters/ has no device-file permission knob at all.
#   - nvidia-modprobe creates /dev/nvidia-uvm and -uvm-tools with a hardcoded 0666 root:root.
# So CUDA's shared-memory devices came up world-open on every boot while the rest of the
# gate held. That is BUG-146.
#
# The obvious fix — a udev rule — cannot work here. nvidia-modprobe creates these nodes with
# mknod(2), which emits no uevent; `udevadm info /dev/nvidia0` reports "Unknown device". The
# repo's 70-luminos-dgpu-access.rules has therefore never fired for anything, ever.
#
# HOW THIS FIXES IT
# -----------------
# nvidia-modprobe only mknods a node when it is ABSENT; if the node already exists it leaves
# it completely alone (verified by deleting the nodes and re-running it). So the reliable move
# is to PRE-CREATE both nodes ourselves, correctly owned, before anything asks CUDA for them.
# nvidia-modprobe then never gets the chance to make a world-open one.
#
# A boot-time oneshot is sufficient: devtmpfs nodes are not removed when the module unloads
# (verified with `rmmod nvidia_uvm` — both nodes stayed put, 0660 root:dgpu intact), so once
# these are correct they stay correct until reboot. See luminos-uvm-gate.service for why the
# .path watcher that was tried alongside this got removed.
#
# This script is also a repair path, not only a creator: if something does manage to create a
# world-open node before us, running it again chowns/chmods the existing node into line.
#
# The device major is allocated dynamically by the kernel, so it is read from /proc/devices
# rather than hardcoded. It happened to be 237 on 2026-08-29; do not rely on that.

set -eu

GROUP=dgpu
MODE=0660

log() { echo "luminos-uvm-gate: $*" >&2; }

gid=$(getent group "$GROUP" | cut -d: -f3)
if [ -z "${gid:-}" ]; then
    log "group '$GROUP' does not exist — is the dGPU gate installed? refusing to guess"
    exit 1
fi

# The module must be loaded for the major to be allocated. modules-load.d/nvidia.conf loads
# nvidia-uvm at boot; if it is somehow absent there is no major and nothing to pre-create.
major=$(awk '$2 == "nvidia-uvm" { print $1 }' /proc/devices)
if [ -z "${major:-}" ]; then
    log "nvidia-uvm major not in /proc/devices (module not loaded) — nothing to gate yet"
    exit 0
fi

fix_node() {
    node=$1
    minor=$2

    if [ -e "$node" ]; then
        # Guard against a stale node left over from a previous driver with a different major.
        cur_major=$(stat -c '%Hr' "$node" 2>/dev/null || echo "")
        cur_minor=$(stat -c '%Lr' "$node" 2>/dev/null || echo "")
        if [ "$cur_major" != "$major" ] || [ "$cur_minor" != "$minor" ]; then
            log "$node has stale device numbers ($cur_major:$cur_minor, want $major:$minor) — recreating"
            rm -f "$node"
        fi
    fi

    if [ ! -e "$node" ]; then
        mknod "$node" c "$major" "$minor"
        log "created $node ($major:$minor)"
    fi

    chown "root:$gid" "$node"
    chmod "$MODE" "$node"
}

fix_node /dev/nvidia-uvm       0
fix_node /dev/nvidia-uvm-tools 1

log "gated: $(stat -c '%n %U:%G %a' /dev/nvidia-uvm /dev/nvidia-uvm-tools | tr '\n' ' ')"
