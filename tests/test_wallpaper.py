"""
tests/test_wallpaper.py
Phase 8.7 — Video Wallpaper Engine test suite.

Covers:
  - wallpaper_config: load, save, round-trip, file scan     (4 tests)
  - vaapi_check: check_vaapi, get_decode_flags               (2 tests)
  - swww_controller: is_swww_running, set_color_wallpaper    (2 tests)
  - video_wallpaper: _build_mpv_cmd, is_running              (4 tests)
  - wallpaper_manager: apply color, apply saves, lock/unlock,
                       get_status                            (5 tests)
  - daemon routing: wallpaper_set, wallpaper_status           (2 tests)

Total: 19 tests
All headless — no display required.
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

import gui.wallpaper.wallpaper_config as cfg_mod
from gui.wallpaper.wallpaper_config import (
    load_config, save_config, get_wallpaper_files, DEFAULT_CONFIG,
)
from gui.wallpaper.vaapi_check import check_vaapi, get_decode_flags
from gui.wallpaper.swww_controller import is_swww_running, set_color_wallpaper
from gui.wallpaper.video_wallpaper import VideoWallpaper
from gui.wallpaper.wallpaper_manager import WallpaperManager


# ===========================================================================
# wallpaper_config
# ===========================================================================

class TestLoadConfig(unittest.TestCase):

    def test_missing_file_returns_defaults(self):
        with patch.object(cfg_mod, "CONFIG_PATH", "/nonexistent/path/wallpaper.json"):
            result = load_config()
        self.assertIsInstance(result, dict)
        for key in DEFAULT_CONFIG:
            self.assertIn(key, result)

    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "wallpaper.json")
            with patch.object(cfg_mod, "CONFIG_PATH", path):
                ok = save_config(DEFAULT_CONFIG)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(path))

    def test_load_after_save_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "wallpaper.json")
            custom = {**DEFAULT_CONFIG, "type": "image", "value": "/tmp/test.png"}
            with patch.object(cfg_mod, "CONFIG_PATH", path):
                save_config(custom)
                result = load_config()
            self.assertEqual(result["type"],  "image")
            self.assertEqual(result["value"], "/tmp/test.png")

    def test_get_wallpaper_files_no_crash_missing_dirs(self):
        with patch.object(cfg_mod, "WALLPAPER_DIRS", ["/nonexistent/wallpapers"]):
            files = get_wallpaper_files()
        self.assertIsInstance(files, list)

    def test_get_wallpaper_files_scans_real_dir(self):
        with tempfile.TemporaryDirectory() as d:
            # Create one image and one video stub
            open(os.path.join(d, "bg.jpg"), "w").close()
            open(os.path.join(d, "loop.mp4"), "w").close()
            with patch.object(cfg_mod, "WALLPAPER_DIRS", [d]):
                files = get_wallpaper_files()
        types = {f["type"] for f in files}
        names = {f["name"] for f in files}
        self.assertIn("image", types)
        self.assertIn("video", types)
        self.assertIn("bg.jpg",  names)
        self.assertIn("loop.mp4", names)


# ===========================================================================
# vaapi_check
# ===========================================================================

class TestCheckVaapi(unittest.TestCase):

    def test_returns_correct_shape(self):
        result = check_vaapi()
        self.assertIn("available", result)
        self.assertIn("device",   result)
        self.assertIn("codecs",   result)
        self.assertIn("driver",   result)
        self.assertIsInstance(result["available"], bool)
        self.assertIsInstance(result["codecs"],    list)

    def test_no_crash_if_vainfo_missing(self):
        import subprocess
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = check_vaapi()
        self.assertFalse(result["available"])

    def test_get_decode_flags_returns_list(self):
        flags = get_decode_flags()
        self.assertIsInstance(flags, list)
        self.assertTrue(len(flags) > 0)

    def test_decode_flags_vaapi_path(self):
        with patch("gui.wallpaper.vaapi_check.check_vaapi",
                   return_value={"available": True, "codecs": ["H264"],
                                 "device": "/dev/dri/renderD128", "driver": "radeonsi"}):
            flags = get_decode_flags()
        self.assertIn("--hwdec=vaapi", flags)

    def test_decode_flags_cpu_fallback(self):
        with patch("gui.wallpaper.vaapi_check.check_vaapi",
                   return_value={"available": False, "codecs": [],
                                 "device": None, "driver": None}):
            flags = get_decode_flags()
        self.assertNotIn("--hwdec=vaapi", flags)
        self.assertIn("--vo=gpu", flags)


# ===========================================================================
# swww_controller
# ===========================================================================

class TestSwwwController(unittest.TestCase):

    def test_is_swww_running_returns_bool(self):
        result = is_swww_running()
        self.assertIsInstance(result, bool)

    def test_set_color_wallpaper_swww_missing_no_crash(self):
        """If swww is not installed, must return success=False without raising."""
        import subprocess
        with patch("gui.wallpaper.swww_controller.is_swww_running", return_value=False), \
             patch("gui.wallpaper.swww_controller.subprocess.Popen",
                   side_effect=FileNotFoundError):
            result = set_color_wallpaper("#1c1c1e")
        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])

    def test_set_color_wallpaper_invalid_hex_no_crash(self):
        result = set_color_wallpaper("not-a-color")
        self.assertFalse(result["success"])
        self.assertIn("error", result)


# ===========================================================================
# video_wallpaper
# ===========================================================================

class TestBuildMpvCmd(unittest.TestCase):

    def _cmd(self, loop=True, mute=True, speed=1.0) -> list:
        vw = VideoWallpaper()
        config = {
            "video_loop":  loop,
            "video_mute":  mute,
            "video_speed": speed,
        }
        with patch("gui.wallpaper.vaapi_check.check_vaapi",
                   return_value={"available": False, "codecs": [],
                                 "device": None, "driver": None}):
            return vw._build_mpv_cmd("/tmp/test.mp4", config)

    def test_path_in_cmd(self):
        cmd = self._cmd()
        self.assertIn("/tmp/test.mp4", cmd)

    def test_loop_flag_present_when_loop_true(self):
        cmd = self._cmd(loop=True)
        self.assertIn("--loop", cmd)

    def test_loop_flag_absent_when_loop_false(self):
        cmd = self._cmd(loop=False)
        self.assertNotIn("--loop", cmd)

    def test_no_audio_when_mute_true(self):
        cmd = self._cmd(mute=True)
        self.assertIn("--no-audio", cmd)
        self.assertNotIn("--audio", cmd)

    def test_audio_when_mute_false(self):
        cmd = self._cmd(mute=False)
        self.assertIn("--audio", cmd)
        self.assertNotIn("--no-audio", cmd)

    def test_no_empty_strings_in_cmd(self):
        cmd = self._cmd()
        self.assertNotIn("", cmd)


class TestVideoWallpaperIsRunning(unittest.TestCase):

    def test_is_running_no_process_false(self):
        vw = VideoWallpaper()
        self.assertFalse(vw.is_running())


# ===========================================================================
# wallpaper_manager
# ===========================================================================

class TestWallpaperManagerApply(unittest.TestCase):

    def _make_manager(self, tmpdir):
        """Return a WallpaperManager with CONFIG_PATH redirected to tmpdir."""
        path = os.path.join(tmpdir, "wallpaper.json")
        with patch.object(cfg_mod, "CONFIG_PATH", path):
            mgr = WallpaperManager()
        return mgr, path

    def test_apply_color_returns_applied_color(self):
        with tempfile.TemporaryDirectory() as d:
            mgr, _ = self._make_manager(d)
            with patch("gui.wallpaper.wallpaper_manager.set_color_wallpaper",
                       return_value={"success": True, "error": None}):
                result = mgr.apply({"type": "color", "value": "#ff0000"})
        self.assertEqual(result["applied"], "color")

    def test_apply_saves_config_to_disk(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "wallpaper.json")
            with patch.object(cfg_mod, "CONFIG_PATH", path):
                mgr = WallpaperManager()
                with patch("gui.wallpaper.wallpaper_manager.set_color_wallpaper",
                           return_value={"success": True}):
                    mgr.apply({**DEFAULT_CONFIG, "type": "color", "value": "#aabbcc"})
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                saved = json.load(f)
            self.assertEqual(saved["value"], "#aabbcc")

    def test_on_lock_no_video_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            mgr, _ = self._make_manager(d)
            mgr.on_lock()   # no video running — must not raise
        self.assertTrue(mgr.locked)

    def test_on_unlock_no_video_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            mgr, _ = self._make_manager(d)
            with patch("gui.wallpaper.wallpaper_manager.set_color_wallpaper",
                       return_value={"success": True}):
                mgr.on_unlock()
        self.assertFalse(mgr.locked)

    def test_get_status_all_keys_present(self):
        with tempfile.TemporaryDirectory() as d:
            mgr, _ = self._make_manager(d)
            with patch("gui.wallpaper.wallpaper_manager.check_vaapi",
                       return_value={"available": False}):
                status = mgr.get_status()
        for key in ("type", "value", "video_running", "video_paused", "vaapi", "locked"):
            self.assertIn(key, status)


# ===========================================================================
# daemon routing
# ===========================================================================

class TestDaemonWallpaperRouting(unittest.TestCase):

    def _route(self, message):
        """Import and call route_request with a dummy ModelManager."""
        sys.path.insert(0, os.path.join(SRC, ".."))
        from daemon.main import route_request
        mm = MagicMock()
        return route_request(message, mm)

    def test_wallpaper_set_response_shape(self):
        with patch("daemon.main._WALLPAPER_AVAILABLE", True), \
             patch("daemon.main._wall_status",
                   return_value={"type": "color", "value": "#000000",
                                 "video_running": False, "video_paused": False,
                                 "vaapi": False, "locked": False}), \
             patch("daemon.main._wall_apply",
                   return_value={"applied": "color"}):
            result = self._route({"type": "wallpaper_set",
                                  "wallpaper_type": "color", "value": "#ff0000"})
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("applied", result)

    def test_wallpaper_status_response_shape(self):
        with patch("daemon.main._WALLPAPER_AVAILABLE", True), \
             patch("daemon.main._wall_status",
                   return_value={"type": "color", "value": "#1c1c1e",
                                 "video_running": False, "video_paused": False,
                                 "vaapi": False, "locked": False}):
            result = self._route({"type": "wallpaper_status"})
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("type",  result)
        self.assertIn("value", result)

    def test_wallpaper_files_response_shape(self):
        with patch("daemon.main._WALLPAPER_AVAILABLE", True), \
             patch("daemon.main._wall_files", return_value=[]):
            result = self._route({"type": "wallpaper_files"})
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("files", result)
        self.assertIsInstance(result["files"], list)


if __name__ == "__main__":
    unittest.main()
