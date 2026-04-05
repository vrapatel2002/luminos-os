"""
src/gui/settings/panels/keyboard_panel.py
KeyboardPanel — backlight brightness, auto-off, LED effect, color.

Pure helpers:
    _get_brightness_options() → list[dict]
    _get_auto_off_options()   → list[str]
    _get_effect_options()     → list[str]
    _get_color_presets()      → list[dict]
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.keyboard")

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

from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE, ACCENT_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    COLOR_SUCCESS,
    FONT_FAMILY, FONT_H3, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_FULL,
    SETTINGS_PADDING,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_brightness_options() -> list[dict]:
    """
    Returns brightness level options.

    Each dict: {"label": str, "value": int}
    Values: 0=Off, 1=Low, 2=Medium, 3=High
    """
    return [
        {"label": "Off",    "value": 0},
        {"label": "Low",    "value": 1},
        {"label": "Medium", "value": 2},
        {"label": "High",   "value": 3},
    ]


def _get_auto_off_options() -> list[str]:
    """Returns auto-off timeout options."""
    return ["30s", "1min", "2min", "Never"]


def _get_effect_options() -> list[str]:
    """Returns keyboard LED effect options."""
    return ["Solid", "Breathe", "Reactive"]


def _get_color_presets() -> list[dict]:
    """
    Returns keyboard color presets (same palette as accent picker).

    Each dict: {"name": str, "hex": str}
    """
    return [
        {"name": "Electric Blue", "hex": "#0080FF"},
        {"name": "Deep Purple",   "hex": "#7B2FFF"},
        {"name": "Teal",          "hex": "#00C8C8"},
        {"name": "Amber",         "hex": "#FFB020"},
        {"name": "Red",           "hex": "#FF4455"},
        {"name": "Green",         "hex": "#00C896"},
        {"name": "Pink",          "hex": "#E01B6A"},
        {"name": "Soft White",    "hex": "#E8E8F0"},
    ]


# ===========================================================================
# CSS
# ===========================================================================

_KEYBOARD_CSS = f"""
.luminos-kbd-segmented {{
    background-color: {BG_ELEVATED};
    border-radius: {RADIUS_FULL}px;
    padding: 2px;
}}

.luminos-kbd-segmented > button {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_SECONDARY};
    background: transparent;
    border: none;
    border-radius: {RADIUS_FULL}px;
    padding: {SPACE_2}px {SPACE_3}px;
    min-height: 28px;
}}

.luminos-kbd-segmented-active {{
    background-color: {ACCENT};
    color: {TEXT_PRIMARY};
}}

.luminos-kbd-color-dot {{
    min-width: 28px;
    min-height: 28px;
    border-radius: {RADIUS_FULL}px;
    border: 2px solid transparent;
}}

