"""
src/zone2/__init__.py
Public API for the Luminos Zone 2 Wine/Proton execution layer.

Usage:
    from zone2 import run_in_zone2
    result = run_in_zone2("/path/to/game.exe")
    # {"success": True, "pid": 12345, "runner": "wine", "cmd": [...], "prefix": "..."}
"""

from .prefix_manager import get_prefix_path, ensure_prefix_exists
from .wine_runner import launch_windows_app


def run_in_zone2(exe_path: str) -> dict:
    """
    Full Zone 2 pipeline:
      1. Compute a unique Wine prefix for this exe.
      2. Create the prefix directory if it does not exist.
      3. Launch the exe under Wine/Proton with the isolated prefix.

    Args:
        exe_path: Path to the Windows executable.

    Returns:
        On success:
            {"success": True, "pid": int, "runner": "wine"|"proton",
             "cmd": list, "prefix": str}
        On failure:
            {"success": False, "error": str, ...}
    """
    prefix_path = get_prefix_path(exe_path)
    ensure_prefix_exists(prefix_path)

    result = launch_windows_app(
        exe_path,
        env_overrides={"WINEPREFIX": prefix_path},
    )

    result["prefix"] = prefix_path
    return result
