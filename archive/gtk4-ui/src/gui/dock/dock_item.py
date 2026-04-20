"""
src/gui/dock/dock_item.py
DockItem — a single application icon in the Luminos dock.

Visual spec (from LUMINOS_DESIGN_SYSTEM.md):
  Icon size: DOCK_ICON_SIZE (48px)
  Hover: scale 1.1x over ANIM_FAST (100ms), ACCENT_GLOW beneath icon
  Click: scale 0.95x instant, back to 1.0x over ANIM_FAST
  Active indicator: 4px circle below icon, ACCENT color
  Labels: hidden, appear on hover after 500ms, pill-shaped BG_ELEVATED
  Zone badge: bottom-right corner overlay

Pure helpers (_get_tooltip, _should_show_badge) testable without GTK.
"""

import logging
import math
import os
import sys

logger = logging.getLogger("luminos-ai.gui.dock.item")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    ACCENT, ACCENT_GLOW, BG_ELEVATED, TEXT_SECONDARY,
    FONT_FAMILY, FONT_CAPTION,
    DOCK_ICON_SIZE, RADIUS_SM,
    ANIM_FAST, ANIM_INSTANT,
)
from gui.theme import find_icon


# ===========================================================================
# Pure logic — testable without GTK
# ===========================================================================

def _get_tooltip(app_info: dict, zone: int) -> str:
    """Build tooltip text for a dock item."""
    name = app_info.get("name", app_info.get("exec", "App"))
    if zone == 2:
        return f"{name} (Wine)"
    if zone == 3:
        return f"{name} (Quarantine)"
    return name


def _should_show_badge(zone: int) -> bool:
    """Return True if the zone warrants a visual badge overlay."""
    return zone in (2, 3)


# ===========================================================================
# GTK widget
# ===========================================================================

if _GTK_AVAILABLE:

    ICON_HOVER_SIZE = int(DOCK_ICON_SIZE * 1.1)  # 52px
    ICON_PRESS_SIZE = int(DOCK_ICON_SIZE * 0.95)  # 45px
    DOT_SIZE = 4
    BADGE_SIZE = 14
    LABEL_DELAY_MS = 500

    class DockItem(Gtk.Box):
        """Single application icon widget for the Luminos dock."""

        def __init__(self, app_info: dict,
                     is_open: bool = False,
                     zone: int = 1):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            self.app_info = app_info
            self.is_open = is_open
            self.zone = zone
            self._label_timeout_id = None
            self._build()

        @staticmethod
        def _get_tooltip(app_info: dict, zone: int) -> str:
            return _get_tooltip(app_info, zone)

        @staticmethod
        def _should_show_badge(zone: int) -> bool:
            return _should_show_badge(zone)

        def _build(self):
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.END)
            self.add_css_class("luminos-dock-item")

            # Icon container with overlay for badge
            icon_overlay = Gtk.Overlay()

            icon_name = self.app_info.get("icon", "application-x-executable")
            # Use new_from_icon_name so set_pixel_size is respected for correct
            # 48px sizing. new_from_file ignores set_pixel_size (GTK4 limitation).
            self._icon = Gtk.Image.new_from_icon_name(icon_name)
            self._icon.set_pixel_size(DOCK_ICON_SIZE)
            self._icon.add_css_class("luminos-dock-icon")

            icon_overlay.set_child(self._icon)

            # Zone badge (bottom-right)
            self._badge = None
            if _should_show_badge(self.zone):
                self._badge = self._make_badge(self.zone)
                self._badge.set_halign(Gtk.Align.END)
                self._badge.set_valign(Gtk.Align.END)
                icon_overlay.add_overlay(self._badge)

            self.append(icon_overlay)

            # Active indicator dot — 4px circle, ACCENT color
            self._dot = Gtk.DrawingArea()
            self._dot.set_size_request(DOT_SIZE, DOT_SIZE)
            self._dot.set_halign(Gtk.Align.CENTER)
            self._dot.set_draw_func(self._draw_dot)
            self._dot.set_visible(self.is_open)
            self.append(self._dot)

            # Hover label (hidden, appears after 500ms delay)
            self._label = Gtk.Label(
                label=self.app_info.get("name", "App")
            )
            self._label.add_css_class("luminos-dock-label")
            self._label.set_visible(False)
            self.append(self._label)

            # Hover controller
            motion = Gtk.EventControllerMotion()
            motion.connect("enter", self._on_hover_enter)
            motion.connect("leave", self._on_hover_leave)
            self.add_controller(motion)

            # Click controller
            click = Gtk.GestureClick()
            click.connect("pressed", self._on_press)
            click.connect("released", self._on_release)
            self.add_controller(click)

        def _make_badge(self, zone: int) -> Gtk.Label:
            if zone == 2:
                badge = Gtk.Label(label="W")
                badge.add_css_class("zone-badge-2")
            else:
                badge = Gtk.Label(label="!")
                badge.add_css_class("zone-badge-3")
            badge.set_size_request(BADGE_SIZE, BADGE_SIZE)
            return badge

        # -------------------------------------------------------------------
        # Drawing
        # -------------------------------------------------------------------

        def _draw_dot(self, area, cr, width, height):
            """Draw the 4px ACCENT circle indicator."""
            # ACCENT = #0080FF → rgb(0, 128, 255)
            cr.set_source_rgb(0.0, 0.502, 1.0)
            cx = width / 2
            cy = height / 2
            r = min(width, height) / 2
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.fill()

        # -------------------------------------------------------------------
        # Hover: scale 1.1x, show glow, delayed label
        # -------------------------------------------------------------------

        def _on_hover_enter(self, *_):
            self._icon.set_pixel_size(ICON_HOVER_SIZE)
            # Schedule label appearance after 500ms
            if self._label_timeout_id is not None:
                GLib.source_remove(self._label_timeout_id)
            self._label_timeout_id = GLib.timeout_add(
                LABEL_DELAY_MS, self._show_label
            )

        def _on_hover_leave(self, *_):
            self._icon.set_pixel_size(DOCK_ICON_SIZE)
            # Cancel label timer and hide
            if self._label_timeout_id is not None:
                GLib.source_remove(self._label_timeout_id)
                self._label_timeout_id = None
            self._label.set_visible(False)

        def _show_label(self) -> bool:
            self._label.set_visible(True)
            self._label_timeout_id = None
            return GLib.SOURCE_REMOVE

        # -------------------------------------------------------------------
        # Click: scale 0.95x instant, back to 1.0x fast
        # -------------------------------------------------------------------

        def _on_press(self, gesture, n_press, x, y):
            self._icon.set_pixel_size(ICON_PRESS_SIZE)

        def _on_release(self, gesture, n_press, x, y):
            self._icon.set_pixel_size(DOCK_ICON_SIZE)
            # Walk up to dock window and call activation handler
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
            """Show or hide the active indicator dot."""
            self.is_open = open_state
            self._dot.set_visible(open_state)

        def set_zone(self, zone: int):
            """Update zone badge overlay."""
            self.zone = zone
            if self._badge is not None:
                overlay = self._icon.get_parent()
                if isinstance(overlay, Gtk.Overlay):
                    overlay.remove_overlay(self._badge)
                self._badge = None
            if _should_show_badge(zone):
                overlay = self._icon.get_parent()
                if isinstance(overlay, Gtk.Overlay):
                    self._badge = self._make_badge(zone)
                    self._badge.set_halign(Gtk.Align.END)
                    self._badge.set_valign(Gtk.Align.END)
                    overlay.add_overlay(self._badge)
