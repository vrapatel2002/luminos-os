"""
src/gui/store/store_app.py
Luminos Store application entry point.

Run directly:
  python3 src/gui/store/store_app.py
Or as installed command:
  luminos-store
"""

import logging
import sys

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gio
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False


if _GTK_AVAILABLE:
    class LuminosStoreApp(Gtk.Application):
        """GTK4 Application wrapper for the Luminos Store."""

        def __init__(self):
            super().__init__(application_id="io.luminos.store")

        def do_activate(self):
            # Apply Luminos theme CSS
            try:
                from gui.theme import generate_css, mode
                css = generate_css(mode.is_dark)
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                Gtk.StyleContext.add_provider_for_display(
                    self.get_display(),
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception as e:
                logger.debug(f"Theme CSS load failed: {e}")

            from gui.store.store_window import LuminosStore
            win = LuminosStore(self)
            win.present()


def main():
    if not _GTK_AVAILABLE:
        print("GTK4 not available — cannot start Luminos Store", file=sys.stderr)
        sys.exit(1)
    app = LuminosStoreApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
