"""
src/gui/settings/settings_window.py
LuminosSettings — full settings window with sidebar navigation.

Visual spec (LUMINOS_DESIGN_SYSTEM.md):
  Window: 900x600 min, BG_SURFACE
  Sidebar: SIDEBAR_WIDTH (220px), BG_BASE, BORDER right
  Sidebar items: 44px height, RADIUS_MD, ACCENT_SUBTLE active
  Panel area: SETTINGS_PADDING (24px), panel title FONT_H2

Pure: CATEGORIES list, _match_category() for sidebar search.
GTK guard: headless-safe via _GTK_AVAILABLE flag.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.window")

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

from gui.theme.luminos_theme import (
    BG_BASE, BG_SURFACE, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    FONT_FAMILY, FONT_H2, FONT_BODY, FONT_LABEL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6,
    RADIUS_MD,
    SIDEBAR_WIDTH, SETTINGS_PADDING,
    ANIM_DEFAULT, ANIM_SLOW,
)


# ===========================================================================
# Public constants — testable without GTK
# ===========================================================================

CATEGORIES: list[dict] = [
    # --- General ---
    {"id": "appearance",    "label": "Appearance",    "icon": "preferences-desktop-theme",          "group": "General"},
    {"id": "wallpaper",     "label": "Wallpaper",     "icon": "preferences-desktop-wallpaper",      "group": "General"},
    {"id": "sound",         "label": "Sound",         "icon": "audio-card",                         "group": "General"},
    {"id": "network",       "label": "Network",       "icon": "network-wireless",                   "group": "General"},
    {"id": "notifications", "label": "Notifications", "icon": "preferences-system-notifications",   "group": "General"},
    # --- Hardware ---
    {"id": "keyboard",      "label": "Keyboard",      "icon": "input-keyboard",                     "group": "Hardware"},
    {"id": "display",       "label": "Display",       "icon": "video-display",                      "group": "Hardware"},
    # --- System ---
    {"id": "power",         "label": "Power",         "icon": "battery",                            "group": "System"},
    {"id": "privacy",       "label": "Privacy",       "icon": "security-high",                      "group": "System"},
    {"id": "zones",         "label": "Zones",         "icon": "applications-system",                "group": "System"},
    {"id": "ai",            "label": "AI & HIVE",     "icon": "cpu",                                "group": "System"},
    {"id": "about",         "label": "About Luminos", "icon": "help-about",                         "group": "System"},
]

CATEGORY_IDS = [c["id"] for c in CATEGORIES]


def _match_category(query: str, category: dict) -> bool:
    """
    Return True if the query matches the category label (case-insensitive).

    Args:
        query: Search string from sidebar entry.
        category: Dict with at least a "label" key.

    Returns:
        True if query is a substring of the label.
    """
    return query.lower() in category["label"].lower()


# ===========================================================================
# CSS — all values from luminos_theme
# ===========================================================================

_SETTINGS_CSS = f"""
.luminos-settings {{
    background-color: {BG_SURFACE};
}}

.luminos-settings-sidebar {{
    background-color: {BG_BASE};
    border-right: 1px solid {BORDER};
    padding-top: {SPACE_3}px;
    padding-left: {SPACE_2}px;
    padding-right: {SPACE_2}px;
}}

.luminos-settings-search {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    min-height: 36px;
    border-radius: {RADIUS_MD}px;
    background-color: {BG_OVERLAY};
    border: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
    margin: {SPACE_2}px {SPACE_2}px {SPACE_3}px {SPACE_2}px;
    padding: 0 {SPACE_3}px;
}}

.luminos-settings-search:focus {{
    border-color: rgba(0, 128, 255, 0.6);
}}

.luminos-settings-group-label {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_LABEL}px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: {TEXT_DISABLED};
    padding-left: {SPACE_3}px;
    margin-top: {SPACE_4}px;
    margin-bottom: {SPACE_2}px;
}}

.luminos-settings-list {{
    background: transparent;
}}

.luminos-settings-list row {{
    min-height: 44px;
    padding: 0 {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
    color: {TEXT_SECONDARY};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
}}

.luminos-settings-list row:hover {{
    background-color: {BG_OVERLAY};
    color: {TEXT_PRIMARY};
}}

.luminos-settings-list row:selected {{
    background-color: {ACCENT_SUBTLE};
    color: {TEXT_PRIMARY};
    border-left: 2px solid {ACCENT};
}}

.luminos-settings-list row image {{
    color: inherit;
}}

.luminos-panel-area {{
    background-color: {BG_SURFACE};
    padding: {SETTINGS_PADDING}px;
}}

.luminos-panel-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_H2}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    margin-bottom: {SPACE_6}px;
}}

.luminos-section-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 18px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
    margin-bottom: {SPACE_4}px;
}}

.luminos-section-divider {{
    background-color: {BORDER_SUBTLE};
    min-height: 1px;
    margin-top: 32px;
    margin-bottom: 32px;
}}

.luminos-setting-row {{
    min-height: 52px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-setting-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-setting-label {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_PRIMARY};
}}

