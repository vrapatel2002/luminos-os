"""
wine_runner.py
Detect Wine/Proton and launch Windows executables under Zone 2.
Pure stdlib — no external dependencies.

Phase 8.12: Uses compatibility_manager for OS-level Wine detection and
DXVK/VKD3D-Proton runner selection when available. Falls back to legacy
scan logic so existing detection behaviour is never broken.
"""

import glob
import os
import subprocess

# Phase 8.12 — OS-level compat manager (optional: graceful fallback if absent)
try:
    from zone2.compatibility_manager import (
        get_wine_path as _compat_get_wine_path,
        get_compat_status as _compat_get_compat_status,
        get_best_runner as _compat_get_best_runner,
        build_compat_env as _compat_build_compat_env,
        ensure_app_prefix as _compat_ensure_app_prefix,
    )
    _HAS_COMPAT_MANAGER = True
except ImportError:
    _HAS_COMPAT_MANAGER = False


# Search paths for Wine binaries (legacy fallback)
_WINE_CANDIDATES = [
    "/usr/bin/wine64",
    "/usr/bin/wine",
    "/usr/local/bin/wine64",
    "/usr/local/bin/wine",
]

# Glob patterns for Steam Proton installations
_PROTON_GLOBS = [
    os.path.expanduser("~/.steam/steam/steamapps/common/Proton*/proton"),
    os.path.expanduser("~/.steam/root/steamapps/common/Proton*/proton"),
    "/usr/share/steam/steamapps/common/Proton*/proton",
]


def _get_wine_version(wine_path: str) -> str | None:
    """Run `wine --version` and return the version string, or None on failure."""
    try:
        result = subprocess.run(
            [wine_path, "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _find_proton() -> tuple[str, str] | tuple[None, None]:
    """Return (path, version_string) for the newest Proton install found, or (None, None)."""
    matches = []
    for pattern in _PROTON_GLOBS:
        matches.extend(glob.glob(pattern))

    if not matches:
        return None, None

    # Sort descending so newest Proton version is first
    matches.sort(reverse=True)
    proton_path = matches[0]

    # Derive a version label from directory name, e.g. "Proton 8.0"
    parent = os.path.basename(os.path.dirname(proton_path))
    return proton_path, parent


def detect_wine() -> dict:
    """
    Probe for Wine and Proton in standard locations.

    Phase 8.12: First checks the OS-level Luminos compat dir via
    compatibility_manager.get_wine_path() so the baked-in Wine is always
    preferred.  Falls back to Proton and then legacy system Wine paths so
    the existing detection behaviour is never broken.

    Returns:
        {
            "available": bool,
            "path":      str | None,
            "type":      "wine" | "proton" | None,
            "version":   str | None,
        }
    """
    # Phase 8.12: OS-level Wine from Luminos compat dir (highest priority)
    if _HAS_COMPAT_MANAGER:
        compat_path = _compat_get_wine_path()
        if compat_path:
            version = _get_wine_version(compat_path)
            return {
                "available": True,
                "path":      compat_path,
                "type":      "wine",
                "version":   version,
            }

    # Prefer Proton when available (better DXVK/VKD3D support)
    proton_path, proton_ver = _find_proton()
    if proton_path and os.path.isfile(proton_path):
        return {
            "available": True,
            "path":      proton_path,
            "type":      "proton",
            "version":   proton_ver,
        }

    # Fall back to system Wine
    for candidate in _WINE_CANDIDATES:
        if os.path.isfile(candidate):
            version = _get_wine_version(candidate)
            return {
                "available": True,
                "path":      candidate,
                "type":      "wine",
                "version":   version,
            }

    return {
        "available": False,
        "path":      None,
        "type":      None,
        "version":   None,
    }


def build_wine_command(exe_path: str, wine_info: dict, env_overrides: dict = {}) -> dict:
    """
    Construct the subprocess command and environment for launching a Windows exe.

    Phase 8.12: When compatibility_manager is available, uses get_best_runner()
    to detect which translation layer (DXVK/VKD3D) the exe needs and
    build_compat_env() to set WINEESYNC/WINEFSYNC and cache paths automatically.
    env_overrides are always applied last so callers can still override anything.

    Args:
        exe_path:      Absolute path to the .exe file.
        wine_info:     Dict returned by detect_wine().
        env_overrides: Extra env vars to layer on top (e.g. WINEPREFIX).

    Returns:
        {
            "cmd": list[str],
            "env": dict,
        }
    """
    runner_path = wine_info["path"]
    runner_type = wine_info["type"]

    if runner_type == "proton":
        cmd = [runner_path, "run", exe_path]
    else:
        # wine / wine64
        cmd = [runner_path, exe_path]

    # Phase 8.12: Use compat manager for full env build when available
    if _HAS_COMPAT_MANAGER and os.path.isfile(exe_path):
        runner_config = _compat_get_best_runner(exe_path)
        prefix_path = os.path.expanduser("~/.luminos/prefixes/default")
        env = _compat_build_compat_env(prefix_path, runner_config)
    else:
        # Legacy fallback — same defaults as before Phase 8.12
        env = dict(os.environ)
        env.setdefault("WINEPREFIX", os.path.expanduser("~/.luminos/prefixes/default"))
        env["WINEDEBUG"] = "-all"   # suppress Wine debug noise
        env["DXVK_HUD"]  = "0"     # no DXVK overlay by default

    env.update(env_overrides)

    return {"cmd": cmd, "env": env}


def launch_windows_app(exe_path: str, env_overrides: dict = {}) -> dict:
    """
    Full pipeline: detect runner → build command → launch non-blocking.

    Returns on success:
        {"success": True, "pid": int, "runner": "wine"|"proton", "cmd": list}

    Returns on failure:
        {"success": False, "error": str, "install_hint": str}  (Wine/Proton missing)
        {"success": False, "error": str}                        (exe not found / OS error)
    """
    wine_info = detect_wine()

    if not wine_info["available"]:
        return {
            "success":      False,
            "error":        "Wine/Proton not installed",
            "install_hint": "sudo apt install wine64",
        }

    command_info = build_wine_command(exe_path, wine_info, env_overrides)

    try:
        proc = subprocess.Popen(
            command_info["cmd"],
            env=command_info["env"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "success": True,
            "pid":     proc.pid,
            "runner":  wine_info["type"],
            "cmd":     command_info["cmd"],
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error":   f"Executable not found: {exe_path}",
        }
    except OSError as e:
        return {
            "success": False,
            "error":   f"OS error launching process: {e}",
        }
