"""
src/classifier/ai_fallback.py
Stage 2 AI fallback for the compatibility router.

Called only when the rule engine returns no confident decision (rule_matched=False).
Uses the NPU abstraction layer for AI inference.

Architecture:
  - Rule engine handles 80% of cases (pure Python, no NPU)
  - AI fallback handles remaining 20% edge cases via NPU
  - AI result is a suggestion — rule engine guardrails cannot be overridden
  - If NPU unavailable: wait, do not reroute to CPU or GPU

Model: ONNX classification model at /opt/luminos/models/router.onnx
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.classifier.ai_fallback")

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from npu import NPUInterface, NPUUnavailableError, NPUModelNotLoadedError

_MODEL_PATH = "/opt/luminos/models/router.onnx"

# Valid layer outputs the AI can suggest
_VALID_LAYERS = {"proton", "wine", "lutris", "firecracker", "kvm"}

# Module-level NPU interface
_npu = NPUInterface()
_model_loaded = False


def _ensure_model():
    """Load router model onto NPU if not already loaded."""
    global _model_loaded
    if _model_loaded:
        return
    if _npu.is_available() and os.path.isfile(_MODEL_PATH):
        _model_loaded = _npu.load_model(_MODEL_PATH, "router")
        if _model_loaded:
            logger.info(f"Router AI model loaded on NPU: {_MODEL_PATH}")
        else:
            logger.warning("Router AI model failed to load on NPU")
    elif not os.path.isfile(_MODEL_PATH):
        logger.debug(f"Router model not found at {_MODEL_PATH}")


def ai_classify(features: dict, rule_result: dict) -> dict:
    """
    Run AI fallback classification on NPU.

    Only called when rule_result["rule_matched"] is False. The AI suggestion
    is validated against the rule engine's guardrails — AI cannot override
    hard rules (e.g. anticheat must always be kvm).

    Args:
        features:    Dict from feature_extractor.extract_features()
        rule_result: Dict from zone_rules.classify() (the uncertain result)

    Returns:
        Updated decision dict. If NPU is unavailable, returns rule_result unchanged.
    """
    # If rules already matched confidently, skip AI
    if rule_result.get("rule_matched", True):
        return rule_result

    _ensure_model()

    if not _npu.is_available():
        logger.debug("NPU not available — using rule engine result as-is")
        return rule_result

    if not _model_loaded:
        logger.debug("Router model not loaded — using rule engine result")
        return rule_result

    # Build exe_data for NPU interface
    exe_data = {
        "path": features.get("path", ""),
        "is_pe": features.get("is_pe", False),
        "has_win32_imports": features.get("has_win32_imports", False),
        "has_kernel_driver_imports": features.get("has_kernel_driver_imports", False),
        "has_kernel_api_calls": features.get("has_kernel_api_calls", False),
        "has_anticheat_strings": features.get("has_anticheat_strings", False),
        "has_dx9": features.get("has_dx9", False),
        "has_dx10": features.get("has_dx10", False),
        "has_dx11": features.get("has_dx11", False),
        "has_dx12": features.get("has_dx12", False),
        "has_dotnet": features.get("has_dotnet", False),
        "has_vulkan": features.get("has_vulkan", False),
        "has_opengl": features.get("has_opengl", False),
        "file_size_mb": features.get("file_size_mb", 0.0),
        "pe_headers": features.get("pe_headers", {}),
        "apis": features.get("apis", []),
    }

    try:
        result = _npu.run_router(exe_data)
        ai_layer = result.get("layer", "proton")
        confidence = result.get("confidence", 0.70)

        # Validate layer
        if ai_layer not in _VALID_LAYERS:
            logger.debug(f"NPU returned invalid layer: {ai_layer}")
            return rule_result

        # Guardrail: AI cannot override hard rules
        if features.get("has_anticheat_strings") and ai_layer != "kvm":
            logger.debug(
                f"AI suggested {ai_layer} but anticheat present — forcing kvm"
            )
            ai_layer = "kvm"
        if features.get("has_kernel_driver_imports") and ai_layer not in (
            "firecracker", "kvm"
        ):
            logger.debug(
                f"AI suggested {ai_layer} but kernel drivers present "
                "— forcing firecracker"
            )
            ai_layer = "firecracker"

        zone = _layer_to_zone(ai_layer)

        return {
            "zone": zone,
            "layer": ai_layer,
            "confidence": confidence,
            "reason": f"NPU AI classification: {ai_layer} "
                      f"(rule engine uncertain)",
            "rule_matched": False,
            "ai_used": True,
        }

    except NPUUnavailableError:
        logger.info("NPU unavailable for router AI — using rule engine result")
        return rule_result
    except NPUModelNotLoadedError:
        logger.debug("Router model not loaded on NPU")
        return rule_result
    except Exception as e:
        logger.debug(f"NPU AI classification error: {e}")
        return rule_result


def _layer_to_zone(layer: str) -> int:
    """Map a layer name to its zone number."""
    return {
        "native": 1,
        "wine": 2,
        "proton": 2,
        "lutris": 2,
        "firecracker": 3,
        "kvm": 3,
    }.get(layer, 2)
