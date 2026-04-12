"""
src/gui/quick_settings/quick_panel.py
QuickSettingsPanel — dropdown from top bar right tray.

Visual spec (Phase 5.6):
  Width: 320px, top right, aligned to bar right edge
  Background: glass_bg(0.9) with blur(20px)
  Border: 1px BORDER, RADIUS_DEFAULT bottom corners only
  Shadow: 0px 8px 24px rgba(0,0,0,0.4)
  Animation: slides down from top bar edge, 200ms ease

Sections:
  1. User row (avatar initials + username + "Luminos OS")
  2. Divider
  3. Connectivity row (WiFi + Bluetooth toggle cards)
  4. Brightness + Volume sliders
  5. Divider
  6. Status row (battery, power mode, GPU)
  7. Divider
  8. Toggles (Do Not Disturb, Night Light)
  9. Settings button

Pure helpers:
  get_greeting(hour) → str
  get_power_mode_label(status) → str
  build_ai_summary(status) → str
  get_username() → str

Closes on: click outside (focus loss), Escape key.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.quick_settings.panel")

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
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    COLOR_SUCCESS,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION, FONT_LABEL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6,
    RADIUS_DEFAULT, RADIUS_MD, RADIUS_FULL,
    BAR_HEIGHT,
    SHADOW_PANEL,
    glass_bg,
)
from gui.common.socket_client import DaemonClient
from gui.common.subprocess_helpers import (
    get_bluetooth_powered, get_volume, set_volume, toggle_mute,
    get_wifi_info,
)
from gui.quick_settings.brightness_ctrl import get_brightness, set_brightness


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

    model = status.get("active_model") or "none"
    quant = status.get("quantization", "")
    gaming = status.get("gaming_mode", False)
    idle_s = status.get("seconds_since_last_use")

    parts = [f"Model: {model}" + (f"-{quant}" if quant else "")]
    if gaming:
        parts.append("Mode: Gaming (AI paused)")
    elif idle_s is not None:
        parts.append(f"Idle: {idle_s}s")

    return "\n".join(parts)


def get_username() -> str:
    """Return the current user's display name or login name."""
    # Try GECOS field first
    try:
        import pwd
        pw = pwd.getpwuid(os.getuid())
        gecos = pw.pw_gecos.split(",")[0]
        if gecos:
            return gecos
        return pw.pw_name
    except Exception:
        return os.environ.get("USER", "User")


def get_battery_status_text() -> str:
    """Return battery status string for the status row."""
    try:
        from hardware.battery_monitor import read_battery_level, read_battery_status
        level = read_battery_level()
        status = read_battery_status()
        if level is None:
            return "No battery"
        if status in ("Charging", "Full"):
            return f"{level}% — Charging"
        return f"{level}%"
    except Exception:
        return "Unknown"


def get_power_mode_text() -> str:
    """Return current power mode description for the status row."""
    try:
        from hardware.asus_controller import AsusController
        asus = AsusController()
        if asus.is_plugged_in():
            return "Performance Mode"
        return "Battery Mode"
    except Exception:
        return "Unknown"


# ===========================================================================
# CSS — all values from luminos_theme
# ===========================================================================

_QS_WIDTH = 300

