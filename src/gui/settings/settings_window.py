"""
src/gui/settings/settings_window.py
LuminosSettings — macOS System Settings style main window.

Architecture:
- 860×580 window — 220px sidebar + 640px content area.
- Sidebar: search entry + category list with icons.
- Content: Gtk.Stack with slide transitions; one child per category.
- Pure: CATEGORIES list, _match_category() for sidebar search.
- GTK guard: headless-safe via _GTK_AVAILABLE flag.
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

from gui.theme import mode, generate_css


# ===========================================================================
# Public constants — testable without GTK
# ===========================================================================

CATEGORIES: list[dict] = [
    {"id": "appearance",   "label": "Appearance",     "icon": "preferences-desktop-theme"},
    {"id": "wallpaper",    "label": "Wallpaper",       "icon": "preferences-desktop-wallpaper"},
    {"id": "display",      "label": "Display",         "icon": "video-display"},
    {"id": "power",        "label": "Power",           "icon": "battery"},
    {"id": "zones",        "label": "Zones",           "icon": "applications-system"},
    {"id": "ai",           "label": "AI & HIVE",       "icon": "cpu"},
    {"id": "notifications","label": "Notifications",   "icon": "preferences-system-notifications"},
    {"id": "privacy",      "label": "Privacy",         "icon": "security-high"},
    {"id": "sound",        "label": "Sound",           "icon": "audio-card"},
    {"id": "network",      "label": "Network",         "icon": "network-wireless"},
    {"id": "about",        "label": "About Luminos",   "icon": "help-about"},
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
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.settings.panels.appearance_panel   import AppearancePanel
    from gui.settings.panels.display_panel      import DisplayPanel
    from gui.settings.panels.power_panel        import PowerPanel
    from gui.settings.panels.zones_panel        import ZonesPanel
    from gui.settings.panels.ai_panel           import AIPanel
    from gui.settings.panels.about_panel        import AboutPanel

    _WIN_W = 860
    _WIN_H = 580
    _SIDEBAR_W = 220

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
            self.add_css_class("luminos-settings")

            # Theme CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(generate_css(mode.get_mode()))
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

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

            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            root.append(sep)

            # ---- Content stack ----
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(
                Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
            )
            self._stack.set_transition_duration(180)
            self._stack.set_hexpand(True)
            self._stack.set_vexpand(True)
            root.append(self._stack)

            # Add panels
            self._panels = {
                "appearance":    AppearancePanel(),
                "display":       DisplayPanel(),
                "power":         PowerPanel(),
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

            # Placeholder panels for categories without full implementations
            _stub_ids = [
                "wallpaper", "notifications", "privacy", "sound", "network"
            ]
            for cat_id in _stub_ids:
                label = Gtk.Label(
                    label=f"{cat_id.capitalize()} settings coming soon."
                )
                label.set_halign(Gtk.Align.CENTER)
                label.set_valign(Gtk.Align.CENTER)
                self._stack.add_named(label, cat_id)

        def _build_sidebar(self) -> Gtk.Box:
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            sidebar.set_size_request(_SIDEBAR_W, -1)
            sidebar.add_css_class("luminos-settings-sidebar")

            # Search
            self._search_entry = Gtk.SearchEntry()
            self._search_entry.set_placeholder_text("Search Settings…")
            self._search_entry.set_margin_top(12)
            self._search_entry.set_margin_bottom(8)
            self._search_entry.set_margin_start(10)
            self._search_entry.set_margin_end(10)
            self._search_entry.connect("search-changed", self._on_search_changed)
            sidebar.append(self._search_entry)

            sidebar.append(Gtk.Separator())

            # Category list
            self._list_box = Gtk.ListBox()
            self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self._list_box.add_css_class("luminos-settings-list")
            self._list_box.connect("row-activated", self._on_row_activated)
            sidebar.append(self._list_box)

            self._rows: dict[str, Gtk.ListBoxRow] = {}
            for cat in CATEGORIES:
                row = self._make_row(cat)
                self._list_box.append(row)
                self._rows[cat["id"]] = row

            return sidebar

        def _make_row(self, cat: dict) -> Gtk.ListBoxRow:
            row = Gtk.ListBoxRow()
            row._cat_id = cat["id"]

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(8)

            # Icon
            icon = Gtk.Image.new_from_icon_name(cat["icon"])
            icon.set_pixel_size(20)
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
                self._list_box.select_row(self._rows[cat_id])

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
