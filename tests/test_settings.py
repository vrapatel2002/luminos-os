"""
tests/test_settings.py
Phase 8.10 — Luminos Settings test suite.

Covers:
  - settings_window: CATEGORIES list structure and search helper           (4 tests)
  - appearance_panel: _get_theme_mode normalization, accent presets         (4 tests)
  - display_panel: _get_scale_options, _get_upscale_modes, _parse_resolution (3 tests)
  - power_panel: _get_power_cards, _get_sleep_options, _format_temp         (3 tests)
  - zones_panel: _get_zone_color, _load_zone_overrides, _save_zone_override (3 tests)
  - ai_panel: _get_daemon_status, _get_hive_models, _get_npu_status         (3 tests)
  - about_panel: _get_kernel_version, _get_hardware_info, _export_report    (3 tests)

Total: 27 tests — all headless, no network or subprocess calls for GTK.
"""

import os
import sys
import tempfile
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gui.settings.settings_window import CATEGORIES, CATEGORY_IDS, _match_category
from gui.settings.panels.appearance_panel import (
    _get_theme_mode, _get_accent_presets,
)
from gui.settings.panels.display_panel import (
    _get_scale_options, _get_upscale_modes, _parse_resolution,
)
from gui.settings.panels.power_panel import (
    _get_power_cards, _get_sleep_options, _format_temp,
)
from gui.settings.panels.zones_panel import (
    _get_zone_color, _load_zone_overrides, _save_zone_override,
)
from gui.settings.panels.ai_panel import (
    _get_daemon_status, _get_hive_models, _get_npu_status,
)
from gui.settings.panels.about_panel import (
    _get_kernel_version, _get_hardware_info, _export_report,
    _format_uptime,
)


# ===========================================================================
# settings_window
# ===========================================================================

class TestCategoriesList(unittest.TestCase):

    def test_has_12_categories(self):
        self.assertEqual(len(CATEGORIES), 12)

    def test_required_ids_present(self):
        for required in ("appearance", "keyboard", "display", "power", "zones", "ai", "about"):
            self.assertIn(required, CATEGORY_IDS)

    def test_each_category_has_required_keys(self):
        for cat in CATEGORIES:
            self.assertIn("id",    cat)
            self.assertIn("label", cat)
            self.assertIn("icon",  cat)

    def test_match_category_case_insensitive(self):
        cat = {"id": "appearance", "label": "Appearance", "icon": "x"}
        self.assertTrue(_match_category("appear", cat))
        self.assertTrue(_match_category("APPEAR", cat))
        self.assertFalse(_match_category("power",  cat))


# ===========================================================================
# appearance_panel
# ===========================================================================

class TestGetThemeMode(unittest.TestCase):

    def test_dark_string(self):
        self.assertEqual(_get_theme_mode("dark"),  "dark")

    def test_light_string(self):
        self.assertEqual(_get_theme_mode("light"), "light")

    def test_auto_string(self):
        self.assertEqual(_get_theme_mode("auto"),  "auto")

    def test_true_maps_to_dark(self):
        self.assertEqual(_get_theme_mode("True"), "dark")

    def test_false_maps_to_light(self):
        self.assertEqual(_get_theme_mode("False"), "light")

    def test_unknown_maps_to_auto(self):
        self.assertEqual(_get_theme_mode("bogus"), "auto")


class TestAccentPresets(unittest.TestCase):

    def test_returns_8_presets(self):
        self.assertEqual(len(_get_accent_presets()), 8)

    def test_each_has_name_and_hex(self):
        for p in _get_accent_presets():
            self.assertIn("name", p)
            self.assertIn("hex", p)
            self.assertTrue(p["hex"].startswith("#"))


# ===========================================================================
# display_panel
# ===========================================================================

class TestDisplayPanelHelpers(unittest.TestCase):

    def test_scale_options_count(self):
        opts = _get_scale_options()
        self.assertGreaterEqual(len(opts), 4)
        self.assertIn("100%", opts)
        self.assertIn("200%", opts)

    def test_upscale_modes_has_fsr(self):
        modes = _get_upscale_modes()
        self.assertTrue(any("FSR" in m for m in modes))

    def test_parse_resolution_valid(self):
        result = _parse_resolution("1920x1080")
        self.assertEqual(result, (1920, 1080))

    def test_parse_resolution_invalid(self):
        self.assertIsNone(_parse_resolution("not-a-resolution"))
        self.assertIsNone(_parse_resolution(""))


# ===========================================================================
# power_panel
# ===========================================================================

