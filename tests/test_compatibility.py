"""
test_compatibility.py
Tests for Phase 8.12 — Wine/Proton OS Integration.

Headless — no Wine or system packages required.
All filesystem-dependent tests use temporary directories.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from zone2 import compatibility_manager as cm
from zone2 import dxvk_manager as dm


# ---------------------------------------------------------------------------
# compatibility_manager — get_compat_status()
# ---------------------------------------------------------------------------

class TestGetCompatStatus(unittest.TestCase):

    def test_returns_correct_shape(self):
        """get_compat_status() always returns a dict with all required keys."""
        status = cm.get_compat_status()
        self.assertIn("wine64", status)
        self.assertIn("dxvk", status)
        self.assertIn("vkd3d", status)
        self.assertIn("vulkan", status)
        self.assertIn("system_prefix", status)
        self.assertIn("overall_ready", status)

    def test_wine64_shape(self):
        status = cm.get_compat_status()
        w = status["wine64"]
        self.assertIn("available", w)
        self.assertIn("path", w)
        self.assertIn("version", w)
        self.assertIn("source", w)

    def test_dxvk_shape(self):
        status = cm.get_compat_status()
        d = status["dxvk"]
        self.assertIn("available", d)
        self.assertIn("version", d)
        self.assertIn("dlls", d)
        self.assertIsInstance(d["dlls"], list)

    def test_vkd3d_shape(self):
        status = cm.get_compat_status()
        v = status["vkd3d"]
        self.assertIn("available", v)
        self.assertIn("version", v)

    def test_vulkan_shape(self):
        status = cm.get_compat_status()
        v = status["vulkan"]
        self.assertIn("available", v)
        self.assertIn("devices", v)
        self.assertIsInstance(v["devices"], list)

    def test_system_prefix_shape(self):
        status = cm.get_compat_status()
        sp = status["system_prefix"]
        self.assertIn("exists", sp)
        self.assertIn("path", sp)
        self.assertIn("initialized", sp)
        self.assertEqual(sp["path"], cm.SYSTEM_PREFIX)

    def test_no_crash_when_nothing_installed(self):
        """Should not raise even when Wine, DXVK, Vulkan are all absent."""
        with patch("os.path.isfile", return_value=False), \
             patch("os.path.isdir", return_value=False), \
             patch("subprocess.run", side_effect=FileNotFoundError):
            status = cm.get_compat_status()
        self.assertIsInstance(status, dict)

    def test_overall_ready_false_when_wine_not_found(self):
        """overall_ready must be False when no wine binary exists."""
        with patch.object(cm, "get_wine_path", return_value=None), \
             patch("subprocess.run", side_effect=FileNotFoundError):
            status = cm.get_compat_status()
        self.assertFalse(status["overall_ready"])

    def test_overall_ready_true_when_wine_found(self):
        with patch.object(cm, "get_wine_path", return_value="/usr/bin/wine64"), \
             patch("os.path.isfile", return_value=True), \
             patch("subprocess.run", side_effect=FileNotFoundError):
            status = cm.get_compat_status()
        self.assertTrue(status["overall_ready"])


# ---------------------------------------------------------------------------
# compatibility_manager — get_wine_path()
# ---------------------------------------------------------------------------

class TestGetWinePath(unittest.TestCase):

    def test_returns_none_when_no_wine(self):
        """Returns None when no wine binary exists — must not raise."""
        with patch("os.path.isfile", return_value=False):
            result = cm.get_wine_path()
        self.assertIsNone(result)

    def test_returns_compat_path_when_present(self):
        """Prefers COMPAT_BASE/wine/wine64 over /usr/bin/wine64."""
        compat_wine = os.path.join(cm.COMPAT_BASE, "wine", "wine64")
        def fake_isfile(path):
            return path == compat_wine
        with patch("os.path.isfile", side_effect=fake_isfile):
            result = cm.get_wine_path()
        self.assertEqual(result, compat_wine)

    def test_falls_back_to_usr_bin_wine64(self):
        """/usr/bin/wine64 is returned when COMPAT_BASE wine is absent."""
        def fake_isfile(path):
            return path == "/usr/bin/wine64"
        with patch("os.path.isfile", side_effect=fake_isfile):
            result = cm.get_wine_path()
        self.assertEqual(result, "/usr/bin/wine64")

    def test_falls_back_to_wine(self):
        """/usr/bin/wine is returned as last resort."""
        def fake_isfile(path):
            return path == "/usr/bin/wine"
        with patch("os.path.isfile", side_effect=fake_isfile):
            result = cm.get_wine_path()
        self.assertEqual(result, "/usr/bin/wine")

    def test_no_crash_no_wine(self):
        with patch("os.path.isfile", return_value=False):
            result = cm.get_wine_path()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# compatibility_manager — get_best_runner()
# ---------------------------------------------------------------------------

class TestGetBestRunner(unittest.TestCase):

    def _make_exe(self, content: bytes) -> str:
        """Write content to a temp file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".exe")
        os.write(fd, content)
        os.close(fd)
        self.addCleanup(os.unlink, path)
        return path

    def test_d3d12_recommends_vkd3d(self):
        """PE with d3d12 string → vkd3d=True recommended."""
        exe = self._make_exe(b"MZ\x00\x00" + b"d3d12.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertTrue(result["vkd3d"])
        self.assertFalse(result["dxvk"])
        self.assertIn("vkd3d", result["reason"].lower())

    def test_D3D12_uppercase_recommends_vkd3d(self):
        """Case-insensitive: D3D12 should also be detected."""
        exe = self._make_exe(b"MZ\x00\x00" + b"D3D12.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertTrue(result["vkd3d"])

    def test_d3d11_recommends_dxvk(self):
        """PE with d3d11 string → dxvk=True recommended."""
        exe = self._make_exe(b"MZ\x00\x00" + b"d3d11.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertTrue(result["dxvk"])
        self.assertFalse(result["vkd3d"])

    def test_d3d10_recommends_dxvk(self):
        """PE with d3d10 string → dxvk=True recommended."""
        exe = self._make_exe(b"MZ\x00\x00" + b"d3d10.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertTrue(result["dxvk"])

    def test_d3d9_recommends_dxvk(self):
        """PE with d3d9 string → dxvk=True recommended."""
        exe = self._make_exe(b"MZ\x00\x00" + b"d3d9.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertTrue(result["dxvk"])
        self.assertFalse(result["vkd3d"])

    def test_no_dx_imports_defaults_to_proton(self):
        """PE with no DX imports → dxvk=False, vkd3d=False, runner=proton."""
        exe = self._make_exe(b"MZ\x00\x00" + b"kernel32.dll\x00user32.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertFalse(result["dxvk"])
        self.assertFalse(result["vkd3d"])
        self.assertEqual(result["runner"], "proton")

    def test_d3d12_beats_d3d11_if_both_present(self):
        """d3d12 takes priority over d3d11 in the same binary."""
        exe = self._make_exe(b"MZ\x00\x00d3d12.dlld3d11.dll\x00")
        result = cm.get_best_runner(exe)
        self.assertTrue(result["vkd3d"])

    def test_missing_exe_returns_plain_wine(self):
        """Non-existent exe should return plain wine recommendation without crash."""
        result = cm.get_best_runner("/nonexistent/path/game.exe")
        self.assertIsInstance(result, dict)
        self.assertIn("runner", result)

    def test_result_has_required_keys(self):
        exe = self._make_exe(b"MZ")
        result = cm.get_best_runner(exe)
        self.assertIn("runner", result)
        self.assertIn("dxvk", result)
        self.assertIn("vkd3d", result)
        self.assertIn("reason", result)


# ---------------------------------------------------------------------------
# compatibility_manager — build_compat_env()
# ---------------------------------------------------------------------------

class TestBuildCompatEnv(unittest.TestCase):

    def _base_config(self, dxvk=False, vkd3d=False):
        return {"runner": "wine64", "dxvk": dxvk, "vkd3d": vkd3d, "reason": "test"}

    def test_wineprefix_in_returned_dict(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config())
        self.assertIn("WINEPREFIX", env)
        self.assertEqual(env["WINEPREFIX"], "/tmp/prefix")

    def test_winedebug_all_in_returned_dict(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config())
        self.assertEqual(env["WINEDEBUG"], "-all")

    def test_wineesync_enabled_by_default(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config())
        self.assertEqual(env["WINEESYNC"], "1")

    def test_winefsync_enabled_by_default(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config())
        self.assertEqual(env["WINEFSYNC"], "1")

    def test_winearch_win64(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config())
        self.assertEqual(env["WINEARCH"], "win64")

    def test_dxvk_hud_zero_by_default(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config(dxvk=True))
        self.assertIn("DXVK_HUD", env)
        self.assertEqual(env["DXVK_HUD"], "0")

    def test_dxvk_state_cache_path_set_when_dxvk_true(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config(dxvk=True))
        self.assertIn("DXVK_STATE_CACHE_PATH", env)

    def test_dxvk_state_cache_path_absent_when_dxvk_false(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config(dxvk=False))
        self.assertNotIn("DXVK_STATE_CACHE_PATH", env)

    def test_vkd3d_shader_cache_set_when_vkd3d_true(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config(vkd3d=True))
        self.assertIn("VKD3D_SHADER_CACHE_PATH", env)

    def test_vkd3d_shader_cache_absent_when_vkd3d_false(self):
        env = cm.build_compat_env("/tmp/prefix", self._base_config(vkd3d=False))
        self.assertNotIn("VKD3D_SHADER_CACHE_PATH", env)

    def test_returns_full_environment_dict(self):
        """Should include inherited env vars (e.g. PATH)."""
        env = cm.build_compat_env("/tmp/prefix", self._base_config())
        self.assertIn("PATH", env)


# ---------------------------------------------------------------------------
# compatibility_manager — ensure_app_prefix()
# ---------------------------------------------------------------------------

class TestEnsureAppPrefix(unittest.TestCase):

    def test_returns_path_string(self):
        """ensure_app_prefix() returns a string path — no crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe = os.path.join(tmpdir, "game.exe")
            with open(exe, "wb") as f:
                f.write(b"MZ")
            # Override USER_PREFIX_BASE to use temp dir so we don't write to ~
            with patch.object(cm, "USER_PREFIX_BASE", tmpdir):
                result = cm.ensure_app_prefix(exe)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_creates_prefix_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exe = os.path.join(tmpdir, "game.exe")
            with open(exe, "wb") as f:
                f.write(b"MZ")
            with patch.object(cm, "USER_PREFIX_BASE", os.path.join(tmpdir, "prefixes")):
                result = cm.ensure_app_prefix(exe)
            self.assertTrue(os.path.isdir(result))

    def test_no_crash_for_nonexistent_exe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(cm, "USER_PREFIX_BASE", tmpdir):
                result = cm.ensure_app_prefix("/nonexistent/game.exe")
        self.assertIsInstance(result, str)

    def test_deterministic_path(self):
        """Same exe always produces the same prefix path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe = os.path.join(tmpdir, "game.exe")
            with open(exe, "wb") as f:
                f.write(b"MZ")
            prefix_base = os.path.join(tmpdir, "prefixes")
            with patch.object(cm, "USER_PREFIX_BASE", prefix_base):
                p1 = cm.ensure_app_prefix(exe)
                p2 = cm.ensure_app_prefix(exe)
        self.assertEqual(p1, p2)


# ---------------------------------------------------------------------------
# dxvk_manager — is_dxvk_installed()
# ---------------------------------------------------------------------------

class TestIsDxvkInstalled(unittest.TestCase):

    def test_returns_false_when_no_prefix(self):
        """is_dxvk_installed() with a non-existent prefix → False, no crash."""
        result = dm.is_dxvk_installed("/nonexistent/prefix")
        self.assertFalse(result)

    def test_returns_false_when_prefix_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = dm.is_dxvk_installed(tmpdir)
        self.assertFalse(result)

    def test_returns_false_when_system32_missing_dlls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sys32 = os.path.join(tmpdir, "drive_c", "windows", "system32")
            os.makedirs(sys32)
            result = dm.is_dxvk_installed(tmpdir)
        self.assertFalse(result)

    def test_returns_true_when_all_dlls_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sys32 = os.path.join(tmpdir, "drive_c", "windows", "system32")
            os.makedirs(sys32)
            for dll in dm.DXVK_DLLS_64:
                with open(os.path.join(sys32, dll), "wb") as f:
                    f.write(b"\x00")
            result = dm.is_dxvk_installed(tmpdir)
        self.assertTrue(result)

    def test_returns_false_when_one_dll_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sys32 = os.path.join(tmpdir, "drive_c", "windows", "system32")
            os.makedirs(sys32)
            for dll in dm.DXVK_DLLS_64[:-1]:  # all but last
                with open(os.path.join(sys32, dll), "wb") as f:
                    f.write(b"\x00")
            result = dm.is_dxvk_installed(tmpdir)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# dxvk_manager — install_dxvk()
# ---------------------------------------------------------------------------

class TestInstallDxvk(unittest.TestCase):

    def test_returns_dict_with_success_key(self):
        """install_dxvk() always returns a dict with 'success' key — no crash."""
        with tempfile.TemporaryDirectory() as prefix_dir:
            # No COMPAT_BASE dxvk dir — should still return a dict, not raise
            with patch.object(dm, "COMPAT_BASE", "/nonexistent/compat"):
                result = dm.install_dxvk(prefix_dir)
        self.assertIn("success", result)

    def test_returns_dict_with_dlls_installed_key(self):
        with tempfile.TemporaryDirectory() as prefix_dir:
            with patch.object(dm, "COMPAT_BASE", "/nonexistent/compat"):
                result = dm.install_dxvk(prefix_dir)
        self.assertIn("dlls_installed", result)
        self.assertIsInstance(result["dlls_installed"], int)

    def test_installs_dlls_when_source_present(self):
        """DLLs are copied when source directory contains them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Build a fake compat dir
            compat = os.path.join(tmpdir, "compat")
            dxvk_src64 = os.path.join(compat, "dxvk")
            dxvk_src32 = os.path.join(compat, "dxvk", "x32")
            os.makedirs(dxvk_src64)
            os.makedirs(dxvk_src32)
            for dll in dm.DXVK_DLLS_64:
                with open(os.path.join(dxvk_src64, dll), "wb") as f:
                    f.write(b"FAKE")
                with open(os.path.join(dxvk_src32, dll), "wb") as f:
                    f.write(b"FAKE32")

            prefix = os.path.join(tmpdir, "prefix")
            os.makedirs(prefix)

            with patch.object(dm, "COMPAT_BASE", compat), \
                 patch("subprocess.run"):  # suppress wine reg calls
                result = dm.install_dxvk(prefix)

        self.assertTrue(result["success"])
        self.assertGreater(result["dlls_installed"], 0)


# ---------------------------------------------------------------------------
# dxvk_manager — get_dxvk_version()
# ---------------------------------------------------------------------------

class TestGetDxvkVersion(unittest.TestCase):

    def test_returns_none_when_no_compat_dir(self):
        """Returns None when COMPAT_BASE/dxvk/version does not exist."""
        with patch.object(dm, "COMPAT_BASE", "/nonexistent/path"):
            result = dm.get_dxvk_version()
        self.assertIsNone(result)

    def test_returns_version_string_when_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dxvk_dir = os.path.join(tmpdir, "dxvk")
            os.makedirs(dxvk_dir)
            with open(os.path.join(dxvk_dir, "version"), "w") as f:
                f.write("2.3.1\n")
            with patch.object(dm, "COMPAT_BASE", tmpdir):
                result = dm.get_dxvk_version()
        self.assertEqual(result, "2.3.1")

    def test_no_crash_on_unreadable_version_file(self):
        with patch.object(dm, "COMPAT_BASE", "/nonexistent"):
            result = dm.get_dxvk_version()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# wine_runner — detect_wine() uses compatibility_manager
# ---------------------------------------------------------------------------

class TestWineRunnerUsesCompatManager(unittest.TestCase):

    def test_detect_wine_calls_get_wine_path(self):
        """detect_wine() must use get_wine_path() from compatibility_manager."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from zone2 import wine_runner

        with patch.object(
            wine_runner,
            "_HAS_COMPAT_MANAGER",
            True,
        ), patch.object(
            wine_runner,
            "_compat_get_wine_path",
            return_value="/usr/lib/luminos/compatibility/wine/wine64",
        ) as mock_get_wine_path, patch(
            "os.path.isfile", return_value=True
        ), patch(
            "subprocess.run",
            return_value=MagicMock(returncode=0, stdout="wine-8.0\n"),
        ):
            result = wine_runner.detect_wine()

        mock_get_wine_path.assert_called_once()
        self.assertTrue(result["available"])
        self.assertEqual(result["path"], "/usr/lib/luminos/compatibility/wine/wine64")

    def test_detect_wine_falls_back_when_compat_manager_returns_none(self):
        """If get_wine_path() returns None, legacy Proton/wine scan is used."""
        from zone2 import wine_runner

        with patch.object(wine_runner, "_HAS_COMPAT_MANAGER", True), \
             patch.object(wine_runner, "_compat_get_wine_path", return_value=None), \
             patch("os.path.isfile", return_value=False), \
             patch("glob.glob", return_value=[]):
            result = wine_runner.detect_wine()

        self.assertFalse(result["available"])


# ---------------------------------------------------------------------------
# .desktop file content
# ---------------------------------------------------------------------------

class TestDesktopFile(unittest.TestCase):

    _DESKTOP_PATH = os.path.join(
        os.path.dirname(__file__), "..", "config", "luminos-windows.desktop"
    )

    def _read_desktop(self) -> str:
        with open(self._DESKTOP_PATH) as f:
            return f.read()

    def test_desktop_file_exists(self):
        self.assertTrue(
            os.path.isfile(self._DESKTOP_PATH),
            "config/luminos-windows.desktop must exist",
        )

    def test_contains_exe_mimetype(self):
        content = self._read_desktop()
        self.assertIn("application/x-ms-dos-executable", content)

    def test_contains_msi_mimetype(self):
        content = self._read_desktop()
        self.assertIn("application/x-msi", content)

    def test_contains_shortcut_mimetype(self):
        content = self._read_desktop()
        self.assertIn("application/x-ms-shortcut", content)

    def test_exec_references_luminos_run_windows(self):
        content = self._read_desktop()
        self.assertIn("luminos-run-windows", content)

    def test_desktop_entry_section_present(self):
        content = self._read_desktop()
        self.assertIn("[Desktop Entry]", content)

    def test_type_is_application(self):
        content = self._read_desktop()
        self.assertIn("Type=Application", content)


if __name__ == "__main__":
    unittest.main()
