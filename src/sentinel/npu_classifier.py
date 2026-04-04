"""
sentinel/npu_classifier.py
ML-based process threat classifier targeting AMD XDNA NPU with CPU fallback.

Architecture:
  - Primary: ONNX model on AMD NPU via onnxruntime (/dev/accel/accel0 + amdxdna)
  - Fallback: Same ONNX model on CPU via onnxruntime
  - Last resort: Skip ML classification, return None (rule engine handles it)

Model: SmolLM2-360M or DistilBERT (deployed at /opt/luminos/models/sentinel.onnx)
The model classifies process behavior vectors into: safe, suspicious, dangerous.

Pure inference — no training, no fine-tuning at runtime.
"""

import logging
import os

logger = logging.getLogger("luminos-ai.sentinel.npu")

_MODEL_PATH = "/opt/luminos/models/sentinel.onnx"
_NPU_AVAILABLE = False
_CPU_AVAILABLE = False
_session = None


def _detect_npu() -> bool:
    """Check if AMD XDNA NPU is available."""
    if not os.path.exists("/dev/accel/accel0"):
        return False
    try:
        with open("/proc/modules", "r") as f:
            modules = f.read()
        return "amdxdna" in modules
    except OSError:
        return False


def _init_session():
    """Initialize ONNX runtime session — NPU preferred, CPU fallback."""
    global _session, _NPU_AVAILABLE, _CPU_AVAILABLE

    if _session is not None:
        return _session

    if not os.path.isfile(_MODEL_PATH):
        logger.debug(f"Sentinel model not found at {_MODEL_PATH} — ML classification disabled")
        return None

    try:
        import onnxruntime as ort
    except ImportError:
        logger.debug("onnxruntime not installed — ML classification disabled")
        return None

    # Try NPU first
    if _detect_npu():
        try:
            _session = ort.InferenceSession(
                _MODEL_PATH,
                providers=["VitisAIExecutionProvider"],
            )
            _NPU_AVAILABLE = True
            logger.info("Sentinel ML: running on AMD NPU")
            return _session
        except Exception as e:
            logger.debug(f"NPU init failed ({e}) — falling back to CPU")

    # CPU fallback
    try:
        _session = ort.InferenceSession(
            _MODEL_PATH,
            providers=["CPUExecutionProvider"],
        )
        _CPU_AVAILABLE = True
        logger.info("Sentinel ML: running on CPU (NPU not available)")
        return _session
    except Exception as e:
        logger.debug(f"CPU ONNX init failed: {e}")
        return None


def classify_behavior(signals: dict) -> dict | None:
    """
    Run ML classification on process behavioral signals.

    Args:
        signals: Dict from process_monitor.get_process_signals()

    Returns:
        {"status": str, "confidence": float, "ml_backend": str} or None if unavailable.
    """
    session = _init_session()
    if session is None:
        return None

    # Build feature vector from signals
    import numpy as np

    features = np.array([[
        signals.get("cpu_percent", 0.0),
        signals.get("memory_mb", 0.0),
        signals.get("open_files_count", 0),
        signals.get("network_connections", 0),
        signals.get("child_process_count", 0),
        1.0 if signals.get("is_elevated", False) else 0.0,
        1.0 if signals.get("cmdline_has_suspicious", False) else 0.0,
    ]], dtype=np.float32)

    try:
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: features})

        # Model output: [batch, 3] logits for [safe, suspicious, dangerous]
        logits = outputs[0][0]
        probs = _softmax(logits)
        labels = ["safe", "suspicious", "dangerous"]
        idx = int(probs.argmax())

        backend = "npu" if _NPU_AVAILABLE else "cpu"
        return {
            "status": labels[idx],
            "confidence": round(float(probs[idx]), 3),
            "ml_backend": backend,
        }
    except Exception as e:
        logger.debug(f"ML inference failed: {e}")
        return None


def _softmax(x):
    """Stable softmax."""
    import numpy as np
    e = np.exp(x - np.max(x))
    return e / e.sum()


def get_backend_status() -> dict:
    """Return current ML backend status for the settings panel."""
    return {
        "npu_available": _NPU_AVAILABLE or _detect_npu(),
        "cpu_fallback": _CPU_AVAILABLE,
        "model_loaded": _session is not None,
        "model_path": _MODEL_PATH,
    }
