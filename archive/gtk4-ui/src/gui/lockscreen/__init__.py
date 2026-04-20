"""
src/gui/lockscreen/__init__.py
Module-level singleton API for the Luminos lock screen.

Public API
----------
lock()          → bool   (False if already locked)
unlock()        → bool   (False if not locked)
is_locked()     → bool
get_status()    → dict
on_activity()   — reset idle timer
"""

from gui.lockscreen.lock_manager import LockManager

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: LockManager = LockManager()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lock() -> bool:
    """Lock the screen. Returns False if already locked."""
    return _manager.lock()


def unlock() -> bool:
    """Unlock the screen. Returns False if not locked."""
    return _manager.unlock()


def is_locked() -> bool:
    """Return True if the screen is currently locked."""
    return _manager.locked


def get_status() -> dict:
    """Return current lock status dict."""
    return _manager.get_status()


def on_activity() -> None:
    """Notify the lock manager of user activity (resets idle timer)."""
    _manager.on_user_activity()
