"""
src/gui/settings/panels/display_panel.py
DisplayPanel — resolution, refresh rate, brightness, night light, external display.

Pure helpers:
    _get_scale_options()       → list[str]
    _get_upscale_modes()       → list[str]
    _parse_resolution(raw)     → tuple[int, int] | None
    _get_available_resolutions() → list[str]
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

from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_FULL,
    SETTINGS_PADDING,
)


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


def _get_available_resolutions() -> list:
    """Detect available resolutions from the current display."""
    try:
        import subprocess
        result = subprocess.run(
            ["hyprctl", "monitors", "-j"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            import json
            monitors = json.loads(result.stdout)
            if monitors:
                modes = monitors[0].get("availableModes", [])
                seen = set()
                resolutions = []
                for m in modes:
                    res = m.split("@")[0] if "@" in m else m
                    if res not in seen:
                        seen.add(res)
                        resolutions.append(res)
                return resolutions if resolutions else ["2560x1600", "1920x1200", "1920x1080"]
    except Exception:
        pass
    return ["2560x1600", "1920x1200", "1920x1080", "1680x1050", "1280x800"]


def _get_external_display_status() -> str:
    """Check if an external display is connected."""
    try:
        import subprocess
        result = subprocess.run(
            ["hyprctl", "monitors", "-j"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            import json
            monitors = json.loads(result.stdout)
            if len(monitors) > 1:
                ext = monitors[1]
                return ext.get("name", "External display")
    except Exception:
        pass
    return ""


# ===========================================================================
# CSS
# ===========================================================================

_DISPLAY_CSS = f"""
.luminos-dropdown {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_MD}px;
    color: {TEXT_PRIMARY};
    min-height: 36px;
    padding: 0 {SPACE_3}px;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class DisplayPanel(Gtk.Box):
        """
        Display settings panel.
        Controls: resolution, refresh rate, brightness, night light, external display.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_DISPLAY_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

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
            title = Gtk.Label(label="Display")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Resolution ----
            self._build_resolution_section()

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Refresh Rate ----
            self._build_refresh_section()

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- Brightness ----
            self._build_brightness_section()

            div3 = Gtk.Box()
            div3.add_css_class("luminos-section-divider")
            self.append(div3)

            # ---- Night Light ----
            self._build_night_light_section()

            div4 = Gtk.Box()
            div4.add_css_class("luminos-section-divider")
            self.append(div4)

            # ---- External Display ----
            self._build_external_display_section()

        def _build_resolution_section(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            lbl = Gtk.Label(label="Resolution")
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            row.append(lbl)

            resolutions = _get_available_resolutions()
            self._res_combo = Gtk.DropDown.new_from_strings(resolutions)
            self._res_combo.set_selected(0)
            self._res_combo.add_css_class("luminos-dropdown")
            self._res_combo.connect("notify::selected", self._on_resolution_changed)
            row.append(self._res_combo)

            self.append(row)

        def _build_refresh_section(self):
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl = Gtk.Label(label="Refresh Rate")
            lbl.add_css_class("luminos-section-title")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label="Auto switches to 120Hz for games and video")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)
            self.append(text_box)

            seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            seg.add_css_class("luminos-segmented")
            seg.set_halign(Gtk.Align.START)
            seg.set_margin_top(SPACE_3)

            self._refresh_btns = {}
            options = [
                ("auto", "Auto (recommended)"),
                ("60hz", "Always 60Hz"),
                ("120hz", "Always 120Hz"),
            ]
            for key, label in options:
                btn = Gtk.Button(label=label)
                self._refresh_btns[key] = btn
                if key == "auto":
                    btn.add_css_class("luminos-segmented-active")
                btn.connect("clicked", self._on_refresh_click, key)
                seg.append(btn)

            self.append(seg)

        def _build_brightness_section(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            lbl = Gtk.Label(label="Brightness")
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            row.append(lbl)

            slider_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            slider_box.set_hexpand(True)

            self._bright_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            self._bright_slider.set_hexpand(True)
            self._bright_slider.set_draw_value(False)
            self._bright_slider.add_css_class("luminos-slider")
            self._bright_slider.connect("value-changed", self._on_bright_changed)
            slider_box.append(self._bright_slider)

            self._bright_val = Gtk.Label(label="--%")
            self._bright_val.add_css_class("luminos-text-primary")
            slider_box.append(self._bright_val)

            row.append(slider_box)
            self.append(row)

            self._load_brightness()

        def _build_night_light_section(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_box.set_hexpand(True)
            text_box.set_valign(Gtk.Align.CENTER)

            lbl = Gtk.Label(label="Night Light")
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label="Reduces blue light in the evening")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            row.append(text_box)

            self._night_switch = Gtk.Switch()
            self._night_switch.set_active(False)
            self._night_switch.add_css_class("luminos-switch")
            self._night_switch.set_valign(Gtk.Align.CENTER)
            self._night_switch.connect("state-set", self._on_night_toggle)
            row.append(self._night_switch)

            self.append(row)

            # Time range row — hidden by default
            self._time_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_4
            )
            self._time_row.set_margin_top(SPACE_3)
            self._time_row.set_margin_start(SPACE_4)
            self._time_row.set_visible(False)

            from_lbl = Gtk.Label(label="From")
            from_lbl.add_css_class("luminos-setting-sublabel")
            self._time_row.append(from_lbl)

            self._from_entry = Gtk.Entry()
            self._from_entry.set_text("20:00")
            self._from_entry.set_max_width_chars(5)
            self._time_row.append(self._from_entry)

            to_lbl = Gtk.Label(label="To")
            to_lbl.add_css_class("luminos-setting-sublabel")
            self._time_row.append(to_lbl)

            self._to_entry = Gtk.Entry()
            self._to_entry.set_text("06:00")
            self._to_entry.set_max_width_chars(5)
            self._time_row.append(self._to_entry)

            self.append(self._time_row)

        def _build_external_display_section(self):
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl = Gtk.Label(label="External Display")
            lbl.add_css_class("luminos-section-title")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label="Automatically configured when connected")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)
            self.append(text_box)

            status = _get_external_display_status()
            status_text = status if status else "No display connected"
            status_lbl = Gtk.Label(label=status_text)
            status_lbl.add_css_class(
                "luminos-text-primary" if status else "luminos-text-secondary"
            )
            status_lbl.set_halign(Gtk.Align.START)
            status_lbl.set_margin_top(SPACE_3)
            self.append(status_lbl)

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

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

        def _on_resolution_changed(self, combo, _param):
            resolutions = _get_available_resolutions()
            idx = combo.get_selected()
            if 0 <= idx < len(resolutions):
                logger.debug(f"Resolution changed to {resolutions[idx]}")

        def _on_refresh_click(self, btn, key):
            for k, b in self._refresh_btns.items():
                if k == key:
                    b.add_css_class("luminos-segmented-active")
                else:
                    b.remove_css_class("luminos-segmented-active")
            logger.debug(f"Refresh rate: {key}")

        def _on_bright_changed(self, slider):
            pct = int(slider.get_value())
            self._bright_val.set_text(f"{pct}%")
            try:
                from gui.quick_settings.brightness_ctrl import set_brightness
                set_brightness(pct)
            except Exception as e:
                logger.debug(f"Brightness set error: {e}")

        def _on_night_toggle(self, switch, state):
            self._time_row.set_visible(state)
            return False

else:
    class DisplayPanel:  # type: ignore[no-redef]
        pass
