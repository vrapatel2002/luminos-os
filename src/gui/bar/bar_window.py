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
  Right: wifi + battery + volume icons using Phosphor SVGs (16px each)
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
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
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
from gui.common.subprocess_helpers import get_wifi_info

# Phosphor SVG icon directory
PHOSPHOR_DIR = "/opt/luminos/assets/icons/phosphor"


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


def get_network_info() -> dict:
    """Return network connection type and status."""
    # Check for active ethernet first
    try:
        for iface in sorted(os.listdir('/sys/class/net/')):
            if iface.startswith('e'):  # eth0, enp*, etc.
                carrier = f'/sys/class/net/{iface}/carrier'
                if os.path.exists(carrier):
                    with open(carrier) as f:
                        if f.read().strip() == '1':
                            return {"type": "ethernet", "connected": True}
    except OSError:
        pass
    # Fall back to wifi
    try:
        from gui.common.subprocess_helpers import get_wifi_info
        info = get_wifi_info()
        return {"type": "wifi", "connected": info.get("connected", False)}
    except Exception:
        pass
    return {"type": "wifi", "connected": False}


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


def _phosphor(name: str) -> str:
    """Return the full path to a Phosphor SVG icon."""
    return os.path.join(PHOSPHOR_DIR, f"{name}.svg")


# ===========================================================================
# CSS — all values from luminos_theme
# ===========================================================================

