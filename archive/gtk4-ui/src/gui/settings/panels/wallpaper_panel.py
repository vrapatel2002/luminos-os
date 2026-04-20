"""
src/gui/settings/panels/wallpaper_panel.py
WallpaperPanel — wallpaper selection grid with Static/Video/Live tabs.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.wallpaper")

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

_STATIC_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_VIDEO_EXTENSIONS = (".mp4", ".webm", ".gif")

_WALLPAPER_DIR = os.path.expanduser("~/.config/luminos/wallpapers")


def _get_wallpaper_files(tab: str) -> list:
    """Return wallpaper file paths for the given tab type."""
    if tab == "static":
        exts = _STATIC_EXTENSIONS
    elif tab == "video":
        exts = _VIDEO_EXTENSIONS
    else:
        return []
    try:
        if not os.path.isdir(_WALLPAPER_DIR):
            return []
        files = []
        for f in sorted(os.listdir(_WALLPAPER_DIR)):
            if any(f.lower().endswith(e) for e in exts):
                files.append(os.path.join(_WALLPAPER_DIR, f))
        return files
    except OSError:
        return []


# ===========================================================================
# CSS
# ===========================================================================

_WALLPAPER_CSS = f"""
.luminos-wp-tab {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
    color: {TEXT_SECONDARY};
    background: transparent;
    border: none;
    border-radius: {RADIUS_FULL}px;
    padding: {SPACE_2}px {SPACE_4}px;
    min-height: 32px;
}}

.luminos-wp-tab:hover {{
    color: {TEXT_PRIMARY};
    background-color: {BG_OVERLAY};
}}

.luminos-wp-tab-active {{
    background-color: {ACCENT} !important;
    color: {TEXT_PRIMARY} !important;
}}

.luminos-wp-cell {{
    border-radius: {RADIUS_MD}px;
    background-color: {BG_ELEVATED};
    min-height: 120px;
}}

.luminos-wp-cell-selected {{
    border: 2px solid {ACCENT};
}}

.luminos-wp-add-cell {{
    border-radius: {RADIUS_MD}px;
    background-color: {BG_ELEVATED};
    border: 1px dashed {BORDER};
    min-height: 120px;
    color: {TEXT_SECONDARY};
    font-size: 24px;
}}

