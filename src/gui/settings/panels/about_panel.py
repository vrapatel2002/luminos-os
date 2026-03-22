"""
src/gui/settings/panels/about_panel.py
AboutPanel — Luminos identity, hardware summary, system info, licenses,
             export diagnostics.

Pure helpers:
    _get_kernel_version()     → str
    _get_hardware_info()      → dict
    _get_system_info()        → dict
    _export_report(path)      → str   (path written to)
"""

import logging
import os
import platform
import subprocess
import sys
import time

logger = logging.getLogger("luminos-ai.gui.settings.about")

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

_LUMINOS_VERSION = "0.9.0-alpha"


# ===========================================================================
# Pure helpers
# ===========================================================================

def _get_kernel_version() -> str:
    """
    Return the running kernel version string.

    Returns:
        e.g. "6.17.0-19-generic" or "unknown".
    """
    try:
        return platform.release()
    except Exception:
        return "unknown"


def _get_hardware_info() -> dict:
    """
    Collect hardware summary from /proc and external tools.

    Returns:
        Dict with keys: cpu, ram_gb, igpu, gpu, npu, storage_gb.
    """
    result = {
        "cpu":        _read_cpu_model(),
        "ram_gb":     _read_ram_gb(),
        "igpu":       _probe_igpu(),
        "gpu":        _probe_nvidia_gpu(),
        "npu":        "AMD XDNA" if os.path.exists("/dev/accel/accel0") else "Not found",
        "storage_gb": _read_storage_gb(),
    }
    return result


def _get_system_info() -> dict:
    """
    Return OS / compositor / uptime info.

    Returns:
        Dict with keys: os, kernel, compositor, uptime_s.
    """
    try:
        compositor = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "unknown"
    except Exception:
        compositor = "unknown"

    try:
        with open("/proc/uptime") as f:
            uptime_s = float(f.read().split()[0])
    except Exception:
        uptime_s = 0.0

    return {
        "os":         "Luminos OS",
        "kernel":     _get_kernel_version(),
        "compositor": compositor,
        "uptime_s":   uptime_s,
    }


def _export_report(path: str | None = None) -> str:
    """
    Write a diagnostic report to a file.

    Args:
        path: Output path. Defaults to ~/luminos-diagnostics.txt.

    Returns:
        Path the report was written to.
    """
    if path is None:
        path = os.path.expanduser(f"~/luminos-diagnostics-{int(time.time())}.txt")

    hw   = _get_hardware_info()
    sys_ = _get_system_info()
    lines = [
        "=== Luminos Diagnostics Report ===",
        f"Luminos Version : {_LUMINOS_VERSION}",
        f"Date            : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "--- Hardware ---",
        f"CPU      : {hw['cpu']}",
        f"RAM      : {hw['ram_gb']} GB",
        f"iGPU     : {hw['igpu']}",
        f"GPU      : {hw['gpu']}",
        f"NPU      : {hw['npu']}",
        f"Storage  : {hw['storage_gb']} GB",
        "",
        "--- System ---",
        f"OS        : {sys_['os']}",
        f"Kernel    : {sys_['kernel']}",
        f"Compositor: {sys_['compositor']}",
        f"Uptime    : {sys_['uptime_s']:.0f}s",
    ]

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        logger.warning(f"Failed to write diagnostics: {e}")

    return path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "Unknown CPU"


def _read_ram_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 1)
    except Exception:
        pass
    return 0.0


def _probe_igpu() -> str:
    try:
        out = subprocess.check_output(
            ["lspci", "-nn"], stderr=subprocess.DEVNULL, timeout=3,
            text=True
        )
        for line in out.splitlines():
            if "VGA" in line or "Display" in line:
                if "AMD" in line or "Intel" in line or "Radeon" in line:
                    return line.split(":")[-1].strip()
    except Exception:
        pass
    return "Unknown iGPU"


def _probe_nvidia_gpu() -> str:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL, timeout=3, text=True
        )
        return out.strip().splitlines()[0] if out.strip() else "Not found"
    except Exception:
        return "Not found"


def _read_storage_gb() -> float:
    try:
        stat = os.statvfs("/")
        total_bytes = stat.f_blocks * stat.f_frsize
        return round(total_bytes / 1024 ** 3, 0)
    except Exception:
        return 0.0


