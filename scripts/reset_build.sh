#!/bin/bash
set -euo pipefail

# ============================================================================
# Luminos OS — Safe Stage Reset
# ============================================================================
# Removes flag files and artifacts for specific stages so smart_build.sh
# will re-execute them on next run.
#
# Usage:
#   reset_build.sh <stage_number>   Reset a single stage
#   reset_build.sh all              Full clean reset
#
# Examples:
#   reset_build.sh 3   → reruns strip_ubuntu.sh only
#   reset_build.sh 4   → reruns install_luminos.sh only
#   reset_build.sh 5   → reruns system configuration + kernel
#   reset_build.sh 7   → rebuilds squashfs only
#   reset_build.sh 8   → rebuilds ISO only
#   reset_build.sh all → full clean reset (removes chroot + ISO)
# ============================================================================

BUILD_DIR="$(pwd)/build"
CHROOT_DIR="$BUILD_DIR/chroot"
ISO_DIR="$BUILD_DIR/iso"
OUTPUT_ISO="$BUILD_DIR/luminos-os-v0.1.0.iso"

umount_chroot() {
  local chroot=$1
  for mnt in \
    "$chroot/dev/pts" \
    "$chroot/dev/shm" \
    "$chroot/dev/mqueue" \
    "$chroot/dev/hugepages" \
    "$chroot/dev" \
    "$chroot/proc" \
    "$chroot/sys/fs/cgroup" \
    "$chroot/sys" \
    "$chroot/run"; do
    mountpoint -q "$mnt" 2>/dev/null && umount -lf "$mnt" 2>/dev/null || true
  done
  sleep 1
}

safe_rm_chroot() {
  local chroot=$1
  [ -z "$chroot" ] && return 0
  [ "$chroot" = "/" ] && return 0
  [ ! -d "$chroot" ] && return 0

  echo "Unmounting chroot..."
  umount_chroot "$chroot"

  # Verify nothing is still mounted
  if mountpoint -q "$chroot/proc" 2>/dev/null; then
    echo "ERROR: /proc still mounted — cannot safely remove chroot"
    echo "Try: sudo umount -lf $chroot/proc"
    exit 1
  fi

  echo "Removing chroot directory..."
  rm -rf "$chroot"
  echo "Chroot removed."
}

if [ $# -ne 1 ]; then
  echo "Usage: reset_build.sh <stage_number|all>"
  echo ""
  echo "Stages:"
  echo "  1   Bootstrap (debootstrap) — resets everything"
  echo "  2   Prepare chroot (mounts + source copy)"
  echo "  3   Strip Ubuntu + install Sway stack"
  echo "  4   Install Luminos components"
  echo "  5   Configure system (kernel, locale, user)"
  echo "  6   Cleanup chroot"
  echo "  7   Build squashfs"
  echo "  8   Build ISO"
  echo "  all Full clean reset"
  exit 1
fi

STAGE=$1

case "$STAGE" in
  1)
    echo "=== Resetting Stage 1: Bootstrap ==="
    echo "WARNING: This removes the entire chroot and resets ALL stages."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0
    safe_rm_chroot "$CHROOT_DIR"
    rm -f "$ISO_DIR/casper/filesystem.squashfs" 2>/dev/null || true
    rm -f "$OUTPUT_ISO" 2>/dev/null || true
    echo "RESET: Stage 1 (and all downstream stages)"
    ;;
  2)
    echo "=== Resetting Stage 2: Prepare ==="
    rm -f "$CHROOT_DIR/.stage2_done" 2>/dev/null || true
    rm -rf "$CHROOT_DIR/luminos-build" 2>/dev/null || true
    echo "RESET: Stage 2 — source will be re-copied on next build"
    ;;
  3)
    echo "=== Resetting Stage 3: Strip Ubuntu ==="
    rm -f "$CHROOT_DIR/.strip_done" 2>/dev/null || true
    echo "RESET: Stage 3 — strip_ubuntu.sh will rerun"
    echo "NOTE: Packages already installed won't be reinstalled (apt is idempotent)"
    ;;
  4)
    echo "=== Resetting Stage 4: Install Luminos ==="
    rm -f "$CHROOT_DIR/.luminos_installed" 2>/dev/null || true
    # Also reset stage 2 so source is re-copied
    rm -f "$CHROOT_DIR/.stage2_done" 2>/dev/null || true
    echo "RESET: Stage 4 — install_luminos.sh will rerun"
    echo "NOTE: Also reset stage 2 so latest source is copied"
    ;;
  5)
    echo "=== Resetting Stage 5: Configure ==="
    rm -f "$CHROOT_DIR/.stage5_done" 2>/dev/null || true
    echo "RESET: Stage 5 — system configuration will rerun"
    ;;
  6)
    echo "=== Resetting Stage 6: Cleanup ==="
    rm -f "$CHROOT_DIR/.stage6_done" 2>/dev/null || true
    echo "RESET: Stage 6 — cleanup will rerun"
    ;;
  7)
    echo "=== Resetting Stage 7: Squashfs ==="
    rm -f "$ISO_DIR/casper/filesystem.squashfs" 2>/dev/null || true
    rm -f "$ISO_DIR/casper/filesystem.size" 2>/dev/null || true
    # Also reset cleanup so chroot is clean before re-squashing
    rm -f "$CHROOT_DIR/.stage6_done" 2>/dev/null || true
    echo "RESET: Stage 7 — squashfs will be rebuilt"
    echo "NOTE: Also reset stage 6 so chroot is cleaned first"
    ;;
  8)
    echo "=== Resetting Stage 8: ISO ==="
    rm -f "$OUTPUT_ISO" 2>/dev/null || true
    echo "RESET: Stage 8 — ISO will be rebuilt"
    ;;
  all)
    echo "=== Full Clean Reset ==="
    echo "WARNING: This removes chroot, squashfs, and ISO."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0
    safe_rm_chroot "$CHROOT_DIR"
    rm -rf "$ISO_DIR" 2>/dev/null || true
    rm -f "$OUTPUT_ISO" 2>/dev/null || true
    mkdir -p "$BUILD_DIR"
    echo "RESET: All stages — full clean build on next run"
    ;;
  *)
    echo "ERROR: Unknown stage '$STAGE'"
    echo "Valid: 1-8 or 'all'"
    exit 1
    ;;
esac

echo ""
echo "Now run: sudo bash scripts/smart_build.sh"
