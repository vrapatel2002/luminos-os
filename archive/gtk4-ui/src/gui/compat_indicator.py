"""
src/gui/compat_indicator.py
Phase 5.10 Task 4 — Floating progress pill shown when routing a .exe.

Appears near the cursor within 100ms of launching a .exe.
Shows: spinner + "Analyzing..." → "Opening with Proton" → disappears.
If routing takes > 5s: shows "This is taking longer than usual..."

Style: glass pill, ACCENT spinner, FONT_BODY_SMALL.

Usage:
    indicator = CompatIndicator()
    indicator.show()
    # ... routing runs ...
    indicator.set_result("Opening with Proton")  # auto-hides after 1.5s
"""

import logging
import os
import sys

logger = logging.getLogger("luminos.compat_indicator")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_LAYER_SHELL_AVAILABLE = False
if _GTK_AVAILABLE:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        _LAYER_SHELL_AVAILABLE = True
    except (ImportError, ValueError):
        pass

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    ACCENT, BG_ELEVATED, TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER, FONT_BODY_SMALL, SPACE_3, SPACE_4,
)

_INDICATOR_CSS = f"""
.compat-pill {{
    background-color: rgba(28, 28, 38, 0.92);
    border: 1px solid {BORDER};
    border-radius: 999px;
    padding: 8px 16px;
    box-shadow: 0px 4px 16px rgba(0,0,0,0.4);
}}
.compat-pill-text {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_BODY_SMALL}px;
    font-weight: 400;
}}
.compat-pill-slow {{
    color: {TEXT_SECONDARY};
    font-size: {FONT_BODY_SMALL}px;
}}
"""

# Layer display names for result messages
LAYER_DISPLAY = {
    "proton":      "Opening with Proton",
    "wine":        "Opening with Wine",
    "lutris":      "Opening with Lutris",
    "firecracker": "Opening with microVM",
    "kvm":         "Opening in Windows VM",
    "native":      "Opening natively",
    "error":       "Could not open app",
}


if _GTK_AVAILABLE:

    class CompatIndicator:
        """
        Floating glass pill that shows routing progress for a .exe launch.
        """

        def __init__(self):
            self._window = None
            self._label  = None
            self._spinner = None
            self._slow_timer = None
            self._hide_timer = None
            self._elapsed_timer = None
            self._elapsed_secs = 0
            self._app = None

        def show(self) -> None:
            """Show the 'Analyzing...' pill. Call within 100ms of launch."""
            if self._window is not None:
                return

            self._elapsed_secs = 0
            self._window = Gtk.Window()
            self._window.set_decorated(False)
            self._window.set_resizable(False)
            self._window.set_can_focus(False)

            # Apply CSS
            css = Gtk.CssProvider()
            css.load_from_string(_INDICATOR_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self._window.get_display(), css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # Layer-shell: float at bottom-center
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self._window)
                LayerShell.set_layer(self._window, LayerShell.Layer.OVERLAY)
                LayerShell.set_anchor(self._window, LayerShell.Edge.BOTTOM, True)
                LayerShell.set_margin(self._window, LayerShell.Edge.BOTTOM, 80)
                LayerShell.set_keyboard_mode(
                    self._window, LayerShell.KeyboardMode.NONE
                )

            # Layout: spinner + label
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3)
            box.add_css_class("compat-pill")

            self._spinner = Gtk.Spinner()
            self._spinner.set_size_request(14, 14)
            self._spinner.start()
            box.append(self._spinner)

            self._label = Gtk.Label(label="Analyzing...")
            self._label.add_css_class("compat-pill-text")
            box.append(self._label)

            self._window.set_child(box)
            self._window.set_default_size(1, 1)
            self._window.present()

            # "Taking longer" warning after 5s
            self._slow_timer = GLib.timeout_add_seconds(
                5, self._on_slow_warning
            )
            # Track elapsed for logging
            self._elapsed_timer = GLib.timeout_add_seconds(
                1, self._tick_elapsed
            )

        def set_result(self, layer_key: str) -> None:
            """
            Show result message for 1.5s then disappear.

            Args:
                layer_key: One of proton/wine/firecracker/kvm/native/error.
            """
            if self._window is None:
                return

            self._cancel_timers()

            msg = LAYER_DISPLAY.get(layer_key, f"Opening with {layer_key}")
            if self._label:
                self._label.set_text(msg)
            if self._spinner:
                self._spinner.stop()
                self._spinner.set_visible(False)

            self._hide_timer = GLib.timeout_add(1500, self._hide)

        def hide(self) -> None:
            """Immediately hide and destroy the pill."""
            self._cancel_timers()
            self._hide()

        def _on_slow_warning(self) -> bool:
            if self._label:
                self._label.set_text("This is taking longer than usual...")
                self._label.remove_css_class("compat-pill-text")
                self._label.add_css_class("compat-pill-slow")
            return GLib.SOURCE_REMOVE

        def _tick_elapsed(self) -> bool:
            self._elapsed_secs += 1
            return GLib.SOURCE_CONTINUE

        def _hide(self) -> bool:
            if self._window:
                self._window.close()
                self._window  = None
                self._label   = None
                self._spinner = None
            return GLib.SOURCE_REMOVE

        def _cancel_timers(self) -> None:
            for attr in ("_slow_timer", "_hide_timer", "_elapsed_timer"):
                handle = getattr(self, attr, None)
                if handle is not None:
                    GLib.source_remove(handle)
                    setattr(self, attr, None)


else:

    class CompatIndicator:  # type: ignore[no-redef]
        """Headless stub."""
        def show(self): pass
        def set_result(self, layer_key): pass
        def hide(self): pass
