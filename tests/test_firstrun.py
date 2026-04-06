"""
tests/test_firstrun.py
Phase 5.9 — First Run Experience test suite.

Covers:
  firstrun_state:
    - is_complete / mark_complete / flag file creation       (3 tests)
    - save_state / load_state round-trip + missing file      (3 tests)
    - SCREENS constant                                        (1 test)

  step_widgets pure helpers:
    - validate_account: valid, empty name, pw mismatch        (4 tests)

  firstrun_window pure:
    - check_can_advance: welcome, wallpaper, account pass,
      account fail                                            (4 tests)

Total: 15 tests — all headless (no display server required).
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gui.firstrun.firstrun_state import (
    FirstRunState, SCREENS,
    is_complete, mark_complete,
    save_state, load_state,
    FIRST_RUN_FLAG, _STATE_PATH,
)
from gui.firstrun.step_widgets import validate_account
from gui.firstrun.firstrun_window import check_can_advance


# ===========================================================================
# firstrun_state
# ===========================================================================

class TestIsComplete(unittest.TestCase):

    def test_no_flag_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_flag = os.path.join(tmpdir, "first_run_complete")
            with patch("gui.firstrun.firstrun_state.FIRST_RUN_FLAG", fake_flag):
                self.assertFalse(is_complete())

    def test_mark_and_detect_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_flag = os.path.join(tmpdir, "first_run_complete")
            with patch("gui.firstrun.firstrun_state.FIRST_RUN_FLAG", fake_flag):
                self.assertFalse(is_complete())
                mark_complete()
                self.assertTrue(is_complete())
                # File must exist and contain a timestamp
                content = open(fake_flag).read()
                self.assertRegex(content, r"\d{4}-\d{2}-\d{2}T")

    def test_mark_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "a", "b", "first_run_complete")
            with patch("gui.firstrun.firstrun_state.FIRST_RUN_FLAG", nested):
                mark_complete()
                self.assertTrue(os.path.exists(nested))


class TestSaveLoadState(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "firstrun_state.json")
            with patch("gui.firstrun.firstrun_state._STATE_PATH", fake_path):
                state = FirstRunState(
                    username="alice",
                    password="s3cr3t",
                    wallpaper_type="live",
                    wallpaper_value="geometric",
                    wallpaper_index=4,
                )
                save_state(state)
                loaded = load_state()
                self.assertEqual(loaded.username,        "alice")
                self.assertEqual(loaded.password,        "s3cr3t")
                self.assertEqual(loaded.wallpaper_type,  "live")
                self.assertEqual(loaded.wallpaper_value, "geometric")
                self.assertEqual(loaded.wallpaper_index, 4)

    def test_load_missing_returns_defaults(self):
        with patch("gui.firstrun.firstrun_state._STATE_PATH",
                   "/tmp/_luminos_nonexistent_xyz.json"):
            state = load_state()
            self.assertIsInstance(state, FirstRunState)
            self.assertEqual(state.username,        "")
            self.assertEqual(state.wallpaper_index, -1)
            self.assertFalse(state.completed)

    def test_screens_constant(self):
        self.assertEqual(len(SCREENS), 4)
        self.assertEqual(SCREENS[0], "welcome")
        self.assertEqual(SCREENS[1], "account")
        self.assertEqual(SCREENS[2], "wallpaper")
        self.assertEqual(SCREENS[3], "ready")


# ===========================================================================
# validate_account pure helper
# ===========================================================================

class TestValidateAccount(unittest.TestCase):

    def test_valid_name_no_password(self):
        ok, msg = validate_account("Alice", "", "")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_valid_name_with_matching_password(self):
        ok, msg = validate_account("Bob", "Secret1!", "Secret1!")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_empty_name_fails(self):
        ok, msg = validate_account("", "", "")
        self.assertFalse(ok)
        self.assertGreater(len(msg), 0)

    def test_password_mismatch_fails(self):
        ok, msg = validate_account("Alice", "abc123", "xyz789")
        self.assertFalse(ok)
        self.assertIn("match", msg.lower())


# ===========================================================================
# check_can_advance pure helper
# ===========================================================================

class TestCheckCanAdvance(unittest.TestCase):

    def test_welcome_always_passes(self):
        ok, msg = check_can_advance("welcome", FirstRunState())
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_wallpaper_always_passes(self):
        ok, msg = check_can_advance("wallpaper", FirstRunState())
        self.assertTrue(ok)

    def test_account_passes_with_valid_data(self):
        state = FirstRunState(username="alice", password="")

        class FakeAccount:
            def collect(self):
                return ("Alice", "", "")

        ok, msg = check_can_advance("account", state, FakeAccount())
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_account_fails_with_pw_mismatch(self):
        state = FirstRunState()

        class FakeAccount:
            def collect(self):
                return ("Alice", "abc", "xyz")

        ok, msg = check_can_advance("account", state, FakeAccount())
        self.assertFalse(ok)
        self.assertGreater(len(msg), 0)


if __name__ == "__main__":
    unittest.main()
