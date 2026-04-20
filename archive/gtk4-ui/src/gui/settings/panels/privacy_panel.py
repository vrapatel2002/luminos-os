"""
src/gui/settings/panels/privacy_panel.py
Phase 5.11 Task 2 — Privacy panel with live data.

Sections:
  1. Telemetry badge (static — zero telemetry confirmation)
  2. App Permissions — camera/mic/location, reads/saves app_permissions.json
  3. Sentinel Log — live, last 50 entries, auto-refresh 10s
  4. Network Activity — outbound connections in last hour from /proc/net/tcp

Pure helpers:
  _get_permission_apps(perm_type) → list[dict]
  _get_sentinel_log_entries()     → list[dict]
  _load_permissions()             → dict
  _save_permissions(data)         → bool
"""

import json
import logging
import os
import sys

logger = logging.getLogger("luminos.gui.settings.privacy")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Pango
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD,
    SETTINGS_PADDING,
)

_SENTINEL_LOG_PATH  = "/var/log/luminos/sentinel.log"
_PERMISSIONS_PATH   = os.path.expanduser("~/.config/luminos/app_permissions.json")


# ===========================================================================
# Pure helpers
# ===========================================================================

def _load_permissions() -> dict:
    """
    Read app permissions from ~/.config/luminos/app_permissions.json.

    Returns:
        Dict: {"camera": {app: bool}, "microphone": {app: bool}, ...}
    """
    try:
        with open(_PERMISSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"permissions load error: {e}")
    return {"camera": {}, "microphone": {}, "location": {}}


