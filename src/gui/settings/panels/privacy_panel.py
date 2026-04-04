"""
src/gui/settings/panels/privacy_panel.py
PrivacyPanel — telemetry badge, camera/mic/location permissions, Sentinel log.

Pure helpers:
    _get_permission_apps(perm_type) → list[dict]
    _get_sentinel_log_entries()     → list[dict]
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.privacy")

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
    COLOR_SUCCESS, COLOR_ERROR,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD,
    SETTINGS_PADDING,
)

_SENTINEL_LOG_PATH = "/var/log/luminos/sentinel.log"


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_permission_apps(perm_type: str) -> list:
    """
    Return apps that have requested a given permission.

    Args:
        perm_type: "camera", "microphone", or "location".

    Returns:
        List of dicts with keys: name, allowed.
    """
    # In production, read from a permissions database.
    # For now, return empty — most apps haven't requested anything yet.
    return []


def _get_sentinel_log_entries(max_entries: int = 50) -> list:
    """
    Read recent Sentinel log entries.

    Returns:
        List of dicts with keys: timestamp, message.
    """
    try:
        if not os.path.exists(_SENTINEL_LOG_PATH):
            return []
        entries = []
        with open(_SENTINEL_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    # Expect format: "2026-04-04 14:30:00 - message"
                    parts = line.split(" - ", 1)
                    if len(parts) == 2:
                        entries.append({
                            "timestamp": parts[0],
                            "message": parts[1],
                        })
                    else:
                        entries.append({"timestamp": "", "message": line})
        return entries[-max_entries:]
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
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class PrivacyPanel(Gtk.Box):
        """Privacy settings: telemetry badge, permissions, Sentinel log."""

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_PRIVACY_CSS)
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
            title = Gtk.Label(label="Privacy")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- Telemetry badge ----
            self._build_telemetry_badge()

            # ---- Camera ----
            self._build_permission_section("Camera", "camera")

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Microphone ----
            self._build_permission_section("Microphone", "microphone")

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- Location ----
            self._build_permission_section("Location", "location")

            div3 = Gtk.Box()
            div3.add_css_class("luminos-section-divider")
            self.append(div3)

            # ---- Sentinel log ----
            self._build_sentinel_log()

        def _build_telemetry_badge(self):
            badge = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            badge.add_css_class("luminos-telemetry-badge")

            # Green dot
            dot = Gtk.Label(label="●")
            dot.set_markup(f"<span foreground='{COLOR_SUCCESS}'>●</span>")
            badge.append(dot)

            text_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            lbl = Gtk.Label(label="Telemetry")
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
                empty = Gtk.Label(label=f"No apps have requested {perm_type.lower()} access")
                empty.add_css_class("luminos-empty-state")
                empty.set_halign(Gtk.Align.START)
                self.append(empty)
            else:
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
                    row.append(switch)

                    self.append(row)

        def _build_sentinel_log(self):
            header = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            sec_title = Gtk.Label(label="Security Log")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            header.append(sec_title)

            sec_sub = Gtk.Label(label="Events flagged by Sentinel")
            sec_sub.add_css_class("luminos-setting-sublabel")
            sec_sub.set_halign(Gtk.Align.START)
            header.append(sec_sub)
            self.append(header)

            # Log view
            log_scroll = Gtk.ScrolledWindow()
            log_scroll.set_policy(
                Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
            )
            log_scroll.set_min_content_height(200)
            log_scroll.set_max_content_height(300)
            log_scroll.add_css_class("luminos-sentinel-log")
            log_scroll.set_margin_top(SPACE_3)

            self._log_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )

            entries = _get_sentinel_log_entries()
            if not entries:
                empty = Gtk.Label(label="No events logged")
                empty.add_css_class("luminos-empty-state")
                empty.set_halign(Gtk.Align.START)
                self._log_box.append(empty)
            else:
                for entry in entries:
                    line = f"{entry['timestamp']}  {entry['message']}"
                    lbl = Gtk.Label(label=line)
                    lbl.add_css_class("luminos-sentinel-entry")
                    lbl.set_halign(Gtk.Align.START)
                    lbl.set_selectable(True)
                    lbl.set_ellipsize(Pango.EllipsizeMode.END)
                    self._log_box.append(lbl)

            log_scroll.set_child(self._log_box)
            self.append(log_scroll)

            # Clear log button
            clear_btn = Gtk.Button(label="Clear Log")
            clear_btn.add_css_class("luminos-btn-destructive")
            clear_btn.set_halign(Gtk.Align.START)
            clear_btn.set_margin_top(SPACE_3)
            clear_btn.connect("clicked", self._on_clear_log)
            self.append(clear_btn)

        def _on_clear_log(self, _btn):
            try:
                if os.path.exists(_SENTINEL_LOG_PATH):
                    with open(_SENTINEL_LOG_PATH, "w") as f:
                        f.write("")
            except Exception as e:
                logger.debug(f"Clear log error: {e}")

            # Refresh display
            while (child := self._log_box.get_first_child()):
                self._log_box.remove(child)
            empty = Gtk.Label(label="No events logged")
            empty.add_css_class("luminos-empty-state")
            empty.set_halign(Gtk.Align.START)
            self._log_box.append(empty)

else:
    class PrivacyPanel:  # type: ignore[no-redef]
        pass
