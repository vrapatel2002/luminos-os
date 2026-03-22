"""
src/gui/launcher/app_result_item.py
AppResultItem — single application icon + label widget in the launcher grid.

Architecture:
- Static pure methods (_get_display_name, _get_zone_hint) testable headless.
- GTK widget guarded behind _GTK_AVAILABLE.
- Zone 2 overlays zone2_badge; zone 3 overlays zone3_badge.
- Hover: background highlight via CSS class.
- Click: calls parent window's _on_item_activated(item).
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.launcher.item")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme import find_icon

_DISPLAY_NAME_MAX = 12
_ICON_SIZE        = 48


# ===========================================================================
# Pure logic — testable without GTK
# ===========================================================================

def _get_display_name(name: str) -> str:
    """
    Truncate name to _DISPLAY_NAME_MAX characters.

    Args:
        name: Full application name.

    Returns:
        Name as-is if ≤12 chars, else first 12 + "…".
    """
    if len(name) <= _DISPLAY_NAME_MAX:
        return name
    return name[:_DISPLAY_NAME_MAX] + "…"


def _get_zone_hint(zone: int) -> str:
    """
    Return a small zone indicator string shown below the app name.

    Args:
        zone: 1 (native), 2 (Wine), 3 (quarantine VM).

    Returns:
        "" for zone 1, "Wine" for zone 2, "⚠ VM" for zone 3.
    """
    if zone == 2:
        return "Wine"
    if zone == 3:
        return "⚠ VM"
    return ""


# ===========================================================================
# GTK widget
# ===========================================================================

if _GTK_AVAILABLE:

    class AppResultItem(Gtk.Box):
        """
        Single application result tile for the launcher grid.

        Layout (vertical, centered):
          [icon 48×48 + zone badge overlay]
          [name label — truncated to 12 chars]
          [zone hint — "Wine" / "⚠ VM" / empty]

        Signals:
          Click → calls parent._on_item_activated(self)
        """

        def __init__(self, app: dict, zone: int = 1):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.app  = app
            self.zone = zone
            self.add_css_class("launcher-item")
            self._build()

        # -------------------------------------------------------------------
        # Static pure methods (used directly by tests)
        # -------------------------------------------------------------------

        @staticmethod
        def _get_display_name(name: str) -> str:
            return _get_display_name(name)

        @staticmethod
        def _get_zone_hint(zone: int) -> str:
            return _get_zone_hint(zone)

        # -------------------------------------------------------------------
        # Build
        # -------------------------------------------------------------------

        def _build(self):
            self.set_halign(Gtk.Align.CENTER)
            self.set_size_request(80, -1)

            # Icon overlay (badge sits bottom-right)
            overlay = Gtk.Overlay()
            overlay.set_halign(Gtk.Align.CENTER)

            icon_name = self.app.get("icon", "application-x-executable")
            icon_path = find_icon(icon_name, _ICON_SIZE)
            if icon_path:
                self._icon = Gtk.Image.new_from_file(icon_path)
            else:
                self._icon = Gtk.Image.new_from_icon_name(icon_name)
            self._icon.set_pixel_size(_ICON_SIZE)
            overlay.set_child(self._icon)

            # Zone badge
            if self.zone == 2:
                badge = Gtk.Label(label="W")
                badge.add_css_class("zone-badge-2")
                badge.set_halign(Gtk.Align.END)
                badge.set_valign(Gtk.Align.END)
                overlay.add_overlay(badge)
            elif self.zone == 3:
                badge = Gtk.Label(label="⚠")
                badge.add_css_class("zone-badge-3")
                badge.set_halign(Gtk.Align.END)
                badge.set_valign(Gtk.Align.END)
                overlay.add_overlay(badge)

            self.append(overlay)

            # Name label
            name_lbl = Gtk.Label(
                label=_get_display_name(self.app.get("name", ""))
            )
            name_lbl.add_css_class("launcher-item-name")
            name_lbl.set_halign(Gtk.Align.CENTER)
            self.append(name_lbl)

            # Zone hint (zone 2/3 only)
            hint = _get_zone_hint(self.zone)
            if hint:
                hint_lbl = Gtk.Label(label=hint)
                css = "zone-badge-2" if self.zone == 2 else "zone-badge-3"
                hint_lbl.add_css_class(css)
                hint_lbl.add_css_class("launcher-item-hint")
                hint_lbl.set_halign(Gtk.Align.CENTER)
                self.append(hint_lbl)

            # Hover
            motion = Gtk.EventControllerMotion()
            motion.connect("enter",  lambda *_: self.add_css_class("selected"))
            motion.connect("leave",  lambda *_: self.remove_css_class("selected"))
            self.add_controller(motion)

            # Click
            click = Gtk.GestureClick()
            click.connect("pressed", self._on_click)
            self.add_controller(click)

        # -------------------------------------------------------------------
        # Selection state
        # -------------------------------------------------------------------

        def set_selected(self, selected: bool):
            """Highlight or unhighlight this tile."""
            if selected:
                self.add_css_class("selected")
            else:
                self.remove_css_class("selected")

        # -------------------------------------------------------------------
        # Click
        # -------------------------------------------------------------------

        def _on_click(self, *_):
            parent = self.get_parent()
            while parent is not None:
                if hasattr(parent, "_on_item_activated"):
                    parent._on_item_activated(self)
                    return
                parent = parent.get_parent()
