"""
tests/test_notifications.py
Phase 8.6 — Notification System test suite.

Covers:
  - notification_model: Notification dataclass, enums, constructors  (7 tests)
  - toast_widget pure logic: _calc_progress, _level_css_class,       (5 tests)
                             _level_icon
  - notification_center: enqueue, dismiss, queue, history, actions   (5 tests)
  - notifications.__init__: headless send / get_unread_count         (1 test)

Total: 18 tests
All run headless — no GTK display required.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gui.notifications.notification_model import (
    Notification, NotifLevel, NotifCategory,
    sentinel_alert, gaming_mode_on, gaming_mode_off,
    zone3_launch, thermal_warning, model_loaded,
)
from gui.notifications.toast_widget import (
    _calc_progress, _level_css_class, _level_icon,
)
from gui.notifications.notification_center import (
    NotificationCenter, MAX_VISIBLE_TOASTS, HISTORY_MAX,
)
import gui.notifications as notif_pkg


# ===========================================================================
# notification_model
# ===========================================================================

class TestNotificationDataclass(unittest.TestCase):

    def test_auto_id_generated(self):
        n = Notification(title="Hi", body="There")
        self.assertIsInstance(n.id, str)
        self.assertEqual(len(n.id), 8)

    def test_auto_timestamp_generated(self):
        import time
        before = time.time()
        n = Notification(title="Hi", body="There")
        after = time.time()
        self.assertGreaterEqual(n.timestamp, before)
        self.assertLessEqual(n.timestamp, after)

    def test_default_level_and_category(self):
        n = Notification(title="Hi", body="There")
        self.assertEqual(n.level,    NotifLevel.INFO)
        self.assertEqual(n.category, NotifCategory.SYSTEM)

    def test_sentinel_alert_constructor(self):
        n = sentinel_alert("malware.exe", "ransomware")
        self.assertEqual(n.level,           NotifLevel.DANGER)
        self.assertEqual(n.category,        NotifCategory.SENTINEL)
        self.assertEqual(n.auto_dismiss_ms, 0)
        keys = [a["key"] for a in n.actions]
        self.assertIn("allow",      keys)
        self.assertIn("block",      keys)
        self.assertIn("quarantine", keys)

    def test_gaming_mode_on_constructor(self):
        n = gaming_mode_on()
        self.assertEqual(n.category, NotifCategory.GAMING)
        self.assertGreater(n.auto_dismiss_ms, 0)

    def test_thermal_warning_constructor(self):
        n = thermal_warning(95.3)
        self.assertEqual(n.level, NotifLevel.WARNING)
        self.assertIn("95", n.body)

    def test_model_loaded_constructor(self):
        n = model_loaded("mistral", "Q4_K_M")
        self.assertEqual(n.level,    NotifLevel.SUCCESS)
        self.assertIn("mistral",     n.body)
        self.assertIn("Q4_K_M",     n.body)


# ===========================================================================
# toast_widget pure logic
# ===========================================================================

class TestCalcProgress(unittest.TestCase):

    def test_zero_done_is_full(self):
        self.assertAlmostEqual(_calc_progress(0, 100), 1.0)

    def test_half_done_is_half(self):
        self.assertAlmostEqual(_calc_progress(50, 100), 0.5)

    def test_all_done_is_zero(self):
        self.assertAlmostEqual(_calc_progress(100, 100), 0.0)

    def test_over_ticks_clamped_to_zero(self):
        self.assertEqual(_calc_progress(200, 100), 0.0)

    def test_zero_total_returns_zero(self):
        self.assertEqual(_calc_progress(0, 0), 0.0)


class TestLevelHelpers(unittest.TestCase):

    def test_css_class_danger(self):
        self.assertEqual(_level_css_class(NotifLevel.DANGER), "notif-danger")

    def test_css_class_success(self):
        self.assertEqual(_level_css_class(NotifLevel.SUCCESS), "notif-success")

    def test_icon_warning(self):
        self.assertIn("⚠", _level_icon(NotifLevel.WARNING))

    def test_icon_info(self):
        self.assertEqual(_level_icon(NotifLevel.INFO), "ℹ")

    def test_icon_success(self):
        self.assertEqual(_level_icon(NotifLevel.SUCCESS), "✓")


# ===========================================================================
# notification_center
# ===========================================================================

class TestNotificationCenter(unittest.TestCase):

    def _make_center(self):
        shown  = []
        hidden = []
        center = NotificationCenter(
            on_show=lambda n: shown.append(n.id),
            on_hide=lambda nid: hidden.append(nid),
        )
        return center, shown, hidden

    def test_enqueue_shows_immediately_when_slot_free(self):
        center, shown, _ = self._make_center()
        n = Notification(title="T", body="B")
        center.enqueue(n)
        self.assertIn(n.id, shown)
        self.assertIn(n.id, center.active_ids())

    def test_queue_held_when_max_visible_full(self):
        center, shown, _ = self._make_center()
        notifs = [Notification(title=f"T{i}", body="B") for i in range(MAX_VISIBLE_TOASTS + 1)]
        for n in notifs:
            center.enqueue(n)
        self.assertEqual(len(center.active_ids()), MAX_VISIBLE_TOASTS)
        self.assertEqual(center.queue_length(), 1)

    def test_dismiss_pops_queue(self):
        center, shown, _ = self._make_center()
        notifs = [Notification(title=f"T{i}", body="B") for i in range(MAX_VISIBLE_TOASTS + 1)]
        for n in notifs:
            center.enqueue(n)
        # Dismiss one active → queued notification should fill slot
        first_id = center.active_ids()[0]
        center.dismiss(first_id)
        self.assertEqual(center.queue_length(), 0)
        self.assertEqual(len(center.active_ids()), MAX_VISIBLE_TOASTS)

    def test_history_recorded(self):
        center, _, _ = self._make_center()
        n = Notification(title="T", body="B")
        center.enqueue(n)
        ids = [h.id for h in center.get_history()]
        self.assertIn(n.id, ids)

    def test_sentinel_action_dispatches_to_daemon(self):
        mock_client = MagicMock()
        center = NotificationCenter(
            on_show=lambda n: None,
            on_hide=lambda nid: None,
            daemon_client=mock_client,
        )
        n = sentinel_alert("bad.exe", "trojan")
        center.enqueue(n)
        center.handle_action(n.id, "block")
        mock_client.send.assert_called_once()
        call_arg = mock_client.send.call_args[0][0]
        self.assertEqual(call_arg["type"],   "sentinel_action")
        self.assertEqual(call_arg["action"], "block")


# ===========================================================================
# notifications.__init__ headless
# ===========================================================================

class TestNotifPackageHeadless(unittest.TestCase):

    def test_send_and_get_unread_no_crash(self):
        """send() and get_unread_count() must not raise even without a display."""
        try:
            notif_pkg.send_gaming_on()
            notif_pkg.send_gaming_off()
            count = notif_pkg.get_unread_count()
            self.assertIsInstance(count, int)
        except Exception as e:
            self.fail(f"notif_pkg raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
