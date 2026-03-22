"""
src/gui/quick_settings/brightness_ctrl.py
AMD backlight brightness control via /sys/class/backlight/amdgpu_bl1.

Rules:
- get_brightness() never raises — returns {"available": False} if path missing.
- set_brightness() clamps to 5-100 (never full dark).
- PermissionError on direct write → pkexec tee fallback.
- brightness_up/down call get → clamp → set → get (return new state).
"""

import logging
import os
import subprocess

logger = logging.getLogger("luminos-ai.gui.quick_settings.brightness")

BACKLIGHT_PATH = "/sys/class/backlight/amdgpu_bl1"

_BRIGHTNESS_FILE     = "brightness"
_MAX_BRIGHTNESS_FILE = "max_brightness"
_MIN_PERCENT         = 5    # never allow full-dark
_MAX_PERCENT         = 100


def _read_int(path: str) -> int | None:
    """Read a single integer from a sysfs file. Returns None on any error."""
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def get_brightness() -> dict:
    """
    Read current backlight brightness from sysfs.

    Returns:
        {
            "current":   int,   # raw sysfs value
            "max":       int,   # max_brightness value
            "percent":   int,   # 0-100
            "available": bool,
        }
        Returns {"available": False} if backlight path does not exist.
    """
    brightness_path = os.path.join(BACKLIGHT_PATH, _BRIGHTNESS_FILE)
    max_path        = os.path.join(BACKLIGHT_PATH, _MAX_BRIGHTNESS_FILE)

    if not os.path.exists(BACKLIGHT_PATH):
        return {"available": False}

    current = _read_int(brightness_path)
    maximum = _read_int(max_path)

    if current is None or maximum is None or maximum == 0:
        return {"available": False}

    percent = round(current / maximum * 100)
    return {
        "current":   current,
        "max":       maximum,
        "percent":   min(100, max(0, percent)),
        "available": True,
    }


def set_brightness(percent: int) -> bool:
    """
    Set backlight brightness to the given percentage.

    Args:
        percent: Target brightness 5-100 (clamped — never below 5).

    Returns:
        True on success, False on failure.
    """
    percent = max(_MIN_PERCENT, min(_MAX_PERCENT, percent))

    max_path        = os.path.join(BACKLIGHT_PATH, _MAX_BRIGHTNESS_FILE)
    brightness_path = os.path.join(BACKLIGHT_PATH, _BRIGHTNESS_FILE)

    maximum = _read_int(max_path)
    if maximum is None or maximum == 0:
        logger.debug("set_brightness: max_brightness unreadable")
        return False

    value = round(percent / 100 * maximum)
    value = max(1, value)   # sysfs value must be ≥ 1

    # Direct write attempt
    try:
        with open(brightness_path, "w") as f:
            f.write(str(value))
        return True
    except PermissionError:
        pass   # fall through to pkexec
    except OSError as e:
        logger.debug(f"set_brightness direct write failed: {e}")
        return False

    # pkexec tee fallback (prompts polkit once per session)
    try:
        result = subprocess.run(
            ["pkexec", "tee", brightness_path],
            input=str(value),
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if result.returncode == 0:
            return True
        logger.debug(f"pkexec tee returned {result.returncode}")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug(f"pkexec brightness fallback failed: {e}")

    return False


def brightness_up(step: int = 10) -> dict:
    """
    Increase brightness by step percent.

    Args:
        step: Percent to add (default 10).

    Returns:
        New brightness status dict from get_brightness().
    """
    status = get_brightness()
    if not status.get("available"):
        return status
    new_pct = min(_MAX_PERCENT, status["percent"] + step)
    set_brightness(new_pct)
    return get_brightness()


def brightness_down(step: int = 10) -> dict:
    """
    Decrease brightness by step percent, clamped to MIN_PERCENT.

    Args:
        step: Percent to subtract (default 10).

    Returns:
        New brightness status dict from get_brightness().
    """
    status = get_brightness()
    if not status.get("available"):
        return status
    new_pct = max(_MIN_PERCENT, status["percent"] - step)
    set_brightness(new_pct)
    return get_brightness()
