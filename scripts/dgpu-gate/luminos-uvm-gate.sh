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
# A udev rule keyed on the NODE cannot work here. nvidia-modprobe creates these nodes with
# mknod(2), which emits no uevent; `udevadm info /dev/nvidia0` reports "Unknown device". The
# repo's 70-luminos-dgpu-access.rules has therefore never fired for anything, ever.
#
# [CHANGE: claude-code | 2026-08-29] BUG-147 — that paragraph used to read "the obvious fix, a
# udev rule, cannot work here", full stop. True of a node-keyed rule, but far too broad, and
# the over-broad version steered the design wrong. A rule keyed on the PCI DEVICE add/bind
# event works fine: that IS a real uevent, and it is the very event 60-nvidia.rules uses to
# invoke nvidia-modprobe in the first place. 71-luminos-uvm-gate.rules does exactly that and
# is now the PRIMARY mechanism; this script is the BACKSTOP. Do not re-broaden the claim.
#
# HOW THIS FIXES IT
# -----------------
# nvidia-modprobe only mknods a node when it is ABSENT; if the node already exists it leaves
# it completely alone (verified by deleting the nodes and re-running it).
#
# !! DO NOT TURN THAT INTO "SO PRE-CREATE THE NODES FIRST" !!
# This script used to say exactly that, and it was WRONG AND DANGEROUS. The guard in
# 60-nvidia.rules is TEST!="/dev/nvidia-uvm", and it covers BOTH of that rule's RUN+= lines.
# So if /dev/nvidia-uvm exists when udev evaluates it, nvidia-modprobe does not run AT ALL,
# and /dev/nvidia0 and /dev/nvidiactl — which it also creates — never appear.
# MEASURED 2026-08-29: UVM nodes present, main nodes deleted, add trigger -> neither main node
# came back, and nvidia-smi failed with "couldn't communicate with the NVIDIA driver".
# So the "won the race" outcome this script was built to achieve would have KILLED the dGPU.
# It only ever worked because it LOST. The mknod path below is now guarded on /dev/nvidia0
# already existing, which is the proof that nvidia-modprobe has already had its turn.
#
# A boot-time backstop is sufficient: devtmpfs nodes are not removed when the module unloads
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

# [CHANGE: claude-code | 2026-08-29] BUG-147 — --udev mode.
# Invoked from 71-luminos-uvm-gate.rules, riding the same PCI uevent that ran
# nvidia-modprobe a few milliseconds earlier. In THAT context finding the nodes freshly
# created and world-open is not a fault, it is the entire expected sequence — so the loud
# "we lost the race" failure below would fire on every boot and mean nothing. Suppress it
# there and there only. Run by hand or from the service, the loud path still applies.
UDEV_MODE=0
case "${1:-}" in
    --udev) UDEV_MODE=1 ;;
    "")     ;;
    *)      echo "luminos-uvm-gate: unknown argument '$1' (only --udev)" >&2; exit 2 ;;
esac

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

# [CHANGE: claude-code | 2026-08-29] BUG-147 — the pass/fail semantics here were INVERTED,
# and this block is the correction. The original text is kept below so the reasoning error is
# visible rather than quietly overwritten:
#
#   "This gate only works by pre-creating the nodes before anything calls nvidia-modprobe...
#    Three outcomes: created -> we won. Correct. / present + WRONG -> WE LOST THE RACE."
#
# "Created" was never the correct outcome. It is the catastrophic one: creating the UVM node
# first trips TEST!="/dev/nvidia-uvm" in 60-nvidia.rules and suppresses nvidia-modprobe
# entirely, so /dev/nvidia0 and /dev/nvidiactl are never created and the card is unreachable.
# Measured 2026-08-29 (see header). The gate has only ever worked because it lost the race.
#
# What actually decides whether the gate is sound is not "who got there first" but "how long
# was the node world-open". With 71-luminos-uvm-gate.rules in place that is 9-18 ms, measured,
# down from 2.2 s. So the outcomes now are:
#   present + correct -> the udev rule did its job. THE EXPECTED BOOT OUTCOME.
#   present + WRONG   -> the udev rule did NOT fire. Repair, then fail loudly (unless --udev,
#                        where being the one doing the repair IS the job).
#   absent            -> nvidia-modprobe has not run yet. Creating it here would break the
#                        card, so refuse unless /dev/nvidia0 proves it already ran.
# Two DIFFERENT bad outcomes, kept apart on purpose. Folding them into one flag was written
# here first and produced a flatly false message — the refusal path printed "the nodes are
# correct NOW" while both nodes were absent. Caught by the guard test, 2026-08-29.
raced=0      # found a node ungated and repaired it
refused=0    # declined to create a node because nvidia-modprobe had not run yet

