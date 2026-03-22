"""
src/gui/wallpaper/__init__.py
Module-level singleton API for the Luminos wallpaper system.

Public API
----------
apply_wallpaper(config)   → dict
set_video(path)           → dict
set_image(path)           → dict
set_color(hex_color)      → dict
on_lock()
on_unlock()
get_status()              → dict
get_files()               → list
"""

from gui.wallpaper.wallpaper_config  import get_wallpaper_files
from gui.wallpaper.wallpaper_manager import WallpaperManager

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: WallpaperManager = WallpaperManager()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_wallpaper(config: dict) -> dict:
    """Apply the given wallpaper config dict."""
    return _manager.apply(config)


def set_video(path: str) -> dict:
    """Switch to video wallpaper at the given path."""
    return _manager.apply({**_manager.config, "type": "video", "value": path})


def set_image(path: str) -> dict:
    """Switch to static image wallpaper at the given path."""
    return _manager.apply({**_manager.config, "type": "image", "value": path})


def set_color(hex_color: str) -> dict:
    """Switch to solid colour wallpaper."""
    return _manager.apply({**_manager.config, "type": "color", "value": hex_color})


def on_lock() -> None:
    """Notify the wallpaper system that the screen is locking."""
    _manager.on_lock()


def on_unlock() -> None:
    """Notify the wallpaper system that the screen has unlocked."""
    _manager.on_unlock()


def get_status() -> dict:
    """Return current wallpaper status dict."""
    return _manager.get_status()


def get_files() -> list:
    """Return list of available wallpaper files from WALLPAPER_DIRS."""
    return get_wallpaper_files()
