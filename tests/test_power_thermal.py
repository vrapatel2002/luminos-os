"""
tests/test_power_thermal.py
Phase 5.5 — Power & Thermal Wiring test suite.

Covers:
  - power_events: PowerEventBus subscribe/emit, power mode wiring  (5 tests)
  - asus_controller: fan curves, config load/save, boot defaults   (5 tests)
  - thermal_monitor: threshold classification, power mode switch    (3 tests)
  - display_manager: refresh modes, setting load/save              (3 tests)
  - battery_monitor: read helpers, notification thresholds         (4 tests)

Total: 20 tests — all headless, no hardware or subprocess calls.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


# ===========================================================================
# PowerEventBus
# ===========================================================================

from hardware.power_events import PowerEventBus, EVENTS


class TestPowerEventBus(unittest.TestCase):

    def test_events_tuple(self):
        self.assertIn("battery", EVENTS)
        self.assertIn("ac", EVENTS)
        self.assertIn("game_start", EVENTS)
        self.assertIn("game_end", EVENTS)

    def test_subscribe_and_emit(self):
        bus = PowerEventBus()
        received = []
        bus.subscribe("ac", lambda data: received.append(data))
        bus.emit("ac", {"plugged_in": True})
        self.assertEqual(len(received), 1)
        self.assertTrue(received[0]["plugged_in"])
        self.assertEqual(received[0]["event"], "ac")

    def test_emit_unknown_event_ignored(self):
        bus = PowerEventBus()
        bus.emit("nonexistent")  # should not crash

    def test_switch_to_battery_calls_thermal(self):
        mock_thermal = mock.MagicMock()
        bus = PowerEventBus(thermal_monitor=mock_thermal)
        with mock.patch("hardware.power_events.PowerEventBus._switch_to_battery") as m:
            m.return_value = None
            # Direct call test
        bus._thermal = mock_thermal
        bus._switch_to_battery()
        mock_thermal.set_power_mode.assert_called_once_with(on_battery=True)

    def test_switch_to_performance_calls_thermal(self):
        mock_thermal = mock.MagicMock()
        bus = PowerEventBus(thermal_monitor=mock_thermal)
        bus._switch_to_performance()
        mock_thermal.set_power_mode.assert_called_once_with(on_battery=False)


# ===========================================================================
# AsusController — fan curves & config
# ===========================================================================

from hardware.asus_controller import (
    AsusController, DEFAULT_FAN_CURVE, BATTERY_FAN_CURVE,
    load_hardware_config, save_hardware_config,
    _VALID_CHARGE_LIMITS,
)


class TestFanCurves(unittest.TestCase):

    def test_default_curve_has_cpu_and_gpu(self):
        self.assertIn("cpu", DEFAULT_FAN_CURVE)
        self.assertIn("gpu", DEFAULT_FAN_CURVE)

    def test_battery_curve_has_cpu_and_gpu(self):
        self.assertIn("cpu", BATTERY_FAN_CURVE)
        self.assertIn("gpu", BATTERY_FAN_CURVE)

    def test_battery_curve_quieter_at_70(self):
        """Battery curve should have 0% fan below 70C."""
        cpu_points = BATTERY_FAN_CURVE["cpu"]
        # First point should be (0, 0)
        self.assertEqual(cpu_points[0], (0, 0))
        # At 70C, fan starts ramping (20%)
        self.assertEqual(cpu_points[1], (70, 20))

    def test_valid_charge_limits(self):
        self.assertEqual(_VALID_CHARGE_LIMITS, (60, 80, 100))


class TestHardwareConfig(unittest.TestCase):

    def test_load_missing_file_returns_default(self):
        with mock.patch("hardware.asus_controller._HARDWARE_CONFIG_PATH",
                        "/tmp/nonexistent_luminos_hw.json"):
            config = load_hardware_config()
        self.assertEqual(config["battery_limit"], 80)

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "hardware.json")
            with mock.patch("hardware.asus_controller._HARDWARE_CONFIG_PATH", path):
                save_hardware_config({"battery_limit": 60})
                config = load_hardware_config()
            self.assertEqual(config["battery_limit"], 60)


# ===========================================================================
# ThermalMonitor
# ===========================================================================

from hardware.thermal_monitor import ThermalMonitor, THRESHOLDS


class TestThermalMonitor(unittest.TestCase):

    def test_thresholds(self):
        self.assertEqual(THRESHOLDS["warn"], 75)
        self.assertEqual(THRESHOLDS["critical"], 85)
        self.assertEqual(THRESHOLDS["emergency"], 95)

    def test_classify_level(self):
        tm = ThermalMonitor()
        self.assertEqual(tm._classify_level(50), "normal")
        self.assertEqual(tm._classify_level(76), "warn")
        self.assertEqual(tm._classify_level(86), "critical")
        self.assertEqual(tm._classify_level(96), "emergency")

    def test_set_power_mode_battery(self):
        mock_asus = mock.MagicMock()
        tm = ThermalMonitor(asus_controller=mock_asus)
        tm.set_power_mode(on_battery=True)
        mock_asus.set_fan_curve.assert_called_once()
        self.assertTrue(tm._on_battery)


# ===========================================================================
# DisplayManager
# ===========================================================================

from hardware.display_manager import (
    get_refresh_modes, load_display_setting, save_display_setting,
)


class TestDisplayManager(unittest.TestCase):

    def test_refresh_modes_count(self):
        modes = get_refresh_modes()
        self.assertEqual(len(modes), 3)

    def test_refresh_mode_ids(self):
        ids = [m["id"] for m in get_refresh_modes()]
        self.assertIn("auto", ids)
        self.assertIn("always_60", ids)
        self.assertIn("always_120", ids)

    def test_save_and_load_display_setting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "display.json")
            with mock.patch("hardware.display_manager._DISPLAY_CONFIG_PATH", path):
                save_display_setting("always_120")
                result = load_display_setting()
            self.assertEqual(result, "always_120")


# ===========================================================================
# BatteryMonitor
# ===========================================================================

from hardware.battery_monitor import read_battery_level, read_battery_status, BatteryMonitor


class TestBatteryMonitor(unittest.TestCase):

    def test_read_battery_level_missing_returns_none(self):
        with mock.patch("builtins.open", side_effect=OSError):
            self.assertIsNone(read_battery_level())

    def test_read_battery_status_missing_returns_unknown(self):
        with mock.patch("builtins.open", side_effect=OSError):
            self.assertEqual(read_battery_status(), "Unknown")

    def test_notification_at_20_percent(self):
        notified = []
        monitor = BatteryMonitor(notify_callback=lambda t, b, u: notified.append((t, b, u)))

        with mock.patch("hardware.battery_monitor.read_battery_level", return_value=20), \
             mock.patch("hardware.battery_monitor.read_battery_status", return_value="Discharging"):
            monitor._check_level()

        self.assertEqual(len(notified), 1)
        self.assertIn("Battery Low", notified[0][0])
        self.assertTrue(monitor._notified_20)

    def test_notifications_reset_on_charging(self):
        monitor = BatteryMonitor()
        monitor._notified_20 = True
        monitor._notified_10 = True

        with mock.patch("hardware.battery_monitor.read_battery_level", return_value=50), \
             mock.patch("hardware.battery_monitor.read_battery_status", return_value="Charging"):
            monitor._check_level()

        self.assertFalse(monitor._notified_20)
        self.assertFalse(monitor._notified_10)


if __name__ == "__main__":
    unittest.main()
