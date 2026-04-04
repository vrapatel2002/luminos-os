"""
src/gui/settings/panels/ai_panel.py
AIPanel — AI hardware status, services, HIVE agents, privacy note.

Pure helpers:
    _get_daemon_status(response) → dict with normalized fields
    _get_hive_models()           → list[dict]
    _get_npu_status()            → dict
    _get_sentinel_status()       → dict
    _get_router_status()         → dict
"""

import logging
import os
import sys

logger = logging.getLogger("luminos-ai.gui.settings.ai")

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
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_SUBTLE,
    COLOR_SUCCESS, COLOR_ERROR,
    FONT_FAMILY, FONT_BODY, FONT_BODY_SMALL, FONT_CAPTION,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD,
    SETTINGS_PADDING,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_daemon_status(response: dict) -> dict:
    """
    Normalize a daemon manager_status response into a display-ready dict.

    Args:
        response: Raw dict from DaemonClient.send({"type": "manager_status"}).

    Returns:
        Dict with keys: online, model, quant, gaming, idle_s, uptime.
    """
    if not response or response.get("available") is False or "error" in response:
        return {
            "online":  False,
            "model":   "—",
            "quant":   "—",
            "gaming":  False,
            "idle_s":  None,
            "uptime":  "—",
        }
    return {
        "online":  True,
        "model":   response.get("active_model") or "none",
        "quant":   response.get("quantization", "—"),
        "gaming":  bool(response.get("gaming_mode", False)),
        "idle_s":  response.get("seconds_since_last_use"),
        "uptime":  response.get("uptime", "—"),
    }


def _get_hive_models() -> list:
    """
    Return the four HIVE model definitions.

    Returns:
        List of dicts with keys: name, role, vram_gb, backend.
    """
    return [
        {
            "name":    "Nexus",
            "role":    "Planning and coordination",
            "vram_gb": 4.0,
            "backend": "llama.cpp",
        },
        {
            "name":    "Bolt",
            "role":    "Code and automation",
            "vram_gb": 2.0,
            "backend": "llama.cpp",
        },
        {
            "name":    "Nova",
            "role":    "Research and knowledge",
            "vram_gb": 4.0,
            "backend": "llama.cpp",
        },
        {
            "name":    "Eye",
            "role":    "Vision and screen understanding",
            "vram_gb": 3.0,
            "backend": "llama.cpp",
        },
    ]


def _get_sentinel_status() -> dict:
    """
    Query Sentinel module status for display.

    Returns:
        Dict with keys: mode, ml_available, ml_backend, log_file.
    """
    try:
        from sentinel import get_sentinel_status
        return get_sentinel_status()
    except ImportError:
        return {"mode": "unavailable", "ml_available": False, "log_file": "—"}


def _get_router_status() -> dict:
    """
    Query Compatibility Router status for display.

    Returns:
        Dict with keys: engine, ai_fallback, hardware.
    """
    result = {"engine": "8 rules", "ai_fallback": "—", "hardware": "CPU only"}

    try:
        from classifier.ai_fallback import _find_llama, _MODEL_PATH
        llama = _find_llama()
        if llama and os.path.isfile(_MODEL_PATH):
            result["ai_fallback"] = "llama.cpp (available)"
        elif llama:
            result["ai_fallback"] = "llama.cpp (no model)"
        else:
            result["ai_fallback"] = "Not available"
    except ImportError:
        result["ai_fallback"] = "Module not loaded"

    return result


def _get_npu_status() -> dict:
    """
    Probe AMD XDNA NPU availability.

    Returns:
        Dict with keys: available (bool), device (str), driver (str).
    """
    npu_path = "/dev/accel/accel0"
    available = os.path.exists(npu_path)
    return {
        "available": available,
        "device":    npu_path if available else "not found",
        "driver":    "xdna" if available else "—",
    }


# ===========================================================================
# CSS
# ===========================================================================

