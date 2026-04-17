"""
src/gui/deco/deco_app.py
LuminosDecoApp — entry point for the window decoration overlay.

Usage:
    python -m gui.deco.deco_app
"""

import logging
import os
import signal
import sys

logger = logging.getLogger("luminos-ai.gui.deco.app")

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
    from gui.deco.deco_window import LuminosDeco

    class LuminosDecoApp(Gtk.Application):

        APP_ID = "io.luminos.deco"

        def __init__(self):
            super().__init__(application_id=self.APP_ID)
            self._window: "LuminosDeco | None" = None

        def do_activate(self):
            if self._window is not None:
                return
            self._window = LuminosDeco(application=self)
            self._window.present()
            logger.info("Luminos deco activated")

        def do_startup(self):
            Gtk.Application.do_startup(self)
            self.hold()
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,  self._quit)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._quit)

        def _quit(self) -> bool:
            logger.info("Signal received — quitting deco app")
            self.quit()
            return GLib.SOURCE_REMOVE


def main(argv: list | None = None) -> int:
    if not _GTK_AVAILABLE:
        print("ERROR: GTK4 not available", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = LuminosDecoApp()
    return app.run(argv or sys.argv)


if __name__ == "__main__":
    sys.exit(main())
