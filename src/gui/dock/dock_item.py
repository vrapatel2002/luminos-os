"""
src/gui/dock/dock_item.py
DockItem — a single application icon in the Luminos dock.

Architecture:
- Static/pure methods (_get_tooltip, _should_show_badge) are testable
  without a display.
- GTK widget class guarded behind _GTK_AVAILABLE so tests import cleanly.
- Zone badge overlaid bottom-right via Gtk.Overlay.
- Open-state dot indicator shown below icon when app is running.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.dock.item")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Pango
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme import find_icon


# ===========================================================================
# Pure logic — testable without GTK
# ===========================================================================

def _get_tooltip(app_info: dict, zone: int) -> str:
    """
    Build tooltip text for a dock item.

    Args:
        app_info: Dict with at least {"name": str}.
        zone:     Execution zone (1 = native, 2 = Wine, 3 = Quarantine).

    Returns:
        Display string, e.g. "Firefox", "game.exe (Wine)",
        "anticheat.exe (Quarantine ⚠)".
    """
    name = app_info.get("name", app_info.get("exec", "App"))
    if zone == 2:
        return f"{name} (Wine)"
    if zone == 3:
        return f"{name} (Quarantine ⚠)"
    return name


def _should_show_badge(zone: int) -> bool:
    """Return True if the zone warrants a visual badge overlay."""
    return zone in (2, 3)


# ===========================================================================
# GTK widget
# ===========================================================================

if _GTK_AVAILABLE:

    # Emitted when the user clicks a dock item.
    # Connect: item.connect("app-activated", handler)
    # (We register it as a regular signal on the class below.)

    ICON_SIZE         = 48   # px — normal state
    ICON_SIZE_HOVER   = 54   # px — hover magnification
    BADGE_SIZE        = 14   # px — zone badge overlay
    DOT_SIZE          = 4    # px — open-state indicator dot

    class DockItem(Gtk.Box):
        """
        Single application icon widget for the Luminos dock.

        Signals:
            app-activated: Emitted on click. Connect with no extra args.
        """

        def __init__(self, app_info: dict,
                     is_open: bool = False,
                     zone: int = 1):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            self.app_info = app_info
            self.is_open  = is_open
            self.zone     = zone

            self._build()

        # -------------------------------------------------------------------
        # Static pure methods (used by tests without instantiating)
        # -------------------------------------------------------------------

        @staticmethod
        def _get_tooltip(app_info: dict, zone: int) -> str:
            return _get_tooltip(app_info, zone)

        @staticmethod
        def _should_show_badge(zone: int) -> bool:
            return _should_show_badge(zone)

        # -------------------------------------------------------------------
        # Build
        # -------------------------------------------------------------------

        def _build(self):
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.END)
            self.add_css_class("luminos-dock-item")
            self.set_tooltip_text(_get_tooltip(self.app_info, self.zone))

            # --- Icon container (overlay for badge) ---
            icon_overlay = Gtk.Overlay()

            # Icon image
            icon_name = self.app_info.get("icon", "application-x-executable")
            icon_path = find_icon(icon_name, ICON_SIZE)

            if icon_path:
                self._icon = Gtk.Image.new_from_file(icon_path)
            else:
                self._icon = Gtk.Image.new_from_icon_name(icon_name)
            self._icon.set_pixel_size(ICON_SIZE)
            self._icon.add_css_class("luminos-dock-icon")

            icon_overlay.set_child(self._icon)

            # Zone badge (bottom-right corner)
            self._badge = None
            if _should_show_badge(self.zone):
                self._badge = self._make_badge(self.zone)
                self._badge.set_halign(Gtk.Align.END)
                self._badge.set_valign(Gtk.Align.END)
                icon_overlay.add_overlay(self._badge)

            self.append(icon_overlay)

            # --- Open-state dot indicator ---
            self._dot = Gtk.DrawingArea()
            self._dot.set_size_request(DOT_SIZE, DOT_SIZE)
            self._dot.set_halign(Gtk.Align.CENTER)
            self._dot.set_draw_func(self._draw_dot)
            self._dot.set_visible(self.is_open)
            self.append(self._dot)

            # --- Hover: scale icon on enter/leave ---
            motion = Gtk.EventControllerMotion()
            motion.connect("enter",  self._on_hover_enter)
            motion.connect("leave",  self._on_hover_leave)
            self.add_controller(motion)

            # --- Click ---
            click = Gtk.GestureClick()
            click.connect("pressed", self._on_click)
            self.add_controller(click)

        def _make_badge(self, zone: int) -> Gtk.Label:
            """Return a small label badge for zone 2 or 3."""
            if zone == 2:
                badge = Gtk.Label(label="W")
                badge.add_css_class("zone-badge-2")
            else:
                badge = Gtk.Label(label="⚠")
                badge.add_css_class("zone-badge-3")
            badge.set_size_request(BADGE_SIZE, BADGE_SIZE)
            return badge

        # -------------------------------------------------------------------
        # Drawing
        # -------------------------------------------------------------------

        def _draw_dot(self, area, cr, width, height):
            """Draw the small accent-blue open-indicator dot."""
            # accent_blue ≈ #0a84ff
            cr.set_source_rgb(0.039, 0.518, 1.0)
            cx = width  / 2
            cy = height / 2
            r  = min(width, height) / 2
            import math
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.fill()

        # -------------------------------------------------------------------
        # Hover magnification
        # -------------------------------------------------------------------

        def _on_hover_enter(self, *_):
            self._icon.set_pixel_size(ICON_SIZE_HOVER)

        def _on_hover_leave(self, *_):
            self._icon.set_pixel_size(ICON_SIZE)

        # -------------------------------------------------------------------
        # Click
        # -------------------------------------------------------------------

        def _on_click(self, gesture, n_press, x, y):
            # Walk up to the dock window and call its activation handler
            parent = self.get_parent()
            while parent is not None:
                if hasattr(parent, "_on_item_activated"):
                    parent._on_item_activated(self)
                    return
                parent = parent.get_parent()

        # -------------------------------------------------------------------
        # State updates
        # -------------------------------------------------------------------

        def set_open(self, open_state: bool):
            """Show or hide the open-state dot indicator."""
            self.is_open = open_state
            self._dot.set_visible(open_state)

        def set_zone(self, zone: int):
            """Update zone badge overlay."""
            self.zone = zone
            self.set_tooltip_text(_get_tooltip(self.app_info, zone))
            # Remove old badge if present
            if self._badge is not None:
                # Overlay children: find and remove via the overlay parent
                overlay = self._icon.get_parent()  # Gtk.Overlay
                if isinstance(overlay, Gtk.Overlay):
                    overlay.remove_overlay(self._badge)
                self._badge = None
            # Add new badge if needed
            if _should_show_badge(zone):
                overlay = self._icon.get_parent()
                if isinstance(overlay, Gtk.Overlay):
                    self._badge = self._make_badge(zone)
                    self._badge.set_halign(Gtk.Align.END)
                    self._badge.set_valign(Gtk.Align.END)
                    overlay.add_overlay(self._badge)
