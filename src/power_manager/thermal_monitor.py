"""
thermal_monitor.py
CPU and GPU temperature monitoring via /sys and nvidia-smi.

Rules:
- Raw /sys thermal values are in milli-°C; divide by 1000.
- Returns highest CPU zone temp — single worst-case number.
- GPU: nvidia-smi first (most accurate), hwmon fallback.
- get_thermal_level() uses max of CPU and GPU.
- Never raises — None returned on any read failure.
"""

import glob
import logging
import subprocess

logger = logging.getLogger("luminos-ai.power_manager.thermal")

THRESHOLDS: dict[str, int] = {
    "warn":      75,   # °C — start watching
    "throttle":  85,   # °C — reduce load
    "emergency": 95,   # °C — quiet everything immediately
}


def get_cpu_temp() -> float | None:
    """
    Read highest CPU temperature across all thermal zones.

    Returns:
        Temperature in °C (float), or None if unreadable.
    """
    paths = sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp"))
    highest: float | None = None
    for path in paths:
        try:
            with open(path) as f:
                raw = f.read().strip()
            temp_c = int(raw) / 1000.0
            if temp_c > 0:  # skip bogus zero readings
                if highest is None or temp_c > highest:
                    highest = temp_c
        except (OSError, ValueError):
            continue
    if highest is not None:
        logger.debug(f"CPU temp: {highest:.1f}°C")
    return highest


def get_gpu_temp() -> float | None:
    """
    Read GPU temperature.

    Tries nvidia-smi first; falls back to hwmon sysfs.

    Returns:
        Temperature in °C (float), or None if unreadable.
    """
    # nvidia-smi probe
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            val = result.stdout.strip().splitlines()[0].strip()
            temp = float(val)
            logger.debug(f"GPU temp (nvidia-smi): {temp:.1f}°C")
            return temp
    except (FileNotFoundError, subprocess.TimeoutExpired,
            ValueError, IndexError):
        pass

    # hwmon fallback (AMD iGPU, etc.)
    for path in sorted(glob.glob("/sys/class/hwmon/hwmon*/temp1_input")):
        try:
            with open(path) as f:
                raw = f.read().strip()
            temp_c = int(raw) / 1000.0
            if temp_c > 0:
                logger.debug(f"GPU temp (hwmon {path}): {temp_c:.1f}°C")
                return temp_c
        except (OSError, ValueError):
            continue

    return None


def get_thermal_level() -> str:
    """
    Determine thermal threat level from CPU and GPU temperatures.

    Returns the highest-threat level across both sensors:
        "normal" | "warn" | "throttle" | "emergency"
    """
    cpu = get_cpu_temp()
    gpu = get_gpu_temp()

    # Take the highest temp from whichever sensors are available
    candidates = [t for t in (cpu, gpu) if t is not None]
    if not candidates:
        logger.debug("thermal_level: no sensors — assuming normal")
        return "normal"

    worst = max(candidates)

    if worst >= THRESHOLDS["emergency"]:
        logger.warning(f"THERMAL EMERGENCY: {worst:.1f}°C")
        return "emergency"
    if worst >= THRESHOLDS["throttle"]:
        logger.warning(f"Thermal throttle: {worst:.1f}°C")
        return "throttle"
    if worst >= THRESHOLDS["warn"]:
        logger.info(f"Thermal warn: {worst:.1f}°C")
        return "warn"

    logger.debug(f"Thermal normal: {worst:.1f}°C")
    return "normal"
