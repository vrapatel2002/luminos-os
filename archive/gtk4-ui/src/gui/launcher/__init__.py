"""
src/gui/launcher/__init__.py
App launcher singleton.

Usage:
    from gui.launcher import toggle_launcher
    toggle_launcher()
"""

import logging

logger = logging.getLogger("luminos-ai.gui.launcher")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_launcher = None


def get_launcher():
    """
    Return the singleton LuminosLauncher, creating it on first call.

    Returns:
        LuminosLauncher instance, or None if GTK is unavailable.
    """
    global _launcher
    if not _GTK_AVAILABLE:
        return None
    if _launcher is None:
        from gui.launcher.launcher_window import LuminosLauncher
        _launcher = LuminosLauncher()
    return _launcher


def toggle_launcher():
    """Toggle launcher visibility. No-op if GTK unavailable."""
    launcher = get_launcher()
    if launcher is not None:
        launcher.toggle()
