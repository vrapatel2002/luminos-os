"""
power_writer.py
Writes power settings to /sys filesystem.

Rules:
- Always check path exists before writing.
- PermissionError is caught and reported, never raised.
- nvidia-smi power limit is stubbed — needs root + persistence mode.
- Partial success is acceptable: count cpus_updated, report remainder.
"""

import glob
import logging
import os

logger = logging.getLogger("luminos-ai.power_manager.writer")

_CPU_FREQ_BASE = "/sys/devices/system/cpu"


def _cpu_freq_paths(filename: str) -> list[str]:
    """Return sorted glob matches for cpu*/cpufreq/<filename>."""
    pattern = os.path.join(_CPU_FREQ_BASE, "cpu[0-9]*", "cpufreq", filename)
    return sorted(glob.glob(pattern))


def _write_sysfs(path: str, value: str) -> bool:
    """Write value to a sysfs file. Returns True on success."""
    try:
        with open(path, "w") as f:
            f.write(value)
        return True
    except PermissionError:
        logger.warning(f"Permission denied writing {path} — run as root for full effect")
        return False
    except OSError as e:
        logger.debug(f"Could not write {path}: {e}")
        return False


# ---------------------------------------------------------------------------
# CPU governor
# ---------------------------------------------------------------------------

def set_cpu_governor(governor: str) -> dict:
    """
    Write governor string to all CPUs' scaling_governor sysfs entry.

    Returns:
        {"success": bool, "cpus_updated": int, "error": str|None}
    """
    paths = _cpu_freq_paths("scaling_governor")
    if not paths:
        logger.debug("No scaling_governor sysfs paths found (normal on dev machine)")
        return {"success": True, "cpus_updated": 0, "error": None}

    updated = sum(1 for p in paths if _write_sysfs(p, governor))
    logger.info(f"CPU governor → {governor} ({updated}/{len(paths)} CPUs updated)")

    # success=True even on partial/no writes — PermissionError is expected without
    # root on dev. The target daemon runs as root; cpus_updated tells the full story.
    return {
        "success":      True,
        "cpus_updated": updated,
        "error":        None if updated == len(paths)
                        else f"Only {updated}/{len(paths)} CPUs updated (run as root for full effect)",
    }


# ---------------------------------------------------------------------------
# Energy performance preference (EPP)
# ---------------------------------------------------------------------------

def set_energy_preference(preference: str) -> dict:
    """
    Write EPP hint to all CPUs that support it.
    Skips CPUs that lack the sysfs entry — EPP is optional.

    Returns:
        {"success": bool, "cpus_updated": int, "error": str|None}
    """
    paths = _cpu_freq_paths("energy_performance_preference")
    if not paths:
        logger.debug("No energy_performance_preference paths found — EPP not supported")
        return {"success": True, "cpus_updated": 0, "error": None}

    updated = sum(1 for p in paths if _write_sysfs(p, preference))
    logger.info(f"Energy preference → {preference} ({updated}/{len(paths)} CPUs updated)")

    return {
        "success":      True,          # partial success is fine — EPP is optional
        "cpus_updated": updated,
        "error":        None if updated == len(paths)
                        else f"Only {updated}/{len(paths)} CPUs support EPP",
    }


# ---------------------------------------------------------------------------
# NVIDIA power limit
# ---------------------------------------------------------------------------

def set_nvidia_power_limit(percent: int) -> dict:
    """
    Apply an NVIDIA power limit.

    percent == 0:
        Log "NVIDIA power-gated". Real gating requires root + persistence mode.
        Returns stub result — no nvidia-smi call.

    percent > 0:
        Log intended limit. Real application requires:
            nvidia-smi -pl <watts>  (needs root + persistence mode on target)
        Returns stub result.

    Returns:
        {"success": bool, "action": str, "percent": int|None, "note": str}
    """
    if percent == 0:
        logger.info("NVIDIA power-gated (0%) — idle profile")
        return {
            "success": True,
            "action":  "power_gated",
            "percent": 0,
            "note":    "stub — real gating needs root + nvidia-smi --persistence-mode",
        }
    else:
        logger.info(f"NVIDIA power limit → {percent}%")
        return {
            "success": True,
            "action":  "power_limit_set",
            "percent": percent,
            "note":    "stub — needs root",
        }


# ---------------------------------------------------------------------------
# Read current state (for status reporting)
# ---------------------------------------------------------------------------

def read_current_governor() -> str:
    """
    Read the active governor for cpu0.

    Returns:
        Governor string (e.g. "powersave", "performance") or "unknown".
    """
    path = os.path.join(_CPU_FREQ_BASE, "cpu0", "cpufreq", "scaling_governor")
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return "unknown"
