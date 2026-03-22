"""
src/gui/bar/bar_window.py
LuminosBar — Full-width top bar window for the Luminos desktop.

Architecture:
- LuminosBar extends Gtk.ApplicationWindow.
- Layout: left (menu + app name) | center (clock) | right (tray).
- gtk4-layer-shell pins it to the top edge as a Wayland layer surface.
  Falls back to a normal 1280×36 window when layer-shell is absent.
- Daemon polling: GLib.timeout_add_seconds(5, ...) for AI + power + battery.
- System polling: GLib.timeout_add_seconds(10, ...) for wifi + bluetooth + volume.
- All polling is on the GTK main thread — callbacks are non-blocking because
  DaemonClient and subprocess helpers have short timeouts.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.bar.window")

# ---------------------------------------------------------------------------
# GTK imports (guarded — headless tests import only helper modules)
# ---------------------------------------------------------------------------
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

# gtk4-layer-shell is optional — falls back gracefully
_LAYER_SHELL_AVAILABLE = False
if _GTK_AVAILABLE:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        _LAYER_SHELL_AVAILABLE = True
    except (ImportError, ValueError):
        pass

# Ensure src/ on path
_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme import mode, generate_css
from gui.common.socket_client import DaemonClient

# ---------------------------------------------------------------------------
# Pure helper — testable without GTK
# ---------------------------------------------------------------------------

def format_clock(hour: int, minute: int, second: int, *, use_24h: bool = True) -> str:
    """Format hour/minute/second into a display string."""
    if use_24h:
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    period = "AM" if hour < 12 else "PM"
    h12 = hour % 12 or 12
    return f"{h12}:{minute:02d}:{second:02d} {period}"


def format_date(year: int, month: int, day: int, weekday: int) -> str:
    """Format a date into a short display string. weekday: 0=Mon … 6=Sun."""
    DAYS   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{DAYS[weekday]}, {MONTHS[month - 1]} {day}"


# ===========================================================================
# GTK Window class
# ===========================================================================

if _GTK_AVAILABLE:
    # Late imports — GTK widget classes live here
    from gui.bar.tray_widgets import (
        AIIndicator, PowerIndicator, BatteryIndicator,
        WiFiIndicator, BluetoothIndicator, VolumeIndicator,
    )

    # Bar geometry constants
    BAR_HEIGHT  = 36   # px — matches SIZING["bar_height"]
    BAR_MARGIN  = 0    # px — flush with screen edges

    class LuminosBar(Gtk.ApplicationWindow):
        """
        Full-width Wayland layer surface top bar.

        Pinned to top edge via gtk4-layer-shell when available.
        Polls daemon every 5 s for AI / power / battery data.
        Polls system every 10 s for wifi / bluetooth / volume.
        """

        def __init__(self, application: Gtk.Application,
                     daemon_client: "DaemonClient | None" = None):
            super().__init__(application=application)
            self._client = daemon_client or DaemonClient()

            # ---------------------------------------------------------------
            # Window setup
            # ---------------------------------------------------------------
            self.set_title("luminos-bar")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(1920, BAR_HEIGHT)

            # Apply theme CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(generate_css(mode.get_mode()))
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            self.add_css_class("luminos-bar")

            # ---------------------------------------------------------------
            # Layer-shell pinning
            # ---------------------------------------------------------------
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.TOP)
                LayerShell.set_anchor(self, LayerShell.Edge.TOP,    True)
                LayerShell.set_anchor(self, LayerShell.Edge.LEFT,   True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT,  True)
                LayerShell.set_exclusive_zone(self, BAR_HEIGHT)
                LayerShell.set_margin(self, LayerShell.Edge.TOP, BAR_MARGIN)
                # ON_DEMAND so bar can receive Super key without blocking others
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.ON_DEMAND
                )
                logger.info("gtk4-layer-shell pinned top bar to screen edge")
            else:
                logger.warning(
                    "gtk4-layer-shell not available — bar shown as normal window"
                )
                self.set_default_size(1280, BAR_HEIGHT)

            # ---------------------------------------------------------------
            # Layout: left | center | right inside an overlay container
            # ---------------------------------------------------------------
            overlay = Gtk.Overlay()
            self.set_child(overlay)

            # Root box (full width, transparent) for left + right
            root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            root_box.set_hexpand(True)
            root_box.add_css_class("luminos-bar")

            # --- Left section ---
            left_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            left_box.set_margin_start(10)
            left_box.set_halign(Gtk.Align.START)
            left_box.set_valign(Gtk.Align.CENTER)

            self._menu_btn = Gtk.Button(label="◉ Luminos")
            self._menu_btn.add_css_class("luminos-btn")
            self._menu_btn.connect("clicked", self._on_menu_click)
            left_box.append(self._menu_btn)

            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            sep.set_margin_top(8)
            sep.set_margin_bottom(8)
            left_box.append(sep)

            self._app_label = Gtk.Label(label="")
            self._app_label.add_css_class("luminos-active-app")
            left_box.append(self._app_label)

            # --- Right (tray) section ---
            right_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=6
            )
            right_box.set_margin_end(10)
            right_box.set_halign(Gtk.Align.END)
            right_box.set_valign(Gtk.Align.CENTER)
            right_box.set_hexpand(True)

            # Quick settings trigger button (⚙)
            qs_btn = Gtk.Button(label="⚙")
            qs_btn.add_css_class("luminos-btn")
            qs_btn.set_tooltip_text("Settings")
            qs_btn.connect("clicked", self._on_quick_settings_click)
            right_box.append(qs_btn)

            self._ai_widget      = AIIndicator()
            self._power_widget   = PowerIndicator(daemon_client=self._client)
            self._battery_widget = BatteryIndicator()
            self._wifi_widget    = WiFiIndicator()
            self._bt_widget      = BluetoothIndicator()
            self._vol_widget     = VolumeIndicator()

            for w in (
                self._ai_widget,
                self._power_widget,
                self._battery_widget,
                self._wifi_widget,
                self._bt_widget,
                self._vol_widget,
            ):
                right_box.append(w)

            root_box.append(left_box)
            root_box.append(right_box)
            overlay.set_child(root_box)

            # --- Center (clock) — floated over root_box via overlay ---
            center_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            center_box.set_halign(Gtk.Align.CENTER)
            center_box.set_valign(Gtk.Align.CENTER)
            center_box.set_can_target(False)  # don't steal pointer events

            self._clock_label = Gtk.Label(label="00:00:00")
            self._clock_label.add_css_class("luminos-clock")
            self._date_label  = Gtk.Label(label="")
            self._date_label.add_css_class("luminos-date")

            center_box.append(self._clock_label)
            center_box.append(self._date_label)
            overlay.add_overlay(center_box)

            # ---------------------------------------------------------------
            # Start polling timers
            # ---------------------------------------------------------------
            self._tick_clock()                                   # immediate
            GLib.timeout_add_seconds(1,  self._tick_clock)
            GLib.timeout_add_seconds(5,  self._poll_daemon)
            GLib.timeout_add_seconds(10, self._poll_system)

            self._poll_daemon()   # immediate
            self._poll_system()   # immediate

            # Super key → toggle launcher
            _key_ctrl = Gtk.EventControllerKey()
            _key_ctrl.connect("key-pressed", self._on_bar_key_pressed)
            self.add_controller(_key_ctrl)

        # -------------------------------------------------------------------
        # Clock
        # -------------------------------------------------------------------

        def _tick_clock(self) -> bool:
            """Update clock and date labels. Called every second by GLib timer."""
            import datetime
            now = datetime.datetime.now()
            self._clock_label.set_text(
                format_clock(now.hour, now.minute, now.second)
            )
            self._date_label.set_text(
                format_date(now.year, now.month, now.day, now.weekday())
            )
            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # Daemon polling (AI, power, battery)
        # -------------------------------------------------------------------

        def _poll_daemon(self) -> bool:
            """Poll daemon for AI status, power status, AC/battery status."""
            try:
                ai_status = self._client.send({"type": "manager_status"})
                self._ai_widget.update(ai_status)
            except Exception as e:
                logger.debug(f"AI poll error: {e}")

            try:
                power_status = self._client.send({"type": "power_status"})
                self._power_widget.update(power_status)
            except Exception as e:
                logger.debug(f"Power poll error: {e}")

            try:
                ac_status = self._client.send({"type": "ac_status"})
                self._battery_widget.update(ac_status)
            except Exception as e:
                logger.debug(f"Battery poll error: {e}")

            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # System polling (wifi, bluetooth, volume — subprocess-based)
        # -------------------------------------------------------------------

        def _poll_system(self) -> bool:
            """Update wifi, bluetooth, and volume tray widgets."""
            try:
                self._wifi_widget.update()
            except Exception as e:
                logger.debug(f"WiFi poll error: {e}")

            try:
                self._bt_widget.update()
            except Exception as e:
                logger.debug(f"Bluetooth poll error: {e}")

            try:
                self._vol_widget.update()
            except Exception as e:
                logger.debug(f"Volume poll error: {e}")

            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # Active app name (called externally or from compositor integration)
        # -------------------------------------------------------------------

        def set_active_app(self, name: str):
            """Update the active application label in the left section."""
            self._app_label.set_text(name or "")

        # -------------------------------------------------------------------
        # Menu
        # -------------------------------------------------------------------

        def _on_quick_settings_click(self, *_):
            """Open Luminos Settings app."""
            try:
                from gui.settings import launch_settings
                launch_settings()
            except Exception as e:
                logger.debug(f"Settings launch error: {e}")

        def _on_menu_click(self, *_):
            """Luminos menu button → toggle app launcher."""
            self._toggle_launcher()

        def _toggle_launcher(self):
            try:
                from gui.launcher import toggle_launcher
                toggle_launcher()
            except Exception as e:
                logger.debug(f"Launcher toggle error: {e}")

        def _on_bar_key_pressed(self, ctrl, keyval, keycode, state) -> bool:
            """Handle Super key to open/close the launcher."""
            if keyval in (Gdk.KEY_Super_L, Gdk.KEY_Super_R):
                self._toggle_launcher()
                return True
            return False
