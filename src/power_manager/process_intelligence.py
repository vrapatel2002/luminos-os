"""
process_intelligence.py
Lightweight process inspection for PowerBrain decision-making.

Rules:
- has_audio() checks /proc fd symlinks — no psutil, no external tools.
- is_gaming_running() scans /proc cmdlines — stdlib only.
- get_foreground_pid() reads /tmp/luminos-focus.pid — written by compositor.
- All functions return False/None on any error. Never raises.
"""

import logging
import os

logger = logging.getLogger("luminos-ai.power_manager.process")

# Signals that indicate a gaming process
_GAME_SIGNALS = [
    "steam", "lutris", "heroic", "gamemode", "gamescope", ".exe",
]

# Audio device / socket path fragments
_AUDIO_SIGNALS = [
    "/dev/snd/",
    "pulse",
    "pipewire",
]


def has_audio(pid: int) -> bool:
    """
    Check whether a process has audio device or socket file descriptors open.

    Reads /proc/{pid}/fd/ and checks symlink targets for audio signals.

    Returns:
        True if audio FDs found, False on any error or absence.
    """
    fd_dir = f"/proc/{pid}/fd"
    try:
        entries = os.listdir(fd_dir)
    except OSError:
        return False

    for entry in entries:
        fd_path = os.path.join(fd_dir, entry)
        try:
            target = os.readlink(fd_path)
        except OSError:
            continue
        for signal in _AUDIO_SIGNALS:
            if signal in target:
                logger.debug(f"has_audio({pid}): found {target!r}")
                return True

    return False


def is_gaming_running() -> bool:
    """
    Scan /proc/*/cmdline for game process signals.

    Returns:
        True if any gaming-related process is found, False otherwise.
    """
    try:
        pids = [
            d for d in os.listdir("/proc")
            if d.isdigit()
        ]
    except OSError:
        return False

    for pid_str in pids:
        cmdline_path = f"/proc/{pid_str}/cmdline"
        try:
            with open(cmdline_path, "rb") as f:
                raw = f.read(512)
            cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").lower()
            for signal in _GAME_SIGNALS:
                if signal in cmdline:
                    logger.debug(f"is_gaming_running: found {signal!r} in pid {pid_str}")
                    return True
        except OSError:
            continue

    return False


def get_foreground_pid() -> int | None:
    """
    Read the currently focused window's PID from /tmp/luminos-focus.pid.

    Written by the compositor layer when focus changes.

    Returns:
        PID as int, or None if file missing/unreadable.
    """
    focus_path = "/tmp/luminos-focus.pid"
    try:
        with open(focus_path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None
