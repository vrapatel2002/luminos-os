#!/usr/bin/env python3
"""
src/gui/greeter/greeter_app.py
Entry point for the Luminos greetd greeter.

Usage (in greetd config.toml):
  command = "python3 /opt/luminos/src/gui/greeter/greeter_app.py"
"""

import logging
import os
import sys

# Ensure src/ is on the path
_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("luminos-greeter")


def main():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
    except (ImportError, ValueError) as e:
        logger.error(f"GTK4 not available: {e}")
        sys.exit(1)

    from gui.greeter.greeter_window import LuminosGreeter

    class GreeterApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="os.luminos.greeter")

        def do_activate(self):
            win = LuminosGreeter(app=self)
            win.present()

    app = GreeterApp()
    app.run(None)


if __name__ == "__main__":
    main()
