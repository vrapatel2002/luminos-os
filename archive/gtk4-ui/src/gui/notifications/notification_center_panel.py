"""
src/gui/notifications/notification_center_panel.py
Notification Center — slide-in panel from right edge.

Visual spec (Phase 5.7):
  Opens from: bell icon in top bar
  Slide-in from right edge, full height, 380px wide
  Background: glass_bg(0.92) with blur(20px)
  Border: 1px BORDER left side only

Contents:
  Header: "Notifications" + "Clear all" button
  Empty state: centered "No notifications" + icon
  List of past notifications, newest first
  Unread: left border 2px ACCENT
  Click: marks as read
  Swipe right or X button: dismisses

Pure helpers:
    format_notification_time(timestamp) → str
"""

import logging
import os
import sys
import time

logger = logging.getLogger("luminos-ai.gui.notifications.center_panel")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Pango
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
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    FONT_FAMILY, FONT_H3, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6,
    RADIUS_MD, BAR_HEIGHT,
    SHADOW_PANEL,
    glass_bg,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def format_notification_time(timestamp: float) -> str:
    """
    Format a notification timestamp as a human-readable relative time.

    Args:
        timestamp: Unix epoch float.

    Returns:
        "Just now", "2m ago", "1h ago", "Yesterday", etc.
    """
    now = time.time()
    diff = now - timestamp

    if diff < 60:
        return "Just now"
    if diff < 3600:
        return f"{int(diff / 60)}m ago"
    if diff < 86400:
        return f"{int(diff / 3600)}h ago"
    if diff < 172800:
        return "Yesterday"
    return f"{int(diff / 86400)}d ago"


# ===========================================================================
# CSS
# ===========================================================================

_PANEL_WIDTH = 380

