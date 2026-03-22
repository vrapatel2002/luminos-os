"""
src/gui/firstrun/firstrun_app.py
FirstRunApp — GTK Application wrapper for the First Run wizard.

Application ID: io.luminos.firstrun
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.firstrun.app")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gio
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

APP_ID = "io.luminos.firstrun"


if _GTK_AVAILABLE:

    class FirstRunApp(Gtk.Application):
        """
        GTK Application for the First Run Setup wizard.

        Presents a full-screen FirstRunWindow.
        The application exits when setup completes (window.close()).
        """

        def __init__(self):
            super().__init__(
                application_id=APP_ID,
                flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            )
            self._window = None

        def do_activate(self):
            if self._window is None:
                from gui.firstrun.firstrun_window import FirstRunWindow
                self._window = FirstRunWindow()
                self._window.set_application(self)
                # Re-exit when window is destroyed
                self._window.connect("destroy", lambda *_: self.quit())

            self._window.present()


    def main():
        """Entry point for the io.luminos.firstrun application."""
        app = FirstRunApp()
        return app.run(sys.argv)


    if __name__ == "__main__":
        sys.exit(main() or 0)

else:
    class FirstRunApp:  # type: ignore[no-redef]
        """Headless stub."""
        def run(self, args):
            logger.warning("GTK not available — cannot run firstrun app")
