"""
src/gui/notifications/__init__.py
Module-level singleton API for the Luminos notification system.

Public API
----------
send(notif)                         Push any Notification to the overlay.
send_sentinel_alert(process, threat)
send_gaming_on()
send_gaming_off()
send_thermal_warning(temp)
send_model_loaded(model, quant)
get_unread_count() -> int

All functions are safe to call from the daemon (headless) context:
if GTK is unavailable, they silently no-op.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

from gui.notifications.notification_model import (
    Notification,
    sentinel_alert,
    gaming_mode_on,
    gaming_mode_off,
    thermal_warning,
    model_loaded,
)

# ---------------------------------------------------------------------------
# Singleton overlay
# ---------------------------------------------------------------------------

_overlay = None


def _get_overlay():
    global _overlay
    if not _GTK_AVAILABLE:
        return None
    if _overlay is None:
        try:
            from gui.notifications.toast_overlay import ToastOverlay
            _overlay = ToastOverlay()
        except Exception as e:
            logger.debug(f"ToastOverlay init failed (headless?): {e}")
            return None
    return _overlay


# ---------------------------------------------------------------------------
# Public send functions
# ---------------------------------------------------------------------------

def send(notif: Notification) -> None:
    """Send any Notification to the overlay."""
    overlay = _get_overlay()
    if overlay is not None:
        try:
            overlay.send(notif)
        except Exception as e:
            logger.debug(f"send() error: {e}")


def send_sentinel_alert(process: str, threat: str) -> None:
    send(sentinel_alert(process, threat))


def send_gaming_on() -> None:
    send(gaming_mode_on())


def send_gaming_off() -> None:
    send(gaming_mode_off())


def send_thermal_warning(temp: float) -> None:
    send(thermal_warning(temp))


def send_model_loaded(model: str, quant: str) -> None:
    send(model_loaded(model, quant))


def get_unread_count() -> int:
    """Return unread notification count, or 0 if GUI unavailable."""
    overlay = _get_overlay()
    if overlay is None:
        return 0
    try:
        return overlay.get_center().get_unread_count()
    except Exception:
        return 0