_BAR_CSS = f"""
window {{
    background: transparent;
}}

.luminos-bar-surface {{
    background: {glass_bg(0.25)};
    border-bottom: 1px solid {BORDER_SUBTLE};
    min-height: {BAR_HEIGHT}px;
    min-width: 100%;
}}

.luminos-bar-clock {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_BODY_LARGE}px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
}}

.luminos-bar-icon {{
    color: {TEXT_SECONDARY};
    -gtk-icon-style: symbolic;
}}

.luminos-bar-icon-muted {{
    color: {TEXT_DISABLED};
    -gtk-icon-style: symbolic;
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
    color: {TEXT_SECONDARY};
    -gtk-icon-style: symbolic;
}}

.luminos-bar-bell-muted {{
    color: {TEXT_DISABLED};
    -gtk-icon-style: symbolic;
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

def _load_svg_texture(svg_name: str, size: int = 16) -> "Gdk.Texture | None":
    """
    Load a Phosphor SVG scaled to size×size and return a Gdk.Texture.
    Uses GdkPixbuf so the SVG is rasterised at exactly the right pixel size.
    """
    try:
        path = _phosphor(svg_name)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
        return Gdk.Texture.new_for_pixbuf(pixbuf)
    except Exception as e:
        logger.debug(f"SVG load failed for {svg_name}: {e}")
        return None


if _GTK_AVAILABLE:

    def _make_svg_image(svg_name: str, size: int = 16) -> "Gtk.Image":
        """Create a Gtk.Image from a Phosphor SVG, pre-scaled to size×size."""
        texture = _load_svg_texture(svg_name, size)
        if texture is not None:
            img = Gtk.Image.new_from_paintable(texture)
        else:
            img = Gtk.Image()
        img.set_size_request(size, size)
        return img

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
            # Do NOT call set_resizable(False) — layer-shell owns the window size.
            # Calling it caps the window at its natural content width and prevents
            # the Wayland compositor from stretching it to full screen width.

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
            LayerShell.set_namespace(self, "luminos-bar")
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

            # Bell icon (notification center) — Phosphor bell.svg
            bell_box = Gtk.Overlay()
            self._bell_icon = _make_svg_image("bell")
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

            # WiFi/Ethernet icon — display only, not clickable
            self._wifi_icon = _make_svg_image("wifi-high")
            self._wifi_icon.add_css_class("luminos-bar-icon")
            right.append(self._wifi_icon)

            # Battery icon — Phosphor battery-full.svg
            self._battery_icon = _make_svg_image("battery-full")
            self._battery_icon.add_css_class("luminos-bar-icon")
            right.append(self._battery_icon)

            self._battery_text = Gtk.Label(label="--%")
            self._battery_text.add_css_class("luminos-bar-battery-text")
            right.append(self._battery_text)

            # Quick settings button — gear icon, opens quick settings panel
            self._qs_icon = _make_svg_image("gear")
            self._qs_icon.add_css_class("luminos-bar-icon")
            right.append(self._qs_icon)

            qs_click = Gtk.GestureClick()
            qs_click.connect("pressed", self._on_tray_click)
            self._qs_icon.add_controller(qs_click)

            root.append(right)
            overlay.set_child(root)

            # --- Center: clock (absolutely centered via overlay) ---
            clock_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            clock_box.set_halign(Gtk.Align.CENTER)
            clock_box.set_valign(Gtk.Align.CENTER)

            self._clock_label = Gtk.Label(label="00:00")
            self._clock_label.add_css_class("luminos-bar-clock")
            clock_box.append(self._clock_label)

            clock_click = Gtk.GestureClick()
            clock_click.connect("pressed", self._on_clock_click)
            clock_box.add_controller(clock_click)

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

        def _set_icon(self, widget: "Gtk.Image", svg_name: str, size: int = 16):
            """Swap the paintable on an existing image widget."""
            texture = _load_svg_texture(svg_name, size)
            if texture is not None:
                widget.set_from_paintable(texture)

        def _poll_tray(self) -> bool:
            # Network — show ethernet or wifi icon based on active connection
            try:
                net = get_network_info()
                if net["type"] == "ethernet":
                    self._set_icon(self._wifi_icon, "ethernet")
                    self._wifi_icon.remove_css_class("luminos-bar-icon-muted")
                    self._wifi_icon.add_css_class("luminos-bar-icon")
                elif net["connected"]:
                    self._set_icon(self._wifi_icon, "wifi-high")
                    self._wifi_icon.remove_css_class("luminos-bar-icon-muted")
                    self._wifi_icon.add_css_class("luminos-bar-icon")
                else:
                    self._set_icon(self._wifi_icon, "wifi-slash")
                    self._wifi_icon.remove_css_class("luminos-bar-icon")
                    self._wifi_icon.add_css_class("luminos-bar-icon-muted")
            except Exception:
                pass

            # Battery — swap SVG based on charging/low state
            try:
                bat = get_battery_info()
                pct = bat.get("percent")
                charging = bat.get("charging", False)
                if charging:
                    self._set_icon(self._battery_icon, "battery-charging")
                elif pct is not None and pct <= 20:
                    self._set_icon(self._battery_icon, "battery-low")
                else:
                    self._set_icon(self._battery_icon, "battery-full")
                self._battery_text.set_text(
                    f"{pct}%" if pct is not None else "--%"
                )
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

        def _on_bell_click(self, gesture, *_):
            """Open/close notification center on bell click."""
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            try:
                from gui.quick_settings import get_panel as get_qs_panel
                qs = get_qs_panel()
                if qs and qs.get_visible():
                    qs.hide()
            except Exception:
                pass
            try:
                from gui.notifications import toggle_panel
                toggle_panel()
            except Exception as e:
                logger.debug(f"Notification center toggle error: {e}")

        def _on_clock_click(self, gesture, *_):
            """Open/close calendar popup on clock click."""
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            try:
                from gui.quick_settings import get_panel as get_qs
                qs = get_qs()
                if qs and qs.get_visible():
                    qs.hide()
            except Exception:
                pass
            try:
                from gui.notifications import get_panel as get_notif
                notif = get_notif()
                if notif and notif.get_visible():
                    notif.hide()
            except Exception:
                pass
            try:
                from gui.bar.calendar_popup import toggle_calendar
                toggle_calendar()
            except Exception as e:
                logger.debug(f"Calendar toggle error: {e}")

        def _on_tray_click(self, gesture, *_):
            """Open/close quick settings panel on gear click."""
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            try:
                from gui.quick_settings import toggle_panel
                toggle_panel()
            except Exception as e:
                logger.debug(f"Quick settings toggle error: {e}")
