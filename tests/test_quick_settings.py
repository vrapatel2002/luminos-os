"""
tests/test_quick_settings.py
Quick Settings Panel test suite.

Covers:
  - brightness_ctrl: get/set/up/down              (7 tests)
  - wifi_panel: get_networks, active, disconnect   (3 tests)
  - bt_panel: get_devices, set_power, toggle       (3 tests)
  - quick_panel pure logic: greeting, power, ai,
    username, battery status, power mode text      (12 tests)

Total: 25 tests
All run headless — no GTK display required.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import gui.quick_settings.brightness_ctrl as bctrl
from gui.quick_settings.brightness_ctrl import (
    get_brightness, set_brightness, brightness_up, brightness_down,
    _MIN_PERCENT,
)
from gui.quick_settings.wifi_panel import (
    get_wifi_networks, get_active_connection, disconnect_wifi,
)
from gui.quick_settings.bt_panel import (
    get_bt_devices, set_bt_power, toggle_bt_device,
)
from gui.quick_settings.quick_panel import (
    get_greeting, get_power_mode_label, build_ai_summary,
    get_username, get_battery_status_text, get_power_mode_text,
)


# ===========================================================================
# Backlight helpers
# ===========================================================================

def _make_fake_backlight(tmpdir: str, current: int, maximum: int) -> str:
    """Create fake sysfs backlight files in tmpdir. Returns path."""
    os.makedirs(tmpdir, exist_ok=True)
    with open(os.path.join(tmpdir, "brightness"), "w") as f:
        f.write(str(current))
    with open(os.path.join(tmpdir, "max_brightness"), "w") as f:
        f.write(str(maximum))
    return tmpdir


# ===========================================================================
# brightness_ctrl
# ===========================================================================

class TestGetBrightness(unittest.TestCase):

    def test_missing_path_returns_unavailable(self):
        with patch.object(bctrl, "BACKLIGHT_PATH", "/nonexistent/backlight/xyz"):
            result = get_brightness()
        self.assertFalse(result.get("available"))

    def test_returns_correct_shape(self):
        with tempfile.TemporaryDirectory() as d:
            _make_fake_backlight(d, 80, 100)
            with patch.object(bctrl, "BACKLIGHT_PATH", d):
                result = get_brightness()
        self.assertTrue(result.get("available"))
        self.assertIn("current",   result)
        self.assertIn("max",       result)
        self.assertIn("percent",   result)
        self.assertEqual(result["percent"], 80)


class TestSetBrightness(unittest.TestCase):

    def test_clamped_to_min_5(self):
        with tempfile.TemporaryDirectory() as d:
            _make_fake_backlight(d, 50, 100)
            with patch.object(bctrl, "BACKLIGHT_PATH", d):
                set_brightness(0)   # should write 5
                result = get_brightness()
        self.assertEqual(result["percent"], _MIN_PERCENT)

    def test_clamped_to_max_100(self):
        with tempfile.TemporaryDirectory() as d:
            _make_fake_backlight(d, 50, 100)
            with patch.object(bctrl, "BACKLIGHT_PATH", d):
                set_brightness(200)  # should write 100
                result = get_brightness()
        self.assertEqual(result["percent"], 100)


class TestBrightnessUpDown(unittest.TestCase):

    def test_brightness_up_increases_percent(self):
        with tempfile.TemporaryDirectory() as d:
            _make_fake_backlight(d, 50, 100)
            with patch.object(bctrl, "BACKLIGHT_PATH", d):
                before = get_brightness()["percent"]
                result = brightness_up(10)
        self.assertGreater(result["percent"], before)

    def test_brightness_down_decreases_percent(self):
        with tempfile.TemporaryDirectory() as d:
            _make_fake_backlight(d, 80, 100)
            with patch.object(bctrl, "BACKLIGHT_PATH", d):
                before = get_brightness()["percent"]
                result = brightness_down(10)
        self.assertLess(result["percent"], before)

    def test_brightness_down_at_min_stays_at_5(self):
        # Start at exactly 5% (min)
        with tempfile.TemporaryDirectory() as d:
            _make_fake_backlight(d, 5, 100)
            with patch.object(bctrl, "BACKLIGHT_PATH", d):
                result = brightness_down(10)
        self.assertEqual(result["percent"], _MIN_PERCENT)

    def test_brightness_up_unavailable_no_crash(self):
        with patch.object(bctrl, "BACKLIGHT_PATH", "/nonexistent"):
            result = brightness_up()
        self.assertFalse(result.get("available"))

    def test_brightness_down_unavailable_no_crash(self):
        with patch.object(bctrl, "BACKLIGHT_PATH", "/nonexistent"):
            result = brightness_down()
        self.assertFalse(result.get("available"))


# ===========================================================================
# wifi_panel
# ===========================================================================

class TestGetWifiNetworks(unittest.TestCase):

    @patch("gui.quick_settings.wifi_panel.run_cmd")
    def test_returns_list_no_crash(self, mock_run):
        mock_run.return_value = None
        result = get_wifi_networks()
        self.assertIsInstance(result, list)

    @patch("gui.quick_settings.wifi_panel.run_cmd")
    def test_parses_networks(self, mock_run):
        mock_run.return_value = (
            "HomeNet:85:WPA2:yes\n"
            "Neighbor:40:WPA2:no\n"
        )
        result = get_wifi_networks()
        self.assertEqual(len(result), 2)
        # sorted by signal desc
        self.assertEqual(result[0]["ssid"], "HomeNet")
        self.assertTrue(result[0]["active"])


class TestGetActiveConnection(unittest.TestCase):

    @patch("gui.quick_settings.wifi_panel.run_cmd")
    def test_returns_correct_shape(self, mock_run):
        mock_run.return_value = "yes:72:MySSID\n"
        result = get_active_connection()
        self.assertIn("connected", result)
        self.assertIn("ssid", result)
        self.assertIn("signal", result)
        self.assertTrue(result["connected"])
        self.assertEqual(result["ssid"], "MySSID")


class TestDisconnectWifi(unittest.TestCase):

    @patch("gui.quick_settings.wifi_panel.run_cmd")
    def test_returns_bool_no_crash(self, mock_run):
        mock_run.return_value = None
        result = disconnect_wifi()
        self.assertIsInstance(result, bool)


# ===========================================================================
# bt_panel
# ===========================================================================

class TestGetBtDevices(unittest.TestCase):

    @patch("gui.quick_settings.bt_panel.run_cmd")
    def test_returns_list_no_crash(self, mock_run):
        mock_run.return_value = None
        result = get_bt_devices()
        self.assertIsInstance(result, list)

    @patch("gui.quick_settings.bt_panel.run_cmd")
    def test_parses_devices(self, mock_run):
        def side(cmd, **kw):
            if "devices" in cmd:
                return "Device AA:BB:CC:DD:EE:FF Headphones\n"
            # info
            return (
                "Device AA:BB:CC:DD:EE:FF (public)\n"
                "\tName: Headphones\n"
                "\tConnected: yes\n"
                "\tBattery Percentage: 0x52 (82)\n"
            )
        mock_run.side_effect = side
        result = get_bt_devices()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Headphones")
        self.assertTrue(result[0]["connected"])
        self.assertEqual(result[0]["battery"], 82)


class TestSetBtPower(unittest.TestCase):

    @patch("gui.quick_settings.bt_panel.run_cmd")
    def test_returns_bool_no_crash(self, mock_run):
        mock_run.return_value = None
        result = set_bt_power(True)
        self.assertIsInstance(result, bool)


class TestToggleBtDevice(unittest.TestCase):

    @patch("gui.quick_settings.bt_panel.run_cmd")
    def test_offline_no_crash(self, mock_run):
        mock_run.return_value = None
        result = toggle_bt_device("AA:BB:CC:DD:EE:FF")
        self.assertIn("success", result)
        self.assertIn("connected", result)


# ===========================================================================
# quick_panel pure logic
# ===========================================================================

class TestGetGreeting(unittest.TestCase):

    def test_morning(self):
        self.assertEqual(get_greeting(8), "Good morning")

    def test_afternoon(self):
        self.assertEqual(get_greeting(14), "Good afternoon")

    def test_evening(self):
        self.assertEqual(get_greeting(20), "Good evening")

    def test_midnight_is_evening(self):
        self.assertEqual(get_greeting(0), "Good evening")

    def test_noon_is_afternoon(self):
        self.assertEqual(get_greeting(12), "Good afternoon")


class TestGetPowerModeLabel(unittest.TestCase):

    def test_with_mock_daemon(self):
        status = {"mode": "balanced", "governor": "schedutil"}
        result = get_power_mode_label(status)
        self.assertEqual(result, "balanced")

    def test_missing_mode_defaults_auto(self):
        self.assertEqual(get_power_mode_label({}), "auto")


class TestBuildAiSummary(unittest.TestCase):

    def test_offline_status(self):
        summary = build_ai_summary({"available": False})
        self.assertIn("offline", summary.lower())

    def test_error_key_shows_offline(self):
        summary = build_ai_summary({"error": "daemon not running"})
        self.assertIn("offline", summary.lower())

    def test_active_model_shown(self):
        summary = build_ai_summary({
            "active_model": "nexus",
            "quantization": "Q4",
            "gaming_mode": False,
        })
        self.assertIn("nexus", summary)
        self.assertIn("Q4", summary)

    def test_gaming_mode_shown(self):
        summary = build_ai_summary({
            "active_model": "nexus",
            "gaming_mode": True,
        })
        self.assertIn("Gaming", summary)

    def test_no_model_shows_none(self):
        summary = build_ai_summary({"active_model": None})
        self.assertIn("none", summary.lower())


class TestGetUsername(unittest.TestCase):

    def test_returns_string(self):
        result = get_username()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestGetBatteryStatusText(unittest.TestCase):

    @patch("hardware.battery_monitor.read_battery_level", return_value=75)
    @patch("hardware.battery_monitor.read_battery_status", return_value="Discharging")
    def test_discharging(self, _s, _l):
        result = get_battery_status_text()
        self.assertEqual(result, "75%")

    @patch("hardware.battery_monitor.read_battery_level", return_value=80)
    @patch("hardware.battery_monitor.read_battery_status", return_value="Charging")
    def test_charging(self, _s, _l):
        result = get_battery_status_text()
        self.assertIn("Charging", result)
        self.assertIn("80%", result)

    @patch("hardware.battery_monitor.read_battery_level", return_value=None)
    @patch("hardware.battery_monitor.read_battery_status", return_value="Unknown")
    def test_no_battery(self, _s, _l):
        result = get_battery_status_text()
        self.assertEqual(result, "No battery")


class TestGetPowerModeText(unittest.TestCase):

    @patch("hardware.asus_controller.AsusController.is_plugged_in", return_value=True)
    def test_plugged_in(self, _mock):
        result = get_power_mode_text()
        self.assertEqual(result, "Performance Mode")

    @patch("hardware.asus_controller.AsusController.is_plugged_in", return_value=False)
    def test_on_battery(self, _mock):
        result = get_power_mode_text()
        self.assertEqual(result, "Battery Mode")


if __name__ == "__main__":
    unittest.main()