def _save_permissions(data: dict) -> bool:
    """Persist app permissions to disk."""
    try:
        os.makedirs(os.path.dirname(_PERMISSIONS_PATH), exist_ok=True)
        with open(_PERMISSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError as e:
        logger.warning(f"permissions save error: {e}")
        return False


def _get_permission_apps(perm_type: str) -> list:
    """
    Return apps that have requested a given permission type.

    Args:
        perm_type: "camera", "microphone", or "location".

    Returns:
        List of dicts: [{name: str, allowed: bool}]
    """
    data = _load_permissions()
    section = data.get(perm_type, {})
    if not isinstance(section, dict):
        return []
    return [
        {"name": app, "allowed": bool(allowed)}
        for app, allowed in section.items()
    ]


def _save_permission(perm_type: str, app_name: str, allowed: bool) -> None:
    """Save a single app permission toggle."""
    data = _load_permissions()
    if perm_type not in data:
        data[perm_type] = {}
    data[perm_type][app_name] = allowed
    _save_permissions(data)


def _get_sentinel_log_entries(max_entries: int = 50) -> list:
    """
    Read recent Sentinel log entries from /var/log/luminos/sentinel.log.

    Returns:
        List of dicts: [{timestamp, process_name, pid, classification, details}]
    """
    try:
        from sentinel.sentinel_daemon import parse_sentinel_log_line
    except ImportError:
        parse_sentinel_log_line = None

    try:
        if not os.path.exists(_SENTINEL_LOG_PATH):
            return []
        with open(_SENTINEL_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        entries = []
        for line in lines[-max_entries:]:
            line = line.strip()
            if not line:
                continue
            if parse_sentinel_log_line:
                parsed = parse_sentinel_log_line(line)
                if parsed:
                    entries.append(parsed)
                    continue
            # Fallback: raw line
            parts = line.split(" | ", 1)
            entries.append({
                "timestamp":      parts[0] if len(parts) > 1 else "",
                "process_name":   "",
                "classification": "unknown",
                "details":        parts[1] if len(parts) > 1 else line,
            })
        return entries
    except Exception as e:
        logger.debug(f"sentinel log read error: {e}")
        return []


def _get_network_activity(max_entries: int = 20) -> list:
    """
    Get recent outbound connections from the network monitor.

    Returns:
        List of dicts: [{timestamp, process, pid, remote_addr, remote_port}]
    """
    try:
        from sentinel.network_monitor import get_monitor
        monitor = get_monitor()
        return monitor.get_recent_connections()[-max_entries:]
    except Exception:
        return []


# ===========================================================================
# CSS
# ===========================================================================

_PRIVACY_CSS = f"""
.luminos-telemetry-badge {{
    background-color: {BG_ELEVATED};
    border-radius: {RADIUS_MD}px;
    padding: {SPACE_4}px;
    margin-bottom: {SPACE_6}px;
}}

.luminos-telemetry-text {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
    color: {TEXT_PRIMARY};
}}

.luminos-telemetry-sub {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
}}

.luminos-perm-row {{
    min-height: 44px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-perm-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-sentinel-log {{
    background-color: {BG_ELEVATED};
    border-radius: {RADIUS_MD}px;
    padding: {SPACE_3}px;
    min-height: 200px;
}}

.luminos-sentinel-entry {{
    font-family: monospace;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
}}

.luminos-sentinel-entry-suspicious {{
    font-family: monospace;
    font-size: {FONT_CAPTION}px;
    color: {COLOR_WARNING};
}}

.luminos-sentinel-entry-block {{
    font-family: monospace;
    font-size: {FONT_CAPTION}px;
    color: {COLOR_ERROR};
}}

.luminos-btn-destructive {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    font-weight: 500;
    background-color: rgba(255, 68, 85, 0.15);
    color: {COLOR_ERROR};
    border-radius: {RADIUS_MD}px;
    border: 1px solid rgba(255, 68, 85, 0.4);
    padding: {SPACE_2}px {SPACE_4}px;
    min-height: 36px;
}}

.luminos-btn-destructive:hover {{
    background-color: rgba(255, 68, 85, 0.25);
}}

.luminos-empty-state {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_DISABLED};
    padding: {SPACE_4}px;
}}

.luminos-netmon-entry {{
    font-family: monospace;
    font-size: {FONT_CAPTION}px;
    color: {TEXT_SECONDARY};
}}

.luminos-netmon-luminos {{
    font-family: monospace;
    font-size: {FONT_CAPTION}px;
    color: {COLOR_ERROR};
    font-weight: 600;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class PrivacyPanel(Gtk.Box):
        """
        Privacy settings panel with live Sentinel log, real permissions,
        and network activity monitor.
        """

        _REFRESH_INTERVAL_MS = 10_000   # 10 seconds

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            self._refresh_id  = None
            self._log_box     = None
            self._netmon_box  = None
            self._perm_refs   = {}   # {(perm_type, app): Gtk.Switch}

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_PRIVACY_CSS)
            self._css_provider = css_provider
            self.connect("realize", self._on_realize)
            self.connect("unrealize", self._on_unrealize)

            self._build()

        def _on_realize(self, *_):
            try:
                Gtk.StyleContext.add_provider_for_display(
                    self.get_display(), self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception:
                pass
            # Start auto-refresh
            self._refresh_id = GLib.timeout_add(
                self._REFRESH_INTERVAL_MS, self._auto_refresh
            )

        def _on_unrealize(self, *_):
            if self._refresh_id is not None:
                GLib.source_remove(self._refresh_id)
                self._refresh_id = None

        def _auto_refresh(self) -> bool:
            self._refresh_sentinel_log()
            self._refresh_network_activity()
            return GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # Build
        # -------------------------------------------------------------------

        def _build(self):
            title = Gtk.Label(label="Privacy")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            self._build_telemetry_badge()

            for perm in ("Camera", "Microphone", "Location"):
                self._build_permission_section(perm, perm.lower())
                div = Gtk.Box()
                div.add_css_class("luminos-section-divider")
                self.append(div)

            self._build_sentinel_section()

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            self._build_network_section()

        def _build_telemetry_badge(self):
            badge = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            badge.add_css_class("luminos-telemetry-badge")

            dot = Gtk.Label()
            dot.set_markup(f"<span foreground='{COLOR_SUCCESS}'>●</span>")
            badge.append(dot)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl = Gtk.Label(label="Zero Telemetry")
            lbl.add_css_class("luminos-telemetry-text")
            lbl.set_halign(Gtk.Align.START)
            text_box.append(lbl)

            sub = Gtk.Label(label="Luminos collects zero telemetry. Always.")
            sub.add_css_class("luminos-telemetry-sub")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)

            badge.append(text_box)
            self.append(badge)

        def _build_permission_section(self, title: str, perm_type: str):
            sec_title = Gtk.Label(label=title)
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            apps = _get_permission_apps(perm_type)
            if not apps:
                empty = Gtk.Label(
                    label=f"No apps have requested {perm_type} access"
                )
                empty.add_css_class("luminos-empty-state")
                empty.set_halign(Gtk.Align.START)
                self.append(empty)
                return

            for app in apps:
                row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
                )
                row.add_css_class("luminos-perm-row")
                row.set_hexpand(True)

                name_lbl = Gtk.Label(label=app["name"])
                name_lbl.add_css_class("luminos-setting-label")
                name_lbl.set_halign(Gtk.Align.START)
                name_lbl.set_hexpand(True)
                row.append(name_lbl)

                switch = Gtk.Switch()
                switch.set_active(app.get("allowed", True))
                switch.add_css_class("luminos-switch")
                switch.set_valign(Gtk.Align.CENTER)

                app_name = app["name"]
                switch.connect(
                    "state-set",
                    lambda w, state, pt=perm_type, an=app_name:
                        self._on_perm_toggle(pt, an, state)
                )
                row.append(switch)
                self.append(row)

        def _build_sentinel_section(self):
            header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            sec_title = Gtk.Label(label="Security Log")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            header.append(sec_title)

            sub = Gtk.Label(label="Events flagged by Sentinel — auto-refreshes every 10s")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            header.append(sub)
            self.append(header)

            log_scroll = Gtk.ScrolledWindow()
            log_scroll.set_policy(
                Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
            )
            log_scroll.set_min_content_height(180)
            log_scroll.set_max_content_height(280)
            log_scroll.add_css_class("luminos-sentinel-log")
            log_scroll.set_margin_top(SPACE_3)

            self._log_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self._populate_sentinel_log()
            log_scroll.set_child(self._log_box)
            self.append(log_scroll)

            clear_btn = Gtk.Button(label="Clear Log")
            clear_btn.add_css_class("luminos-btn-destructive")
            clear_btn.set_halign(Gtk.Align.START)
            clear_btn.set_margin_top(SPACE_3)
            clear_btn.connect("clicked", self._on_clear_sentinel_log)
            self.append(clear_btn)

        def _build_network_section(self):
            header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            sec_title = Gtk.Label(label="Network Activity")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            header.append(sec_title)

            sub = Gtk.Label(label="Outbound connections — Luminos should show zero")
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            header.append(sub)
            self.append(header)

            net_scroll = Gtk.ScrolledWindow()
            net_scroll.set_policy(
                Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
            )
            net_scroll.set_min_content_height(100)
            net_scroll.set_max_content_height(200)
            net_scroll.add_css_class("luminos-sentinel-log")
            net_scroll.set_margin_top(SPACE_3)

            self._netmon_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self._populate_network_activity()
            net_scroll.set_child(self._netmon_box)
            self.append(net_scroll)

        # -------------------------------------------------------------------
        # Data population
        # -------------------------------------------------------------------

        def _populate_sentinel_log(self):
            while (child := self._log_box.get_first_child()):
                self._log_box.remove(child)

            entries = _get_sentinel_log_entries(50)
            if not entries:
                empty = Gtk.Label(label="No security events logged")
                empty.add_css_class("luminos-empty-state")
                empty.set_halign(Gtk.Align.START)
                self._log_box.append(empty)
                return

            for entry in reversed(entries):   # most recent first
                ts     = entry.get("timestamp", "")
                name   = entry.get("process_name", "")
                cls    = entry.get("classification", "")
                detail = entry.get("details", "")

                if name:
                    text = f"{ts}  {name}  [{cls}]  {detail}"
                else:
                    text = f"{ts}  {detail}"

                lbl = Gtk.Label(label=text)
                if cls == "block":
                    lbl.add_css_class("luminos-sentinel-entry-block")
                elif cls == "suspicious":
                    lbl.add_css_class("luminos-sentinel-entry-suspicious")
                else:
                    lbl.add_css_class("luminos-sentinel-entry")
                lbl.set_halign(Gtk.Align.START)
                lbl.set_selectable(True)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                self._log_box.append(lbl)

        def _populate_network_activity(self):
            while (child := self._netmon_box.get_first_child()):
                self._netmon_box.remove(child)

            connections = _get_network_activity()
            if not connections:
                empty = Gtk.Label(label="No outbound connections detected")
                empty.add_css_class("luminos-empty-state")
                empty.set_halign(Gtk.Align.START)
                self._netmon_box.append(empty)
                return

            for conn in reversed(connections):
                text = (
                    f"{conn.get('timestamp','')}  "
                    f"{conn.get('process','?')}  →  "
                    f"{conn.get('remote_addr','')}:{conn.get('remote_port','')}"
                )
                lbl = Gtk.Label(label=text)
                lbl.set_halign(Gtk.Align.START)
                lbl.set_selectable(True)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                # Highlight if it's a Luminos process (should be zero)
                from sentinel.network_monitor import _LUMINOS_PROCS
                proc = conn.get("process", "")
                if any(p in proc for p in _LUMINOS_PROCS):
                    lbl.add_css_class("luminos-netmon-luminos")
                else:
                    lbl.add_css_class("luminos-netmon-entry")
                self._netmon_box.append(lbl)

        # -------------------------------------------------------------------
        # Refresh
        # -------------------------------------------------------------------

        def _refresh_sentinel_log(self):
            if self._log_box:
                self._populate_sentinel_log()

        def _refresh_network_activity(self):
            if self._netmon_box:
                self._populate_network_activity()

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _on_perm_toggle(self, perm_type: str, app_name: str,
                            state: bool) -> bool:
            _save_permission(perm_type, app_name, state)
            return False   # propagate state

        def _on_clear_sentinel_log(self, *_):
            try:
                if os.path.exists(_SENTINEL_LOG_PATH):
                    with open(_SENTINEL_LOG_PATH, "w") as f:
                        f.write("")
            except Exception as e:
                logger.debug(f"Clear sentinel log error: {e}")
            self._refresh_sentinel_log()


else:
    class PrivacyPanel:  # type: ignore[no-redef]
        pass
