"""
src/hardware/asus_controller.py
ASUS ROG G14 hardware control via asusctl.

Provides: battery charge limit, fan curves, keyboard backlight + RGB,
temperature reading, AC plug state.

All commands go through asusctl / sysfs. Graceful on missing hardware.
"""

import glob
import json
import logging
import os
import subprocess

logger = logging.getLogger("luminos-ai.hardware.asus")

_HARDWARE_CONFIG_PATH = os.path.expanduser("~/.config/luminos/hardware.json")

_VALID_CHARGE_LIMITS = (60, 80, 100)

DEFAULT_FAN_CURVE = {
    "cpu": [(0, 0), (60, 20), (75, 60), (85, 90), (95, 100)],
    "gpu": [(0, 0), (60, 20), (75, 60), (85, 90), (95, 100)],
}

BATTERY_FAN_CURVE = {
    "cpu": [(0, 0), (70, 20), (80, 50), (85, 80), (95, 100)],
    "gpu": [(0, 0), (70, 20), (80, 50), (85, 80), (95, 100)],
}

_VALID_EFFECTS = ("static", "breathe", "reactive")


class AsusController:
    """Interface to ASUS ROG hardware via asusctl and sysfs."""

    def __init__(self):
        self._asusctl_available = None

    # ------------------------------------------------------------------
    # asusctl availability
    # ------------------------------------------------------------------

    def _check_asusctl(self) -> bool:
        if self._asusctl_available is not None:
            return self._asusctl_available
        try:
            result = subprocess.run(
                ["asusctl", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            self._asusctl_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._asusctl_available = False

        if not self._asusctl_available:
            logger.warning("asusctl not available — hardware control disabled")
        return self._asusctl_available

    def _run_asusctl(self, args: list[str], timeout: int = 5) -> str | None:
        """Run an asusctl command. Returns stdout or None on failure."""
        if not self._check_asusctl():
            return None
        try:
            result = subprocess.run(
                ["asusctl"] + args,
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            logger.debug(f"asusctl {args} failed: {result.stderr.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            logger.debug(f"asusctl {args} error: {e}")
        return None

    # ------------------------------------------------------------------
    # Battery charge limit
    # ------------------------------------------------------------------

    def get_battery_limit(self) -> int:
        """
        Returns current charge limit: 60, 80, or 100.
        Falls back to 100 if unreadable.
        """
        output = self._run_asusctl(["-c"])
        if output:
            for word in output.split():
                try:
                    val = int(word)
                    if val in _VALID_CHARGE_LIMITS:
                        return val
                except ValueError:
                    continue
        # Try sysfs fallback
        try:
            with open("/sys/class/power_supply/BAT0/charge_control_end_threshold") as f:
                val = int(f.read().strip())
                if val in _VALID_CHARGE_LIMITS:
                    return val
        except (OSError, ValueError):
            pass
        return 100

    def set_battery_limit(self, limit: int) -> bool:
        """
        Sets charge limit. Must be 60, 80, or 100.
        Returns True on success.
        """
        if limit not in _VALID_CHARGE_LIMITS:
            logger.warning(f"Invalid charge limit {limit} — must be 60, 80, or 100")
            return False

        output = self._run_asusctl(["-c", str(limit)])
        if output is not None:
            logger.info(f"Battery charge limit set to {limit}%")
            return True
        return False

    # ------------------------------------------------------------------
    # Fan control
    # ------------------------------------------------------------------

    def get_fan_mode(self) -> str:
        """Returns: 'silent' | 'balanced' | 'turbo' or 'unknown'."""
        output = self._run_asusctl(["profile", "--profile-get"])
        if output:
            lower = output.lower()
            if "silent" in lower or "quiet" in lower:
                return "silent"
            if "balanced" in lower:
                return "balanced"
            if "turbo" in lower or "performance" in lower:
                return "turbo"
        return "unknown"

    def set_fan_curve(self, curve: dict | None = None) -> bool:
        """
        Set custom fan curve via asusctl.

        Args:
            curve: Dict with "cpu" and "gpu" keys, each a list of
                   (temp_c, fan_pct) tuples. Uses DEFAULT_FAN_CURVE if None.

        Returns:
            True on success.
        """
        if curve is None:
            curve = DEFAULT_FAN_CURVE

        cpu_points = curve.get("cpu", DEFAULT_FAN_CURVE["cpu"])
        gpu_points = curve.get("gpu", DEFAULT_FAN_CURVE["gpu"])

        # Format for asusctl fan-curve: temp:fan pairs
        cpu_str = ",".join(f"{t}:{f}" for t, f in cpu_points)
        gpu_str = ",".join(f"{t}:{f}" for t, f in gpu_points)

        success = True
        result = self._run_asusctl(
            ["fan-curve", "--cpu", cpu_str], timeout=10
        )
        if result is None:
            success = False

        result = self._run_asusctl(
            ["fan-curve", "--gpu", gpu_str], timeout=10
        )
        if result is None:
            success = False

        if success:
            logger.info("Fan curve applied successfully")
        return success

    # ------------------------------------------------------------------
    # Keyboard backlight
    # ------------------------------------------------------------------

    def get_keyboard_brightness(self) -> int:
        """Returns 0-3 (0=off, 3=max)."""
        output = self._run_asusctl(["-k"])
        if output:
            for word in output.split():
                try:
                    val = int(word)
                    if 0 <= val <= 3:
                        return val
                except ValueError:
                    continue
        # sysfs fallback
        for path in glob.glob(
            "/sys/class/leds/asus::kbd_backlight/brightness"
        ):
            try:
                with open(path) as f:
                    return int(f.read().strip())
            except (OSError, ValueError):
                pass
        return 0

    def set_keyboard_brightness(self, level: int) -> bool:
        """Set keyboard brightness. level: 0-3 (0=off, 3=max)."""
        level = max(0, min(3, level))
        output = self._run_asusctl(["-k", str(level)])
        if output is not None:
            logger.info(f"Keyboard brightness set to {level}")
            return True
        return False

    def set_keyboard_effect(self, effect: str, color: str = "#0080FF") -> bool:
        """
        Set keyboard LED effect.

        Args:
            effect: "static" | "breathe" | "reactive"
            color: hex color string e.g. "#0080FF"

        Returns:
            True on success.
        """
        if effect not in _VALID_EFFECTS:
            logger.warning(f"Invalid keyboard effect: {effect}")
            return False

        # Strip # from color
        hex_color = color.lstrip("#")

        output = self._run_asusctl(
            ["aura", effect, "--hex", hex_color]
        )
        if output is not None:
            logger.info(f"Keyboard effect: {effect} color: {color}")
            return True
        return False

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    def get_temps(self) -> dict:
        """
        Returns current temperatures in degrees C.

        Keys: cpu, gpu, battery (each float or None).
        """
        result = {
            "cpu": self._read_cpu_temp(),
            "gpu": self._read_gpu_temp(),
            "battery": self._read_battery_temp(),
        }
        return result

    def _read_cpu_temp(self) -> float | None:
        paths = sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp"))
        highest = None
        for path in paths:
            try:
                with open(path) as f:
                    temp_c = int(f.read().strip()) / 1000.0
                if temp_c > 0 and (highest is None or temp_c > highest):
                    highest = temp_c
            except (OSError, ValueError):
                continue
        return highest

    def _read_gpu_temp(self) -> float | None:
        # nvidia-smi first
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return float(result.stdout.strip().splitlines()[0])
        except (FileNotFoundError, subprocess.TimeoutExpired,
                ValueError, IndexError):
            pass

        # hwmon fallback (AMD iGPU)
        for path in sorted(glob.glob("/sys/class/hwmon/hwmon*/temp1_input")):
            try:
                with open(path) as f:
                    temp_c = int(f.read().strip()) / 1000.0
                if temp_c > 0:
                    return temp_c
            except (OSError, ValueError):
                continue
        return None

    def _read_battery_temp(self) -> float | None:
        for path in glob.glob("/sys/class/power_supply/BAT*/temp"):
            try:
                with open(path) as f:
                    # Battery temp is in tenths of degrees C
                    return int(f.read().strip()) / 10.0
            except (OSError, ValueError):
                continue
        return None

    # ------------------------------------------------------------------
    # AC power state
    # ------------------------------------------------------------------

    def is_plugged_in(self) -> bool:
        """Returns True if on AC power."""
        for pattern in [
            "/sys/class/power_supply/AC*/online",
            "/sys/class/power_supply/ADP*/online",
        ]:
            for path in glob.glob(pattern):
                try:
                    with open(path) as f:
                        return f.read().strip() == "1"
                except OSError:
                    continue
        return True  # assume plugged if unknown

    # ------------------------------------------------------------------
    # Boot-time defaults
    # ------------------------------------------------------------------

    def apply_boot_defaults(self) -> dict:
        """
        Apply saved hardware config on boot.

        Reads ~/.config/luminos/hardware.json for battery_limit.
        Applies default fan curve. Returns summary of actions taken.
        """
        config = load_hardware_config()
        result = {"battery_limit": False, "fan_curve": False}

        # Battery charge limit
        limit = config.get("battery_limit", 80)
        if limit not in _VALID_CHARGE_LIMITS:
            limit = 80
        if self.set_battery_limit(limit):
            result["battery_limit"] = True
            logger.info(f"Boot: battery limit → {limit}%")

        # Default fan curve (AC curve — thermal_monitor will switch if on battery)
        if self.set_fan_curve(DEFAULT_FAN_CURVE):
            result["fan_curve"] = True
            logger.info("Boot: default fan curve applied")

        return result


def load_hardware_config() -> dict:
    """
    Load hardware config from ~/.config/luminos/hardware.json.

    Returns dict with at least "battery_limit" key. Defaults to 80 if
    file missing or unreadable.
    """
    try:
        with open(_HARDWARE_CONFIG_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"battery_limit": 80}


def save_hardware_config(config: dict) -> bool:
    """Save hardware config to ~/.config/luminos/hardware.json."""
    try:
        os.makedirs(os.path.dirname(_HARDWARE_CONFIG_PATH), exist_ok=True)
        with open(_HARDWARE_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except OSError as e:
        logger.warning(f"Could not save hardware config: {e}")
        return False
