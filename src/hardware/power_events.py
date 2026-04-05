"""
src/hardware/power_events.py
Central event bus for power state changes.

Monitors AC plug state and fullscreen app detection.
Broadcasts events to all subscribers when state changes.

On unplug: CPU → powersave, wallpaper pause, quiet fans. Immediate.
On plug in: CPU → performance, wallpaper resume, performance fans. Immediate.

Subscribers:
  - wallpaper_manager (pause/resume video + live wallpaper)
  - thermal_monitor (switch fan curve)
  - live_wallpaper C binary (via socket)
  - Any future component that needs power awareness

Events:
  battery    — switched to battery power
  ac         — switched to AC power
  game_start — fullscreen app detected
  game_end   — fullscreen app exited
  suspend    — system entering suspend
  wake       — system woke from suspend
"""

import json
import logging
import subprocess
import threading
import time

logger = logging.getLogger("luminos-ai.hardware.power_events")

EVENTS = ("battery", "ac", "game_start", "game_end", "suspend", "wake")


class PowerEventBus:
    """
    Power state event bus.

    Monitors AC state (2s poll) and fullscreen detection (1s poll).
    Dispatches events to registered callbacks.

    Owns the auto power mode switch:
      - On unplug: CPU powersave, wallpaper pause, quiet fans
      - On plug in: CPU performance, wallpaper resume, performance fans
    """

    def __init__(self, thermal_monitor=None, wallpaper_manager=None):
        """
        Args:
            thermal_monitor: ThermalMonitor instance (optional).
            wallpaper_manager: WallpaperManager instance (optional).
        """
        self._subscribers: dict[str, list[callable]] = {e: [] for e in EVENTS}
        self._running = False
        self._threads: list[threading.Thread] = []
        self._last_plugged = None
        self._last_fullscreen = False
        self._lock = threading.Lock()
        self._thermal = thermal_monitor
        self._wallpaper = wallpaper_manager

    # ------------------------------------------------------------------
    # Subscribe / emit
    # ------------------------------------------------------------------

    def subscribe(self, event: str, callback: callable):
        """
        Register a callback for a power event.

        Args:
            event: One of EVENTS.
            callback: callable(data: dict) — called when event fires.
        """
        if event not in EVENTS:
            logger.warning(f"Unknown power event: {event}")
            return
        with self._lock:
            self._subscribers[event].append(callback)
        logger.debug(f"Power event subscriber: {event} → {callback}")

    def emit(self, event: str, data: dict | None = None):
        """
        Fire a power event to all subscribers.

        Args:
            event: One of EVENTS.
            data: Optional dict payload.
        """
        if event not in EVENTS:
            return
        if data is None:
            data = {}
        data["event"] = event
        data["timestamp"] = time.time()

        logger.info(f"Power event: {event}")

        with self._lock:
            callbacks = list(self._subscribers.get(event, []))

        for cb in callbacks:
            try:
                cb(data)
            except Exception as e:
                logger.debug(f"Power event callback error ({event}): {e}")

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self):
        """Start monitoring threads."""
        if self._running:
            return
        self._running = True

        ac_thread = threading.Thread(
            target=self._monitor_ac_state,
            name="luminos-power-ac",
            daemon=True,
        )
        fs_thread = threading.Thread(
            target=self._monitor_fullscreen,
            name="luminos-power-fullscreen",
            daemon=True,
        )

        self._threads = [ac_thread, fs_thread]
        ac_thread.start()
        fs_thread.start()
        logger.info("Power event bus started")

    def stop(self):
        """Stop monitoring threads."""
        self._running = False
        for t in self._threads:
            t.join(timeout=5)
        self._threads = []
        logger.info("Power event bus stopped")

    # ------------------------------------------------------------------
    # Setters for late binding
    # ------------------------------------------------------------------

    def set_thermal_monitor(self, thermal_monitor):
        """Set or replace the thermal monitor reference."""
        self._thermal = thermal_monitor

    def set_wallpaper_manager(self, wallpaper_manager):
        """Set or replace the wallpaper manager reference."""
        self._wallpaper = wallpaper_manager

    # ------------------------------------------------------------------
    # AC state monitor
    # ------------------------------------------------------------------

    def _monitor_ac_state(self):
        """Poll /sys/class/power_supply every 2 seconds."""
        while self._running:
            try:
                plugged = self._read_ac_state()
                if self._last_plugged is not None and plugged != self._last_plugged:
                    if plugged:
                        self._switch_to_performance()
                        self.emit("ac", {"plugged_in": True})
                    else:
                        self._switch_to_battery()
                        self.emit("battery", {"plugged_in": False})
                self._last_plugged = plugged
            except Exception as e:
                logger.debug(f"AC monitor error: {e}")
            time.sleep(2.0)

    # ------------------------------------------------------------------
    # Power mode switching — immediate, no delay
    # ------------------------------------------------------------------

    def _switch_to_battery(self):
        """Unplug detected — battery mode. Must complete < 500ms."""
        logger.info("Switched to battery mode")

        # CPU governor → powersave
        try:
            from power_manager.power_writer import set_cpu_governor
            set_cpu_governor("powersave")
        except Exception as e:
            logger.debug(f"Could not set powersave governor: {e}")

        # Wallpaper pause (video + live)
        if self._wallpaper:
            try:
                wtype = self._wallpaper.config.get("type", "color")
                if wtype == "video" and self._wallpaper.video.is_running():
                    self._wallpaper.video.pause()
                    logger.debug("Paused video wallpaper on battery")
                elif wtype == "live":
                    from gui.wallpaper.wallpaper_manager import _send_live_command
                    _send_live_command({"cmd": "pause"})
                    logger.debug("Paused live wallpaper on battery")
            except Exception as e:
                logger.debug(f"Wallpaper pause error: {e}")

        # Thermal → quiet fan curve
        if self._thermal:
            try:
                self._thermal.set_power_mode(on_battery=True)
            except Exception as e:
                logger.debug(f"Thermal battery switch error: {e}")

    def _switch_to_performance(self):
        """Plug in detected — performance mode. Must complete < 500ms."""
        logger.info("Switched to performance mode")

        # CPU governor → performance
        try:
            from power_manager.power_writer import set_cpu_governor
            set_cpu_governor("performance")
        except Exception as e:
            logger.debug(f"Could not set performance governor: {e}")

        # Wallpaper resume
        if self._wallpaper:
            try:
                wtype = self._wallpaper.config.get("type", "color")
                if wtype == "video" and self._wallpaper.video.paused:
                    self._wallpaper.video.resume()
                    logger.debug("Resumed video wallpaper on AC")
                elif wtype == "live":
                    from gui.wallpaper.wallpaper_manager import _send_live_command
                    _send_live_command({"cmd": "resume"})
                    logger.debug("Resumed live wallpaper on AC")
            except Exception as e:
                logger.debug(f"Wallpaper resume error: {e}")

        # Thermal → performance fan curve
        if self._thermal:
            try:
                self._thermal.set_power_mode(on_battery=False)
            except Exception as e:
                logger.debug(f"Thermal AC switch error: {e}")

    @staticmethod
    def _read_ac_state() -> bool:
        """Read AC adapter state from sysfs."""
        import glob
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
    # Fullscreen app monitor
    # ------------------------------------------------------------------

    def _monitor_fullscreen(self):
        """Use hyprctl to detect fullscreen apps every 1 second."""
        while self._running:
            try:
                is_fs = self._check_fullscreen()
                if is_fs and not self._last_fullscreen:
                    self.emit("game_start", {"fullscreen": True})
                elif not is_fs and self._last_fullscreen:
                    self.emit("game_end", {"fullscreen": False})
                self._last_fullscreen = is_fs
            except Exception as e:
                logger.debug(f"Fullscreen monitor error: {e}")
            time.sleep(1.0)

    @staticmethod
    def _check_fullscreen() -> bool:
        """Check if active window is fullscreen via hyprctl."""
        try:
            result = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return data.get("fullscreen", 0) > 0
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError, OSError):
            pass
        return False

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current power event bus state."""
        return {
            "running": self._running,
            "plugged_in": self._last_plugged,
            "fullscreen": self._last_fullscreen,
            "subscribers": {
                event: len(cbs) for event, cbs in self._subscribers.items()
            },
        }
