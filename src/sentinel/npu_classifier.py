"""
sentinel/npu_classifier.py
ML-based process threat classifier via the NPU abstraction layer.

All NPU access goes through npu.NPUInterface — no direct ONNX or driver calls.
If NPU is unavailable, raises NPUUnavailableError. Sentinel waits and retries.
No CPU fallback — the NPU is the only backend.

Model: SmolLM2-360M or DistilBERT (deployed at /opt/luminos/models/sentinel.onnx)
The model classifies process behavior vectors into: safe, suspicious, dangerous.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.sentinel.npu")

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from npu import NPUInterface, NPUUnavailableError, NPUModelNotLoadedError

_MODEL_PATH = "/opt/luminos/models/sentinel.onnx"

# Module-level NPU interface — shared across all calls
_npu = NPUInterface()
_model_loaded = False


def _ensure_model():
    """Load sentinel model onto NPU if not already loaded."""
    global _model_loaded
    if _model_loaded:
        return
    if _npu.is_available() and os.path.isfile(_MODEL_PATH):
        _model_loaded = _npu.load_model(_MODEL_PATH, "sentinel")
        if _model_loaded:
            logger.info(f"Sentinel ML model loaded on NPU: {_MODEL_PATH}")
        else:
            logger.warning("Sentinel ML model failed to load on NPU")
    elif not os.path.isfile(_MODEL_PATH):
        logger.debug(f"Sentinel model not found at {_MODEL_PATH}")


def classify_behavior(signals: dict) -> dict | None:
    """
    Run ML classification on process behavioral signals via NPU.

    Args:
        signals: Dict from process_monitor.get_process_signals()

    Returns:
        {"status": str, "confidence": float, "ml_backend": str}

    Raises:
        NPUUnavailableError: if NPU is not available (caller must wait)
    """
    _ensure_model()

    if not _npu.is_available():
        raise NPUUnavailableError("NPU unavailable — sentinel ML paused")

    if not _model_loaded:
        return None

    # Build data dict for NPU interface
    data = {
        "syscalls": [],  # populated by process_monitor in real pipeline
        "process": signals.get("process_name", "unknown"),
        "pid": signals.get("pid", 0),
        "is_elevated": signals.get("is_elevated", False),
        "cpu_percent": signals.get("cpu_percent", 0.0),
        "memory_mb": signals.get("memory_mb", 0.0),
        "open_files_count": signals.get("open_files_count", 0),
        "network_connections": signals.get("network_connections", 0),
        "child_process_count": signals.get("child_process_count", 0),
    }

    try:
        result = _npu.run_sentinel(data)

        # Map NPU output to sentinel's expected format
        classification = result.get("classification", "normal")
        status_map = {
            "normal": "safe",
            "suspicious": "suspicious",
            "block": "dangerous",
        }

        return {
            "status": status_map.get(classification, "safe"),
            "confidence": result.get("confidence", 0.5),
            "ml_backend": "npu",
        }
    except NPUUnavailableError:
        raise  # propagate — caller must wait
    except NPUModelNotLoadedError:
        logger.debug("Sentinel model not loaded on NPU")
        return None
    except Exception as e:
        logger.debug(f"Sentinel NPU inference failed: {e}")
        return None


def get_backend_status() -> dict:
    """Return current ML backend status for the settings panel."""
    status = _npu.status()
    return {
        "npu_available": status["available"],
        "cpu_fallback": False,  # no CPU fallback — NPU only
        "model_loaded": _model_loaded,
        "model_path": _MODEL_PATH,
        "driver": status["driver"],
        "current_task": status["current_task"],
    }
