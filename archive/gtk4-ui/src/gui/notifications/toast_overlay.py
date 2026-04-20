"""
src/gui/notifications/toast_overlay.py
Persistent layer-shell overlay window that hosts all active toast widgets.

Anchored top-right, margin_top=44 (below the Luminos bar), margin_right=12.
Width is fixed at 340px; height grows/shrinks as toasts are added/removed.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    try:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell as LayerShell
        _LAYER_SHELL = True
    except (ImportError, ValueError):
        _LAYER_SHELL = False
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False
    _LAYER_SHELL   = False

from gui.notifications.notification_model import Notification
from gui.notifications.notification_center import NotificationCenter

TOAST_WIDTH    = 340
MARGIN_TOP     = 44   # below Luminos bar
MARGIN_RIGHT   = 12
TOAST_SPACING  = 8


if _GTK_AVAILABLE:
    class ToastOverlay(Gtk.Window):
        """
        Transparent overlay window pinned to the top-right corner of the screen.
        Hosts a vertical box of ToastWidget instances.

        The window is always present (never destroyed), but is shown/hidden
        as toasts appear and disappear.
        """

        def __init__(self, app=None):
            super().__init__()
            if app:
                self.set_application(app)

            self._center = NotificationCenter(
                on_show=self._on_show_notif,
                on_hide=self._on_hide_notif,
            )
            self._widgets: dict[str, object] = {}  # notif_id → ToastWidget

            self._build_window()
            self._build_content()

        # -------------------------------------------------------------------
        # Window setup
        # -------------------------------------------------------------------

        def _build_window(self):
            self.set_title("luminos-toasts")
            self.set_resizable(False)
            self.set_decorated(False)
            self.set_default_size(TOAST_WIDTH, 1)

            if _LAYER_SHELL:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_anchor(self, LayerShell.Edge.TOP,   True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT,  True)
                LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, False)
                LayerShell.set_anchor(self, LayerShell.Edge.LEFT,   False)
                LayerShell.set_margin(self, LayerShell.Edge.TOP,   MARGIN_TOP)
                LayerShell.set_margin(self, LayerShell.Edge.RIGHT, MARGIN_RIGHT)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.NONE
                )
                LayerShell.set_exclusive_zone(self, 0)

        def _build_content(self):
            self._toast_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=TOAST_SPACING,
            )
            self._toast_box.set_size_request(TOAST_WIDTH, -1)
            self.set_child(self._toast_box)

        # -------------------------------------------------------------------
        # NotificationCenter callbacks
        # -------------------------------------------------------------------

        def _on_show_notif(self, notif: Notification) -> None:
            """Called by NotificationCenter when a toast should appear."""
            try:
                from gui.notifications.toast_widget import ToastWidget
                widget = ToastWidget(
                    notif=notif,
                    on_action=self._center.handle_action,
                    on_dismiss=self._center.dismiss,
                )
                self._widgets[notif.id] = widget
                self._toast_box.append(widget)
                self.present()
            except Exception as e:
                logger.warning(f"ToastOverlay._on_show_notif error: {e}")

        def _on_hide_notif(self, notif_id: str) -> None:
            """Called by NotificationCenter when a toast should disappear."""
            widget = self._widgets.pop(notif_id, None)
            if widget is not None:
                self._toast_box.remove(widget)
            # Hide the window when no toasts remain
            if not self._widgets:
                self.set_visible(False)

        # -------------------------------------------------------------------
        # Public send API (delegates to NotificationCenter)
        # -------------------------------------------------------------------

        def send(self, notif: Notification) -> None:
            self._center.enqueue(notif)

        def get_center(self) -> NotificationCenter:
            return self._center
