"""
src/gui/settings/panels/appearance_panel.py
AppearancePanel — theme, accent color, font size, icon theme, animations.

Pure helpers:
    _get_theme_mode(mode_str) → "dark" | "light" | "auto"
    _get_accent_presets()     → list[dict] with name + hex
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.appearance")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme import mode


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_theme_mode(mode_str: str) -> str:
    """
    Normalize a theme mode string to "dark" | "light" | "auto".

    Args:
        mode_str: Raw string from config or mode manager.

    Returns:
        One of "dark", "light", "auto".
    """
    cleaned = mode_str.strip().lower()
    if cleaned in ("dark", "light", "auto"):
        return cleaned
    # True/False from ModeManager.get_mode() → bool
    if mode_str is True or cleaned == "true":
        return "dark"
    if mode_str is False or cleaned == "false":
        return "light"
    return "auto"


def _get_accent_presets() -> list:
    """Return the 8 built-in accent color presets."""
    return [
        {"name": "Blue",    "hex": "#3584e4"},
        {"name": "Purple",  "hex": "#9141ac"},
        {"name": "Pink",    "hex": "#e01b6a"},
        {"name": "Red",     "hex": "#e01b24"},
        {"name": "Orange",  "hex": "#ff7800"},
        {"name": "Yellow",  "hex": "#f5c211"},
        {"name": "Green",   "hex": "#26a269"},
        {"name": "Teal",    "hex": "#2190a4"},
    ]


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class AppearancePanel(Gtk.Box):
        """
        Appearance settings panel.

        Controls: theme radio (dark/light/auto), accent color picker,
        font size slider, icon theme dropdown, animations toggle.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            self.set_margin_top(24)
            self.set_margin_bottom(24)
            self.set_margin_start(32)
            self.set_margin_end(32)

            self._build()

        def _build(self):
            # ---- Theme mode ----
            theme_lbl = Gtk.Label(label="Theme")
            theme_lbl.add_css_class("luminos-settings-section-title")
            theme_lbl.set_halign(Gtk.Align.START)
            self.append(theme_lbl)

            theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            current = _get_theme_mode(str(mode.get_mode()))

            self._dark_radio  = Gtk.CheckButton(label="Dark")
            self._light_radio = Gtk.CheckButton(label="Light")
            self._auto_radio  = Gtk.CheckButton(label="Auto")
            self._light_radio.set_group(self._dark_radio)
            self._auto_radio.set_group(self._dark_radio)

            if current == "dark":
                self._dark_radio.set_active(True)
            elif current == "light":
                self._light_radio.set_active(True)
            else:
                self._auto_radio.set_active(True)

            for radio in (self._dark_radio, self._light_radio, self._auto_radio):
                radio.connect("toggled", self._on_theme_toggled)
                theme_box.append(radio)

            self.append(theme_box)

            self.append(Gtk.Separator())

            # ---- Accent color ----
            accent_lbl = Gtk.Label(label="Accent Color")
            accent_lbl.add_css_class("luminos-settings-section-title")
            accent_lbl.set_halign(Gtk.Align.START)
            self.append(accent_lbl)

            accent_flow = Gtk.FlowBox()
            accent_flow.set_max_children_per_line(8)
            accent_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
            for preset in _get_accent_presets():
                swatch = Gtk.Button()
                swatch.set_size_request(32, 32)
                swatch.set_tooltip_text(preset["name"])
                swatch.add_css_class("luminos-accent-swatch")
                swatch._hex = preset["hex"]
                # Inline color via CSS — simple inline style via CssProvider
                swatch.connect("clicked", self._on_accent_click)
                accent_flow.append(swatch)
            self.append(accent_flow)

            self.append(Gtk.Separator())

            # ---- Font size ----
            font_lbl = Gtk.Label(label="Font Size")
            font_lbl.add_css_class("luminos-settings-section-title")
            font_lbl.set_halign(Gtk.Align.START)
            self.append(font_lbl)

            font_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            font_row.set_hexpand(True)

            self._font_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 8, 20, 1
            )
            self._font_slider.set_value(11)
            self._font_slider.set_hexpand(True)
            self._font_slider.set_draw_value(True)
            self._font_slider.connect("value-changed", self._on_font_changed)
            font_row.append(self._font_slider)
            self.append(font_row)

            self.append(Gtk.Separator())

            # ---- Animations toggle ----
            anim_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            anim_row.set_hexpand(True)
            anim_lbl = Gtk.Label(label="Enable Animations")
            anim_lbl.set_hexpand(True)
            anim_lbl.set_halign(Gtk.Align.START)
            self._anim_switch = Gtk.Switch()
            self._anim_switch.set_active(True)
            self._anim_switch.connect("state-set", self._on_anim_toggle)
            anim_row.append(anim_lbl)
            anim_row.append(self._anim_switch)
            self.append(anim_row)

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _on_theme_toggled(self, radio):
            if not radio.get_active():
                return
            if radio is self._dark_radio:
                mode.set_manual(True)
            elif radio is self._light_radio:
                mode.set_manual(False)
            else:
                mode.set_auto()

        def _on_accent_click(self, btn):
            hex_color = getattr(btn, "_hex", None)
            if hex_color:
                logger.debug(f"Accent color selected: {hex_color}")
                # Future: write accent to theme config

        def _on_font_changed(self, slider):
            size = int(slider.get_value())
            logger.debug(f"Font size changed to {size}")
            # Future: write to theme config + reload CSS

        def _on_anim_toggle(self, switch, state):
            logger.debug(f"Animations {'on' if state else 'off'}")
            return False

else:
    # Headless stub so other modules can import panel name without GTK
    class AppearancePanel:  # type: ignore[no-redef]
        pass
