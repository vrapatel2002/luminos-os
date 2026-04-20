"""
src/gui/wallpaper/wallpaper_config.py
Persistent wallpaper configuration — pure Python, no display required.

Handles load/save of ~/.config/luminos/wallpaper.json and
scanning WALLPAPER_DIRS for image/video files.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.expanduser("~/.config/luminos/wallpaper.json")

WALLPAPER_DIRS = [
    os.path.expanduser("~/.local/share/luminos/wallpapers"),
    "/usr/share/luminos/wallpapers",
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}

DEFAULT_CONFIG: dict = {
    "type":          "color",   # color / image / video
    "value":         "#1c1c1e", # color hex, image path, or video path
    "video_loop":    True,
    "video_mute":    True,      # audio off by default
    "video_speed":   1.0,
    "blur_on_lock":  True,
    "dim_percent":   0,         # 0-50 % dim overlay
    "transition":    "fade",    # fade / wipe / grow
    "transition_ms": 800,
}


def load_config() -> dict:
    """
    Read CONFIG_PATH, merge with DEFAULT_CONFIG for missing keys.
    Returns complete config dict. Falls back to DEFAULT_CONFIG on any error.
    """
    base = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            base.update(saved)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"wallpaper_config: load error — {e}, using defaults")
    return base


def save_config(config: dict) -> bool:
    """
    Write config dict to CONFIG_PATH, creating parent dirs as needed.
    Returns True on success.
    """
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.warning(f"wallpaper_config: save error — {e}")
        return False


def get_wallpaper_files() -> list:
    """
    Scan WALLPAPER_DIRS for image and video files.

    Returns:
        List of dicts:
        {"path": str, "type": "image"|"video", "name": str, "size_mb": float}
    """
    results = []
    for directory in WALLPAPER_DIRS:
        if not os.path.isdir(directory):
            continue
        try:
            for fname in sorted(os.listdir(directory)):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
                    continue
                fpath = os.path.join(directory, fname)
                try:
                    size_mb = round(os.path.getsize(fpath) / (1024 * 1024), 2)
                except OSError:
                    size_mb = 0.0
                results.append({
                    "path":    fpath,
                    "type":    "image" if ext in IMAGE_EXTS else "video",
                    "name":    fname,
                    "size_mb": size_mb,
                })
        except OSError as e:
            logger.debug(f"wallpaper_config: scan error in {directory} — {e}")
    return results
