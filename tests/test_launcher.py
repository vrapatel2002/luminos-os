"""
tests/test_launcher.py
Phase 8.5 — App Launcher test suite.

Covers:
  - app_scanner: scan, cache, parse, predict_zone, search  (10 tests)
  - launch_history: add/get/clear/max/dedup                 (5 tests)
  - app_result_item pure logic: display name, zone hint     (4 tests)
  - launcher.__init__: toggle headless                      (1 test)

Total: 20 tests
All run headless — no GTK display required.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import gui.launcher.app_scanner as scanner_mod
from gui.launcher.app_scanner import (
    _parse_desktop_file, scan_applications,
    predict_zone, search_apps,
)
import gui.launcher.launch_history as history_mod
from gui.launcher.launch_history import (
    add_to_history, get_recent, clear_history, MAX_HISTORY,
)
from gui.launcher.app_result_item import _get_display_name, _get_zone_hint
import gui.launcher as launcher_pkg


# ===========================================================================
# app_scanner
# ===========================================================================

class TestScanApplications(unittest.TestCase):

    def setUp(self):
        # Reset cache before each test
        scanner_mod._cache      = None
        scanner_mod._cache_time = 0.0

    def test_no_crash_no_desktop_files(self):
        """scan_applications() must not raise even if no .desktop files exist."""
        with patch.object(scanner_mod, "SEARCH_PATHS", ["/nonexistent/path/xyz"]):
            result = scan_applications()
        self.assertIsInstance(result, list)

    def test_caching_returns_same_object(self):
        """Second call within TTL returns the exact same list object."""
        with patch.object(scanner_mod, "SEARCH_PATHS", ["/nonexistent"]):
            first  = scan_applications()
            second = scan_applications()
        self.assertIs(first, second)

    def test_cache_invalidated_after_ttl(self):
        """After TTL expires, a fresh scan is performed."""
        with patch.object(scanner_mod, "SEARCH_PATHS", ["/nonexistent"]):
            first = scan_applications()
        # Force cache to look stale
        scanner_mod._cache_time = 0.0
        with patch.object(scanner_mod, "SEARCH_PATHS", ["/nonexistent"]):
            second = scan_applications()
        # Both are empty lists — different objects after rescan
        self.assertIsNot(first, second)


class TestParseDesktopFile(unittest.TestCase):

    def test_parses_valid_desktop_file(self):
        content = (
            "[Desktop Entry]\n"
            "Name=TestApp\n"
            "Exec=testapp %F\n"
            "Icon=test-icon\n"
            "Comment=A great test app\n"
            "Categories=Utility;Science;\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".desktop", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        try:
            result = _parse_desktop_file(path)
            self.assertIsNotNone(result)
            self.assertEqual(result["name"], "TestApp")
            self.assertEqual(result["exec"], "testapp %F")
            self.assertEqual(result["icon"], "test-icon")
            self.assertEqual(result["comment"], "A great test app")
            self.assertIn("Utility", result["categories"])
        finally:
            os.unlink(path)

    def test_nodisplay_skipped(self):
        content = "[Desktop Entry]\nName=Hidden\nExec=hidden\nNoDisplay=true\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".desktop", delete=False
        ) as f:
            f.write(content)
            path = f.name
        try:
            self.assertIsNone(_parse_desktop_file(path))
        finally:
            os.unlink(path)

    def test_missing_name_skipped(self):
        content = "[Desktop Entry]\nExec=no-name-app\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".desktop", delete=False
        ) as f:
            f.write(content)
            path = f.name
        try:
            self.assertIsNone(_parse_desktop_file(path))
        finally:
            os.unlink(path)


class TestPredictZone(unittest.TestCase):

    def test_exe_in_exec_returns_zone2(self):
        app = {"name": "Game", "exec": "wine game.exe"}
        self.assertEqual(predict_zone(app), 2)

    def test_explicit_exe_extension_returns_zone2(self):
        app = {"name": "App", "exec": "/home/user/app.exe"}
        self.assertEqual(predict_zone(app), 2)

    def test_native_binary_returns_zone1(self):
        app = {"name": "Firefox", "exec": "firefox %U"}
        self.assertEqual(predict_zone(app), 1)

    def test_empty_exec_returns_zone1(self):
        app = {"name": "Broken", "exec": ""}
        self.assertEqual(predict_zone(app), 1)


class TestSearchApps(unittest.TestCase):

    _APPS = [
        {"name": "Firefox", "exec": "firefox",   "icon": "firefox",
         "comment": "Web browser",  "categories": ["Network"]},
        {"name": "Files",   "exec": "nautilus",  "icon": "nautilus",
         "comment": "File manager", "categories": ["System"]},
        {"name": "Terminal","exec": "alacritty", "icon": "terminal",
         "comment": "Fast terminal emulator", "categories": ["Utility"]},
    ]

    def test_empty_query_returns_empty(self):
        self.assertEqual(search_apps("", self._APPS), [])

    def test_empty_apps_returns_empty(self):
        self.assertEqual(search_apps("firefox", []), [])

    def test_name_match(self):
        results = search_apps("fire", self._APPS)
        names = [r["name"] for r in results]
        self.assertIn("Firefox", names)

    def test_case_insensitive(self):
        results = search_apps("FIRE", self._APPS)
        names = [r["name"] for r in results]
        self.assertIn("Firefox", names)

    def test_name_scores_higher_than_comment(self):
        # "term" matches Terminal's name AND comment contains "emulator"
        # but "term" in name → higher score
        apps = [
            {"name": "Terminal", "exec": "term", "comment": "",
             "categories": [], "icon": "term"},
            {"name": "Other", "exec": "other", "comment": "has term in it",
             "categories": [], "icon": "other"},
        ]
        results = search_apps("term", apps)
        self.assertEqual(results[0]["name"], "Terminal")

    def test_max_12_results(self):
        many_apps = [
            {"name": f"App{i}", "exec": f"app{i}", "icon": "",
             "comment": "test app", "categories": []}
            for i in range(20)
        ]
        results = search_apps("app", many_apps)
        self.assertLessEqual(len(results), 12)


# ===========================================================================
# launch_history
# ===========================================================================

class TestLaunchHistory(unittest.TestCase):

    def _patched(self, tmpdir):
        """Return context manager that patches HISTORY_PATH into tmpdir."""
        path = os.path.join(tmpdir, "launch_history.json")
        return patch.object(history_mod, "HISTORY_PATH", path)

    def test_add_appears_in_recent(self):
        with tempfile.TemporaryDirectory() as d:
            with self._patched(d):
                add_to_history({"name": "Firefox", "exec": "firefox"})
                recent = get_recent()
        execs = [r["exec"] for r in recent]
        self.assertIn("firefox", execs)

    def test_duplicate_moved_to_top(self):
        with tempfile.TemporaryDirectory() as d:
            with self._patched(d):
                add_to_history({"name": "Firefox", "exec": "firefox"})
                add_to_history({"name": "Terminal","exec": "alacritty"})
                add_to_history({"name": "Firefox", "exec": "firefox"})
                recent = get_recent()
        self.assertEqual(recent[0]["exec"], "firefox")
        count = sum(1 for r in recent if r["exec"] == "firefox")
        self.assertEqual(count, 1)

    def test_get_recent_respects_n(self):
        with tempfile.TemporaryDirectory() as d:
            with self._patched(d):
                for i in range(10):
                    add_to_history({"name": f"App{i}", "exec": f"app{i}"})
                recent = get_recent(3)
        self.assertLessEqual(len(recent), 3)

    def test_clear_history(self):
        with tempfile.TemporaryDirectory() as d:
            with self._patched(d):
                add_to_history({"name": "Firefox", "exec": "firefox"})
                clear_history()
                recent = get_recent()
        self.assertEqual(recent, [])

    def test_max_history_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            with self._patched(d):
                for i in range(MAX_HISTORY + 5):
                    add_to_history({"name": f"App{i}", "exec": f"app{i}"})
                recent = get_recent(100)
        self.assertLessEqual(len(recent), MAX_HISTORY)


# ===========================================================================
# app_result_item pure logic
# ===========================================================================

class TestGetDisplayName(unittest.TestCase):

    def test_short_name_unchanged(self):
        self.assertEqual(_get_display_name("Firefox"), "Firefox")

    def test_exactly_12_unchanged(self):
        name = "A" * 12
        self.assertEqual(_get_display_name(name), name)

    def test_long_name_truncated(self):
        name   = "VeryLongApplicationName"
        result = _get_display_name(name)
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(len(result), 13)   # 12 chars + ellipsis


class TestGetZoneHint(unittest.TestCase):

    def test_zone1_empty(self):
        self.assertEqual(_get_zone_hint(1), "")

    def test_zone2_wine(self):
        self.assertIn("Wine", _get_zone_hint(2))

    def test_zone3_vm(self):
        hint = _get_zone_hint(3)
        self.assertIn("⚠", hint)
        self.assertIn("VM", hint)


# ===========================================================================
# launcher singleton (headless)
# ===========================================================================

class TestToggleLauncherHeadless(unittest.TestCase):

    def test_toggle_no_crash_headless(self):
        """toggle_launcher() must not raise even without a display."""
        try:
            launcher_pkg.toggle_launcher()
        except Exception as e:
            self.fail(f"toggle_launcher() raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
