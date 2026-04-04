"""
src/gpu_manager/__init__.py
Public API for the Luminos GPU Manager.

Philosophy: NVIDIA is OFF by default.
One model at a time. 5-minute idle timeout. Gaming mode evicts instantly.
supergfxctl MUST stay in Hybrid mode — never changed by any code.

Usage:
    from gpu_manager import request_model, enter_gaming_mode, get_hardware_status
    result = request_model("nexus")
    # {"loaded": "nexus", "quantization": "Q4", "layers": 32, ...}
"""

import logging
import subprocess

from .model_manager import ModelManager
from .vram_monitor import get_full_hardware_status, get_nvidia_vram
from .process_watcher import scan_running_games, is_gaming_process

logger = logging.getLogger("luminos-ai.gpu_manager")

# Module-level singleton — one manager for the lifetime of the daemon
_manager = ModelManager()


# ---------------------------------------------------------------------------
# supergfxctl guard — NEVER change GPU mode from Hybrid
# ---------------------------------------------------------------------------

def _get_supergfxctl_mode() -> str | None:
    """Query current supergfxctl GPU mode. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["supergfxctl", "--get"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def assert_hybrid_mode() -> dict:
    """
    Verify supergfxctl is in Hybrid mode.
    Logs a warning if not — but NEVER changes the mode.
    This is a read-only safety check.

    Returns:
        {"mode": str|None, "is_hybrid": bool, "supergfxctl_available": bool}
    """
    mode = _get_supergfxctl_mode()
    if mode is None:
        return {"mode": None, "is_hybrid": False, "supergfxctl_available": False}

    is_hybrid = mode.lower() in ("hybrid", "hybrid mode")
    if not is_hybrid:
        logger.warning(
            f"supergfxctl mode is '{mode}' — expected Hybrid. "
            f"Luminos never changes this. Check if something else modified it."
        )
    return {"mode": mode, "is_hybrid": is_hybrid, "supergfxctl_available": True}


# Run the guard on import (daemon startup)
_gpu_mode_check = assert_hybrid_mode()
if _gpu_mode_check["supergfxctl_available"] and not _gpu_mode_check["is_hybrid"]:
    logger.warning("GPU mode is NOT Hybrid at daemon startup — this may cause issues")


# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------

def get_hardware_status() -> dict:
    """Full hardware snapshot: NVIDIA + AMD iGPU + NPU + timestamp."""
    return get_full_hardware_status()


# ---------------------------------------------------------------------------
# Model lifecycle
# ---------------------------------------------------------------------------

def request_model(model_name: str) -> dict:
    """
    Wake NVIDIA and load model_name. Evicts any different active model first.
    Queries live VRAM to pick the best quantization automatically.
    """
    nvidia_info  = get_nvidia_vram()
    free_vram_mb = nvidia_info.get("free_mb", 0) if nvidia_info.get("available") else 0
    return _manager.request_model(model_name, free_vram_mb)


def release_model() -> dict:
    """
    Immediately unload the active model and idle NVIDIA.
    Use this when a task is done and no further AI work is expected soon.
    """
    unloaded = _manager._unload_current()
    return {
        "unloaded": unloaded,
        "reason":   "explicit release — NVIDIA idled",
    }


def check_idle_timeout() -> dict:
    """
    Check if the active model has exceeded the idle timeout.
    Call this from a periodic timer (every ~60 seconds).
    """
    return _manager.release_model_if_idle()


# ---------------------------------------------------------------------------
# Gaming mode
# ---------------------------------------------------------------------------

def enter_gaming_mode() -> dict:
    """Game starting — evict model, free NVIDIA VRAM immediately."""
    return _manager.enter_gaming_mode()


def exit_gaming_mode() -> dict:
    """Game finished — return to idle. Does NOT pre-load anything."""
    return _manager.exit_gaming_mode()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_status() -> dict:
    """Full manager state: active model, gaming mode, nvidia_active, idle timer, GPU mode."""
    status = _manager.get_status()
    status["gpu_mode"] = assert_hybrid_mode()
    return status
