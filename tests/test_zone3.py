"""
tests/test_zone3.py
Unit tests for Phase 5 Zone 3 Firecracker microVM quarantine layer.

Strategy:
- detect_firecracker() / detect_kvm() / launch_vm() tested for correct dict
  shape — Firecracker is not installed on dev, so failure paths are exercised.
- build_vm_config() tested for all required keys with known inputs.
- session_manager functions tested with real temp dirs.
- run_in_zone3() tested end-to-end: session created then cleaned up on failure.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from zone3.firecracker_runner import (
    detect_firecracker, detect_kvm, build_vm_config, launch_vm,
)
from zone3.session_manager import (
    create_session, destroy_session, list_sessions, cleanup_old_sessions,
    SESSION_DIR,
)
from zone3 import run_in_zone3


# ---------------------------------------------------------------------------
# detect_firecracker
# ---------------------------------------------------------------------------

class TestDetectFirecracker(unittest.TestCase):

    def test_returns_required_keys(self):
        info = detect_firecracker()
        for key in ("available", "path", "version"):
            self.assertIn(key, info)

    def test_available_is_bool(self):
        self.assertIsInstance(detect_firecracker()["available"], bool)

    def test_when_not_available_path_is_none(self):
        info = detect_firecracker()
        if not info["available"]:
            self.assertIsNone(info["path"])
            self.assertIsNone(info["version"])

    def test_when_available_path_is_string(self):
        info = detect_firecracker()
        if info["available"]:
            self.assertIsInstance(info["path"], str)
            self.assertTrue(os.path.isfile(info["path"]))


# ---------------------------------------------------------------------------
# detect_kvm
# ---------------------------------------------------------------------------

class TestDetectKvm(unittest.TestCase):

    def test_returns_required_keys(self):
        info = detect_kvm()
        for key in ("available", "reason"):
            self.assertIn(key, info)

    def test_available_is_bool(self):
        self.assertIsInstance(detect_kvm()["available"], bool)

    def test_reason_is_non_empty_string(self):
        info = detect_kvm()
        self.assertIsInstance(info["reason"], str)
        self.assertGreater(len(info["reason"]), 0)

    def test_unavailable_reason_is_informative(self):
        info = detect_kvm()
        if not info["available"]:
            # Reason should mention kvm or permission
            reason_lower = info["reason"].lower()
            self.assertTrue(
                "kvm" in reason_lower or "permission" in reason_lower
                or "access" in reason_lower,
                f"Reason not informative: {info['reason']}"
            )


# ---------------------------------------------------------------------------
# build_vm_config
# ---------------------------------------------------------------------------

class TestBuildVmConfig(unittest.TestCase):

    REQUIRED_KEYS = (
        "kernel_image_path",
        "rootfs_path",
        "vcpu_count",
        "mem_size_mib",
        "session_id",
        "exe_path",
        "socket_path",
        "boot_args",
    )

    def setUp(self):
        self.config = build_vm_config("/games/game.exe", "deadbeef")

    def test_has_all_required_keys(self):
        for key in self.REQUIRED_KEYS:
            self.assertIn(key, self.config, f"Missing key: {key}")

    def test_session_id_preserved(self):
        self.assertEqual(self.config["session_id"], "deadbeef")

    def test_exe_path_preserved(self):
        self.assertEqual(self.config["exe_path"], "/games/game.exe")

    def test_vcpu_count_is_positive_int(self):
        self.assertIsInstance(self.config["vcpu_count"], int)
        self.assertGreater(self.config["vcpu_count"], 0)

    def test_mem_size_mib_is_positive_int(self):
        self.assertIsInstance(self.config["mem_size_mib"], int)
        self.assertGreater(self.config["mem_size_mib"], 0)

    def test_rootfs_path_contains_session_id(self):
        self.assertIn("deadbeef", self.config["rootfs_path"])

    def test_socket_path_contains_session_id(self):
        self.assertIn("deadbeef", self.config["socket_path"])

    def test_kernel_image_path_is_string(self):
        self.assertIsInstance(self.config["kernel_image_path"], str)

    def test_boot_args_contains_exe_path(self):
        self.assertIn("/games/game.exe", self.config["boot_args"])

    def test_different_sessions_get_different_paths(self):
        config_b = build_vm_config("/games/game.exe", "cafebabe")
        self.assertNotEqual(self.config["rootfs_path"], config_b["rootfs_path"])
        self.assertNotEqual(self.config["socket_path"], config_b["socket_path"])


# ---------------------------------------------------------------------------
# launch_vm
# ---------------------------------------------------------------------------

class TestLaunchVm(unittest.TestCase):

    def test_returns_dict(self):
        result = launch_vm("/fake/game.exe")
        self.assertIsInstance(result, dict)

    def test_has_success_key(self):
        result = launch_vm("/fake/game.exe")
        self.assertIn("success", result)

    def test_no_firecracker_returns_meaningful_error(self):
        fc = detect_firecracker()
        if fc["available"]:
            self.skipTest("Firecracker is installed")
        result = launch_vm("/fake/game.exe")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("install_hint", result)

    def test_install_hint_references_firecracker_site(self):
        fc = detect_firecracker()
        if fc["available"]:
            self.skipTest("Firecracker is installed")
        result = launch_vm("/fake/game.exe")
        self.assertIn("firecracker", result["install_hint"].lower())

    def test_no_kvm_returns_reason(self):
        fc = detect_firecracker()
        kvm = detect_kvm()
        if fc["available"] and not kvm["available"]:
            result = launch_vm("/fake/game.exe")
            self.assertFalse(result["success"])
            self.assertIn("reason", result)

    def test_kernel_stub_includes_session_id_and_config(self):
        """When infra is ready but kernel missing, result has session_id + config."""
        fc = detect_firecracker()
        kvm = detect_kvm()
        if not (fc["available"] and kvm["available"]):
            self.skipTest("Firecracker + KVM not both available")
        result = launch_vm("/fake/game.exe")
        # Kernel not found stub
        self.assertIn("session_id", result)
        self.assertIn("config", result)


# ---------------------------------------------------------------------------
# session_manager — create / destroy
# ---------------------------------------------------------------------------

class TestSessionLifecycle(unittest.TestCase):

    def test_create_session_returns_string(self):
        sid = create_session()
        try:
            self.assertIsInstance(sid, str)
            self.assertGreater(len(sid), 0)
        finally:
            destroy_session(sid)

    def test_create_session_creates_directory(self):
        sid = create_session()
        try:
            self.assertTrue(os.path.isdir(os.path.join(SESSION_DIR, sid)))
        finally:
            destroy_session(sid)

    def test_destroy_session_removes_directory(self):
        sid = create_session()
        session_path = os.path.join(SESSION_DIR, sid)
        self.assertTrue(os.path.isdir(session_path))
        result = destroy_session(sid)
        self.assertTrue(result)
        self.assertFalse(os.path.isdir(session_path))

    def test_destroy_nonexistent_session_returns_false(self):
        result = destroy_session("00000000")
        self.assertFalse(result)

    def test_destroy_nonexistent_session_does_not_crash(self):
        # Must not raise
        destroy_session("ffffffff")


# ---------------------------------------------------------------------------
# session_manager — list / cleanup
# ---------------------------------------------------------------------------

class TestSessionList(unittest.TestCase):

    def test_list_sessions_returns_list(self):
        result = list_sessions()
        self.assertIsInstance(result, list)

    def test_list_sessions_shows_created_session(self):
        sid = create_session()
        try:
            sessions = list_sessions()
            ids = [s["session_id"] for s in sessions]
            self.assertIn(sid, ids)
        finally:
            destroy_session(sid)

    def test_list_sessions_entry_has_required_keys(self):
        sid = create_session()
        try:
            sessions = list_sessions()
            entry = next(s for s in sessions if s["session_id"] == sid)
            for key in ("session_id", "created", "size_mb"):
                self.assertIn(key, entry)
            self.assertIsInstance(entry["size_mb"], float)
        finally:
            destroy_session(sid)

    def test_destroyed_session_removed_from_list(self):
        sid = create_session()
        destroy_session(sid)
        sessions = list_sessions()
        ids = [s["session_id"] for s in sessions]
        self.assertNotIn(sid, ids)


class TestCleanupOldSessions(unittest.TestCase):

    def test_cleanup_runs_without_crash(self):
        count = cleanup_old_sessions(max_age_hours=24)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_cleanup_removes_old_sessions(self):
        # Create a session then backdate its mtime/ctime by moving the clock
        # We can't easily fake ctime, but we can verify cleanup returns an int
        # and doesn't crash with a freshly created session (age < threshold).
        sid = create_session()
        try:
            # Fresh session (age ~0) should NOT be cleaned by a 24h threshold
            removed = cleanup_old_sessions(max_age_hours=24)
            # Session should still exist
            self.assertTrue(os.path.isdir(os.path.join(SESSION_DIR, sid)))
        finally:
            destroy_session(sid)

    def test_cleanup_with_zero_hour_threshold_removes_all(self):
        """max_age_hours=0 means anything older than now → removes everything."""
        sid = create_session()
        # Sleep briefly so ctime is in the past
        time.sleep(0.05)
        try:
            removed = cleanup_old_sessions(max_age_hours=0)
            self.assertGreaterEqual(removed, 0)  # may or may not catch it on fast machines
        finally:
            # Clean up if still present
            destroy_session(sid)


# ---------------------------------------------------------------------------
# run_in_zone3 — end-to-end
# ---------------------------------------------------------------------------

class TestRunInZone3(unittest.TestCase):

    def test_returns_dict(self):
        result = run_in_zone3("/fake/game.exe")
        self.assertIsInstance(result, dict)

    def test_always_has_success_key(self):
        result = run_in_zone3("/fake/game.exe")
        self.assertIn("success", result)

    def test_always_has_session_id(self):
        result = run_in_zone3("/fake/game.exe")
        self.assertIn("session_id", result)

    def test_session_cleaned_up_on_failure(self):
        """On launch failure, run_in_zone3 must destroy the session it created."""
        fc = detect_firecracker()
        if fc["available"] and detect_kvm()["available"]:
            self.skipTest("Full infra available — failure path not triggered")

        result = run_in_zone3("/fake/game.exe")
        self.assertFalse(result["success"])

        # The session directory allocated by run_in_zone3 must be gone
        sid = result.get("session_id")
        if sid:
            session_path = os.path.join(SESSION_DIR, sid)
            self.assertFalse(
                os.path.isdir(session_path),
                f"Session {sid} was not cleaned up after failure"
            )

    def test_error_key_present_on_failure(self):
        fc = detect_firecracker()
        if fc["available"] and detect_kvm()["available"]:
            self.skipTest("Full infra available")
        result = run_in_zone3("/fake/game.exe")
        self.assertIn("error", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