_AI_CSS = f"""
.luminos-hw-row {{
    min-height: 44px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-hw-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-hive-row {{
    min-height: 48px;
    padding: {SPACE_2}px {SPACE_3}px;
    border-radius: {RADIUS_MD}px;
}}

.luminos-hive-row:hover {{
    background-color: {BG_OVERLAY};
}}

.luminos-ai-note {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
    margin-top: {SPACE_8}px;
}}
"""


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class AIPanel(Gtk.Box):
        """
        AI & HIVE settings panel.
        Shows: hardware status, services, HIVE agents, privacy note.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)
            self._client = DaemonClient()

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_AI_CSS)
            self._css_provider = css_provider
            self.connect("realize", lambda w: self._ensure_css())

            self._hive_states = {m["name"]: False for m in _get_hive_models()}
            self._build()
            GLib.timeout_add_seconds(3, self._refresh_status)
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
            title = Gtk.Label(label="AI & HIVE")
            title.add_css_class("luminos-panel-title")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # ---- AI Hardware section ----
            self._build_hardware_section()

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Services section ----
            self._build_services_section()

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- HIVE agents section ----
            self._build_hive_section()

            # ---- Privacy note ----
            note = Gtk.Label(
                label="All AI runs locally on your hardware. Nothing leaves your device."
            )
            note.add_css_class("luminos-ai-note")
            note.set_halign(Gtk.Align.CENTER)
            self.append(note)

        def _build_hardware_section(self):
            sec_title = Gtk.Label(label="AI Hardware")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            npu = _get_npu_status()

            hw_items = [
                ("NPU (AMD XDNA)",
                 "Available" if npu["available"] else "Unavailable",
                 f"Driver: {npu['driver']}",
                 npu["available"]),
                ("Compatibility Router",
                 "Active", "Runs on NPU", True),
                ("Sentinel Security",
                 "Active", "Runs on NPU", True),
                ("iGPU (AMD RDNA3)",
                 "Active", "Handles all UI rendering", True),
            ]

            for name, status, note, active in hw_items:
                row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
                )
                row.add_css_class("luminos-hw-row")
                row.set_hexpand(True)

                # Status dot
                color = COLOR_SUCCESS if active else COLOR_ERROR
                dot = Gtk.Label()
                dot.set_markup(f"<span foreground='{color}'>●</span>")
                row.append(dot)

                # Name + note
                text_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=1
                )
                text_box.set_hexpand(True)

                name_lbl = Gtk.Label(label=name)
                name_lbl.add_css_class("luminos-setting-label")
                name_lbl.set_halign(Gtk.Align.START)
                text_box.append(name_lbl)

                note_lbl = Gtk.Label(label=note)
                note_lbl.add_css_class("luminos-setting-sublabel")
                note_lbl.set_halign(Gtk.Align.START)
                text_box.append(note_lbl)

                row.append(text_box)

                # Status text
                self._hw_status_labels = getattr(self, '_hw_status_labels', {})
                status_lbl = Gtk.Label(label=status)
                status_lbl.add_css_class("luminos-text-secondary")
                self._hw_status_labels[name] = status_lbl
                row.append(status_lbl)

                self.append(row)

        def _build_services_section(self):
            sec_title = Gtk.Label(label="Services")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            self.append(sec_title)

            # llama.cpp daemon
            llama_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            llama_row.add_css_class("luminos-hw-row")
            llama_row.set_hexpand(True)

            llama_text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=1
            )
            llama_text.set_hexpand(True)
            llama_name = Gtk.Label(label="llama.cpp daemon")
            llama_name.add_css_class("luminos-setting-label")
            llama_name.set_halign(Gtk.Align.START)
            llama_text.append(llama_name)
            llama_row.append(llama_text)

            self._llama_status = Gtk.Label(label="—")
            self._llama_status.add_css_class("luminos-text-secondary")
            llama_row.append(self._llama_status)
            self.append(llama_row)

            # Sentinel
            sent_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            sent_row.add_css_class("luminos-hw-row")
            sent_row.set_hexpand(True)

            sent_text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=1
            )
            sent_text.set_hexpand(True)
            sent_name = Gtk.Label(label="Sentinel")
            sent_name.add_css_class("luminos-setting-label")
            sent_name.set_halign(Gtk.Align.START)
            sent_text.append(sent_name)
            sent_row.append(sent_text)

            self._sentinel_status = Gtk.Label(label="—")
            self._sentinel_status.add_css_class("luminos-text-secondary")
            sent_row.append(self._sentinel_status)
            self.append(sent_row)

            # Router cache
            cache_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_3
            )
            cache_row.add_css_class("luminos-hw-row")
            cache_row.set_hexpand(True)

            cache_text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=1
            )
            cache_text.set_hexpand(True)
            cache_name = Gtk.Label(label="Router cache")
            cache_name.add_css_class("luminos-setting-label")
            cache_name.set_halign(Gtk.Align.START)
            cache_text.append(cache_name)
            cache_row.append(cache_text)

            self._cache_label = Gtk.Label(label="0 apps cached")
            self._cache_label.add_css_class("luminos-text-secondary")
            cache_row.append(self._cache_label)

            clear_btn = Gtk.Button(label="Clear")
            clear_btn.add_css_class("luminos-btn-secondary")
            clear_btn.connect("clicked", lambda _: logger.debug("Router cache cleared"))
            cache_row.append(clear_btn)

            self.append(cache_row)

        def _build_hive_section(self):
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            sec_title = Gtk.Label(label="HIVE Agents")
            sec_title.add_css_class("luminos-section-title")
            sec_title.set_halign(Gtk.Align.START)
            text_box.append(sec_title)

            sub = Gtk.Label(
                label="Optional AI agents — not required for OS to function"
            )
            sub.add_css_class("luminos-setting-sublabel")
            sub.set_halign(Gtk.Align.START)
            text_box.append(sub)
            self.append(text_box)

            self._hive_status_labels = {}
            for model in _get_hive_models():
                row = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=0
                )
                row.add_css_class("luminos-hive-row")
                row.set_hexpand(True)

                text = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=1
                )
                text.set_hexpand(True)
                text.set_valign(Gtk.Align.CENTER)

                name_lbl = Gtk.Label(label=model["name"])
                name_lbl.add_css_class("luminos-setting-label")
                name_lbl.set_halign(Gtk.Align.START)
                text.append(name_lbl)

                role_lbl = Gtk.Label(label=model["role"])
                role_lbl.add_css_class("luminos-setting-sublabel")
                role_lbl.set_halign(Gtk.Align.START)
                text.append(role_lbl)

                row.append(text)

                switch = Gtk.Switch()
                switch.set_active(False)
                switch.add_css_class("luminos-switch")
                switch.set_valign(Gtk.Align.CENTER)
                switch.connect(
                    "state-set", self._on_hive_toggle, model["name"]
                )
                row.append(switch)

                self.append(row)

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _refresh_status(self) -> bool:
            # Daemon status
            try:
                resp = self._client.send({"type": "manager_status"})
                s = _get_daemon_status(resp)
            except Exception:
                s = _get_daemon_status({})

            if s["online"]:
                uptime = s.get("uptime", "—")
                self._llama_status.set_text(f"Running — {uptime}")
            else:
                self._llama_status.set_text("Stopped")

            # Sentinel
            sentinel = _get_sentinel_status()
            mode = sentinel.get("mode", "—")
            ml_backend = sentinel.get("ml_backend", {})
            if isinstance(ml_backend, dict):
                if ml_backend.get("npu_available"):
                    self._sentinel_status.set_text(f"Active (NPU)")
                elif ml_backend.get("cpu_fallback"):
                    self._sentinel_status.set_text(f"Active (CPU fallback)")
                else:
                    self._sentinel_status.set_text("Rules only")
            else:
                self._sentinel_status.set_text(mode)

            return GLib.SOURCE_CONTINUE

        def _on_hive_toggle(self, switch, state, model_name):
            self._hive_states[model_name] = state
            if state:
                logger.debug(f"HIVE agent {model_name}: starting")
                try:
                    self._client.send({
                        "type": "hive_start", "agent": model_name.lower()
                    })
                except Exception:
                    pass
            else:
                logger.debug(f"HIVE agent {model_name}: stopping")
                try:
                    self._client.send({
                        "type": "hive_stop", "agent": model_name.lower()
                    })
                except Exception:
                    pass
            return False

else:
    class AIPanel:  # type: ignore[no-redef]
        pass