_QS_CSS = f"""
window {{
    background: transparent;
}}

.luminos-qs {{
    background: {glass_bg(0.25)};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_DEFAULT}px;
    box-shadow: {SHADOW_PANEL};
}}

/* ── User row ── */
.luminos-qs-avatar {{
    min-width: 36px;
    min-height: 36px;
    border-radius: {RADIUS_FULL}px;
    background-color: rgba(0,128,255,0.18);
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 700;
    color: {ACCENT};
}}

.luminos-qs-username {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

.luminos-qs-subtitle {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
}}

/* ── Section label ── */
.luminos-qs-section-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: {TEXT_DISABLED};
}}

/* ── Toggle cards (wifi / bt) ── */
.luminos-qs-toggle-card {{
    background-color: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADIUS_MD}px;
    min-height: 52px;
    padding: 0 {SPACE_3}px;
}}

.luminos-qs-toggle-card:hover {{
    background-color: rgba(255,255,255,0.09);
    border-color: rgba(255,255,255,0.14);
}}

.luminos-qs-toggle-card-active {{
    background-color: rgba(0,128,255,0.18);
    border-color: rgba(0,128,255,0.35);
}}

.luminos-qs-toggle-card-active:hover {{
    background-color: rgba(0,128,255,0.24);
}}

.luminos-qs-toggle-label {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
}}

.luminos-qs-toggle-state {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
}}

/* ── Sliders ── */
.luminos-qs-slider-row {{
    background-color: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADIUS_MD}px;
    padding: {SPACE_2}px {SPACE_3}px;
}}

.luminos-qs-slider-icon {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 13px;
    color: {TEXT_SECONDARY};
    min-width: 20px;
}}

.luminos-qs-slider-value {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
    min-width: 30px;
}}

scale trough {{
    background-color: rgba(255,255,255,0.12);
    border-radius: 4px;
    min-height: 4px;
}}

scale trough highlight {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

scale slider {{
    background-color: white;
    border-radius: {RADIUS_FULL}px;
    min-width: 14px;
    min-height: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4);
}}

/* ── Status chips ── */
.luminos-qs-chip {{
    background-color: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADIUS_FULL}px;
    padding: 3px {SPACE_3}px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
}}

/* ── Pill toggles (DND / Night light) ── */
.luminos-qs-pill-toggle {{
    background-color: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADIUS_FULL}px;
    padding: {SPACE_2}px {SPACE_4}px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
}}

.luminos-qs-pill-toggle:hover {{
    background-color: rgba(255,255,255,0.09);
}}

.luminos-qs-pill-toggle-active {{
    background-color: rgba(0,128,255,0.18);
    border-color: rgba(0,128,255,0.35);
    color: {ACCENT};
}}

/* ── Settings button ── */
.luminos-qs-power-btn {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    font-weight: 500;
    color: {TEXT_SECONDARY};
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADIUS_MD}px;
    min-height: 36px;
    padding: 0 {SPACE_3}px;
}}

.luminos-qs-power-btn:hover {{
    background-color: rgba(255,255,255,0.10);
    color: {TEXT_PRIMARY};
}}

.luminos-qs-power-btn-danger:hover {{
    background-color: rgba(220,50,50,0.18);
    border-color: rgba(220,50,50,0.35);
    color: #FF5555;
}}

.luminos-qs-divider {{
    background-color: rgba(255,255,255,0.07);
    min-height: 1px;
}}
"""


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.quick_settings.wifi_panel import WiFiPanel
    from gui.quick_settings.bt_panel import BluetoothPanel, set_bt_power

    class QuickSettingsPanel(Gtk.Window):
        """
        Quick Settings dropdown panel.

        Created once; hidden after focus loss or Escape; re-shown via show_panel().
        """

        def __init__(self, daemon_client: "DaemonClient | None" = None):
            super().__init__()
            self._client = daemon_client or DaemonClient()

            self.set_title("luminos-quick-settings")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(_QS_WIDTH, -1)

            # Layer shell — pin to top-right, just below the bar.
            # This makes the panel a proper Wayland surface so pointer
            # events work correctly and the panel doesn't vanish when
            # the mouse moves away from the bar button.
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_namespace(self, "luminos-quick-settings")
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
                LayerShell.set_margin(self, LayerShell.Edge.TOP, 3)
                LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 3)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.ON_DEMAND
                )

            # Apply CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_QS_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())
            self.connect("notify::is-active", self._on_active_changed)

            self.add_css_class("luminos-qs")

            # Escape key closes
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key_pressed)
            self.add_controller(key_ctrl)

            # State
            self._wifi_on = True
            self._bt_on = False
            self._dnd_on = False
            self._night_light_on = False

            self._build()

        def _ensure_css(self):
            try:
                Gtk.StyleContext.add_provider_for_display(
                    self.get_display(), self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception:
                pass

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
            scroll.set_max_content_height(560)
            scroll.set_propagate_natural_height(True)
            self.set_child(scroll)

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_3)
            root.set_margin_top(SPACE_4)
            root.set_margin_bottom(SPACE_4)
            root.set_margin_start(SPACE_4)
            root.set_margin_end(SPACE_4)
            scroll.set_child(root)

            # User row
            self._build_user_row(root)
            root.append(self._make_divider())

            # Connectivity
            self._build_section_title(root, "Connectivity")
            self._build_connectivity_row(root)

            # Sliders
            self._build_section_title(root, "Controls")
            self._build_sliders(root)

            root.append(self._make_divider())

            # Status chips
            self._build_section_title(root, "Status")
            self._build_status_row(root)

            root.append(self._make_divider())

            # Toggle pills
            self._build_toggles(root)

            root.append(self._make_divider())

            # Power row
            self._build_power_row(root)

        def _build_section_title(self, root, text: str):
            lbl = Gtk.Label(label=text.upper())
            lbl.add_css_class("luminos-qs-section-title")
            lbl.set_halign(Gtk.Align.START)
            root.append(lbl)

        def _make_divider(self) -> Gtk.Box:
            div = Gtk.Box()
            div.add_css_class("luminos-qs-divider")
            div.set_margin_top(SPACE_3)
            div.set_margin_bottom(SPACE_3)
            return div

        # -------------------------------------------------------------------
        # Section 1: User row
        # -------------------------------------------------------------------

        def _build_user_row(self, root):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            row.add_css_class("luminos-qs-user-row")
            row.set_valign(Gtk.Align.CENTER)

            # Avatar circle with initials
            name = get_username()
            initials = "".join(w[0].upper() for w in name.split()[:2]) if name else "U"
            avatar = Gtk.Label(label=initials)
            avatar.add_css_class("luminos-qs-avatar")
            avatar.set_halign(Gtk.Align.CENTER)
            avatar.set_valign(Gtk.Align.CENTER)
            row.append(avatar)

            # Name + "Luminos OS"
            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self._username_label = Gtk.Label(label=name)
            self._username_label.add_css_class("luminos-qs-username")
            self._username_label.set_halign(Gtk.Align.START)
            text_box.append(self._username_label)

            os_label = Gtk.Label(label="Luminos OS")
            os_label.add_css_class("luminos-qs-subtitle")
            os_label.set_halign(Gtk.Align.START)
            text_box.append(os_label)

            row.append(text_box)
            root.append(row)

        # -------------------------------------------------------------------
        # Section 2: Connectivity toggle cards
        # -------------------------------------------------------------------

        def _build_connectivity_row(self, root):
            grid = Gtk.Grid()
            grid.set_row_spacing(SPACE_2)
            grid.set_column_spacing(SPACE_2)
            grid.set_hexpand(True)
            grid.set_margin_top(SPACE_2)

            self._wifi_card = self._make_toggle_card(
                "WiFi", "Connected", self._wifi_on
            )
            self._wifi_card.connect("clicked", self._on_wifi_toggle)

            self._bt_card = self._make_toggle_card(
                "Bluetooth", "Off", self._bt_on
            )
            self._bt_card.connect("clicked", self._on_bt_toggle)

            grid.attach(self._wifi_card, 0, 0, 1, 1)
            grid.attach(self._bt_card, 1, 0, 1, 1)
            root.append(grid)

        def _make_toggle_card(self, label: str, state: str,
                              active: bool) -> Gtk.Button:
            btn = Gtk.Button()
            btn.set_hexpand(True)

            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            box.set_halign(Gtk.Align.START)

            lbl = Gtk.Label(label=label)
            lbl.add_css_class("luminos-qs-toggle-label")
            lbl.set_halign(Gtk.Align.START)
            box.append(lbl)

            state_lbl = Gtk.Label(label=state)
            state_lbl.add_css_class("luminos-qs-toggle-state")
            state_lbl.set_halign(Gtk.Align.START)
            box.append(state_lbl)

            btn.set_child(box)
            btn.add_css_class("luminos-qs-toggle-card")
            if active:
                btn.add_css_class("luminos-qs-toggle-card-active")

            # Store references for updates
            btn._toggle_label = lbl
            btn._toggle_state = state_lbl

            return btn

        # -------------------------------------------------------------------
        # Section 3: Sliders (brightness + volume)
        # -------------------------------------------------------------------

        def _make_slider_row(self, icon: str, low: float, high: float) -> tuple:
            """Return (row_widget, slider, value_label)."""
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2)
            row.add_css_class("luminos-qs-slider-row")
            row.set_hexpand(True)

            icon_lbl = Gtk.Label(label=icon)
            icon_lbl.add_css_class("luminos-qs-slider-icon")
            row.append(icon_lbl)

            slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, 1)
            slider.set_hexpand(True)
            slider.set_draw_value(False)
            row.append(slider)

            val_lbl = Gtk.Label(label="--")
            val_lbl.add_css_class("luminos-qs-slider-value")
            row.append(val_lbl)

            return row, slider, val_lbl

        def _build_sliders(self, root):
            bright_row, self._bright_slider, self._bright_label = \
                self._make_slider_row("☀", 5, 100)
            self._bright_slider.connect("value-changed", self._on_bright_changed)
            root.append(bright_row)

            vol_row, self._vol_slider, self._vol_label = \
                self._make_slider_row("♪", 0, 100)
            self._vol_slider.connect("value-changed", self._on_vol_changed)
            root.append(vol_row)

        # -------------------------------------------------------------------
        # Section 4: Status row (battery, power mode, GPU)
        # -------------------------------------------------------------------

        def _build_status_row(self, root):
            chip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2)
            chip_row.set_hexpand(True)

            self._battery_status = Gtk.Label(label="🔋 --%")
            self._battery_status.add_css_class("luminos-qs-chip")
            chip_row.append(self._battery_status)

            self._power_mode_label = Gtk.Label(label="⚡ --")
            self._power_mode_label.add_css_class("luminos-qs-chip")
            chip_row.append(self._power_mode_label)

            gpu_chip = Gtk.Label(label="GPU Hybrid")
            gpu_chip.add_css_class("luminos-qs-chip")
            chip_row.append(gpu_chip)

            root.append(chip_row)

        # -------------------------------------------------------------------
        # Section 5: Toggle pills (DND, Night Light)
        # -------------------------------------------------------------------

        def _build_toggles(self, root):
            toggle_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2
            )
            toggle_row.set_margin_top(SPACE_2)

            self._dnd_pill = Gtk.Button(label="Do Not Disturb")
            self._dnd_pill.add_css_class("luminos-qs-pill-toggle")
            self._dnd_pill.connect("clicked", self._on_dnd_toggle)
            toggle_row.append(self._dnd_pill)

            self._night_pill = Gtk.Button(label="Night Light")
            self._night_pill.add_css_class("luminos-qs-pill-toggle")
            self._night_pill.connect("clicked", self._on_night_toggle)
            toggle_row.append(self._night_pill)

            root.append(toggle_row)

        # -------------------------------------------------------------------
        # Refresh — called on show
        # -------------------------------------------------------------------

        def _refresh(self):
            """Pull fresh data from system and update all widgets."""
            # Volume
            try:
                vol = get_volume()
                self._vol_slider.set_value(vol["percent"])
                self._vol_label.set_text(f"{vol['percent']}%")
            except Exception:
                pass

            # Brightness
            try:
                bright = get_brightness()
                if bright.get("available"):
                    self._bright_slider.set_sensitive(True)
                    self._bright_slider.set_value(bright["percent"])
                    self._bright_label.set_text(f"{bright['percent']}%")
                else:
                    self._bright_slider.set_sensitive(False)
                    self._bright_label.set_text("N/A")
            except Exception:
                pass

            # WiFi state
            try:
                wifi = get_wifi_info()
                if wifi.get("connected"):
                    self._wifi_card._toggle_state.set_text(
                        wifi.get("ssid", "Connected")
                    )
                    self._wifi_card.add_css_class("luminos-qs-toggle-card-active")
                    self._wifi_on = True
                else:
                    self._wifi_card._toggle_state.set_text("Off")
                    self._wifi_card.remove_css_class("luminos-qs-toggle-card-active")
                    self._wifi_on = False
            except Exception:
                pass

            # Bluetooth state
            try:
                self._bt_on = get_bluetooth_powered()
                self._bt_card._toggle_state.set_text("On" if self._bt_on else "Off")
                if self._bt_on:
                    self._bt_card.add_css_class("luminos-qs-toggle-card-active")
                else:
                    self._bt_card.remove_css_class("luminos-qs-toggle-card-active")
            except Exception:
                pass

            # Battery status
            self._battery_status.set_text(f"🔋 {get_battery_status_text()}")

            # Power mode
            self._power_mode_label.set_text(f"⚡ {get_power_mode_text()}")

        # -------------------------------------------------------------------
        # Toggle handlers
        # -------------------------------------------------------------------

        def _on_wifi_toggle(self, *_):
            """Toggle WiFi on/off via nmcli."""
            try:
                if self._wifi_on:
                    subprocess.run(
                        ["nmcli", "radio", "wifi", "off"],
                        capture_output=True, timeout=5,
                    )
                else:
                    subprocess.run(
                        ["nmcli", "radio", "wifi", "on"],
                        capture_output=True, timeout=5,
                    )
                self._wifi_on = not self._wifi_on
                state = "On" if self._wifi_on else "Off"
                self._wifi_card._toggle_state.set_text(state)
                if self._wifi_on:
                    self._wifi_card.add_css_class("luminos-qs-toggle-card-active")
                else:
                    self._wifi_card.remove_css_class("luminos-qs-toggle-card-active")
            except Exception as e:
                logger.debug(f"WiFi toggle error: {e}")

        def _on_bt_toggle(self, *_):
            try:
                set_bt_power(not self._bt_on)
                self._bt_on = not self._bt_on
                state = "On" if self._bt_on else "Off"
                self._bt_card._toggle_state.set_text(state)
                if self._bt_on:
                    self._bt_card.add_css_class("luminos-qs-toggle-card-active")
                else:
                    self._bt_card.remove_css_class("luminos-qs-toggle-card-active")
            except Exception as e:
                logger.debug(f"BT toggle error: {e}")

        def _on_mute_toggle(self):
            toggle_mute()
            try:
                vol = get_volume()
                self._vol_slider.set_value(vol["percent"])
                self._vol_label.set_text(f"{vol['percent']}%")
            except Exception:
                pass

        def _on_vol_changed(self, slider):
            pct = int(slider.get_value())
            self._vol_label.set_text(f"{pct}%")
            set_volume(pct)

        def _on_bright_changed(self, slider):
            pct = int(slider.get_value())
            self._bright_label.set_text(f"{pct}%")
            set_brightness(pct)

        def _on_dnd_toggle(self, *_):
            self._dnd_on = not self._dnd_on
            if self._dnd_on:
                self._dnd_pill.add_css_class("luminos-qs-pill-toggle-active")
            else:
                self._dnd_pill.remove_css_class("luminos-qs-pill-toggle-active")

        def _on_night_toggle(self, *_):
            self._night_light_on = not self._night_light_on
            if self._night_light_on:
                self._night_pill.add_css_class("luminos-qs-pill-toggle-active")
                # Apply night light via hyprctl
                try:
                    subprocess.run(
                        ["hyprctl", "keyword", "decoration:screen_shader",
                         "/usr/share/luminos/shaders/nightlight.glsl"],
                        capture_output=True, timeout=3,
                    )
                except Exception:
                    pass
            else:
                self._night_pill.remove_css_class("luminos-qs-pill-toggle-active")
                try:
                    subprocess.run(
                        ["hyprctl", "keyword", "decoration:screen_shader", ""],
                        capture_output=True, timeout=3,
                    )
                except Exception:
                    pass

        # -------------------------------------------------------------------
        # Section 6: Power row
        # -------------------------------------------------------------------

        def _build_power_row(self, root):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2)
            row.set_hexpand(True)

            actions = [
                ("⏾  Sleep",     self._on_sleep,    False),
                ("↩  Logout",    self._on_logout,   False),
                ("↺  Reboot",    self._on_reboot,   True),
                ("⏻  Power off", self._on_poweroff, True),
            ]
            for label, handler, danger in actions:
                btn = Gtk.Button(label=label)
                btn.add_css_class("luminos-qs-power-btn")
                if danger:
                    btn.add_css_class("luminos-qs-power-btn-danger")
                btn.set_hexpand(True)
                btn.connect("clicked", handler)
                row.append(btn)

            root.append(row)

        def _on_sleep(self, *_):
            self.hide()
            subprocess.run(["systemctl", "suspend"], check=False)

        def _on_logout(self, *_):
            self.hide()
            try:
                hypr_dir = f"/run/user/{os.getuid()}/hypr"
                sig = next(iter(os.listdir(hypr_dir)), "")
                env = {**os.environ, "HYPRLAND_INSTANCE_SIGNATURE": sig}
                subprocess.run(
                    ["hyprctl", "dispatch", "exit"], env=env, check=False
                )
            except Exception as e:
                logger.debug(f"Logout error: {e}")

        def _on_reboot(self, *_):
            self.hide()
            subprocess.run(["systemctl", "reboot"], check=False)

        def _on_poweroff(self, *_):
            self.hide()
            subprocess.run(["systemctl", "poweroff"], check=False)

        # -------------------------------------------------------------------
        # Show / hide / keyboard
        # -------------------------------------------------------------------

        def show_panel(self):
            """Refresh data and present the panel."""
            self._refresh()
            self._just_shown = True
            GLib.timeout_add(400, self._clear_just_shown)
            self.present()

        def _clear_just_shown(self):
            self._just_shown = False
            return False

        def toggle(self):
            if self.get_visible():
                self.hide()
            else:
                self.show_panel()

        def _on_active_changed(self, window, _param):
            if not window.is_active() and not getattr(self, "_just_shown", False):
                self.hide()

        def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
            if keyval == Gdk.KEY_Escape:
                self.hide()
                return True
            return False
