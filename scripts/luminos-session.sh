#!/usr/bin/env bash
# scripts/luminos-session.sh
# Luminos session startup script.
#
# Called by luminos-session.service on user login.
# Order:
#   1. Check if first-run setup is complete.
#   2. If not → launch first-run wizard (blocks until complete).
#   3. Start luminos-ai daemon if not running.
#   4. Launch bar + dock + wallpaper daemon.
#
# NOTE: First-run detection happens here (not in luminos-ai.service).
# luminos-ai.service starts before login and should not touch the GUI.

set -euo pipefail

LUMINOS_FLAG="${HOME}/.config/luminos/.setup_complete"
LUMINOS_SOCK="/run/luminos/ai.sock"
SRC_DIR="$(dirname "$(readlink -f "$0")")/../src"

log() { echo "[luminos-session] $*" >&2; }

# ----------------------------------------------------------------
# 1. First-run check
# ----------------------------------------------------------------
if [ ! -f "${LUMINOS_FLAG}" ]; then
    log "First run not complete — launching setup wizard."
    if command -v luminos-firstrun &>/dev/null; then
        luminos-firstrun
    else
        # Dev fallback
        python3 -m gui.firstrun.firstrun_app || true
    fi
    log "First run complete. Continuing session."
fi

# ----------------------------------------------------------------
# 2. Start AI daemon if not running
# ----------------------------------------------------------------
if [ ! -S "${LUMINOS_SOCK}" ]; then
    log "Daemon socket not found — starting luminos-ai.service."
    systemctl --user start luminos-ai.service 2>/dev/null || \
        python3 "${SRC_DIR}/daemon/main.py" &
fi

# ----------------------------------------------------------------
# 3. Launch desktop components
# ----------------------------------------------------------------
log "Starting Luminos desktop components."

if command -v luminos-bar &>/dev/null; then
    luminos-bar &
else
    log "luminos-bar not found (install or build first)."
fi

if command -v luminos-dock &>/dev/null; then
    luminos-dock &
else
    log "luminos-dock not found (install or build first)."
fi

# Wallpaper — start swww and apply saved config
if command -v swww-daemon &>/dev/null; then
    swww-daemon &
    sleep 1
    # Apply last wallpaper from config
    WALLPAPER_CONF="${HOME}/.config/luminos/wallpaper.json"
    if [ -f "${WALLPAPER_CONF}" ]; then
        WALLPAPER_TYPE=$(python3 -c \
            "import json; c=json.load(open('${WALLPAPER_CONF}')); print(c.get('type','color'))")
        WALLPAPER_VAL=$(python3 -c \
            "import json; c=json.load(open('${WALLPAPER_CONF}')); print(c.get('value','#1c1c1e'))")
        if [ "${WALLPAPER_TYPE}" = "image" ] && [ -f "${WALLPAPER_VAL}" ]; then
            swww img "${WALLPAPER_VAL}" --transition-type fade --transition-duration 1 || true
        fi
    fi
fi

log "Session ready."

# Keep session alive (replace with sway/compositor if needed)
wait