.luminos-kbd-color-dot-selected {{
    border-color: {TEXT_PRIMARY};
    box-shadow: 0 0 0 2px {ACCENT};
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class KeyboardPanel(Gtk.Box):
        """
        Keyboard settings panel.
        Shows: backlight brightness, auto-off, LED effect, color.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_KEYBOARD_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            self._selected_brightness = 2  # Medium default
            self._selected_effect = "Reactive"
            self._selected_color = "#0080FF"
            self._build()

        def _ensure_css(self):
            try:
                Gtk.StyleContext.add_provider_for_display(
                    self.get_display(), self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception:
                pass

        def _build(self):
            # Panel title
            title = Gtk.Label(label="Keyboard")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Backlight section ----
            self._build_backlight_section()

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Auto-off section ----
            self._build_auto_off_section()

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- Effect section ----
            self._build_effect_section()

            div3 = Gtk.Box()
            div3.add_css_class("luminos-section-divider")
            self.append(div3)

            # ---- Color section ----
            self._build_color_section()

        # -------------------------------------------------------------------
        # Backlight brightness — segmented control
        # -------------------------------------------------------------------

        def _build_backlight_section(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_4
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            text_box.set_hexpand(True)

            label = Gtk.Label(label="Backlight")
            label.add_css_class("luminos-setting-label")
            label.set_halign(Gtk.Align.START)
            text_box.append(label)

            sub = Gtk.Label(label="Keyboard LED brightness")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            row.append(text_box)

            # Segmented control: Off / Low / Medium / High
            seg = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            seg.add_css_class("luminos-kbd-segmented")

            self._brightness_buttons = []
            for opt in _get_brightness_options():
                btn = Gtk.Button(label=opt["label"])
                if opt["value"] == self._selected_brightness:
                    btn.add_css_class("luminos-kbd-segmented-active")
                btn.connect(
                    "clicked", self._on_brightness_clicked, opt["value"]
                )
                seg.append(btn)
                self._brightness_buttons.append((btn, opt["value"]))

            row.append(seg)
            self.append(row)

        def _on_brightness_clicked(self, _btn, value):
            self._selected_brightness = value
            for btn, val in self._brightness_buttons:
                if val == value:
                    btn.add_css_class("luminos-kbd-segmented-active")
                else:
                    btn.remove_css_class("luminos-kbd-segmented-active")

            try:
                from hardware.asus_controller import AsusController
                asus = AsusController()
                asus.set_keyboard_brightness(value)
            except ImportError:
                logger.debug("asus_controller not available")

        # -------------------------------------------------------------------
        # Auto-off — dropdown
        # -------------------------------------------------------------------

        def _build_auto_off_section(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_4
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            text_box.set_hexpand(True)

            label = Gtk.Label(label="Auto-off")
            label.add_css_class("luminos-setting-label")
            label.set_halign(Gtk.Align.START)
            text_box.append(label)

            sub = Gtk.Label(label="Turn off backlight when idle")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            row.append(text_box)

            options = _get_auto_off_options()
            dropdown = Gtk.DropDown.new_from_strings(options)
            dropdown.set_selected(0)  # 30s default
            dropdown.set_size_request(120, -1)
            row.append(dropdown)

            self.append(row)

        # -------------------------------------------------------------------
        # Effect — segmented control
        # -------------------------------------------------------------------

        def _build_effect_section(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_4
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            text_box.set_hexpand(True)

            label = Gtk.Label(label="Effect")
            label.add_css_class("luminos-setting-label")
            label.set_halign(Gtk.Align.START)
            text_box.append(label)

            row.append(text_box)

            seg = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            seg.add_css_class("luminos-kbd-segmented")

            self._effect_buttons = []
            for effect in _get_effect_options():
                btn = Gtk.Button(label=effect)
                if effect == self._selected_effect:
                    btn.add_css_class("luminos-kbd-segmented-active")
                btn.connect("clicked", self._on_effect_clicked, effect)
                seg.append(btn)
                self._effect_buttons.append((btn, effect))

            row.append(seg)
            self.append(row)

        def _on_effect_clicked(self, _btn, effect):
            self._selected_effect = effect
            for btn, eff in self._effect_buttons:
                if eff == effect:
                    btn.add_css_class("luminos-kbd-segmented-active")
                else:
                    btn.remove_css_class("luminos-kbd-segmented-active")

            effect_map = {
                "Solid": "static",
                "Breathe": "breathe",
                "Reactive": "reactive",
            }

            try:
                from hardware.asus_controller import AsusController
                asus = AsusController()
                asus.set_keyboard_effect(
                    effect_map.get(effect, "static"),
                    self._selected_color,
                )
            except ImportError:
                logger.debug("asus_controller not available")

        # -------------------------------------------------------------------
        # Color — dot picker (same as accent color picker)
        # -------------------------------------------------------------------

        def _build_color_section(self):
            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )

            label = Gtk.Label(label="Color")
            label.add_css_class("luminos-setting-label")
            label.set_halign(Gtk.Align.START)
            text_box.append(label)

            sub = Gtk.Label(label="Uses accent color by default")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            self.append(text_box)

            # Color dots
            color_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            color_row.set_margin_top(SPACE_3)

            self._color_buttons = []
            for preset in _get_color_presets():
                btn = Gtk.Button()
                btn.set_size_request(28, 28)
                btn.add_css_class("luminos-kbd-color-dot")

                # Set background color via inline CSS
                inline_css = Gtk.CssProvider()
                inline_css.load_from_string(
                    f"button {{ background-color: {preset['hex']}; }}"
                )
                btn.get_style_context().add_provider(
                    inline_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
                )

                if preset["hex"] == self._selected_color:
                    btn.add_css_class("luminos-kbd-color-dot-selected")

                btn.set_tooltip_text(preset["name"])
                btn.connect(
                    "clicked", self._on_color_clicked, preset["hex"]
                )
                color_row.append(btn)
                self._color_buttons.append((btn, preset["hex"]))

            self.append(color_row)

        def _on_color_clicked(self, _btn, hex_color):
            self._selected_color = hex_color
            for btn, hx in self._color_buttons:
                if hx == hex_color:
                    btn.add_css_class("luminos-kbd-color-dot-selected")
                else:
                    btn.remove_css_class("luminos-kbd-color-dot-selected")

            # Apply immediately
            effect_map = {
                "Solid": "static",
                "Breathe": "breathe",
                "Reactive": "reactive",
            }
            try:
                from hardware.asus_controller import AsusController
                asus = AsusController()
                asus.set_keyboard_effect(
                    effect_map.get(self._selected_effect, "static"),
                    hex_color,
                )
            except ImportError:
                logger.debug("asus_controller not available")

else:
    class KeyboardPanel:  # type: ignore[no-redef]
        pass
