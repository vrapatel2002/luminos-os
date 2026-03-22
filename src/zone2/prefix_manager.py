"""
prefix_manager.py
Manages per-application Wine prefix directories under ~/.luminos/prefixes/.

Each app gets an isolated Windows environment so registry/DLL changes
from one game cannot affect another.
"""

import hashlib
import os


DEFAULT_PREFIX_BASE = os.path.expanduser("~/.luminos/prefixes/")


def get_prefix_path(exe_path: str) -> str:
    """
    Return a unique, deterministic prefix directory path for this executable.

    The prefix name is: <exe_stem>_<8-char hash of parent dir path>
    Example: ~/.luminos/prefixes/game_exe_a3f2b1c8/

    Args:
        exe_path: Absolute or relative path to the .exe file.

    Returns:
        Full path to the prefix directory (not guaranteed to exist yet).
    """
    exe_path = os.path.realpath(os.path.abspath(exe_path))
    exe_stem = os.path.splitext(os.path.basename(exe_path))[0]
    parent_dir = os.path.dirname(exe_path)

    # Short hash of parent directory so two different games with the same
    # filename (e.g. "launcher.exe") get separate prefixes
    dir_hash = hashlib.sha256(parent_dir.encode()).hexdigest()[:8]

    # Sanitise exe_stem: lowercase, replace non-alphanumeric with _
    safe_stem = "".join(c if c.isalnum() else "_" for c in exe_stem.lower())
    # Collapse consecutive underscores and strip leading/trailing ones
    safe_stem = "_".join(part for part in safe_stem.split("_") if part)[:32]

    prefix_name = f"{safe_stem}_{dir_hash}"
    return os.path.join(DEFAULT_PREFIX_BASE, prefix_name)


def ensure_prefix_exists(prefix_path: str) -> bool:
    """
    Create the prefix directory if it does not already exist.

    Args:
        prefix_path: Full path to the desired prefix directory.

    Returns:
        True  — directory exists (or was created successfully).
        False — creation failed due to an OS error.
    """
    if os.path.isdir(prefix_path):
        return True
    try:
        os.makedirs(prefix_path, exist_ok=True)
        return True
    except OSError:
        return False


def _dir_size_mb(path: str) -> float:
    """Walk a directory tree and sum file sizes in MB."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass
    except OSError:
        pass
    return total / (1024 * 1024)


def list_prefixes() -> list:
    """
    Return metadata for every prefix directory under DEFAULT_PREFIX_BASE.

    Returns:
        List of dicts: [{"name": str, "path": str, "size_mb": float}, ...]
        Empty list if the base directory does not exist or is empty.
    """
    if not os.path.isdir(DEFAULT_PREFIX_BASE):
        return []

    prefixes = []
    try:
        entries = sorted(os.listdir(DEFAULT_PREFIX_BASE))
    except OSError:
        return []

    for name in entries:
        full_path = os.path.join(DEFAULT_PREFIX_BASE, name)
        if not os.path.isdir(full_path):
            continue
        prefixes.append({
            "name":    name,
            "path":    full_path,
            "size_mb": _dir_size_mb(full_path),
        })

    return prefixes
