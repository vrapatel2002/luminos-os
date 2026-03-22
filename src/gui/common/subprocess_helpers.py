"""
src/gui/common/subprocess_helpers.py
Safe subprocess wrappers for tray widget data collection.

Rules:
- run_cmd() never raises — catches all exceptions, returns None on failure.
- All parse functions return sensible defaults on error.
- Timeouts are short (2s default) to avoid blocking the GTK event loop.
"""

import logging
import re
import subprocess

logger = logging.getLogger("luminos-ai.gui.subprocess")


def run_cmd(cmd: list, timeout: float = 2.0) -> str | None:
    """
    Run a subprocess command and return its stdout as a string.

    Args:
        cmd:     Command as a list of strings.
        timeout: Maximum seconds to wait (default 2.0).

    Returns:
        stdout string (may include trailing newline), or None on any error.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout
        logger.debug(f"run_cmd {cmd[0]!r} returned code {result.returncode}")
        return None
    except FileNotFoundError:
        logger.debug(f"Command not found: {cmd[0]!r}")
        return None
    except subprocess.TimeoutExpired:
        logger.debug(f"Command timed out: {cmd[0]!r}")
        return None
    except Exception as e:
        logger.debug(f"run_cmd error: {e}")
        return None


def get_wifi_info() -> dict:
    """
    Query WiFi connection state via nmcli.

    Returns:
        {
            "connected": bool,
            "ssid":      str|None,
            "signal":    int|None,   # 0-100
        }
    """
    out = run_cmd(
        ["nmcli", "-t", "-f", "active,signal,ssid", "dev", "wifi", "list"],
        timeout=2.0,
    )
    if out is None:
        return {"connected": False, "ssid": None, "signal": None}

    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[0].strip().lower() == "yes":
            try:
                signal = int(parts[1].strip())
                ssid   = ":".join(parts[2:]).strip()
                return {"connected": True, "ssid": ssid or None, "signal": signal}
            except (ValueError, IndexError):
                continue

    return {"connected": False, "ssid": None, "signal": None}


def get_bluetooth_powered() -> bool:
    """
    Check whether the system Bluetooth adapter is powered on.

    Runs `bluetoothctl show` and checks for "Powered: yes".

    Returns:
        True if BT is powered, False on error or powered off.
    """
    out = run_cmd(["bluetoothctl", "show"], timeout=2.0)
    if out is None:
        return False
    return "powered: yes" in out.lower()


def get_volume() -> dict:
    """
    Query the default PulseAudio/PipeWire sink volume via pactl.

    Returns:
        {
            "percent": int,   # 0-100
            "muted":   bool,
        }
    """
    out = run_cmd(
        ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
        timeout=2.0,
    )
    percent = 0
    muted   = False

    if out:
        # Parse "Volume: front-left: 65536 / 100% ..."
        m = re.search(r"(\d+)%", out)
        if m:
            percent = int(m.group(1))

    # Separate mute query
    mute_out = run_cmd(
        ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
        timeout=2.0,
    )
    if mute_out:
        muted = "yes" in mute_out.lower()

    return {"percent": percent, "muted": muted}


def set_volume(percent: int) -> bool:
    """
    Set the default sink volume to the given percentage.

    Args:
        percent: Target volume 0-100.

    Returns:
        True on success, False on error.
    """
    percent = max(0, min(100, percent))
    out = run_cmd(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"],
        timeout=2.0,
    )
    return out is not None


def toggle_mute() -> bool:
    """
    Toggle mute on the default PulseAudio/PipeWire sink.

    Returns:
        True on success, False on error.
    """
    out = run_cmd(
        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
        timeout=2.0,
    )
    return out is not None
