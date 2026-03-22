"""
src/gui/wallpaper/wallpaper_manager.py
Unified wallpaper manager — decides image vs video,
handles lock/unlock blur, and battery-aware pause.

No GTK dependency — all logic is plain Python and fully testable headless.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)

from gui.wallpaper.wallpaper_config import load_config, save_config
from gui.wallpaper.vaapi_check      import check_vaapi
from gui.wallpaper.swww_controller  import (
    set_color_wallpaper,
    set_image_wallpaper,
    kill_swww,
)
from gui.wallpaper.video_wallpaper  import VideoWallpaper


class WallpaperManager:
    """
    Single source of truth for the current wallpaper state.

    Responsibilities:
      - Applies color / image / video wallpapers.
      - Pauses video on screen-lock; resumes on unlock.
      - Pauses video on low battery (< 20 % + on battery).
      - Re-applies on unlock or AC reconnect.
    """

    _BATTERY_PAUSE_THRESHOLD = 20   # percent

    def __init__(self):
        self.config: dict       = load_config()
        self.video: VideoWallpaper = VideoWallpaper()
        self.locked: bool       = False
        self._battery_paused: bool = False

    # -----------------------------------------------------------------------
    # Apply
    # -----------------------------------------------------------------------

    def apply(self, config: dict | None = None) -> dict:
        """
        Apply the given wallpaper config (or re-apply current config).

        Args:
            config: Optional new config dict. Saved to disk if provided.

        Returns:
            {"applied": "color"|"image"|"video", "decode": "vaapi"|"cpu" (video only)}
        """
        if config is not None:
            self.config = config
            save_config(config)

        wtype = self.config.get("type", "color")

        if wtype == "color":
            if self.video.is_running():
                self.video.stop()
            set_color_wallpaper(self.config.get("value", "#1c1c1e"))
            return {"applied": "color"}

        if wtype == "image":
            if self.video.is_running():
                self.video.stop()
            set_image_wallpaper(
                self.config.get("value", ""),
                self.config.get("transition", "fade"),
                self.config.get("transition_ms", 800),
            )
            return {"applied": "image"}

        if wtype == "video":
            vaapi = check_vaapi()
            method = "vaapi" if vaapi["available"] else "cpu"
            logger.info(f"WallpaperManager: video decode via {method.upper()}")
            self.video.start(self.config.get("value", ""), self.config)
            return {"applied": "video", "decode": method}

        return {"applied": "unknown", "error": f"unknown wallpaper type: {wtype}"}

    # -----------------------------------------------------------------------
    # Lock / unlock
    # -----------------------------------------------------------------------

    def on_lock(self) -> None:
        """
        Called when the screen locks.
        Pauses video and optionally sets a blurred screenshot as the lock
        background (requires grim + imagemagick).
        """
        self.locked = True
        if self.video.is_running():
            self.video.pause()
            if self.config.get("blur_on_lock", True):
                self._apply_blur_screenshot()

    def on_unlock(self) -> None:
        """
        Called when the screen unlocks.
        Resumes video if it was paused.
        """
        self.locked = False
        if self.video.paused and not self._battery_paused:
            self.video.resume()
        # Re-apply to restore full wallpaper state
        self.apply()

    # -----------------------------------------------------------------------
    # Battery-aware pause
    # -----------------------------------------------------------------------

    def check_battery_pause(self) -> None:
        """
        Pause video if on battery and below threshold; resume if charged / plugged.
        Call this from a periodic poll (e.g. daemon's power watcher loop).
        """
        try:
            from power_manager.ac_monitor import get_ac_status
            status = get_ac_status()
            plugged     = status.get("plugged_in", True)
            battery_pct = status.get("battery_percent") or 100

            should_pause = (
                not plugged
                and battery_pct < self._BATTERY_PAUSE_THRESHOLD
                and self.video.is_running()
            )
            if should_pause and not self._battery_paused:
                logger.info("WallpaperManager: battery low — pausing video wallpaper")
                self.video.pause()
                self._battery_paused = True
            elif not should_pause and self._battery_paused and not self.locked:
                logger.info("WallpaperManager: battery OK — resuming video wallpaper")
                self.video.resume()
                self._battery_paused = False
        except Exception as e:
            logger.debug(f"WallpaperManager.check_battery_pause: {e}")

    # -----------------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current wallpaper state as a JSON-serialisable dict."""
        return {
            "type":          self.config.get("type",  "color"),
            "value":         self.config.get("value", "#1c1c1e"),
            "video_running": self.video.is_running(),
            "video_paused":  self.video.paused,
            "vaapi":         check_vaapi()["available"],
            "locked":        self.locked,
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _apply_blur_screenshot(self) -> None:
        """
        Capture the screen with grim, blur it with ImageMagick,
        then set it as the swww wallpaper.
        Silently skips if tools are not installed.
        """
        import tempfile
        import os

        try:
            tmp_raw  = tempfile.mktemp(suffix=".png", dir="/tmp")
            tmp_blur = tempfile.mktemp(suffix="_blur.png", dir="/tmp")

            # Capture
            result = subprocess.run(
                ["grim", tmp_raw],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return

            # Blur
            result = subprocess.run(
                ["convert", tmp_raw, "-blur", "0x20", tmp_blur],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                return

            set_image_wallpaper(tmp_blur, transition="fade", duration_ms=300)

        except FileNotFoundError:
            logger.debug("WallpaperManager: grim or ImageMagick not installed")
        except Exception as e:
            logger.debug(f"WallpaperManager._apply_blur_screenshot: {e}")
        finally:
            for p in (tmp_raw, tmp_blur):
                try:
                    os.unlink(p)
                except Exception:
                    pass
