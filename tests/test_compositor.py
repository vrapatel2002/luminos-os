"""
tests/test_compositor.py
Unit tests for Phase 8 Compositor & Display Layer.

Strategy:
- window_manager: test all lifecycle operations + zone rule enforcement.
- upscale_manager: test mode setting, invalid mode, status structure.
- compositor_config: test config generation content, write to /tmp.
- compositor __init__: public API smoke tests.
- Daemon routing: route_request() integration for all compositor types.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compositor.window_manager    import WindowManager, ZONE_WINDOW_RULES
from compositor.upscale_manager   import UpscaleManager, UPSCALE_MODES, detect_display
from compositor.compositor_config import (
    generate_hyprland_config, generate_sway_config,
    write_config, generate_waybar_config,
)
import compositor as comp


# ---------------------------------------------------------------------------
# WindowManager — zone rules
# ---------------------------------------------------------------------------

class TestWindowManagerZoneRules(unittest.TestCase):

    def setUp(self):
        self.wm = WindowManager()

    def test_zone1_no_border(self):
        info = self.wm.register_window(100, "/usr/bin/app", 1)
        self.assertEqual(info["border"], "none")

    def test_zone1_no_xwayland(self):
        info = self.wm.register_window(100, "/usr/bin/app", 1)
        self.assertFalse(info["xwayland"])

    def test_zone1_no_label(self):
        info = self.wm.register_window(100, "/usr/bin/app", 1)
        self.assertIsNone(info["label"])

    def test_zone2_blue_border(self):
        info = self.wm.register_window(200, "/path/to/app.exe", 2)
        self.assertEqual(info["border"], "blue")

    def test_zone2_xwayland_true(self):
        info = self.wm.register_window(200, "/path/to/app.exe", 2)
        self.assertTrue(info["xwayland"])

    def test_zone2_label_wine(self):
        info = self.wm.register_window(200, "/path/to/app.exe", 2)
        self.assertEqual(info["label"], "Wine")

    def test_zone3_red_border(self):
        info = self.wm.register_window(300, "/path/to/dangerous.exe", 3)
        self.assertEqual(info["border"], "red")

    def test_zone3_quarantine_label(self):
        info = self.wm.register_window(300, "/path/to/dangerous.exe", 3)
        self.assertEqual(info["label"], "QUARANTINE")

    def test_zone3_opacity_reduced(self):
        info = self.wm.register_window(300, "/path/to/dangerous.exe", 3)
        self.assertLess(info["opacity"], 1.0)

    def test_zone3_no_xwayland(self):
        info = self.wm.register_window(300, "/path/to/dangerous.exe", 3)
        self.assertFalse(info["xwayland"])


# ---------------------------------------------------------------------------
# WindowManager — lifecycle
# ---------------------------------------------------------------------------

class TestWindowManagerLifecycle(unittest.TestCase):

    def setUp(self):
        self.wm = WindowManager()

    def test_register_stores_window(self):
        self.wm.register_window(1, "/app", 1)
        self.assertIn(1, self.wm.windows)

    def test_register_returns_info_dict(self):
        info = self.wm.register_window(1, "/app", 1)
        for key in ("pid", "exe", "zone", "border", "xwayland", "label", "opacity", "registered_at"):
            self.assertIn(key, info)

    def test_unregister_removes_window(self):
        self.wm.register_window(1, "/app", 1)
        result = self.wm.unregister_window(1)
        self.assertTrue(result["removed"])
        self.assertNotIn(1, self.wm.windows)

    def test_unregister_unknown_pid_returns_removed_false(self):
        result = self.wm.unregister_window(9999)
        self.assertFalse(result["removed"])
        self.assertEqual(result["pid"], 9999)

    def test_unregister_active_clears_active_pid(self):
        self.wm.register_window(1, "/app", 1)
        self.wm.focus_window(1)
        self.wm.unregister_window(1)
        self.assertIsNone(self.wm.active_pid)

    def test_focus_window_sets_active_pid(self):
        self.wm.register_window(5, "/app", 2)
        self.wm.focus_window(5)
        self.assertEqual(self.wm.active_pid, 5)

    def test_focus_window_returns_correct_zone(self):
        self.wm.register_window(5, "/app", 2)
        result = self.wm.focus_window(5)
        self.assertEqual(result["zone"], 2)

    def test_focus_window_unknown_pid_returns_error(self):
        result = self.wm.focus_window(9999)
        self.assertIn("error", result)

    def test_list_windows_returns_all_registered(self):
        self.wm.register_window(1, "/a", 1)
        self.wm.register_window(2, "/b", 2)
        self.wm.register_window(3, "/c", 3)
        self.assertEqual(len(self.wm.list_windows()), 3)

    def test_list_windows_empty_initially(self):
        self.assertEqual(self.wm.list_windows(), [])

    def test_get_zone_summary_correct_counts(self):
        self.wm.register_window(1, "/a", 1)
        self.wm.register_window(2, "/b", 2)
        self.wm.register_window(3, "/c", 2)
        self.wm.register_window(4, "/d", 3)
        summary = self.wm.get_zone_summary()
        self.assertEqual(summary["zone1"], 1)
        self.assertEqual(summary["zone2"], 2)
        self.assertEqual(summary["zone3"], 1)
        self.assertEqual(summary["total"], 4)

    def test_get_zone_summary_all_zero_initially(self):
        summary = self.wm.get_zone_summary()
        self.assertEqual(summary["total"], 0)


# ---------------------------------------------------------------------------
# UpscaleManager — set_mode
# ---------------------------------------------------------------------------

class TestUpscaleManagerSetMode(unittest.TestCase):

    def setUp(self):
        self.upm = UpscaleManager()

    def test_set_off_returns_ratio_1(self):
        result = self.upm.set_mode("off")
        self.assertEqual(result["render_ratio"], 1.0)

    def test_set_quality_returns_correct_ratio(self):
        result = self.upm.set_mode("quality")
        self.assertEqual(result["render_ratio"], UPSCALE_MODES["quality"]["ratio"])

    def test_set_balanced_returns_correct_ratio(self):
        result = self.upm.set_mode("balanced")
        self.assertEqual(result["render_ratio"], UPSCALE_MODES["balanced"]["ratio"])

    def test_set_performance_returns_correct_ratio(self):
        result = self.upm.set_mode("performance")
        self.assertEqual(result["render_ratio"], UPSCALE_MODES["performance"]["ratio"])

    def test_set_mode_updates_current_mode(self):
        self.upm.set_mode("quality")
        self.assertEqual(self.upm.current_mode, "quality")

    def test_set_mode_returns_note(self):
        result = self.upm.set_mode("quality")
        self.assertIn("note", result)

    def test_invalid_mode_returns_error(self):
        result = self.upm.set_mode("ultra_turbo_9000")
        self.assertIn("error", result)

    def test_invalid_mode_lists_valid_modes(self):
        result = self.upm.set_mode("bad")
        self.assertIn("valid_modes", result)
        self.assertEqual(set(result["valid_modes"]), set(UPSCALE_MODES.keys()))

    def test_invalid_mode_does_not_change_current_mode(self):
        self.upm.set_mode("quality")
        self.upm.set_mode("not_real")
        self.assertEqual(self.upm.current_mode, "quality")

    def test_set_mode_does_not_raise(self):
        for mode in UPSCALE_MODES:
            with self.subTest(mode=mode):
                try:
                    self.upm.set_mode(mode)
                except Exception as e:
                    self.fail(f"set_mode({mode!r}) raised: {e}")


# ---------------------------------------------------------------------------
# UpscaleManager — get_status / detect_display
# ---------------------------------------------------------------------------

class TestUpscaleManagerStatus(unittest.TestCase):

    def test_get_status_has_required_keys(self):
        upm = UpscaleManager()
        status = upm.get_status()
        for key in ("current_mode", "display", "available_modes"):
            self.assertIn(key, status)

    def test_get_status_current_mode_is_off_initially(self):
        upm = UpscaleManager()
        self.assertEqual(upm.get_status()["current_mode"], "off")

    def test_get_status_available_modes_has_four(self):
        upm = UpscaleManager()
        self.assertEqual(len(upm.get_status()["available_modes"]), 4)

    def test_detect_display_returns_dict_with_available_key(self):
        result = detect_display()
        self.assertIn("available", result)

    def test_detect_display_has_all_keys(self):
        result = detect_display()
        for key in ("available", "resolution", "refresh_hz", "connector"):
            self.assertIn(key, result)

    def test_detect_display_does_not_raise(self):
        try:
            detect_display()
        except Exception as e:
            self.fail(f"detect_display() raised: {e}")


# ---------------------------------------------------------------------------
# compositor_config — generate_sway_config
# ---------------------------------------------------------------------------

class TestGenerateHyprlandConfig(unittest.TestCase):

    def test_returns_string(self):
        self.assertIsInstance(generate_hyprland_config(), str)

    def test_contains_exec_luminos_ai(self):
        self.assertIn("exec-once = luminos-ai", generate_hyprland_config())

    def test_contains_quarantine(self):
        self.assertIn("QUARANTINE", generate_hyprland_config())

    def test_contains_output_name(self):
        cfg = generate_hyprland_config("HDMI-A-1")
        self.assertIn("HDMI-A-1", cfg)

    def test_default_output_name_is_edp1(self):
        cfg = generate_hyprland_config()
        self.assertIn("eDP-1", cfg)

    def test_contains_xwayland_rule(self):
        self.assertIn("xwayland", generate_hyprland_config())

    def test_contains_key_binding_super_q(self):
        self.assertIn("$mod, Q", generate_hyprland_config())

    def test_contains_key_binding_super_enter(self):
        self.assertIn("$mod, Return", generate_hyprland_config())

    def test_contains_gaps(self):
        self.assertIn("gaps_in", generate_hyprland_config())

    def test_shadow_uses_block_not_flat(self):
        cfg = generate_hyprland_config()
        self.assertIn("shadow {", cfg)
        self.assertNotIn("drop_shadow", cfg)
        self.assertNotIn("shadow_range", cfg)
        self.assertNotIn("shadow_render_power", cfg)
        self.assertNotIn("col.shadow", cfg)

    def test_backward_compat_alias(self):
        self.assertEqual(generate_sway_config(), generate_hyprland_config())


# ---------------------------------------------------------------------------
# compositor_config — write_config
# ---------------------------------------------------------------------------

class TestWriteConfig(unittest.TestCase):

    def test_write_to_tmp_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sway_test", "config")
            result = write_config(path)
            self.assertTrue(result["success"])

    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sway", "config")
            write_config(path)
            self.assertTrue(os.path.exists(path))

    def test_write_returns_path_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config")
            result = write_config(path)
            self.assertIn("path", result)

    def test_write_no_error_on_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config")
            result = write_config(path)
            self.assertIsNone(result["error"])


# ---------------------------------------------------------------------------
# compositor_config — generate_waybar_config
# ---------------------------------------------------------------------------

class TestGenerateWaybarConfig(unittest.TestCase):

    def test_returns_dict(self):
        self.assertIsInstance(generate_waybar_config(), dict)

    def test_has_left_modules(self):
        cfg = generate_waybar_config()
        self.assertIn("modules-left", cfg)

    def test_has_center_modules(self):
        cfg = generate_waybar_config()
        self.assertIn("modules-center", cfg)

    def test_has_right_modules(self):
        cfg = generate_waybar_config()
        self.assertIn("modules-right", cfg)

    def test_left_contains_workspaces(self):
        cfg = generate_waybar_config()
        self.assertIn("hyprland/workspaces", cfg["modules-left"])

    def test_center_contains_clock(self):
        cfg = generate_waybar_config()
        self.assertIn("clock", cfg["modules-center"])

    def test_right_contains_cpu_and_memory(self):
        cfg = generate_waybar_config()
        right = cfg["modules-right"]
        self.assertIn("cpu", right)
        self.assertIn("memory", right)


# ---------------------------------------------------------------------------
# Daemon routing — compositor request types
# ---------------------------------------------------------------------------

class TestDaemonCompositorRouting(unittest.TestCase):

    def setUp(self):
        import daemon.main as dm
        self.route   = dm.route_request
        self.stub_mm = dm.ModelManager()

    def test_window_register_returns_pid_and_zone(self):
        result = self.route(
            {"type": "window_register", "pid": 42, "exe": "/app", "zone": 1},
            self.stub_mm
        )
        self.assertEqual(result["pid"], 42)
        self.assertEqual(result["zone"], 1)

    def test_window_register_zone2_blue_border(self):
        result = self.route(
            {"type": "window_register", "pid": 43, "exe": "/app.exe", "zone": 2},
            self.stub_mm
        )
        self.assertEqual(result["border"], "blue")

    def test_window_register_zone3_quarantine(self):
        result = self.route(
            {"type": "window_register", "pid": 44, "exe": "/danger.exe", "zone": 3},
            self.stub_mm
        )
        self.assertEqual(result["label"], "QUARANTINE")

    def test_window_register_missing_pid_returns_error(self):
        result = self.route(
            {"type": "window_register", "exe": "/app", "zone": 1},
            self.stub_mm
        )
        self.assertEqual(result.get("status"), "error")

    def test_window_list_returns_windows_key(self):
        result = self.route({"type": "window_list"}, self.stub_mm)
        self.assertIn("windows", result)

    def test_window_list_returns_summary_key(self):
        result = self.route({"type": "window_list"}, self.stub_mm)
        self.assertIn("summary", result)

    def test_upscale_set_quality_returns_mode(self):
        result = self.route(
            {"type": "upscale_set", "mode": "quality"},
            self.stub_mm
        )
        self.assertEqual(result.get("mode"), "quality")

    def test_upscale_set_invalid_mode_returns_error_info(self):
        result = self.route(
            {"type": "upscale_set", "mode": "warp_speed"},
            self.stub_mm
        )
        self.assertIn("error", result)

    def test_upscale_set_missing_mode_returns_error(self):
        result = self.route({"type": "upscale_set"}, self.stub_mm)
        self.assertEqual(result.get("status"), "error")

    def test_display_status_has_current_mode(self):
        result = self.route({"type": "display_status"}, self.stub_mm)
        self.assertIn("current_mode", result)

    def test_display_status_has_available_modes(self):
        result = self.route({"type": "display_status"}, self.stub_mm)
        self.assertIn("available_modes", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
