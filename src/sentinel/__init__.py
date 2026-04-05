"""
src/sentinel/__init__.py
Public API for the Luminos Sentinel process threat monitor.

Pipeline:
    1. Collect /proc signals (CPU, memory, network, elevation, cmdline)
    2. Apply rule-based threat classification
    3. Optionally run ML classification on NPU (CPU fallback)
    4. Log all non-safe results to /var/log/luminos/sentinel.log

Current mode: LOG ONLY — no auto-blocking. Actions are recorded but not enforced.

Usage:
    from sentinel import assess_process
    result = assess_process(1234)
"""

import logging
import os

from .process_monitor import get_process_signals
from .threat_rules import assess

# Sentinel file logger — separate from daemon journal logging
_sentinel_logger = logging.getLogger("luminos-sentinel")
_sentinel_logger.setLevel(logging.INFO)

_LOG_DIR = "/var/log/luminos"
_LOG_FILE = os.path.join(_LOG_DIR, "sentinel.log")

try:
    os.makedirs(_LOG_DIR, exist_ok=True)
    _file_handler = logging.FileHandler(_LOG_FILE)
    _file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [SENTINEL] %(levelname)s: %(message)s"
    ))
    _sentinel_logger.addHandler(_file_handler)
except (OSError, PermissionError):
    # Can't write to /var/log — fall back to journal only
    pass

# ML classifier — lazy import, graceful if unavailable
_ml_available = False
try:
    from .npu_classifier import classify_behavior, get_backend_status
    from npu import NPUUnavailableError
    _ml_available = True
except ImportError:
    classify_behavior = None
    get_backend_status = None
    NPUUnavailableError = None


def assess_process(pid: int) -> dict:
    """
    Full Sentinel pipeline: collect live signals → rules → ML → log.

    LOG ONLY mode: actions are recorded in sentinel.log but never enforced.
    The "action" field in the result is informational — no process is killed or blocked.

    Returns:
        {
            "status":     "safe" | "suspicious" | "dangerous",
            "confidence": float,
            "flags":      list[str],
            "action":     "allow" | "warn" | "block",  (informational only)
            "mode":       "log_only",
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
            "mode":       "log_only",
            "error":      f"signal collection failed: {e}",
        }

    # Stage 1: Rule-based classification
    result = assess(signals)

    # Stage 2: ML classification on NPU (no CPU fallback)
    if _ml_available and classify_behavior is not None:
        try:
            ml_result = classify_behavior(signals)
            if ml_result is not None:
                result["ml_status"] = ml_result["status"]
                result["ml_confidence"] = ml_result["confidence"]
                result["ml_backend"] = ml_result["ml_backend"]

                # ML can upgrade threat level but never downgrade
                # (rule engine has final say on safe → safe stays safe from rules)
                if ml_result["status"] == "dangerous" and result["status"] == "safe":
                    result["ml_note"] = "ML flagged dangerous but rules say safe — logged"
                elif ml_result["status"] == "dangerous" and result["status"] == "suspicious":
                    result["status"] = "dangerous"
                    result["confidence"] = max(result["confidence"], ml_result["confidence"])
                    result["flags"].append("ml_upgrade")
        except Exception as e:
            # NPUUnavailableError: log and skip ML — sentinel continues with rules only
            if NPUUnavailableError and isinstance(e, NPUUnavailableError):
                _sentinel_logger.info(
                    "NPU unavailable, sentinel ML paused — using rules only"
                )
            else:
                pass

    result["pid"] = pid
    result["process_name"] = signals.get("process_name", "unknown")
    result["mode"] = "log_only"

    # Log non-safe results to sentinel.log
    if result["status"] != "safe":
        _sentinel_logger.warning(
            f"pid={pid} process={result['process_name']} "
            f"status={result['status']} confidence={result['confidence']:.2f} "
            f"flags={result['flags']} action={result['action']} (LOG ONLY)"
        )

    return result


def get_sentinel_status() -> dict:
    """Status snapshot for the settings panel."""
    status = {
        "mode": "log_only",
        "ml_available": _ml_available,
        "log_file": _LOG_FILE,
    }
    if _ml_available and get_backend_status is not None:
        try:
            status["ml_backend"] = get_backend_status()
        except Exception:
            status["ml_backend"] = {"error": "failed to query"}
    return status
