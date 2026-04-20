"""
src/gui/settings/panels/network_panel.py
NetworkPanel — WiFi network list, Ethernet status, connection management.

Pure helpers:
    _get_wifi_networks()     → list[dict]
    _get_ethernet_status()   → dict
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.network")

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
    COLOR_SUCCESS,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD, RADIUS_DEFAULT,
    SETTINGS_PADDING,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_wifi_networks() -> list:
    """
    Scan for available WiFi networks.

    Returns:
        List of dicts with keys: ssid, signal, secured, connected.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SIGNAL,SECURITY,SSID", "device", "wifi", "list"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            networks = []
            for line in result.stdout.strip().splitlines():
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    networks.append({
                        "ssid": parts[3],
                        "signal": int(parts[1]) if parts[1].isdigit() else 0,
                        "secured": bool(parts[2].strip()),
                        "connected": parts[0] == "yes",
                    })
            return networks
    except Exception:
        pass
    return []


def _get_ethernet_status() -> dict:
    """
    Get Ethernet connection status.

    Returns:
        Dict with keys: connected, ip_address.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["nmcli", "-t", "-f", "TYPE,STATE,IP4.ADDRESS", "connection", "show", "--active"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if "ethernet" in line.lower():
                    return {"connected": True, "ip_address": "Connected"}
    except Exception:
        pass
    return {"connected": False, "ip_address": ""}


# ===========================================================================
# CSS
# ===========================================================================

_NETWORK_CSS = f"""
.luminos-wifi-row {{
    min-height: 48px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-wifi-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-wifi-connected {{
    background-color: {ACCENT_SUBTLE};
}}

.luminos-wifi-badge {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: {ACCENT};
    padding: 2px 8px;
    border-radius: {RADIUS_MD}px;
    background-color: {ACCENT_SUBTLE};
}}

.luminos-password-dialog {{
    background-color: {BG_ELEVATED};
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACE_6}px;
}}

.luminos-password-dialog-overlay {{
    background-color: rgba(0, 0, 0, 0.6);
}}

.luminos-btn-primary {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
    background-color: {ACCENT};
    color: {TEXT_PRIMARY};
    border-radius: {RADIUS_MD}px;
    padding: {SPACE_2}px {SPACE_4}px;
    min-height: 36px;
    border: none;
}}

