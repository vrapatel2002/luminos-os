"""
process_watcher.py
Detect running game processes so the daemon knows when to enter/exit gaming mode.
Reads /proc directly — no psutil.
"""

import os
import logging

logger = logging.getLogger("luminos-ai.gpu_manager.watcher")

# Tokens that identify a gaming process anywhere in the process name or exe path
GAME_SIGNALS: list[str] = [
    "steam",
    "lutris",
    "heroic",
    ".exe",
    "gamemode",
    "gamescope",
]


def is_gaming_process(process_name: str, exe_path: str = "") -> bool:
    """
    Return True if the process name or exe path matches any game signal.

    Args:
        process_name: Process name (e.g. from /proc/<pid>/comm).
        exe_path:     Full executable path (e.g. from /proc/<pid>/exe).
                      Optional — increases detection accuracy for Wine/Proton exes.
    """
    combined = (process_name + " " + exe_path).lower()
    return any(signal in combined for signal in GAME_SIGNALS)


def _read_file(path: str) -> str:
    """Read a /proc file, return empty string on any error."""
    try:
        with open(path, "r") as f:
            return f.read()
    except (OSError, PermissionError):
        return ""


def _get_exe_path(pid: str) -> str:
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except (OSError, PermissionError):
        return ""


def scan_running_games() -> list:
    """
    Scan /proc for processes that look like games.

    Returns:
        List of dicts: [{"pid": int, "name": str}]
        Empty list if none found or /proc is unreadable.
    """
    games = []

    try:
        proc_entries = os.listdir("/proc")
    except OSError:
        return []

    for entry in proc_entries:
        if not entry.isdigit():
            continue
        pid = entry

        # Read process name from comm
        name = _read_file(f"/proc/{pid}/comm").strip()
        if not name:
            # Fall back to cmdline basename
            cmdline_raw = _read_file(f"/proc/{pid}/cmdline")
            if cmdline_raw:
                first_arg = cmdline_raw.split("\x00")[0]
                name = os.path.basename(first_arg)

        exe_path = _get_exe_path(pid)

        if is_gaming_process(name, exe_path):
            try:
                games.append({"pid": int(pid), "name": name})
            except ValueError:
                pass

    return games
