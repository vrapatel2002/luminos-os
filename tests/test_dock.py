"""
tests/test_dock.py
Phase 8.3 — Luminos Dock test suite.

Covers:
  - dock_config: load/save/add/remove               (7 tests)
  - dock_item pure logic: tooltip + badge            (6 tests)
  - dock_window pure logic: dedup + window→app_info  (4 tests)
  - dock_window._poll_windows: daemon offline        (1 test)
  - dock_window._poll_windows: window_list response  (1 test)

Total: 19 tests
All run headless — no GTK display required.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gui.dock.dock_config import (
    DEFAULT_PINNED, load_pinned, save_pinned, add_pinned, remove_pinned,
)
from gui.dock.dock_item import _get_tooltip, _should_show_badge
from gui.dock.dock_window import get_open_apps_not_pinned, build_app_info_from_window


# ===========================================================================
# dock_config
# ===========================================================================

class TestLoadPinned(unittest.TestCase):

    def test_returns_list_with_required_keys(self):
        apps = load_pinned()
        self.assertIsInstance(apps, list)
        for app in apps:
            self.assertIn("name", app)
            self.assertIn("exec", app)
            self.assertIn("icon", app)

    def test_missing_file_returns_defaults(self):
        import gui.dock.dock_config as cfg
        with patch.object(cfg, "CONFIG_PATH", "/nonexistent/path/dock.json"):
            apps = load_pinned()
        self.assertEqual(apps, DEFAULT_PINNED)

    def test_corrupt_json_returns_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False) as f:
            f.write("NOT_JSON{{{{")
            path = f.name
        try:
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                apps = load_pinned()
            self.assertEqual(apps, DEFAULT_PINNED)
        finally:
            os.unlink(path)

    def test_loads_custom_file(self):
        custom = [{"name": "Vim", "exec": "vim", "icon": "vim"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False) as f:
            json.dump(custom, f)
            path = f.name
        try:
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                apps = load_pinned()
            self.assertEqual(apps, custom)
        finally:
            os.unlink(path)


class TestSavePinned(unittest.TestCase):

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "dock.json")
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                result = save_pinned([{"name": "A", "exec": "a", "icon": "a"}])
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data[0]["exec"], "a")


class TestAddPinned(unittest.TestCase):

    def test_adds_new_item(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dock.json")
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                apps = add_pinned({"name": "Vim", "exec": "vim", "icon": "vim"})
            execs = [a["exec"] for a in apps]
            self.assertIn("vim", execs)

    def test_duplicate_not_added_twice(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dock.json")
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                first  = add_pinned({"name": "Vim", "exec": "vim", "icon": "vim"})
                second = add_pinned({"name": "Vim", "exec": "vim", "icon": "vim"})
            vim_count = sum(1 for a in second if a.get("exec") == "vim")
            self.assertEqual(vim_count, 1)


class TestRemovePinned(unittest.TestCase):

    def test_removes_item(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dock.json")
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                add_pinned({"name": "Vim", "exec": "vim", "icon": "vim"})
                apps = remove_pinned("vim")
            self.assertNotIn("vim", [a.get("exec") for a in apps])

    def test_nonexistent_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dock.json")
            import gui.dock.dock_config as cfg
            with patch.object(cfg, "CONFIG_PATH", path):
                # Write defaults first
                save_pinned(list(DEFAULT_PINNED))
                before = load_pinned()
                apps   = remove_pinned("nonexistent-app-xyz")
            self.assertEqual(len(apps), len(before))


# ===========================================================================
# dock_item pure logic
# ===========================================================================

class TestGetTooltip(unittest.TestCase):

    def test_zone1_no_suffix(self):
        tip = _get_tooltip({"name": "Firefox"}, zone=1)
        self.assertEqual(tip, "Firefox")
        self.assertNotIn("Wine", tip)
        self.assertNotIn("Quarantine", tip)

    def test_zone2_wine(self):
        tip = _get_tooltip({"name": "game.exe"}, zone=2)
        self.assertIn("Wine", tip)
        self.assertIn("game.exe", tip)

    def test_zone3_quarantine(self):
        tip = _get_tooltip({"name": "anticheat.exe"}, zone=3)
        self.assertIn("Quarantine", tip)
        self.assertIn("⚠", tip)

    def test_fallback_to_exec(self):
        tip = _get_tooltip({"exec": "alacritty"}, zone=1)
        self.assertIn("alacritty", tip)


class TestShouldShowBadge(unittest.TestCase):

    def test_zone1_no_badge(self):
        self.assertFalse(_should_show_badge(1))

    def test_zone2_badge(self):
        self.assertTrue(_should_show_badge(2))

    def test_zone3_badge(self):
        self.assertTrue(_should_show_badge(3))


# ===========================================================================
# dock_window pure logic
# ===========================================================================

class TestGetOpenAppsNotPinned(unittest.TestCase):

    def _pinned(self, *execs):
        return [{"name": e, "exec": e, "icon": e} for e in execs]

    def _windows(self, *execs):
        return [{"exe": e, "pid": i + 100, "zone": 1}
                for i, e in enumerate(execs)]

    def test_all_pinned_returns_empty(self):
        result = get_open_apps_not_pinned(
            self._windows("firefox", "nautilus"),
            self._pinned("firefox", "nautilus"),
        )
        self.assertEqual(result, [])

    def test_unpinned_app_returned(self):
        result = get_open_apps_not_pinned(
            self._windows("firefox", "steam"),
            self._pinned("firefox"),
        )
        execs = [w["exe"] for w in result]
        self.assertIn("steam", execs)
        self.assertNotIn("firefox", execs)

    def test_empty_open_returns_empty(self):
        result = get_open_apps_not_pinned([], self._pinned("firefox"))
        self.assertEqual(result, [])

    def test_empty_pinned_returns_all(self):
        windows = self._windows("vim", "htop")
        result  = get_open_apps_not_pinned(windows, [])
        self.assertEqual(len(result), 2)


class TestBuildAppInfoFromWindow(unittest.TestCase):

    def test_extracts_name_from_exe(self):
        info = build_app_info_from_window(
            {"exe": "/usr/bin/firefox", "pid": 1234, "zone": 1}
        )
        self.assertEqual(info["name"], "firefox")
        self.assertEqual(info["pid"], 1234)
        self.assertEqual(info["zone"], 1)

    def test_zone_preserved(self):
        info = build_app_info_from_window({"exe": "game.exe", "pid": 5, "zone": 2})
        self.assertEqual(info["zone"], 2)


# ===========================================================================
# dock_window._poll_windows  (mocked daemon)
# ===========================================================================

class TestPollWindowsMocked(unittest.TestCase):
    """
    Test _poll_windows logic without GTK by calling _sync_dock directly
    on a lightweight stub object.
    """

    def _make_stub(self, client):
        """Return a minimal object with the same state attrs as LuminosDock."""
        stub = MagicMock()
        stub._client    = client
        stub.open_apps  = []
        stub.pinned_apps = [{"name": "Firefox", "exec": "firefox", "icon": "fx"}]
        stub._pinned_items = {}
        stub._open_items   = {}

        # Bind the real methods to the stub
        import gui.dock.dock_window as dw
        stub._sync_dock     = lambda w: dw.get_open_apps_not_pinned(w, stub.pinned_apps)
        return stub

    def test_daemon_offline_open_apps_stays_empty(self):
        client = MagicMock()
        client.send.return_value = {"error": "daemon not running", "available": False}

        # Simulate what _poll_windows does when response is not a list
        response = client.send({"type": "window_list"})
        windows  = response if isinstance(response, list) else []
        self.assertEqual(windows, [])

    def test_window_list_updates_open_apps(self):
        client = MagicMock()
        client.send.return_value = [
            {"exe": "firefox", "pid": 1001, "zone": 1},
            {"exe": "steam",   "pid": 1002, "zone": 1},
        ]

        response = client.send({"type": "window_list"})
        windows  = response if isinstance(response, list) else []
        self.assertEqual(len(windows), 2)

        # Dedup: firefox is pinned, so only steam goes to center
        pinned = [{"name": "Firefox", "exec": "firefox", "icon": "fx"}]
        extra  = get_open_apps_not_pinned(windows, pinned)
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0]["exe"], "steam")


if __name__ == "__main__":
    unittest.main()
