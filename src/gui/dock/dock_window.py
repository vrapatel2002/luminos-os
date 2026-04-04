"""
src/gui/dock/dock_window.py
LuminosDock — macOS-style frosted glass pill dock for the Luminos desktop.

Architecture:
- Pinned to the bottom edge via gtk4-layer-shell (fallback: 700×72 window).
- Three sections inside a rounded pill container:
    LEFT   — pinned apps (static, from dock.json / DEFAULT_PINNED)
    CENTER — open apps that are NOT already in the pinned list
    RIGHT  — Settings + Trash utility icons
- Polls daemon every 3 s via window_list request to track open windows.
- Zone badges (W / ⚠) appear on Wine and Quarantine apps.
- All daemon calls graceful — no crash when daemon is offline.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.dock.window")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
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
from gui.dock.dock_item import _get_tooltip, _should_show_badge

# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def get_open_apps_not_pinned(open_apps: list, pinned_apps: list) -> list:
    """
    Filter open_apps to exclude any already represented in pinned_apps.

    Comparison key: "exec" field.

    Args:
        open_apps:   List of window_info dicts from daemon window_list.
        pinned_apps: List of pinned app dicts (from dock_config).

    Returns:
        Subset of open_apps whose exec is not in pinned_apps.
    """
    pinned_execs = {a.get("exec", "") for a in pinned_apps}
    return [w for w in open_apps if w.get("exe", w.get("exec", "")) not in pinned_execs]


def build_app_info_from_window(window_info: dict) -> dict:
    """
    Convert a daemon window_list entry into a dock app_info dict.

    Args:
        window_info: Dict from window_list: {pid, exe, zone, ...}.

    Returns:
        {"name": str, "exec": str, "icon": str, "pid": int, "zone": int}
    """
    exe  = window_info.get("exe", "")
    name = os.path.basename(exe) if exe else window_info.get("name", "App")
    return {
        "name": name,
        "exec": exe,
        "icon": "application-x-executable",
        "pid":  window_info.get("pid"),
        "zone": window_info.get("zone", 1),
    }


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.dock.dock_item import DockItem

    DOCK_HEIGHT = 72   # px — matches SIZING["dock_height"]
    DOCK_MARGIN = 8    # px — gap from screen bottom

    class LuminosDock(Gtk.ApplicationWindow):
        """
        Full macOS-style dock pinned to the bottom of the screen.

        Sections (left → right):
            Pinned apps | [separator] | Open (not pinned) | [separator] | Utilities
        """

        def __init__(self, application: Gtk.Application,
                     daemon_client: "DaemonClient | None" = None):
            super().__init__(application=application)
            self._client    = daemon_client or DaemonClient()
            self.open_apps: list[dict] = []   # current daemon window_list

            # ---------------------------------------------------------------
            # Window setup
            # ---------------------------------------------------------------
            self.set_title("luminos-dock")
            self.set_decorated(False)
            self.set_resizable(False)
            self.add_css_class("luminos-dock")

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(generate_css(mode.get_mode()))
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # ---------------------------------------------------------------
            # Layer-shell pinning
            # ---------------------------------------------------------------
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.TOP)
                LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, True)
                LayerShell.set_anchor(self, LayerShell.Edge.LEFT,   True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT,  True)
                LayerShell.set_exclusive_zone(self, DOCK_HEIGHT + DOCK_MARGIN)
                LayerShell.set_margin(self, LayerShell.Edge.BOTTOM, DOCK_MARGIN)
                logger.info("gtk4-layer-shell pinned dock to bottom edge")
            else:
                logger.warning(
                    "gtk4-layer-shell not available — dock shown as normal window"
                )
                self.set_default_size(700, DOCK_HEIGHT)

            # ---------------------------------------------------------------
            # Load pinned apps
            # ---------------------------------------------------------------
            self.pinned_apps = load_pinned()

            # ---------------------------------------------------------------
            # Build layout
            # ---------------------------------------------------------------
            self._build_dock()

            # ---------------------------------------------------------------
            # Polling
            # ---------------------------------------------------------------
            GLib.timeout_add_seconds(3, self._poll_windows)
            self._poll_windows()   # immediate

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build_dock(self):
            """Construct the pill container with left/center/right sections."""

            # Outer centering box (so pill doesn't stretch full screen width)
            outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            outer.set_halign(Gtk.Align.CENTER)
            outer.set_valign(Gtk.Align.END)
            outer.set_margin_bottom(DOCK_MARGIN)
            self.set_child(outer)

            # Pill container — frosted glass via CSS class luminos-dock
            pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            pill.set_margin_start(8)
            pill.set_margin_end(8)
            pill.set_margin_top(6)
            pill.set_margin_bottom(6)
            pill.add_css_class("luminos-dock")
            outer.append(pill)

            # LEFT — pinned apps
            self._left_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )
            pill.append(self._left_box)

            self._pinned_items: dict[str, DockItem] = {}   # exec → DockItem
            for app in self.pinned_apps:
                item = DockItem(app_info=app, is_open=False, zone=1)
                self._left_box.append(item)
                self._pinned_items[app.get("exec", "")] = item

            # Separator after pinned
            self._sep_pinned = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            self._sep_pinned.set_margin_top(8)
            self._sep_pinned.set_margin_bottom(8)
            pill.append(self._sep_pinned)

            # CENTER — open apps not in pinned
            self._center_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )
            pill.append(self._center_box)
            self._open_items: dict[int, DockItem] = {}   # pid → DockItem

            # Separator before utilities
            self._sep_utils = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            self._sep_utils.set_margin_top(8)
            self._sep_utils.set_margin_bottom(8)
            pill.append(self._sep_utils)

            # RIGHT — utilities
            right_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )
            pill.append(right_box)

            settings_item = DockItem(
                app_info={"name": "Settings", "exec": "luminos-settings",
                          "icon": "preferences-system"},
                is_open=False, zone=1,
            )
            right_box.append(settings_item)

            trash_item = DockItem(
                app_info={"name": "Trash", "exec": "luminos-trash",
                          "icon": "user-trash"},
                is_open=False, zone=1,
            )
            right_box.append(trash_item)

        # -------------------------------------------------------------------
        # Daemon polling
        # -------------------------------------------------------------------

        def _poll_windows(self) -> bool:
            """
            Query daemon for the current open window list.
            Updates pinned item open-state dots and center section.
            """
            try:
                response = self._client.send({"type": "window_list"})
                windows  = response if isinstance(response, list) else []
            except Exception as e:
                logger.debug(f"window_list poll error: {e}")
                windows = []

            self.open_apps = windows
            self._sync_dock(windows)
            return GLib.SOURCE_CONTINUE

        def _sync_dock(self, windows: list):
            """
            Update dock item states to match the current window list.

            - Mark pinned items as open/closed.
            - Add new open-but-not-pinned items to center.
            - Remove center items whose pid is no longer in window list.
            """
            open_pids  = {w.get("pid") for w in windows}
            open_execs = {w.get("exe", w.get("exec", "")): w for w in windows}

            # Update pinned open-state dots
            for exec_name, item in self._pinned_items.items():
                w = open_execs.get(exec_name)
                item.set_open(w is not None)
                if w is not None:
                    item.set_zone(w.get("zone", 1))

            # Remove center items no longer open
            stale_pids = [pid for pid in self._open_items if pid not in open_pids]
            for pid in stale_pids:
                self.remove_running_app(pid)

            # Add newly opened apps that aren't pinned
            extra = get_open_apps_not_pinned(windows, self.pinned_apps)
            existing_center_pids = set(self._open_items.keys())
            for window_info in extra:
                pid = window_info.get("pid")
                if pid is not None and pid not in existing_center_pids:
                    self.add_running_app(window_info)

        # -------------------------------------------------------------------
        # Running app management
        # -------------------------------------------------------------------

        def add_running_app(self, window_info: dict):
            """Add a non-pinned open window to the center section."""
            app_info = build_app_info_from_window(window_info)
            pid  = window_info.get("pid")
            zone = window_info.get("zone", 1)
            item = DockItem(app_info=app_info, is_open=True, zone=zone)
            self._center_box.append(item)
            if pid is not None:
                self._open_items[pid] = item
            logger.debug(f"Dock: added running app pid={pid} zone={zone}")

        def remove_running_app(self, pid: int):
            """Remove a center-section dock item by pid."""
            item = self._open_items.pop(pid, None)
            if item is not None:
                self._center_box.remove(item)
                logger.debug(f"Dock: removed app pid={pid}")

        # -------------------------------------------------------------------
        # App activation (click handler — called by DockItem._on_click)
        # -------------------------------------------------------------------

        def _on_item_activated(self, item: "DockItem"):
            """
            Handle dock icon click.

            - If app is open: send focus_window to compositor.
            - If pinned but closed: launch via subprocess.
            """
            app_info = item.app_info
            pid      = app_info.get("pid")

            if pid is not None and pid in self._open_items:
                # App is open — ask compositor to focus it
                try:
                    self._client.send({"type": "window_focus", "pid": pid})
                except Exception as e:
                    logger.debug(f"focus error: {e}")
                return

            # Pinned but not open — launch it
            exec_cmd = app_info.get("exec", "")
            if exec_cmd:
                try:
                    subprocess.Popen(
                        exec_cmd.split(),
                        start_new_session=True,
                        close_fds=True,
                    )
                    logger.info(f"Dock: launched {exec_cmd!r}")
                except Exception as e:
                    logger.warning(f"Dock: failed to launch {exec_cmd!r}: {e}")
