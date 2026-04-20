"""
onnx_classifier.py
Luminos OS .exe classifier (Phase 2: Rule-based, Phase 3: AI-based).
Accepts JSON input via stdin, extracts PE features, and returns JSON decision.
[CHANGE: gemini-cli | 2026-04-20]
"""

import sys
import json
import os

# Ensure we can import the local feature_extractor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feature_extractor

def classify_rules(features: dict) -> dict:
    """
    Apply Phase 2 rule-based heuristics for edge cases.
    Phase 3: This will be replaced by Phi-3-mini Q4 ONNX inference.
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

    # Zone 2 (Wine): Standard Win32 apps, .NET, DX9-11
    if features.get("is_pe"):
        return {
            "zone": 2,
            "confidence": 0.90,
            "reason": "standard Win32 binary"
        }

    # Zone 1 (Native): ELF binaries (though the router primarily handles .exe)
    if features.get("is_elf"):
        return {
            "zone": 1,
            "confidence": 1.0,
            "reason": "native Linux ELF binary"
        }

    # Default to Zone 2
    return {
        "zone": 2,
        "confidence": 0.5,
        "reason": "unknown binary type — defaulting to Wine"
    }

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
            print(json.dumps({"error": f"path not found: {path}"}))
            return

        # Extract features
        features = feature_extractor.extract_features(path)

        # Classify
        decision = classify_rules(features)

        # Add path for context
        decision["path"] = path
        
        # Phase 3: replace rules with Phi-3-mini Q4
        # decision["model"] = "phi-3-mini-q4"

        print(json.dumps(decision))

    except Exception as e:
        print(json.dumps({"error": str(e), "zone": 2}))

if __name__ == "__main__":
    main()