def _format_uptime(seconds: float) -> str:
    """Format uptime seconds into a human-readable string."""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h {m}m"


# ===========================================================================
# GTK Panel
# ===========================================================================

if _GTK_AVAILABLE:

    class AboutPanel(Gtk.Box):
        """
        About Luminos panel.

        Shows: version, hardware summary, system info, licenses,
        export diagnostics button.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
            self.set_margin_top(24)
            self.set_margin_bottom(24)
            self.set_margin_start(32)
            self.set_margin_end(32)
            self._build()

        def _build(self):
            # ---- Identity ----
            logo_lbl = Gtk.Label(label="◉ Luminos")
            logo_lbl.add_css_class("luminos-bar-logo")
            logo_lbl.set_halign(Gtk.Align.START)
            self.append(logo_lbl)

            ver_lbl = Gtk.Label(label=f"Version {_LUMINOS_VERSION}")
            ver_lbl.add_css_class("luminos-qs-dim")
            ver_lbl.set_halign(Gtk.Align.START)
            self.append(ver_lbl)

            self.append(Gtk.Separator())

            # ---- Hardware summary ----
            hw_lbl = Gtk.Label(label="Hardware")
            hw_lbl.add_css_class("luminos-settings-section-title")
            hw_lbl.set_halign(Gtk.Align.START)
            self.append(hw_lbl)

            hw = _get_hardware_info()
            hw_grid = Gtk.Grid()
            hw_grid.set_row_spacing(6)
            hw_grid.set_column_spacing(24)
            for row, (key, val) in enumerate((
                ("CPU",     hw["cpu"]),
                ("RAM",     f"{hw['ram_gb']} GB"),
                ("iGPU",    hw["igpu"]),
                ("GPU",     hw["gpu"]),
                ("NPU",     hw["npu"]),
                ("Storage", f"{hw['storage_gb']:.0f} GB"),
            )):
                k = Gtk.Label(label=key)
                k.add_css_class("luminos-qs-dim")
                k.set_halign(Gtk.Align.START)
                hw_grid.attach(k, 0, row, 1, 1)
                v = Gtk.Label(label=str(val))
                v.set_halign(Gtk.Align.START)
                v.set_selectable(True)
                hw_grid.attach(v, 1, row, 1, 1)
            self.append(hw_grid)

            self.append(Gtk.Separator())

            # ---- System info ----
            sys_lbl = Gtk.Label(label="System")
            sys_lbl.add_css_class("luminos-settings-section-title")
            sys_lbl.set_halign(Gtk.Align.START)
            self.append(sys_lbl)

            sys_info = _get_system_info()
            sys_grid = Gtk.Grid()
            sys_grid.set_row_spacing(6)
            sys_grid.set_column_spacing(24)
            for row, (key, val) in enumerate((
                ("Kernel",      sys_info["kernel"]),
                ("Compositor",  sys_info["compositor"]),
                ("Uptime",      _format_uptime(sys_info["uptime_s"])),
            )):
                k = Gtk.Label(label=key)
                k.add_css_class("luminos-qs-dim")
                k.set_halign(Gtk.Align.START)
                sys_grid.attach(k, 0, row, 1, 1)
                v = Gtk.Label(label=str(val))
                v.set_halign(Gtk.Align.START)
                sys_grid.attach(v, 1, row, 1, 1)
            self.append(sys_grid)

            self.append(Gtk.Separator())

            # ---- Export diagnostics ----
            export_btn = Gtk.Button(label="Export Diagnostics Report…")
            export_btn.add_css_class("luminos-btn")
            export_btn.set_halign(Gtk.Align.START)
            export_btn.connect("clicked", self._on_export)
            self.append(export_btn)

            self._export_status = Gtk.Label(label="")
            self._export_status.set_halign(Gtk.Align.START)
            self._export_status.add_css_class("luminos-qs-dim")
            self.append(self._export_status)

        def _on_export(self, *_):
            path = _export_report()
            self._export_status.set_text(f"Saved: {path}")

else:
    class AboutPanel:  # type: ignore[no-redef]
        pass
