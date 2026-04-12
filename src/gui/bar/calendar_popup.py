"""
src/gui/bar/calendar_popup.py
CalendarPopup — dropdown calendar from the clock in the top bar.

Pinned to top edge via gtk4-layer-shell, centered on screen.
Closes on Escape or focus loss.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.bar.calendar")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_LAYER_SHELL_AVAILABLE = False
if _GTK_AVAILABLE:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        _LAYER_SHELL_AVAILABLE = True
    except (ImportError, ValueError):
        pass

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL,
    SPACE_3, SPACE_4, RADIUS_DEFAULT, BAR_HEIGHT,
    SHADOW_PANEL, glass_bg,
)

_CAL_CSS = f"""
window {{
    background: transparent;
}}

.luminos-calendar-popup {{
    background: {glass_bg(0.25)};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_DEFAULT}px;
    box-shadow: {SHADOW_PANEL};
    padding: {SPACE_3}px;
}}

calendar {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    border: none;
}}

calendar:selected {{
    background-color: rgba(0, 128, 255, 0.6);
    border-radius: 4px;
    color: white;
}}

calendar.header {{
    font-size: {FONT_BODY}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    background: transparent;
}}

calendar.button {{
    color: {TEXT_SECONDARY};
    background: transparent;
    border: none;
}}

calendar.highlight {{
    color: rgba(0, 128, 255, 0.9);
    font-weight: 600;
}}

calendar.day-name {{
    color: {TEXT_DISABLED};
    font-size: {FONT_BODY_SMALL}px;
}}
"""

if _GTK_AVAILABLE:

    class CalendarPopup(Gtk.Window):
        """Centered calendar dropdown below the bar clock."""

        def __init__(self):
            super().__init__()
            self.set_title("luminos-calendar")
            self.set_decorated(False)
            self.set_resizable(False)

            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_namespace(self, "luminos-calendar")
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                # Anchor TOP only → compositor centers horizontally
                LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
                LayerShell.set_margin(self, LayerShell.Edge.TOP, 3)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.ON_DEMAND
                )

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_CAL_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key_pressed)
            self.add_controller(key_ctrl)

            self.connect("notify::is-active", self._on_active_changed)

            self._build()

        def _ensure_css(self):
            try:
                Gtk.StyleContext.add_provider_for_display(
                    self.get_display(), self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception:
                pass

        def _build(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            box.add_css_class("luminos-calendar-popup")
            self.set_child(box)

            self._calendar = Gtk.Calendar()
            box.append(self._calendar)

        def show_popup(self):
            import datetime
            now = datetime.date.today()
            self._calendar.select_day(
                GLib.DateTime.new_local(now.year, now.month, now.day, 0, 0, 0)
            )
            self._just_shown = True
            GLib.timeout_add(400, self._clear_just_shown)
            self.present()

        def _clear_just_shown(self):
            self._just_shown = False
            return False

        def _on_active_changed(self, window, _param):
            if not window.is_active() and not getattr(self, "_just_shown", False):
                self.hide()

        def toggle(self):
            if self.get_visible():
                self.hide()
            else:
                self.show_popup()

        def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
            if keyval == Gdk.KEY_Escape:
                self.hide()
                return True
            return False


_calendar_popup = None


def get_calendar_popup():
    global _calendar_popup
    if not _GTK_AVAILABLE:
        return None
    if _calendar_popup is None:
        _calendar_popup = CalendarPopup()
    return _calendar_popup


def toggle_calendar():
    popup = get_calendar_popup()
    if popup is not None:
        popup.toggle()
