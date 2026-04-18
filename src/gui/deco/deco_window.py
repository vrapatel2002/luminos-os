"""
src/gui/deco/deco_window.py
LuminosDeco — macOS-style window control buttons (close/minimize/maximize)
for all Hyprland windows.

Architecture:
  Layer-shell OVERLAY surface, TOP+LEFT anchors only.
  Polls hyprctl activewindow every 300ms.
  Repositions itself over the active window's top-left corner.
  Sends hyprctl dispatch commands on button click.

Button colours (macOS):
  Red    #FF5F57  — close     (killactive)
  Yellow #FEBC2E  — minimize  (movetoworkspacesilent special:minimized)
  Green  #28C840  — maximize  (fullscreen 1 toggle)
"""

import json
import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.deco.window")

_BUTTON_SIZE    = 13      # px diameter (macOS standard)
_BUTTON_SPACING = 8       # px between buttons
_TOP_OFFSET     = 8       # px down from window top edge
_LEFT_OFFSET    = 8       # px in from window left edge

# Classes that should never get decoration buttons
_SKIP_CLASSES = {
    "luminos-bar", "luminos-dock", "luminos-deco",
    "luminos-launcher", "luminos-quick-settings",
    "luminos-greeter", "luminos-lockscreen",
    "io.luminos.bar", "io.luminos.dock",
}

_CSS = """
.deco-btn {
    border-radius: 50%;
    border: none;
    padding: 0;
    min-width: 13px;
    min-height: 13px;
    box-shadow: none;
    outline: none;
}
.deco-btn:focus { outline: none; }

.deco-close    { background: #FF5F57; }
.deco-close:hover  { background: #E0443F; }
.deco-minimize { background: #FEBC2E; }
.deco-minimize:hover { background: #D99A1A; }
.deco-maximize { background: #28C840; }
.deco-maximize:hover { background: #1DAA31; }

.deco-pill {
    background: rgba(30, 30, 30, 0.85);
    border-radius: 20px;
    padding: 5px 8px;
}

window.deco-window {
    background: transparent;
}
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gdk
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_LAYER_SHELL_AVAILABLE = False
if _GTK_AVAILABLE:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        _LAYER_SHELL_AVAILABLE = True
    except Exception as _e:
        logger.warning(f"gtk4-layer-shell import failed: {type(_e).__name__}: {_e}")


if _GTK_AVAILABLE:

    def _make_button(css_class: str) -> "Gtk.Button":
        btn = Gtk.Button()
        btn.set_size_request(_BUTTON_SIZE, _BUTTON_SIZE)
        btn.add_css_class("deco-btn")
        btn.add_css_class(css_class)
        btn.set_can_focus(False)
        return btn

    class LuminosDeco(Gtk.ApplicationWindow):

        def __init__(self, application: Gtk.Application):
            super().__init__(application=application)

            # Layer shell MUST be init'd before anything else touches the window
            if not _LAYER_SHELL_AVAILABLE:
                logger.error("gtk4-layer-shell not available — deco disabled")
                return

            LayerShell.init_for_window(self)
            LayerShell.set_namespace(self, "luminos-deco")

            self.set_title("luminos-deco")
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_can_focus(False)
            self.add_css_class("deco-window")

            # Apply CSS
            css = Gtk.CssProvider()
            css.load_from_string(_CSS)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
            LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
            LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
            LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, False)
            LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, False)
            LayerShell.set_exclusive_zone(self, 0)
            LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.NONE)
            LayerShell.set_margin(self, LayerShell.Edge.TOP, _TOP_OFFSET)
            LayerShell.set_margin(self, LayerShell.Edge.LEFT, _LEFT_OFFSET)

            # Build button row inside a dark pill for visibility
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                          spacing=_BUTTON_SPACING)
            box.add_css_class("deco-pill")

            self._close_btn = _make_button("deco-close")
            self._close_btn.connect("clicked", self._on_close)
            box.append(self._close_btn)

            self._min_btn = _make_button("deco-minimize")
            self._min_btn.connect("clicked", self._on_minimize)
            box.append(self._min_btn)

            self._max_btn = _make_button("deco-maximize")
            self._max_btn.connect("clicked", self._on_maximize)
            box.append(self._max_btn)

            self.set_child(box)

            self._last_addr: str | None = None
            self._is_maximized_state = False

            # Start polling
            GLib.timeout_add(300, self._poll_active)

        # ------------------------------------------------------------------
        # Hyprctl helpers
        # ------------------------------------------------------------------

        def _hypr(self, *args, check=False) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["hyprctl", *args],
                capture_output=True, text=True, timeout=0.5
            )

        # ------------------------------------------------------------------
        # Active window polling
        # ------------------------------------------------------------------

        def _poll_active(self) -> bool:
            try:
                result = self._hypr("activewindow", "-j")
                if result.returncode != 0 or not result.stdout.strip():
                    self.set_visible(False)
                    return GLib.SOURCE_CONTINUE

                data = json.loads(result.stdout)
                addr = data.get("address", "")
                wclass = data.get("class", "").lower()
                over_fullscreen = data.get("overFullscreen", False)
                at   = data.get("at",   [0, 0])
                size = data.get("size", [0, 0])

                # Hide for our own surfaces or when window covers the entire screen
                if not addr or over_fullscreen or wclass in _SKIP_CLASSES:
                    self.set_visible(False)
                    return GLib.SOURCE_CONTINUE

                # Reposition when window changes or moves
                top_margin  = at[1] + _TOP_OFFSET
                left_margin = at[0] + _LEFT_OFFSET

                LayerShell.set_margin(self, LayerShell.Edge.TOP,  top_margin)
                LayerShell.set_margin(self, LayerShell.Edge.LEFT, left_margin)

                self._last_addr = addr
                self._is_maximized_state = bool(data.get("fullscreenClient", 0))

                if not self.get_visible():
                    self.set_visible(True)

            except Exception as e:
                logger.debug(f"deco poll error: {e}")

            return GLib.SOURCE_CONTINUE

        # ------------------------------------------------------------------
        # Button handlers
        # ------------------------------------------------------------------

        def _on_close(self, *_):
            self._hypr("dispatch", "killactive")

        def _on_minimize(self, *_):
            # Move active window to the hidden special:minimized workspace
            self._hypr("dispatch", "movetoworkspacesilent", "special:minimized")

        def _on_maximize(self, *_):
            # fullscreen 1 = maximize (fills workspace, no actual fullscreen)
            self._hypr("dispatch", "fullscreen", "1")
