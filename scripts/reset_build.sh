#!/bin/bash
set -euo pipefail

# ============================================================================
# Luminos OS — Safe Stage Reset (archiso workflow)
# ============================================================================
# Removes flag files and artifacts for specific stages so smart_build.sh
# will re-execute them on next run.
#
# Usage:
#   reset_build.sh <stage_number>   Reset a single stage
#   reset_build.sh all              Full clean reset
#
# Examples:
#   reset_build.sh 1   → recreates archiso profile
#   reset_build.sh 2   → reruns airootfs customization
#   reset_build.sh 3   → re-copies Luminos configs and source
#   reset_build.sh 4   → rebuilds ISO
#   reset_build.sh all → full clean reset (removes everything)
# ============================================================================

BUILD_DIR="$(pwd)/build"
PROFILE_DIR="$BUILD_DIR/luminos-profile"
WORK_DIR="$BUILD_DIR/work"
OUTPUT_DIR="$BUILD_DIR/out"

if [ $# -ne 1 ]; then
  echo "Usage: reset_build.sh <stage_number|all>"
  echo ""
  echo "Stages:"
  echo "  1   Profile (archiso package list)"
  echo "  2   Customize (users, services, dirs)"
  echo "  3   Configs (Luminos source + desktop configs)"
  echo "  4   Build ISO (mkarchiso)"
  echo "  all Full clean reset"
  exit 1
fi

STAGE=$1

case "$STAGE" in
  1)
    echo "=== Resetting Stage 1: Profile ==="
    echo "WARNING: This removes the profile and resets all downstream stages."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0
    rm -rf "$PROFILE_DIR"
    rm -rf "$WORK_DIR"
    rm -rf "$OUTPUT_DIR"
    rm -f "$BUILD_DIR"/.stage*_done
    echo "RESET: Stage 1 (and all downstream stages)"
    ;;
  2)
    echo "=== Resetting Stage 2: Customize ==="
    rm -f "$BUILD_DIR/.stage2_customize_done"
    rm -f "$BUILD_DIR/.stage3_configs_done"
    rm -f "$BUILD_DIR/.stage4_iso_done"
    rm -rf "$WORK_DIR"
    rm -rf "$OUTPUT_DIR"
    echo "RESET: Stage 2 — airootfs will be re-customized"
    ;;
  3)
    echo "=== Resetting Stage 3: Configs ==="
    rm -f "$BUILD_DIR/.stage3_configs_done"
    rm -f "$BUILD_DIR/.stage4_iso_done"
    rm -rf "$WORK_DIR"
    rm -rf "$OUTPUT_DIR"
    echo "RESET: Stage 3 — Luminos configs will be re-copied"
    ;;
  4)
    echo "=== Resetting Stage 4: ISO ==="
    rm -f "$BUILD_DIR/.stage4_iso_done"
    rm -rf "$WORK_DIR"
    rm -rf "$OUTPUT_DIR"
    echo "RESET: Stage 4 — ISO will be rebuilt"
    ;;
  all)
    echo "=== Full Clean Reset ==="
    echo "WARNING: This removes the profile, work dir, and ISO output."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0
    rm -rf "$PROFILE_DIR"
    rm -rf "$WORK_DIR"
    rm -rf "$OUTPUT_DIR"
    rm -f "$BUILD_DIR"/.stage*_done
    echo "RESET: All stages — full clean build on next run"
    ;;
  *)
    echo "ERROR: Unknown stage '$STAGE'"
    echo "Valid: 1-4 or 'all'"
    exit 1
    ;;
esac

echo ""
echo "Now run: sudo bash scripts/smart_build.sh"
