"""
src/gui/lockscreen/lock_manager.py
Lock/unlock lifecycle manager — no GTK in __init__.

The LockWindow is only created when lock() is first called.
All state (self.locked, self.lock_time, idle timer) is plain Python
so it can be constructed and tested without a display.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

_GTK_AVAILABLE = False
try:
    import gi
    gi.require_version("Gtk", "4.0")
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    pass


class LockManager:
    """
    Controls screen lock lifecycle.

    Responsibilities:
      - lock():  blur/pause wallpaper, show lock screen.
      - unlock(): hide lock screen.
      - Idle timer: lock after N seconds of inactivity.
      - USB logging: log USB hotplug events while locked (daemon-side).
    """

    DEFAULT_IDLE_TIMEOUT = 300   # 5 minutes

    def __init__(self, idle_timeout: int = DEFAULT_IDLE_TIMEOUT):
        self.locked:       bool              = False
        self.lock_window:  object | None     = None   # LuminosLockScreen
        self.idle_timeout: int               = idle_timeout
        self.lock_time:    float | None      = None
        self._last_activity: float           = time.monotonic()
        self._idle_thread: threading.Thread | None = None
        self._pam = None   # lazily shared with lock_window

    # -----------------------------------------------------------------------
    # Lock / unlock
    # -----------------------------------------------------------------------

    def lock(self) -> bool:
        """
        Lock the screen.
        - Blurs/pauses wallpaper.
        - Creates the lock window if needed and presents it.

        Returns False if already locked.
        """
        if self.locked:
            return False

        # Blur/pause video wallpaper
        try:
            from gui.wallpaper import on_lock
            on_lock()
        except Exception as e:
            logger.debug(f"LockManager.lock: wallpaper on_lock error — {e}")

        # Create window on first lock
        if self.lock_window is None and _GTK_AVAILABLE:
            try:
                from gui.lockscreen.lock_window import LuminosLockScreen
                self.lock_window = LuminosLockScreen()
            except Exception as e:
                logger.warning(f"LockManager.lock: could not create lock window — {e}")

        if self.lock_window is not None:
            try:
                self.lock_window.pam.reset()
                self.lock_window._set_state("clock")
                self.lock_window.present()
                self.lock_window.fullscreen()
            except Exception as e:
                logger.warning(f"LockManager.lock: window present error — {e}")

        self.locked    = True
        self.lock_time = time.time()
        logger.info("LockManager: screen locked")
        return True

    def unlock(self) -> bool:
        """
        Unlock the screen.
        Called programmatically (e.g. from daemon test) or by the window itself.

        Returns False if not locked.
        """
        if not self.locked:
            return False

        if self.lock_window is not None:
            try:
                self.lock_window.hide()
            except Exception:
                pass

        try:
            from gui.wallpaper import on_unlock
            on_unlock()
        except Exception as e:
            logger.debug(f"LockManager.unlock: wallpaper on_unlock error — {e}")

        self.locked    = False
        self.lock_time = None
        logger.info("LockManager: screen unlocked")
        return True

    # -----------------------------------------------------------------------
    # Idle timer
    # -----------------------------------------------------------------------

    def start_idle_timer(self) -> None:
        """
        Start a daemon thread that locks the screen after `idle_timeout` seconds
        of no registered user activity.
        """
        if self._idle_thread is not None and self._idle_thread.is_alive():
            return
        self._idle_thread = threading.Thread(
            target=self._idle_loop,
            name="lockscreen-idle",
            daemon=True,
        )
        self._idle_thread.start()

    def on_user_activity(self) -> None:
        """
        Reset the idle timer.
        Bar/dock/daemon call this on any user interaction.
        """
        self._last_activity = time.monotonic()

    # -----------------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current lock state as a JSON-serialisable dict."""
        attempts = 0
        if self.lock_window is not None:
            try:
                attempts = self.lock_window.pam.attempts
            except Exception:
                pass
        return {
            "locked":       self.locked,
            "lock_time":    self.lock_time,
            "idle_timeout": self.idle_timeout,
            "attempts":     attempts,
        }

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _idle_loop(self) -> None:
        """Background thread — checks inactivity every 30 s."""
        while True:
            time.sleep(30)
            if self.locked:
                continue
            idle_for = time.monotonic() - self._last_activity
            if idle_for >= self.idle_timeout:
                logger.info(
                    f"LockManager: idle for {idle_for:.0f}s — locking screen"
                )
                self.lock()
