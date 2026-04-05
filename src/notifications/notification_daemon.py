"""
src/notifications/notification_daemon.py
Freedesktop.org notification server implementation via D-Bus.

Implements org.freedesktop.Notifications interface:
  - Notify(app_name, replaces_id, icon, summary, body, actions, hints, timeout)
  - CloseNotification(id)
  - GetCapabilities() → ["body", "actions", "persistence"]
  - GetServerInformation() → ("Luminos", "Luminos OS", "0.1.0", "1.2")

Stores notifications in memory (max 50 history).
Bridges to the Luminos GUI notification system when available.

Pure helpers:
    map_urgency(hints) → str
    build_notification(app_name, summary, body, hints, timeout) → dict
"""

import logging
import threading
import time

logger = logging.getLogger("luminos-ai.notifications.daemon")

_HISTORY_MAX = 50
_NEXT_ID = 1
_HISTORY: list[dict] = []
_LOCK = threading.Lock()


# ===========================================================================
# Pure helpers — testable without D-Bus
# ===========================================================================

def map_urgency(hints: dict) -> str:
    """
    Map freedesktop urgency hint to Luminos urgency string.

    Args:
        hints: D-Bus hints dict. Key "urgency" → 0=low, 1=normal, 2=critical.

    Returns:
        "low", "normal", or "critical"
    """
    urgency = hints.get("urgency", 1)
    if isinstance(urgency, int):
        if urgency == 0:
            return "low"
        if urgency >= 2:
            return "critical"
    return "normal"


def build_notification(app_name: str, summary: str, body: str,
                       hints: dict, timeout: int) -> dict:
    """
    Build a notification dict from freedesktop Notify parameters.

    Args:
        app_name: Sending application name.
        summary: Notification title.
        body: Notification body text.
        hints: D-Bus hints dict.
        timeout: Auto-dismiss timeout in ms. -1 = server default, 0 = never.

    Returns:
        Normalized notification dict.
    """
    urgency = map_urgency(hints)

    # Timeout: -1 means server decides based on urgency
    if timeout < 0:
        if urgency == "low":
            timeout = 3000
        elif urgency == "critical":
            timeout = 0  # never auto-dismiss
        else:
            timeout = 5000

    return {
        "app_name": app_name or "Unknown",
        "summary": summary,
        "body": body,
        "urgency": urgency,
        "timeout_ms": timeout,
        "timestamp": time.time(),
        "read": False,
    }


def get_auto_dismiss_ms(urgency: str) -> int:
    """
    Return default auto-dismiss time for an urgency level.

    Args:
        urgency: "low", "normal", or "critical".

    Returns:
        Milliseconds. 0 = never auto-dismiss.
    """
    if urgency == "low":
        return 3000
    if urgency == "critical":
        return 0
    return 5000


# ===========================================================================
# In-memory notification store
# ===========================================================================

def store_notification(notif: dict) -> int:
    """
    Store a notification and return its ID.

    Thread-safe. Caps history at _HISTORY_MAX.
    """
    global _NEXT_ID
    with _LOCK:
        nid = _NEXT_ID
        _NEXT_ID += 1
        notif["id"] = nid
        _HISTORY.insert(0, notif)
        if len(_HISTORY) > _HISTORY_MAX:
            _HISTORY.pop()
    return nid


def close_notification(nid: int) -> bool:
    """Mark a notification as dismissed. Returns True if found."""
    with _LOCK:
        for n in _HISTORY:
            if n.get("id") == nid:
                n["dismissed"] = True
                return True
    return False


def get_history() -> list[dict]:
    """Return notification history (newest first)."""
    with _LOCK:
        return list(_HISTORY)


def get_unread_count() -> int:
    """Return count of unread notifications."""
    with _LOCK:
        return sum(1 for n in _HISTORY if not n.get("read", False))


def clear_all() -> None:
    """Clear all notification history."""
    with _LOCK:
        _HISTORY.clear()


# ===========================================================================
# D-Bus server
# ===========================================================================

_DBUS_AVAILABLE = False
try:
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    _DBUS_AVAILABLE = True
except ImportError:
    logger.debug("python-dbus not available — D-Bus notification server disabled")


if _DBUS_AVAILABLE:

    class NotificationServer(dbus.service.Object):
        """
        Freedesktop.org Notifications D-Bus service.

        Bus name: org.freedesktop.Notifications
        Object path: /org/freedesktop/Notifications
        """

        def __init__(self, gui_callback=None):
            """
            Args:
                gui_callback: Optional callable(notif_dict) to bridge to
                    Luminos GUI notification system.
            """
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            bus_name = dbus.service.BusName(
                "org.freedesktop.Notifications", bus
            )
            super().__init__(bus_name, "/org/freedesktop/Notifications")
            self._gui_callback = gui_callback
            logger.info("D-Bus notification server started")

        @dbus.service.method(
            "org.freedesktop.Notifications",
            in_signature="susssasa{sv}i",
            out_signature="u",
        )
        def Notify(self, app_name, replaces_id, app_icon, summary,
                   body, actions, hints, expire_timeout):
            """Handle incoming notification."""
            notif = build_notification(
                str(app_name), str(summary), str(body),
                dict(hints), int(expire_timeout),
            )
            notif["icon"] = str(app_icon)
            notif["actions"] = list(actions)

            if replaces_id > 0:
                close_notification(int(replaces_id))

            nid = store_notification(notif)

            # Bridge to Luminos GUI
            if self._gui_callback:
                try:
                    self._gui_callback(notif)
                except Exception as e:
                    logger.debug(f"GUI callback error: {e}")

            logger.debug(f"Notify: [{app_name}] {summary}")
            return dbus.UInt32(nid)

        @dbus.service.method(
            "org.freedesktop.Notifications",
            in_signature="u",
            out_signature="",
        )
        def CloseNotification(self, nid):
            """Close a notification by ID."""
            close_notification(int(nid))
            self.NotificationClosed(dbus.UInt32(nid), dbus.UInt32(3))

        @dbus.service.method(
            "org.freedesktop.Notifications",
            in_signature="",
            out_signature="as",
        )
        def GetCapabilities(self):
            """Return server capabilities."""
            return ["body", "actions", "persistence", "icon-static"]

        @dbus.service.method(
            "org.freedesktop.Notifications",
            in_signature="",
            out_signature="ssss",
        )
        def GetServerInformation(self):
            """Return server info: name, vendor, version, spec version."""
            return ("Luminos", "Luminos OS", "0.1.0", "1.2")

        @dbus.service.signal(
            "org.freedesktop.Notifications",
            signature="uu",
        )
        def NotificationClosed(self, nid, reason):
            """Signal: notification closed. Reason: 1=expired, 2=dismissed, 3=closed."""
            pass

        @dbus.service.signal(
            "org.freedesktop.Notifications",
            signature="us",
        )
        def ActionInvoked(self, nid, action_key):
            """Signal: action button was clicked."""
            pass


def start_dbus_server(gui_callback=None) -> "NotificationServer | None":
    """
    Start the D-Bus notification server.

    Args:
        gui_callback: Optional callable(notif_dict) to bridge notifications
            to the Luminos GUI system.

    Returns:
        NotificationServer instance, or None if D-Bus unavailable.
    """
    if not _DBUS_AVAILABLE:
        logger.warning(
            "D-Bus not available — install python-dbus for notification server"
        )
        return None

    try:
        server = NotificationServer(gui_callback=gui_callback)
        return server
    except Exception as e:
        logger.warning(f"Failed to start D-Bus notification server: {e}")
        return None
