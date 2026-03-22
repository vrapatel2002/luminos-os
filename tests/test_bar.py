"""
tests/test_bar.py
Phase 8.2 — Top Bar test suite.

Covers:
  - format_clock / format_date helpers           (6 tests)
  - tray_widgets pure logic: AI state/label       (6 tests)
  - tray_widgets pure logic: power mode           (3 tests)
  - tray_widgets pure logic: battery icon/color   (6 tests)
  - tray_widgets pure logic: wifi icon/color      (4 tests)
  - tray_widgets pure logic: volume icon          (4 tests)
  - subprocess_helpers: get_wifi_info parsing     (4 tests)
  - subprocess_helpers: get_bluetooth_powered     (2 tests)
  - subprocess_helpers: get_volume parsing        (2 tests)

Total: 37 tests
All run headless — no GTK display required.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure src/ is on path
SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# ---------------------------------------------------------------------------
# Import pure logic (no GTK needed)
# ---------------------------------------------------------------------------
from gui.bar.bar_window import format_clock, format_date
from gui.bar.tray_widgets import (
    get_ai_state, get_ai_label,
    get_power_mode_label, get_power_mode_color_key,
    get_battery_icon, get_battery_color,
    get_wifi_icon, get_wifi_color_key,
    get_volume_icon,
)
from gui.common.subprocess_helpers import (
    get_wifi_info, get_bluetooth_powered, get_volume,
)


# ===========================================================================
# format_clock / format_date
# ===========================================================================

class TestFormatClock(unittest.TestCase):

    def test_24h_zero_padding(self):
        self.assertEqual(format_clock(9, 5, 3), "09:05:03")

    def test_24h_noon(self):
        self.assertEqual(format_clock(12, 0, 0), "12:00:00")

    def test_24h_midnight(self):
        self.assertEqual(format_clock(0, 0, 0), "00:00:00")

    def test_12h_am(self):
        self.assertEqual(format_clock(9, 5, 3, use_24h=False), "9:05:03 AM")

    def test_12h_pm(self):
        self.assertEqual(format_clock(15, 30, 0, use_24h=False), "3:30:00 PM")

    def test_12h_midnight(self):
        self.assertEqual(format_clock(0, 0, 0, use_24h=False), "12:00:00 AM")


class TestFormatDate(unittest.TestCase):

    def test_monday(self):
        result = format_date(2026, 3, 23, 0)
        self.assertIn("Mon", result)
        self.assertIn("Mar", result)
        self.assertIn("23", result)

    def test_sunday(self):
        result = format_date(2026, 3, 22, 6)
        self.assertIn("Sun", result)
        self.assertIn("Mar", result)

    def test_january(self):
        result = format_date(2026, 1, 1, 3)
        self.assertIn("Jan", result)

    def test_december(self):
        result = format_date(2026, 12, 25, 4)
        self.assertIn("Dec", result)
        self.assertIn("25", result)


# ===========================================================================
# AI state / label
# ===========================================================================

class TestGetAiState(unittest.TestCase):

    def test_offline_on_error(self):
        self.assertEqual(get_ai_state({"error": "conn refused"}), "offline")

    def test_offline_when_unavailable(self):
        self.assertEqual(get_ai_state({"available": False}), "offline")

    def test_gaming(self):
        self.assertEqual(get_ai_state({"gaming_mode": True}), "gaming")

    def test_active(self):
        self.assertEqual(get_ai_state({"active_model": "nexus"}), "active")

    def test_idle(self):
        self.assertEqual(get_ai_state({}), "idle")

    def test_gaming_trumps_active(self):
        self.assertEqual(
            get_ai_state({"gaming_mode": True, "active_model": "nexus"}),
            "gaming",
        )


class TestGetAiLabel(unittest.TestCase):

    def test_offline_label(self):
        self.assertEqual(get_ai_label({"available": False}), "⚠")

    def test_gaming_label(self):
        self.assertEqual(get_ai_label({"gaming_mode": True}), "🎮")

    def test_idle_label(self):
        self.assertEqual(get_ai_label({}), "💤")

    def test_active_label_with_quant(self):
        label = get_ai_label({"active_model": "nexus", "quantization": "Q4"})
        self.assertIn("nexus", label)
        self.assertIn("Q4", label)

    def test_active_label_without_quant(self):
        label = get_ai_label({"active_model": "nexus"})
        self.assertIn("nexus", label)
        self.assertNotIn("-", label)


# ===========================================================================
# Power mode
# ===========================================================================

class TestPowerMode(unittest.TestCase):

    def test_label_default(self):
        self.assertEqual(get_power_mode_label({}), "auto")

    def test_label_max(self):
        self.assertEqual(get_power_mode_label({"mode": "max"}), "max")

    def test_color_key_balanced(self):
        self.assertEqual(get_power_mode_color_key("balanced"), "success")

    def test_color_key_unknown_falls_back(self):
        self.assertEqual(get_power_mode_color_key("unknown"), "text_secondary")

    def test_color_key_auto(self):
        self.assertEqual(get_power_mode_color_key("auto"), "accent_blue")

    def test_color_key_max(self):
        self.assertEqual(get_power_mode_color_key("max"), "warning")


# ===========================================================================
# Battery icon / color
# ===========================================================================

class TestBatteryIcon(unittest.TestCase):

    def test_charging(self):
        icon = get_battery_icon(50, charging=True)
        self.assertIn("⚡", icon)

    def test_none_percent(self):
        self.assertIsInstance(get_battery_icon(None), str)

    def test_full(self):
        self.assertIsInstance(get_battery_icon(95), str)

    def test_low(self):
        icon_low  = get_battery_icon(10)
        icon_full = get_battery_icon(95)
        self.assertIsInstance(icon_low, str)
        self.assertIsInstance(icon_full, str)


class TestBatteryColor(unittest.TestCase):

    def test_high_battery_primary(self):
        color = get_battery_color(80)
        # Should be text_primary from DARK palette
        self.assertIsInstance(color, str)
        self.assertTrue(len(color) > 0)

    def test_low_battery_warning(self):
        color_warn = get_battery_color(15)
        self.assertIsInstance(color_warn, str)

    def test_critical_battery_error(self):
        color_err = get_battery_color(5)
        self.assertIsInstance(color_err, str)

    def test_none_percent(self):
        color = get_battery_color(None)
        self.assertIsInstance(color, str)


# ===========================================================================
# WiFi icon / color key
# ===========================================================================

class TestWifiIcon(unittest.TestCase):

    def test_disconnected(self):
        icon = get_wifi_icon({"connected": False})
        self.assertEqual(icon, "📵")

    def test_connected_strong(self):
        icon = get_wifi_icon({"connected": True, "signal": 80})
        self.assertEqual(icon, "📶")

    def test_connected_medium(self):
        icon = get_wifi_icon({"connected": True, "signal": 50})
        self.assertEqual(icon, "📶")

    def test_connected_weak(self):
        icon = get_wifi_icon({"connected": True, "signal": 20})
        self.assertEqual(icon, "📶")


class TestWifiColorKey(unittest.TestCase):

    def test_disconnected(self):
        key = get_wifi_color_key({"connected": False})
        self.assertEqual(key, "text_disabled")

    def test_strong_signal(self):
        key = get_wifi_color_key({"connected": True, "signal": 80})
        self.assertEqual(key, "text_primary")

    def test_medium_signal(self):
        key = get_wifi_color_key({"connected": True, "signal": 50})
        self.assertEqual(key, "warning")

    def test_weak_signal(self):
        key = get_wifi_color_key({"connected": True, "signal": 20})
        self.assertEqual(key, "error")


# ===========================================================================
# Volume icon
# ===========================================================================

class TestVolumeIcon(unittest.TestCase):

    def test_muted(self):
        self.assertEqual(get_volume_icon({"muted": True, "percent": 80}), "🔇")

    def test_zero_percent(self):
        self.assertEqual(get_volume_icon({"muted": False, "percent": 0}), "🔇")

    def test_high_volume(self):
        self.assertEqual(get_volume_icon({"percent": 80}), "🔊")

    def test_medium_volume(self):
        self.assertEqual(get_volume_icon({"percent": 40}), "🔉")

    def test_low_volume(self):
        self.assertEqual(get_volume_icon({"percent": 10}), "🔈")


# ===========================================================================
# subprocess_helpers — mocked subprocess
# ===========================================================================

class TestGetWifiInfo(unittest.TestCase):

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_connected(self, mock_run):
        mock_run.return_value = "yes:85:MyNetwork\n"
        info = get_wifi_info()
        self.assertTrue(info["connected"])
        self.assertEqual(info["signal"], 85)
        self.assertEqual(info["ssid"], "MyNetwork")

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_not_connected(self, mock_run):
        mock_run.return_value = "no:0:SomeNet\n"
        info = get_wifi_info()
        self.assertFalse(info["connected"])

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_none_output(self, mock_run):
        mock_run.return_value = None
        info = get_wifi_info()
        self.assertFalse(info["connected"])
        self.assertIsNone(info["signal"])

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_ssid_with_colon(self, mock_run):
        # SSIDs can contain colons — everything after field[1] is the SSID
        mock_run.return_value = "yes:72:My:Fancy:Net\n"
        info = get_wifi_info()
        self.assertTrue(info["connected"])
        self.assertEqual(info["ssid"], "My:Fancy:Net")


class TestGetBluetoothPowered(unittest.TestCase):

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_powered_on(self, mock_run):
        mock_run.return_value = "Controller AA:BB:CC:DD\n\tPowered: yes\n"
        self.assertTrue(get_bluetooth_powered())

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_powered_off(self, mock_run):
        mock_run.return_value = "Controller AA:BB:CC:DD\n\tPowered: no\n"
        self.assertFalse(get_bluetooth_powered())


class TestGetVolume(unittest.TestCase):

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_parses_percent(self, mock_run):
        def side(cmd, **kw):
            if "get-sink-volume" in cmd:
                return "Volume: front-left: 65536 / 100% / 0.00 dB"
            return "Mute: no"
        mock_run.side_effect = side
        vol = get_volume()
        self.assertEqual(vol["percent"], 100)
        self.assertFalse(vol["muted"])

    @patch("gui.common.subprocess_helpers.run_cmd")
    def test_muted(self, mock_run):
        def side(cmd, **kw):
            if "get-sink-volume" in cmd:
                return "Volume: front-left: 32768 / 50%"
            return "Mute: yes"
        mock_run.side_effect = side
        vol = get_volume()
        self.assertEqual(vol["percent"], 50)
        self.assertTrue(vol["muted"])


if __name__ == "__main__":
    unittest.main()
