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

# The module must be loaded for the major to be allocated. Verified 2026-08-29:
# nvidia-uvm.ko.zst IS inside /boot/initramfs-linux.img (mkinitcpio MODULES=) and
# modules-load.d/nvidia.conf lists nvidia-uvm, so by the time this unit runs the major
# exists. If it does not, something is badly wrong.
#
# [CHANGE: claude-code | 2026-08-29] BUG-147 — this used to `exit 0` here, and that was a
# SILENT FAILURE. Measured in a sandbox: with the major absent the script logged "nothing
# to gate yet" and returned SUCCESS, so `systemctl status` showed a green `active (exited)`
# while the gate had done nothing at all and /dev/nvidia-uvm stayed world-open. A gate that
# is not in place is a failure and must say so. Exiting non-zero is safe for boot: nothing
# Requires= this unit, it is only ORDERED before supergfxd and display-manager, so a failure
# is loud without being fatal.
major=$(awk '$2 == "nvidia-uvm" { print $1 }' /proc/devices)
if [ -z "${major:-}" ]; then
    log "FAILED: nvidia-uvm major not in /proc/devices — the module is not loaded, so the"
    log "        UVM nodes CANNOT be gated and are left ungated. DECISION 25 is NOT in"
    log "        force. Check modules-load.d/nvidia.conf and the initramfs."
    exit 1
fi

# [CHANGE: claude-code | 2026-08-29] BUG-147 — report whether we WON the boot race.
#
# This gate only works by pre-creating the nodes before anything calls nvidia-modprobe,
# because nvidia-modprobe leaves an existing node alone and only mknods an absent one.
# So "did we get there first?" is the single fact that decides whether the gate is sound,
# and until now it was invisible: winning and losing produced byte-identical output and
# exit 0 either way. Measured in a sandbox 2026-08-29 — the only difference was the
# presence of a "created" line, which is an inference, not a report.
#
# Losing is not harmless just because we repair it afterwards. It means something raced us
# and won, and the window where the node sat world-open was real. On a slower boot the
# repair might come after a CUDA client has already opened it. That must be a FAILURE.
#
# Three outcomes, deliberately distinguished:
#   created           -> we won. Correct.
#   present + correct -> benign; almost certainly a re-run inside the same boot.
#   present + WRONG   -> WE LOST THE RACE. Repair it, then fail loudly.
raced=0

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
        log "created $node ($major:$minor) — won the race"
    else
        # Already there. Was it already correct, or did somebody beat us to it?
        # stat %a prints without a leading zero (660), MODE carries one (0660).
        cur=$(stat -c '%U:%G %a' "$node" 2>/dev/null || echo "?:? ?")
        if [ "$cur" != "root:$GROUP ${MODE#0}" ]; then
            log "UNGATED NODE FOUND: $node was [$cur], wanted [root:$GROUP ${MODE#0}]. Repaired,"
            log "                    but it was open until this moment."
            log "                    At BOOT this means we lost the race and something created"
            log "                    it before us — the ordering is wrong."
            log "                    MID-SESSION it more likely means BUG-146: a setuid-root"
            log "                    nvidia-modprobe re-applied the driver defaults after we ran."
            log "                    This script cannot tell those two apart; check the timestamp."
            raced=1
        fi
    fi

    chown "root:$gid" "$node"
    chmod "$MODE" "$node"
}

fix_node /dev/nvidia-uvm       0
fix_node /dev/nvidia-uvm-tools 1

log "gated: $(stat -c '%n %U:%G %a' /dev/nvidia-uvm /dev/nvidia-uvm-tools | tr '\n' ' ')"

if [ "$raced" -eq 1 ]; then
    log "FAILED: the nodes are correct NOW, but this unit did not create them — it found them"
    log "        already open and repaired them. Do not trust the repair; find what opened"
    log "        them. If this line appears in the FIRST seconds of a boot, the unit ordering"
    log "        is wrong. If it appears later, it is BUG-146 re-opening them at runtime."
    exit 1
fi
