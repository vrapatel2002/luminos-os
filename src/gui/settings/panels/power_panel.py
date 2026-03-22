"""
src/gui/settings/panels/power_panel.py
PowerPanel — power mode cards, live status, sleep settings, battery thresholds.

Pure helpers:
    _get_power_cards()         → list[dict] with id/label/description/icon
    _get_sleep_options()       → list[str]
    _format_temp(celsius)      → str like "62 °C"
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.power")

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

from gui.common.socket_client import DaemonClient


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_power_cards() -> list:
    """
    Return the four power mode card definitions.

    Returns:
        List of dicts with keys: id, label, description, icon.
    """
    return [
        {
            "id":          "quiet",
            "label":       "Quiet",
            "description": "Silent — typing, music, calls",
            "icon":        "audio-volume-muted",
        },
        {
            "id":          "auto",
            "label":       "Auto",
            "description": "Smart automatic switching",
            "icon":        "system-run",
        },
        {
            "id":          "balanced",
            "label":       "Balanced",
            "description": "Performance + efficiency",
            "icon":        "battery-good",
        },
        {
            "id":          "max",
            "label":       "Max",
            "description": "Maximum performance (fans on)",
            "icon":        "utilities-system-monitor",
        },
    ]


def _get_sleep_options() -> list:
    """Return available sleep/suspend delay options."""
    return ["Never", "5 minutes", "10 minutes", "15 minutes", "30 minutes", "1 hour"]


def _format_temp(celsius: float) -> str:
    """
    Format a temperature value for display.

    Args:
        celsius: Temperature in °C.

    Returns:
        Formatted string like "62 °C".
    """
    return f"{celsius:.0f} °C"


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class PowerPanel(Gtk.Box):
        """
        Power settings panel.

        Controls: 4 mode cards (Quiet/Auto/Balanced/Max) → daemon power_set,
        live status (CPU/GPU temp, battery), sleep settings, battery thresholds.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            self.set_margin_top(24)
            self.set_margin_bottom(24)
            self.set_margin_start(32)
            self.set_margin_end(32)
            self._client = DaemonClient()
            self._active_mode = "auto"
            self._build()
            # Refresh live status every 3 s
            GLib.timeout_add_seconds(3, self._refresh_status)
            self._refresh_status()

        def _build(self):
            # ---- Power mode cards ----
            mode_lbl = Gtk.Label(label="Power Mode")
            mode_lbl.add_css_class("luminos-settings-section-title")
            mode_lbl.set_halign(Gtk.Align.START)
            self.append(mode_lbl)

            cards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self._mode_btns: dict[str, Gtk.Button] = {}
            for card in _get_power_cards():
                btn = self._make_mode_card(card)
                cards_box.append(btn)
                self._mode_btns[card["id"]] = btn
            self.append(cards_box)

            self.append(Gtk.Separator())

            # ---- Live status ----
            status_lbl = Gtk.Label(label="System Status")
            status_lbl.add_css_class("luminos-settings-section-title")
            status_lbl.set_halign(Gtk.Align.START)
            self.append(status_lbl)

            status_grid = Gtk.Grid()
            status_grid.set_row_spacing(6)
            status_grid.set_column_spacing(24)

            self._cpu_temp_lbl  = self._stat_row(status_grid, 0, "CPU Temp")
            self._gpu_temp_lbl  = self._stat_row(status_grid, 1, "GPU Temp")
            self._battery_lbl   = self._stat_row(status_grid, 2, "Battery")
            self.append(status_grid)

            self.append(Gtk.Separator())

            # ---- Sleep settings ----
            sleep_lbl = Gtk.Label(label="Sleep After Inactivity")
            sleep_lbl.add_css_class("luminos-settings-section-title")
            sleep_lbl.set_halign(Gtk.Align.START)
            self.append(sleep_lbl)

            self._sleep_combo = Gtk.DropDown.new_from_strings(_get_sleep_options())
            self._sleep_combo.set_selected(2)  # default: 10 minutes
            self.append(self._sleep_combo)

            self.append(Gtk.Separator())

            # ---- Battery threshold ----
            thresh_lbl = Gtk.Label(label="Charge Limit")
            thresh_lbl.add_css_class("luminos-settings-section-title")
            thresh_lbl.set_halign(Gtk.Align.START)
            self.append(thresh_lbl)

            thresh_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            self._thresh_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 60, 100, 5
            )
            self._thresh_slider.set_value(100)
            self._thresh_slider.set_hexpand(True)
            self._thresh_slider.set_draw_value(True)
            thresh_row.append(self._thresh_slider)
            self.append(thresh_row)

        def _make_mode_card(self, card: dict) -> Gtk.Button:
            btn = Gtk.Button()
            btn.add_css_class("luminos-power-card")

            inner = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            inner.set_margin_top(12)
            inner.set_margin_bottom(12)
            inner.set_margin_start(12)
            inner.set_margin_end(12)

            icon = Gtk.Image.new_from_icon_name(card["icon"])
            icon.set_pixel_size(24)
            inner.append(icon)

            name_lbl = Gtk.Label(label=card["label"])
            name_lbl.add_css_class("luminos-power-card-name")
            inner.append(name_lbl)

            desc_lbl = Gtk.Label(label=card["description"])
            desc_lbl.add_css_class("luminos-qs-dim")
            desc_lbl.set_wrap(True)
            desc_lbl.set_max_width_chars(12)
            inner.append(desc_lbl)

            btn.set_child(inner)
            btn.connect("clicked", self._on_mode_card_clicked, card["id"])
            return btn

        def _stat_row(self, grid: Gtk.Grid, row: int, label: str) -> Gtk.Label:
            key = Gtk.Label(label=label)
            key.set_halign(Gtk.Align.START)
            key.add_css_class("luminos-qs-dim")
            grid.attach(key, 0, row, 1, 1)
            val = Gtk.Label(label="—")
            val.set_halign(Gtk.Align.START)
            grid.attach(val, 1, row, 1, 1)
            return val

        def _on_mode_card_clicked(self, _btn, mode_id: str):
            try:
                self._client.send({"type": "power_set", "mode": mode_id})
            except Exception as e:
                logger.debug(f"power_set error: {e}")
            self._active_mode = mode_id
            self._update_card_styles()

        def _update_card_styles(self):
            for mode_id, btn in self._mode_btns.items():
                if mode_id == self._active_mode:
                    btn.add_css_class("luminos-btn-accent")
                else:
                    btn.remove_css_class("luminos-btn-accent")

        def _refresh_status(self) -> bool:
            try:
                from power_manager import get_cpu_temp, get_gpu_temp, get_ac_status
                cpu = get_cpu_temp()
                gpu = get_gpu_temp()
                ac  = get_ac_status()
                self._cpu_temp_lbl.set_text(_format_temp(cpu))
                self._gpu_temp_lbl.set_text(
                    _format_temp(gpu) if gpu > 0 else "N/A"
                )
                pct = ac.get("battery_percent", 0)
                plug = "⚡" if ac.get("plugged_in") else "🔋"
                self._battery_lbl.set_text(f"{plug} {pct}%")
            except Exception as e:
                logger.debug(f"Status refresh error: {e}")
            return GLib.SOURCE_CONTINUE

else:
    class PowerPanel:  # type: ignore[no-redef]
        pass
