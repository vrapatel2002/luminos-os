"""
src/hardware/gpu_guard.py
supergfxctl Hybrid mode enforcement.

Runs at session start, every single time, no exceptions.
If mode is not Hybrid: logs CRITICAL, attempts to set Hybrid.
NEVER crashes the session if this fails.
"""

import logging
import subprocess

logger = logging.getLogger("luminos-ai.hardware.gpu_guard")


def assert_hybrid_mode() -> dict:
    """
    Check supergfxctl mode. If not Hybrid, attempt to correct it.

    Returns:
        {
            "mode": str | None,
            "is_hybrid": bool,
            "corrected": bool,
            "available": bool,
        }

    NEVER crashes the session — just logs and continues.
    """
    result = {
        "mode": None,
        "is_hybrid": False,
        "corrected": False,
        "available": False,
    }

    # Read current mode
    mode = _get_mode()
    if mode is None:
        logger.warning(
            "supergfxctl not available — cannot verify Hybrid mode. "
            "Install with: yay -S supergfxctl"
        )
        return result

    result["available"] = True
    result["mode"] = mode

    if _is_hybrid(mode):
        result["is_hybrid"] = True
        logger.info("GPU mode: Hybrid (correct)")
        return result

    # Mode is NOT Hybrid — attempt to correct
    logger.critical(
        f"GPU mode is '{mode}' — expected Hybrid. "
        "Attempting to correct..."
    )

    try:
        subprocess.run(
            ["supergfxctl", "--mode", "Hybrid"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.critical(f"Failed to set Hybrid mode: {e}")
        return result

    # Verify it changed
    verify_mode = _get_mode()
    if verify_mode and _is_hybrid(verify_mode):
        result["mode"] = verify_mode
        result["is_hybrid"] = True
        result["corrected"] = True
        logger.info("GPU mode corrected to Hybrid")
    else:
        logger.critical(
            f"Could not set Hybrid mode (still '{verify_mode}'). "
            "Manual intervention required. "
            "Run: supergfxctl --mode Hybrid"
        )
        result["mode"] = verify_mode

    return result


def _get_mode() -> str | None:
    """Query current supergfxctl GPU mode."""
    try:
        result = subprocess.run(
            ["supergfxctl", "--get"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Try --mode flag (some versions)
    try:
        result = subprocess.run(
            ["supergfxctl", "--mode"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return None


def _is_hybrid(mode: str) -> bool:
    """Check if mode string indicates Hybrid."""
    return mode.lower().strip() in ("hybrid", "hybrid mode")