# The proof that nvidia-modprobe has already had its turn on this uevent. If /dev/nvidia0
# exists, the main nodes are made and suppressing a future nvidia-modprobe costs nothing.
MAIN_NODE=/dev/nvidia0

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
        # [CHANGE: claude-code | 2026-08-29] BUG-147 — guarded. Creating this node while
        # nvidia-modprobe has still to run makes 60-nvidia.rules skip it, and then NOTHING
        # creates /dev/nvidia0 or /dev/nvidiactl. Measured: card becomes unreachable,
        # "nvidia-smi has failed because it couldn't communicate with the NVIDIA driver".
        if [ ! -e "$MAIN_NODE" ]; then
            log "REFUSING to create $node: $MAIN_NODE does not exist yet, so nvidia-modprobe"
            log "        has not run. Creating this node now would trip TEST!=/dev/nvidia-uvm"
            log "        in 60-nvidia.rules and leave the card with no /dev/nvidia0 at all."
            log "        Leaving it absent is strictly safer than a dead GPU."
            refused=1
            return 0
        fi
        mknod "$node" c "$major" "$minor"
        log "created $node ($major:$minor) — nvidia-modprobe had already run, safe to create"
    else
        # Already there. Was it already correct, or did somebody beat us to it?
        # stat %a prints without a leading zero (660), MODE carries one (0660).
        cur=$(stat -c '%U:%G %a' "$node" 2>/dev/null || echo "?:? ?")
        if [ "$cur" != "root:$GROUP ${MODE#0}" ] && [ "$UDEV_MODE" -eq 0 ]; then
            log "UNGATED NODE FOUND: $node was [$cur], wanted [root:$GROUP ${MODE#0}]. Repaired,"
            log "                    but it was open until this moment."
            log "                    At BOOT this now means 71-luminos-uvm-gate.rules did NOT"
            log "                    fire — check it is installed and udev was reloaded."
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

# [CHANGE: claude-code | 2026-08-29] BUG-149 — /dev/nvidia-modeset, and why it is in the "uvm" gate.
#
# THIS IS A REGRESSION WE CAUSED. BUG-146 stripped the setuid bit from nvidia-modprobe, and a
# pacman hook keeps it stripped. That was correct and must stay. But the setuid helper was the
# ONLY thing on this machine creating /dev/nvidia-modeset: 60-nvidia.rules runs `nvidia-modprobe`
# and `nvidia-modprobe -c0 -u` and NEVER passes -m. Read it, it is four lines. So from BUG-146
# onward the node simply stopped existing, and nothing anywhere said so.
#
# WHAT IT COST — this is the whole of BUG-142, which we spent two days blaming on vkd3d:
#   node absent : vulkaninfo dies on vkGetPhysicalDeviceDisplayPropertiesKHR -> ERROR_UNKNOWN
#   node present: vulkaninfo prints "NVIDIA GeForce RTX 4050 Laptop GPU", clean
# Same binary, same boot, one node apart. Measured 2026-08-29. The AMD control does NOT produce
# that error, so it is NVIDIA-specific and not a vulkaninfo quirk. With the node restored, 007
# First Light ran on the 4050 for minutes at 98-100% GPU with ZERO swapchain failures, where the
# same build had produced 278 failures in 3 s and fallen back to the 780M.
#
# It lives in this script, whose name says "uvm", because this script is already the thing that
# runs as root on the nvidia PCI uevent with the driver's own helper suppressed. A second unit
# would double the moving parts to fix one missing flag. The name is now narrower than the job;
# that is a smaller problem than the node silently going missing again.
#
# Use `nvidia-modprobe -m`, NOT mknod: the minor is a driver convention (254 here), not something
# /proc/devices reports, and the helper is the supported way to ask for this node. Absolute path
# because udev's RUN= environment has no useful PATH. We run as root, so the stripped setuid bit
# does not matter here — that is precisely why this works from the gate but not from a normal app.
modeset_created=0
modeset_failed=0
MODESET_NODE=/dev/nvidia-modeset
if [ ! -e "$MODESET_NODE" ]; then
    /usr/bin/nvidia-modprobe -m || true
    if [ -e "$MODESET_NODE" ]; then
        modeset_created=1
    else
        modeset_failed=1
    fi
