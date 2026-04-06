#!/usr/bin/env bash
# scripts/luminos-session.sh
# Phase 5.12 — Luminos session startup with timing + crash recovery.
#
# Called by luminos-session.service on user login.
# Order:
#   T0: session script starts → record timing
#   1.  Check first-run wizard
#   2.  GPU guard
#   3.  Hardware boot defaults
#   4.  Start AI daemon
#   T1: Launch Hyprland
#   T2: Login screen visible (greetd handles this, mark after)
#   5.  Desktop components (bar, dock, wallpaper)
#   T3: Desktop fully loaded
#   6.  Power & thermal wiring
#
# Crash recovery: if Hyprland exits non-zero, restart once within 30s.
# If second crash within 30s: drop to TTY with error.

set -uo pipefail

LUMINOS_FLAG="${HOME}/.config/luminos/first_run_complete"
LUMINOS_SOCK="/run/luminos/ai.sock"
SRC_DIR="$(dirname "$(readlink -f "$0")")/../src"
CRASH_LOG="${HOME}/.local/share/luminos/crash.log"

log() { echo "[luminos-session] $*" >&2; }

# ----------------------------------------------------------------
# T0 — Record session start time
# ----------------------------------------------------------------
python3 -c "
import sys; sys.path.insert(0, '${SRC_DIR}')
try:
    from startup.startup_timer import record_stage
    record_stage('T0')
except Exception: pass
" 2>/dev/null || true

log "Session starting."

# ----------------------------------------------------------------
# 1. First-run check
# ----------------------------------------------------------------
if [ ! -f "${LUMINOS_FLAG}" ]; then
    log "First run not complete — launching setup wizard."
    if command -v luminos-firstrun &>/dev/null; then
        luminos-firstrun
    else
        python3 -m gui.firstrun.firstrun_app 2>/dev/null || true
    fi
    log "First run complete. Continuing session."
fi

# ----------------------------------------------------------------
# 2. GPU guard — assert Hybrid mode
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
" 2>&1 | while read -r line; do log "$line"; done || true

# ----------------------------------------------------------------
# 3. Apply hardware boot defaults (fan curve + battery limit)
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
# 4. Start AI daemon if not running
# ----------------------------------------------------------------
if [ ! -S "${LUMINOS_SOCK}" ]; then
    log "Daemon socket not found — starting luminos-ai.service."
    systemctl --user start luminos-ai.service 2>/dev/null || \
        python3 "${SRC_DIR}/daemon/main.py" &
fi

# ----------------------------------------------------------------
# T1 — Record Hyprland launch time
# ----------------------------------------------------------------
python3 -c "
import sys; sys.path.insert(0, '${SRC_DIR}')
try:
    from startup.startup_timer import record_stage
    record_stage('T1')
except Exception: pass
" 2>/dev/null || true

# ----------------------------------------------------------------
# 5. Launch desktop components
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

# Wallpaper
if command -v swww-daemon &>/dev/null; then
    swww-daemon &
    sleep 0.5
    WALLPAPER_CONF="${HOME}/.config/luminos/wallpaper.json"
    if [ -f "${WALLPAPER_CONF}" ]; then
        WALLPAPER_TYPE=$(python3 -c \
            "import json; c=json.load(open('${WALLPAPER_CONF}')); print(c.get('type','color'))" \
            2>/dev/null || echo "color")
        WALLPAPER_VAL=$(python3 -c \
            "import json; c=json.load(open('${WALLPAPER_CONF}')); print(c.get('value',''))" \
            2>/dev/null || echo "")
        if [ "${WALLPAPER_TYPE}" = "image" ] && [ -n "${WALLPAPER_VAL}" ] && [ -f "${WALLPAPER_VAL}" ]; then
            swww img "${WALLPAPER_VAL}" --transition-type fade --transition-duration 1 || true
        elif [ "${WALLPAPER_TYPE}" = "live" ] && [ -n "${WALLPAPER_VAL}" ]; then
            luminos-live-wallpaper --preset "${WALLPAPER_VAL}" --intensity low &>/dev/null &
        fi
    fi
fi

# ----------------------------------------------------------------
# T3 — Record desktop fully loaded
# ----------------------------------------------------------------
python3 -c "
import sys; sys.path.insert(0, '${SRC_DIR}')
try:
    from startup.startup_timer import record_stage, load_timings, write_log_entry, compute_summary
    record_stage('T3')
    timings = load_timings()
    write_log_entry(timings)
    summary = compute_summary(timings)
    total = summary.get('total_seconds')
    if total is not None:
        status = 'OK' if summary['met_target'] else 'SLOW'
        print(f'Startup time: {total:.2f}s ({status})')
except Exception as e:
    print(f'Startup timer error: {e}')
" 2>&1 | while read -r line; do log "$line"; done || true

# ----------------------------------------------------------------
# 6. Start power & thermal wiring (background)
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

import signal, threading
evt = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: evt.set())
signal.signal(signal.SIGINT, lambda *_: evt.set())
evt.wait()

thermal.stop()
power_bus.stop()
battery.stop()
display.stop()
" 2>&1 | while read -r line; do log "$line"; done &

log "Session ready."

# ----------------------------------------------------------------
# Crash recovery — monitor Hyprland exit
# ----------------------------------------------------------------
_hyprland_pid=""
_crash_time_1=0

_launch_hyprland() {
    if command -v Hyprland &>/dev/null; then
        Hyprland &
        _hyprland_pid=$!
    fi
}

_log_crash() {
    local reason="$1"
    mkdir -p "$(dirname "${CRASH_LOG}")"
    echo "$(date -Iseconds) | Hyprland crash | ${reason}" >> "${CRASH_LOG}" || true
}

# Check if Hyprland is managed separately (greetd etc.)
if command -v Hyprland &>/dev/null && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    log "Launching Hyprland with crash recovery..."
    _launch_time=$(date +%s)
    _crash_count=0

    while true; do
        Hyprland || _exit_code=$?
        _exit_code=${_exit_code:-0}

        if [ "${_exit_code}" -eq 0 ]; then
            # Clean exit — user logged out
            log "Hyprland exited cleanly. Session ending."
            break
        fi

        # Crash — decide whether to retry
        _now=$(date +%s)
        log "Hyprland crashed (exit=${_exit_code}). Attempting restart..."
        _log_crash "exit=${_exit_code}"

        if [ $((_now - _launch_time)) -le 30 ] && [ "${_crash_count}" -ge 1 ]; then
            # Second crash within 30s — drop to TTY
            log "Second crash within 30 seconds. Dropping to TTY."
            _log_crash "second crash within 30s — dropping to TTY"
            printf "\n\n\033[31m[Luminos] Hyprland crashed twice in 30 seconds.\033[0m\n"
            printf "Log: %s\n\n" "${CRASH_LOG}"
            break
        fi

        _crash_count=$((_crash_count + 1))
        _launch_time=${_now}
        log "Restarting Hyprland in 2 seconds..."
        sleep 2
    done
fi

# Keep session alive
wait
