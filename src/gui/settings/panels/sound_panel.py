"""
src/gui/settings/panels/sound_panel.py
SoundPanel — output/input device selection, volume, system sounds toggle.

Pure helpers:
    _get_audio_devices(direction) → list[dict]
    _get_volume_info()            → dict
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.sound")

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
    BORDER, BORDER_SUBTLE,
    FONT_FAMILY, FONT_H3, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD,
    SETTINGS_PADDING,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_audio_devices(direction: str) -> list:
    """
    List audio devices for 'output' or 'input'.

    Returns:
        List of dicts with keys: name, description, active.
    """
    cmd_map = {"output": "list-sinks", "input": "list-sources"}
    cmd = cmd_map.get(direction, "list-sinks")
    try:
        import subprocess
        result = subprocess.run(
            ["pactl", cmd, "--format=json"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            devices = []
            for d in data:
                devices.append({
                    "name": d.get("name", ""),
                    "description": d.get("description", d.get("name", "Unknown")),
                    "active": d.get("state", "") == "RUNNING",
                })
            return devices
    except Exception:
        pass
    return [{"name": "default", "description": "Default Device", "active": True}]


def _get_volume_info() -> dict:
    """Return current volume percent and mute state."""
    try:
        from gui.common.subprocess_helpers import get_volume
        return get_volume()
    except Exception:
        return {"percent": 50, "muted": False}


# ===========================================================================
# CSS
# ===========================================================================

_SOUND_CSS = f"""
.luminos-device-row {{
    min-height: 48px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-device-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-device-active {{
    background-color: {ACCENT_SUBTLE};
}}

.luminos-input-meter {{
    background-color: rgba(255, 255, 255, 0.12);
    min-height: 4px;
    border-radius: 2px;
}}

.luminos-input-meter-fill {{
    background-color: {ACCENT};
    min-height: 4px;
    border-radius: 2px;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class SoundPanel(Gtk.Box):
        """Sound settings: output/input device selection, volume, system sounds."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            self._selected_output = None
            self._selected_input = None

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_SOUND_CSS)
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
            title = Gtk.Label(label="Sound")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Output section ----
            self._build_output_section()

            div = Gtk.Box()
            div.add_css_class("luminos-section-divider")
            self.append(div)

            # ---- Input section ----
            self._build_input_section()

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- System sounds ----
            self._build_system_sounds()

        def _build_output_section(self):
            sec_title = Gtk.Label(label="Output")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            # Device list
            self._output_list = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            self._output_list.set_margin_bottom(SPACE_4)
            self.append(self._output_list)
            self._refresh_output_devices()

            # Volume slider
            vol_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            vol_row.set_hexpand(True)

            self._output_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            self._output_slider.set_hexpand(True)
            self._output_slider.set_draw_value(False)
            self._output_slider.add_css_class("luminos-slider")

            vol = _get_volume_info()
            self._output_slider.set_value(vol.get("percent", 50))
            self._output_slider.connect("value-changed", self._on_volume_changed)
            vol_row.append(self._output_slider)

            self._vol_label = Gtk.Label(label=f"{vol.get('percent', 50)}%")
            self._vol_label.add_css_class("luminos-text-primary")
            vol_row.append(self._vol_label)

            self.append(vol_row)

        def _build_input_section(self):
            sec_title = Gtk.Label(label="Input")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            # Device list
            self._input_list = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            self._input_list.set_margin_bottom(SPACE_4)
            self.append(self._input_list)
            self._refresh_input_devices()

            # Input level meter
            meter_label = Gtk.Label(label="Input Level")
            meter_label.add_css_class("luminos-setting-sublabel")
            meter_label.set_halign(Gtk.Align.START)
            self.append(meter_label)

            self._input_meter = Gtk.LevelBar()
            self._input_meter.set_min_value(0)
            self._input_meter.set_max_value(100)
            self._input_meter.set_value(0)
            self._input_meter.add_css_class("luminos-input-meter")
            self._input_meter.set_margin_top(SPACE_2)
            self._input_meter.set_margin_bottom(SPACE_4)
            self.append(self._input_meter)

            # Mute toggle
            mute_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            mute_row.add_css_class("luminos-setting-row")
            mute_row.set_hexpand(True)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_box.set_hexpand(True)
            text_box.set_valign(Gtk.Align.CENTER)
            lbl = Gtk.Label(label="Mute Microphone")
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)
            mute_row.append(text_box)

            self._mute_switch = Gtk.Switch()
            self._mute_switch.set_active(False)
            self._mute_switch.add_css_class("luminos-switch")
            self._mute_switch.set_valign(Gtk.Align.CENTER)
            mute_row.append(self._mute_switch)

            self.append(mute_row)

        def _build_system_sounds(self):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            row.add_css_class("luminos-setting-row")
            row.set_hexpand(True)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_box.set_hexpand(True)
            text_box.set_valign(Gtk.Align.CENTER)

            lbl = Gtk.Label(label="System Sounds")
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label="UI feedback sounds")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            row.append(text_box)

            switch = Gtk.Switch()
            switch.set_active(True)
            switch.add_css_class("luminos-switch")
            switch.set_valign(Gtk.Align.CENTER)
            row.append(switch)

            self.append(row)

        def _refresh_output_devices(self):
            while (child := self._output_list.get_first_child()):
                self._output_list.remove(child)
            devices = _get_audio_devices("output")
            for dev in devices:
                row = self._make_device_row(dev, "output")
                self._output_list.append(row)

        def _refresh_input_devices(self):
            while (child := self._input_list.get_first_child()):
                self._input_list.remove(child)
            devices = _get_audio_devices("input")
            for dev in devices:
                row = self._make_device_row(dev, "input")
                self._input_list.append(row)

        def _make_device_row(self, dev: dict, direction: str) -> Gtk.Box:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            row.add_css_class("luminos-device-row")

            # Radio indicator
            radio = Gtk.CheckButton()
            selected = (
                (direction == "output" and dev["name"] == self._selected_output) or
                (direction == "input" and dev["name"] == self._selected_input) or
                dev.get("active", False)
            )
            radio.set_active(selected)
            if selected:
                row.add_css_class("luminos-device-active")
                if direction == "output":
                    self._selected_output = dev["name"]
                else:
                    self._selected_input = dev["name"]
            row.append(radio)

            lbl = Gtk.Label(label=dev["description"])
            lbl.add_css_class("luminos-setting-label")
            lbl.set_halign(Gtk.Align.START)
            row.append(lbl)

            return row

        def _on_volume_changed(self, slider):
            pct = int(slider.get_value())
            self._vol_label.set_text(f"{pct}%")
            try:
                from gui.common.subprocess_helpers import set_volume
                set_volume(pct)
            except Exception as e:
                logger.debug(f"Volume set error: {e}")

else:
    class SoundPanel:  # type: ignore[no-redef]
        pass
