"""
src/gui/quick_settings/quick_panel.py
QuickSettingsPanel — macOS Control Center style popup.

Architecture:
- Gtk.Window (not ApplicationWindow) — created once, hidden/shown.
- Pure static methods (_get_greeting, _get_power_mode, _build_ai_summary)
  are testable without a display.
- Closes on focus-out (notify::is-active).
- Sections: greeting → toggles → volume → brightness → power → AI → WiFi → BT.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.quick_settings.panel")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme import mode, generate_css, get_colors
from gui.common.socket_client import DaemonClient
from gui.common.subprocess_helpers import (
    get_bluetooth_powered, get_volume, set_volume, toggle_mute,
)
from gui.quick_settings.brightness_ctrl import get_brightness, set_brightness
from gui.quick_settings.wifi_panel import get_active_connection, disconnect_wifi
from gui.quick_settings.bt_panel import set_bt_power


# ===========================================================================
# Pure logic — testable without GTK
# ===========================================================================

def get_greeting(hour: int) -> str:
    """
    Return a time-appropriate greeting string.

    Args:
        hour: 0-23

    Returns:
        "Good morning" | "Good afternoon" | "Good evening"
    """
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 18:
        return "Good afternoon"
    return "Good evening"


def get_power_mode_label(status: dict) -> str:
    """
    Extract current power mode from a daemon power_status response.

    Args:
        status: Dict from daemon power_status request.

    Returns:
        Mode string: "auto" | "quiet" | "balanced" | "max".
    """
    return status.get("mode", "auto")


def build_ai_summary(status: dict) -> str:
    """
    Build a multi-line AI status summary string from a manager_status response.

    Args:
        status: Dict from daemon manager_status request.

    Returns:
        Human-readable summary string.
    """
    if status.get("available") is False or "error" in status:
        return "Luminos AI: offline"

    model    = status.get("active_model") or "none"
    quant    = status.get("quantization", "")
    gaming   = status.get("gaming_mode", False)
    idle_s   = status.get("seconds_since_last_use")

    parts = [f"Model: {model}" + (f"-{quant}" if quant else "")]
    if gaming:
        parts.append("Mode: Gaming (AI paused)")
    elif idle_s is not None:
        parts.append(f"Idle: {idle_s}s")

    return "\n".join(parts)


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.quick_settings.wifi_panel import WiFiPanel
    from gui.quick_settings.bt_panel   import BluetoothPanel

    _POWER_MODES = ["quiet", "auto", "balanced", "max"]

    class QuickSettingsPanel(Gtk.Window):
        """
        Quick Settings popup panel.

        Created once; hidden after focus loss; re-shown via show_panel().
        """

        def __init__(self, daemon_client: "DaemonClient | None" = None):
            super().__init__()
            self._client = daemon_client or DaemonClient()

            self.set_title("luminos-quick-settings")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(360, -1)
            self.add_css_class("luminos-panel")

            # Apply theme CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(generate_css(mode.get_mode()))
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # Hide on focus-out (window becomes inactive)
            self.connect("notify::is-active", self._on_active_changed)

            self._build()

        # -------------------------------------------------------------------
        # Static pure methods (delegate to module-level functions)
        # -------------------------------------------------------------------

        @staticmethod
        def _get_greeting(hour: int) -> str:
            return get_greeting(hour)

        @staticmethod
        def _get_power_mode(status: dict) -> str:
            return get_power_mode_label(status)

        @staticmethod
        def _build_ai_summary(status: dict) -> str:
            return build_ai_summary(status)

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build(self):
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_max_content_height(700)
            scroll.set_propagate_natural_height(True)
            self.set_child(scroll)

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            root.set_margin_top(16)
            root.set_margin_bottom(16)
            root.set_margin_start(16)
            root.set_margin_end(16)
            scroll.set_child(root)

            # ---- Section 1: Greeting + date ----
            import datetime
            now = datetime.datetime.now()
            greeting_text = get_greeting(now.hour)

            self._greeting_lbl = Gtk.Label(label=greeting_text)
            self._greeting_lbl.add_css_class("luminos-qs-greeting")
            self._greeting_lbl.set_halign(Gtk.Align.START)
            root.append(self._greeting_lbl)

            DAYS   = ["Monday","Tuesday","Wednesday","Thursday",
                      "Friday","Saturday","Sunday"]
            MONTHS = ["January","February","March","April","May","June",
                      "July","August","September","October","November","December"]
            date_text = f"{DAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]}"
            date_lbl = Gtk.Label(label=date_text)
            date_lbl.add_css_class("luminos-qs-date")
            date_lbl.set_halign(Gtk.Align.START)
            root.append(date_lbl)

            root.append(Gtk.Separator())

            # ---- Section 2: Quick toggle pills (2×2) ----
            toggles_grid = Gtk.Grid()
            toggles_grid.set_row_spacing(8)
            toggles_grid.set_column_spacing(8)
            toggles_grid.set_hexpand(True)

            self._wifi_pill = self._make_pill("📶", "WiFi", True)
            self._bt_pill   = self._make_pill("🔵", "Bluetooth", False)
            self._dark_pill = self._make_pill("🌙", "Dark Mode", mode.get_mode())
            self._air_pill  = self._make_pill("✈", "Airplane", False)

            toggles_grid.attach(self._wifi_pill, 0, 0, 1, 1)
            toggles_grid.attach(self._bt_pill,   1, 0, 1, 1)
            toggles_grid.attach(self._dark_pill, 0, 1, 1, 1)
            toggles_grid.attach(self._air_pill,  1, 1, 1, 1)

            # Wire toggles
            self._wifi_pill.connect("clicked", self._on_wifi_toggle)
            self._bt_pill.connect("clicked",   self._on_bt_toggle)
            self._dark_pill.connect("clicked", self._on_dark_toggle)
            root.append(toggles_grid)

            root.append(Gtk.Separator())

            # ---- Section 3: Volume slider ----
            vol_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            vol_box.set_hexpand(True)

            vol_icon_btn = Gtk.Button(label="🔊")
            vol_icon_btn.add_css_class("luminos-btn")
            vol_icon_btn.connect("clicked", lambda *_: self._on_mute_toggle())
            vol_box.append(vol_icon_btn)

            self._vol_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            self._vol_slider.set_hexpand(True)
            self._vol_slider.set_draw_value(False)
            self._vol_slider.connect("value-changed", self._on_vol_changed)
            vol_box.append(self._vol_slider)

            self._vol_label = Gtk.Label(label="--")
            self._vol_label.set_width_chars(4)
            vol_box.append(self._vol_label)
            root.append(vol_box)

            # ---- Section 4: Brightness slider ----
            bright_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            bright_box.set_hexpand(True)

            bright_lbl = Gtk.Label(label="☀")
            bright_box.append(bright_lbl)

            self._bright_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 5, 100, 1
            )
            self._bright_slider.set_hexpand(True)
            self._bright_slider.set_draw_value(False)
            self._bright_slider.connect("value-changed", self._on_bright_changed)
            bright_box.append(self._bright_slider)

            self._bright_label = Gtk.Label(label="--")
            self._bright_label.set_width_chars(4)
            bright_box.append(self._bright_label)
            root.append(bright_box)

            root.append(Gtk.Separator())

            # ---- Section 5: Power mode pills ----
            power_header = Gtk.Label(label="Power Mode")
            power_header.add_css_class("luminos-qs-section-title")
            power_header.set_halign(Gtk.Align.START)
            root.append(power_header)

            power_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self._power_pills: dict[str, Gtk.Button] = {}
            for m_name in _POWER_MODES:
                btn = Gtk.Button(label=m_name.capitalize())
                btn.add_css_class("luminos-btn")
                btn.connect("clicked", self._on_power_mode, m_name)
                power_row.append(btn)
                self._power_pills[m_name] = btn
            root.append(power_row)

            root.append(Gtk.Separator())

            # ---- Section 6: AI status ----
            ai_header = Gtk.Label(label="🤖 Luminos AI")
            ai_header.add_css_class("luminos-qs-section-title")
            ai_header.set_halign(Gtk.Align.START)
            root.append(ai_header)

            self._ai_summary_lbl = Gtk.Label(label="…")
            self._ai_summary_lbl.set_halign(Gtk.Align.START)
            self._ai_summary_lbl.add_css_class("luminos-qs-dim")
            root.append(self._ai_summary_lbl)

            root.append(Gtk.Separator())

            # ---- Section 7: WiFi expandable ----
            self._wifi_expand_btn = Gtk.Button(label="▶ WiFi Networks")
            self._wifi_expand_btn.add_css_class("luminos-btn")
            self._wifi_expand_btn.set_halign(Gtk.Align.START)
            self._wifi_expand_btn.connect("clicked", self._on_wifi_expand)
            root.append(self._wifi_expand_btn)

            self._wifi_panel = WiFiPanel()
            self._wifi_panel.set_visible(False)
            root.append(self._wifi_panel)

            # ---- Section 8: BT expandable ----
            self._bt_expand_btn = Gtk.Button(label="▶ Bluetooth Devices")
            self._bt_expand_btn.add_css_class("luminos-btn")
            self._bt_expand_btn.set_halign(Gtk.Align.START)
            self._bt_expand_btn.connect("clicked", self._on_bt_expand)
            root.append(self._bt_expand_btn)

            self._bt_panel = BluetoothPanel()
            self._bt_panel.set_visible(False)
            root.append(self._bt_panel)

            root.append(Gtk.Separator())

            # ---- Section 9: Open Settings ----
            settings_btn = Gtk.Button(label="⚙  Open Settings…")
            settings_btn.add_css_class("luminos-btn")
            settings_btn.set_halign(Gtk.Align.END)
            settings_btn.connect("clicked", self._on_open_settings)
            root.append(settings_btn)

        # -------------------------------------------------------------------
        # Helpers
        # -------------------------------------------------------------------

        def _make_pill(self, icon: str, label: str,
                       active: bool) -> Gtk.Button:
            """Create a toggle pill button with icon + label."""
            btn = Gtk.Button(label=f"{icon} {label}")
            btn.add_css_class("luminos-btn-accent" if active else "luminos-btn")
            return btn

        # -------------------------------------------------------------------
        # Refresh — called on show
        # -------------------------------------------------------------------

        def _refresh(self):
            """Pull fresh data from daemon + system and update all widgets."""
            import datetime
            now = datetime.datetime.now()
            self._greeting_lbl.set_text(get_greeting(now.hour))

            # Volume
            vol = get_volume()
            self._vol_slider.set_value(vol["percent"])
            self._vol_label.set_text(f"{vol['percent']}%")

            # Brightness
            bright = get_brightness()
            if bright.get("available"):
                self._bright_slider.set_sensitive(True)
                self._bright_slider.set_value(bright["percent"])
                self._bright_label.set_text(f"{bright['percent']}%")
            else:
                self._bright_slider.set_sensitive(False)
                self._bright_label.set_text("N/A")

            # AI status
            try:
                ai_status = self._client.send({"type": "manager_status"})
            except Exception:
                ai_status = {"available": False}
            self._ai_summary_lbl.set_text(build_ai_summary(ai_status))

            # Power mode
            try:
                power_status = self._client.send({"type": "power_status"})
                current_mode = get_power_mode_label(power_status)
            except Exception:
                current_mode = "auto"
            for m_name, btn in self._power_pills.items():
                if m_name == current_mode:
                    btn.remove_css_class("luminos-btn")
                    btn.add_css_class("luminos-btn-accent")
                else:
                    btn.remove_css_class("luminos-btn-accent")
                    btn.add_css_class("luminos-btn")

        # -------------------------------------------------------------------
        # Toggle handlers
        # -------------------------------------------------------------------

        def _on_wifi_toggle(self, *_):
            # Toggle WiFi on/off via nmcli (placeholder — full impl Phase 8.7)
            pass

        def _on_bt_toggle(self, *_):
            powered = get_bluetooth_powered()
            set_bt_power(not powered)

        def _on_dark_toggle(self, *_):
            mode.set_manual(not mode.get_mode())

        def _on_mute_toggle(self):
            toggle_mute()
            vol = get_volume()
            self._vol_slider.set_value(vol["percent"])
            self._vol_label.set_text(f"{vol['percent']}%")

        def _on_vol_changed(self, slider):
            pct = int(slider.get_value())
            self._vol_label.set_text(f"{pct}%")
            set_volume(pct)

        def _on_bright_changed(self, slider):
            pct = int(slider.get_value())
            self._bright_label.set_text(f"{pct}%")
            set_brightness(pct)

        def _on_power_mode(self, _btn, mode_name: str):
            try:
                self._client.send({"type": "power_set", "mode": mode_name})
            except Exception as e:
                logger.debug(f"power_set error: {e}")
            for m_name, btn in self._power_pills.items():
                if m_name == mode_name:
                    btn.remove_css_class("luminos-btn")
                    btn.add_css_class("luminos-btn-accent")
                else:
                    btn.remove_css_class("luminos-btn-accent")
                    btn.add_css_class("luminos-btn")

        def _on_wifi_expand(self, *_):
            visible = not self._wifi_panel.get_visible()
            self._wifi_panel.set_visible(visible)
            self._wifi_expand_btn.set_label(
                "▼ WiFi Networks" if visible else "▶ WiFi Networks"
            )
            if visible:
                self._wifi_panel.refresh()

        def _on_bt_expand(self, *_):
            visible = not self._bt_panel.get_visible()
            self._bt_panel.set_visible(visible)
            self._bt_expand_btn.set_label(
                "▼ Bluetooth Devices" if visible else "▶ Bluetooth Devices"
            )
            if visible:
                self._bt_panel.refresh()

        def _on_open_settings(self, *_):
            """Launch the full Luminos Settings app."""
            self.hide()
            try:
                from gui.settings import launch_settings
                launch_settings()
            except Exception as e:
                logger.debug(f"Settings launch error: {e}")

        # -------------------------------------------------------------------
        # Show / hide
        # -------------------------------------------------------------------

        def show_panel(self):
            """Refresh data and present the panel."""
            self._refresh()
            self.present()

        def toggle(self):
            """Show if hidden, hide if visible."""
            if self.get_visible():
                self.hide()
            else:
                self.show_panel()

        def _on_active_changed(self, window, _param):
            """Hide when the window loses focus."""
            if not window.is_active():
                self.hide()
