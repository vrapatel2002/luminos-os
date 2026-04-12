"""
src/gui/bar/bar_app.py
LuminosBarApp — GTK4 Application entry point for the Luminos top bar.

Usage:
    python -m gui.bar.bar_app
    # or
    python src/gui/bar/bar_app.py

The application:
- Creates a single LuminosBar window.
- Passes a DaemonClient so the bar can poll the luminos-ai daemon.
- Exits cleanly on SIGINT/SIGTERM.
"""

import logging
import os
import signal
import sys

logger = logging.getLogger("luminos-ai.gui.bar.app")

# Ensure src/ on path (needed when running directly)
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
    from gui.bar.bar_window import LuminosBar
    from gui.common.socket_client import DaemonClient

    class LuminosBarApp(Gtk.Application):
        """
        GTK4 Application wrapper for the Luminos top bar.

        Application ID: io.luminos.bar
        """

        APP_ID = "io.luminos.bar"

        def __init__(self, socket_path: str | None = None):
            super().__init__(application_id=self.APP_ID)
            self._socket_path = socket_path
            self._window: LuminosBar | None = None

        def do_activate(self):
            """Called by GTK when the app is activated. Creates the bar window."""
            if self._window is not None:
                self._window.present()
                return

            client = (
                DaemonClient(self._socket_path)
                if self._socket_path
                else DaemonClient()
            )

            self._window = LuminosBar(application=self, daemon_client=client)
            self._window.present()
            logger.info("Luminos top bar activated")

        def do_startup(self):
            """Called once on startup. Set up SIGINT/SIGTERM handlers."""
            Gtk.Application.do_startup(self)

            # Keep the application alive even if the window is somehow closed;
            # the bar must never disappear unless explicitly killed.
            self.hold()

            # Allow Ctrl+C / SIGTERM to quit the GTK app cleanly
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                                 self._on_signal)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                                 self._on_signal)

        def _on_signal(self) -> bool:
            logger.info("Signal received — quitting bar app")
            self.quit()
            return GLib.SOURCE_REMOVE


def main(argv: list | None = None) -> int:
    """
    Entry point for the Luminos top bar process.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code (0 = success).
    """
    if not _GTK_AVAILABLE:
        print("ERROR: GTK4 not available — cannot start bar", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    socket_path = None
    # Only use the production socket if it exists AND is accessible to this
    # user.  The daemon runs as root; if we can't connect we leave socket_path
    # as None and let DaemonClient use its default (/tmp/luminos-ai.sock).
    for candidate in ("/run/luminos/ai.sock", "/tmp/luminos-ai.sock"):
        if os.path.exists(candidate) and os.access(candidate, os.W_OK):
            socket_path = candidate
            break

    app = LuminosBarApp(socket_path=socket_path)
    return app.run(argv or sys.argv)


if __name__ == "__main__":
    sys.exit(main())
