"""
src/hardware/display_manager.py
Smart refresh rate manager for ASUS ROG G14.

Monitors fullscreen apps via hyprctl. Auto-switches between 60Hz and 120Hz
based on user setting:
  "auto"       — 60Hz desktop, 120Hz fullscreen games
  "always_60"  — locked to 60Hz
  "always_120" — locked to 120Hz

Pure helpers:
    get_refresh_modes()    → list[dict]
    load_display_setting() → str
    save_display_setting() → bool
"""

import json
import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger("luminos-ai.hardware.display")

_DISPLAY_CONFIG_PATH = os.path.expanduser("~/.config/luminos/display.json")
_DISPLAY_OUTPUT = "eDP-1"

REFRESH_MODES: list[dict] = [
    {"id": "auto",       "label": "Auto (recommended)", "description": "60Hz desktop, 120Hz for games"},
    {"id": "always_60",  "label": "Always 60Hz",        "description": "Saves battery"},
    {"id": "always_120", "label": "Always 120Hz",       "description": "Smooth always"},
]


# ===========================================================================
# Pure helpers — testable without hardware
# ===========================================================================

def get_refresh_modes() -> list[dict]:
    """Return available refresh rate mode options."""
    return list(REFRESH_MODES)


def load_display_setting() -> str:
    """
    Load saved refresh rate mode from config.

    Returns "auto", "always_60", or "always_120". Defaults to "auto".
    """
    try:
        with open(_DISPLAY_CONFIG_PATH) as f:
            data = json.load(f)
            mode = data.get("refresh_mode", "auto")
            if mode in ("auto", "always_60", "always_120"):
                return mode
    except (OSError, json.JSONDecodeError):
        pass
    return "auto"


def save_display_setting(mode: str) -> bool:
    """Save refresh rate mode to config."""
    if mode not in ("auto", "always_60", "always_120"):
        return False
    try:
        os.makedirs(os.path.dirname(_DISPLAY_CONFIG_PATH), exist_ok=True)
        # Merge with existing config
        existing = {}
        try:
            with open(_DISPLAY_CONFIG_PATH) as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
        existing["refresh_mode"] = mode
        with open(_DISPLAY_CONFIG_PATH, "w") as f:
            json.dump(existing, f, indent=2)
        return True
    except OSError as e:
        logger.warning(f"Could not save display config: {e}")
        return False


# ===========================================================================
# Display manager
# ===========================================================================

class DisplayManager:
    """
    Smart refresh rate manager.

    Polls hyprctl every 2 seconds for fullscreen state.
    Switches refresh rate based on user setting.
    """

    def __init__(self, output: str = _DISPLAY_OUTPUT):
        self._output = output
        self._running = False
        self._thread: threading.Thread | None = None
        self._current_hz: int | None = None
        self._mode = load_display_setting()
        self._last_fullscreen = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the refresh rate monitor thread."""
        if self._running:
            return
        self._running = True
        self._mode = load_display_setting()

        # Apply initial rate based on mode
        if self._mode == "always_120":
            self._set_refresh(120)
        else:
            self._set_refresh(60)

        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="luminos-display-manager",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"Display manager started (mode={self._mode})")

    def stop(self):
        """Stop the monitor thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Display manager stopped")

    def set_mode(self, mode: str):
        """Change the refresh rate mode and apply immediately."""
        if mode not in ("auto", "always_60", "always_120"):
            return
        self._mode = mode
        save_display_setting(mode)

        if mode == "always_60":
            self._set_refresh(60)
        elif mode == "always_120":
            self._set_refresh(120)
        else:
            # Auto — check current fullscreen state
            if self._last_fullscreen:
                self._set_refresh(120)
            else:
                self._set_refresh(60)

        logger.info(f"Display mode changed to {mode}")

    # ------------------------------------------------------------------
    # Monitor loop
    # ------------------------------------------------------------------

    def _monitor_loop(self):
        """Poll fullscreen state every 2 seconds."""
        while self._running:
            try:
                if self._mode == "auto":
                    is_fs = self._check_fullscreen()
                    if is_fs and not self._last_fullscreen:
                        self._set_refresh(120)
                    elif not is_fs and self._last_fullscreen:
                        self._set_refresh(60)
                    self._last_fullscreen = is_fs
            except Exception as e:
                logger.debug(f"Display monitor error: {e}")
            time.sleep(2.0)

    # ------------------------------------------------------------------
    # Fullscreen detection
    # ------------------------------------------------------------------

    @staticmethod
    def _check_fullscreen() -> bool:
        """Check if active window is fullscreen via hyprctl."""
        try:
            result = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return data.get("fullscreen", 0) > 0
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError, OSError):
            pass
        return False

    # ------------------------------------------------------------------
    # Refresh rate control
    # ------------------------------------------------------------------

    def _set_refresh(self, hz: int):
        """Set monitor refresh rate via hyprctl."""
        if self._current_hz == hz:
            return

        cmd = f"{self._output},1920x1200@{hz},auto,1"
        try:
            result = subprocess.run(
                ["hyprctl", "keyword", "monitor", cmd],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                self._current_hz = hz
                logger.info(f"Refresh rate → {hz}Hz")
            else:
                logger.debug(f"hyprctl monitor error: {result.stderr.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            logger.debug(f"Could not set refresh rate: {e}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current display manager state."""
        return {
            "mode": self._mode,
            "current_hz": self._current_hz,
            "fullscreen": self._last_fullscreen,
            "monitoring": self._running,
        }
