"""
dxvk_manager.py
Manages DXVK DLL installation per Wine prefix.

DXVK translates DirectX 9/10/11 API calls to Vulkan, enabling
hardware-accelerated rendering for Windows games under Wine.
DLLs are installed from the OS-level compat dir — no network access required.
Pure stdlib — no external dependencies.
"""

import os
import shutil
import subprocess


COMPAT_BASE = "/usr/lib/luminos/compatibility"

# DLLs that DXVK provides (same filenames for both 64-bit and 32-bit)
DXVK_DLLS_64 = [
    "d3d9.dll",
    "d3d10.dll",
    "d3d10_1.dll",
    "d3d10core.dll",
    "d3d11.dll",
    "dxgi.dll",
]
DXVK_DLLS_32 = DXVK_DLLS_64  # same names, different arch directory


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_wine() -> str | None:
    """Locate wine64 or wine binary."""
    for candidate in [
        os.path.join(COMPAT_BASE, "wine", "wine64"),
        "/usr/bin/wine64",
        "/usr/bin/wine",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def _register_dxvk_dlls(wine_path: str, prefix_path: str) -> None:
    """
    Register DXVK DLLs as 'native' overrides in the Wine registry so Wine
    loads the DXVK Vulkan translator instead of its built-in DirectX stubs.
    """
    env = dict(os.environ)
    env["WINEPREFIX"] = prefix_path
    env["WINEDEBUG"]  = "-all"

    for dll in DXVK_DLLS_64:
        dll_name = dll.replace(".dll", "")
        try:
            subprocess.run(
                [
                    wine_path, "reg", "add",
                    r"HKEY_CURRENT_USER\Software\Wine\DllOverrides",
                    "/v", dll_name, "/d", "native", "/f",
                ],
                env=env,
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_dxvk_installed(prefix_path: str) -> bool:
    """
    Check whether DXVK DLLs are present in the prefix's system32 directory.

    Args:
        prefix_path: Path to the Wine prefix directory.

    Returns:
        True if all DXVK DLLs are found in system32, False otherwise.
    """
    sys32 = os.path.join(prefix_path, "drive_c", "windows", "system32")
    if not os.path.isdir(sys32):
        return False
    return all(os.path.isfile(os.path.join(sys32, dll)) for dll in DXVK_DLLS_64)


def install_dxvk(prefix_path: str) -> dict:
    """
    Copy DXVK DLLs from the OS compat dir into a Wine prefix and register them.

    Copies:
      - 64-bit DLLs → {prefix}/drive_c/windows/system32/
      - 32-bit DLLs → {prefix}/drive_c/windows/syswow64/

    Then registers each DLL as a native override via winreg so Wine uses the
    DXVK Vulkan translator instead of its own DirectX implementation.

    Args:
        prefix_path: Path to the Wine prefix directory.

    Returns:
        {"success": bool, "dlls_installed": int}
    """
    src64 = os.path.join(COMPAT_BASE, "dxvk")
    src32 = os.path.join(COMPAT_BASE, "dxvk", "x32")
    dst64 = os.path.join(prefix_path, "drive_c", "windows", "system32")
    dst32 = os.path.join(prefix_path, "drive_c", "windows", "syswow64")

    dlls_installed = 0

    try:
        os.makedirs(dst64, exist_ok=True)
        os.makedirs(dst32, exist_ok=True)

        for dll in DXVK_DLLS_64:
            src_file = os.path.join(src64, dll)
            dst_file = os.path.join(dst64, dll)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, dst_file)
                dlls_installed += 1

        for dll in DXVK_DLLS_32:
            src_file = os.path.join(src32, dll)
            dst_file = os.path.join(dst32, dll)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, dst_file)
                dlls_installed += 1

        # Register DLL overrides via Wine registry (best-effort)
        wine_path = _find_wine()
        if wine_path:
            _register_dxvk_dlls(wine_path, prefix_path)

        return {"success": True, "dlls_installed": dlls_installed}

    except OSError as e:
        return {"success": False, "dlls_installed": dlls_installed, "error": str(e)}


def get_dxvk_version() -> str | None:
    """
    Return the installed DXVK version string, or None if not installed.

    Reads from COMPAT_BASE/dxvk/version (written by install_compatibility.sh).

    Returns:
        Version string (e.g. "2.3.1") or None.
    """
    version_file = os.path.join(COMPAT_BASE, "dxvk", "version")
    if os.path.isfile(version_file):
        try:
            with open(version_file) as f:
                return f.read().strip() or None
        except OSError:
            pass
    return None
