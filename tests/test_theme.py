"""
tests/test_theme.py
Unit tests for Phase 8.1 Luminos GUI Theme Foundation.

Strategy:
- colors.py: structural — key presence, type consistency.
- spacing.py: key presence, type correctness.
- gtk_css.py: content checks — no display server needed.
- mode_manager.py: logic tests with mocked datetime hour.
- icons.py: no-crash guarantee + shape checks.
- SVG files: existence checks.
"""

import datetime
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui.theme.colors      import DARK, LIGHT, get_colors
from gui.theme.spacing     import RADIUS, SPACING, SIZING, ANIMATION
from gui.theme.gtk_css     import generate_css
from gui.theme.mode_manager import ModeManager
from gui.theme.icons       import find_icon, get_system_icons


# Locate the luminos_icons directory relative to this file
_THEME_DIR   = os.path.join(os.path.dirname(__file__), '..', 'src', 'gui', 'theme')
_ICONS_DIR   = os.path.join(_THEME_DIR, 'luminos_icons')

_REQUIRED_COLOR_KEYS = [
    "bg_primary", "bg_secondary", "bg_tertiary",
    "surface", "surface_raised", "surface_overlay",
    "border", "border_strong",
    "text_primary", "text_secondary", "text_tertiary", "text_disabled",
    "accent_blue", "accent_blue_hover",
    "luminos_ai", "zone2_wine", "zone3_alert",
    "sentinel_safe", "sentinel_warn", "sentinel_danger",
    "success", "warning", "error", "info",
    "bar_bg", "dock_bg", "dock_item_hover",
]


# ---------------------------------------------------------------------------
# colors.py
# ---------------------------------------------------------------------------

class TestColors(unittest.TestCase):

    def test_dark_has_all_required_keys(self):
        for key in _REQUIRED_COLOR_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, DARK)

    def test_light_has_all_required_keys(self):
        for key in _REQUIRED_COLOR_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, LIGHT)

    def test_dark_and_light_have_same_keys(self):
        self.assertEqual(set(DARK.keys()), set(LIGHT.keys()))

    def test_all_color_values_are_strings(self):
        for key, val in DARK.items():
            with self.subTest(key=key):
                self.assertIsInstance(val, str)
        for key, val in LIGHT.items():
            with self.subTest(key=key):
                self.assertIsInstance(val, str)

    def test_get_colors_dark_true_returns_dark(self):
        self.assertIs(get_colors(dark=True), DARK)

    def test_get_colors_dark_false_returns_light(self):
        self.assertIs(get_colors(dark=False), LIGHT)

    def test_dark_bg_primary_differs_from_light(self):
        self.assertNotEqual(DARK["bg_primary"], LIGHT["bg_primary"])

    def test_dark_text_primary_is_white(self):
        self.assertEqual(DARK["text_primary"], "#ffffff")

    def test_light_text_primary_is_dark(self):
        self.assertEqual(LIGHT["text_primary"], "#1d1d1f")


# ---------------------------------------------------------------------------
# spacing.py
# ---------------------------------------------------------------------------

class TestSpacing(unittest.TestCase):

    def test_radius_has_required_keys(self):
        for key in ("small", "medium", "large", "xlarge", "pill"):
            self.assertIn(key, RADIUS)

    def test_spacing_has_required_keys(self):
        for key in ("xs", "sm", "md", "lg", "xl", "xxl"):
            self.assertIn(key, SPACING)

    def test_sizing_has_required_keys(self):
        for key in ("bar_height", "dock_height", "dock_icon", "launcher_width",
                    "launcher_height", "settings_w", "settings_h",
                    "icon_sm", "icon_md", "icon_lg", "icon_xl"):
            self.assertIn(key, SIZING)

    def test_animation_has_required_keys(self):
        for key in ("fast", "normal", "slow"):
            self.assertIn(key, ANIMATION)

    def test_all_radius_values_are_ints(self):
        for key, val in RADIUS.items():
            with self.subTest(key=key):
                self.assertIsInstance(val, int)

    def test_all_spacing_values_are_ints(self):
        for key, val in SPACING.items():
            with self.subTest(key=key):
                self.assertIsInstance(val, int)

    def test_animation_fast_less_than_normal(self):
        self.assertLess(ANIMATION["fast"], ANIMATION["normal"])

    def test_animation_normal_less_than_slow(self):
        self.assertLess(ANIMATION["normal"], ANIMATION["slow"])

    def test_radius_pill_is_large(self):
        self.assertGreater(RADIUS["pill"], 100)


