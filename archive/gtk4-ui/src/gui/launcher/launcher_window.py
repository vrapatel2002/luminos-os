"""
src/gui/launcher/launcher_window.py
LuminosLauncher — full-screen frosted-glass app launcher.

Visual spec (Phase 5.8):
  Full-screen overlay OR centered 640×600 panel
  Background: glass_bg(0.85) with blur(20px)
  Border: 1px BORDER, RADIUS_LG corners
  Sections: Recents (8) | All Apps | Windows Apps | Games
  Search bar: type instantly filters
  Keyboard: arrows + Enter to launch, Escape to close

Architecture:
- Gtk.Window — created once, shown/hidden via toggle().
- Layer shell OVERLAY + KEYBOARD_MODE_EXCLUSIVE.
- AppResultItem tiles in 5-column FlowBox grid.
- _show_sections(): Recents / All Apps / Windows Apps / Games.
- _launch_app(): classifies via daemon, launches subprocess, records history.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.launcher.window")

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
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE, ACCENT_GLOW,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_FOCUS, BORDER_SUBTLE,
    FONT_FAMILY, FONT_H3, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_LG,
    SHADOW_PANEL,
    glass_bg,
)
from gui.common.socket_client import DaemonClient
from gui.dock.dock_config import load_pinned
from gui.launcher.app_scanner import (
    scan_applications, search_apps, predict_zone,
    scan_windows_apps, scan_games,
)
from gui.launcher.launch_history import add_to_history, get_recent


# ===========================================================================
# CSS — all values from luminos_theme
# ===========================================================================

_LAUNCHER_CSS = f"""
.luminos-launcher {{
    background: {glass_bg(0.85)};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_LG}px;
    box-shadow: {SHADOW_PANEL};
}}

.luminos-launcher-search {{
    background: {BG_OVERLAY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: {RADIUS_MD}px;
    padding: {SPACE_3}px {SPACE_4}px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_PRIMARY};
    caret-color: {ACCENT};
}}

.luminos-launcher-search:focus {{
    border-color: {BORDER_FOCUS};
    box-shadow: 0 0 0 2px {ACCENT_SUBTLE};
}}

.luminos-launcher-section-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    font-weight: 600;
    color: {TEXT_DISABLED};
    letter-spacing: 0.5px;
    padding: {SPACE_2}px 0;
}}

.luminos-launcher-item {{
    padding: {SPACE_2}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-launcher-item:hover,
.luminos-launcher-item.selected {{
    background: {BG_OVERLAY};
}}

.luminos-launcher-item-name {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_PRIMARY};
}}

.luminos-launcher-item-hint {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_DISABLED};
}}

.luminos-launcher-zone-badge {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 9px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    background: {ACCENT};
    border-radius: 9999px;
    min-width: 14px;
    min-height: 14px;
    padding: 0 2px;
}}

.luminos-launcher-zone-badge-warn {{
    background: rgba(255, 68, 85, 0.8);
}}

.luminos-launcher-context {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
}}

