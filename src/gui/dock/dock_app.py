"""
src/gui/dock/dock_app.py
LuminosDockApp — GTK4 Application entry point for the Luminos dock.

Usage:
    python -m gui.dock.dock_app
    # or
    python src/gui/dock/dock_app.py
"""

import logging
import os
import signal
import sys

logger = logging.getLogger("luminos-ai.gui.dock.app")

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

if _GTK_AVAILABLE:
    from gui.dock.dock_window import LuminosDock
    from gui.common.socket_client import DaemonClient

    class LuminosDockApp(Gtk.Application):
        """
        GTK4 Application wrapper for the Luminos dock.

        Application ID: io.luminos.dock
        """

        APP_ID = "io.luminos.dock"

        def __init__(self, socket_path: str | None = None):
            super().__init__(application_id=self.APP_ID)
            self._socket_path = socket_path
            self._window: "LuminosDock | None" = None

        def do_activate(self):
            if self._window is not None:
                self._window.present()
                return

            client = (
                DaemonClient(self._socket_path)
                if self._socket_path
                else DaemonClient()
            )

            self._window = LuminosDock(application=self, daemon_client=client)
            self._window.present()
            logger.info("Luminos dock activated")

        def do_startup(self):
            Gtk.Application.do_startup(self)

            # Keep the application alive even if the window is somehow closed;
            # the dock must never disappear unless explicitly killed.
            self.hold()

            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                                 self._on_signal)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                                 self._on_signal)

        def _on_signal(self) -> bool:
            logger.info("Signal received — quitting dock app")
            self.quit()
            return GLib.SOURCE_REMOVE


def main(argv: list | None = None) -> int:
    """Entry point for the Luminos dock process."""
    if not _GTK_AVAILABLE:
        print("ERROR: GTK4 not available — cannot start dock", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    socket_path = None
    prod_path   = "/run/luminos/ai.sock"
    if os.path.exists(prod_path):
        socket_path = prod_path

    app = LuminosDockApp(socket_path=socket_path)
    return app.run(argv or sys.argv)


if __name__ == "__main__":
    sys.exit(main())
