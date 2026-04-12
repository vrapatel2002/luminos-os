"""
src/gui/bar/bar_window.py
LuminosBar — minimal top bar for the Luminos desktop.

Visual spec (from LUMINOS_DESIGN_SYSTEM.md):
  Height: BAR_HEIGHT (36px), full screen width
  Background: glass_bg(0.75) with blur(20px)
  Bottom border: 1px BORDER_SUBTLE
  No rounded corners — touches screen edges

  Left: workspace dots (6px inactive, 8px active)
  Center: clock HH:MM, absolutely centered
  Right: wifi + battery + volume icons (16px each)
"""

import datetime
import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.bar.window")

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
    ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER_SUBTLE, FONT_FAMILY, FONT_BODY_LARGE, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, BAR_HEIGHT,
    glass_bg,
)
from gui.common.socket_client import DaemonClient
from gui.common.subprocess_helpers import (
    get_wifi_info, get_volume, set_volume, toggle_mute,
)


# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def format_clock(hour: int, minute: int, *, use_24h: bool = True) -> str:
    """Format hour:minute into HH:MM display string."""
    if use_24h:
        return f"{hour:02d}:{minute:02d}"
    period = "AM" if hour < 12 else "PM"
    h12 = hour % 12 or 12
    return f"{h12}:{minute:02d} {period}"


def format_date(year: int, month: int, day: int, weekday: int) -> str:
    """Format a date. weekday: 0=Mon ... 6=Sun."""
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{DAYS[weekday]}, {MONTHS[month - 1]} {day}"


