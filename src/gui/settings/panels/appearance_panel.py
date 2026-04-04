"""
src/gui/settings/panels/appearance_panel.py
AppearancePanel — theme, accent color, font size, animations.

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
from gui.theme.luminos_theme import (
    BG_BASE, BG_SURFACE, BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE, ACCENT_HOVER, ACCENT_PRESSED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    COLOR_SUCCESS,
    FONT_FAMILY, FONT_H2, FONT_H3, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_FULL, RADIUS_DEFAULT,
    SETTINGS_PADDING,
)


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
    if mode_str is True or cleaned == "true":
        return "dark"
    if mode_str is False or cleaned == "false":
        return "light"
    return "auto"


def _get_accent_presets() -> list:
    """Return the 8 built-in accent color presets."""
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
# CSS — all from luminos_theme
# ===========================================================================

_APPEARANCE_CSS = f"""
.luminos-segmented {{
    background-color: {BG_ELEVATED};
    border-radius: {RADIUS_FULL}px;
    padding: 2px;
}}

.luminos-segmented button {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
    color: {TEXT_SECONDARY};
    background: transparent;
    border: none;
    border-radius: {RADIUS_FULL}px;
    padding: {SPACE_2}px {SPACE_4}px;
    min-height: 32px;
}}

.luminos-segmented button:hover {{
    color: {TEXT_PRIMARY};
    background-color: {BG_OVERLAY};
}}

.luminos-segmented-active {{
    background-color: {ACCENT} !important;
    color: {TEXT_PRIMARY} !important;
}}

.luminos-accent-circle {{
    border-radius: {RADIUS_FULL}px;
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    border: 2px solid transparent;
}}

.luminos-accent-circle-selected {{
    border-color: {TEXT_PRIMARY};
}}

.luminos-accent-add {{
    border-radius: {RADIUS_FULL}px;
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    background-color: {BG_ELEVATED};
    border: 1px dashed {BORDER};
    color: {TEXT_SECONDARY};
    font-size: 16px;
}}

.luminos-slider trough {{
    background-color: rgba(255, 255, 255, 0.12);
    min-height: 4px;
    border-radius: 2px;
}}

.luminos-slider trough highlight {{
    background-color: {ACCENT};
    border-radius: 2px;
}}

.luminos-slider slider {{
    background-color: {TEXT_PRIMARY};
    min-width: 16px;
    min-height: 16px;
    border-radius: {RADIUS_FULL}px;
}}

.luminos-switch {{
    font-size: 0;
}}

