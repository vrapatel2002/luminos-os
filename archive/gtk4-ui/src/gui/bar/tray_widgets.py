"""
src/gui/bar/tray_widgets.py
Right-side tray indicator widgets for the Luminos top bar.

Architecture:
- Each widget class has static logic methods (_get_state, _get_icon, _get_color)
  that are pure functions taking data dicts → testable without a display.
- GTK widget classes call those static methods from update().
- All GTK code guarded behind the gi import so the logic layer
  can be imported in headless test environments.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.bar.tray")

# ---------------------------------------------------------------------------
# GTK import (guarded — tests import only the logic functions)
# ---------------------------------------------------------------------------
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

# Ensure src/ is on path for theme imports
_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.colors import get_colors
from gui.common.subprocess_helpers import (
    get_wifi_info, get_bluetooth_powered, get_volume,
    set_volume, toggle_mute, run_cmd,
)


# ===========================================================================
# Pure logic functions — testable without GTK or display
# ===========================================================================

# ---------------------------------------------------------------------------
# AI Indicator logic
# ---------------------------------------------------------------------------

def get_ai_state(status: dict) -> str:
    """
    Map a daemon manager_status response → AI state string.

    States: "offline" | "gaming" | "active" | "idle"
    """
    if status.get("available") is False or "error" in status:
        return "offline"
    if status.get("gaming_mode", False):
        return "gaming"
    if status.get("active_model"):
        return "active"
    return "idle"


def get_ai_label(status: dict) -> str:
    """Return display label for the AI state."""
    state = get_ai_state(status)
    if state == "offline":
        return "⚠"
    if state == "gaming":
        return "🎮"
    if state == "active":
        model = status.get("active_model", "")
        quant = status.get("quantization", "")
        suffix = f"-{quant}" if quant else ""
        return f"🤖 {model}{suffix}"
    return "💤"


# ---------------------------------------------------------------------------
# Power Indicator logic
# ---------------------------------------------------------------------------

def get_power_mode_label(status: dict) -> str:
    """Return the short mode name from a power_status response."""
    return status.get("mode", "auto")


_POWER_MODE_COLORS = {
    "auto":     "accent_blue",
    "quiet":    "text_secondary",
    "balanced": "success",
    "max":      "warning",
}


def get_power_mode_color_key(mode: str) -> str:
    """Return the theme color key for a power mode."""
    return _POWER_MODE_COLORS.get(mode, "text_secondary")


# ---------------------------------------------------------------------------
# Battery Indicator logic
# ---------------------------------------------------------------------------

_BATTERY_ICONS = [
    (90, "🔋"),   # full
    (70, "🔋"),   # high
    (50, "🔋"),   # medium
    (30, "🪫"),   # low
    (15, "🪫"),   # warning
    (0,  "🪫"),   # critical
]

_BATTERY_CHARGING_ICON = "⚡🔋"


def get_battery_icon(percent: int | None, charging: bool = False) -> str:
    """Return battery icon character for the given percentage."""
    if charging:
        return _BATTERY_CHARGING_ICON
    if percent is None:
        return "🔋"
    for threshold, icon in _BATTERY_ICONS:
        if percent >= threshold:
            return icon
    return "🪫"


def get_battery_color(percent: int | None, dark: bool = True) -> str:
    """Return CSS color string for the battery level."""
    colors = get_colors(dark)
    if percent is None or percent >= 20:
        return colors["text_primary"]
    if percent >= 10:
        return colors["warning"]
    return colors["error"]


# ---------------------------------------------------------------------------
# WiFi Indicator logic
# ---------------------------------------------------------------------------

def get_wifi_icon(info: dict) -> str:
    """Return wifi icon based on connection info."""
    if not info.get("connected", False):
        return "📵"
    signal = info.get("signal", 0) or 0
    if signal >= 70:
        return "📶"
    if signal >= 40:
        return "📶"   # same icon, colour differs
    return "📶"


def get_wifi_color_key(info: dict) -> str:
    """Return theme color key for wifi signal strength."""
    if not info.get("connected", False):
        return "text_disabled"
    signal = info.get("signal", 0) or 0
    if signal >= 70:
        return "text_primary"
    if signal >= 40:
        return "warning"
    return "error"


# ---------------------------------------------------------------------------
# Volume Indicator logic
# ---------------------------------------------------------------------------

def get_volume_icon(vol: dict) -> str:
    """Return volume icon based on percent and mute state."""
    if vol.get("muted", False) or vol.get("percent", 0) == 0:
        return "🔇"
    p = vol.get("percent", 50)
    if p >= 60:
        return "🔊"
    if p >= 20:
        return "🔉"
    return "🔈"


# ===========================================================================
# GTK Widget classes (require display to instantiate)
# ===========================================================================

if _GTK_AVAILABLE:

    class AIIndicator(Gtk.Box):
        """AI status tray indicator."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            self.add_css_class("luminos-ai-status")
            self._label = Gtk.Label(label="💤")
            self.append(self._label)
            btn = Gtk.GestureClick()
            btn.connect("pressed", self._on_click)
            self.add_controller(btn)

        @staticmethod
        def _get_state(status: dict) -> str:
            return get_ai_state(status)

        def update(self, status: dict):
            self._label.set_text(get_ai_label(status))

        def _on_click(self, *_):
            pass  # Phase 8.3 — quick settings panel

    class PowerIndicator(Gtk.Box):
        """Power mode tray indicator — pill label, click cycles modes."""

        _MODES = ["auto", "quiet", "balanced", "max"]

        def __init__(self, daemon_client=None):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            self._client = daemon_client
            self._label  = Gtk.Label(label="auto")
            self._label.add_css_class("luminos-power-mode")
            self.append(self._label)
            btn = Gtk.GestureClick()
            btn.connect("pressed", self._on_click)
            self.add_controller(btn)

        @staticmethod
        def _get_mode_label(status: dict) -> str:
            return get_power_mode_label(status)

        def update(self, status: dict):
            mode = get_power_mode_label(status)
            self._label.set_text(mode)

        def _on_click(self, *_):
            if not self._client:
                return
            current = self._label.get_text()
            idx  = self._MODES.index(current) if current in self._MODES else 0
            next_mode = self._MODES[(idx + 1) % len(self._MODES)]
            self._client.send({"type": "power_set", "mode": next_mode})
            self._label.set_text(next_mode)

    class BatteryIndicator(Gtk.Box):
        """Battery percentage + icon tray indicator."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            self._icon  = Gtk.Label(label="🔋")
            self._label = Gtk.Label(label="--")
            self.append(self._icon)
            self.append(self._label)

        @staticmethod
        def _get_icon(percent: int | None, charging: bool = False) -> str:
            return get_battery_icon(percent, charging)

        @staticmethod
        def _get_color(percent: int | None, dark: bool = True) -> str:
            return get_battery_color(percent, dark)

        def update(self, ac_status: dict):
            pct      = ac_status.get("battery_percent")
            charging = ac_status.get("battery_status", "") in ("Charging", "Full")
            icon     = get_battery_icon(pct, charging)
            self._icon.set_text(icon)
            self._label.set_text(f"{pct}%" if pct is not None else "--")

    class WiFiIndicator(Gtk.Box):
        """WiFi signal tray indicator."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            self._label = Gtk.Label(label="📵")
            self.append(self._label)
            btn = Gtk.GestureClick()
            btn.connect("pressed", self._on_click)
            self.add_controller(btn)

        def update(self):
            info = get_wifi_info()
            self._label.set_text(get_wifi_icon(info))

        def _on_click(self, *_):
            pass  # Phase 8.3

    class BluetoothIndicator(Gtk.Box):
        """Bluetooth power tray indicator."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            self._label = Gtk.Label(label="🔵")
            self.append(self._label)
            btn = Gtk.GestureClick()
            btn.connect("pressed", self._on_click)
            self.add_controller(btn)

        def update(self):
            powered = get_bluetooth_powered()
            self._label.set_text("🔵" if powered else "⬛")

        def _on_click(self, *_):
            pass  # Phase 8.3

    class VolumeIndicator(Gtk.Box):
        """Volume icon + percent tray indicator with scroll-to-adjust."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            self._icon  = Gtk.Label(label="🔊")
            self._label = Gtk.Label(label="--")
            self.append(self._icon)
            self.append(self._label)

            click = Gtk.GestureClick()
            click.connect("pressed", self._on_click)
            self.add_controller(click)

            scroll = Gtk.EventControllerScroll(
                flags=Gtk.EventControllerScrollFlags.VERTICAL
            )
            scroll.connect("scroll", self._on_scroll)
            self.add_controller(scroll)

        def update(self):
            vol = get_volume()
            self._icon.set_text(get_volume_icon(vol))
            self._label.set_text(f"{vol['percent']}%")

        def _on_click(self, *_):
            toggle_mute()
            self.update()

        def _on_scroll(self, _ctrl, _dx, dy):
            vol = get_volume()
            new_pct = max(0, min(100, vol["percent"] - int(dy * 5)))
            set_volume(new_pct)
            self.update()
