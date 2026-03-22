"""
src/classifier/__init__.py
Public API for the Luminos binary zone classifier.

Usage:
    from classifier import classify_binary
    result = classify_binary("/path/to/app.exe")
    # {"zone": 2, "confidence": 0.85, "reason": "Win32 application — Wine/Proton compatible"}
"""

from .feature_extractor import extract_features
from .zone_rules import classify


def classify_binary(path: str) -> dict:
    """
    Full pipeline: extract features from binary at `path`, apply zone rules.

    Returns:
        {"zone": 1|2|3, "confidence": float, "reason": str}

    Raises:
        FileNotFoundError: if path does not exist
        OSError: if file cannot be read
    """
    features = extract_features(path)
    decision = classify(features)
    return decision
