"""
src/classifier/ai_fallback.py
Stage 2 AI fallback for the compatibility router.

Called only when the rule engine returns no confident decision (rule_matched=False).
Uses llama.cpp on CPU with a sub-1GB GGUF model to classify edge cases.

Architecture:
  - Model runs on CPU only — never GPU or NPU (scope doc rule)
  - AI result is a suggestion — rule engine can override
  - If llama.cpp is not available, returns the rule engine's best guess unchanged
  - Model path: /opt/luminos/models/router.gguf (deployed at install)

Pure stdlib + subprocess — no Python ML dependencies.
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger("luminos-ai.classifier.ai_fallback")

_MODEL_PATH = "/opt/luminos/models/router.gguf"
_LLAMA_CANDIDATES = [
    "/usr/bin/llama-cli",
    "/usr/local/bin/llama-cli",
    os.path.expanduser("~/.local/bin/llama-cli"),
    "/usr/bin/llama",
    "/usr/local/bin/llama",
]

# Valid layer outputs the AI can suggest
_VALID_LAYERS = {"proton", "wine", "lutris", "firecracker", "kvm"}


def _find_llama() -> str | None:
    """Find the llama.cpp CLI binary."""
    for candidate in _LLAMA_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _build_prompt(features: dict) -> str:
    """Build a classification prompt from extracted binary features."""
    lines = [
        "You are a Windows application compatibility classifier for a Linux OS.",
        "Given the following binary analysis, respond with exactly one word:",
        "proton, wine, lutris, firecracker, or kvm.",
        "",
        "Binary features:",
        f"  PE format: {features.get('is_pe', False)}",
        f"  Win32 imports: {features.get('has_win32_imports', False)}",
        f"  Kernel driver imports: {features.get('has_kernel_driver_imports', False)}",
        f"  Kernel API calls: {features.get('has_kernel_api_calls', False)}",
        f"  Anticheat strings: {features.get('has_anticheat_strings', False)}",
        f"  DirectX 9: {features.get('has_dx9', False)}",
        f"  DirectX 10: {features.get('has_dx10', False)}",
        f"  DirectX 11: {features.get('has_dx11', False)}",
        f"  DirectX 12: {features.get('has_dx12', False)}",
        f"  .NET runtime: {features.get('has_dotnet', False)}",
        f"  Vulkan: {features.get('has_vulkan', False)}",
        f"  OpenGL: {features.get('has_opengl', False)}",
        f"  File size: {features.get('file_size_mb', 0):.1f} MB",
        "",
        "Rules (you cannot override these):",
        "  - Anticheat present → must be kvm",
        "  - Kernel-level access → must be firecracker",
        "  - DX12 → prefer proton",
        "  - DX9/10/11 → prefer proton",
        "  - .NET only → prefer wine",
        "",
        "Your classification (one word):",
    ]
    return "\n".join(lines)


def ai_classify(features: dict, rule_result: dict) -> dict:
    """
    Run AI fallback classification on CPU via llama.cpp.

    Only called when rule_result["rule_matched"] is False. The AI suggestion
    is validated against the rule engine's guardrails — AI cannot override
    hard rules (e.g. anticheat must always be kvm).

    Args:
        features:    Dict from feature_extractor.extract_features()
        rule_result: Dict from zone_rules.classify() (the uncertain result)

    Returns:
        Updated decision dict. If AI is unavailable, returns rule_result unchanged.
    """
    # If rules already matched confidently, skip AI
    if rule_result.get("rule_matched", True):
        return rule_result

    llama_path = _find_llama()
    if not llama_path:
        logger.debug("llama.cpp not found — using rule engine result as-is")
        return rule_result

    if not os.path.isfile(_MODEL_PATH):
        logger.debug(f"Router model not found at {_MODEL_PATH} — using rule engine result")
        return rule_result

    prompt = _build_prompt(features)

    try:
        result = subprocess.run(
            [
                llama_path,
                "-m", _MODEL_PATH,
                "-p", prompt,
                "-n", "10",           # max tokens — we only need one word
                "--temp", "0.1",      # low temperature for determinism
                "--threads", "4",     # CPU only, 4 threads
                "--no-display-prompt",
            ],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},  # force CPU
        )

        if result.returncode != 0:
            logger.debug(f"llama.cpp returned code {result.returncode}")
            return rule_result

        # Parse the AI output — look for a valid layer word
        output = result.stdout.strip().lower()
        ai_layer = None
        for word in output.split():
            cleaned = word.strip(".,;:!?\"'")
            if cleaned in _VALID_LAYERS:
                ai_layer = cleaned
                break

        if ai_layer is None:
            logger.debug(f"AI output not parseable: {output!r}")
            return rule_result

        # Guardrail: AI cannot override hard rules
        if features.get("has_anticheat_strings") and ai_layer != "kvm":
            logger.debug(f"AI suggested {ai_layer} but anticheat present — forcing kvm")
            ai_layer = "kvm"
        if features.get("has_kernel_driver_imports") and ai_layer not in ("firecracker", "kvm"):
            logger.debug(f"AI suggested {ai_layer} but kernel drivers present — forcing firecracker")
            ai_layer = "firecracker"

        # Map layer to zone
        zone = _layer_to_zone(ai_layer)

        return {
            "zone":         zone,
            "layer":        ai_layer,
            "confidence":   0.70,
            "reason":       f"AI classification: {ai_layer} (rule engine uncertain)",
            "rule_matched": False,
            "ai_used":      True,
        }

    except subprocess.TimeoutExpired:
        logger.warning("AI classification timed out (30s)")
        return rule_result
    except (FileNotFoundError, OSError) as e:
        logger.debug(f"AI classification error: {e}")
        return rule_result


def _layer_to_zone(layer: str) -> int:
    """Map a layer name to its zone number."""
    return {
        "native":      1,
        "wine":        2,
        "proton":      2,
        "lutris":      2,
        "firecracker": 3,
        "kvm":         3,
    }.get(layer, 2)