.luminos-switch:checked {{
    background-color: {ACCENT};
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class AppearancePanel(Gtk.Box):
        """
        Appearance settings panel.
        Controls: theme segmented, accent color circles, font slider,
        animations toggle, reduce motion toggle.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            # Load CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_APPEARANCE_CSS)
            # Will be applied when widget is realized
            self._css_provider = css_provider

            self._selected_accent = "#0080FF"
            self._build()

        def _ensure_css(self):
            try:
                display = self.get_display()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display, self._css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
            except Exception:
                pass

        def _build(self):
            self.connect("realize", lambda w: self._ensure_css())

            # Panel title
            title = Gtk.Label(label="Appearance")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Theme section ----
            self._build_theme_section()
            self.append(self._make_divider())

            # ---- Accent color section ----
            self._build_accent_section()
            self.append(self._make_divider())

            # ---- Font size section ----
            self._build_font_section()
            self.append(self._make_divider())

            # ---- Animations section ----
            self._build_animations_section()

        # -------------------------------------------------------------------
        # Theme
        # -------------------------------------------------------------------

        def _build_theme_section(self):
            row = self._make_setting_row(
                "Theme", None,
            )
            self.append(row)

            current = _get_theme_mode(str(mode.get_mode()))
            seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            seg.add_css_class("luminos-segmented")
            seg.set_halign(Gtk.Align.START)
            seg.set_margin_top(SPACE_2)

            self._theme_btns = {}
            for label in ("Dark", "Light", "Auto"):
                btn = Gtk.Button(label=label)
                key = label.lower()
                self._theme_btns[key] = btn
                if key == current:
                    btn.add_css_class("luminos-segmented-active")
                btn.connect("clicked", self._on_theme_click, key)
                seg.append(btn)

            self.append(seg)

        def _on_theme_click(self, btn, key):
            for k, b in self._theme_btns.items():
                if k == key:
                    b.add_css_class("luminos-segmented-active")
                else:
                    b.remove_css_class("luminos-segmented-active")
            if key == "dark":
                mode.set_manual(True)
            elif key == "light":
                mode.set_manual(False)
            else:
                mode.set_auto()

        # -------------------------------------------------------------------
        # Accent color
        # -------------------------------------------------------------------

        def _build_accent_section(self):
            row = self._make_setting_row(
                "Accent Color",
                "Used across the entire interface",
            )
            self.append(row)

            color_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_2
            )
            color_box.set_margin_top(SPACE_2)
            color_box.set_halign(Gtk.Align.START)

            self._accent_btns = []
            for preset in _get_accent_presets():
                btn = Gtk.Button()
                btn.set_size_request(28, 28)
                btn.add_css_class("luminos-accent-circle")
                btn.set_tooltip_text(preset["name"])
                btn._hex = preset["hex"]

                # Apply color via inline CSS
                provider = Gtk.CssProvider()
                provider.load_from_string(
                    f".accent-{preset['hex'][1:]} {{ background-color: {preset['hex']}; }}"
                )
                btn.add_css_class(f"accent-{preset['hex'][1:]}")
                btn._provider = provider

                if preset["hex"].upper() == self._selected_accent.upper():
                    btn.add_css_class("luminos-accent-circle-selected")

                btn.connect("clicked", self._on_accent_click)
                btn.connect("realize", self._on_accent_realize)
                color_box.append(btn)
                self._accent_btns.append(btn)

            # "+" custom button
            add_btn = Gtk.Button(label="+")
            add_btn.add_css_class("luminos-accent-add")
            add_btn.set_tooltip_text("Custom color")
            add_btn.connect("clicked", self._on_accent_custom)
            color_box.append(add_btn)

            self.append(color_box)

        def _on_accent_realize(self, btn):
            try:
                display = btn.get_display()
                if display and hasattr(btn, '_provider'):
                    Gtk.StyleContext.add_provider_for_display(
                        display, btn._provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
            except Exception:
                pass

        def _on_accent_click(self, btn):
            hex_color = getattr(btn, "_hex", None)
            if not hex_color:
                return
            self._selected_accent = hex_color
            for b in self._accent_btns:
                b.remove_css_class("luminos-accent-circle-selected")
            btn.add_css_class("luminos-accent-circle-selected")
            logger.debug(f"Accent color selected: {hex_color}")

        def _on_accent_custom(self, _btn):
            dialog = Gtk.ColorChooserDialog(
                title="Choose Accent Color",
                transient_for=self.get_root(),
            )
            dialog.connect("response", self._on_color_response)
            dialog.present()

        def _on_color_response(self, dialog, response):
            if response == Gtk.ResponseType.OK:
                rgba = dialog.get_rgba()
                r, g, b = int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
                hex_color = f"#{r:02X}{g:02X}{b:02X}"
                self._selected_accent = hex_color
                for btn in self._accent_btns:
                    btn.remove_css_class("luminos-accent-circle-selected")
                logger.debug(f"Custom accent color: {hex_color}")
            dialog.close()

        # -------------------------------------------------------------------
        # Font size
        # -------------------------------------------------------------------

        def _build_font_section(self):
            row = self._make_setting_row(
                "Font Size",
                "Affects text across the interface",
            )
            self.append(row)

            slider_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            slider_row.set_margin_top(SPACE_2)
            slider_row.set_hexpand(True)

            self._font_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 10, 16, 1
            )
            self._font_slider.set_value(13)
            self._font_slider.set_hexpand(True)
            self._font_slider.set_draw_value(False)
            self._font_slider.add_css_class("luminos-slider")
            self._font_slider.connect("value-changed", self._on_font_changed)
            slider_row.append(self._font_slider)

            self._font_val = Gtk.Label(label="13")
            self._font_val.add_css_class("luminos-text-primary")
            slider_row.append(self._font_val)

            self.append(slider_row)

        def _on_font_changed(self, slider):
            size = int(slider.get_value())
            self._font_val.set_text(str(size))
            logger.debug(f"Font size changed to {size}")

        # -------------------------------------------------------------------
        # Animations
        # -------------------------------------------------------------------

        def _build_animations_section(self):
            # Enable Animations
            anim_row = self._make_toggle_row(
                "Enable Animations",
                "Smooth transitions and motion effects",
                active=True,
            )
            self._anim_switch = anim_row._switch
            self._anim_switch.connect("state-set", self._on_anim_toggle)
            self.append(anim_row)

            # Reduce Motion — only visible when animations are enabled
            self._reduce_row = self._make_toggle_row(
                "Reduce Motion",
                "Minimizes animation for accessibility",
                active=False,
            )
            self._reduce_switch = self._reduce_row._switch
            self.append(self._reduce_row)

        def _on_anim_toggle(self, switch, state):
            self._reduce_row.set_visible(state)
            logger.debug(f"Animations {'on' if state else 'off'}")
            return False

        # -------------------------------------------------------------------
        # Shared builders
        # -------------------------------------------------------------------

        def _make_setting_row(self, label: str, sublabel: str | None) -> Gtk.Box:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("luminos-section-title")
            lbl.set_halign(Gtk.Align.START)
            box.append(lbl)
            if sublabel:
                sub = Gtk.Label(label=sublabel)
                sub.add_css_class("luminos-setting-sublabel")
                sub.set_halign(Gtk.Align.START)
                box.append(sub)
            return box

        def _make_toggle_row(self, label: str, sublabel: str,
                             active: bool = False) -> Gtk.Box:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            text_box.set_hexpand(True)
            text_box.set_valign(Gtk.Align.CENTER)

            lbl = Gtk.Label(label=label)
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label=sublabel)
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            row.append(text_box)

            switch = Gtk.Switch()
            switch.set_active(active)
            switch.add_css_class("luminos-switch")
            switch.set_valign(Gtk.Align.CENTER)
            row.append(switch)

            row._switch = switch
            return row

        def _make_divider(self) -> Gtk.Box:
            div = Gtk.Box()
            div.add_css_class("luminos-section-divider")
            return div

    # -------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------

else:
    class AppearancePanel:  # type: ignore[no-redef]
        pass
