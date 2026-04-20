"""
src/gui/notifications/notification_center.py
Notification queue manager — tracks active toasts and history.

State (pure Python, no GTK):
  _active:  list[Notification] — currently visible (≤ MAX_VISIBLE_TOASTS)
  _queue:   list[Notification] — waiting for a visible slot
  _history: list[Notification] — all-time log (newest first)
  _widgets: dict[str, ToastWidget] — GTK widgets keyed by notif.id

GTK widget creation and overlay management are delegated back to
the overlay via the _on_show/_on_hide callbacks injected at construction.
"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)

from gui.notifications.notification_model import Notification, NotifCategory

MAX_VISIBLE_TOASTS = 4
HISTORY_MAX        = 100


class NotificationCenter:
    """
    Manages notification lifecycle:
      enqueue → show (up to MAX_VISIBLE_TOASTS) → dismiss → dequeue next.

    Args:
        on_show:        Callable(notif) → called when a toast should appear.
        on_hide:        Callable(notif_id) → called when a toast should disappear.
        daemon_client:  Optional DaemonClient for Sentinel action dispatch.
    """

    def __init__(
        self,
        on_show: Callable | None = None,
        on_hide: Callable | None = None,
        daemon_client=None,
    ):
        self._active:  list[Notification] = []
        self._queue:   list[Notification] = []
        self._history: list[Notification] = []

        self._on_show      = on_show      or (lambda n: None)
        self._on_hide      = on_hide      or (lambda nid: None)
        self._daemon_client = daemon_client

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def enqueue(self, notif: Notification) -> None:
        """Add a notification — shows immediately if slot available, else queues."""
        self._history.insert(0, notif)
        if len(self._history) > HISTORY_MAX:
            self._history = self._history[:HISTORY_MAX]

        if len(self._active) < MAX_VISIBLE_TOASTS:
            self._show(notif)
        else:
            self._queue.append(notif)

    def dismiss(self, notif_id: str) -> None:
        """
        Called when a toast closes (auto-dismiss or close button).
        Removes from active list, pops next from queue if available.
        """
        self._active = [n for n in self._active if n.id != notif_id]
        self._on_hide(notif_id)

        if self._queue:
            next_notif = self._queue.pop(0)
            self._show(next_notif)

    def handle_action(self, notif_id: str, action_key: str) -> None:
        """
        Called when an action button is clicked.

        Sentinel actions (allow/block/quarantine) are dispatched to the
        daemon; all actions also dismiss the toast.
        """
        notif = self._find_active(notif_id)
        if notif and notif.category == NotifCategory.SENTINEL:
            self._dispatch_sentinel_action(notif, action_key)
        self.dismiss(notif_id)

    def get_history(self) -> list[Notification]:
        """Return all notifications (newest first), up to HISTORY_MAX."""
        return list(self._history)

    def get_unread_count(self) -> int:
        """Return the number of unread notifications in history."""
        return sum(1 for n in self._history if not n.read)

    def mark_all_read(self) -> None:
        """Mark every notification in history as read."""
        for notif in self._history:
            notif.read = True

    def active_ids(self) -> list[str]:
        """Return IDs of currently visible toasts (for testing)."""
        return [n.id for n in self._active]

    def queue_length(self) -> int:
        """Return number of notifications waiting in queue (for testing)."""
        return len(self._queue)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _show(self, notif: Notification) -> None:
        self._active.append(notif)
        try:
            self._on_show(notif)
        except Exception as e:
            logger.debug(f"NotificationCenter._show callback error: {e}")

    def _find_active(self, notif_id: str) -> Notification | None:
        for n in self._active:
            if n.id == notif_id:
                return n
        return None

    def _dispatch_sentinel_action(
        self, notif: Notification, action_key: str
    ) -> None:
        if self._daemon_client is None:
            logger.debug(
                f"Sentinel action '{action_key}' on {notif.body} — no daemon client"
            )
            return
        try:
            self._daemon_client.send(
                {
                    "type":   "sentinel_action",
                    "action": action_key,
                    "body":   notif.body,
                }
            )
        except Exception as e:
            logger.warning(f"Sentinel action dispatch failed: {e}")
