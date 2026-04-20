"""
onnx_classifier.py
Luminos OS .exe classifier (Phase 3: SmolLM2-135M AI-based).
Accepts JSON input via stdin, extracts PE features, and returns JSON decision.

# MODEL: SMOLLM2-135M INT8 ONNX (~140MB + ~60MB runtime)
# RAM LIMIT: SOFT 300MB / HARD 800MB
# NPU: VitisAI EP if available, CPU fallback
# [CHANGE: gemini-cli | 2026-04-20]
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
MODEL_DIR = os.path.expanduser("~/.local/share/luminos/models/smollm2-135m")
ONNX_PATH = os.path.join(MODEL_DIR, "onnx/model_int8.onnx")

# Global session singleton
_SESSION = None
_TOKENIZER = None

def get_ai_resources():
    """Load and return the ONNX session and tokenizer (singleton)."""
    global _SESSION, _TOKENIZER
    if not HAS_AI:
        return None, None
    
    if _SESSION is None:
        if not os.path.exists(ONNX_PATH):
            logger.error(f"Model not found at {ONNX_PATH}")
            return None, None
            
        try:
            # Try VitisAI EP first, then CPU
            providers = ["VitisAIExecutionProvider", "CPUExecutionProvider"]
            _SESSION = ort.InferenceSession(ONNX_PATH, providers=providers)
            _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_DIR)
            logger.info(f"Loaded SmolLM2-135M via {_SESSION.get_providers()[0]}")
        except Exception as e:
            logger.error(f"Failed to load AI resources: {e}")
            _SESSION = None
            
    return _SESSION, _TOKENIZER

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
    """Run SmolLM2-135M inference for refined classification."""
    sess, tokenizer = get_ai_resources()
    if sess is None:
        return {"zone": 2, "confidence": 0.5, "reason": "AI unavailable, fallback to Wine"}

    prompt = (
        "Windows app classification task.\n"
        f"Features: {json.dumps(features)}\n"
        "Choose one label: Zone2_Wine Zone3_Firecracker Zone4_KVM\n"
        "Label:"
    )
    
    try:
        inputs = tokenizer(prompt, return_tensors="np")
        # Align inputs with ONNX names
        ort_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        
        # Add dummy position_ids if required by model
        for inp in sess.get_inputs():
            if inp.name == "position_ids":
                ort_inputs[inp.name] = np.arange(ort_inputs["input_ids"].shape[1]).reshape(1, -1).astype(np.int64)
            elif inp.name.startswith("past_key_values"):
                # Handle KV cache stubs if present (empty input for first pass)
                shape = [1 if (s == "batch_size" or isinstance(s, str)) else s for s in inp.shape]
                shape = [s if s is not None else 0 for s in shape]
                ort_inputs[inp.name] = np.zeros(shape, dtype=np.float32)

        outputs = sess.run(None, ort_inputs)
        # Parse first token of output (logits -> argmax)
        # For simplicity in Phase 3, we just take the highest logit of the first new token
        logits = outputs[0]
        next_token_id = np.argmax(logits[0, -1, :])
        token_str = tokenizer.decode([next_token_id]).strip().lower()
        
        zone = 2
        if "zone3" in token_str: zone = 3
        elif "zone4" in token_str: zone = 4
        
        return {
            "zone": zone,
            "confidence": 0.80,
            "reason": f"AI classified as {token_str}"
        }
    except Exception as e:
        logger.error(f"AI inference failed: {e}")
        return {"zone": 2, "confidence": 0.5, "reason": f"AI error: {str(e)}"}

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
