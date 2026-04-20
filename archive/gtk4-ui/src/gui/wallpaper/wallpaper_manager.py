"""
src/gui/wallpaper/wallpaper_manager.py
Unified wallpaper manager — decides image vs video vs live,
handles lock/unlock blur, and battery-aware pause.

Live wallpapers are rendered by the luminos-live-wallpaper C binary,
controlled via Unix socket. This module is the only Python interface.

No GTK dependency — all logic is plain Python and fully testable headless.
"""

import json
import logging
import os
import shutil
import socket
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

_LIVE_BINARY = "luminos-live-wallpaper"
_LIVE_SOCKET = "/tmp/luminos-wallpaper.sock"


def _send_live_command(cmd: dict, socket_path: str = _LIVE_SOCKET) -> dict:
    """Send a JSON command to the live wallpaper binary via Unix socket."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(socket_path)
        payload = json.dumps(cmd) + "\n"
        sock.sendall(payload.encode("utf-8"))
        data = sock.recv(4096)
        sock.close()
        return json.loads(data.decode("utf-8"))
    except (OSError, json.JSONDecodeError, ConnectionRefusedError) as e:
        logger.debug(f"live wallpaper socket error: {e}")
        return {"status": "error", "message": str(e)}


def _is_live_running(socket_path: str = _LIVE_SOCKET) -> bool:
    """Check if the live wallpaper binary is reachable."""
    result = _send_live_command({"cmd": "status"}, socket_path)
    return result.get("status") == "ok"


class WallpaperManager:
    """
    Single source of truth for the current wallpaper state.

    Responsibilities:
      - Applies color / image / video / live wallpapers.
      - Pauses video on screen-lock; resumes on unlock.
      - Pauses video on low battery (< 20 % + on battery).
      - Controls live wallpaper C binary via Unix socket.
      - Re-applies on unlock or AC reconnect.
    """

    _BATTERY_PAUSE_THRESHOLD = 20   # percent

    def __init__(self):
        self.config: dict       = load_config()
        self.video: VideoWallpaper = VideoWallpaper()
        self.locked: bool       = False
        self._battery_paused: bool = False
        self._live_proc: subprocess.Popen | None = None
        self._live_socket: str  = _LIVE_SOCKET

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
            self._stop_live()
            if self.video.is_running():
                self.video.stop()
            set_color_wallpaper(self.config.get("value", "#1c1c1e"))
            return {"applied": "color"}

        if wtype == "image":
            self._stop_live()
            if self.video.is_running():
                self.video.stop()
            set_image_wallpaper(
                self.config.get("value", ""),
                self.config.get("transition", "fade"),
                self.config.get("transition_ms", 800),
            )
            return {"applied": "image"}

        if wtype == "video":
            self._stop_live()
            vaapi = check_vaapi()
            method = "vaapi" if vaapi["available"] else "cpu"
            logger.info(f"WallpaperManager: video decode via {method.upper()}")
            self.video.start(self.config.get("value", ""), self.config)
            return {"applied": "video", "decode": method}

        if wtype == "live":
            if self.video.is_running():
                self.video.stop()
            preset    = self.config.get("preset", "particles")
            intensity = self.config.get("intensity", "medium")
            return self.set_live(preset, intensity)

        return {"applied": "unknown", "error": f"unknown wallpaper type: {wtype}"}

    # -----------------------------------------------------------------------
    # Live wallpaper control
    # -----------------------------------------------------------------------

    def set_live(self, preset: str = "particles",
                 intensity: str = "medium") -> dict:
        """
        Start or switch the live wallpaper.

        If the C binary is already running, sends a socket command.
        If not running, launches it as a subprocess.

        Args:
            preset: "particles", "aurora", or "geometric".
            intensity: "low", "medium", or "high".

        Returns:
            {"applied": "live", "preset": ..., "intensity": ...}
        """
        # Check if binary exists
        binary = shutil.which(_LIVE_BINARY)
        if not binary:
            logger.warning("luminos-live-wallpaper binary not found in PATH")
            return {"applied": "live", "error": "binary not found"}

        if _is_live_running(self._live_socket):
            # Already running — send command
            result = _send_live_command({
                "cmd": "set_preset",
                "preset": preset,
                "intensity": intensity,
            }, self._live_socket)
            logger.info(f"WallpaperManager: live preset switch: {result}")
        else:
            # Not running — launch binary
            self._stop_live()
            cmd = [
                binary,
                "--preset", preset,
                "--intensity", intensity,
                "--socket", self._live_socket,
            ]
            try:
                self._live_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                logger.info(f"WallpaperManager: launched live wallpaper "
                           f"pid={self._live_proc.pid}")
            except OSError as e:
                logger.warning(f"Failed to launch live wallpaper: {e}")
                return {"applied": "live", "error": str(e)}

        return {"applied": "live", "preset": preset, "intensity": intensity}

    def _stop_live(self) -> None:
        """Stop the live wallpaper binary if running."""
        if _is_live_running(self._live_socket):
            _send_live_command({"cmd": "quit"}, self._live_socket)

        if self._live_proc:
            try:
                self._live_proc.terminate()
                self._live_proc.wait(timeout=3)
            except Exception:
                try:
                    self._live_proc.kill()
                except Exception:
                    pass
            self._live_proc = None

    def suspend_for_game(self) -> None:
        """Suspend live wallpaper rendering during fullscreen games."""
        _send_live_command({"cmd": "suspend"}, self._live_socket)

    def resume_from_game(self) -> None:
        """Resume live wallpaper after game exits fullscreen."""
        _send_live_command({"cmd": "resume_from_suspend"}, self._live_socket)

    def get_live_status(self) -> dict:
        """Query the live wallpaper binary status."""
        return _send_live_command({"cmd": "status"}, self._live_socket)

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
        status = {
            "type":          self.config.get("type",  "color"),
            "value":         self.config.get("value", "#1c1c1e"),
            "video_running": self.video.is_running(),
            "video_paused":  self.video.paused,
            "vaapi":         check_vaapi()["available"],
            "locked":        self.locked,
        }
        if self.config.get("type") == "live":
            status["live"] = self.get_live_status()
        return status

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
