"""
vram_monitor.py
Read live VRAM / GPU / NPU hardware state.
Pure stdlib + nvidia-smi subprocess — no Python GPU libraries.

Philosophy: this module observes only. It never loads models or changes state.
"""

import glob
import logging
import os
import subprocess
import time

logger = logging.getLogger("luminos-ai.gpu_manager.vram")


# ---------------------------------------------------------------------------
# NVIDIA (discrete GPU)
# ---------------------------------------------------------------------------

def get_nvidia_vram() -> dict:
    """
    Query NVIDIA VRAM and utilisation via nvidia-smi.

    Returns on success:
        {"available": True, "total_mb": int, "free_mb": int,
         "used_mb": int, "gpu_utilization_percent": float}
    Returns on failure:
        {"available": False}
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.free,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {"available": False}

        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            return {"available": False}

        total_mb = int(parts[0])
        free_mb  = int(parts[1])
        used_mb  = int(parts[2])
        util_pct = float(parts[3])

        return {
            "available":               True,
            "total_mb":                total_mb,
            "free_mb":                 free_mb,
            "used_mb":                 used_mb,
            "gpu_utilization_percent": util_pct,
        }

    except (FileNotFoundError, subprocess.TimeoutExpired,
            ValueError, IndexError, OSError):
        return {"available": False}


# ---------------------------------------------------------------------------
# AMD iGPU (RDNA3)
# ---------------------------------------------------------------------------

_AMD_VRAM_SYSFS_GLOBS = [
    "/sys/class/drm/card*/device/mem_info_vram_total",
    "/sys/class/drm/renderD*/device/mem_info_vram_total",
]


def _read_sysfs_int(path: str) -> int | None:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def get_amd_vram() -> dict:
    """
    Read AMD iGPU VRAM from sysfs.

    Returns on success:
        {"available": True, "total_mb": int, "used_mb": int, "free_mb": int}
    Returns on failure:
        {"available": False}
    """
    total_path = None
    for pattern in _AMD_VRAM_SYSFS_GLOBS:
        matches = glob.glob(pattern)
        if matches:
            total_path = matches[0]
            break

    if not total_path:
        return {"available": False}

    total_bytes = _read_sysfs_int(total_path)
    used_path   = total_path.replace("mem_info_vram_total", "mem_info_vram_used")
    used_bytes  = _read_sysfs_int(used_path)

    if total_bytes is None:
        return {"available": False}

    total_mb = total_bytes // (1024 * 1024)
    used_mb  = (used_bytes // (1024 * 1024)) if used_bytes is not None else 0
    free_mb  = max(0, total_mb - used_mb)

    return {
        "available": True,
        "total_mb":  total_mb,
        "used_mb":   used_mb,
        "free_mb":   free_mb,
    }


# ---------------------------------------------------------------------------
# AMD XDNA NPU
# ---------------------------------------------------------------------------

_NPU_DEVICE_PATH = "/dev/accel/accel0"
_NPU_DRIVER_NAME = "amdxdna"


def _driver_loaded(driver: str) -> bool:
    """Return True if kernel module is present in lsmod output."""
    try:
        result = subprocess.run(
            ["lsmod"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return any(
                line.split()[0] == driver
                for line in result.stdout.splitlines()
                if line.strip()
            )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return False


def get_npu_status() -> dict:
    """
    Check availability of the AMD XDNA NPU.

    Returns:
        {
            "available":      bool,
            "device":         str | None,   # e.g. "/dev/accel/accel0"
            "driver_loaded":  bool,
        }
    """
    device_exists = os.path.exists(_NPU_DEVICE_PATH)
    driver        = _driver_loaded(_NPU_DRIVER_NAME)

    return {
        "available":     device_exists,
        "device":        _NPU_DEVICE_PATH if device_exists else None,
        "driver_loaded": driver,
    }


# ---------------------------------------------------------------------------
# Combined snapshot
# ---------------------------------------------------------------------------

def get_full_hardware_status() -> dict:
    """
    Return a single snapshot of all compute hardware state.

    Returns:
        {
            "nvidia":    {...},   # from get_nvidia_vram()
            "amd_igpu":  {...},   # from get_amd_vram()
            "npu":       {...},   # from get_npu_status()
            "timestamp": float,  # monotonic clock
        }
    """
    return {
        "nvidia":    get_nvidia_vram(),
        "amd_igpu":  get_amd_vram(),
        "npu":       get_npu_status(),
        "timestamp": time.monotonic(),
    }
