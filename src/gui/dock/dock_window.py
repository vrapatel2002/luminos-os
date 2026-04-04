"""
src/gui/dock/dock_window.py
LuminosDock — frosted glass pill dock for the Luminos desktop.

Visual spec (from LUMINOS_DESIGN_SYSTEM.md):
  Shape: floating pill, frosted glass
  Background: glass_bg(0.8) with blur(20px)
  Border: 1px BORDER
  Corner radius: RADIUS_LG (16px)
  Height: DOCK_HEIGHT (64px)
  Position: centered, DOCK_BOTTOM_MARGIN (20px) from bottom
  Layer shell: BOTTOM + LEFT + RIGHT anchors, pill centered via halign

Architecture:
  Three sections: pinned | separator | running (not pinned)
  Polls daemon every 3s for open windows.
  All daemon calls graceful — no crash when daemon offline.
"""

import logging
import math
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.dock.window")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gdk
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
    BG_BASE, BG_ELEVATED, ACCENT, ACCENT_GLOW, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED, BORDER, BORDER_SUBTLE,
    FONT_FAMILY, FONT_CAPTION, SPACE_1, SPACE_2, SPACE_3, SPACE_4,
    RADIUS_LG, RADIUS_MD, RADIUS_SM,
    ANIM_INSTANT, ANIM_FAST,
    DOCK_HEIGHT, DOCK_ICON_SIZE, DOCK_BOTTOM_MARGIN,
    glass_bg,
)
from gui.common.socket_client import DaemonClient
from gui.dock.dock_config import load_pinned
from gui.dock.dock_item import _get_tooltip, _should_show_badge


# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def get_open_apps_not_pinned(open_apps: list, pinned_apps: list) -> list:
    """Filter open_apps to exclude those already in pinned_apps."""
    pinned_execs = {a.get("exec", "") for a in pinned_apps}
    return [w for w in open_apps if w.get("exe", w.get("exec", "")) not in pinned_execs]


def build_app_info_from_window(window_info: dict) -> dict:
    """Convert a daemon window_list entry into a dock app_info dict."""
    exe = window_info.get("exe", "")
    name = os.path.basename(exe) if exe else window_info.get("name", "App")
    return {
        "name": name,
        "exec": exe,
        "icon": "application-x-executable",
        "pid": window_info.get("pid"),
        "zone": window_info.get("zone", 1),
    }


# ===========================================================================
# CSS — all values from luminos_theme.py
# ===========================================================================

_DOCK_CSS = f"""
.luminos-dock-surface {{
    background: transparent;
}}

.luminos-dock-pill {{
    background: {glass_bg(0.8)};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_LG}px;
    padding: {SPACE_2}px {SPACE_3}px;
    min-height: {DOCK_HEIGHT}px;
}}

.luminos-dock-icon {{
    transition: {ANIM_FAST}ms ease;
}}

.luminos-dock-icon:hover {{
    transition: {ANIM_FAST}ms ease;
}}

.luminos-dock-item {{
    padding: {SPACE_1}px;
    border-radius: {RADIUS_MD}px;
    transition: {ANIM_FAST}ms ease;
}}

.luminos-dock-item:hover {{
    background: {ACCENT_SUBTLE};
}}

.luminos-dock-separator {{
    background: {BORDER};
    min-width: 1px;
    margin-top: {SPACE_3}px;
    margin-bottom: {SPACE_3}px;
}}

.luminos-dock-label {{
    background: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_CAPTION}px;
    padding: {SPACE_1}px {SPACE_2}px;
    border-radius: {RADIUS_SM}px;
}}

.zone-badge-2 {{
    background: {ACCENT_SUBTLE};
    color: {ACCENT};
    font-size: 9px;
    font-weight: 600;
    border-radius: {RADIUS_SM}px;
    padding: 1px 3px;
}}

.zone-badge-3 {{
    background: rgba(255, 68, 85, 0.15);
    color: #FF4455;
    font-size: 9px;
    font-weight: 600;
    border-radius: {RADIUS_SM}px;
    padding: 1px 3px;
}}
"""

# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.dock.dock_item import DockItem

    class LuminosDock(Gtk.ApplicationWindow):
        """
        Frosted glass pill dock pinned to screen bottom.

        Sections (left → right):
            Pinned apps | separator | Running (not pinned)
        """

        def __init__(self, application: Gtk.Application,
                     daemon_client: "DaemonClient | None" = None):
            super().__init__(application=application)
            self._client = daemon_client or DaemonClient()
            self.open_apps: list[dict] = []

            # Window setup
            self.set_title("luminos-dock")
            self.set_decorated(False)
            self.set_resizable(False)

            # Load CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_DOCK_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # Layer shell: anchor bottom + left + right for full-width surface
            # Pill itself is halign=CENTER inside
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.TOP)
                LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, True)
                LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
                LayerShell.set_exclusive_zone(self, DOCK_HEIGHT + DOCK_BOTTOM_MARGIN)
                LayerShell.set_margin(self, LayerShell.Edge.BOTTOM, DOCK_BOTTOM_MARGIN)
                logger.info("gtk4-layer-shell: dock pinned to bottom edge")
            else:
                logger.warning("gtk4-layer-shell not available — dock as normal window")
                self.set_default_size(700, DOCK_HEIGHT + DOCK_BOTTOM_MARGIN * 2)

            # Load pinned apps
            self.pinned_apps = load_pinned()

            # Build layout
            self._build_dock()

            # Poll daemon every 3s
            GLib.timeout_add_seconds(3, self._poll_windows)
            self._poll_windows()

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build_dock(self):
            """Construct the pill container with pinned | separator | running."""

            # Outer transparent surface — full width, pill centered inside
            outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            outer.set_halign(Gtk.Align.CENTER)
            outer.set_valign(Gtk.Align.END)
            outer.add_css_class("luminos-dock-surface")
            self.set_child(outer)

            # Pill container
            self._pill = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            self._pill.add_css_class("luminos-dock-pill")
            outer.append(self._pill)

            # LEFT — pinned apps
            self._left_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            self._pill.append(self._left_box)

            self._pinned_items: dict[str, "DockItem"] = {}
            for app in self.pinned_apps:
                item = DockItem(app_info=app, is_open=False, zone=1)
                self._left_box.append(item)
                self._pinned_items[app.get("exec", "")] = item

            # Separator between pinned and running
            self._separator = Gtk.Box()
            self._separator.add_css_class("luminos-dock-separator")
            self._separator.set_visible(False)
            self._pill.append(self._separator)

            # CENTER — running apps not in pinned
            self._center_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            self._pill.append(self._center_box)
            self._open_items: dict[int, "DockItem"] = {}

        # -------------------------------------------------------------------
        # Daemon polling
        # -------------------------------------------------------------------

        def _poll_windows(self) -> bool:
            """Query daemon for current open windows."""
            try:
                response = self._client.send({"type": "window_list"})
                windows = response if isinstance(response, list) else []
            except Exception as e:
                logger.debug(f"window_list poll error: {e}")
                windows = []

            self.open_apps = windows
            self._sync_dock(windows)
            return GLib.SOURCE_CONTINUE

        def _sync_dock(self, windows: list):
            """Update dock items to match current window list."""
            open_pids = {w.get("pid") for w in windows}
            open_execs = {w.get("exe", w.get("exec", "")): w for w in windows}

            # Update pinned open-state dots
            for exec_name, item in self._pinned_items.items():
                w = open_execs.get(exec_name)
                item.set_open(w is not None)
                if w is not None:
                    item.set_zone(w.get("zone", 1))

            # Remove stale center items
            stale_pids = [pid for pid in self._open_items if pid not in open_pids]
            for pid in stale_pids:
                self.remove_running_app(pid)

            # Add new running apps not in pinned
            extra = get_open_apps_not_pinned(windows, self.pinned_apps)
            existing = set(self._open_items.keys())
            for window_info in extra:
                pid = window_info.get("pid")
                if pid is not None and pid not in existing:
                    self.add_running_app(window_info)

            # Show separator only when both sections have items
            has_running = len(self._open_items) > 0
            has_pinned = len(self._pinned_items) > 0
            self._separator.set_visible(has_pinned and has_running)

        # -------------------------------------------------------------------
        # Running app management
        # -------------------------------------------------------------------

        def add_running_app(self, window_info: dict):
            """Add a non-pinned running app to the center section."""
            app_info = build_app_info_from_window(window_info)
            pid = window_info.get("pid")
            zone = window_info.get("zone", 1)
            item = DockItem(app_info=app_info, is_open=True, zone=zone)
            self._center_box.append(item)
            if pid is not None:
                self._open_items[pid] = item

        def remove_running_app(self, pid: int):
            """Remove a center-section dock item by pid."""
            item = self._open_items.pop(pid, None)
            if item is not None:
                self._center_box.remove(item)

        # -------------------------------------------------------------------
        # App activation (click handler)
        # -------------------------------------------------------------------

        def _on_item_activated(self, item: "DockItem"):
            """Handle dock icon click — focus if open, launch if not."""
            app_info = item.app_info
            pid = app_info.get("pid")

            if pid is not None and pid in self._open_items:
                try:
                    self._client.send({"type": "window_focus", "pid": pid})
                except Exception as e:
                    logger.debug(f"focus error: {e}")
                return

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