.luminos-launcher-empty {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_DISABLED};
}}
"""

_PANEL_WIDTH = 640
_PANEL_HEIGHT = 600


if _GTK_AVAILABLE:
    from gui.launcher.app_result_item import AppResultItem

    _GRID_COLS = 5   # icons per row

    class LuminosLauncher(Gtk.Window):
        """
        Full-screen frosted-glass application launcher.

        Keyboard:
            Type          → search
            Escape        → close
            Enter         → launch selected
            Arrow keys    → navigate grid
        """

        def __init__(self, daemon_client: "DaemonClient | None" = None):
            super().__init__()
            self._client  = daemon_client or DaemonClient()
            self.all_apps: list[dict] = []
            self._windows_apps: list[dict] = []
            self._games: list[dict] = []
            self._items:   list[AppResultItem] = []
            self._sel_idx: int = 0

            self.set_title("luminos-launcher")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(_PANEL_WIDTH, _PANEL_HEIGHT)
            self.add_css_class("luminos-launcher")

            # Theme CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_LAUNCHER_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            # Layer-shell: floating overlay, exclusive keyboard
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.EXCLUSIVE
                )
                logger.info("Launcher: layer-shell OVERLAY + keyboard exclusive")
            else:
                logger.warning("Launcher: layer-shell unavailable, using normal window")

            # Close on focus-out when not using layer-shell exclusive
            self.connect("notify::is-active", self._on_active_changed)

            self._build()

            # Keyboard controller
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key_pressed)
            self.add_controller(key_ctrl)

        def _ensure_css(self):
            try:
                Gtk.StyleContext.add_provider_for_display(
                    self.get_display(), self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception:
                pass

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build(self):
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            root.set_margin_top(SPACE_6)
            root.set_margin_bottom(SPACE_4)
            root.set_margin_start(SPACE_6)
            root.set_margin_end(SPACE_6)
            self.set_child(root)

            # Search bar
            self._search_entry = Gtk.Entry()
            self._search_entry.set_placeholder_text("Search apps…")
            self._search_entry.set_hexpand(True)
            self._search_entry.add_css_class("luminos-launcher-search")
            self._search_entry.connect("changed", self._on_search_changed)
            self._search_entry.set_margin_bottom(SPACE_4)
            root.append(self._search_entry)

            # Results scroll + grid
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)
            scroll.set_max_content_height(480)
            scroll.set_propagate_natural_height(True)
            root.append(scroll)

            self._grid = Gtk.FlowBox()
            self._grid.set_max_children_per_line(_GRID_COLS)
            self._grid.set_min_children_per_line(2)
            self._grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self._grid.set_homogeneous(True)
            self._grid.set_column_spacing(SPACE_2)
            self._grid.set_row_spacing(SPACE_3)
            self._grid.connect("child-activated", self._on_grid_activated)
            scroll.set_child(self._grid)

            # Context bar
            self._ctx_label = Gtk.Label(label="Press Enter to launch")
            self._ctx_label.add_css_class("luminos-launcher-context")
            self._ctx_label.set_halign(Gtk.Align.START)
            self._ctx_label.set_margin_top(SPACE_3)
            root.append(self._ctx_label)

        # -------------------------------------------------------------------
        # Content population
        # -------------------------------------------------------------------

        def _clear_grid(self):
            child = self._grid.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                self._grid.remove(child)
                child = nxt
            self._items = []
            self._sel_idx = 0

        def _add_section_label(self, text: str):
            lbl = Gtk.Label(label=text.upper())
            lbl.add_css_class("luminos-launcher-section-title")
            lbl.set_halign(Gtk.Align.START)
            wrap = Gtk.Box()
            wrap.set_hexpand(True)
            wrap.append(lbl)
            self._grid.insert(wrap, -1)

        def _add_app_tile(self, app: dict):
            zone = predict_zone(app)
            item = AppResultItem(app=app, zone=zone)
            self._grid.insert(item, -1)
            self._items.append(item)

        def _show_sections(self):
            """Populate grid: Recents (8) / All Apps / Windows Apps / Games."""
            self._clear_grid()

            # --- Recents (last 8 launched) ---
            recent = get_recent(8)
            recent_execs = {r.get("exec", "") for r in recent}
            if recent:
                self._add_section_label("Recents")
                for app in recent:
                    self._add_app_tile(app)

            # --- All Apps (native, excluding recents) ---
            all_section = [
                a for a in self.all_apps
                if a.get("exec", "") not in recent_execs
            ]
            if all_section:
                self._add_section_label("All Apps")
                for app in all_section:
                    self._add_app_tile(app)

            # --- Windows Apps (from router cache) ---
            if self._windows_apps:
                self._add_section_label("Windows Apps")
                for app in self._windows_apps:
                    self._add_app_tile(app)

            # --- Games (filtered by category) ---
            if self._games:
                self._add_section_label("Games")
                for app in self._games:
                    self._add_app_tile(app)

            if not recent and not all_section and not self._windows_apps and not self._games:
                lbl = Gtk.Label(label="No applications found")
                lbl.add_css_class("luminos-launcher-empty")
                lbl.set_valign(Gtk.Align.CENTER)
                lbl.set_vexpand(True)
                self._grid.insert(lbl, -1)

            self._update_context()

        def _show_results(self, results: list):
            """Populate grid with search results, select first."""
            self._clear_grid()
            for app in results:
                self._add_app_tile(app)
            if self._items:
                self._items[0].set_selected(True)
            self._update_context()

        def _update_context(self):
            """Update the context bar for the currently selected item."""
            if not self._items or self._sel_idx >= len(self._items):
                self._ctx_label.set_text("Press Enter to launch")
                return
            app  = self._items[self._sel_idx].app
            zone = self._items[self._sel_idx].zone
            name = app.get("name", "")
            if zone == 1:
                self._ctx_label.set_text(
                    f"Enter to launch · {name} · Zone 1 Native"
                )
            elif zone == 2:
                self._ctx_label.set_text(
                    f"Enter to launch · {name} · Zone 2 — Will run via Wine/Proton"
                )
            else:
                self._ctx_label.set_text(
                    f"Enter to launch · {name} · Zone 3 — Will run in quarantine ⚠"
                )

        # -------------------------------------------------------------------
        # Search
        # -------------------------------------------------------------------

        def _on_search_changed(self, entry):
            query = entry.get_text().strip()
            if not query:
                self._show_sections()
            else:
                # Search across all app pools
                all_pools = self.all_apps + self._windows_apps + self._games
                # Deduplicate by exec
                seen = set()
                unique = []
                for a in all_pools:
                    key = a.get("exec", "")
                    if key not in seen:
                        seen.add(key)
                        unique.append(a)
                results = search_apps(query, unique)
                self._show_results(results)

        # -------------------------------------------------------------------
        # Keyboard navigation
        # -------------------------------------------------------------------

        def _on_key_pressed(self, ctrl, keyval, keycode, state) -> bool:
            if keyval == Gdk.KEY_Escape:
                self.hide()
                return True

            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                if self._items and self._sel_idx < len(self._items):
                    self._launch_app(self._items[self._sel_idx].app)
                return True

            n = len(self._items)
            if n == 0:
                return False

            if keyval == Gdk.KEY_Down:
                new_idx = min(self._sel_idx + _GRID_COLS, n - 1)
            elif keyval == Gdk.KEY_Up:
                new_idx = max(self._sel_idx - _GRID_COLS, 0)
            elif keyval == Gdk.KEY_Right:
                new_idx = min(self._sel_idx + 1, n - 1)
            elif keyval == Gdk.KEY_Left:
                new_idx = max(self._sel_idx - 1, 0)
            else:
                return False

            self._items[self._sel_idx].set_selected(False)
            self._sel_idx = new_idx
            self._items[self._sel_idx].set_selected(True)
            self._update_context()
            return True

        # -------------------------------------------------------------------
        # Grid click
        # -------------------------------------------------------------------

        def _on_grid_activated(self, flowbox, child):
            # FlowBox wraps our AppResultItem in a FlowBoxChild
            item_widget = child.get_child()
            if isinstance(item_widget, AppResultItem):
                self._launch_app(item_widget.app)

        def _on_item_activated(self, item: AppResultItem):
            self._launch_app(item.app)

        # -------------------------------------------------------------------
        # Launch
        # -------------------------------------------------------------------

        def _launch_app(self, app: dict):
            """Record history, classify, launch, register, hide."""
            add_to_history(app)

            exec_cmd = app.get("exec", "")
            if not exec_cmd:
                logger.warning("launch_app: empty exec field")
                self.hide()
                return

            # Strip .desktop %X substitution tokens
            import re
            exec_clean = re.sub(r"%[A-Za-z]", "", exec_cmd).strip()

            # Send classify to daemon (best-effort, don't block on result)
            binary = exec_clean.split()[0] if exec_clean else ""
            if binary:
                try:
                    self._client.send({"type": "classify", "binary": binary})
                except Exception as e:
                    logger.debug(f"classify send failed: {e}")

            # Launch process
            try:
                proc = subprocess.Popen(
                    exec_clean,
                    shell=True,
                    env=os.environ.copy(),
                    start_new_session=True,
                )
                logger.info(f"Launched: {exec_clean!r} pid={proc.pid}")

                # Register window with compositor (best-effort)
                try:
                    self._client.send({
                        "type": "window_register",
                        "pid":  proc.pid,
                        "exe":  binary,
                        "zone": predict_zone(app),
                    })
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Failed to launch {exec_clean!r}: {e}")

            self.hide()

        # -------------------------------------------------------------------
        # Show / hide
        # -------------------------------------------------------------------

        def show_launcher(self):
            """Refresh all app lists, reset search, show."""
            self.all_apps = scan_applications()
            self._windows_apps = scan_windows_apps()
            self._games = scan_games(self.all_apps)
            self._search_entry.set_text("")
            self._show_sections()
            self.present()
            GLib.idle_add(self._search_entry.grab_focus)

        def toggle(self):
            if self.get_visible():
                self.hide()
            else:
                self.show_launcher()

        def _on_active_changed(self, window, _param):
            """Hide on focus loss (when not using layer-shell exclusive mode)."""
            if _LAYER_SHELL_AVAILABLE:
                return   # layer-shell keyboard-exclusive handles this
            if not window.is_active():
                self.hide()