.luminos-btn-secondary {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
    background-color: {BG_OVERLAY};
    color: {TEXT_PRIMARY};
    border-radius: {RADIUS_MD}px;
    border: 1px solid {BORDER};
    padding: {SPACE_2}px {SPACE_4}px;
    min-height: 36px;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class NetworkPanel(Gtk.Box):
        """Network settings: WiFi list, Ethernet status."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            self._wifi_enabled = True

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_NETWORK_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            self._build()
            GLib.timeout_add_seconds(10, self._refresh_networks)

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
            title = Gtk.Label(label="Network")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- WiFi section ----
            wifi_header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            wifi_header.set_hexpand(True)

            wifi_title = Gtk.Label(label="Wi-Fi")
            wifi_title.add_css_class("luminos-section-title")
            wifi_title.set_halign(Gtk.Align.START)
            wifi_title.set_hexpand(True)
            wifi_header.append(wifi_title)

            self._wifi_switch = Gtk.Switch()
            self._wifi_switch.set_active(True)
            self._wifi_switch.add_css_class("luminos-switch")
            self._wifi_switch.set_valign(Gtk.Align.CENTER)
            self._wifi_switch.connect("state-set", self._on_wifi_toggle)
            wifi_header.append(self._wifi_switch)

            self.append(wifi_header)

            # Network list
            self._wifi_list = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            self._wifi_list.set_margin_top(SPACE_3)
            self.append(self._wifi_list)

            self._refresh_networks()

            div = Gtk.Box()
            div.add_css_class("luminos-section-divider")
            self.append(div)

            # ---- Ethernet section ----
            eth_title = Gtk.Label(label="Ethernet")
            eth_title.add_css_class("luminos-section-title")
            eth_title.set_halign(Gtk.Align.START)
            self.append(eth_title)

            eth_status = _get_ethernet_status()
            if eth_status["connected"]:
                status_text = "Connected"
                status_css = "luminos-text-primary"
            else:
                status_text = "Not connected"
                status_css = "luminos-text-secondary"

            self._eth_label = Gtk.Label(label=status_text)
            self._eth_label.add_css_class(status_css)
            self._eth_label.set_halign(Gtk.Align.START)
            self._eth_label.set_margin_top(SPACE_2)
            self.append(self._eth_label)

            if eth_status.get("ip_address") and eth_status["connected"]:
                ip_lbl = Gtk.Label(label=eth_status["ip_address"])
                ip_lbl.add_css_class("luminos-setting-sublabel")
                ip_lbl.set_halign(Gtk.Align.START)
                self.append(ip_lbl)

        def _on_wifi_toggle(self, switch, state):
            self._wifi_enabled = state
            self._wifi_list.set_visible(state)
            return False

        def _refresh_networks(self) -> bool:
            if not self._wifi_enabled:
                return GLib.SOURCE_CONTINUE

            while (child := self._wifi_list.get_first_child()):
                self._wifi_list.remove(child)

            networks = _get_wifi_networks()
            if not networks:
                empty = Gtk.Label(label="No networks found")
                empty.add_css_class("luminos-text-secondary")
                empty.set_halign(Gtk.Align.START)
                self._wifi_list.append(empty)
            else:
                for net in networks:
                    row = self._make_wifi_row(net)
                    self._wifi_list.append(row)

            return GLib.SOURCE_CONTINUE

        def _make_wifi_row(self, net: dict) -> Gtk.Box:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            row.add_css_class("luminos-wifi-row")
            row.set_hexpand(True)

            if net.get("connected"):
                row.add_css_class("luminos-wifi-connected")

            # Network name
            name_lbl = Gtk.Label(label=net.get("ssid", "Hidden Network"))
            name_lbl.add_css_class("luminos-setting-label")
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_hexpand(True)
            row.append(name_lbl)

            # Connected badge
            if net.get("connected"):
                badge = Gtk.Label(label="Connected")
                badge.add_css_class("luminos-wifi-badge")
                row.append(badge)

            # Lock icon if secured
            if net.get("secured"):
                lock = Gtk.Label(label="🔒")
                lock.set_margin_start(SPACE_2)
                row.append(lock)

            # Signal strength
            signal = net.get("signal", 0)
            if signal >= 60:
                sig_icon = "▂▄▆█"
            elif signal >= 40:
                sig_icon = "▂▄▆░"
            elif signal >= 20:
                sig_icon = "▂▄░░"
            else:
                sig_icon = "▂░░░"
            sig_lbl = Gtk.Label(label=sig_icon)
            sig_lbl.add_css_class("luminos-text-secondary")
            row.append(sig_lbl)

            # Make clickable
            click = Gtk.GestureClick()
            click.connect("pressed", self._on_network_click, net)
            row.add_controller(click)

            return row

        def _on_network_click(self, gesture, n_press, x, y, net):
            if net.get("connected"):
                return
            if net.get("secured"):
                self._show_password_dialog(net)
            else:
                self._connect_network(net["ssid"])

        def _show_password_dialog(self, net):
            dialog = Gtk.Dialog(
                title=f"Connect to {net.get('ssid', '')}",
                transient_for=self.get_root(),
            )
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Connect", Gtk.ResponseType.OK)

            content = dialog.get_content_area()
            content.set_margin_top(SPACE_6)
            content.set_margin_bottom(SPACE_6)
            content.set_margin_start(SPACE_6)
            content.set_margin_end(SPACE_6)
            content.set_spacing(SPACE_4)

            lbl = Gtk.Label(label=f"Password for \"{net.get('ssid', '')}\"")
            lbl.add_css_class("luminos-setting-label")
            content.append(lbl)

            pw_entry = Gtk.PasswordEntry()
            pw_entry.set_show_peek_icon(True)
            content.append(pw_entry)

            dialog.connect("response", self._on_password_response, net, pw_entry)
            dialog.present()

        def _on_password_response(self, dialog, response, net, pw_entry):
            if response == Gtk.ResponseType.OK:
                password = pw_entry.get_text()
                self._connect_network(net["ssid"], password)
            dialog.close()

        def _connect_network(self, ssid: str, password: str = None):
            try:
                import subprocess
                cmd = ["nmcli", "device", "wifi", "connect", ssid]
                if password:
                    cmd += ["password", password]
                subprocess.run(cmd, capture_output=True, timeout=15)
                self._refresh_networks()
            except Exception as e:
                logger.debug(f"WiFi connect error: {e}")

else:
    class NetworkPanel:  # type: ignore[no-redef]
        pass
