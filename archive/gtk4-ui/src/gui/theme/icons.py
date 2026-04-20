"""
src/gui/theme/icons.py
Icon path resolver for Luminos.

Search order:
  1. Papirus icon theme (preferred — best coverage)
  2. hicolor fallback
  3. Luminos bundled SVG icons

Rules:
- find_icon() never raises — returns None if not found.
- All paths are expanded (tilde → home).
- Size folder searched: "{size}x{size}" then "scalable".
"""

import logging
import os

logger = logging.getLogger("luminos-ai.gui.theme.icons")

PAPIRUS_PATHS: list[str] = [
    "/usr/share/icons/Papirus",
    "/usr/share/icons/Papirus-Dark",
    os.path.expanduser("~/.local/share/icons/Papirus"),
]

HICOLOR_PATH = "/usr/share/icons/hicolor"

LUMINOS_ICONS_PATH = "/opt/luminos/src/gui/theme/luminos_icons/"

# Bundled Luminos icons (relative to this file's directory)
_LOCAL_ICONS_DIR = os.path.join(os.path.dirname(__file__), "luminos_icons")


def find_icon(name: str, size: int = 24) -> str | None:
    """
    Search for an icon by name, returning a full file path.

    Search order:
        1. Papirus — {size}x{size}/apps/, then scalable/apps/
        2. hicolor — same pattern
        3. Luminos bundled icons

    Args:
        name: Icon name without extension (e.g. "firefox", "terminal").
        size: Preferred pixel size (e.g. 16, 24, 32, 48).

    Returns:
        Absolute file path string, or None if not found.
    """
    size_folder = f"{size}x{size}"
    subdirs      = [size_folder, "scalable"]
    categories   = ["apps", "devices", "status", "actions", "places"]
    extensions   = [".svg", ".png"]

    search_roots = [p for p in PAPIRUS_PATHS if os.path.isdir(p)]
    if os.path.isdir(HICOLOR_PATH):
        search_roots.append(HICOLOR_PATH)

    for root in search_roots:
        for sub in subdirs:
            for cat in categories:
                for ext in extensions:
                    path = os.path.join(root, sub, cat, name + ext)
                    if os.path.isfile(path):
                        logger.debug(f"Icon found: {path}")
                        return path

    # Luminos bundled fallback
    for ext in extensions:
        local = os.path.join(_LOCAL_ICONS_DIR, name + ext)
        if os.path.isfile(local):
            logger.debug(f"Icon found (bundled): {local}")
            return local

    logger.debug(f"Icon not found: {name} ({size}px)")
    return None


def get_system_icons() -> dict:
    """
    Return a dict of key system icon paths.

    All values are resolved paths (str) or None if not installed.
    The luminos_ai entry always points to the bundled SVG.

    Returns:
        Dict mapping icon role → file path or None.
    """
    names = {
        "wifi_on":          "network-wireless",
        "wifi_off":         "network-wireless-offline",
        "bt_on":            "bluetooth-active",
        "bt_off":           "bluetooth-disabled",
        "volume_high":      "audio-volume-high",
        "volume_low":       "audio-volume-low",
        "volume_mute":      "audio-volume-muted",
        "brightness":       "display-brightness",
        "battery_full":     "battery",
        "battery_low":      "battery-caution",
        "battery_charging": "battery-good-charging",
        "power":            "system-shutdown",
        "settings":         "preferences-system",
    }

    result = {key: find_icon(icon_name) for key, icon_name in names.items()}
    result["luminos_ai"] = os.path.join(_LOCAL_ICONS_DIR, "ai_idle.svg")
    return result
