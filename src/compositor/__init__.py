"""
src/compositor/__init__.py
Public API for the Luminos Compositor layer.

Exposes window management, upscaling, and config generation
via a minimal, daemon-friendly interface.

Usage:
    from compositor import register_window, set_upscale_mode, get_display_status
    result = register_window(pid=1234, exe_path="/path/to/app.exe", zone=2)
    # {"pid": 1234, "zone": 2, "border": "blue", "xwayland": True, ...}
"""

from .window_manager    import WindowManager
from .upscale_manager   import UpscaleManager
from .compositor_config import generate_sway_config, write_config, generate_waybar_config

# Module-level singletons — one instance per daemon lifetime
_wm  = WindowManager()
_upm = UpscaleManager()


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

def register_window(pid: int, exe_path: str, zone: int) -> dict:
    """Register a new window with zone-derived display rules."""
    return _wm.register_window(pid, exe_path, zone)


def unregister_window(pid: int) -> dict:
    """Remove a window from tracking."""
    return _wm.unregister_window(pid)


def focus_window(pid: int) -> dict:
    """Set focus to the given window PID."""
    return _wm.focus_window(pid)


def list_windows() -> list:
    """Return all currently registered windows."""
    return _wm.list_windows()


def get_zone_summary() -> dict:
    """Return window count per zone."""
    return _wm.get_zone_summary()


# ---------------------------------------------------------------------------
# Upscaling
# ---------------------------------------------------------------------------

def set_upscale_mode(mode: str) -> dict:
    """Set FSR/NIS upscaling mode: off | quality | balanced | performance."""
    return _upm.set_mode(mode)


def get_display_status() -> dict:
    """Return current upscale mode and live display info."""
    return _upm.get_status()


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------

def generate_config(output_path: str = "~/.config/sway/config") -> dict:
    """Write generated Sway config to output_path."""
    return write_config(output_path)