.luminos-setting-sublabel {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

.luminos-text-secondary {{
    color: {TEXT_SECONDARY};
    font-family: "{FONT_FAMILY}", sans-serif;
}}

.luminos-text-disabled {{
    color: {TEXT_DISABLED};
    font-family: "{FONT_FAMILY}", sans-serif;
}}

.luminos-text-primary {{
    color: {TEXT_PRIMARY};
    font-family: "{FONT_FAMILY}", sans-serif;
}}
"""


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.settings.panels.appearance_panel   import AppearancePanel
    from gui.settings.panels.display_panel      import DisplayPanel
    from gui.settings.panels.power_panel        import PowerPanel
    from gui.settings.panels.zones_panel        import ZonesPanel
    from gui.settings.panels.ai_panel           import AIPanel
    from gui.settings.panels.about_panel        import AboutPanel
    from gui.settings.panels.wallpaper_panel    import WallpaperPanel
    from gui.settings.panels.sound_panel        import SoundPanel
    from gui.settings.panels.network_panel      import NetworkPanel
    from gui.settings.panels.notifications_panel import NotificationsPanel
    from gui.settings.panels.privacy_panel      import PrivacyPanel
    from gui.settings.panels.keyboard_panel     import KeyboardPanel

    _WIN_W = 900
    _WIN_H = 600

    class LuminosSettings(Gtk.ApplicationWindow):
        """
        Full Luminos Settings window.
        One instance per process. Categories shown via sidebar click.
        """

        def __init__(self, application: Gtk.Application):
            super().__init__(application=application)
            self.set_title("Luminos Settings")
            self.set_default_size(_WIN_W, _WIN_H)
            self.set_resizable(True)

            # Apply CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_SETTINGS_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self.add_css_class("luminos-settings")
            self._build()
            self._show_category("appearance")

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build(self):
            root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            self.set_child(root)

            # ---- Sidebar ----
            sidebar = self._build_sidebar()
            root.append(sidebar)

            # ---- Content stack ----
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(
                Gtk.StackTransitionType.CROSSFADE
            )
            self._stack.set_transition_duration(ANIM_DEFAULT)
            self._stack.set_hexpand(True)
            self._stack.set_vexpand(True)
            root.append(self._stack)

            # Add panels
            self._panels = {
                "appearance":    AppearancePanel(),
                "wallpaper":     WallpaperPanel(),
                "sound":         SoundPanel(),
                "network":       NetworkPanel(),
                "notifications": NotificationsPanel(),
                "keyboard":      KeyboardPanel(),
                "display":       DisplayPanel(),
                "power":         PowerPanel(),
                "privacy":       PrivacyPanel(),
                "zones":         ZonesPanel(),
                "ai":            AIPanel(),
                "about":         AboutPanel(),
            }

            for cat_id, panel in self._panels.items():
                scroll = Gtk.ScrolledWindow()
                scroll.set_policy(
                    Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
                )
                scroll.set_child(panel)
                self._stack.add_named(scroll, cat_id)

        def _build_sidebar(self) -> Gtk.Box:
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            sidebar.set_size_request(SIDEBAR_WIDTH, -1)
            sidebar.add_css_class("luminos-settings-sidebar")

            # Search
            self._search_entry = Gtk.SearchEntry()
            self._search_entry.set_placeholder_text("Search Settings...")
            self._search_entry.add_css_class("luminos-settings-search")
            self._search_entry.connect("search-changed", self._on_search_changed)
            sidebar.append(self._search_entry)

            # Scrollable category list
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)

            list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

            # Build sidebar with group labels
            self._list_box = Gtk.ListBox()
            self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self._list_box.add_css_class("luminos-settings-list")
            self._list_box.connect("row-activated", self._on_row_activated)

            self._rows: dict[str, Gtk.ListBoxRow] = {}
            current_group = None
            for cat in CATEGORIES:
                group = cat.get("group", "")
                if group != current_group:
                    current_group = group
                    group_lbl = Gtk.Label(label=group.upper())
                    group_lbl.add_css_class("luminos-settings-group-label")
                    group_lbl.set_halign(Gtk.Align.START)
                    list_container.append(group_lbl)

                    # Insert a new listbox per group for visual separation
                    if self._list_box.get_first_child() is not None:
                        list_container.append(self._list_box)
                        self._list_box = Gtk.ListBox()
                        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
                        self._list_box.add_css_class("luminos-settings-list")
                        self._list_box.connect("row-activated", self._on_row_activated)

                row = self._make_row(cat)
                self._list_box.append(row)
                self._rows[cat["id"]] = row

            list_container.append(self._list_box)
            scroll.set_child(list_container)
            sidebar.append(scroll)

            return sidebar

        def _make_row(self, cat: dict) -> Gtk.ListBoxRow:
            row = Gtk.ListBoxRow()
            row._cat_id = cat["id"]

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2)
            box.set_margin_top(0)
            box.set_margin_bottom(0)
            box.set_margin_start(SPACE_3)
            box.set_margin_end(SPACE_2)
            box.set_valign(Gtk.Align.CENTER)

            # Icon
            icon = Gtk.Image.new_from_icon_name(cat["icon"])
            icon.set_pixel_size(18)
            box.append(icon)

            # Label
            lbl = Gtk.Label(label=cat["label"])
            lbl.set_halign(Gtk.Align.START)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(lbl)

            row.set_child(box)
            return row

        # -------------------------------------------------------------------
        # Navigation
        # -------------------------------------------------------------------

        def _show_category(self, cat_id: str):
            if cat_id not in CATEGORY_IDS:
                return
            self._stack.set_visible_child_name(cat_id)
            if cat_id in self._rows:
                row = self._rows[cat_id]
                parent_list = row.get_parent()
                if isinstance(parent_list, Gtk.ListBox):
                    parent_list.select_row(row)

        def _on_row_activated(self, _list_box, row):
            cat_id = getattr(row, "_cat_id", None)
            if cat_id:
                self._show_category(cat_id)

        # -------------------------------------------------------------------
        # Search
        # -------------------------------------------------------------------

        def _on_search_changed(self, entry):
            query = entry.get_text().strip()
            for cat in CATEGORIES:
                row = self._rows.get(cat["id"])
                if row:
                    row.set_visible(not query or _match_category(query, cat))
