"""
src/gui/notifications/toast_widget.py
Single toast notification widget — slide-in popup with progress bar.

Pure logic (_calc_progress) is module-level for headless testing.
GTK class is guarded behind _GTK_AVAILABLE.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

from gui.notifications.notification_model import Notification, NotifLevel


# ===========================================================================
# Pure logic — testable without GTK
# ===========================================================================

def _calc_progress(ticks_done: int, ticks_total: float) -> float:
    """
    Return progress bar fill fraction [1.0 → 0.0].

    Args:
        ticks_done:  How many ticks have elapsed.
        ticks_total: Total ticks for the full dismiss duration.

    Returns:
        Clamped float in [0.0, 1.0].
    """
    if ticks_total <= 0:
        return 0.0
    raw = 1.0 - ticks_done / ticks_total
    return max(0.0, min(1.0, raw))


def _level_css_class(level: NotifLevel) -> str:
    """Map NotifLevel to a CSS class name."""
    return {
        NotifLevel.INFO:    "notif-info",
        NotifLevel.SUCCESS: "notif-success",
        NotifLevel.WARNING: "notif-warning",
        NotifLevel.DANGER:  "notif-danger",
    }.get(level, "notif-info")


def _level_icon(level: NotifLevel) -> str:
    """Map NotifLevel to a leading icon character."""
    return {
        NotifLevel.INFO:    "ℹ",
        NotifLevel.SUCCESS: "✓",
        NotifLevel.WARNING: "⚠",
        NotifLevel.DANGER:  "✕",
    }.get(level, "ℹ")


# ===========================================================================
# GTK widget
# ===========================================================================

if _GTK_AVAILABLE:
    class ToastWidget(Gtk.Box):
        """
        A single toast notification card.

        Layout (vertical box):
          ┌─────────────────────────────────┐
          │ [icon] Title             [×]    │
          │        Body text                │
          │ [Action1] [Action2]             │
          │ ════════════════════ progress   │
          └─────────────────────────────────┘

        Args:
            notif:      The Notification to display.
            on_action:  Callable(notif_id: str, action_key: str) — action button clicked.
            on_dismiss: Callable(notif_id: str) — close button or auto-dismiss fired.
        """

        TICK_INTERVAL_MS = 50

        def __init__(
            self,
            notif: Notification,
            on_action,
            on_dismiss,
        ):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.notif     = notif
            self.on_action = on_action
            self.on_dismiss = on_dismiss

            # Auto-dismiss state
            self.ticks_done  = 0
            self.ticks_total = (
                notif.auto_dismiss_ms / self.TICK_INTERVAL_MS
                if notif.auto_dismiss_ms > 0 else 0
            )

            self._build_ui()
            self.add_css_class("toast-card")
            self.add_css_class(_level_css_class(notif.level))

            if notif.auto_dismiss_ms > 0:
                self._start_auto_dismiss()

        # -------------------------------------------------------------------
        # UI construction
        # -------------------------------------------------------------------

        def _build_ui(self):
            # Header row: [icon] [title_label] [close_btn]
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            header.set_margin_start(12)
            header.set_margin_end(8)
            header.set_margin_top(10)

            icon_label = Gtk.Label(label=_level_icon(self.notif.level))
            icon_label.add_css_class("toast-icon")
            header.append(icon_label)

            title_label = Gtk.Label(label=self.notif.title)
            title_label.set_hexpand(True)
            title_label.set_halign(Gtk.Align.START)
            title_label.add_css_class("toast-title")
            header.append(title_label)

            close_btn = Gtk.Button(label="×")
            close_btn.add_css_class("toast-close")
            close_btn.connect("clicked", self._on_close_click)
            header.append(close_btn)

            self.append(header)

            # Body text
            if self.notif.body:
                body_label = Gtk.Label(label=self.notif.body)
                body_label.set_halign(Gtk.Align.START)
                body_label.set_margin_start(12)
                body_label.set_margin_end(12)
                body_label.set_margin_top(2)
                body_label.set_margin_bottom(6)
                body_label.set_wrap(True)
                body_label.add_css_class("toast-body")
                self.append(body_label)

            # Action buttons row
            if self.notif.actions:
                actions_row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=6
                )
                actions_row.set_margin_start(12)
                actions_row.set_margin_end(12)
                actions_row.set_margin_bottom(8)
                for action in self.notif.actions:
                    btn = Gtk.Button(label=action["label"])
                    btn.add_css_class("toast-action")
                    btn.connect(
                        "clicked",
                        self._make_action_handler(action["key"]),
                    )
                    actions_row.append(btn)
                self.append(actions_row)

            # Progress bar (auto-dismiss indicator)
            self._progress_bar = Gtk.ProgressBar()
            self._progress_bar.set_fraction(1.0)
            self._progress_bar.add_css_class("toast-progress")
            if self.notif.auto_dismiss_ms == 0:
                self._progress_bar.set_visible(False)
            self.append(self._progress_bar)

        # -------------------------------------------------------------------
        # Auto-dismiss
        # -------------------------------------------------------------------

        def _start_auto_dismiss(self):
            self.ticks_done = 0
            GLib.timeout_add(self.TICK_INTERVAL_MS, self._tick)

        def _tick(self) -> bool:
            self.ticks_done += 1
            progress = _calc_progress(self.ticks_done, self.ticks_total)
            self._update_progress_bar(progress)
            if self.ticks_done >= self.ticks_total:
                self.on_dismiss(self.notif.id)
                return False           # stop timer
            return True                # GLib.SOURCE_CONTINUE

        def _update_progress_bar(self, fraction: float):
            self._progress_bar.set_fraction(fraction)

        # -------------------------------------------------------------------
        # Callbacks
        # -------------------------------------------------------------------

        def _on_close_click(self, *_):
            self.on_dismiss(self.notif.id)

        def _make_action_handler(self, key: str):
            def handler(*_):
                self.on_action(self.notif.id, key)
            return handler

        # -------------------------------------------------------------------
        # Pure-logic mirrors (for symmetry with other modules)
        # -------------------------------------------------------------------

        @staticmethod
        def _calc_progress(ticks_done: int, ticks_total: float) -> float:
            return _calc_progress(ticks_done, ticks_total)

        @staticmethod
        def _level_css_class(level: NotifLevel) -> str:
            return _level_css_class(level)

        @staticmethod
        def _level_icon(level: NotifLevel) -> str:
            return _level_icon(level)
