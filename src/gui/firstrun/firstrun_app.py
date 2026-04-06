"""
src/gui/firstrun/firstrun_app.py
Phase 5.9 — FirstRunApp GTK Application wrapper.

Application ID: io.luminos.firstrun

Checks ~/.config/luminos/first_run_complete on start:
  - If missing: launch the 4-screen first-run wizard.
  - If present: exit immediately (session script handles desktop launch).
"""

import logging
import os
import sys

logger = logging.getLogger("luminos.firstrun.app")

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
        """GTK Application for the Luminos first-run wizard."""

        def __init__(self):
            super().__init__(
                application_id=APP_ID,
                flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            )
            self._window = None

        def do_activate(self):
            from gui.firstrun.firstrun_state import is_complete
            if is_complete():
                logger.info("First run already complete — exiting.")
                self.quit()
                return

            if self._window is None:
                from gui.firstrun.firstrun_window import FirstRunWindow
                self._window = FirstRunWindow()
                self._window.set_application(self)
                self._window.connect("destroy", lambda *_: self.quit())

            self._window.present()


    def main():
        """Entry point: check flag, run wizard if needed."""
        from gui.firstrun.firstrun_state import is_complete
        if is_complete():
            return 0
        app = FirstRunApp()
        return app.run(sys.argv)


    if __name__ == "__main__":
        sys.exit(main() or 0)

else:

    class FirstRunApp:  # type: ignore[no-redef]
        """Headless stub."""
        def run(self, args):
            logger.warning("GTK not available — cannot run firstrun app")

    def main():
        logger.warning("GTK not available")
        return 1
