"""
src/gui/settings/panels/display_panel.py
DisplayPanel — brightness, resolution, scaling, upscaling, night light.

Pure helpers:
    _get_scale_options()       → list[str]
    _get_upscale_modes()       → list[str]
    _parse_resolution(raw)     → tuple[int, int] | None
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.display")

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


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_scale_options() -> list:
    """Return available display scaling options."""
    return ["100%", "125%", "150%", "200%"]


def _get_upscale_modes() -> list:
    """Return available iGPU upscaling modes."""
    return ["None", "Bilinear", "FSR 1.0", "NIS"]


def _parse_resolution(raw: str):
    """
    Parse a resolution string like '1920x1080' into (width, height).

    Args:
        raw: String of the form 'WxH'.

    Returns:
        Tuple (width, height) as ints, or None if unparseable.
    """
    try:
        parts = raw.strip().lower().split("x")
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
    except (ValueError, AttributeError):
        pass
    return None


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class DisplayPanel(Gtk.Box):
        """
        Display settings panel.

        Controls: brightness slider, resolution/refresh rate, scaling,
        upscaling mode, night light placeholder.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            self.set_margin_top(24)
            self.set_margin_bottom(24)
            self.set_margin_start(32)
            self.set_margin_end(32)
            self._build()

        def _build(self):
            # ---- Brightness ----
            bright_lbl = Gtk.Label(label="Brightness")
            bright_lbl.add_css_class("luminos-settings-section-title")
            bright_lbl.set_halign(Gtk.Align.START)
            self.append(bright_lbl)

            bright_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            bright_row.set_hexpand(True)

            self._bright_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 5, 100, 1
            )
            self._bright_slider.set_hexpand(True)
            self._bright_slider.set_draw_value(False)
            self._bright_slider.connect("value-changed", self._on_bright_changed)
            bright_row.append(self._bright_slider)

            self._bright_val = Gtk.Label(label="--")
            self._bright_val.set_width_chars(5)
            bright_row.append(self._bright_val)
            self.append(bright_row)

            self._load_brightness()

            self.append(Gtk.Separator())

            # ---- Scaling ----
            scale_lbl = Gtk.Label(label="Display Scaling")
            scale_lbl.add_css_class("luminos-settings-section-title")
            scale_lbl.set_halign(Gtk.Align.START)
            self.append(scale_lbl)

            scale_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self._scale_combo = Gtk.DropDown.new_from_strings(_get_scale_options())
            self._scale_combo.set_selected(0)
            self._scale_combo.connect("notify::selected", self._on_scale_changed)
            scale_row.append(self._scale_combo)
            self.append(scale_row)

            self.append(Gtk.Separator())

            # ---- Upscaling mode ----
            up_lbl = Gtk.Label(label="iGPU Upscaling")
            up_lbl.add_css_class("luminos-settings-section-title")
            up_lbl.set_halign(Gtk.Align.START)
            self.append(up_lbl)

            up_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self._up_combo = Gtk.DropDown.new_from_strings(_get_upscale_modes())
            self._up_combo.set_selected(0)
            self._up_combo.connect("notify::selected", self._on_upscale_changed)
            up_row.append(self._up_combo)
            self.append(up_row)

            self.append(Gtk.Separator())

            # ---- Night light (placeholder) ----
            night_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            night_row.set_hexpand(True)
            night_lbl = Gtk.Label(label="Night Light")
            night_lbl.set_hexpand(True)
            night_lbl.set_halign(Gtk.Align.START)
            self._night_switch = Gtk.Switch()
            self._night_switch.set_active(False)
            self._night_switch.set_sensitive(False)
            self._night_switch.set_tooltip_text("Coming soon")
            night_row.append(night_lbl)
            night_row.append(self._night_switch)
            self.append(night_row)

        def _load_brightness(self):
            try:
                from gui.quick_settings.brightness_ctrl import get_brightness
                result = get_brightness()
                if result.get("available"):
                    pct = result["percent"]
                    self._bright_slider.set_value(pct)
                    self._bright_val.set_text(f"{pct}%")
                    return
            except Exception:
                pass
            self._bright_slider.set_sensitive(False)
            self._bright_val.set_text("N/A")

        def _on_bright_changed(self, slider):
            pct = int(slider.get_value())
            self._bright_val.set_text(f"{pct}%")
            try:
                from gui.quick_settings.brightness_ctrl import set_brightness
                set_brightness(pct)
            except Exception as e:
                logger.debug(f"Brightness set error: {e}")

        def _on_scale_changed(self, combo, _param):
            opts = _get_scale_options()
            idx = combo.get_selected()
            if 0 <= idx < len(opts):
                logger.debug(f"Scale changed to {opts[idx]}")

        def _on_upscale_changed(self, combo, _param):
            modes = _get_upscale_modes()
            idx = combo.get_selected()
            if 0 <= idx < len(modes):
                mode_name = modes[idx]
                logger.debug(f"Upscale mode: {mode_name}")
                try:
                    from compositor import set_upscale_mode  # type: ignore
                    set_upscale_mode(mode_name)
                except Exception:
                    pass

else:
    class DisplayPanel:  # type: ignore[no-redef]
        pass
