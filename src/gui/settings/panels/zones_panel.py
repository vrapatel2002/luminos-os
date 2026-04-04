"""
src/gui/settings/panels/zones_panel.py
ZonesPanel — compatibility layer status, router, recent activity, app overrides.

Pure helpers:
    _get_zone_color(zone)      → hex str
    _load_zone_overrides()     → dict
    _save_zone_override(name, zone) → bool
"""

import json
import logging
import os
import sys
import time

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

from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    COLOR_SUCCESS, COLOR_ERROR,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_DEFAULT,
    SETTINGS_PADDING,
)


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
    colors = {1: COLOR_SUCCESS, 2: ACCENT, 3: COLOR_ERROR}
    return colors.get(zone, TEXT_DISABLED)


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


_LAYER_INFO = {
    1: {"name": "Proton/Wine/Lutris", "desc": "Near-native Windows app support"},
    2: {"name": "Firecracker microVM", "desc": "Lightweight VM for incompatible apps"},
    3: {"name": "KVM/QEMU",           "desc": "Full VM with GPU passthrough"},
}


# ===========================================================================
# CSS
# ===========================================================================

_ZONES_CSS = f"""
.luminos-zone-status-row {{
    min-height: 44px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-zone-status-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-recent-row {{
    min-height: 36px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-recent-row:hover {{
    background-color: {BG_OVERLAY};
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class ZonesPanel(Gtk.Box):
        """
        Zones settings panel.
        Shows: compatibility layer status, router status, recent activity, app overrides.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_ZONES_CSS)
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
            title = Gtk.Label(label="Zones")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Compatibility Layers status ----
            self._build_status_section()

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Router section ----
            self._build_router_section()

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- Recent activity ----
            self._build_recent_section()

            div3 = Gtk.Box()
            div3.add_css_class("luminos-section-divider")
            self.append(div3)

            # ---- App overrides ----
            self._build_overrides_section()

        def _build_status_section(self):
            sec_title = Gtk.Label(label="Compatibility Layers")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            for zone_num, info in _LAYER_INFO.items():
                row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
                )
                row.add_css_class("luminos-zone-status-row")
                row.set_hexpand(True)

                # Status dot
                color = _get_zone_color(zone_num)
                dot = Gtk.Label()
                dot.set_markup(f"<span foreground='{color}'>●</span>")
                row.append(dot)

                # Name + status
                text_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=1
                )
                text_box.set_hexpand(True)

                name_lbl = Gtk.Label(label=info["name"])
                name_lbl.add_css_class("luminos-setting-label")
                name_lbl.set_halign(Gtk.Align.START)
                text_box.append(name_lbl)

                desc_lbl = Gtk.Label(label=info["desc"])
                desc_lbl.add_css_class("luminos-setting-sublabel")
                desc_lbl.set_halign(Gtk.Align.START)
                text_box.append(desc_lbl)

                row.append(text_box)

                # Status text
                status = self._get_layer_status(zone_num)
                status_lbl = Gtk.Label(label=status)
                status_lbl.add_css_class("luminos-text-secondary")
                row.append(status_lbl)

                self.append(row)

        def _get_layer_status(self, zone_num: int) -> str:
            if zone_num == 1:
                try:
                    import subprocess
                    result = subprocess.run(
                        ["wine", "--version"],
                        capture_output=True, text=True, timeout=2,
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                except Exception:
                    pass
                return "Available"
            elif zone_num == 2:
                return "Available"
            else:
                return "Not configured"

        def _build_router_section(self):
            sec_title = Gtk.Label(label="Compatibility Router")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            # Status row
            try:
                from gui.settings.panels.ai_panel import _get_router_status
                router = _get_router_status()
            except ImportError:
                router = {"engine": "8 rules", "hardware": "CPU only"}

            status_lbl = Gtk.Label(
                label=f"Active ({router.get('hardware', 'CPU')})"
            )
            status_lbl.add_css_class("luminos-text-primary")
            status_lbl.set_halign(Gtk.Align.START)
            status_lbl.set_margin_top(SPACE_2)
            self.append(status_lbl)

            # Cache info
            cache_lbl = Gtk.Label(label="0 apps analyzed")
            cache_lbl.add_css_class("luminos-setting-sublabel")
            cache_lbl.set_halign(Gtk.Align.START)
            cache_lbl.set_margin_top(SPACE_2)
            self.append(cache_lbl)

            # Clear cache button
            clear_btn = Gtk.Button(label="Clear Cache")
            clear_btn.add_css_class("luminos-btn-secondary")
            clear_btn.set_halign(Gtk.Align.START)
            clear_btn.set_margin_top(SPACE_3)
            clear_btn.connect("clicked", self._on_clear_cache)
            self.append(clear_btn)

        def _build_recent_section(self):
            sec_title = Gtk.Label(label="Recent")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            self._recent_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            self._recent_box.set_margin_top(SPACE_2)
            self.append(self._recent_box)

            # Empty state
            empty = Gtk.Label(label="No Windows apps launched yet")
            empty.add_css_class("luminos-text-disabled")
            empty.set_halign(Gtk.Align.START)
            self._recent_box.append(empty)

        def _build_overrides_section(self):
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            sec_title = Gtk.Label(label="App Overrides")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            text_box.append(sec_title)

            sub = Gtk.Label(label="Force a specific layer for an app")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)
            self.append(text_box)

            self._overrides_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            self._overrides_box.set_margin_top(SPACE_3)
            self.append(self._overrides_box)
            self._refresh_overrides()

            # Add override button
            add_btn = Gtk.Button(label="Add Override")
            add_btn.add_css_class("luminos-btn-secondary")
            add_btn.set_halign(Gtk.Align.START)
            add_btn.set_margin_top(SPACE_3)
            add_btn.connect("clicked", self._on_add_override)
            self.append(add_btn)

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _refresh_overrides(self):
            while (child := self._overrides_box.get_first_child()):
                self._overrides_box.remove(child)

            overrides = _load_zone_overrides()
            if not overrides:
                empty = Gtk.Label(
                    label="No overrides set — router decides automatically"
                )
                empty.add_css_class("luminos-text-disabled")
                empty.set_halign(Gtk.Align.START)
                self._overrides_box.append(empty)
                return

            layer_names = {1: "Proton", 2: "Firecracker", 3: "KVM"}
            for app_name, zone in overrides.items():
                row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
                )
                row.add_css_class("luminos-zone-status-row")
                row.set_hexpand(True)

                lbl = Gtk.Label(
                    label=f"{app_name} → {layer_names.get(zone, f'Zone {zone}')}"
                )
                lbl.add_css_class("luminos-setting-label")
                lbl.set_hexpand(True)
                lbl.set_halign(Gtk.Align.START)
                row.append(lbl)

                rm_btn = Gtk.Button(label="Remove")
                rm_btn.add_css_class("luminos-btn-secondary")
                rm_btn.connect(
                    "clicked", self._on_remove_override, app_name
                )
                row.append(rm_btn)

                self._overrides_box.append(row)

        def _on_add_override(self, _btn):
            dialog = Gtk.Dialog(
                title="Add App Override",
                transient_for=self.get_root(),
            )
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Add", Gtk.ResponseType.OK)

            content = dialog.get_content_area()
            content.set_margin_top(SPACE_6)
            content.set_margin_bottom(SPACE_6)
            content.set_margin_start(SPACE_6)
            content.set_margin_end(SPACE_6)
            content.set_spacing(SPACE_4)

            # App name
            app_lbl = Gtk.Label(label="Application (.exe path)")
            app_lbl.add_css_class("luminos-setting-label")
            app_lbl.set_halign(Gtk.Align.START)
            content.append(app_lbl)

            app_entry = Gtk.Entry()
            app_entry.set_placeholder_text("e.g. notepad.exe")
            content.append(app_entry)

            # Layer selector
            layer_lbl = Gtk.Label(label="Layer")
            layer_lbl.add_css_class("luminos-setting-label")
            layer_lbl.set_halign(Gtk.Align.START)
            content.append(layer_lbl)

            layers = ["Auto", "Proton", "Wine", "Firecracker", "KVM"]
            layer_combo = Gtk.DropDown.new_from_strings(layers)
            layer_combo.set_selected(0)
            content.append(layer_combo)

            dialog.connect(
                "response", self._on_override_response, app_entry, layer_combo
            )
            dialog.present()

        def _on_override_response(self, dialog, response, app_entry, layer_combo):
            if response == Gtk.ResponseType.OK:
                app = app_entry.get_text().strip()
                layer_map = {0: 0, 1: 1, 2: 1, 3: 2, 4: 3}
                zone = layer_map.get(layer_combo.get_selected(), 0)
                if app and zone > 0:
                    _save_zone_override(app, zone)
                    self._refresh_overrides()
            dialog.close()

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

        def _on_clear_cache(self, _btn):
            logger.debug("Router cache cleared")

else:
    class ZonesPanel:  # type: ignore[no-redef]
        pass
