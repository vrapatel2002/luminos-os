"""
src/notifications/system_notifier.py
Wires system events to the Luminos notification system.

Events → Notifications:
  Battery 20%  → "Battery Low" / normal urgency
  Battery 10%  → "Battery Critical" / critical
  Battery 5%   → "Suspending Soon" / critical
  WiFi on      → "Connected" / ssid / low urgency (3s)
  WiFi off     → "Disconnected" / normal
  App error    → "Could not launch app" / app name / normal
  Sentinel     → "Security Alert" / critical, no auto-dismiss
  Luminos update → "Update Available" (future)

Pure helpers:
    battery_notification(level) → dict
    wifi_notification(connected, ssid) → dict
    sentinel_notification(process, threat) → dict
    app_error_notification(app_name, error) → dict
"""

import logging

logger = logging.getLogger("luminos-ai.notifications.system_notifier")


# ===========================================================================
# Pure helpers — build notification dicts without side effects
# ===========================================================================

def battery_notification(level: int) -> dict | None:
    """
    Build a battery notification dict for the given level.

    Args:
        level: Battery percentage (20, 10, or 5).

    Returns:
        Notification dict, or None if level is not a trigger point.
    """
    if level == 20:
        return {
            "title": "Battery Low",
            "body": "20% remaining — consider plugging in.",
            "urgency": "normal",
            "timeout_ms": 5000,
            "category": "power",
        }
    if level == 10:
        return {
            "title": "Battery Critical",
            "body": "10% remaining — please plug in.",
            "urgency": "critical",
            "timeout_ms": 0,
            "category": "power",
        }
    if level == 5:
        return {
            "title": "Suspending Soon",
            "body": "5% remaining — suspending in 60 seconds.",
            "urgency": "critical",
            "timeout_ms": 0,
            "category": "power",
        }
    return None


def wifi_notification(connected: bool, ssid: str = "") -> dict:
    """
    Build a WiFi status change notification dict.

    Args:
        connected: True if just connected, False if disconnected.
        ssid: Network name (only used when connected).

    Returns:
        Notification dict.
    """
    if connected:
        return {
            "title": "Connected",
            "body": ssid or "Wi-Fi connected",
            "urgency": "low",
            "timeout_ms": 3000,
            "category": "network",
        }
    return {
        "title": "Disconnected",
        "body": "Wi-Fi disconnected",
        "urgency": "normal",
        "timeout_ms": 5000,
        "category": "network",
    }


def sentinel_notification(process: str, threat: str) -> dict:
    """
    Build a Sentinel security alert notification dict.

    Args:
        process: Process name that was flagged.
        threat: Brief description of the threat.

    Returns:
        Notification dict — critical, no auto-dismiss.
    """
    return {
        "title": "Security Alert",
        "body": f"{process} — {threat}",
        "urgency": "critical",
        "timeout_ms": 0,
        "category": "sentinel",
    }


def app_error_notification(app_name: str, layer: str = "") -> dict:
    """
    Build an app launch error notification dict.

    Args:
        app_name: Name of the application that failed.
        layer: Which compatibility layer failed (optional).

    Returns:
        Notification dict.
    """
    body = f"Could not launch {app_name}"
    if layer:
        body += f" ({layer} failed)"
    return {
        "title": "App Launch Failed",
        "body": body,
        "urgency": "normal",
        "timeout_ms": 8000,
        "category": "system",
    }


# ===========================================================================
# Dispatcher — sends to Luminos GUI notification system
# ===========================================================================

class SystemNotifier:
    """
    Bridges system events to the notification system.

    Call the event methods when system state changes. Each method
    builds a notification and sends it to the GUI overlay.
    """

    def __init__(self):
        self._last_wifi_state: bool | None = None

    def on_battery_level(self, level: int):
        """Called when battery reaches a trigger level (20, 10, 5)."""
        notif = battery_notification(level)
        if notif:
            self._send(notif)

    def on_wifi_change(self, connected: bool, ssid: str = ""):
        """Called when WiFi state changes."""
        # Avoid duplicate notifications
        if connected == self._last_wifi_state:
            return
        self._last_wifi_state = connected
        notif = wifi_notification(connected, ssid)
        self._send(notif)

    def on_sentinel_alert(self, process: str, threat: str):
        """Called when Sentinel flags a process."""
        notif = sentinel_notification(process, threat)
        self._send(notif)
        logger.warning(f"Sentinel alert: {process} — {threat}")

    def on_app_error(self, app_name: str, layer: str = ""):
        """Called when an app fails to launch."""
        notif = app_error_notification(app_name, layer)
        self._send(notif)

    def _send(self, notif_dict: dict):
        """Send a notification dict to the GUI system."""
        try:
            from gui.notifications.notification_model import (
                Notification, NotifLevel, NotifCategory,
            )

            # Map urgency to level
            urgency = notif_dict.get("urgency", "normal")
            level_map = {
                "low": NotifLevel.INFO,
                "normal": NotifLevel.WARNING,
                "critical": NotifLevel.DANGER,
            }
            level = level_map.get(urgency, NotifLevel.INFO)

            # Map category
            cat_str = notif_dict.get("category", "system")
            cat_map = {
                "power": NotifCategory.POWER,
                "network": NotifCategory.NETWORK,
                "sentinel": NotifCategory.SENTINEL,
                "system": NotifCategory.SYSTEM,
            }
            category = cat_map.get(cat_str, NotifCategory.SYSTEM)

            notif = Notification(
                title=notif_dict["title"],
                body=notif_dict["body"],
                level=level,
                category=category,
                auto_dismiss_ms=notif_dict.get("timeout_ms", 5000),
            )

            from gui.notifications import send
            send(notif)
        except Exception as e:
            logger.debug(f"SystemNotifier._send error: {e}")

        # Also store in the D-Bus daemon history
        try:
            from notifications.notification_daemon import store_notification
            store_notification(notif_dict)
        except Exception:
            pass
