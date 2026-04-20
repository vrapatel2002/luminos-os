"""
src/gui/quick_settings/bt_panel.py
Bluetooth device list + connect/disconnect/power for the Quick Settings panel.

Pure functions are testable without GTK or a display.
GTK widget class is guarded behind _GTK_AVAILABLE.
"""

import logging
import os
import re
import sys

logger = logging.getLogger("luminos-ai.gui.quick_settings.bt")

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

def _parse_bt_info(info_out: str) -> dict:
    """
    Parse a single `bluetoothctl info <mac>` output block.

    Returns partial dict with keys: name, connected, battery.
    """
    result: dict = {"name": None, "connected": False, "battery": None}

    for line in info_out.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            result["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Connected:"):
            result["connected"] = "yes" in line.lower()
        elif "Battery Percentage" in line:
            # "Battery Percentage: 0x52 (82)"
            m = re.search(r"\((\d+)\)", line)
            if m:
                result["battery"] = int(m.group(1))

    return result


def get_bt_devices() -> list:
    """
    List paired Bluetooth devices with connection status.

    Returns:
        [{"name": str, "mac": str, "connected": bool, "battery": int|None}]
        Returns [] on error or if bluetoothctl not installed.
    """
    out = run_cmd(["bluetoothctl", "devices"], timeout=3.0)
    if not out:
        return []

    devices = []
    for line in out.splitlines():
        # Format: "Device AA:BB:CC:DD:EE:FF DeviceName"
        parts = line.strip().split(" ", 2)
        if len(parts) < 2 or parts[0] != "Device":
            continue
        mac  = parts[1]
        name = parts[2] if len(parts) > 2 else mac

        # Get detailed info (best effort — don't fail on error)
        info_out = run_cmd(["bluetoothctl", "info", mac], timeout=2.0)
        if info_out:
            detail = _parse_bt_info(info_out)
            name      = detail.get("name") or name
            connected = detail.get("connected", False)
            battery   = detail.get("battery")
        else:
            connected = False
            battery   = None

        devices.append({
            "name":      name,
            "mac":       mac,
            "connected": connected,
            "battery":   battery,
        })

    return devices


def toggle_bt_device(mac: str) -> dict:
    """
    Connect or disconnect a paired Bluetooth device.

    Queries current state first, then toggles.

    Args:
        mac: Bluetooth MAC address (e.g. "AA:BB:CC:DD:EE:FF").

    Returns:
        {"success": bool, "connected": bool}
    """
    # Check current state
    info_out = run_cmd(["bluetoothctl", "info", mac], timeout=2.0)
    currently_connected = False
    if info_out:
        currently_connected = _parse_bt_info(info_out).get("connected", False)

    if currently_connected:
        out = run_cmd(["bluetoothctl", "disconnect", mac], timeout=5.0)
        return {"success": out is not None, "connected": False}
    else:
        out = run_cmd(["bluetoothctl", "connect", mac], timeout=10.0)
        return {"success": out is not None, "connected": out is not None}


def set_bt_power(on: bool) -> bool:
    """
    Turn Bluetooth adapter on or off.

    Args:
        on: True to power on, False to power off.

    Returns:
        True on success, False on error.
    """
    cmd = ["bluetoothctl", "power", "on" if on else "off"]
    out = run_cmd(cmd, timeout=3.0)
    return out is not None


# ===========================================================================
# GTK widget
# ===========================================================================

if _GTK_AVAILABLE:

    class BluetoothPanel(Gtk.Box):
        """
        Expandable Bluetooth section for the Quick Settings panel.

        Shows:
        - Header row: "Bluetooth" label + on/off toggle
        - Device list (when on): device icon, name, battery %, connected badge
        - "Connect New Device..." button at bottom
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self._bt_on = True
            self._build()

        def _build(self):
            self.add_css_class("luminos-qs-section")

            # Header row
            header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            header.set_hexpand(True)

            lbl = Gtk.Label(label="Bluetooth")
            lbl.add_css_class("luminos-qs-section-title")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            header.append(lbl)

            self._switch = Gtk.Switch()
            self._switch.set_active(True)
            self._switch.connect("notify::active", self._on_toggle)
            header.append(self._switch)

            self.append(header)

            # Content area
            self._content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self.append(self._content)

            self._offline_label = Gtk.Label(label="Bluetooth Off")
            self._offline_label.add_css_class("luminos-qs-dim")
            self._offline_label.set_visible(False)
            self.append(self._offline_label)

            self._new_btn = Gtk.Button(label="Connect New Device…")
            self._new_btn.add_css_class("luminos-btn")
            self._new_btn.set_halign(Gtk.Align.START)
            self.append(self._new_btn)

        def refresh(self):
            """Reload device list from bluetoothctl."""
            child = self._content.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                self._content.remove(child)
                child = nxt

            if not self._bt_on:
                self._offline_label.set_visible(True)
                self._content.set_visible(False)
                self._new_btn.set_visible(False)
                return

            self._offline_label.set_visible(False)
            self._content.set_visible(True)
            self._new_btn.set_visible(True)

            devices = get_bt_devices()
            for dev in devices:
                row = self._make_device_row(dev)
                self._content.append(row)

        def _make_device_row(self, dev: dict) -> Gtk.Box:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            row.add_css_class("luminos-qs-row")

            icon = Gtk.Label(label="🔵")
            row.append(icon)

            name_lbl = Gtk.Label(label=dev["name"])
            name_lbl.set_hexpand(True)
            name_lbl.set_halign(Gtk.Align.START)
            row.append(name_lbl)

            if dev.get("battery") is not None:
                bat = Gtk.Label(label=f"{dev['battery']}%")
                bat.add_css_class("luminos-qs-dim")
                row.append(bat)

            if dev.get("connected"):
                badge = Gtk.Label(label="Connected")
                badge.add_css_class("luminos-qs-badge-active")
                row.append(badge)

            mac   = dev["mac"]
            click = Gtk.GestureClick()
            click.connect("pressed", lambda *_: self._on_device_click(mac))
            row.add_controller(click)
            return row

        def _on_device_click(self, mac: str):
            toggle_bt_device(mac)
            GLib.timeout_add(500, self.refresh)   # brief delay for BT stack

        def _on_toggle(self, switch, _param):
            self._bt_on = switch.get_active()
            set_bt_power(self._bt_on)
            self.refresh()
