"""
src/classifier/icon_extractor.py
Phase 5.10 Task 3 — Extract app icon from Windows .exe file.

Uses icoutils (wrestool + icotool) to pull the embedded icon.
Falls back to a generic Windows icon on any failure.

Requires: sudo pacman -S icoutils

Cache: ~/.cache/luminos/icons/<sha256[:16]>.png
"""

import hashlib
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger("luminos.classifier.icon_extractor")

_ICON_CACHE_DIR = os.path.expanduser("~/.cache/luminos/icons")
_GENERIC_ICON   = "/usr/share/icons/hicolor/48x48/apps/wine.png"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_app_icon(exe_path: str) -> str:
    """
    Return path to a 48×48 PNG icon for the given .exe.

    Extracts from the .exe if not already cached.
    Returns the generic Windows icon path if extraction fails.

    Args:
        exe_path: Absolute path to the .exe file.

    Returns:
        Path to a PNG file (always returns something).
    """
    if not os.path.isfile(exe_path):
        return _generic_icon()

    # Cache key = first 16 chars of sha256 of the exe path + mtime
    try:
        stat = os.stat(exe_path)
        key_src = f"{exe_path}:{stat.st_size}:{stat.st_mtime}"
    except OSError:
        key_src = exe_path

    icon_hash = hashlib.sha256(key_src.encode()).hexdigest()[:16]
    cache_path = os.path.join(_ICON_CACHE_DIR, f"{icon_hash}.png")

    if os.path.isfile(cache_path):
        return cache_path

    # Extract
    result = _extract_icon(exe_path, cache_path)
    return cache_path if result else _generic_icon()


def clear_icon_cache() -> int:
    """
    Remove all cached icon files.

    Returns:
        Number of files removed.
    """
    if not os.path.isdir(_ICON_CACHE_DIR):
        return 0
    count = 0
    for fname in os.listdir(_ICON_CACHE_DIR):
        if fname.endswith(".png"):
            try:
                os.remove(os.path.join(_ICON_CACHE_DIR, fname))
                count += 1
            except OSError:
                pass
    return count


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _extract_icon(exe_path: str, out_png: str) -> bool:
    """
    Extract icon from .exe → PNG using wrestool + icotool.

    Returns True on success, False on any failure.
    """
    os.makedirs(_ICON_CACHE_DIR, exist_ok=True)

    # Check dependencies
    if not _has_cmd("wrestool") or not _has_cmd("icotool"):
        logger.debug("icoutils not installed — cannot extract icon")
        return False

    with tempfile.TemporaryDirectory(prefix="luminos-icon-") as tmpdir:
        ico_path = os.path.join(tmpdir, "app.ico")

        # Step 1: wrestool extracts .ico from .exe
        try:
            result = subprocess.run(
                ["wrestool", "-x", "--type=14", "-o", ico_path, exe_path],
                capture_output=True, timeout=10,
            )
            if result.returncode != 0 or not os.path.isfile(ico_path):
                # Try without type filter — some exes store icons differently
                result = subprocess.run(
                    ["wrestool", "-x", "-o", ico_path, exe_path],
                    capture_output=True, timeout=10,
                )
                if result.returncode != 0 or not os.path.isfile(ico_path):
                    logger.debug(f"wrestool failed for {os.path.basename(exe_path)}")
                    return False
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.debug(f"wrestool error: {e}")
            return False

        # Step 2: icotool converts .ico → PNG (largest icon, index 0)
        try:
            result = subprocess.run(
                ["icotool", "-x", "--index=0", "-o", out_png, ico_path],
                capture_output=True, timeout=10,
            )
            if result.returncode != 0 or not os.path.isfile(out_png):
                # Try without index (first icon)
                result = subprocess.run(
                    ["icotool", "-x", "-o", out_png, ico_path],
                    capture_output=True, timeout=10,
                )
                if result.returncode != 0 or not os.path.isfile(out_png):
                    logger.debug(f"icotool failed for {os.path.basename(exe_path)}")
                    return False
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.debug(f"icotool error: {e}")
            return False

    logger.debug(f"Icon extracted: {out_png}")
    return True


def _has_cmd(cmd: str) -> bool:
    """Return True if cmd is on PATH."""
    import shutil
    return shutil.which(cmd) is not None


def _generic_icon() -> str:
    """Return path to generic Windows icon, or empty string if not found."""
    if os.path.isfile(_GENERIC_ICON):
        return _GENERIC_ICON
    # Try common fallback locations
    fallbacks = [
        "/usr/share/pixmaps/wine.png",
        "/usr/share/icons/hicolor/scalable/apps/wine.svg",
    ]
    for path in fallbacks:
        if os.path.isfile(path):
            return path
    return ""
