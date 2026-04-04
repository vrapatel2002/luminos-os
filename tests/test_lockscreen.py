"""
tests/test_lockscreen.py
Phase 8.8 — Lock Screen test suite.

Covers:
  - pam_auth: get_current_user, is_locked_out, backoff, reset,
              authenticate (mocked pam)               (8 tests)
  - pam_auth pure helper: _backoff_for_attempts       (1 test)
  - lock_window pure helpers: format, initials        (3 tests)
  - lock_manager: lock, unlock, double-lock, status   (4 tests)
  - daemon routing: lock, lock_status                 (2 tests)

Total: 18 tests
All headless — no PAM calls, no GTK display required.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gui.lockscreen.pam_auth import PAMAuth, _backoff_for_attempts
from gui.lockscreen.lock_window import (
    _format_clock_time, _format_clock_date, _get_initials,
)
from gui.lockscreen.lock_manager import LockManager
import gui.lockscreen as lockscreen_pkg


# ===========================================================================
# PAMAuth — pure logic (no real PAM calls)
# ===========================================================================

class TestGetCurrentUser(unittest.TestCase):

    def test_returns_string_no_crash(self):
        auth = PAMAuth()
        user = auth.get_current_user()
        self.assertIsInstance(user, str)
        self.assertTrue(len(user) > 0)


class TestIsLockedOut(unittest.TestCase):

    def test_no_lockout_initially(self):
        auth = PAMAuth()
        result = auth.is_locked_out()
        self.assertFalse(result["locked"])
        self.assertEqual(result["wait_seconds"], 0)

    def test_active_lockout_returns_locked_true(self):
        auth = PAMAuth()
        auth.locked_until = time.time() + 30
        result = auth.is_locked_out()
        self.assertTrue(result["locked"])
        self.assertGreater(result["wait_seconds"], 0)

    def test_expired_lockout_clears_itself(self):
        auth = PAMAuth()
        auth.locked_until = time.time() - 1   # already past
        result = auth.is_locked_out()
        self.assertFalse(result["locked"])
        self.assertIsNone(auth.locked_until)


class TestBackoff(unittest.TestCase):

    def _fail_n_times(self, auth: PAMAuth, n: int):
        """
        Trigger n accumulated failed attempts, clearing lockout between groups
        so the counter keeps rising (simulates multiple lockout cycles).
        """
        with patch.object(auth, "_pam_authenticate", return_value=False):
            for _ in range(n):
                auth.authenticate("wrong")
                # If a lockout was just applied, clear it so we can keep failing
                auth.locked_until = None

    def test_backoff_after_3_fails(self):
        auth = PAMAuth()
        self._fail_n_times(auth, 3)
        # After 3 accumulated fails the last _apply_backoff should trigger
        self.assertGreaterEqual(auth.attempts, 3)
        # Verify _backoff_for_attempts returns a non-zero duration
        from gui.lockscreen.pam_auth import _backoff_for_attempts
        self.assertGreater(_backoff_for_attempts(auth.attempts), 0)

    def test_backoff_after_5_fails_longer_than_3(self):
        """5 accumulated fails produce a longer lockout than 3."""
        from gui.lockscreen.pam_auth import _backoff_for_attempts
        wait3 = _backoff_for_attempts(3)
        wait5 = _backoff_for_attempts(5)
        self.assertGreater(wait5, wait3)

    def test_reset_clears_attempts_and_lockout(self):
        auth = PAMAuth()
        self._fail_n_times(auth, 5)
        auth.reset()
        self.assertEqual(auth.attempts, 0)
        self.assertIsNone(auth.locked_until)
        self.assertFalse(auth.is_locked_out()["locked"])


class TestAuthenticate(unittest.TestCase):

    def test_success_resets_attempts(self):
        auth = PAMAuth()
        auth.attempts = 2   # had some failures before
        with patch.object(auth, "_pam_authenticate", return_value=True):
            result = auth.authenticate("correct")
        self.assertTrue(result["success"])
        self.assertEqual(auth.attempts, 0)

    def test_failure_increments_attempts(self):
        auth = PAMAuth()
        with patch.object(auth, "_pam_authenticate", return_value=False):
            result = auth.authenticate("wrong")
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "wrong_password")
        self.assertEqual(auth.attempts, 1)

    def test_locked_out_blocks_immediately(self):
        auth = PAMAuth()
        auth.locked_until = time.time() + 60
        result = auth.authenticate("any")
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "locked_out")
        self.assertGreater(result["wait_seconds"], 0)


class TestBackoffHelper(unittest.TestCase):

    def test_zero_attempts_no_lockout(self):
        self.assertEqual(_backoff_for_attempts(0), 0)

    def test_3_attempts_30s(self):
        self.assertEqual(_backoff_for_attempts(3), 30)

    def test_5_attempts_120s(self):
        self.assertEqual(_backoff_for_attempts(5), 120)

    def test_7_attempts_300s(self):
        self.assertEqual(_backoff_for_attempts(7), 300)

    def test_high_attempts_still_300s(self):
        self.assertEqual(_backoff_for_attempts(20), 300)


# ===========================================================================
# lock_window pure helpers
# ===========================================================================

class TestLockWindowHelpers(unittest.TestCase):

    def test_format_clock_time(self):
        import datetime
        dt = datetime.datetime(2026, 3, 22, 14, 5)
        self.assertEqual(_format_clock_time(dt), "14:05")

    def test_format_clock_date(self):
        import datetime
        dt = datetime.datetime(2026, 3, 22, 10, 0)   # Sunday, March 22
        result = _format_clock_date(dt)
        self.assertIn("March", result)
        self.assertIn("22", result)

    def test_get_initials_single_name(self):
        self.assertEqual(_get_initials("alice"), "A")

    def test_get_initials_underscore(self):
        self.assertEqual(_get_initials("john_doe"), "JD")

    def test_get_initials_dot_separated(self):
        self.assertEqual(_get_initials("j.smith"), "JS")


# ===========================================================================
# LockManager
# ===========================================================================

class TestLockManager(unittest.TestCase):

    def _make_manager(self) -> LockManager:
        mgr = LockManager(idle_timeout=300)
        return mgr

    def test_lock_sets_locked_true(self):
        mgr = self._make_manager()
        with patch("gui.lockscreen.lock_manager._GTK_AVAILABLE", False), \
             patch("gui.lockscreen.lock_manager.LockManager.lock",
                   wraps=mgr.lock):
            # Patch wallpaper on_lock to avoid import errors
            with patch("gui.lockscreen.lock_manager.__builtins__", {}):
                pass
        # Direct test without GTK
        mgr2 = LockManager()
        with patch("gui.lockscreen.lock_manager._GTK_AVAILABLE", False):
            with patch.object(mgr2, "_idle_loop"):
                result = mgr2.lock()
        self.assertTrue(result)
        self.assertTrue(mgr2.locked)
        self.assertIsNotNone(mgr2.lock_time)

    def test_unlock_sets_locked_false(self):
        mgr = LockManager()
        with patch("gui.lockscreen.lock_manager._GTK_AVAILABLE", False):
            mgr.lock()
            result = mgr.unlock()
        self.assertTrue(result)
        self.assertFalse(mgr.locked)
        self.assertIsNone(mgr.lock_time)

    def test_lock_while_already_locked_returns_false(self):
        mgr = LockManager()
        with patch("gui.lockscreen.lock_manager._GTK_AVAILABLE", False):
            mgr.lock()
            result = mgr.lock()
        self.assertFalse(result)

    def test_unlock_while_not_locked_returns_false(self):
        mgr = LockManager()
        result = mgr.unlock()
        self.assertFalse(result)

    def test_get_status_all_keys_present(self):
        mgr = LockManager()
        status = mgr.get_status()
        for key in ("locked", "lock_time", "idle_timeout", "attempts"):
            self.assertIn(key, status)


# ===========================================================================
# daemon routing
# ===========================================================================

class TestDaemonLockRouting(unittest.TestCase):

    def _route(self, message):
        sys.path.insert(0, os.path.join(SRC, ".."))
        from daemon.main import route_request
        return route_request(message)

    def test_lock_request_response_shape(self):
        with patch("daemon.main._LOCKSCREEN_AVAILABLE", True), \
             patch("daemon.main._lock_lock", return_value=True):
            result = self._route({"type": "lock"})
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("locked", result)

    def test_lock_status_response_shape(self):
        with patch("daemon.main._LOCKSCREEN_AVAILABLE", True), \
             patch("daemon.main._lock_status",
                   return_value={"locked": False, "lock_time": None,
                                 "idle_timeout": 300, "attempts": 0}):
            result = self._route({"type": "lock_status"})
        self.assertEqual(result.get("status"), "ok")
        self.assertIn("locked", result)
        self.assertIn("idle_timeout", result)

    def test_lock_activity_always_ok(self):
        with patch("daemon.main._LOCKSCREEN_AVAILABLE", True), \
             patch("daemon.main._lock_activity"):
            result = self._route({"type": "lock_activity"})
        self.assertEqual(result.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
