"""
tests/test_sentinel.py
Unit tests for Phase 3 Sentinel — process monitor + threat rules.

Strategy:
- Rule logic tested with hand-crafted signal dicts (fast, deterministic).
- Live monitor tested against current Python process (always present, always readable).
- Robustness tested with a nonexistent PID (999999).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sentinel import assess_process
from sentinel.process_monitor import get_process_signals
from sentinel.threat_rules import assess


# ---------------------------------------------------------------------------
# Helper — build a minimal safe signals dict, override specific fields
# ---------------------------------------------------------------------------

def _signals(**overrides) -> dict:
    base = {
        "pid":                    1,
        "process_name":           "test",
        "cpu_percent":            1.0,
        "memory_mb":              50.0,
        "open_files_count":       5,
        "network_connections":    0,
        "child_process_count":    0,
        "is_elevated":            False,
        "cmdline_has_suspicious": False,
        "exe_path":               "/usr/bin/test",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Threat rule tests (pure logic — no live OS calls)
# ---------------------------------------------------------------------------

class TestThreatRules(unittest.TestCase):

    def test_elevated_plus_suspicious_cmd_is_dangerous(self):
        result = assess(_signals(is_elevated=True, cmdline_has_suspicious=True))
        self.assertEqual(result["status"], "dangerous")
        self.assertEqual(result["confidence"], 0.95)
        self.assertIn("elevated+suspicious_cmd", result["flags"])
        self.assertEqual(result["action"], "block")

    def test_cpu_spike_plus_high_network_is_dangerous(self):
        result = assess(_signals(cpu_percent=95.0, network_connections=60))
        self.assertEqual(result["status"], "dangerous")
        self.assertEqual(result["confidence"], 0.90)
        self.assertIn("cpu_spike+high_network", result["flags"])
        self.assertEqual(result["action"], "block")

    def test_suspicious_cmdline_alone_is_suspicious(self):
        result = assess(_signals(cmdline_has_suspicious=True))
        self.assertEqual(result["status"], "suspicious")
        self.assertEqual(result["confidence"], 0.75)
        self.assertIn("suspicious_cmdline", result["flags"])
        self.assertEqual(result["action"], "warn")

    def test_elevated_plus_network_is_suspicious(self):
        result = assess(_signals(is_elevated=True, network_connections=25))
        self.assertEqual(result["status"], "suspicious")
        self.assertEqual(result["confidence"], 0.70)
        self.assertIn("elevated+network", result["flags"])
        self.assertEqual(result["action"], "warn")

    def test_high_mem_plus_network_is_suspicious(self):
        result = assess(_signals(memory_mb=2500.0, network_connections=40))
        self.assertEqual(result["status"], "suspicious")
        self.assertEqual(result["confidence"], 0.65)
        self.assertIn("high_mem+network", result["flags"])
        self.assertEqual(result["action"], "warn")

    def test_normal_process_is_safe(self):
        result = assess(_signals())
        self.assertEqual(result["status"], "safe")
        self.assertEqual(result["confidence"], 0.95)
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["action"], "allow")

    def test_rule1_takes_priority_over_rule3(self):
        """elevated+suspicious_cmd must fire before suspicious_cmdline alone."""
        result = assess(_signals(is_elevated=True, cmdline_has_suspicious=True,
                                 cpu_percent=95.0, network_connections=60))
        self.assertEqual(result["status"], "dangerous")
        self.assertEqual(result["confidence"], 0.95)

    def test_result_has_required_keys(self):
        result = assess(_signals())
        for key in ("status", "confidence", "flags", "action"):
            self.assertIn(key, result)

    def test_cpu_boundary_exactly_at_threshold(self):
        """cpu_percent == 90 should NOT trigger Rule 2 (rule uses > 90)."""
        result = assess(_signals(cpu_percent=90.0, network_connections=60))
        self.assertNotEqual(result["status"], "dangerous")

    def test_network_boundary_for_rule2(self):
        """net_conns == 50 should NOT trigger Rule 2 (rule uses > 50)."""
        result = assess(_signals(cpu_percent=95.0, network_connections=50))
        self.assertNotEqual(result["status"], "dangerous")


# ---------------------------------------------------------------------------
# Process monitor tests (live /proc reads)
# ---------------------------------------------------------------------------

class TestProcessMonitor(unittest.TestCase):

    def test_current_python_process_returns_signals(self):
        pid = os.getpid()
        signals = get_process_signals(pid)
        self.assertEqual(signals["pid"], pid)
        self.assertIsInstance(signals["process_name"], str)
        self.assertIsInstance(signals["cpu_percent"], float)
        self.assertIsInstance(signals["memory_mb"], float)
        self.assertIsInstance(signals["open_files_count"], int)
        self.assertIsInstance(signals["network_connections"], int)
        self.assertIsInstance(signals["child_process_count"], int)
        self.assertIsInstance(signals["is_elevated"], bool)
        self.assertIsInstance(signals["cmdline_has_suspicious"], bool)
        self.assertIsInstance(signals["exe_path"], str)

    def test_current_process_memory_is_positive(self):
        signals = get_process_signals(os.getpid())
        self.assertGreater(signals["memory_mb"], 0.0)

    def test_current_process_open_files_positive(self):
        signals = get_process_signals(os.getpid())
        # Python process always has at least stdin/stdout/stderr open
        self.assertGreaterEqual(signals["open_files_count"], 3)

    def test_nonexistent_pid_does_not_crash(self):
        signals = get_process_signals(999999)
        self.assertEqual(signals["pid"], 999999)
        self.assertFalse(signals["is_elevated"])
        self.assertIn("error", signals)

    def test_nonexistent_pid_error_is_process_not_found(self):
        signals = get_process_signals(999999)
        self.assertEqual(signals["error"], "process_not_found")


# ---------------------------------------------------------------------------
# End-to-end assess_process() tests
# ---------------------------------------------------------------------------

class TestAssessProcess(unittest.TestCase):

    def test_current_python_process_is_safe(self):
        result = assess_process(os.getpid())
        self.assertEqual(result["status"], "safe")
        self.assertEqual(result["action"], "allow")

    def test_nonexistent_pid_does_not_raise(self):
        result = assess_process(999999)
        # Must return a dict with status key — never raise
        self.assertIn("status", result)
        self.assertIn("action", result)

    def test_result_always_has_pid_and_process_name(self):
        result = assess_process(os.getpid())
        self.assertEqual(result["pid"], os.getpid())
        self.assertIsInstance(result["process_name"], str)

    def test_result_confidence_in_range(self):
        result = assess_process(os.getpid())
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
