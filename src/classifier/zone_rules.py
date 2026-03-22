"""
zone_rules.py
Rule-based zone classifier. Takes extracted features, returns zone decision.

Zones:
  1 — Native Linux (run directly)
  2 — Windows PE, Wine/Proton compatible
  3 — Kernel-level / anti-cheat — requires Firecracker microVM or block
"""


def classify(features: dict) -> dict:
    """
    Apply priority-ordered rules to extracted features.

    Args:
        features: dict from feature_extractor.extract_features()

    Returns:
        {"zone": int, "confidence": float, "reason": str}
    """
    is_elf   = features.get("is_elf", False)
    is_pe    = features.get("is_pe", False)
    has_kern = features.get("has_kernel_driver_imports", False)
    has_ac   = features.get("has_anticheat_strings", False)
    has_w32  = features.get("has_win32_imports", False)

    # Rule 1 — Native Linux ELF
    if is_elf:
        return {
            "zone": 1,
            "confidence": 0.99,
            "reason": "Native Linux binary",
        }

    # Rule 2 — PE with kernel-driver imports (highest risk, Zone 3 first)
    if is_pe and has_kern:
        return {
            "zone": 3,
            "confidence": 0.95,
            "reason": "Kernel-level driver detected",
        }

    # Rule 3 — PE with anti-cheat strings
    if is_pe and has_ac:
        return {
            "zone": 3,
            "confidence": 0.90,
            "reason": "Anti-cheat software detected",
        }

    # Rule 4 — PE with Win32 imports (normal Windows app)
    if is_pe and has_w32:
        return {
            "zone": 2,
            "confidence": 0.85,
            "reason": "Win32 application — Wine/Proton compatible",
        }

    # Rule 5 — PE with no known imports
    if is_pe:
        return {
            "zone": 2,
            "confidence": 0.70,
            "reason": "PE binary, no driver imports",
        }

    # Fallback — unknown binary type
    return {
        "zone": 1,
        "confidence": 0.50,
        "reason": "Unknown binary type",
    }
