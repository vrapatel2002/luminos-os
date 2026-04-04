"""
compatibility_manager.py
Manages the OS-level Wine/DXVK/VKD3D-Proton compatibility layer.

Wine is a Luminos OS component — not a user-installed application.
It lives at /usr/lib/luminos/compatibility/ and is available on first boot
with no user configuration required.
Pure stdlib — no external dependencies.
"""

import hashlib
import os
import subprocess


COMPAT_BASE = "/usr/lib/luminos/compatibility"
SYSTEM_PREFIX = "/var/lib/luminos/prefixes/default"
USER_PREFIX_BASE = os.path.expanduser("~/.luminos/prefixes")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_wine_version(wine_path: str) -> str | None:
    """Run wine --version, return version string or None."""
    try:
        result = subprocess.run(
            [wine_path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_dxvk_dlls() -> list:
    """Return list of .dll filenames in the DXVK compat dir."""
    dxvk_dir = os.path.join(COMPAT_BASE, "dxvk")
    if not os.path.isdir(dxvk_dir):
        return []
    try:
        return [f for f in os.listdir(dxvk_dir) if f.endswith(".dll")]
    except OSError:
        return []


def _read_version_file(component: str) -> str | None:
    """Read version from COMPAT_BASE/<component>/version file."""
    version_file = os.path.join(COMPAT_BASE, component, "version")
    if os.path.isfile(version_file):
        try:
            with open(version_file) as f:
                return f.read().strip()
        except OSError:
            pass
    return None


def _get_vulkan_devices() -> list:
    """Run vulkaninfo --summary and extract device names."""
    try:
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True, text=True, timeout=10,
        )
        devices = []
        for line in result.stdout.splitlines():
            if "deviceName" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    devices.append(parts[1].strip())
        return devices
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _read_exe_bytes(exe_path: str) -> bytes:
    """Read first 4MB of an exe for import-table API detection."""
    try:
        with open(exe_path, "rb") as f:
            return f.read(4 * 1024 * 1024)
    except OSError:
        return b""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_wine_path() -> str | None:
    """
    Return the path to wine64 (or wine), checking the Luminos compat dir first.

    Search order:
      1. COMPAT_BASE/wine/wine64   (OS component — preferred)
      2. /usr/bin/wine64           (system package fallback)
      3. /usr/bin/wine             (32-bit fallback)

    Returns:
        Absolute path to the first found wine binary, or None.
    """
    candidates = [
        os.path.join(COMPAT_BASE, "wine", "wine64"),
        "/usr/bin/wine64",
        "/usr/bin/wine",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def get_compat_status() -> dict:
    """
    Check all compatibility layer components and return their status.

    Returns:
        {
            "wine64":         {"available": bool, "path": str|None,
                               "version": str|None, "source": "system"|"user"|None},
            "dxvk":           {"available": bool, "version": str|None, "dlls": [str]},
            "vkd3d":          {"available": bool, "version": str|None},
            "vulkan":         {"available": bool, "devices": [str]},
            "system_prefix":  {"exists": bool, "path": str, "initialized": bool},
            "overall_ready":  bool,
        }
    """
    # Wine
    wine_path = get_wine_path()
    wine_available = wine_path is not None
    wine_version = _get_wine_version(wine_path) if wine_available else None
    if wine_available and wine_path and wine_path.startswith(COMPAT_BASE):
        wine_source = "system"
    elif wine_available:
        wine_source = "user"
    else:
        wine_source = None

    # DXVK
    dxvk_dir = os.path.join(COMPAT_BASE, "dxvk")
    dxvk_available = os.path.isdir(dxvk_dir)
    dxvk_dlls = _get_dxvk_dlls()
    dxvk_version = _read_version_file("dxvk")

    # VKD3D-Proton
    vkd3d_dir = os.path.join(COMPAT_BASE, "vkd3d")
    vkd3d_available = os.path.isdir(vkd3d_dir)
    vkd3d_version = _read_version_file("vkd3d")

    # Vulkan
    vulkan_devices = _get_vulkan_devices()
    vulkan_available = len(vulkan_devices) > 0

    # System prefix — initialized means wineboot has run (drive_c/windows/system32 exists)
    system_prefix_exists = os.path.isdir(SYSTEM_PREFIX)
    system32_path = os.path.join(SYSTEM_PREFIX, "drive_c", "windows", "system32")
    system_prefix_initialized = os.path.isdir(system32_path)

    # overall_ready requires at minimum a working wine binary
    overall_ready = wine_available

    return {
        "wine64": {
            "available": wine_available,
            "path":      wine_path,
            "version":   wine_version,
            "source":    wine_source,
        },
        "dxvk": {
            "available": dxvk_available,
            "version":   dxvk_version,
            "dlls":      dxvk_dlls,
        },
        "vkd3d": {
            "available": vkd3d_available,
            "version":   vkd3d_version,
        },
        "vulkan": {
            "available": vulkan_available,
            "devices":   vulkan_devices,
        },
        "system_prefix": {
            "exists":      system_prefix_exists,
            "path":        SYSTEM_PREFIX,
            "initialized": system_prefix_initialized,
        },
        "overall_ready": overall_ready,
    }


def get_best_runner(exe_path: str) -> dict:
    """
    Analyze a Windows executable and return the recommended runner configuration.

    Scans the binary for DirectX API import strings to determine which
    translation layer (DXVK for DX9/10/11, VKD3D-Proton for DX12) to use.

    Returns:
        {
            "runner":  "wine64" | "proton",
            "dxvk":    bool,
            "vkd3d":   bool,
            "reason":  str,
        }
    """
    data = _read_exe_bytes(exe_path)
    lower = data.lower()

    has_d3d12 = b"d3d12" in lower
    has_d3d11 = b"d3d11" in lower
    has_d3d10 = b"d3d10" in lower
    has_d3d9  = b"d3d9"  in lower

    # Check for .NET-only apps (no DirectX) — plain Wine is best
    has_dotnet = b"mscoree.dll" in lower or b"mscorlib" in lower

    if has_d3d12:
        return {
            "runner": "proton",
            "dxvk":   False,
            "vkd3d":  True,
            "reason": "DX12 imports detected — Proton + VKD3D-Proton recommended",
        }
    elif has_d3d11 or has_d3d10:
        return {
            "runner": "proton",
            "dxvk":   True,
            "vkd3d":  False,
            "reason": "DX11/DX10 imports detected — Proton + DXVK recommended",
        }
    elif has_d3d9:
        return {
            "runner": "wine64",
            "dxvk":   True,
            "vkd3d":  False,
            "reason": "DX9 imports detected — Wine + DXVK recommended",
        }
    elif has_dotnet:
        return {
            "runner": "wine64",
            "dxvk":   False,
            "vkd3d":  False,
            "reason": ".NET application — plain Wine recommended",
        }
    else:
        return {
            "runner": "proton",
            "dxvk":   False,
            "vkd3d":  False,
            "reason": "No special APIs detected — Proton (default)",
        }


def build_compat_env(prefix_path: str, runner_config: dict) -> dict:
    """
    Build a complete environment dict for launching a Windows application.

    Inherits current environment, applies Luminos defaults, then layers
    runner-specific variables.

    Args:
        prefix_path:   Path to the Wine prefix directory.
        runner_config: Dict from get_best_runner() — must include "dxvk" and "vkd3d" keys.

    Returns:
        Complete environment dict ready to pass to subprocess.Popen(env=...).
    """
    env = dict(os.environ)

    env["WINEPREFIX"] = prefix_path
    env["WINEDEBUG"]  = "-all"       # suppress Wine debug noise
    env["WINEARCH"]   = "win64"
    env["DXVK_HUD"]  = "0"          # no DXVK overlay by default

    # Performance: esync/fsync reduce kernel overhead for synchronization objects
    env["WINEESYNC"] = "1"
    env["WINEFSYNC"] = "1"

    # Sandbox: redirect HOME so Wine apps cannot access real home directory.
    # The prefix itself becomes the app's home. Z: drive mapping is disabled
    # via WINEDLLOVERRIDES to prevent Wine's default / mount.
    env["HOME"] = prefix_path
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe=d"

    if runner_config.get("dxvk"):
        env["DXVK_STATE_CACHE_PATH"] = prefix_path

    if runner_config.get("vkd3d"):
        env["VKD3D_SHADER_CACHE_PATH"] = prefix_path

    return env


def _get_app_prefix_path(exe_path: str) -> str:
    """Return deterministic per-app prefix path under USER_PREFIX_BASE."""
    exe_path  = os.path.realpath(os.path.abspath(exe_path))
    exe_stem  = os.path.splitext(os.path.basename(exe_path))[0]
    parent    = os.path.dirname(exe_path)
    dir_hash  = hashlib.sha256(parent.encode()).hexdigest()[:8]
    safe_stem = "".join(c if c.isalnum() else "_" for c in exe_stem.lower())
    safe_stem = "_".join(p for p in safe_stem.split("_") if p)[:32]
    return os.path.join(USER_PREFIX_BASE, f"{safe_stem}_{dir_hash}")


def ensure_app_prefix(exe_path: str) -> str:
    """
    Get or create an app-specific Wine prefix for the given executable.

    Creates the directory if it does not exist.
    Applies DXVK automatically if available.

    Returns:
        Absolute path to the prefix directory.
    """
    prefix_path = _get_app_prefix_path(exe_path)
    os.makedirs(prefix_path, exist_ok=True)

    # Apply DXVK if available (best-effort — no crash if dxvk_manager absent)
    if os.path.isdir(os.path.join(COMPAT_BASE, "dxvk")):
        try:
            from zone2.dxvk_manager import is_dxvk_installed, install_dxvk
            if not is_dxvk_installed(prefix_path):
                install_dxvk(prefix_path)
        except Exception:
            pass

    return prefix_path
