"""
ac_monitor.py
Reads AC adapter and battery state from /sys/class/power_supply/.

Rules:
- All reads are graceful — None returned if path missing or unreadable.
- discharge_rate_w and minutes_remaining are None on AC or if not available.
- power_now is in microwatts on most Linux kernels; divide by 1e6 for watts.
- energy_now is in microjoules; divide by 1e6 for watt-hours.
- Never raises.
"""

import glob
import logging

logger = logging.getLogger("luminos-ai.power_manager.ac")


def _read_first(pattern: str) -> str | None:
    """Read the first file matching glob pattern. Returns stripped string or None."""
    paths = sorted(glob.glob(pattern))
    for path in paths:
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            continue
    return None


def _read_int(pattern: str) -> int | None:
    """Read first matching file as int, or None."""
    raw = _read_first(pattern)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_ac_status() -> dict:
    """
    Read AC adapter and battery state from /sys/class/power_supply/.

    Returns:
        {
            "plugged_in":        bool,        # AC online
            "battery_percent":   int|None,    # 0-100
            "battery_status":    str|None,    # "Charging", "Discharging", "Full", ...
            "discharge_rate_w":  float|None,  # Watts drawn from battery
            "minutes_remaining": int|None,    # Estimated time left on battery
        }
    """
    # AC adapter
    ac_raw = _read_int("/sys/class/power_supply/AC*/online")
    # Also check ACAD (some ASUS/Lenovo), ADP1, etc.
    if ac_raw is None:
        ac_raw = _read_int("/sys/class/power_supply/ADP*/online")
    plugged_in = bool(ac_raw) if ac_raw is not None else True  # assume plugged if unknown

    # Battery capacity
    battery_percent = _read_int("/sys/class/power_supply/BAT*/capacity")

    # Battery status string
    battery_status = _read_first("/sys/class/power_supply/BAT*/status")

    # Discharge rate — power_now is in microwatts
    power_now_uw = _read_int("/sys/class/power_supply/BAT*/power_now")
    discharge_rate_w: float | None = None
    if power_now_uw is not None and power_now_uw > 0:
        discharge_rate_w = round(power_now_uw / 1_000_000.0, 2)

    # Minutes remaining: energy_now (µWh) / power_now (µW) * 60
    minutes_remaining: int | None = None
    energy_now_uwh = _read_int("/sys/class/power_supply/BAT*/energy_now")
    if (
        not plugged_in
        and energy_now_uwh is not None
        and power_now_uw is not None
        and power_now_uw > 0
    ):
        hours = energy_now_uwh / power_now_uw
        minutes_remaining = int(hours * 60)

    logger.debug(
        f"AC status: plugged={plugged_in} bat={battery_percent}% "
        f"rate={discharge_rate_w}W mins={minutes_remaining}"
    )
    return {
        "plugged_in":        plugged_in,
        "battery_percent":   battery_percent,
        "battery_status":    battery_status,
        "discharge_rate_w":  discharge_rate_w,
        "minutes_remaining": minutes_remaining,
    }
