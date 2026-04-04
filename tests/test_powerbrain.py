"""
tests/test_powerbrain.py
Unit tests for the unified PowerBrain power management system.

Strategy:
- Sensor functions (ac_monitor, thermal_monitor, process_intelligence):
  tested for correct shape and no-crash — hardware may not be present.
- PowerBrain logic: _auto_decide() tested with injected fake data so
  tests are deterministic with no hardware dependency.
- Daemon routing: route_request() integration for all power request types.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from power_manager.ac_monitor          import get_ac_status
from power_manager.thermal_monitor     import (
    get_cpu_temp, get_gpu_temp, get_thermal_level, THRESHOLDS
)
from power_manager.process_intelligence import (
    has_audio, is_gaming_running, get_foreground_pid
)
from power_manager.powerbrain import PowerBrain, MANUAL_PROFILES
import power_manager as pm


# ---------------------------------------------------------------------------
# AC monitor
# ---------------------------------------------------------------------------

class TestAcMonitor(unittest.TestCase):

    def test_returns_dict(self):
        self.assertIsInstance(get_ac_status(), dict)

    def test_has_all_required_keys(self):
        result = get_ac_status()
        for key in ("plugged_in", "battery_percent",
                    "battery_status", "discharge_rate_w", "minutes_remaining"):
            self.assertIn(key, result)

    def test_plugged_in_is_bool(self):
        self.assertIsInstance(get_ac_status()["plugged_in"], bool)

    def test_battery_percent_int_or_none(self):
        val = get_ac_status()["battery_percent"]
        self.assertTrue(val is None or isinstance(val, int))

    def test_discharge_rate_float_or_none(self):
        val = get_ac_status()["discharge_rate_w"]
        self.assertTrue(val is None or isinstance(val, float))

    def test_does_not_raise(self):
        try:
            get_ac_status()
        except Exception as e:
            self.fail(f"get_ac_status() raised: {e}")


# ---------------------------------------------------------------------------
# Thermal monitor
# ---------------------------------------------------------------------------

class TestThermalMonitor(unittest.TestCase):

    def test_get_cpu_temp_float_or_none(self):
        val = get_cpu_temp()
        self.assertTrue(val is None or isinstance(val, float))

    def test_get_cpu_temp_does_not_raise(self):
        try:
            get_cpu_temp()
        except Exception as e:
            self.fail(f"get_cpu_temp() raised: {e}")

    def test_get_gpu_temp_float_or_none(self):
        val = get_gpu_temp()
        self.assertTrue(val is None or isinstance(val, float))

    def test_get_gpu_temp_does_not_raise(self):
        try:
            get_gpu_temp()
        except Exception as e:
            self.fail(f"get_gpu_temp() raised: {e}")

    def test_get_thermal_level_returns_valid_string(self):
        level = get_thermal_level()
        self.assertIn(level, ("normal", "warn", "throttle", "emergency"))

    def test_get_thermal_level_does_not_raise(self):
        try:
            get_thermal_level()
        except Exception as e:
            self.fail(f"get_thermal_level() raised: {e}")

    def test_thresholds_are_ordered(self):
        self.assertLess(THRESHOLDS["warn"], THRESHOLDS["throttle"])
        self.assertLess(THRESHOLDS["throttle"], THRESHOLDS["emergency"])


# ---------------------------------------------------------------------------
# Process intelligence
# ---------------------------------------------------------------------------

class TestProcessIntelligence(unittest.TestCase):

    def test_has_audio_current_pid_returns_bool(self):
        result = has_audio(os.getpid())
        self.assertIsInstance(result, bool)

    def test_has_audio_bogus_pid_returns_false(self):
        self.assertFalse(has_audio(999999999))

    def test_has_audio_does_not_raise(self):
        try:
            has_audio(os.getpid())
        except Exception as e:
            self.fail(f"has_audio() raised: {e}")

    def test_is_gaming_running_returns_bool(self):
        self.assertIsInstance(is_gaming_running(), bool)

    def test_is_gaming_running_does_not_raise(self):
        try:
            is_gaming_running()
        except Exception as e:
            self.fail(f"is_gaming_running() raised: {e}")

    def test_get_foreground_pid_returns_int_or_none(self):
        val = get_foreground_pid()
        self.assertTrue(val is None or isinstance(val, int))


# ---------------------------------------------------------------------------
# PowerBrain — set_mode
# ---------------------------------------------------------------------------

class TestPowerBrainSetMode(unittest.TestCase):

    def setUp(self):
        self.brain = PowerBrain()

    def test_set_quiet_sets_mode(self):
        result = self.brain.set_mode("quiet")
        self.assertEqual(result["mode"], "quiet")
        self.assertEqual(self.brain.mode, "quiet")

    def test_set_quiet_description_present(self):
        result = self.brain.set_mode("quiet")
        self.assertIn("description", result)

    def test_set_balanced_has_schedutil_in_decision(self):
        result = self.brain.set_mode("balanced")
        decision = result.get("decision", {})
        self.assertEqual(decision.get("governor"), "schedutil")

    def test_set_max_has_nvidia_100(self):
        result = self.brain.set_mode("max")
        decision = result.get("decision", {})
        self.assertEqual(decision.get("nvidia_percent"), 100)

    def test_set_auto_mode_string(self):
        result = self.brain.set_mode("auto")
        self.assertEqual(result["mode"], "auto")
        self.assertEqual(self.brain.mode, "auto")

    def test_invalid_mode_returns_error(self):
        result = self.brain.set_mode("ludicrous_speed")
        self.assertIn("error", result)

    def test_invalid_mode_does_not_change_mode(self):
        self.brain.set_mode("quiet")
        self.brain.set_mode("does_not_exist")
        self.assertEqual(self.brain.mode, "quiet")

    def test_invalid_mode_lists_valid_modes(self):
        result = self.brain.set_mode("bad")
        self.assertIn("valid_modes", result)
        self.assertIn("auto", result["valid_modes"])


# ---------------------------------------------------------------------------
# PowerBrain — _auto_decide (pure logic, no I/O)
# ---------------------------------------------------------------------------

class TestAutoDecide(unittest.TestCase):

    def setUp(self):
        self.brain = PowerBrain()

    def _ac(self, plugged_in, battery_percent=None):
        return {
            "plugged_in":        plugged_in,
            "battery_percent":   battery_percent,
            "battery_status":    "Discharging" if not plugged_in else "Charging",
            "discharge_rate_w":  None,
            "minutes_remaining": None,
        }

    def test_gaming_always_max(self):
        decision = self.brain._auto_decide(self._ac(True), "normal", True)
        self.assertEqual(decision["governor"], "performance")
        self.assertEqual(decision["nvidia_percent"], 100)
        self.assertIn("gaming", decision["reason"])

    def test_gaming_beats_thermal_emergency(self):
        # Gaming detected even during thermal emergency → max
        decision = self.brain._auto_decide(self._ac(True), "emergency", True)
        self.assertEqual(decision["nvidia_percent"], 100)

    def test_plugged_normal_is_max(self):
        decision = self.brain._auto_decide(self._ac(True), "normal", False)
        self.assertEqual(decision["governor"], "performance")
        self.assertEqual(decision["nvidia_percent"], 100)

    def test_plugged_warn_is_balanced(self):
        decision = self.brain._auto_decide(self._ac(True), "warn", False)
        self.assertEqual(decision["governor"], "schedutil")

    def test_plugged_throttle_is_balanced(self):
        decision = self.brain._auto_decide(self._ac(True), "throttle", False)
        self.assertEqual(decision["governor"], "schedutil")

    def test_plugged_emergency_is_quiet(self):
        decision = self.brain._auto_decide(self._ac(True), "emergency", False)
        self.assertEqual(decision["governor"], "powersave")
        self.assertEqual(decision["nvidia_percent"], 0)

    def test_battery_critical_under_20_is_quiet(self):
        decision = self.brain._auto_decide(self._ac(False, 15), "normal", False)
        self.assertEqual(decision["governor"], "powersave")
        self.assertEqual(decision["nvidia_percent"], 0)

    def test_battery_50_and_below_is_quiet(self):
        decision = self.brain._auto_decide(self._ac(False, 40), "normal", False)
        self.assertEqual(decision["governor"], "powersave")

    def test_battery_above_50_normal_is_balanced(self):
        decision = self.brain._auto_decide(self._ac(False, 75), "normal", False)
        self.assertEqual(decision["governor"], "schedutil")

    def test_battery_emergency_is_quiet(self):
        decision = self.brain._auto_decide(self._ac(False, 80), "emergency", False)
        self.assertEqual(decision["governor"], "powersave")

    def test_decision_has_reason(self):
        decision = self.brain._auto_decide(self._ac(True), "normal", False)
        self.assertIn("reason", decision)


# ---------------------------------------------------------------------------
# PowerBrain — thermal emergency overrides manual mode
# ---------------------------------------------------------------------------

class TestThermalEmergencyOverride(unittest.TestCase):

    def test_emergency_overrides_max_mode(self):
        """When thermal emergency while in manual max mode → quiet applied."""
        from unittest.mock import patch
        brain = PowerBrain()
        brain.mode = "max"
        with patch("power_manager.powerbrain.get_thermal_level", return_value="emergency"):
            decision = brain.apply_current_decision()
        self.assertEqual(decision["governor"], "powersave")
        self.assertIn("emergency", decision.get("reason", ""))

    def test_normal_thermal_does_not_override_manual(self):
        """Normal thermal → manual mode respected."""
        from unittest.mock import patch
        brain = PowerBrain()
        brain.mode = "max"
        with patch("power_manager.powerbrain.get_thermal_level", return_value="normal"):
            decision = brain.apply_current_decision()
        self.assertEqual(decision["governor"], "performance")


# ---------------------------------------------------------------------------
# PowerBrain — decision log
# ---------------------------------------------------------------------------

class TestDecisionLog(unittest.TestCase):

    def test_decision_log_capped_at_30(self):
        brain = PowerBrain()
        for _ in range(35):
            brain.apply_current_decision()
        self.assertLessEqual(len(brain.decision_log), 30)

    def test_decision_log_grows_with_decisions(self):
        brain = PowerBrain()
        brain.apply_current_decision()
        brain.apply_current_decision()
        self.assertGreaterEqual(len(brain.decision_log), 2)

    def test_decision_log_entry_has_timestamp(self):
        brain = PowerBrain()
        brain.apply_current_decision()
        entry = brain.decision_log[-1]
        self.assertIn("timestamp", entry)


# ---------------------------------------------------------------------------
# PowerBrain — get_status
# ---------------------------------------------------------------------------

class TestGetStatus(unittest.TestCase):

    def test_has_all_required_keys(self):
        brain = PowerBrain()
        status = brain.get_status()
        for key in ("mode", "auto_or_manual", "last_decision",
                    "ac", "thermal", "gaming_detected", "recent_log"):
            self.assertIn(key, status)

    def test_auto_mode_auto_or_manual_is_auto(self):
        brain = PowerBrain()
        self.assertEqual(brain.get_status()["auto_or_manual"], "auto")

    def test_manual_mode_auto_or_manual_is_manual(self):
        brain = PowerBrain()
        brain.mode = "quiet"
        self.assertEqual(brain.get_status()["auto_or_manual"], "manual")

    def test_gaming_detected_is_bool(self):
        brain = PowerBrain()
        self.assertIsInstance(brain.get_status()["gaming_detected"], bool)

    def test_recent_log_is_list(self):
        brain = PowerBrain()
        self.assertIsInstance(brain.get_status()["recent_log"], list)


# ---------------------------------------------------------------------------
# power_manager public API
# ---------------------------------------------------------------------------

class TestPowerManagerPublicApi(unittest.TestCase):

    def test_list_modes_has_four_entries(self):
        modes = pm.list_modes()
        self.assertEqual(len(modes), 4)

    def test_list_modes_has_auto(self):
        self.assertIn("auto", pm.list_modes())

    def test_list_modes_has_quiet_balanced_max(self):
        modes = pm.list_modes()
        for key in ("quiet", "balanced", "max"):
            self.assertIn(key, modes)

    def test_get_status_has_required_keys(self):
        status = pm.get_status()
        for key in ("mode", "auto_or_manual", "last_decision", "ac", "thermal"):
            self.assertIn(key, status)


# ---------------------------------------------------------------------------
# Daemon routing
# ---------------------------------------------------------------------------

class TestDaemonPowerRouting(unittest.TestCase):

    def setUp(self):
        import daemon.main as dm
        self.route = dm.route_request

    def test_power_set_quiet_returns_mode(self):
        result = self.route({"type": "power_set", "mode": "quiet"})
        self.assertEqual(result.get("mode"), "quiet")

    def test_power_set_auto_returns_mode(self):
        result = self.route({"type": "power_set", "mode": "auto"})
        self.assertEqual(result.get("mode"), "auto")

    def test_power_set_missing_mode_returns_error(self):
        result = self.route({"type": "power_set"})
        self.assertEqual(result.get("status"), "error")

    def test_power_set_invalid_mode_returns_error(self):
        result = self.route({"type": "power_set", "mode": "warp_factor_9"})
        self.assertIn("error", result)

    def test_power_status_returns_required_keys(self):
        result = self.route({"type": "power_status"})
        for key in ("mode", "ac", "thermal"):
            self.assertIn(key, result)

    def test_power_modes_returns_dict(self):
        result = self.route({"type": "power_modes"})
        self.assertIsInstance(result, dict)

    def test_power_modes_has_all_four(self):
        result = self.route({"type": "power_modes"})
        for key in ("auto", "quiet", "balanced", "max"):
            self.assertIn(key, result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
