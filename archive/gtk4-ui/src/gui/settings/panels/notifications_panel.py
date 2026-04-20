"""
src/gui/settings/panels/notifications_panel.py
NotificationsPanel — Do Not Disturb, per-app toggles, preview style.

Pure helpers:
    _get_notification_apps()    → list[dict]
    _get_preview_options()      → list[str]
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.notifications")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER, BORDER_SUBTLE,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_FULL,
    SETTINGS_PADDING,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_notification_apps() -> list:
    """
    Return apps that can send notifications.

    Returns:
        List of dicts with keys: name, icon, enabled.
    """
    # In a real implementation, query the notification daemon.
    # For now, return common apps.
    return [
        {"name": "Firefox", "icon": "firefox", "enabled": True},
        {"name": "Foot Terminal", "icon": "utilities-terminal", "enabled": True},
        {"name": "Files", "icon": "system-file-manager", "enabled": True},
        {"name": "Steam", "icon": "steam", "enabled": True},
        {"name": "Discord", "icon": "discord", "enabled": True},
    ]


def _get_preview_options() -> list:
    """Return notification preview options."""
    return ["Always", "When unlocked", "Never"]


# ===========================================================================
# CSS
# ===========================================================================

_NOTIF_CSS = f"""
.luminos-dnd-row {{
    min-height: 64px;
    padding: {SPACE_4}px;
    border-radius: {RADIUS_MD}px;
    background-color: {BG_ELEVATED};
    margin-bottom: {SPACE_6}px;
}}

.luminos-dnd-label {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 16px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
}}

.luminos-dnd-sublabel {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

.luminos-app-notif-row {{
    min-height: 44px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-app-notif-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-dimmed {{
    opacity: 0.5;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class NotificationsPanel(Gtk.Box):
        """Notifications settings: DND toggle, per-app toggles, preview style."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            self._dnd_active = False

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_NOTIF_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

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
            # Panel title
            title = Gtk.Label(label="Notifications")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Do Not Disturb ----
            dnd_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            dnd_row.add_css_class("luminos-dnd-row")
            dnd_row.set_hexpand(True)

            dnd_text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            dnd_text.set_hexpand(True)
            dnd_text.set_valign(Gtk.Align.CENTER)

            dnd_label = Gtk.Label(label="Do Not Disturb")
            dnd_label.add_css_class("luminos-dnd-label")
            dnd_label.set_halign(Gtk.Align.START)
            dnd_text.append(dnd_label)

            dnd_sub = Gtk.Label(label="Silence all notifications")
            dnd_sub.add_css_class("luminos-dnd-sublabel")
            dnd_sub.set_halign(Gtk.Align.START)
            dnd_text.append(dnd_sub)

            dnd_row.append(dnd_text)

            self._dnd_switch = Gtk.Switch()
            self._dnd_switch.set_active(False)
            self._dnd_switch.add_css_class("luminos-switch")
            self._dnd_switch.set_valign(Gtk.Align.CENTER)
            self._dnd_switch.connect("state-set", self._on_dnd_toggle)
            dnd_row.append(self._dnd_switch)

            self.append(dnd_row)

            # ---- Container for rest of panel (dims when DND on) ----
            self._rest_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )

            # ---- Per-app notifications ----
            apps_title = Gtk.Label(label="Applications")
            apps_title.add_css_class("luminos-section-title")
            apps_title.set_halign(Gtk.Align.START)
            self._rest_box.append(apps_title)

            self._apps_list = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            self._apps_list.set_margin_bottom(SPACE_6)
            self._rest_box.append(self._apps_list)

            for app in _get_notification_apps():
                row = self._make_app_row(app)
                self._apps_list.append(row)

            div = Gtk.Box()
            div.add_css_class("luminos-section-divider")
            self._rest_box.append(div)

            # ---- Notification style ----
            style_title = Gtk.Label(label="Show previews")
            style_title.add_css_class("luminos-section-title")
            style_title.set_halign(Gtk.Align.START)
            self._rest_box.append(style_title)

            seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            seg.add_css_class("luminos-segmented")
            seg.set_halign(Gtk.Align.START)
            seg.set_margin_top(SPACE_2)

            self._preview_btns = {}
            for option in _get_preview_options():
                btn = Gtk.Button(label=option)
                key = option.lower().replace(" ", "_")
                self._preview_btns[key] = btn
                if option == "Always":
                    btn.add_css_class("luminos-segmented-active")
                btn.connect("clicked", self._on_preview_click, key)
                seg.append(btn)

            self._rest_box.append(seg)
            self.append(self._rest_box)

        def _make_app_row(self, app: dict) -> Gtk.Box:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            row.add_css_class("luminos-app-notif-row")
            row.set_hexpand(True)

            icon = Gtk.Image.new_from_icon_name(app.get("icon", "application-x-executable"))
            icon.set_pixel_size(24)
            row.append(icon)

            name_lbl = Gtk.Label(label=app["name"])
            name_lbl.add_css_class("luminos-setting-label")
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_hexpand(True)
            row.append(name_lbl)

            switch = Gtk.Switch()
            switch.set_active(app.get("enabled", True))
            switch.add_css_class("luminos-switch")
            switch.set_valign(Gtk.Align.CENTER)
            row.append(switch)

            return row

        def _on_dnd_toggle(self, switch, state):
            self._dnd_active = state
            if state:
                self._rest_box.add_css_class("luminos-dimmed")
            else:
                self._rest_box.remove_css_class("luminos-dimmed")
            return False

        def _on_preview_click(self, btn, key):
            for k, b in self._preview_btns.items():
                if k == key:
                    b.add_css_class("luminos-segmented-active")
                else:
                    b.remove_css_class("luminos-segmented-active")

else:
    class NotificationsPanel:  # type: ignore[no-redef]
        pass
