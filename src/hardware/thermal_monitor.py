"""
src/hardware/thermal_monitor.py
Active thermal management daemon.

Runs as a background thread. Polls temps every 5 seconds.
Takes action when thresholds hit: adjusts fan curve, throttles, notifies.

Thresholds:
  warn (75C)     — aggressive fan curve
  critical (85C) — max fans + throttle + user notification
  emergency (95C) — max fans + full throttle + urgent notification

Cooldown: threshold - 10C restores normal operation.
"""

import logging
import threading
import time

logger = logging.getLogger("luminos-ai.hardware.thermal")

THRESHOLDS = {
    "warn": 75,
    "critical": 85,
    "emergency": 95,
}

COOLDOWN_OFFSET = 10  # drop 10C below threshold to restore

_AGGRESSIVE_FAN_CURVE = {
    "cpu": [(0, 30), (60, 50), (70, 70), (80, 90), (85, 100)],
    "gpu": [(0, 30), (60, 50), (70, 70), (80, 90), (85, 100)],
}

_MAX_FAN_CURVE = {
    "cpu": [(0, 100), (100, 100)],
    "gpu": [(0, 100), (100, 100)],
}


class ThermalMonitor:
    """
    Background thermal management daemon.

    Integrates with:
      - AsusController for fan curves
      - PowerEventBus for notifications
    """

    def __init__(self, asus_controller=None, notify_callback=None):
        """
        Args:
            asus_controller: AsusController instance for fan curve control.
            notify_callback: callable(title, message, urgency) for user notifications.
        """
        self._asus = asus_controller
        self._notify = notify_callback
        self._running = False
        self._thread = None
        self._poll_interval = 5.0  # seconds
        self._current_level = "normal"
        self._on_battery = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the thermal monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="luminos-thermal-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("Thermal monitor started (poll every %.0fs)", self._poll_interval)

    def stop(self):
        """Stop the thermal monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Thermal monitor stopped")

    def set_power_mode(self, on_battery: bool):
        """Called by power event bus when AC state changes."""
        with self._lock:
            self._on_battery = on_battery
        if on_battery:
            logger.info("Thermal: switched to battery — quiet fan curve")
            self._apply_quiet_curve()
        else:
            logger.info("Thermal: switched to AC — performance fan curve")
            self._restore_normal_curve()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _monitor_loop(self):
        while self._running:
            try:
                self._check_temps()
            except Exception as e:
                logger.debug(f"Thermal check error: {e}")
            time.sleep(self._poll_interval)

    def _check_temps(self):
        if not self._asus:
            return

        temps = self._asus.get_temps()
        cpu = temps.get("cpu")
        gpu = temps.get("gpu")
        battery = temps.get("battery")

        # Take worst temp across all sensors
        candidates = [t for t in (cpu, gpu, battery) if t is not None]
        if not candidates:
            return

        worst = max(candidates)
        new_level = self._classify_level(worst)

        if new_level != self._current_level:
            self._handle_transition(self._current_level, new_level, worst, temps)
            self._current_level = new_level

    def _classify_level(self, temp: float) -> str:
        if temp >= THRESHOLDS["emergency"]:
            return "emergency"
        if temp >= THRESHOLDS["critical"]:
            return "critical"
        if temp >= THRESHOLDS["warn"]:
            return "warn"
        return "normal"

    # ------------------------------------------------------------------
    # Threshold transitions
    # ------------------------------------------------------------------

    def _handle_transition(self, old_level: str, new_level: str,
                           worst_temp: float, temps: dict):
        """Handle transition between thermal levels."""

        # Escalating
        if new_level == "warn" and old_level == "normal":
            self._on_warn(worst_temp, temps)
        elif new_level == "critical":
            self._on_critical(worst_temp, temps)
        elif new_level == "emergency":
            self._on_emergency(worst_temp, temps)

        # Cooling down
        elif new_level == "normal" and old_level in ("warn", "critical", "emergency"):
            self._on_cooldown(worst_temp, temps)
        elif new_level == "warn" and old_level in ("critical", "emergency"):
            # Dropped from critical/emergency to warn — still aggressive but not max
            self._on_warn(worst_temp, temps)

    def _on_warn(self, worst_temp: float, temps: dict):
        """75C+ — aggressive fan curve."""
        logger.info(f"Thermal WARN: {worst_temp:.1f}C — switching to aggressive fans")
        if self._asus:
            self._asus.set_fan_curve(_AGGRESSIVE_FAN_CURVE)

    def _on_critical(self, worst_temp: float, temps: dict):
        """85C+ — max fans + throttle + notification."""
        logger.warning(f"Thermal CRITICAL: {worst_temp:.1f}C — max fans, throttling")
        if self._asus:
            self._asus.set_fan_curve(_MAX_FAN_CURVE)

        # Throttle via GPU manager
        try:
            from power_manager.power_writer import set_cpu_governor, set_nvidia_power_limit
            set_cpu_governor("powersave")
            set_nvidia_power_limit(50)
        except ImportError:
            logger.debug("power_writer not available for throttle")

        if self._notify:
            self._notify(
                "System Running Hot",
                f"Temperature: {worst_temp:.0f}°C — performance reduced to protect hardware.",
                "normal",
            )

    def _on_emergency(self, worst_temp: float, temps: dict):
        """95C+ — max fans + full throttle + urgent notification."""
        logger.critical(
            f"Thermal EMERGENCY: {worst_temp:.1f}C — "
            f"CPU={temps.get('cpu')}, GPU={temps.get('gpu')}, "
            f"Battery={temps.get('battery')}"
        )
        if self._asus:
            self._asus.set_fan_curve(_MAX_FAN_CURVE)

        try:
            from power_manager.power_writer import set_cpu_governor, set_nvidia_power_limit
            set_cpu_governor("powersave")
            set_nvidia_power_limit(0)
        except ImportError:
            pass

        if self._notify:
            self._notify(
                "Temperature Emergency",
                f"Temperature: {worst_temp:.0f}°C — system heavily throttled. "
                "Consider closing intensive applications.",
                "urgent",
            )

    def _on_cooldown(self, worst_temp: float, temps: dict):
        """Dropped below threshold - 10C — restore normal operation."""
        logger.info(f"Thermal COOLDOWN: {worst_temp:.1f}C — restoring normal operation")
        self._restore_normal_curve()

        try:
            from power_manager.power_writer import set_cpu_governor, set_nvidia_power_limit
            with self._lock:
                if self._on_battery:
                    set_cpu_governor("powersave")
                    set_nvidia_power_limit(0)
                else:
                    set_cpu_governor("schedutil")
                    set_nvidia_power_limit(100)
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Fan curve helpers
    # ------------------------------------------------------------------

    def _apply_quiet_curve(self):
        """Battery mode — quiet fan curve."""
        if self._asus:
            quiet_curve = {
                "cpu": [(0, 0), (60, 10), (75, 30), (85, 60), (95, 100)],
                "gpu": [(0, 0), (60, 10), (75, 30), (85, 60), (95, 100)],
            }
            self._asus.set_fan_curve(quiet_curve)

    def _restore_normal_curve(self):
        """AC mode — default Luminos fan curve."""
        if self._asus:
            from .asus_controller import DEFAULT_FAN_CURVE
            self._asus.set_fan_curve(DEFAULT_FAN_CURVE)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current thermal status."""
        temps = self._asus.get_temps() if self._asus else {}
        return {
            "level": self._current_level,
            "temps": temps,
            "on_battery": self._on_battery,
            "monitoring": self._running,
        }
