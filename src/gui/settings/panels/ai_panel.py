"""
src/gui/settings/panels/ai_panel.py
AIPanel — daemon status, HIVE model table, NPU status, inference settings.

Pure helpers:
    _get_daemon_status(response) → dict with normalized fields
    _get_hive_models()           → list[dict]
    _get_npu_status()            → dict
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
            "role":    "General reasoning",
            "vram_gb": 4.0,
            "backend": "llama.cpp",
        },
        {
            "name":    "Bolt",
            "role":    "Fast completions",
            "vram_gb": 2.0,
            "backend": "llama.cpp",
        },
        {
            "name":    "Nova",
            "role":    "Code generation",
            "vram_gb": 4.0,
            "backend": "llama.cpp",
        },
        {
            "name":    "Eye",
            "role":    "Vision / multimodal",
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
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class AIPanel(Gtk.Box):
        """
        AI & HIVE settings panel.

        Shows: daemon status card (3s update), HIVE model table,
        NPU status, inference settings, gaming mode toggle.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            self.set_margin_top(24)
            self.set_margin_bottom(24)
            self.set_margin_start(32)
            self.set_margin_end(32)
            self._client = DaemonClient()
            self._build()
            GLib.timeout_add_seconds(3, self._refresh_status)
            self._refresh_status()

        def _build(self):
            # ---- Daemon status ----
            daemon_lbl = Gtk.Label(label="Luminos AI Daemon")
            daemon_lbl.add_css_class("luminos-settings-section-title")
            daemon_lbl.set_halign(Gtk.Align.START)
            self.append(daemon_lbl)

            status_grid = Gtk.Grid()
            status_grid.set_row_spacing(6)
            status_grid.set_column_spacing(24)

            self._status_online = self._grid_row(status_grid, 0, "Status")
            self._status_model  = self._grid_row(status_grid, 1, "Active model")
            self._status_gaming = self._grid_row(status_grid, 2, "Gaming mode")
            self._status_idle   = self._grid_row(status_grid, 3, "Idle since")
            self.append(status_grid)

            self.append(Gtk.Separator())

            # ---- HIVE model table ----
            hive_lbl = Gtk.Label(label="HIVE Models")
            hive_lbl.add_css_class("luminos-settings-section-title")
            hive_lbl.set_halign(Gtk.Align.START)
            self.append(hive_lbl)

            models_grid = Gtk.Grid()
            models_grid.set_row_spacing(6)
            models_grid.set_column_spacing(24)

            for col, header in enumerate(("Model", "Role", "VRAM", "Backend")):
                h = Gtk.Label(label=header)
                h.add_css_class("luminos-power-card-name")
                h.set_halign(Gtk.Align.START)
                models_grid.attach(h, col, 0, 1, 1)

            for row, m in enumerate(_get_hive_models(), start=1):
                for col, val in enumerate((
                    m["name"], m["role"],
                    f"{m['vram_gb']:.0f} GB", m["backend"]
                )):
                    cell = Gtk.Label(label=val)
                    cell.set_halign(Gtk.Align.START)
                    models_grid.attach(cell, col, row, 1, 1)

            self.append(models_grid)

            self.append(Gtk.Separator())

            # ---- NPU status ----
            npu_lbl = Gtk.Label(label="NPU (XDNA)")
            npu_lbl.add_css_class("luminos-settings-section-title")
            npu_lbl.set_halign(Gtk.Align.START)
            self.append(npu_lbl)

            npu = _get_npu_status()
            npu_status = Gtk.Label(
                label=f"{'Available' if npu['available'] else 'Not found'} — "
                      f"Device: {npu['device']}, Driver: {npu['driver']}"
            )
            npu_status.set_halign(Gtk.Align.START)
            npu_status.add_css_class("luminos-qs-dim")
            self.append(npu_status)

            self.append(Gtk.Separator())

            # ---- Sentinel status ----
            sentinel_lbl = Gtk.Label(label="Sentinel (Security Monitor)")
            sentinel_lbl.add_css_class("luminos-settings-section-title")
            sentinel_lbl.set_halign(Gtk.Align.START)
            self.append(sentinel_lbl)

            sentinel_grid = Gtk.Grid()
            sentinel_grid.set_row_spacing(6)
            sentinel_grid.set_column_spacing(24)
            self._sentinel_mode    = self._grid_row(sentinel_grid, 0, "Mode")
            self._sentinel_ml      = self._grid_row(sentinel_grid, 1, "ML backend")
            self._sentinel_log     = self._grid_row(sentinel_grid, 2, "Log file")
            self.append(sentinel_grid)

            self.append(Gtk.Separator())

            # ---- Compatibility Router ----
            router_lbl = Gtk.Label(label="Compatibility Router")
            router_lbl.add_css_class("luminos-settings-section-title")
            router_lbl.set_halign(Gtk.Align.START)
            self.append(router_lbl)

            router_grid = Gtk.Grid()
            router_grid.set_row_spacing(6)
            router_grid.set_column_spacing(24)
            self._router_engine = self._grid_row(router_grid, 0, "Rule engine")
            self._router_ai     = self._grid_row(router_grid, 1, "AI fallback")
            self._router_hw     = self._grid_row(router_grid, 2, "Hardware")
            self.append(router_grid)

            self.append(Gtk.Separator())

            # ---- GPU mode guard ----
            gpu_lbl = Gtk.Label(label="GPU Mode (supergfxctl)")
            gpu_lbl.add_css_class("luminos-settings-section-title")
            gpu_lbl.set_halign(Gtk.Align.START)
            self.append(gpu_lbl)

            gpu_grid = Gtk.Grid()
            gpu_grid.set_row_spacing(6)
            gpu_grid.set_column_spacing(24)
            self._gpu_mode   = self._grid_row(gpu_grid, 0, "Current mode")
            self._gpu_status = self._grid_row(gpu_grid, 1, "Status")
            self.append(gpu_grid)

            self.append(Gtk.Separator())

            # ---- Gaming mode ----
            gaming_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            gaming_row.set_hexpand(True)
            g_lbl = Gtk.Label(label="Gaming mode (pause AI inference)")
            g_lbl.set_hexpand(True)
            g_lbl.set_halign(Gtk.Align.START)
            self._gaming_switch = Gtk.Switch()
            self._gaming_switch.set_active(False)
            self._gaming_switch.connect("state-set", self._on_gaming_toggle)
            gaming_row.append(g_lbl)
            gaming_row.append(self._gaming_switch)
            self.append(gaming_row)

        def _grid_row(self, grid: Gtk.Grid, row: int, label: str) -> Gtk.Label:
            key = Gtk.Label(label=label)
            key.set_halign(Gtk.Align.START)
            key.add_css_class("luminos-qs-dim")
            grid.attach(key, 0, row, 1, 1)
            val = Gtk.Label(label="—")
            val.set_halign(Gtk.Align.START)
            grid.attach(val, 1, row, 1, 1)
            return val

        def _refresh_status(self) -> bool:
            # Daemon + model status
            try:
                resp = self._client.send({"type": "manager_status"})
                s = _get_daemon_status(resp)
            except Exception:
                s = _get_daemon_status({})

            self._status_online.set_text("Online" if s["online"] else "Offline")
            self._status_model.set_text(
                f"{s['model']} ({s['quant']})" if s["online"] else "—"
            )
            self._status_gaming.set_text("Yes" if s["gaming"] else "No")
            idle = s["idle_s"]
            self._status_idle.set_text(
                f"{idle}s" if idle is not None else "—"
            )

            # Sentinel status
            sentinel = _get_sentinel_status()
            self._sentinel_mode.set_text(sentinel.get("mode", "—"))
            ml_backend = sentinel.get("ml_backend", {})
            if isinstance(ml_backend, dict):
                if ml_backend.get("npu_available"):
                    self._sentinel_ml.set_text("NPU (AMD XDNA)")
                elif ml_backend.get("cpu_fallback"):
                    self._sentinel_ml.set_text("CPU (fallback)")
                else:
                    self._sentinel_ml.set_text("Rules only")
            else:
                self._sentinel_ml.set_text("Rules only")
            self._sentinel_log.set_text(sentinel.get("log_file", "—"))

            # Router status
            router = _get_router_status()
            self._router_engine.set_text(router.get("engine", "—"))
            self._router_ai.set_text(router.get("ai_fallback", "—"))
            self._router_hw.set_text(router.get("hardware", "—"))

            # GPU mode guard
            gpu_mode = resp.get("gpu_mode", {}) if s["online"] else {}
            mode_str = gpu_mode.get("mode", "—")
            is_hybrid = gpu_mode.get("is_hybrid", False)
            self._gpu_mode.set_text(mode_str if mode_str else "—")
            if gpu_mode.get("supergfxctl_available"):
                self._gpu_status.set_text(
                    "Hybrid (correct)" if is_hybrid else f"WARNING: {mode_str}"
                )
            else:
                self._gpu_status.set_text("supergfxctl not available")

            return GLib.SOURCE_CONTINUE

        def _on_gaming_toggle(self, _switch, state):
            try:
                req_type = "gaming_on" if state else "gaming_off"
                self._client.send({"type": req_type})
            except Exception as e:
                logger.debug(f"gaming toggle error: {e}")
            return False

else:
    class AIPanel:  # type: ignore[no-redef]
        pass