.luminos-wp-intensity {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_PRIMARY};
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class WallpaperPanel(Gtk.Box):
        """Wallpaper selection panel with Static/Video/Live tabs."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            self._current_tab = "static"
            self._selected_wallpaper = None

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_WALLPAPER_CSS)
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
            title = Gtk.Label(label="Wallpaper")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # Tab bar
            tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            tab_box.set_halign(Gtk.Align.START)
            tab_box.set_margin_bottom(SPACE_4)

            seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            seg.add_css_class("luminos-segmented")

            self._tab_btns = {}
            for label in ("Static", "Video", "Live"):
                btn = Gtk.Button(label=label)
                btn.add_css_class("luminos-wp-tab")
                key = label.lower()
                self._tab_btns[key] = btn
                if key == self._current_tab:
                    btn.add_css_class("luminos-wp-tab-active")
                btn.connect("clicked", self._on_tab_click, key)
                seg.append(btn)

            tab_box.append(seg)
            self.append(tab_box)

            # Intensity control (Live tab only)
            self._intensity_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            self._intensity_box.set_margin_bottom(SPACE_4)
            self._intensity_box.set_visible(False)

            int_label = Gtk.Label(label="Intensity")
            int_label.add_css_class("luminos-wp-intensity")
            self._intensity_box.append(int_label)

            int_seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            int_seg.add_css_class("luminos-segmented")
            self._intensity_btns = {}
            for level in ("Low", "Medium", "High"):
                btn = Gtk.Button(label=level)
                btn.add_css_class("luminos-wp-tab")
                key = level.lower()
                self._intensity_btns[key] = btn
                if key == "medium":
                    btn.add_css_class("luminos-wp-tab-active")
                btn.connect("clicked", self._on_intensity_click, key)
                int_seg.append(btn)
            self._intensity_box.append(int_seg)
            self.append(self._intensity_box)

            # Grid container
            self._grid_scroll = Gtk.ScrolledWindow()
            self._grid_scroll.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
            )
            self._grid_scroll.set_vexpand(True)

            self._grid = Gtk.FlowBox()
            self._grid.set_max_children_per_line(3)
            self._grid.set_min_children_per_line(3)
            self._grid.set_column_spacing(SPACE_3)
            self._grid.set_row_spacing(SPACE_3)
            self._grid.set_selection_mode(Gtk.SelectionMode.NONE)
            self._grid.set_homogeneous(True)

            self._grid_scroll.set_child(self._grid)
            self.append(self._grid_scroll)

            self._refresh_grid()

        def _on_tab_click(self, btn, key):
            self._current_tab = key
            for k, b in self._tab_btns.items():
                if k == key:
                    b.add_css_class("luminos-wp-tab-active")
                else:
                    b.remove_css_class("luminos-wp-tab-active")
            self._intensity_box.set_visible(key == "live")
            self._refresh_grid()

        def _on_intensity_click(self, btn, key):
            for k, b in self._intensity_btns.items():
                if k == key:
                    b.add_css_class("luminos-wp-tab-active")
                else:
                    b.remove_css_class("luminos-wp-tab-active")
            logger.debug(f"Live wallpaper intensity: {key}")

        def _refresh_grid(self):
            # Clear grid
            while (child := self._grid.get_first_child()):
                self._grid.remove(child)

            files = _get_wallpaper_files(self._current_tab)
            for path in files:
                cell = self._make_cell(path)
                self._grid.append(cell)

            # Add "+" cell
            add_cell = Gtk.Button(label="+")
            add_cell.add_css_class("luminos-wp-add-cell")
            add_cell.set_hexpand(True)
            add_cell.connect("clicked", self._on_add_wallpaper)
            self._grid.append(add_cell)

        def _make_cell(self, path: str) -> Gtk.Button:
            cell = Gtk.Button()
            cell.add_css_class("luminos-wp-cell")
            cell.set_hexpand(True)

            # Show filename as label (thumbnails need GdkPixbuf which may not be available)
            name = os.path.basename(path)
            lbl = Gtk.Label(label=name)
            lbl.set_ellipsize(Pango.EllipsizeMode.END) if hasattr(Gtk, 'Label') else None
            lbl.add_css_class("luminos-text-secondary")
            cell.set_child(lbl)

            if path == self._selected_wallpaper:
                cell.add_css_class("luminos-wp-cell-selected")

            cell.connect("clicked", self._on_cell_click, path)
            return cell

        def _on_cell_click(self, btn, path):
            self._selected_wallpaper = path
            self._refresh_grid()
            # Apply wallpaper immediately
            try:
                from gui.wallpaper import set_wallpaper
                set_wallpaper(path)
            except Exception as e:
                logger.debug(f"Wallpaper apply error: {e}")

        def _on_add_wallpaper(self, _btn):
            dialog = Gtk.FileChooserDialog(
                title="Choose Wallpaper",
                action=Gtk.FileChooserAction.OPEN,
                transient_for=self.get_root(),
            )
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Open", Gtk.ResponseType.ACCEPT)

            ff = Gtk.FileFilter()
            if self._current_tab == "static":
                ff.set_name("Images")
                for ext in _STATIC_EXTENSIONS:
                    ff.add_pattern(f"*{ext}")
            elif self._current_tab == "video":
                ff.set_name("Videos")
                for ext in _VIDEO_EXTENSIONS:
                    ff.add_pattern(f"*{ext}")
            dialog.add_filter(ff)
            dialog.connect("response", self._on_file_response)
            dialog.present()

        def _on_file_response(self, dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                file = dialog.get_file()
                if file:
                    path = file.get_path()
                    self._selected_wallpaper = path
                    try:
                        from gui.wallpaper import set_wallpaper
                        set_wallpaper(path)
                    except Exception as e:
                        logger.debug(f"Wallpaper apply error: {e}")
            dialog.close()

else:
    class WallpaperPanel:  # type: ignore[no-redef]
        pass
