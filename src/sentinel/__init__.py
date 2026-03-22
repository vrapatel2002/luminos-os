"""
src/sentinel/__init__.py
Public API for the Luminos Sentinel process threat monitor.

Usage:
    from sentinel import assess_process
    result = assess_process(1234)
    # {"status": "safe", "confidence": 0.95, "flags": [], "action": "allow"}
"""

from .process_monitor import get_process_signals
from .threat_rules import assess


def assess_process(pid: int) -> dict:
    """
    Full Sentinel pipeline: collect live signals for `pid`, apply threat rules.

    Returns:
        {
            "status":     "safe" | "suspicious" | "dangerous",
            "confidence": float,
            "flags":      list[str],
            "action":     "allow" | "warn" | "block",
        }

    Never raises — returns a safe default with an error key if collection fails.
    """
    try:
        signals = get_process_signals(pid)
    except Exception as e:
        return {
            "status":     "safe",
            "confidence": 0.50,
            "flags":      [],
            "action":     "allow",
            "error":      f"signal collection failed: {e}",
        }

    result = assess(signals)
    result["pid"] = pid
    result["process_name"] = signals.get("process_name", "unknown")
    return result