# ---------------------------------------------------------------------------
# gtk_css.py
# ---------------------------------------------------------------------------

class TestGtkCss(unittest.TestCase):

    def test_returns_string(self):
        self.assertIsInstance(generate_css(dark=True), str)

    def test_dark_css_contains_luminos_panel(self):
        self.assertIn("luminos-panel", generate_css(dark=True))

    def test_dark_css_contains_backdrop_filter(self):
        self.assertIn("backdrop-filter", generate_css(dark=True))

    def test_dark_css_contains_luminos_bar(self):
        self.assertIn("luminos-bar", generate_css(dark=True))

    def test_dark_css_contains_luminos_dock(self):
        self.assertIn("luminos-dock", generate_css(dark=True))

    def test_dark_css_contains_zone_badge(self):
        self.assertIn("zone-badge-2", generate_css(dark=True))
        self.assertIn("zone-badge-3", generate_css(dark=True))

    def test_dark_css_contains_sentinel_classes(self):
        css = generate_css(dark=True)
        self.assertIn("sentinel-safe", css)
        self.assertIn("sentinel-danger", css)

    def test_dark_css_contains_scrollbar(self):
        self.assertIn("scrollbar", generate_css(dark=True))

    def test_light_css_returns_string(self):
        self.assertIsInstance(generate_css(dark=False), str)

    def test_light_and_dark_css_differ(self):
        self.assertNotEqual(generate_css(dark=True), generate_css(dark=False))

    def test_light_css_has_different_bg(self):
        dark_css  = generate_css(dark=True)
        light_css = generate_css(dark=False)
        # bg_primary differs between modes
        self.assertIn(DARK["bg_primary"],  dark_css)
        self.assertIn(LIGHT["bg_primary"], light_css)


# ---------------------------------------------------------------------------
# mode_manager.py
# ---------------------------------------------------------------------------

