"""
src/gui/quick_settings/__init__.py
Quick Settings panel singleton.

Usage (from bar or any widget):
    from gui.quick_settings import toggle_panel
    toggle_panel()
"""

import logging

logger = logging.getLogger("luminos-ai.gui.quick_settings")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_panel = None


def get_panel():
    """
    Return the singleton QuickSettingsPanel, creating it on first call.

    Returns:
        QuickSettingsPanel instance, or None if GTK is unavailable.
    """
    global _panel
    if not _GTK_AVAILABLE:
        return None
    if _panel is None:
        from gui.quick_settings.quick_panel import QuickSettingsPanel
        _panel = QuickSettingsPanel()
    return _panel


def toggle_panel():
    """Show the panel if hidden, hide if visible. Closes notification panel first."""
    try:
        from gui.notifications import get_panel as get_notif_panel
        notif = get_notif_panel()
        if notif and notif.get_visible():
            notif.hide()
    except Exception:
        pass
    panel = get_panel()
    if panel is not None:
        panel.toggle()
