"""
src/hardware/battery_monitor.py
Battery level monitor with low-battery notifications and auto-suspend.

Polls /sys/class/power_supply/BAT0/capacity every 60 seconds.

Thresholds:
  20% — notification "Battery low"
  10% — notification "Battery critical"
   5% — notification "Suspending in 60 seconds", then suspend

Pure helpers:
    read_battery_level() → int | None
    read_battery_status() → str
"""

import logging
import subprocess
import threading
import time

logger = logging.getLogger("luminos-ai.hardware.battery")

_BAT_CAPACITY_PATH = "/sys/class/power_supply/BAT0/capacity"
_BAT_STATUS_PATH = "/sys/class/power_supply/BAT0/status"


# ===========================================================================
# Pure helpers — testable without hardware
# ===========================================================================

def read_battery_level() -> int | None:
    """
    Read battery percentage from sysfs.

    Returns 0-100 or None if unreadable.
    """
    try:
        with open(_BAT_CAPACITY_PATH) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def read_battery_status() -> str:
    """
    Read battery status string from sysfs.

    Returns "Charging", "Discharging", "Full", "Not charging", or "Unknown".
    """
    try:
        with open(_BAT_STATUS_PATH) as f:
            return f.read().strip()
    except OSError:
        return "Unknown"


# ===========================================================================
# Battery monitor
# ===========================================================================

class BatteryMonitor:
    """
    Background battery level monitor.

    Sends notifications at 20%, 10%, 5%. Suspends system at 5% after
    60-second countdown (cancellable by plugging in).
    """

    def __init__(self, notify_callback=None):
        """
        Args:
            notify_callback: callable(title: str, body: str, urgency: str)
                urgency: "low", "normal", "critical"
        """
        self._notify = notify_callback
        self._running = False
        self._thread: threading.Thread | None = None
        self._poll_interval = 60.0  # seconds
        self._notified_20 = False
        self._notified_10 = False
        self._notified_5 = False
        self._suspend_countdown_active = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the battery monitor thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="luminos-battery-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("Battery monitor started")

    def stop(self):
        """Stop the battery monitor thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Battery monitor stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _monitor_loop(self):
        while self._running:
            try:
                self._check_level()
            except Exception as e:
                logger.debug(f"Battery check error: {e}")
            time.sleep(self._poll_interval)

    def _check_level(self):
        level = read_battery_level()
        if level is None:
            return

        status = read_battery_status()

        # Reset notifications when charging
        if status in ("Charging", "Full"):
            self._notified_20 = False
            self._notified_10 = False
            self._notified_5 = False
            self._suspend_countdown_active = False
            return

        # Only warn when discharging
        if status != "Discharging":
            return

        if level <= 5 and not self._notified_5:
            self._notified_5 = True
            logger.warning(f"Battery critical: {level}% — suspending in 60s")
            self._send_notification(
                "Battery Critical",
                "Suspending in 60 seconds — plug in to cancel.",
                "critical",
            )
            self._start_suspend_countdown()

        elif level <= 10 and not self._notified_10:
            self._notified_10 = True
            logger.warning(f"Battery critical: {level}% — please plug in")
            self._send_notification(
                "Battery Critical",
                f"{level}% remaining — please plug in.",
                "critical",
            )

        elif level <= 20 and not self._notified_20:
            self._notified_20 = True
            logger.info(f"Battery low: {level}%")
            self._send_notification(
                "Battery Low",
                f"{level}% remaining.",
                "normal",
            )

    # ------------------------------------------------------------------
    # Suspend countdown
    # ------------------------------------------------------------------

    def _start_suspend_countdown(self):
        """Wait 60 seconds, then suspend if still on battery."""
        if self._suspend_countdown_active:
            return
        self._suspend_countdown_active = True

        def _countdown():
            for _ in range(60):
                if not self._running or not self._suspend_countdown_active:
                    return
                # Check if plugged in — cancel if so
                status = read_battery_status()
                if status in ("Charging", "Full"):
                    logger.info("Battery: charging detected — suspend cancelled")
                    self._suspend_countdown_active = False
                    return
                time.sleep(1.0)

            # Still on battery after 60s — suspend
            if self._suspend_countdown_active:
                logger.warning("Battery: 60s expired — suspending system")
                self._suspend_system()

        t = threading.Thread(
            target=_countdown,
            name="luminos-battery-suspend",
            daemon=True,
        )
        t.start()

    @staticmethod
    def _suspend_system():
        """Suspend the system via systemctl."""
        try:
            subprocess.run(
                ["systemctl", "suspend"],
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            logger.critical(f"Failed to suspend: {e}")

    # ------------------------------------------------------------------
    # Notification helper
    # ------------------------------------------------------------------

    def _send_notification(self, title: str, body: str, urgency: str):
        """Send notification via callback or notify-send fallback."""
        if self._notify:
            try:
                self._notify(title, body, urgency)
                return
            except Exception as e:
                logger.debug(f"Notification callback error: {e}")

        # Fallback to notify-send
        urgency_map = {"low": "low", "normal": "normal", "critical": "critical"}
        try:
            subprocess.run(
                ["notify-send", "-u", urgency_map.get(urgency, "normal"),
                 title, body],
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current battery monitor state."""
        return {
            "level": read_battery_level(),
            "status": read_battery_status(),
            "monitoring": self._running,
            "suspend_countdown": self._suspend_countdown_active,
        }