class TestModeManager(unittest.TestCase):

    def _make_mm_at_hour(self, hour: int) -> ModeManager:
        """Create a ModeManager whose auto detection runs at the given hour."""
        fixed_dt = datetime.datetime(2026, 3, 22, hour, 0, 0)
        with patch("gui.theme.mode_manager.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            mm = ModeManager()
        return mm

    def test_auto_at_hour_10_is_light(self):
        mm = self._make_mm_at_hour(10)
        self.assertFalse(mm.dark_mode)

    def test_auto_at_hour_21_is_dark(self):
        mm = self._make_mm_at_hour(21)
        self.assertTrue(mm.dark_mode)

    def test_auto_at_hour_6_is_light(self):
        mm = self._make_mm_at_hour(6)
        self.assertFalse(mm.dark_mode)

    def test_auto_at_hour_19_is_dark(self):
        mm = self._make_mm_at_hour(19)
        self.assertTrue(mm.dark_mode)

    def test_set_manual_dark_overrides_auto(self):
        mm = self._make_mm_at_hour(10)   # would be light
        mm.set_manual(True)
        self.assertTrue(mm.get_mode())

    def test_set_manual_light_overrides_auto(self):
        mm = self._make_mm_at_hour(21)   # would be dark
        mm.set_manual(False)
        self.assertFalse(mm.get_mode())

    def test_set_auto_clears_manual_override(self):
        mm = ModeManager()
        mm.set_manual(True)
        mm.set_auto()
        self.assertIsNone(mm.manual_override)

    def test_is_auto_true_initially(self):
        mm = ModeManager()
        self.assertTrue(mm.is_auto())

    def test_is_auto_false_after_set_manual(self):
        mm = ModeManager()
        mm.set_manual(True)
        self.assertFalse(mm.is_auto())

    def test_is_auto_true_after_set_auto(self):
        mm = ModeManager()
        mm.set_manual(True)
        mm.set_auto()
        self.assertTrue(mm.is_auto())

    def test_get_css_returns_non_empty_string(self):
        mm = ModeManager()
        css = mm.get_css()
        self.assertIsInstance(css, str)
        self.assertGreater(len(css), 100)

    def test_get_colors_returns_dict(self):
        mm = ModeManager()
        colors = mm.get_colors()
        self.assertIsInstance(colors, dict)
        self.assertIn("bg_primary", colors)


# ---------------------------------------------------------------------------
# icons.py
# ---------------------------------------------------------------------------

class TestIcons(unittest.TestCase):

    def test_find_icon_returns_str_or_none(self):
        result = find_icon("firefox")
        self.assertTrue(result is None or isinstance(result, str))

    def test_find_icon_does_not_raise(self):
        try:
            find_icon("this-icon-does-not-exist-at-all-xyz123")
        except Exception as e:
            self.fail(f"find_icon() raised: {e}")

    def test_find_icon_nonexistent_returns_none(self):
        result = find_icon("this-icon-does-not-exist-at-all-xyz123")
        self.assertIsNone(result)

    def test_get_system_icons_returns_dict(self):
        self.assertIsInstance(get_system_icons(), dict)

    def test_get_system_icons_has_wifi_on(self):
        self.assertIn("wifi_on", get_system_icons())

    def test_get_system_icons_has_luminos_ai(self):
        self.assertIn("luminos_ai", get_system_icons())

    def test_get_system_icons_has_all_required_keys(self):
        icons = get_system_icons()
        for key in ("wifi_on", "wifi_off", "bt_on", "bt_off",
                    "volume_high", "volume_mute",
                    "battery_full", "battery_low",
                    "power", "settings", "luminos_ai"):
            with self.subTest(key=key):
                self.assertIn(key, icons)

    def test_get_system_icons_does_not_raise(self):
        try:
            get_system_icons()
        except Exception as e:
            self.fail(f"get_system_icons() raised: {e}")


# ---------------------------------------------------------------------------
# SVG files
# ---------------------------------------------------------------------------

class TestSvgFiles(unittest.TestCase):

    _REQUIRED_SVGS = [
        "ai_idle.svg",
        "ai_active.svg",
        "ai_gaming.svg",
        "ai_offline.svg",
        "zone2_badge.svg",
        "zone3_badge.svg",
    ]

    def test_all_svg_files_exist(self):
        for name in self._REQUIRED_SVGS:
            with self.subTest(name=name):
                path = os.path.join(_ICONS_DIR, name)
                self.assertTrue(os.path.isfile(path), f"Missing SVG: {path}")

    def test_all_svg_files_contain_viewbox(self):
        for name in self._REQUIRED_SVGS:
            with self.subTest(name=name):
                path = os.path.join(_ICONS_DIR, name)
                if os.path.isfile(path):
                    with open(path) as f:
                        content = f.read()
                    self.assertIn("viewBox", content)

    def test_all_svg_files_nonempty(self):
        for name in self._REQUIRED_SVGS:
            with self.subTest(name=name):
                path = os.path.join(_ICONS_DIR, name)
                if os.path.isfile(path):
                    self.assertGreater(os.path.getsize(path), 0)


# ---------------------------------------------------------------------------
# theme __init__ (public exports)
# ---------------------------------------------------------------------------

class TestThemeInit(unittest.TestCase):

    def test_mode_singleton_is_mode_manager(self):
        import gui.theme as theme
        self.assertIsInstance(theme.mode, ModeManager)

    def test_dark_and_light_exported(self):
        import gui.theme as theme
        self.assertIsNotNone(theme.DARK)
        self.assertIsNotNone(theme.LIGHT)

    def test_generate_css_exported(self):
        import gui.theme as theme
        self.assertTrue(callable(theme.generate_css))

    def test_find_icon_exported(self):
        import gui.theme as theme
        self.assertTrue(callable(theme.find_icon))


if __name__ == '__main__':
    unittest.main(verbosity=2)
