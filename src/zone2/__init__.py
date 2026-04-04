"""
src/zone2/__init__.py
Public API for the Luminos Zone 2 Wine/Proton execution layer.

Usage:
    from zone2 import run_in_zone2
    result = run_in_zone2("/path/to/game.exe")
    # {"success": True, "pid": 12345, "runner": "wine", "cmd": [...], "prefix": "..."}
"""

import logging

from .prefix_manager import get_prefix_path, ensure_prefix_exists
from .wine_runner import (
    launch_windows_app,
    launch_with_lutris,
    detect_wine,
    detect_lutris,
)

logger = logging.getLogger("luminos-ai.zone2")


def _report_to_daemon(result: dict) -> None:
    """Best-effort report of launch result to the Luminos daemon via Unix socket."""
    try:
        from gui.common.socket_client import DaemonClient
        client = DaemonClient()
        client.send({
            "type":    "zone2_launch_result",
            "success": result.get("success", False),
            "runner":  result.get("runner"),
            "pid":     result.get("pid"),
            "prefix":  result.get("prefix"),
        })
    except Exception as e:
        logger.debug(f"Daemon report skipped: {e}")


def run_in_zone2(exe_path: str, runner: str = "auto") -> dict:
    """
    Full Zone 2 pipeline:
      1. Compute a unique Wine prefix for this exe.
      2. Create the prefix directory if it does not exist.
      3. Launch the exe under Wine/Proton/Lutris with the isolated prefix.
      4. Report result to daemon.

    Args:
        exe_path: Path to the Windows executable.
        runner:   "wine", "proton", "lutris", or "auto" (detect best).

    Returns:
        On success:
            {"success": True, "pid": int, "runner": "wine"|"proton"|"lutris",
             "cmd": list, "prefix": str}
        On failure:
            {"success": False, "error": str, ...}
    """
    prefix_path = get_prefix_path(exe_path)
    ensure_prefix_exists(prefix_path)

    if runner == "lutris":
        result = launch_with_lutris(exe_path)
    else:
        env_overrides = {"WINEPREFIX": prefix_path}

        # If caller requests proton specifically, try to force it
        if runner == "proton":
            from .wine_runner import _find_proton
            proton_path, proton_ver = _find_proton()
            if proton_path:
                wine_info = {
                    "available": True,
                    "path": proton_path,
                    "type": "proton",
                    "version": proton_ver,
                }
                from .wine_runner import build_wine_command
                import subprocess
                command_info = build_wine_command(exe_path, wine_info, env_overrides)
                try:
                    proc = subprocess.Popen(
                        command_info["cmd"],
                        env=command_info["env"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    result = {
                        "success": True,
                        "pid": proc.pid,
                        "runner": "proton",
                        "cmd": command_info["cmd"],
                    }
                except (FileNotFoundError, OSError) as e:
                    result = {"success": False, "error": str(e)}
            else:
                result = {
                    "success": False,
                    "error": "Proton not found",
                    "install_hint": "yay -S proton-ge-custom",
                }
        else:
            result = launch_windows_app(exe_path, env_overrides=env_overrides)

    result["prefix"] = prefix_path
    _report_to_daemon(result)
    return result
