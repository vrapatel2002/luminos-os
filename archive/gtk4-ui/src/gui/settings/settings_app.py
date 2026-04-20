"""
src/gui/settings/settings_app.py
LuminosSettingsApp — GTK Application wrapper for the Settings window.

Application ID: io.luminos.settings
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.app")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gio
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme import mode, generate_css

APP_ID = "io.luminos.settings"


if _GTK_AVAILABLE:

    class LuminosSettingsApp(Gtk.Application):
        """
        GTK Application for the Luminos Settings window.

        Creates one LuminosSettings window and presents it on activate.
        Re-raises the existing window if the app is activated again.
        """

        def __init__(self):
            super().__init__(
                application_id=APP_ID,
                flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            )
            self._window = None

        def do_activate(self):
            if self._window is None:
                from gui.settings.settings_window import LuminosSettings

                # Apply theme CSS globally before creating window
                css_provider = Gtk.CssProvider()
                css_provider.load_from_string(generate_css(mode.get_mode()))
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(),
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                ) if False else None  # Display available after window creation

                self._window = LuminosSettings(application=self)

            self._window.present()


def main():
    """Entry point for the luminos-settings command."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    app = LuminosSettingsApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main() or 0)