fi

# Unlike the UVM nodes, this one IS covered by the driver's NVreg_DeviceFile* params — created by
# hand on 2026-08-29 it came up root:dgpu 660 unaided. So verify rather than assume, and repair
# only if the driver did not. Do NOT delete this check on the grounds that "the param handles it":
# that is exactly what was believed about the UVM nodes before BUG-146, and it was false.
if [ -e "$MODESET_NODE" ]; then
    cur=$(stat -c '%U:%G %a' "$MODESET_NODE" 2>/dev/null || echo "?:? ?")
    if [ "$cur" != "root:$GROUP ${MODE#0}" ]; then
        log "$MODESET_NODE was [$cur], wanted [root:$GROUP ${MODE#0}] — repairing"
        chown "root:$gid" "$MODESET_NODE"
        chmod "$MODE" "$MODESET_NODE"
    fi
fi

# In --udev mode this runs on every PCI add/bind for the card, so keep it to one line and
# do not stat nodes that the guard above may have deliberately left absent.
if [ -e /dev/nvidia-uvm ] && [ -e /dev/nvidia-uvm-tools ]; then
    log "gated: $(stat -c '%n %U:%G %a' /dev/nvidia-uvm /dev/nvidia-uvm-tools | tr '\n' ' ')"
else
    log "gated: nothing to gate — UVM nodes absent (see REFUSING above)"
fi

# [CHANGE: claude-code | 2026-08-29] BUG-149 — reported on its own line, not folded into the one
# above, because "created" is the INTERESTING outcome here and the opposite of what it means for
# the UVM nodes. At boot, created is EXPECTED: nothing else makes this node any more. Silence
# means it already existed, which mid-session is normal and at boot would mean something else
# started creating it — worth noticing, not worth failing on.
if [ "$modeset_created" -eq 1 ]; then
    log "modeset: created $MODESET_NODE $(stat -c '%U:%G %a' "$MODESET_NODE") — BUG-149, 60-nvidia.rules never asks for it"
fi

if [ "$modeset_failed" -eq 1 ]; then
    log "FAILED: $MODESET_NODE is ABSENT and 'nvidia-modprobe -m' did not create it. NVIDIA Vulkan"
    log "        will fail every display/presentation call with a bare ERROR_UNKNOWN and 007 will"
    log "        fall back to the 780M — that is BUG-142/BUG-149, and it will look like a vkd3d"
    log "        bug rather than a missing device node. Check the nvidia_modeset module is loaded"
    log "        ('lsmod | grep nvidia_modeset') and that /usr/bin/nvidia-modprobe exists."
    exit 1
fi

if [ "$refused" -eq 1 ]; then
    log "FAILED: one or both UVM nodes are ABSENT and this run refused to create them, because"
    log "        $MAIN_NODE is missing and creating them first would suppress nvidia-modprobe"
    log "        and leave the card with no device node at all. Fix the cause: run"
    log "        'nvidia-modprobe -c0' to make $MAIN_NODE, then run this again."
    exit 1
fi

if [ "$raced" -eq 1 ] && [ "$UDEV_MODE" -eq 0 ]; then
    log "FAILED: the nodes are correct NOW, but this run had to repair them rather than find"
    log "        them already gated. With 71-luminos-uvm-gate.rules installed the expected"
    log "        boot outcome is 'already correct'; a repair here means that rule did not"
    log "        fire. Check it exists and that udev was reloaded. If this appears MID-SESSION"
    log "        it is BUG-146 re-opening them at runtime instead."
    exit 1
fi

exit 0
