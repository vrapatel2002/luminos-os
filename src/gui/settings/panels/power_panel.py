"""
src/gui/settings/panels/power_panel.py
PowerPanel — current mode status card (read-only), charge limit, screen timeout, suspend.

Pure helpers:
    _get_power_cards()         → list[dict] with id/label/description/icon
    _get_sleep_options()       → list[str]
    _format_temp(celsius)      → str like "62 °C"
    _get_timeout_options()     → list[str]
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
from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER, BORDER_SUBTLE,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL, FONT_H3,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_DEFAULT, RADIUS_FULL,
    SETTINGS_PADDING,
)


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


def _get_timeout_options() -> list:
    """Return screen timeout / suspend options."""
    return ["1 min", "2 min", "5 min", "10 min", "Never"]


# ===========================================================================
# CSS
# ===========================================================================

_POWER_CSS = f"""
.luminos-power-status-card {{
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACE_6}px;
    margin-bottom: {SPACE_6}px;
}}

.luminos-power-card-battery {{
    background-color: {BG_ELEVATED};
}}

.luminos-power-card-performance {{
    background-color: {ACCENT_SUBTLE};
}}

.luminos-power-card-title {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_H3}px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
}}

.luminos-power-card-sub {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
    margin-top: 4px;
}}

.luminos-charge-note {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 12px;
    color: {TEXT_SECONDARY};
    margin-top: {SPACE_2}px;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class PowerPanel(Gtk.Box):
        """
        Power settings panel.
        Read-only current mode status, charge limit, screen timeout, suspend.
        NOTE: No manual power mode switcher per spec.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)
            self._client = DaemonClient()

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_POWER_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            self._build()
            GLib.timeout_add_seconds(5, self._refresh_status)
            self._refresh_status()

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
            title = Gtk.Label(label="Power")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Current mode status card (READ ONLY) ----
            self._status_card = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            self._status_card.add_css_class("luminos-power-status-card")
            self._status_card.add_css_class("luminos-power-card-battery")

            self._status_title = Gtk.Label(label="Battery Mode")
            self._status_title.add_css_class("luminos-power-card-title")
            self._status_title.set_halign(Gtk.Align.START)
            self._status_card.append(self._status_title)

            self._status_sub = Gtk.Label(label="Running on battery")
            self._status_sub.add_css_class("luminos-power-card-sub")
            self._status_sub.set_halign(Gtk.Align.START)
            self._status_card.append(self._status_sub)

            self.append(self._status_card)

            # ---- Charge limit ----
            self._build_charge_limit()

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Screen timeout ----
            self._build_timeout_section("Screen Timeout", "screen")

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- Suspend ----
            self._build_timeout_section("Suspend after", "suspend")

        def _build_charge_limit(self):
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl = Gtk.Label(label="Charge Limit")
            lbl.add_css_class("luminos-section-title")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label="Protects long-term battery health")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)
            self.append(text_box)

            seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            seg.add_css_class("luminos-segmented")
            seg.set_halign(Gtk.Align.START)
            seg.set_margin_top(SPACE_3)

            self._charge_btns = {}
            for pct in ("60%", "80%", "100%"):
                btn = Gtk.Button(label=pct)
                key = pct
                self._charge_btns[key] = btn
                if key == "80%":
                    btn.add_css_class("luminos-segmented-active")
                btn.connect("clicked", self._on_charge_click, key)
                seg.append(btn)

            self.append(seg)

            note = Gtk.Label(label="Changes take effect immediately")
            note.add_css_class("luminos-charge-note")
            note.set_halign(Gtk.Align.START)
            self.append(note)

        def _build_timeout_section(self, title: str, section_id: str):
            sec_title = Gtk.Label(label=title)
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            options = _get_timeout_options()

            # On battery row
            bat_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            bat_row.add_css_class("luminos-setting-row")
            bat_row.set_hexpand(True)

            bat_lbl = Gtk.Label(label="On battery")
            bat_lbl.add_css_class("luminos-setting-label")
            bat_lbl.set_halign(Gtk.Align.START)
            bat_lbl.set_hexpand(True)
            bat_row.append(bat_lbl)

            bat_combo = Gtk.DropDown.new_from_strings(options)
            bat_combo.set_selected(2)  # 5 min
            bat_combo.add_css_class("luminos-dropdown")
            bat_row.append(bat_combo)
            self.append(bat_row)

            # Plugged in row
            plug_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            plug_row.add_css_class("luminos-setting-row")
            plug_row.set_hexpand(True)

            plug_lbl = Gtk.Label(label="Plugged in")
            plug_lbl.add_css_class("luminos-setting-label")
            plug_lbl.set_halign(Gtk.Align.START)
            plug_lbl.set_hexpand(True)
            plug_row.append(plug_lbl)

            plug_combo = Gtk.DropDown.new_from_strings(options)
            plug_combo.set_selected(3)  # 10 min
            plug_combo.add_css_class("luminos-dropdown")
            plug_row.append(plug_combo)
            self.append(plug_row)

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _on_charge_click(self, btn, key):
            for k, b in self._charge_btns.items():
                if k == key:
                    b.add_css_class("luminos-segmented-active")
                else:
                    b.remove_css_class("luminos-segmented-active")
            logger.debug(f"Charge limit set to {key}")

        def _refresh_status(self) -> bool:
            try:
                from power_manager import get_ac_status
                ac = get_ac_status()
                plugged = ac.get("plugged_in", False)
                if plugged:
                    self._status_title.set_text("Performance Mode")
                    self._status_sub.set_text("Plugged in — full performance")
                    self._status_card.remove_css_class("luminos-power-card-battery")
                    self._status_card.add_css_class("luminos-power-card-performance")
                else:
                    self._status_title.set_text("Battery Mode")
                    pct = ac.get("battery_percent", 0)
                    self._status_sub.set_text(f"Running on battery — {pct}%")
                    self._status_card.remove_css_class("luminos-power-card-performance")
                    self._status_card.add_css_class("luminos-power-card-battery")
            except Exception:
                pass
            return GLib.SOURCE_CONTINUE

else:
    class PowerPanel:  # type: ignore[no-redef]
        pass