def get_active_workspace() -> int:
    """Query Hyprland for the active workspace ID."""
    try:
        import json
        result = subprocess.run(
            ["hyprctl", "activeworkspace", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("id", 1)
    except Exception:
        pass
    return 1


def get_workspace_count() -> int:
    """Query Hyprland for total workspace count."""
    try:
        import json
        result = subprocess.run(
            ["hyprctl", "workspaces", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return max(len(data), 1)
    except Exception:
        pass
    return 5


def get_battery_info() -> dict:
    """Read battery percentage and charging status from sysfs."""
    result = {"percent": None, "charging": False}
    try:
        cap_path = "/sys/class/power_supply/BAT0/capacity"
        status_path = "/sys/class/power_supply/BAT0/status"
        if os.path.exists(cap_path):
            with open(cap_path) as f:
                result["percent"] = int(f.read().strip())
        if os.path.exists(status_path):
            with open(status_path) as f:
                result["charging"] = f.read().strip() in ("Charging", "Full")
    except (OSError, ValueError):
        pass
    return result


# ===========================================================================
# CSS — all values from luminos_theme
# ===========================================================================

_BAR_CSS = f"""
.luminos-bar-surface {{
    background: {glass_bg(0.75)};
    border-bottom: 1px solid {BORDER_SUBTLE};
    min-height: {BAR_HEIGHT}px;
}}

.luminos-bar-clock {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_BODY_LARGE}px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
}}

.luminos-bar-icon {{
    font-size: 16px;
    color: {TEXT_SECONDARY};
}}

.luminos-bar-icon-muted {{
    font-size: 16px;
    color: {TEXT_DISABLED};
}}

.luminos-bar-battery-text {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
}}

.luminos-workspace-dot {{
    min-width: 6px;
    min-height: 6px;
    border-radius: 9999px;
    background: {TEXT_DISABLED};
}}

.luminos-workspace-dot-active {{
    min-width: 8px;
    min-height: 8px;
    border-radius: 9999px;
    background: {ACCENT};
}}

.luminos-bar-bell {{
    font-size: 16px;
    color: {TEXT_SECONDARY};
}}

.luminos-bar-badge {{
    font-family: {FONT_FAMILY};
    font-size: 9px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    background-color: {ACCENT};
    border-radius: 9999px;
    min-width: 14px;
    min-height: 14px;
    padding: 0 2px;
}}
"""


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:

    class LuminosBar(Gtk.ApplicationWindow):
        """
        Minimal top bar: workspace dots | clock | system tray.
        Pinned to top edge via gtk4-layer-shell.
        """

        def __init__(self, application: Gtk.Application,
                     daemon_client: "DaemonClient | None" = None):
            super().__init__(application=application)
            self._client = daemon_client or DaemonClient()

            self.set_title("luminos-bar")
            self.set_decorated(False)
            self.set_resizable(False)

            # Load CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_BAR_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self.set_hide_on_close(False)

            # Layer shell — full width, top edge, no rounded corners
            if not _LAYER_SHELL_AVAILABLE:
                logger.error(
                    "gtk4-layer-shell is not available. "
                    "Install it with: sudo pacman -S gtk4-layer-shell"
                )
                sys.exit(1)

            LayerShell.init_for_window(self)
            LayerShell.set_layer(self, LayerShell.Layer.TOP)
            LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
            LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
            LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
            LayerShell.set_exclusive_zone(self, BAR_HEIGHT)
            LayerShell.set_keyboard_mode(
                self, LayerShell.KeyboardMode.ON_DEMAND
            )
            logger.info("gtk4-layer-shell: bar pinned to top edge")

            # Build layout using overlay for true center clock
            self._build_layout()

            # Start timers
            self._tick_clock()
            GLib.timeout_add_seconds(1, self._tick_clock)
            GLib.timeout_add_seconds(5, self._poll_workspaces)
            GLib.timeout_add_seconds(10, self._poll_tray)
            self._poll_workspaces()
            self._poll_tray()

        def _build_layout(self):
            overlay = Gtk.Overlay()
            self.set_child(overlay)

            # Root box for left + right sections
            root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            root.set_hexpand(True)
            root.add_css_class("luminos-bar-surface")

            # --- Left: workspace dots ---
            self._workspace_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2
            )
            self._workspace_box.set_margin_start(SPACE_4)
            self._workspace_box.set_halign(Gtk.Align.START)
            self._workspace_box.set_valign(Gtk.Align.CENTER)
            root.append(self._workspace_box)

            # Build initial workspace dots
            self._workspace_dots: list[Gtk.Box] = []
            self._build_workspace_dots(5, 1)

            # --- Right: system tray icons ---
            right = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            right.set_margin_end(SPACE_4)
            right.set_halign(Gtk.Align.END)
            right.set_valign(Gtk.Align.CENTER)
            right.set_hexpand(True)

            # Bell icon (notification center)
            bell_box = Gtk.Overlay()
            self._bell_icon = Gtk.Label(label="󰂚")
            self._bell_icon.add_css_class("luminos-bar-bell")
            bell_box.set_child(self._bell_icon)

            self._bell_badge = Gtk.Label(label="")
            self._bell_badge.add_css_class("luminos-bar-badge")
            self._bell_badge.set_halign(Gtk.Align.END)
            self._bell_badge.set_valign(Gtk.Align.START)
            self._bell_badge.set_visible(False)
            bell_box.add_overlay(self._bell_badge)

            bell_click = Gtk.GestureClick()
            bell_click.connect("pressed", self._on_bell_click)
            bell_box.add_controller(bell_click)
            right.append(bell_box)

            # WiFi icon
            self._wifi_icon = Gtk.Label(label="󰤨")
            self._wifi_icon.add_css_class("luminos-bar-icon")
            right.append(self._wifi_icon)

            # Battery icon + percentage
            self._battery_icon = Gtk.Label(label="󰁹")
            self._battery_icon.add_css_class("luminos-bar-icon")
            right.append(self._battery_icon)

            self._battery_text = Gtk.Label(label="--%")
            self._battery_text.add_css_class("luminos-bar-battery-text")
            right.append(self._battery_text)

            # Volume icon
            self._volume_icon = Gtk.Label(label="󰕾")
            self._volume_icon.add_css_class("luminos-bar-icon")
            right.append(self._volume_icon)

            # Volume scroll control
            scroll = Gtk.EventControllerScroll(
                flags=Gtk.EventControllerScrollFlags.VERTICAL
            )
            scroll.connect("scroll", self._on_volume_scroll)
            self._volume_icon.add_controller(scroll)

            vol_click = Gtk.GestureClick()
            vol_click.connect("pressed", self._on_volume_click)
            self._volume_icon.add_controller(vol_click)

            # Click on tray area → open quick settings
            tray_click = Gtk.GestureClick()
            tray_click.connect("pressed", self._on_tray_click)
            right.add_controller(tray_click)

            root.append(right)
            overlay.set_child(root)

            # --- Center: clock (absolutely centered via overlay) ---
            clock_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            clock_box.set_halign(Gtk.Align.CENTER)
            clock_box.set_valign(Gtk.Align.CENTER)
            clock_box.set_can_target(False)

            self._clock_label = Gtk.Label(label="00:00")
            self._clock_label.add_css_class("luminos-bar-clock")
            clock_box.append(self._clock_label)

            overlay.add_overlay(clock_box)

        def _build_workspace_dots(self, total: int, active: int):
            """Rebuild workspace dot indicators."""
            for dot in self._workspace_dots:
                self._workspace_box.remove(dot)
            self._workspace_dots.clear()

            for i in range(1, total + 1):
                dot = Gtk.Box()
                if i == active:
                    dot.add_css_class("luminos-workspace-dot-active")
                else:
                    dot.add_css_class("luminos-workspace-dot")
                dot.set_valign(Gtk.Align.CENTER)
                self._workspace_box.append(dot)
                self._workspace_dots.append(dot)

        # -------------------------------------------------------------------
        # Clock — updates every second, HH:MM format
        # -------------------------------------------------------------------

        def _tick_clock(self) -> bool:
            now = datetime.datetime.now()
            self._clock_label.set_text(format_clock(now.hour, now.minute))
            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # Workspace polling
        # -------------------------------------------------------------------

        def _poll_workspaces(self) -> bool:
            active = get_active_workspace()
            total = get_workspace_count()
            total = max(total, active)
            self._build_workspace_dots(total, active)
            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # System tray polling
        # -------------------------------------------------------------------

        def _poll_tray(self) -> bool:
            # WiFi
            try:
                info = get_wifi_info()
                if info.get("connected"):
                    self._wifi_icon.set_text("󰤨")
                    self._wifi_icon.remove_css_class("luminos-bar-icon-muted")
                    self._wifi_icon.add_css_class("luminos-bar-icon")
                else:
                    self._wifi_icon.set_text("󰤭")
                    self._wifi_icon.remove_css_class("luminos-bar-icon")
                    self._wifi_icon.add_css_class("luminos-bar-icon-muted")
            except Exception:
                pass

            # Battery
            try:
                bat = get_battery_info()
                pct = bat.get("percent")
                charging = bat.get("charging", False)
                if charging:
                    self._battery_icon.set_text("󰂄")
                elif pct is not None and pct <= 20:
                    self._battery_icon.set_text("󰁺")
                else:
                    self._battery_icon.set_text("󰁹")
                self._battery_text.set_text(
                    f"{pct}%" if pct is not None else "--%"
                )
            except Exception:
                pass

            # Volume
            try:
                vol = get_volume()
                muted = vol.get("muted", False)
                if muted:
                    self._volume_icon.set_text("󰖁")
                    self._volume_icon.remove_css_class("luminos-bar-icon")
                    self._volume_icon.add_css_class("luminos-bar-icon-muted")
                else:
                    self._volume_icon.set_text("󰕾")
                    self._volume_icon.remove_css_class("luminos-bar-icon-muted")
                    self._volume_icon.add_css_class("luminos-bar-icon")
            except Exception:
                pass

            # Notification badge
            try:
                from gui.notifications import get_unread_count
                count = get_unread_count()
                if count > 0:
                    self._bell_badge.set_text(str(min(count, 99)))
                    self._bell_badge.set_visible(True)
                else:
                    self._bell_badge.set_visible(False)
            except Exception:
                pass

            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # Volume controls
        # -------------------------------------------------------------------

        def _on_bell_click(self, *_):
            """Open/close notification center on bell click."""
            try:
                from gui.notifications.notification_center_panel import NotificationCenterPanel
                if not hasattr(self, "_notif_panel") or self._notif_panel is None:
                    # Get the notification center from the overlay singleton
                    center = None
                    try:
                        from gui.notifications import _get_overlay
                        overlay = _get_overlay()
                        if overlay:
                            center = overlay.get_center()
                    except Exception:
                        pass
                    self._notif_panel = NotificationCenterPanel(
                        notification_center=center
                    )
                self._notif_panel.toggle()
            except Exception as e:
                logger.debug(f"Notification center toggle error: {e}")

        def _on_tray_click(self, *_):
            """Open/close quick settings panel on tray click."""
            try:
                from gui.quick_settings import toggle_panel
                toggle_panel()
            except Exception as e:
                logger.debug(f"Quick settings toggle error: {e}")

        def _on_volume_scroll(self, _ctrl, _dx, dy):
            vol = get_volume()
            new_pct = max(0, min(100, vol["percent"] - int(dy * 5)))
            set_volume(new_pct)
            self._poll_tray()

        def _on_volume_click(self, *_):
            toggle_mute()
            self._poll_tray()