_CENTER_CSS = f"""
.luminos-notif-center {{
    background: {glass_bg(0.25)};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_MD}px;
    box-shadow: {SHADOW_PANEL};
}}

.luminos-notif-header {{
    min-height: 56px;
    padding: 0 {SPACE_4}px;
}}

.luminos-notif-header-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_H3}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

.luminos-notif-clear-btn {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
    background: transparent;
    border: none;
    padding: {SPACE_2}px {SPACE_3}px;
}}

.luminos-notif-clear-btn:hover {{
    color: {TEXT_PRIMARY};
    background-color: {BG_OVERLAY};
    border-radius: {RADIUS_MD}px;
}}

.luminos-notif-empty {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_DISABLED};
}}

.luminos-notif-item {{
    padding: {SPACE_3}px {SPACE_4}px;
    min-height: 48px;
}}

.luminos-notif-item:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-notif-item-unread {{
    border-left: 2px solid {ACCENT};
}}

.luminos-notif-item-app {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_DISABLED};
}}

.luminos-notif-item-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_PRIMARY};
}}

.luminos-notif-item-body {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
}}

.luminos-notif-item-time {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_DISABLED};
}}

.luminos-notif-item-close {{
    color: {TEXT_DISABLED};
    background: transparent;
    border: none;
    min-width: 24px;
    min-height: 24px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-notif-item-close:hover {{
    color: {TEXT_PRIMARY};
    background-color: {BG_OVERLAY};
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class NotificationCenterPanel(Gtk.Window):
        """
        Notification center — slide-in panel from right edge.

        Shows notification history. Click marks as read.
        Created once, hidden/shown via toggle().
        """

        def __init__(self, notification_center=None):
            """
            Args:
                notification_center: NotificationCenter instance for history.
            """
            super().__init__()
            self._center = notification_center
            self.set_title("luminos-notification-center")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(_PANEL_WIDTH, -1)

            # Layer shell — pin to top-right, full height, below bar
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_namespace(self, "luminos-notification-center")
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
                LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, True)
                LayerShell.set_margin(self, LayerShell.Edge.TOP, 3)
                LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 3)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.ON_DEMAND
                )

            # CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_CENTER_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            self.add_css_class("luminos-notif-center")

            # Hide on focus loss
            self.connect("notify::is-active", self._on_active_changed)

            # Escape closes
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key_pressed)
            self.add_controller(key_ctrl)

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
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_child(root)

            # Header
            header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            header.add_css_class("luminos-notif-header")
            header.set_valign(Gtk.Align.CENTER)

            title = Gtk.Label(label="Notifications")
            title.add_css_class("luminos-notif-header-title")
            title.set_halign(Gtk.Align.START)
            title.set_hexpand(True)
            header.append(title)

            clear_btn = Gtk.Button(label="Clear all")
            clear_btn.add_css_class("luminos-notif-clear-btn")
            clear_btn.connect("clicked", self._on_clear_all)
            header.append(clear_btn)

            root.append(header)

            # Divider
            div = Gtk.Box()
            div.set_size_request(-1, 1)
            div.set_css_classes(["luminos-notif-item"])  # reuse for border
            root.append(div)

            # Scrollable list
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)

            self._list_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            scroll.set_child(self._list_box)
            root.append(scroll)

            # Empty state
            self._empty_label = Gtk.Label(label="No notifications")
            self._empty_label.add_css_class("luminos-notif-empty")
            self._empty_label.set_valign(Gtk.Align.CENTER)
            self._empty_label.set_vexpand(True)
            self._list_box.append(self._empty_label)

        def _refresh(self):
            """Rebuild the notification list from history."""
            # Clear existing items
            child = self._list_box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._list_box.remove(child)
                child = next_child

            history = []
            if self._center:
                history = self._center.get_history()

            if not history:
                self._empty_label = Gtk.Label(label="No notifications")
                self._empty_label.add_css_class("luminos-notif-empty")
                self._empty_label.set_valign(Gtk.Align.CENTER)
                self._empty_label.set_vexpand(True)
                self._list_box.append(self._empty_label)
                return

            for notif in history:
                if getattr(notif, "dismissed", False):
                    continue
                row = self._make_notif_row(notif)
                self._list_box.append(row)

        def _make_notif_row(self, notif) -> Gtk.Box:
            """Build a single notification row widget."""
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            row.add_css_class("luminos-notif-item")
            if not getattr(notif, "read", True):
                row.add_css_class("luminos-notif-item-unread")

            # Text content
            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            text_box.set_hexpand(True)

            # App name + time
            meta_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2
            )
            app_name = getattr(notif, "category", None)
            if app_name and hasattr(app_name, "value"):
                app_name = app_name.value.capitalize()
            else:
                app_name = getattr(notif, "app_name", "System")
            app_lbl = Gtk.Label(label=app_name)
            app_lbl.add_css_class("luminos-notif-item-app")
            app_lbl.set_halign(Gtk.Align.START)
            meta_box.append(app_lbl)

            ts = getattr(notif, "timestamp", 0)
            time_lbl = Gtk.Label(label=format_notification_time(ts))
            time_lbl.add_css_class("luminos-notif-item-time")
            time_lbl.set_halign(Gtk.Align.END)
            time_lbl.set_hexpand(True)
            meta_box.append(time_lbl)
            text_box.append(meta_box)

            # Title
            title_lbl = Gtk.Label(label=getattr(notif, "title", ""))
            title_lbl.add_css_class("luminos-notif-item-title")
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            text_box.append(title_lbl)

            # Body
            body = getattr(notif, "body", "")
            if body:
                body_lbl = Gtk.Label(label=body)
                body_lbl.add_css_class("luminos-notif-item-body")
                body_lbl.set_halign(Gtk.Align.START)
                body_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                body_lbl.set_max_width_chars(40)
                text_box.append(body_lbl)

            row.append(text_box)

            # Close button
            close_btn = Gtk.Button(label="×")
            close_btn.add_css_class("luminos-notif-item-close")
            close_btn.set_valign(Gtk.Align.START)
            nid = getattr(notif, "id", None)
            close_btn.connect("clicked", self._on_dismiss_item, nid)
            row.append(close_btn)

            # Click to mark as read
            click = Gtk.GestureClick()
            click.connect("pressed", self._on_item_click, notif)
            row.add_controller(click)

            return row

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _on_item_click(self, _gesture, _n, _x, _y, notif):
            """Mark notification as read on click."""
            notif.read = True

        def _on_dismiss_item(self, _btn, nid):
            """Dismiss a notification."""
            if self._center and nid:
                self._center.dismiss(nid)
            self._refresh()

        def _on_clear_all(self, *_):
            """Clear all notifications."""
            if self._center:
                self._center.mark_all_read()
            self._refresh()

        # -------------------------------------------------------------------
        # Show / hide
        # -------------------------------------------------------------------

        def show_panel(self):
            """Refresh and present the panel."""
            self._refresh()
            if self._center:
                self._center.mark_all_read()
            self._just_shown = True
            GLib.timeout_add(400, self._clear_just_shown)
            self.present()

        def _clear_just_shown(self):
            self._just_shown = False
            return False

        def toggle(self):
            """Show if hidden, hide if visible."""
            if self.get_visible():
                self.hide()
            else:
                self.show_panel()

        def _on_active_changed(self, window, _param):
            if not window.is_active() and not getattr(self, "_just_shown", False):
                self.hide()

        def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
            from gi.repository import Gdk
            if keyval == Gdk.KEY_Escape:
                self.hide()
                return True
            return False

else:
    class NotificationCenterPanel:  # type: ignore[no-redef]
        """Headless stub."""
        pass
