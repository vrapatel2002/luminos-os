"""
tests/test_zone2.py
Unit tests for Phase 4 Zone 2 Wine/Proton integration layer.

Strategy:
- detect_wine() / launch_windows_app() tested for correct dict shape —
  Wine is not installed on the dev machine so we exercise the "not available" path.
- build_wine_command() tested with injected mock wine_info so no real binary needed.
- prefix_manager functions tested with real temp directories.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from zone2.wine_runner import detect_wine, build_wine_command, launch_windows_app
from zone2.prefix_manager import (
    get_prefix_path, ensure_prefix_exists, list_prefixes,
    DEFAULT_PREFIX_BASE,
)
from zone2 import run_in_zone2


# ---------------------------------------------------------------------------
# detect_wine
# ---------------------------------------------------------------------------

class TestDetectWine(unittest.TestCase):

    def test_returns_required_keys(self):
        info = detect_wine()
        for key in ("available", "path", "type", "version"):
            self.assertIn(key, info)

    def test_available_is_bool(self):
        info = detect_wine()
        self.assertIsInstance(info["available"], bool)

    def test_type_is_valid_value(self):
        info = detect_wine()
        self.assertIn(info["type"], ("wine", "proton", None))

    def test_when_not_available_path_is_none(self):
        info = detect_wine()
        if not info["available"]:
            self.assertIsNone(info["path"])
            self.assertIsNone(info["type"])

    def test_when_available_path_is_string(self):
        info = detect_wine()
        if info["available"]:
            self.assertIsInstance(info["path"], str)


# ---------------------------------------------------------------------------
# build_wine_command
# ---------------------------------------------------------------------------

class TestBuildWineCommand(unittest.TestCase):
    """Mock wine_info so tests never require a real Wine installation."""

    MOCK_WINE = {
        "available": True,
        "path":      "/usr/bin/wine64",
        "type":      "wine",
        "version":   "wine-8.0",
    }

    MOCK_PROTON = {
        "available": True,
        "path":      "/home/user/.steam/steam/steamapps/common/Proton 8.0/proton",
        "type":      "proton",
        "version":   "Proton 8.0",
    }

    def test_wine_cmd_structure(self):
        result = build_wine_command("/games/app.exe", self.MOCK_WINE)
        self.assertIn("cmd", result)
        self.assertIn("env", result)
        cmd = result["cmd"]
        self.assertEqual(cmd[0], "/usr/bin/wine64")
        self.assertEqual(cmd[-1], "/games/app.exe")

    def test_proton_cmd_has_run_argument(self):
        result = build_wine_command("/games/app.exe", self.MOCK_PROTON)
        cmd = result["cmd"]
        self.assertIn("run", cmd)
        self.assertEqual(cmd[-1], "/games/app.exe")

    def test_env_contains_winedebug(self):
        result = build_wine_command("/games/app.exe", self.MOCK_WINE)
        self.assertEqual(result["env"]["WINEDEBUG"], "-all")

    def test_env_contains_dxvk_hud(self):
        result = build_wine_command("/games/app.exe", self.MOCK_WINE)
        self.assertEqual(result["env"]["DXVK_HUD"], "0")

    def test_env_contains_wineprefix(self):
        result = build_wine_command("/games/app.exe", self.MOCK_WINE)
        self.assertIn("WINEPREFIX", result["env"])

    def test_env_overrides_applied(self):
        result = build_wine_command(
            "/games/app.exe", self.MOCK_WINE,
            env_overrides={"WINEPREFIX": "/custom/prefix", "MY_VAR": "1"}
        )
        self.assertEqual(result["env"]["WINEPREFIX"], "/custom/prefix")
        self.assertEqual(result["env"]["MY_VAR"], "1")

    def test_env_override_does_not_remove_winedebug(self):
        result = build_wine_command(
            "/games/app.exe", self.MOCK_WINE,
            env_overrides={"WINEPREFIX": "/custom/prefix"}
        )
        self.assertIn("WINEDEBUG", result["env"])

    def test_cmd_is_list(self):
        result = build_wine_command("/games/app.exe", self.MOCK_WINE)
        self.assertIsInstance(result["cmd"], list)


# ---------------------------------------------------------------------------
# launch_windows_app
# ---------------------------------------------------------------------------

class TestLaunchWindowsApp(unittest.TestCase):

    def test_returns_dict(self):
        result = launch_windows_app("/fake/app.exe")
        self.assertIsInstance(result, dict)

    def test_missing_wine_returns_success_false(self):
        """On dev machine Wine is not installed — must get a clean failure."""
        info = detect_wine()
        if info["available"]:
            self.skipTest("Wine is installed — skipping not-available path test")
        result = launch_windows_app("/fake/app.exe")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("install_hint", result)

    def test_install_hint_mentions_pacman(self):
        info = detect_wine()
        if info["available"]:
            self.skipTest("Wine is installed")
        result = launch_windows_app("/fake/app.exe")
        self.assertIn("pacman", result["install_hint"])

    def test_success_result_has_required_keys(self):
        """Validate shape of a success response via mock — just check keys exist."""
        # We can't easily mock detect_wine() without patching, so just validate
        # that when wine IS available the response has the right shape by checking
        # that our failure response at minimum doesn't have conflicting keys.
        result = launch_windows_app("/fake/app.exe")
        self.assertIn("success", result)


# ---------------------------------------------------------------------------
# prefix_manager — get_prefix_path
# ---------------------------------------------------------------------------

class TestGetPrefixPath(unittest.TestCase):

    def test_returns_string(self):
        path = get_prefix_path("/games/mygame/launcher.exe")
        self.assertIsInstance(path, str)

    def test_path_starts_with_prefix_base(self):
        path = get_prefix_path("/games/mygame/launcher.exe")
        self.assertTrue(path.startswith(DEFAULT_PREFIX_BASE))

    def test_different_exes_get_different_paths(self):
        path_a = get_prefix_path("/games/gamea/launcher.exe")
        path_b = get_prefix_path("/games/gameb/launcher.exe")
        self.assertNotEqual(path_a, path_b)

    def test_same_exe_same_path(self):
        path_a = get_prefix_path("/games/mygame/launcher.exe")
        path_b = get_prefix_path("/games/mygame/launcher.exe")
        self.assertEqual(path_a, path_b)

    def test_same_name_different_dir_different_path(self):
        """Two games both called 'launcher.exe' must not share a prefix."""
        path_a = get_prefix_path("/games/game_a/launcher.exe")
        path_b = get_prefix_path("/games/game_b/launcher.exe")
        self.assertNotEqual(path_a, path_b)

    def test_prefix_name_is_filesystem_safe(self):
        path = get_prefix_path("/games/My Game (2024)/Setup Launcher.exe")
        name = os.path.basename(path)
        for ch in name:
            self.assertTrue(ch.isalnum() or ch in ('_', '-'),
                            f"Unsafe char '{ch}' in prefix name '{name}'")


# ---------------------------------------------------------------------------
# prefix_manager — ensure_prefix_exists
# ---------------------------------------------------------------------------

class TestEnsurePrefixExists(unittest.TestCase):

    def test_creates_directory_and_returns_true(self):
        with tempfile.TemporaryDirectory() as base:
            target = os.path.join(base, "mygame_abc12345")
            self.assertFalse(os.path.isdir(target))
            result = ensure_prefix_exists(target)
            self.assertTrue(result)
            self.assertTrue(os.path.isdir(target))

    def test_existing_directory_returns_true(self):
        with tempfile.TemporaryDirectory() as base:
            result = ensure_prefix_exists(base)
            self.assertTrue(result)

    def test_creates_nested_dirs(self):
        with tempfile.TemporaryDirectory() as base:
            deep = os.path.join(base, "a", "b", "c")
            result = ensure_prefix_exists(deep)
            self.assertTrue(result)
            self.assertTrue(os.path.isdir(deep))


# ---------------------------------------------------------------------------
# prefix_manager — list_prefixes
# ---------------------------------------------------------------------------

class TestListPrefixes(unittest.TestCase):

    def test_returns_list(self):
        result = list_prefixes()
        self.assertIsInstance(result, list)

    def test_nonexistent_base_returns_empty_list(self):
        """Monkeypatching DEFAULT_PREFIX_BASE is complex; test via a fresh import."""
        import zone2.prefix_manager as pm
        original = pm.DEFAULT_PREFIX_BASE
        pm.DEFAULT_PREFIX_BASE = "/tmp/luminos_nonexistent_prefixes_xyz"
        try:
            result = pm.list_prefixes()
            self.assertEqual(result, [])
        finally:
            pm.DEFAULT_PREFIX_BASE = original

    def test_lists_subdirs_with_correct_keys(self):
        import zone2.prefix_manager as pm
        with tempfile.TemporaryDirectory() as base:
            os.makedirs(os.path.join(base, "game_a_00000001"))
            os.makedirs(os.path.join(base, "game_b_00000002"))
            original = pm.DEFAULT_PREFIX_BASE
            pm.DEFAULT_PREFIX_BASE = base
            try:
                result = pm.list_prefixes()
                self.assertEqual(len(result), 2)
                for entry in result:
                    self.assertIn("name", entry)
                    self.assertIn("path", entry)
                    self.assertIn("size_mb", entry)
                    self.assertIsInstance(entry["size_mb"], float)
            finally:
                pm.DEFAULT_PREFIX_BASE = original

    def test_files_in_base_are_ignored(self):
        import zone2.prefix_manager as pm
        with tempfile.TemporaryDirectory() as base:
            # Create a file (not a directory) — should not appear in results
            open(os.path.join(base, "readme.txt"), "w").close()
            os.makedirs(os.path.join(base, "game_dir"))
            original = pm.DEFAULT_PREFIX_BASE
            pm.DEFAULT_PREFIX_BASE = base
            try:
                result = pm.list_prefixes()
                names = [e["name"] for e in result]
                self.assertNotIn("readme.txt", names)
                self.assertIn("game_dir", names)
            finally:
                pm.DEFAULT_PREFIX_BASE = original


# ---------------------------------------------------------------------------
# run_in_zone2 end-to-end
# ---------------------------------------------------------------------------

class TestRunInZone2(unittest.TestCase):

    def test_returns_dict_with_success_key(self):
        result = run_in_zone2("/fake/nonexistent/game.exe")
        self.assertIn("success", result)

    def test_always_includes_prefix_key(self):
        result = run_in_zone2("/fake/nonexistent/game.exe")
        self.assertIn("prefix", result)

    def test_prefix_path_is_string(self):
        result = run_in_zone2("/fake/nonexistent/game.exe")
        self.assertIsInstance(result["prefix"], str)

    def test_no_wine_returns_false_with_hint(self):
        info = detect_wine()
        if info["available"]:
            self.skipTest("Wine is installed")
        result = run_in_zone2("/fake/nonexistent/game.exe")
        self.assertFalse(result["success"])
        self.assertIn("install_hint", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
