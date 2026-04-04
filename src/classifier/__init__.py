"""
src/classifier/__init__.py
Public API for the Luminos compatibility router.

Two-stage architecture:
  Stage 1: Rule engine (fast, deterministic, handles ~80% of binaries)
  Stage 2: AI model fallback (llama.cpp on CPU, handles edge cases)

Results are cached by file hash in ~/.cache/luminos/router/.

Usage:
    from classifier import classify_binary
    result = classify_binary("/path/to/app.exe")
    # {"zone": 2, "layer": "proton", "confidence": 0.90, "reason": "...", "cached": False}

Layer outputs: proton | wine | lutris | firecracker | kvm | native
"""

from .feature_extractor import extract_features
from .zone_rules import classify
from .ai_fallback import ai_classify
from .cache import get_cached, store


def classify_binary(path: str) -> dict:
    """
    Full router pipeline: cache check → feature extraction → rules → AI fallback.

    Args:
        path: Path to the executable file.

    Returns:
        {
            "zone": 1|2|3,
            "layer": "proton"|"wine"|"lutris"|"firecracker"|"kvm"|"native",
            "confidence": float,
            "reason": str,
            "cached": bool,
        }

    Raises:
        FileNotFoundError: if path does not exist
        OSError: if file cannot be read
    """
    # Stage 0 — Cache lookup
    cached = get_cached(path)
    if cached:
        return cached

    # Stage 1 — Feature extraction + rule engine
    features = extract_features(path)
    decision = classify(features)

    # Stage 2 — AI fallback (only if rules are uncertain)
    if not decision.get("rule_matched", True):
        decision = ai_classify(features, decision)

    # Store in cache
    decision["cached"] = False
    store(path, decision)

    return decision
