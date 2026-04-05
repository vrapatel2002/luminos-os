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
# 1b. GPU guard — assert Hybrid mode before anything else
# ----------------------------------------------------------------
log "Checking GPU mode..."
python3 -c "
import sys; sys.path.insert(0, '${SRC_DIR}')
from hardware.gpu_guard import assert_hybrid_mode
result = assert_hybrid_mode()
if result['is_hybrid']:
    print('[gpu_guard] Hybrid mode verified')
elif result['available']:
    print('[gpu_guard] WARNING: GPU mode is not Hybrid')
else:
    print('[gpu_guard] supergfxctl not available')
" 2>&1 | while read -r line; do log "$line"; done

# ----------------------------------------------------------------
# 1c. Apply hardware boot defaults (fan curve + battery limit)
# ----------------------------------------------------------------
log "Applying hardware boot defaults..."
python3 -c "
import sys; sys.path.insert(0, '${SRC_DIR}')
from hardware.asus_controller import AsusController
asus = AsusController()
result = asus.apply_boot_defaults()
print(f'Hardware defaults applied: {result}')
" 2>&1 | while read -r line; do log "$line"; done || true

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

# ----------------------------------------------------------------
# 4. Start power & thermal wiring
# ----------------------------------------------------------------
log "Starting power and thermal wiring..."
python3 -c "
import sys; sys.path.insert(0, '${SRC_DIR}')
from hardware.asus_controller import AsusController
from hardware.thermal_monitor import ThermalMonitor
from hardware.power_events import PowerEventBus
from hardware.battery_monitor import BatteryMonitor
from hardware.display_manager import DisplayManager

asus = AsusController()
thermal = ThermalMonitor(asus_controller=asus)
power_bus = PowerEventBus(thermal_monitor=thermal)
battery = BatteryMonitor()
display = DisplayManager()

thermal.start()
power_bus.start()
battery.start()
display.start()
print('Power, thermal, battery, and display managers started')

# Block — these are daemon threads, keep the process alive
import signal, threading
evt = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: evt.set())
signal.signal(signal.SIGINT, lambda *_: evt.set())
evt.wait()

thermal.stop()
power_bus.stop()
battery.stop()
display.stop()
print('Power subsystems stopped')
" 2>&1 | while read -r line; do log "$line"; done &

log "Session ready."

# Keep session alive (replace with sway/compositor if needed)
wait