class TestPowerPanelHelpers(unittest.TestCase):

    def test_get_power_cards_has_4(self):
        cards = _get_power_cards()
        self.assertEqual(len(cards), 4)

    def test_power_cards_ids(self):
        ids = [c["id"] for c in _get_power_cards()]
        for expected in ("quiet", "auto", "balanced", "max"):
            self.assertIn(expected, ids)

    def test_power_card_has_required_keys(self):
        for card in _get_power_cards():
            for key in ("id", "label", "description", "icon"):
                self.assertIn(key, card)

    def test_sleep_options_nonempty(self):
        opts = _get_sleep_options()
        self.assertGreater(len(opts), 0)
        self.assertIn("Never", opts)

    def test_format_temp(self):
        self.assertEqual(_format_temp(62.4), "62 °C")
        self.assertEqual(_format_temp(100.0), "100 °C")


# ===========================================================================
# zones_panel
# ===========================================================================

class TestZonesPanelHelpers(unittest.TestCase):

    def test_zone_color_zone1_green(self):
        color = _get_zone_color(1)
        self.assertTrue(color.startswith("#"))
        self.assertEqual(color.lower(), "#00c896")

    def test_zone_color_zone2_accent(self):
        color = _get_zone_color(2)
        self.assertEqual(color.lower(), "#0080ff")

    def test_zone_color_zone3_red(self):
        color = _get_zone_color(3)
        self.assertEqual(color.lower(), "#ff4455")

    def test_zone_color_unknown_grey(self):
        color = _get_zone_color(99)
        self.assertTrue(color.startswith("#"))

    def test_load_zone_overrides_no_file(self):
        """_load_zone_overrides returns empty dict when file missing."""
        import unittest.mock as mock
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            result = _load_zone_overrides()
        self.assertIsInstance(result, dict)

    def test_save_and_load_zone_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import unittest.mock as mock
            fake_path = os.path.join(tmpdir, "zones.json")
            with mock.patch(
                "gui.settings.panels.zones_panel._OVERRIDES_PATH", fake_path
            ):
                ok = _save_zone_override("myapp", 2)
                self.assertTrue(ok)
                loaded = _load_zone_overrides()
            self.assertEqual(loaded.get("myapp"), 2)


# ===========================================================================
# ai_panel
# ===========================================================================

class TestAIPanelHelpers(unittest.TestCase):

    def test_daemon_status_offline(self):
        s = _get_daemon_status({"available": False})
        self.assertFalse(s["online"])
        self.assertEqual(s["model"], "—")

    def test_daemon_status_online(self):
        s = _get_daemon_status({
            "active_model": "Nexus", "quantization": "Q4_K_M",
            "gaming_mode": False, "seconds_since_last_use": 10,
        })
        self.assertTrue(s["online"])
        self.assertEqual(s["model"], "Nexus")
        self.assertEqual(s["quant"], "Q4_K_M")

    def test_daemon_status_empty_response(self):
        s = _get_daemon_status({})
        self.assertFalse(s["online"])  # empty dict → treat as offline

    def test_hive_models_count(self):
        models = _get_hive_models()
        self.assertEqual(len(models), 4)

    def test_hive_model_names(self):
        names = [m["name"] for m in _get_hive_models()]
        for expected in ("Nexus", "Bolt", "Nova", "Eye"):
            self.assertIn(expected, names)

    def test_get_npu_status_returns_dict(self):
        status = _get_npu_status()
        self.assertIn("available", status)
        self.assertIn("device", status)
        self.assertIsInstance(status["available"], bool)


# ===========================================================================
# about_panel
# ===========================================================================

class TestAboutPanelHelpers(unittest.TestCase):

    def test_kernel_version_is_string(self):
        ver = _get_kernel_version()
        self.assertIsInstance(ver, str)
        self.assertGreater(len(ver), 0)

    def test_hardware_info_keys(self):
        hw = _get_hardware_info()
        for key in ("cpu", "ram_gb", "igpu", "gpu", "npu", "storage_gb"):
            self.assertIn(key, hw)

    def test_hardware_info_ram_is_numeric(self):
        hw = _get_hardware_info()
        self.assertIsInstance(hw["ram_gb"], float)

    def test_export_report_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.txt")
            result = _export_report(path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            content = open(path).read()
            self.assertIn("Luminos", content)
            self.assertIn("Kernel", content)

    def test_format_uptime(self):
        from gui.settings.panels.about_panel import _format_uptime
        self.assertEqual(_format_uptime(3661), "1h 1m")
        self.assertEqual(_format_uptime(0),    "0h 0m")


if __name__ == "__main__":
    unittest.main()
