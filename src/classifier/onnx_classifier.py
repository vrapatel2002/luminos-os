"""
onnx_classifier.py
Luminos OS .exe classifier (Phase 3: MobileLLM-R1-140M AI-based).
Accepts JSON input via stdin, extracts PE features, and returns JSON decision.

# MODEL: MobileLLM-R1-140M INT8 ONNX
# ARCHITECTURE: HATS (Host-Assisted Tile-Streaming)
# NPU: npu1 (AIE2) via Triton-XDNA kernels
# CPU: Host (logic, BO management, fallback)
# [CHANGE: gemini-cli | 2026-04-20]
# [CHANGE: gemini-cli | 2026-04-22] Transition to HATS / MobileLLM-R1-140M
"""

import sys
import json
import os
import time
import logging
import numpy as np

# Ensure we can import the local feature_extractor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feature_extractor

# AI Runtime
try:
    import onnxruntime as ort
    from transformers import AutoTokenizer
    HAS_AI = True
except ImportError:
    HAS_AI = False

logger = logging.getLogger("onnx_classifier")

# Model Paths
# [CHANGE: gemini-cli | 2026-04-22] Migrating to MobileLLM-R1-140M
MODEL_DIR = os.path.expanduser("~/.local/share/luminos/models/mobilellm-r1-140m")
ONNX_PATH = os.path.join(MODEL_DIR, "model.onnx")

# [CHANGE: claude-code | 2026-04-24] Replaced HATSEngine stub with live HATS kernel.
# VitisAI EP is broken on Linux — HATS bypasses it via triton-xdna directly.
# get_ai_resources() retained for sentinel_daemon backward compat.

def get_ai_resources():
    """
    Return HATS sentinel singleton (replaces ONNX session tuple).
    Returns (sentinel, None) — callers that use (sess, tokenizer) pattern
    receive sentinel as sess; second element is unused for HATS path.
    """
    try:
        from npu.hats_kernel import get_hats_sentinel
        sentinel = get_hats_sentinel()
        return sentinel, None
    except Exception as e:
        logger.error(f"Failed to load HATS resources: {e}")
        return None, None

def classify_rules(features: dict) -> dict:
    """
    Apply Phase 2 rule-based heuristics for edge cases.
    """
    # Zone 4 (KVM): Heavy anticheat or kernel drivers
    if features.get("has_anticheat_strings") or features.get("has_kernel_driver_imports"):
        return {
            "zone": 4,
            "confidence": 0.95,
            "reason": "kernel-level security or anticheat detected"
        }

    # Zone 3 (Firecracker): Complex .NET or low-level WinAPI Wine might struggle with
    if features.get("has_kernel_api_calls"):
         return {
            "zone": 3,
            "confidence": 0.85,
            "reason": "low-level NT internal API calls"
        }

    # Zone 1 (Native): ELF binaries
    if features.get("is_elf"):
        return {
            "zone": 1,
            "confidence": 1.0,
            "reason": "native Linux ELF binary"
        }

    # Standard PEs: Rules are less certain, Phase 3 AI will refine
    if features.get("is_pe"):
        return {
            "zone": 2,
            "confidence": 0.60,  # Below 0.7 threshold triggers AI
            "reason": "standard Win32 binary"
        }

    # Default to Zone 2
    return {
        "zone": 2,
        "confidence": 0.5,
        "reason": "unknown binary type — defaulting to Wine"
    }

def classify_ai(features: dict) -> dict:
    """
    Run HATS MobileLLM-R1-140M INT8 inference for edge-case .exe routing.
    [CHANGE: claude-code | 2026-04-24] Replaced ONNX/SmolLM2 with HATS kernel.
    """
    try:
        from npu.hats_kernel import get_hats_sentinel
        from npu.training_collector import log_router
        sentinel = get_hats_sentinel()
        result = sentinel.classify_with_threshold(
            text=str(features), threshold=0.7, task="router")
        log_router(features.get('exe_path', 'unknown'), str(features),
            result['label'], result['source'],
            result['confidence'])
        
        label = result.get("label", "Zone2_Wine")
        confidence = result.get("confidence", 0.5)
        backend = result.get("backend", "unknown")
        
        zone_map = {"Zone2_Wine": 2, "Zone3_Firecracker": 3, "Zone4_KVM": 4}
        zone = zone_map.get(label, 2)

        # Fall back to Zone2 if confidence too low
        if confidence < 0.5:
            return {
                "zone": 2,
                "confidence": confidence,
                "reason": f"HATS low confidence ({confidence:.2f}), defaulting to Wine",
            }

        return {
            "zone": zone,
            "confidence": confidence,
            "reason": f"HATS ({backend}) zone={zone} conf={confidence:.2f}",
        }
    except Exception as e:
        logger.error(f"HATS classify_ai failed: {e}")
        return {"zone": 2, "confidence": 0.5, "reason": f"HATS error: {e}"}

def main():
    try:
        # Read request from stdin
        raw_input = sys.stdin.read()
        if not raw_input:
            print(json.dumps({"error": "empty input"}))
            return

        req = json.loads(raw_input)
        path = req.get("path")

        if not path or not os.path.exists(path):
            # If features are provided directly (for testing)
            if "features" in req:
                features = req["features"]
            else:
                print(json.dumps({"error": f"path not found: {path}"}))
                return
        else:
            # Extract features
            features = feature_extractor.extract_features(path)

        # Step 1: Rules
        decision = classify_rules(features)

        # Step 2: AI (if confidence < 0.7)
        if decision["confidence"] < 0.7:
            ai_decision = classify_ai(features)
            ai_decision["path"] = path if path else "test"
            ai_decision["method"] = "model"
            print(json.dumps(ai_decision))
        else:
            decision["path"] = path if path else "test"
            decision["method"] = "rules"
            print(json.dumps(decision))

    except Exception as e:
        print(json.dumps({"error": str(e), "zone": 2}))

if __name__ == "__main__":
    main()
