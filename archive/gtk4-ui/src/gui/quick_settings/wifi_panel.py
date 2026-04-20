"""
src/gui/quick_settings/wifi_panel.py
WiFi network list + connect/disconnect control for the Quick Settings panel.

Pure functions are testable without GTK or a display.
GTK widget class is guarded behind _GTK_AVAILABLE.
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.quick_settings.wifi")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.common.subprocess_helpers import run_cmd


# ===========================================================================
# Pure logic — testable without GTK
# ===========================================================================

def get_wifi_networks() -> list:
    """
    List available WiFi networks via nmcli.

    Returns:
        List of dicts sorted by signal descending:
        [{"ssid": str, "signal": int, "security": str, "active": bool}]
        Returns [] on error or if nmcli not installed.
    """
    out = run_cmd(
        ["nmcli", "-t", "-f", "ssid,signal,security,active",
         "dev", "wifi", "list"],
        timeout=4.0,
    )
    if not out:
        return []

    networks = []
    seen_ssids: set[str] = set()
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        ssid     = parts[0].strip()
        security = parts[2].strip()
        active   = parts[-1].strip().lower() == "yes"
        try:
            signal = int(parts[1].strip())
        except ValueError:
            signal = 0
        if not ssid or ssid in seen_ssids:
            continue
        seen_ssids.add(ssid)
        networks.append({
            "ssid":     ssid,
            "signal":   signal,
            "security": security,
            "active":   active,
        })

    networks.sort(key=lambda n: n["signal"], reverse=True)
    return networks


def get_active_connection() -> dict:
    """
    Query the active WiFi connection.

    Returns:
        {
            "connected": bool,
            "ssid":      str|None,
            "signal":    int|None,
        }
    """
    out = run_cmd(
        ["nmcli", "-t", "-f", "active,signal,ssid",
         "dev", "wifi", "list"],
        timeout=2.0,
    )
    if not out:
        return {"connected": False, "ssid": None, "signal": None}

    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[0].strip().lower() == "yes":
            try:
                signal = int(parts[1].strip())
                ssid   = ":".join(parts[2:]).strip()
                return {"connected": True, "ssid": ssid or None, "signal": signal}
            except (ValueError, IndexError):
                continue

    return {"connected": False, "ssid": None, "signal": None}


def connect_wifi(ssid: str, password: str | None = None) -> dict:
    """
    Connect to a WiFi network.

    Args:
        ssid:     Network name.
        password: WPA passphrase (None for open networks or saved profiles).

    Returns:
        {"success": bool, "message": str}
    """
    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]

    out = run_cmd(cmd, timeout=15.0)
    if out is not None:
        return {"success": True, "message": out.strip() or f"Connected to {ssid}"}
    return {"success": False, "message": f"Failed to connect to {ssid}"}


def disconnect_wifi() -> bool:
    """
    Disconnect from the current WiFi network.

    Tries to find the active wireless device from nmcli before disconnecting.

    Returns:
        True on success, False on error.
    """
    # Find active wireless device name
    dev_out = run_cmd(
        ["nmcli", "-t", "-f", "device,type,state", "dev"],
        timeout=2.0,
    )
    device = "wlan0"   # default fallback
    if dev_out:
        for line in dev_out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and "wifi" in parts[1].lower():
                candidate = parts[0].strip()
                if candidate:
                    device = candidate
                    break

    out = run_cmd(["nmcli", "dev", "disconnect", device], timeout=5.0)
    return out is not None


# ===========================================================================
# GTK widget
# ===========================================================================

if _GTK_AVAILABLE:

    def _signal_icon(signal: int) -> str:
        """Return a text signal-strength indicator."""
        if signal >= 75:
            return "▂▄▆█"
        if signal >= 50:
            return "▂▄▆_"
        if signal >= 25:
            return "▂▄__"
        return "▂___"

    class WiFiPanel(Gtk.Box):
        """
        Expandable WiFi section for the Quick Settings panel.

        Shows:
        - Header row: "WiFi" label + on/off toggle
        - Network list (when on): signal icon, SSID, lock, active badge
        - "Other Network..." button at bottom
        """

        def __init__(self, on_connect=None):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self._on_connect_cb = on_connect
            self._wifi_on = True   # toggled by switch
            self._build()

        def _build(self):
            self.add_css_class("luminos-qs-section")

            # Header row: label + toggle
            header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            header.set_hexpand(True)

            lbl = Gtk.Label(label="WiFi")
            lbl.add_css_class("luminos-qs-section-title")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            header.append(lbl)

            self._switch = Gtk.Switch()
            self._switch.set_active(True)
            self._switch.connect("notify::active", self._on_toggle)
            header.append(self._switch)

            self.append(header)

            # Content area (shown when on)
            self._content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self.append(self._content)

            self._offline_label = Gtk.Label(label="WiFi Off")
            self._offline_label.add_css_class("luminos-qs-dim")
            self._offline_label.set_visible(False)
            self.append(self._offline_label)

            # "Other Network..." button
            self._other_btn = Gtk.Button(label="Other Network…")
            self._other_btn.add_css_class("luminos-btn")
            self._other_btn.set_halign(Gtk.Align.START)
            self.append(self._other_btn)

        def refresh(self):
            """Reload network list from nmcli."""
            # Clear existing network rows
            child = self._content.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._content.remove(child)
                child = next_child

            if not self._wifi_on:
                self._offline_label.set_visible(True)
                self._content.set_visible(False)
                self._other_btn.set_visible(False)
                return

            self._offline_label.set_visible(False)
            self._content.set_visible(True)
            self._other_btn.set_visible(True)

            networks = get_wifi_networks()
            for net in networks[:12]:   # cap at 12 visible networks
                row = self._make_network_row(net)
                self._content.append(row)

        def _make_network_row(self, net: dict) -> Gtk.Box:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            row.add_css_class("luminos-qs-row")

            sig_lbl = Gtk.Label(label=_signal_icon(net["signal"]))
            sig_lbl.add_css_class("luminos-qs-signal")
            row.append(sig_lbl)

            ssid_lbl = Gtk.Label(label=net["ssid"])
            ssid_lbl.set_hexpand(True)
            ssid_lbl.set_halign(Gtk.Align.START)
            row.append(ssid_lbl)

            if net.get("security") and net["security"].lower() not in ("", "--"):
                lock = Gtk.Label(label="🔒")
                row.append(lock)

            if net.get("active"):
                badge = Gtk.Label(label="Connected")
                badge.add_css_class("luminos-qs-badge-active")
                row.append(badge)

            click = Gtk.GestureClick()
            ssid  = net["ssid"]
            click.connect("pressed", lambda *_: self._on_network_click(ssid))
            row.add_controller(click)
            return row

        def _on_network_click(self, ssid: str):
            if self._on_connect_cb:
                self._on_connect_cb(ssid)
            else:
                connect_wifi(ssid)
            self.refresh()

        def _on_toggle(self, switch, _param):
            self._wifi_on = switch.get_active()
            self.refresh()
