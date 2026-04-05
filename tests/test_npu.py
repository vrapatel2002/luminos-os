"""
tests/test_npu.py
Phase 5.3b — NPU abstraction layer test suite.

All tests use MockNPUInterface — zero real hardware required.

Covers:
  - NPUInterface.is_available() returns bool                         (2 tests)
  - run_sentinel() returns correct dict shape                        (2 tests)
  - run_router() returns correct dict shape                          (2 tests)
  - Router pauses sentinel during analysis                           (1 test)
  - Sentinel resumes after router finishes                           (1 test)
  - NPUUnavailableError raised when unavailable                      (2 tests)
  - NPUModelNotLoadedError raised when model not loaded              (2 tests)
  - MockNPUInterface works as drop-in replacement                    (1 test)
  - status() returns correct dict shape                              (2 tests)

Total: 15 tests — all headless, no hardware required.
"""

import os
import sys
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from npu import (
    NPUInterface,
    MockNPUInterface,
    NPUUnavailableError,
    NPUModelNotLoadedError,
    NPUInferenceError,
)


# ===========================================================================
# is_available
# ===========================================================================

class TestIsAvailable(unittest.TestCase):

    def test_mock_available_true(self):
        npu = MockNPUInterface(mock_available=True)
        self.assertTrue(npu.is_available())

    def test_mock_available_false(self):
        npu = MockNPUInterface(mock_available=False)
        self.assertFalse(npu.is_available())


# ===========================================================================
# status
# ===========================================================================

class TestStatus(unittest.TestCase):

    def test_status_available(self):
        npu = MockNPUInterface(mock_available=True)
        s = npu.status()
        self.assertTrue(s["available"])
        self.assertEqual(s["driver"], "xdna")
        self.assertIn("current_task", s)
        self.assertIn("queue_depth", s)

    def test_status_unavailable(self):
        npu = MockNPUInterface(mock_available=False)
        s = npu.status()
        self.assertFalse(s["available"])
        self.assertEqual(s["driver"], "none")


# ===========================================================================
# run_sentinel
# ===========================================================================

class TestRunSentinel(unittest.TestCase):

    def test_sentinel_returns_dict(self):
        npu = MockNPUInterface(mock_available=True)
        npu.load_model("/fake/path", "sentinel")
        result = npu.run_sentinel({
            "syscalls": ["read", "write"],
            "process": "test.exe",
            "pid": 1234,
        })
        self.assertIsInstance(result, dict)
        self.assertIn("classification", result)
        self.assertIn("confidence", result)
        self.assertIn("reason", result)
        self.assertIn(result["classification"], ("normal", "suspicious", "block"))

    def test_sentinel_normal_process(self):
        npu = MockNPUInterface(mock_available=True)
        npu.load_model("/fake/path", "sentinel")
        result = npu.run_sentinel({
            "syscalls": ["read"],
            "process": "safe.exe",
            "pid": 100,
        })
        self.assertEqual(result["classification"], "normal")
        self.assertGreater(result["confidence"], 0.5)


# ===========================================================================
# run_router
# ===========================================================================

class TestRunRouter(unittest.TestCase):

    def test_router_returns_dict(self):
        npu = MockNPUInterface(mock_available=True)
        npu.load_model("/fake/path", "router")
        result = npu.run_router({
            "path": "/tmp/app.exe",
            "has_dx12": True,
            "has_anticheat_strings": False,
        })
        self.assertIsInstance(result, dict)
        self.assertIn("layer", result)
        self.assertIn("confidence", result)
        self.assertIn(result["layer"], ("proton", "wine", "firecracker", "kvm"))

    def test_router_anticheat_routes_to_kvm(self):
        npu = MockNPUInterface(mock_available=True)
        npu.load_model("/fake/path", "router")
        result = npu.run_router({
            "path": "/tmp/game.exe",
            "has_anticheat_strings": True,
        })
        self.assertEqual(result["layer"], "kvm")


# ===========================================================================
# Queue behavior — router pauses/resumes sentinel
# ===========================================================================

class TestQueueBehavior(unittest.TestCase):

    def test_router_pauses_and_resumes_sentinel(self):
        npu = MockNPUInterface(mock_available=True)
        npu.load_model("/fake/path", "sentinel")
        npu.load_model("/fake/path", "router")

        # Initially sentinel is not paused
        self.assertTrue(npu._sentinel_paused.is_set())

        # Run router — should pause then resume sentinel
        npu.run_router({"path": "/tmp/app.exe"})

        # After router completes, sentinel should be resumed
        self.assertTrue(npu._sentinel_paused.is_set())
        self.assertEqual(npu._pause_count, 1)
        self.assertEqual(npu._resume_count, 1)


# ===========================================================================
# Error handling
# ===========================================================================

class TestErrors(unittest.TestCase):

    def test_sentinel_raises_when_unavailable(self):
        npu = MockNPUInterface(mock_available=False)
        with self.assertRaises(NPUUnavailableError):
            npu.run_sentinel({"syscalls": [], "process": "x", "pid": 1})

    def test_router_raises_when_unavailable(self):
        npu = MockNPUInterface(mock_available=False)
        with self.assertRaises(NPUUnavailableError):
            npu.run_router({"path": "/tmp/x.exe"})

    def test_sentinel_raises_when_model_not_loaded(self):
        npu = MockNPUInterface(mock_available=True)
        # Don't load model
        with self.assertRaises(NPUModelNotLoadedError):
            npu.run_sentinel({"syscalls": [], "process": "x", "pid": 1})

    def test_router_raises_when_model_not_loaded(self):
        npu = MockNPUInterface(mock_available=True)
        # Don't load model
        with self.assertRaises(NPUModelNotLoadedError):
            npu.run_router({"path": "/tmp/x.exe"})


# ===========================================================================
# MockNPUInterface drop-in
# ===========================================================================

class TestMockDropIn(unittest.TestCase):

    def test_mock_is_subclass(self):
        """MockNPUInterface can be used wherever NPUInterface is expected."""
        npu = MockNPUInterface()
        self.assertIsInstance(npu, NPUInterface)


if __name__ == "__main__":
    unittest.main()
