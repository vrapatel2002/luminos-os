"""
src/gui/launcher/launcher_window.py
LuminosLauncher — Spotlight-style app launcher popup.

Architecture:
- Gtk.Window (not ApplicationWindow) — created once, shown/hidden.
- Layer shell OVERLAY layer with KEYBOARD_MODE_EXCLUSIVE when present.
- Three zones: search bar (top) | results grid (middle) | context bar (bottom).
- Results grid: AppResultItem tiles, keyboard navigable.
- _show_recent(): pinned apps + launch history + alphabetical fallback.
- _launch_app(): classifies via daemon, launches via subprocess, records history.
- Closes on Escape key.
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

from gui.theme import mode, generate_css
from gui.common.socket_client import DaemonClient
from gui.dock.dock_config import load_pinned
from gui.launcher.app_scanner import scan_applications, search_apps, predict_zone
from gui.launcher.launch_history import add_to_history, get_recent


if _GTK_AVAILABLE:
    from gui.launcher.app_result_item import AppResultItem

    _GRID_COLS = 4   # icons per row

    class LuminosLauncher(Gtk.Window):
        """
        Spotlight-style application launcher.

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
            self._items:   list[AppResultItem] = []
            self._sel_idx: int = 0

            self.set_title("luminos-launcher")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(560, 480)
            self.add_css_class("luminos-panel")

            # Theme CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(generate_css(mode.get_mode()))
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

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

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build(self):
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            root.set_margin_top(16)
            root.set_margin_bottom(16)
            root.set_margin_start(16)
            root.set_margin_end(16)
            self.set_child(root)

            # Search bar
            search_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            search_box.add_css_class("luminos-qs-section")
            search_box.set_margin_bottom(12)

            mag = Gtk.Label(label="🔍")
            search_box.append(mag)

            self._search_entry = Gtk.Entry()
            self._search_entry.set_placeholder_text("Search apps, files…")
            self._search_entry.set_hexpand(True)
            self._search_entry.add_css_class("luminos-input")
            self._search_entry.connect("changed", self._on_search_changed)
            search_box.append(self._search_entry)
            root.append(search_box)

            # Results scroll + grid
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_vexpand(True)
            scroll.set_max_content_height(360)
            scroll.set_propagate_natural_height(True)
            root.append(scroll)

            self._grid = Gtk.FlowBox()
            self._grid.set_max_children_per_line(_GRID_COLS)
            self._grid.set_min_children_per_line(2)
            self._grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self._grid.set_homogeneous(True)
            self._grid.set_column_spacing(4)
            self._grid.set_row_spacing(8)
            self._grid.connect("child-activated", self._on_grid_activated)
            scroll.set_child(self._grid)

            # Context bar
            self._ctx_label = Gtk.Label(label="Press Enter to launch")
            self._ctx_label.add_css_class("luminos-qs-dim")
            self._ctx_label.set_halign(Gtk.Align.START)
            self._ctx_label.set_margin_top(8)
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
            lbl = Gtk.Label(label=text)
            lbl.add_css_class("luminos-qs-section-title")
            lbl.set_halign(Gtk.Align.START)
            # Wrap in FlowBoxChild spanning all columns via hexpand
            wrap = Gtk.Box()
            wrap.set_hexpand(True)
            wrap.append(lbl)
            self._grid.insert(wrap, -1)

        def _add_app_tile(self, app: dict):
            zone = predict_zone(app)
            item = AppResultItem(app=app, zone=zone)
            self._grid.insert(item, -1)
            self._items.append(item)

        def _show_recent(self):
            """Populate grid with pinned + recent + first 8 alphabetical."""
            self._clear_grid()

            pinned = load_pinned()
            recent = get_recent(8)
            recent_execs = {r.get("exec", "") for r in recent}
            pinned_execs = {p.get("exec", "") for p in pinned}

            if pinned:
                self._add_section_label("Pinned")
                for app in pinned:
                    self._add_app_tile(app)

            extra_recent = [r for r in recent if r.get("exec") not in pinned_execs]
            if extra_recent:
                self._add_section_label("Recent")
                for app in extra_recent:
                    self._add_app_tile(app)

            shown_execs = pinned_execs | recent_execs
            all_section = [
                a for a in self.all_apps
                if a.get("exec", "") not in shown_execs
            ][:8]
            if all_section:
                self._add_section_label("All Apps")
                for app in all_section:
                    self._add_app_tile(app)

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
                self._show_recent()
            else:
                results = search_apps(query, self.all_apps)
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
            """Refresh app list, reset search, show."""
            self.all_apps = scan_applications()
            self._search_entry.set_text("")
            self._show_recent()
            # Focus the search entry after presenting
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
