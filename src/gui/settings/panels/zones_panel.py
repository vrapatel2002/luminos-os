"""
src/gui/settings/panels/zones_panel.py
ZonesPanel — zone overview, app overrides, Wine settings, Sentinel settings.

Pure helpers:
    _get_zone_color(zone)      → hex str
    _load_zone_overrides()     → dict
    _save_zone_override(name, zone) → bool
"""

import json
import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.zones")

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

_OVERRIDES_PATH = os.path.expanduser("~/.config/luminos/zones.json")

_ZONE_LABELS = {1: "Zone 1 — Native", 2: "Zone 2 — Wine", 3: "Zone 3 — VM"}
_ZONE_DESCS  = {
    1: "Standard Linux binaries. Full hardware access.",
    2: "Windows apps via Wine/Proton. GPU passthrough.",
    3: "Untrusted/unknown. Firecracker microVM sandbox.",
}


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_zone_color(zone: int) -> str:
    """
    Return the display hex color for a given zone number.

    Args:
        zone: 1, 2, or 3.

    Returns:
        Hex color string. Falls back to grey for unknown zones.
    """
    colors = {1: "#26a269", 2: "#f5c211", 3: "#e01b24"}
    return colors.get(zone, "#888888")


def _load_zone_overrides() -> dict:
    """
    Load per-app zone override config from ~/.config/luminos/zones.json.

    Returns:
        Dict mapping app name → zone int. Empty dict on any error.
    """
    try:
        with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load zone overrides: {e}")
    return {}


def _save_zone_override(app_name: str, zone: int) -> bool:
    """
    Save a per-app zone override to the config file.

    Args:
        app_name: Application name or binary.
        zone: Target zone (1, 2, or 3).

    Returns:
        True on success, False on error.
    """
    try:
        overrides = _load_zone_overrides()
        overrides[app_name] = zone
        os.makedirs(os.path.dirname(_OVERRIDES_PATH), exist_ok=True)
        with open(_OVERRIDES_PATH, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2)
        return True
    except OSError as e:
        logger.warning(f"Failed to save zone override: {e}")
        return False


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class ZonesPanel(Gtk.Box):
        """
        Zones settings panel.

        Shows: zone overview cards, app override table, Wine settings,
        Zone 3 settings, Sentinel alert settings.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            self.set_margin_top(24)
            self.set_margin_bottom(24)
            self.set_margin_start(32)
            self.set_margin_end(32)
            self._build()

        def _build(self):
            # ---- Zone overview cards ----
            overview_lbl = Gtk.Label(label="Execution Zones")
            overview_lbl.add_css_class("luminos-settings-section-title")
            overview_lbl.set_halign(Gtk.Align.START)
            self.append(overview_lbl)

            cards_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            for zone in (1, 2, 3):
                card = self._make_zone_card(zone)
                cards_box.append(card)
            self.append(cards_box)

            self.append(Gtk.Separator())

            # ---- App zone overrides ----
            overrides_lbl = Gtk.Label(label="Per-App Zone Overrides")
            overrides_lbl.add_css_class("luminos-settings-section-title")
            overrides_lbl.set_halign(Gtk.Align.START)
            self.append(overrides_lbl)

            self._overrides_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            self.append(self._overrides_box)
            self._refresh_overrides()

            add_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            self._app_entry = Gtk.Entry()
            self._app_entry.set_placeholder_text("App name or binary")
            self._app_entry.set_hexpand(True)
            self._zone_spin = Gtk.SpinButton.new_with_range(1, 3, 1)
            self._zone_spin.set_value(1)
            add_btn = Gtk.Button(label="Add Override")
            add_btn.add_css_class("luminos-btn")
            add_btn.connect("clicked", self._on_add_override)
            add_row.append(self._app_entry)
            add_row.append(self._zone_spin)
            add_row.append(add_btn)
            self.append(add_row)

            self.append(Gtk.Separator())

            # ---- Sentinel settings ----
            sentinel_lbl = Gtk.Label(label="Sentinel Alerts")
            sentinel_lbl.add_css_class("luminos-settings-section-title")
            sentinel_lbl.set_halign(Gtk.Align.START)
            self.append(sentinel_lbl)

            sentinel_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            sentinel_row.set_hexpand(True)
            s_lbl = Gtk.Label(label="Show notifications on zone classification")
            s_lbl.set_hexpand(True)
            s_lbl.set_halign(Gtk.Align.START)
            self._sentinel_switch = Gtk.Switch()
            self._sentinel_switch.set_active(True)
            sentinel_row.append(s_lbl)
            sentinel_row.append(self._sentinel_switch)
            self.append(sentinel_row)

        def _make_zone_card(self, zone: int) -> Gtk.Box:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.add_css_class("luminos-power-card")
            card.set_hexpand(True)
            card.set_margin_top(8)
            card.set_margin_bottom(8)
            card.set_margin_start(8)
            card.set_margin_end(8)

            name_lbl = Gtk.Label(label=_ZONE_LABELS[zone])
            name_lbl.add_css_class("luminos-power-card-name")
            name_lbl.set_halign(Gtk.Align.START)
            card.append(name_lbl)

            desc_lbl = Gtk.Label(label=_ZONE_DESCS[zone])
            desc_lbl.add_css_class("luminos-qs-dim")
            desc_lbl.set_wrap(True)
            desc_lbl.set_halign(Gtk.Align.START)
            card.append(desc_lbl)

            return card

        def _refresh_overrides(self):
            while (child := self._overrides_box.get_first_child()):
                self._overrides_box.remove(child)
            overrides = _load_zone_overrides()
            if not overrides:
                empty = Gtk.Label(label="No overrides configured.")
                empty.add_css_class("luminos-qs-dim")
                empty.set_halign(Gtk.Align.START)
                self._overrides_box.append(empty)
                return
            for app_name, zone in overrides.items():
                row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=8
                )
                lbl = Gtk.Label(label=f"{app_name} → Zone {zone}")
                lbl.set_hexpand(True)
                lbl.set_halign(Gtk.Align.START)
                rm_btn = Gtk.Button(label="Remove")
                rm_btn.add_css_class("luminos-btn")
                rm_btn.connect(
                    "clicked", self._on_remove_override, app_name
                )
                row.append(lbl)
                row.append(rm_btn)
                self._overrides_box.append(row)

        def _on_add_override(self, *_):
            app = self._app_entry.get_text().strip()
            zone = int(self._zone_spin.get_value())
            if app:
                _save_zone_override(app, zone)
                self._app_entry.set_text("")
                self._refresh_overrides()

        def _on_remove_override(self, _btn, app_name: str):
            overrides = _load_zone_overrides()
            overrides.pop(app_name, None)
            try:
                os.makedirs(os.path.dirname(_OVERRIDES_PATH), exist_ok=True)
                with open(_OVERRIDES_PATH, "w", encoding="utf-8") as f:
                    json.dump(overrides, f, indent=2)
            except OSError as e:
                logger.warning(f"Failed to remove override: {e}")
            self._refresh_overrides()

else:
    class ZonesPanel:  # type: ignore[no-redef]
        pass
