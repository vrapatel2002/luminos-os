"""
tests/test_gpu_manager.py
Unit tests for Phase 6 GPU Manager.

Strategy:
- Hardware probes (get_nvidia_vram, get_amd_vram, get_npu_status) tested for
  correct dict shape — hardware may not be present, that is fine.
- ModelManager logic tested directly with controlled inputs — no real GPU needed.
- process_watcher tested with known strings.
- Daemon routing tested via route_request() with a fake message dict.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gpu_manager.vram_monitor import get_nvidia_vram, get_amd_vram, get_npu_status, get_full_hardware_status
from gpu_manager.model_manager import ModelManager, IDLE_TIMEOUT_SECONDS, HIVE_MODELS
from gpu_manager.process_watcher import is_gaming_process, scan_running_games
import gpu_manager as gm


# ---------------------------------------------------------------------------
# Hardware probe — shape tests
# ---------------------------------------------------------------------------

class TestGetNvidiaVram(unittest.TestCase):

    def test_returns_dict(self):
        self.assertIsInstance(get_nvidia_vram(), dict)

    def test_has_available_key(self):
        self.assertIn("available", get_nvidia_vram())

    def test_available_is_bool(self):
        self.assertIsInstance(get_nvidia_vram()["available"], bool)

    def test_when_available_has_all_keys(self):
        info = get_nvidia_vram()
        if info["available"]:
            for key in ("total_mb", "free_mb", "used_mb", "gpu_utilization_percent"):
                self.assertIn(key, info)

    def test_when_available_values_are_non_negative(self):
        info = get_nvidia_vram()
        if info["available"]:
            self.assertGreaterEqual(info["total_mb"], 0)
            self.assertGreaterEqual(info["free_mb"], 0)
            self.assertGreaterEqual(info["used_mb"], 0)
            self.assertGreaterEqual(info["gpu_utilization_percent"], 0.0)

    def test_when_not_available_only_available_key_required(self):
        info = get_nvidia_vram()
        if not info["available"]:
            self.assertFalse(info["available"])


class TestGetAmdVram(unittest.TestCase):

    def test_returns_dict(self):
        self.assertIsInstance(get_amd_vram(), dict)

    def test_has_available_key(self):
        self.assertIn("available", get_amd_vram())

    def test_available_is_bool(self):
        self.assertIsInstance(get_amd_vram()["available"], bool)

    def test_when_available_has_all_keys(self):
        info = get_amd_vram()
        if info["available"]:
            for key in ("total_mb", "used_mb", "free_mb"):
                self.assertIn(key, info)
                self.assertIsInstance(info[key], int)

    def test_when_available_free_plus_used_equals_total(self):
        info = get_amd_vram()
        if info["available"]:
            self.assertEqual(info["free_mb"], info["total_mb"] - info["used_mb"])


class TestGetNpuStatus(unittest.TestCase):

    def test_returns_dict(self):
        self.assertIsInstance(get_npu_status(), dict)

    def test_has_required_keys(self):
        info = get_npu_status()
        for key in ("available", "device", "driver_loaded"):
            self.assertIn(key, info)

    def test_available_is_bool(self):
        self.assertIsInstance(get_npu_status()["available"], bool)

    def test_driver_loaded_is_bool(self):
        self.assertIsInstance(get_npu_status()["driver_loaded"], bool)

    def test_device_is_string_or_none(self):
        device = get_npu_status()["device"]
        self.assertTrue(device is None or isinstance(device, str))

    def test_when_not_available_device_is_none(self):
        info = get_npu_status()
        if not info["available"]:
            self.assertIsNone(info["device"])


class TestGetFullHardwareStatus(unittest.TestCase):

    def test_returns_dict_with_all_sections(self):
        status = get_full_hardware_status()
        for key in ("nvidia", "amd_igpu", "npu", "timestamp"):
            self.assertIn(key, status)

    def test_timestamp_is_float(self):
        self.assertIsInstance(get_full_hardware_status()["timestamp"], float)


# ---------------------------------------------------------------------------
# ModelManager — calculate_gpu_layers
# ---------------------------------------------------------------------------

class TestCalculateGpuLayers(unittest.TestCase):

    def setUp(self):
        self.mm = ModelManager()

    def test_full_vram_returns_32(self):
        # 4GB model, 8GB free → all 32 layers
        self.assertEqual(self.mm.calculate_gpu_layers(4.0, 8192), 32)

    def test_sixty_percent_vram_returns_19(self):
        # 4GB model, 2.5GB free (~62%) → 32*0.6 = 19
        self.assertEqual(self.mm.calculate_gpu_layers(4.0, 2560), int(32 * 0.6))

    def test_thirty_percent_vram_returns_9(self):
        # 4GB model, 1.3GB free (~32%) → 32*0.3 = 9
        self.assertEqual(self.mm.calculate_gpu_layers(4.0, 1300), int(32 * 0.3))

    def test_no_vram_returns_0(self):
        # 4GB model, 0MB free → CPU only
        self.assertEqual(self.mm.calculate_gpu_layers(4.0, 0), 0)

    def test_exact_model_size_returns_32(self):
        # Exactly enough VRAM → full offload
        self.assertEqual(self.mm.calculate_gpu_layers(4.0, 4096), 32)


# ---------------------------------------------------------------------------
# ModelManager — select_quantization
# ---------------------------------------------------------------------------

class TestSelectQuantization(unittest.TestCase):

    def setUp(self):
        self.mm = ModelManager()

    def test_7gb_plus_returns_q8(self):
        self.assertEqual(self.mm.select_quantization(7000), "Q8")

    def test_4gb_returns_q4(self):
        self.assertEqual(self.mm.select_quantization(4000), "Q4")

    def test_2gb_returns_q2(self):
        self.assertEqual(self.mm.select_quantization(2000), "Q2")

    def test_under_2gb_returns_1b(self):
        self.assertEqual(self.mm.select_quantization(1000), "1b")

    def test_zero_vram_returns_1b(self):
        self.assertEqual(self.mm.select_quantization(0), "1b")


# ---------------------------------------------------------------------------
# ModelManager — request_model
# ---------------------------------------------------------------------------

class TestRequestModel(unittest.TestCase):

    def setUp(self):
        self.mm = ModelManager()

    def test_loads_model_and_returns_correct_keys(self):
        result = self.mm.request_model("nexus", 5000)
        for key in ("loaded", "quantization", "layers", "previously_unloaded"):
            self.assertIn(key, result)

    def test_loaded_model_matches_request(self):
        result = self.mm.request_model("nexus", 5000)
        self.assertEqual(result["loaded"], "nexus")

    def test_sets_nvidia_active_true(self):
        self.mm.request_model("nexus", 5000)
        self.assertTrue(self.mm.nvidia_active)

    def test_sets_active_model(self):
        self.mm.request_model("bolt", 5000)
        self.assertEqual(self.mm.active_model, "bolt")

    def test_second_different_model_evicts_first(self):
        self.mm.request_model("nexus", 5000)
        result = self.mm.request_model("bolt", 5000)
        self.assertEqual(result["loaded"], "bolt")
        self.assertEqual(result["previously_unloaded"], "nexus")
        self.assertEqual(self.mm.active_model, "bolt")

    def test_same_model_twice_no_eviction(self):
        self.mm.request_model("nova", 5000)
        result = self.mm.request_model("nova", 5000)
        self.assertEqual(result["loaded"], "nova")
        self.assertIsNone(result["previously_unloaded"])

    def test_only_one_model_in_vram_at_a_time(self):
        for name in ("nexus", "bolt", "nova", "eye", "nexus"):
            self.mm.request_model(name, 5000)
        # Only the last requested model should be active
        self.assertEqual(self.mm.active_model, "nexus")

    def test_unknown_model_returns_error(self):
        result = self.mm.request_model("nonexistent", 5000)
        self.assertIn("error", result)
        self.assertIsNone(result["loaded"])

    def test_quantization_chosen_based_on_vram(self):
        result_high = self.mm.request_model("nexus", 8000)
        self.assertEqual(result_high["quantization"], "Q8")
        self.mm.active_model = None  # reset
        result_low = self.mm.request_model("nexus", 1000)
        self.assertEqual(result_low["quantization"], "1b")


# ---------------------------------------------------------------------------
# ModelManager — release_model_if_idle
# ---------------------------------------------------------------------------

class TestReleaseModelIfIdle(unittest.TestCase):

    def setUp(self):
        self.mm = ModelManager()

    def test_no_model_loaded_returns_none(self):
        result = self.mm.release_model_if_idle()
        self.assertIsNone(result["unloaded"])

    def test_recently_used_model_not_unloaded(self):
        self.mm.request_model("nexus", 5000)
        result = self.mm.release_model_if_idle()
        self.assertIsNone(result["unloaded"])
        self.assertEqual(self.mm.active_model, "nexus")

    def test_force_idle_by_backdating_timestamp(self):
        self.mm.request_model("nexus", 5000)
        # Backdate last_used well past the timeout
        self.mm.last_used = time.monotonic() - (IDLE_TIMEOUT_SECONDS + 10)
        result = self.mm.release_model_if_idle()
        self.assertEqual(result["unloaded"], "nexus")
        self.assertIsNone(self.mm.active_model)
        self.assertFalse(self.mm.nvidia_active)

    def test_after_unload_nvidia_active_is_false(self):
        self.mm.request_model("bolt", 5000)
        self.mm.last_used = time.monotonic() - (IDLE_TIMEOUT_SECONDS + 1)
        self.mm.release_model_if_idle()
        self.assertFalse(self.mm.nvidia_active)


# ---------------------------------------------------------------------------
# ModelManager — gaming mode
# ---------------------------------------------------------------------------

class TestGamingMode(unittest.TestCase):

    def setUp(self):
        self.mm = ModelManager()

    def test_enter_gaming_mode_unloads_active_model(self):
        self.mm.request_model("eye", 5000)
        result = self.mm.enter_gaming_mode()
        self.assertEqual(result["unloaded"], "eye")
        self.assertIsNone(self.mm.active_model)

    def test_enter_gaming_mode_sets_gaming_mode_true(self):
        self.mm.enter_gaming_mode()
        self.assertTrue(self.mm.gaming_mode)

    def test_enter_gaming_mode_sets_nvidia_active_false(self):
        self.mm.request_model("nexus", 5000)
        self.mm.enter_gaming_mode()
        self.assertFalse(self.mm.nvidia_active)

    def test_enter_gaming_mode_message_present(self):
        result = self.mm.enter_gaming_mode()
        self.assertIn("message", result)
        self.assertIn("NVIDIA", result["message"])

    def test_enter_gaming_mode_no_model_loaded_is_fine(self):
        result = self.mm.enter_gaming_mode()
        self.assertIsNone(result["unloaded"])
        self.assertTrue(self.mm.gaming_mode)

    def test_exit_gaming_mode_sets_gaming_mode_false(self):
        self.mm.enter_gaming_mode()
        self.mm.exit_gaming_mode()
        self.assertFalse(self.mm.gaming_mode)

    def test_exit_gaming_mode_does_not_preload_model(self):
        self.mm.enter_gaming_mode()
        self.mm.exit_gaming_mode()
        # Apple philosophy: no preload on exit
        self.assertIsNone(self.mm.active_model)

    def test_exit_gaming_mode_nvidia_stays_idle(self):
        self.mm.enter_gaming_mode()
        self.mm.exit_gaming_mode()
        self.assertFalse(self.mm.nvidia_active)

    def test_get_status_reflects_gaming_mode(self):
        self.mm.enter_gaming_mode()
        status = self.mm.get_status()
        self.assertTrue(status["gaming_mode"])
        self.assertFalse(status["nvidia_active"])
        self.assertIsNone(status["active_model"])


# ---------------------------------------------------------------------------
# ModelManager — get_status
# ---------------------------------------------------------------------------

class TestGetStatus(unittest.TestCase):

    def setUp(self):
        self.mm = ModelManager()

    def test_returns_required_keys(self):
        status = self.mm.get_status()
        for key in ("active_model", "gaming_mode", "nvidia_active",
                    "idle_timeout_seconds", "seconds_since_last_use"):
            self.assertIn(key, status)

    def test_idle_timeout_matches_constant(self):
        self.assertEqual(self.mm.get_status()["idle_timeout_seconds"], IDLE_TIMEOUT_SECONDS)

    def test_no_model_seconds_since_use_is_none(self):
        self.assertIsNone(self.mm.get_status()["seconds_since_last_use"])

    def test_after_load_seconds_since_use_is_float(self):
        self.mm.request_model("nexus", 5000)
        seconds = self.mm.get_status()["seconds_since_last_use"]
        self.assertIsInstance(seconds, float)
        self.assertGreaterEqual(seconds, 0.0)


# ---------------------------------------------------------------------------
# process_watcher
# ---------------------------------------------------------------------------

class TestIsGamingProcess(unittest.TestCase):

    def test_steam_is_gaming(self):
        self.assertTrue(is_gaming_process("steam"))

    def test_lutris_is_gaming(self):
        self.assertTrue(is_gaming_process("lutris"))

    def test_heroic_is_gaming(self):
        self.assertTrue(is_gaming_process("heroic"))

    def test_exe_extension_is_gaming(self):
        self.assertTrue(is_gaming_process("", "/games/MyGame.exe"))

    def test_gamescope_is_gaming(self):
        self.assertTrue(is_gaming_process("gamescope"))

    def test_gamemode_is_gaming(self):
        self.assertTrue(is_gaming_process("gamemode"))

    def test_firefox_is_not_gaming(self):
        self.assertFalse(is_gaming_process("firefox"))

    def test_python_is_not_gaming(self):
        self.assertFalse(is_gaming_process("python3"))

    def test_empty_strings_is_not_gaming(self):
        self.assertFalse(is_gaming_process("", ""))

    def test_case_insensitive_exe(self):
        self.assertTrue(is_gaming_process("", "/games/MyGame.EXE"))


class TestScanRunningGames(unittest.TestCase):

    def test_returns_list(self):
        self.assertIsInstance(scan_running_games(), list)

    def test_each_entry_has_pid_and_name(self):
        games = scan_running_games()
        for entry in games:
            self.assertIn("pid", entry)
            self.assertIn("name", entry)
            self.assertIsInstance(entry["pid"], int)
            self.assertIsInstance(entry["name"], str)


# ---------------------------------------------------------------------------
# Daemon routing — gpu_manager request types
# ---------------------------------------------------------------------------

class TestDaemonGpuRouting(unittest.TestCase):
    """Test daemon route_request() integration for GPU manager request types."""

    def setUp(self):
        # Import route_request and the daemon's stub ModelManager
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'daemon'))
        import importlib
        import daemon.main as daemon_main
        self.route = daemon_main.route_request
        self.stub_mm = daemon_main.ModelManager()

    def test_model_request_returns_dict_with_loaded_key(self):
        result = self.route({"type": "model_request", "model": "nexus"}, self.stub_mm)
        self.assertIn("loaded", result)

    def test_model_request_missing_model_returns_error(self):
        result = self.route({"type": "model_request"}, self.stub_mm)
        self.assertEqual(result.get("status"), "error")

    def test_model_release_returns_dict_with_unloaded_key(self):
        result = self.route({"type": "model_release"}, self.stub_mm)
        self.assertIn("unloaded", result)

    def test_gaming_mode_true_returns_message(self):
        result = self.route({"type": "gaming_mode", "active": True}, self.stub_mm)
        self.assertIn("message", result)

    def test_gaming_mode_false_returns_message(self):
        result = self.route({"type": "gaming_mode", "active": False}, self.stub_mm)
        self.assertIn("message", result)

    def test_gaming_mode_missing_active_returns_error(self):
        result = self.route({"type": "gaming_mode"}, self.stub_mm)
        self.assertEqual(result.get("status"), "error")

    def test_manager_status_returns_status_keys(self):
        result = self.route({"type": "manager_status"}, self.stub_mm)
        self.assertIn("active_model", result)
        self.assertIn("nvidia_active", result)

    def test_gpu_query_returns_hardware_dict(self):
        result = self.route({"type": "gpu_query"}, self.stub_mm)
        # Should now return full hardware status (nvidia + amd_igpu + npu + timestamp)
        self.assertIn("nvidia", result)
        self.assertIn("npu", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
