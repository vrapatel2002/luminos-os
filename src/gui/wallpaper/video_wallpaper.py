"""
src/gui/wallpaper/video_wallpaper.py
mpv-based video wallpaper — renders below all windows on Wayland.

Uses VA-API hardware decode on the AMD iGPU when available;
falls back to CPU software decode automatically via get_decode_flags().

VideoWallpaper is a plain Python class — no GTK, no display required
for construction or logic testing.
"""

import logging
import os
import signal
import subprocess

logger = logging.getLogger(__name__)

_DEVNULL = subprocess.DEVNULL


class VideoWallpaper:
    """
    Manages an mpv subprocess that renders a looping video as the desktop
    wallpaper on a Wayland compositor.

    The mpv process is launched with:
      --layer=background   → below all other surfaces
      --wid=auto           → Wayland surface via mpv's wayland backend
      --no-osc             → no on-screen controls
      --no-config          → ignore user mpv.conf

    Hardware decode (VA-API) vs CPU decode is chosen automatically by
    get_decode_flags() from vaapi_check.py.
    """

    def __init__(self):
        self.process:      subprocess.Popen | None = None
        self.current_path: str | None              = None
        self.paused:       bool                    = False

    # -----------------------------------------------------------------------
    # Command building (pure logic — testable without a display)
    # -----------------------------------------------------------------------

    def _build_mpv_cmd(self, path: str, config: dict) -> list:
        """
        Build the mpv command list for a given video path and wallpaper config.

        Args:
            path:   Absolute path to the video file.
            config: Wallpaper config dict (video_loop, video_speed, video_mute).

        Returns:
            List of strings suitable for subprocess.Popen().
        """
        from gui.wallpaper.vaapi_check import get_decode_flags

        loop_flag  = "--loop"      if config.get("video_loop",  True)  else ""
        mute_flag  = "--no-audio"  if config.get("video_mute",  True)  else "--audio"
        speed      = config.get("video_speed", 1.0)

        raw_cmd = [
            "mpv",
            path,
            loop_flag,
            f"--speed={speed}",
            mute_flag,
            "--no-osc",
            "--no-input-default-bindings",
            "--no-config",
            "--wid=auto",
            "--layer=background",
            "--ontop=no",
            "--border=no",
            "--fullscreen",
        ] + get_decode_flags()

        # Filter empty strings (e.g. loop_flag when loop=False)
        return [part for part in raw_cmd if part]

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start(self, path: str, config: dict) -> dict:
        """
        Start mpv with the given video path and config.
        Stops any currently running mpv first.

        Returns:
            {"success": bool, "pid": int | None, "error": str | None}
        """
        if self.is_running():
            self.stop()

        cmd = self._build_mpv_cmd(path, config)
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=_DEVNULL,
                stderr=_DEVNULL,
            )
            self.current_path = path
            self.paused = False
            logger.info(f"VideoWallpaper: started mpv PID {self.process.pid}")
            return {"success": True, "pid": self.process.pid, "error": None}
        except FileNotFoundError:
            self.process = None
            return {"success": False, "pid": None, "error": "mpv not installed"}
        except Exception as e:
            self.process = None
            return {"success": False, "pid": None, "error": str(e)}

    def stop(self) -> bool:
        """
        Terminate the mpv process gracefully (SIGTERM → wait 3 s).
        Returns True if the process was stopped or was not running.
        """
        if self.process is None:
            return True
        try:
            self.process.terminate()
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                self.process.kill()
                self.process.wait(timeout=2)
            except Exception:
                pass
        except Exception:
            pass
        self.process = None
        self.current_path = None
        self.paused = False
        logger.info("VideoWallpaper: mpv stopped")
        return True

    def pause(self) -> None:
        """Send SIGSTOP to the mpv process (freeze video decode)."""
        if self.process is not None and self.process.poll() is None:
            try:
                os.kill(self.process.pid, signal.SIGSTOP)
                self.paused = True
                logger.debug("VideoWallpaper: paused (SIGSTOP)")
            except Exception as e:
                logger.debug(f"VideoWallpaper: pause failed — {e}")

    def resume(self) -> None:
        """Send SIGCONT to the mpv process (unfreeze video decode)."""
        if self.process is not None and self.process.poll() is None:
            try:
                os.kill(self.process.pid, signal.SIGCONT)
                self.paused = False
                logger.debug("VideoWallpaper: resumed (SIGCONT)")
            except Exception as e:
                logger.debug(f"VideoWallpaper: resume failed — {e}")

    def is_running(self) -> bool:
        """Return True if the mpv process is alive."""
        return self.process is not None and self.process.poll() is None
