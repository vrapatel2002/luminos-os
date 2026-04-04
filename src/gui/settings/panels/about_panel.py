"""
src/gui/settings/panels/about_panel.py
AboutPanel — Luminos identity, hardware summary, software info, legal.

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

from gui.theme.luminos_theme import (
    BG_ELEVATED, BG_OVERLAY,
    ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER_SUBTLE,
    FONT_FAMILY, FONT_H1, FONT_BODY, FONT_BODY_SMALL,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    RADIUS_MD,
    SETTINGS_PADDING,
)

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
        Dict with keys: os, kernel, compositor, python, uptime_s.
    """
    compositor = "Hyprland"
    try:
        result = subprocess.run(
            ["hyprctl", "version", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            compositor = f"Hyprland {data.get('tag', '')}"
    except Exception:
        pass

    try:
        with open("/proc/uptime") as f:
            uptime_s = float(f.read().split()[0])
    except Exception:
        uptime_s = 0.0

    return {
        "os":         "Luminos OS",
        "kernel":     _get_kernel_version(),
        "compositor": compositor,
        "python":     platform.python_version(),
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
        f"Python    : {sys_['python']}",
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
# CSS
# ===========================================================================

_ABOUT_CSS = f"""
.luminos-about-logo {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 48px;
    font-weight: 700;
    color: {ACCENT};
}}

.luminos-about-name {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_H1}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

.luminos-about-version {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_SECONDARY};
}}

.luminos-about-arch {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY_SMALL}px;
    color: {TEXT_SECONDARY};
}}

.luminos-info-grid {{
    margin-top: {SPACE_3}px;
}}

.luminos-info-key {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_SECONDARY};
    min-width: 100px;
}}

.luminos-info-val {{
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {FONT_BODY}px;
    color: {TEXT_PRIMARY};
}}

.luminos-legal {{
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

    class AboutPanel(Gtk.Box):
        """
        About Luminos panel.
        Shows: identity block, hardware, software, legal.
        """

        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_margin_top(SETTINGS_PADDING)
            self.set_margin_bottom(SETTINGS_PADDING)
            self.set_margin_start(SETTINGS_PADDING)
            self.set_margin_end(SETTINGS_PADDING)

            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_ABOUT_CSS)
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
            # ---- Identity block ----
            identity = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2
            )
            identity.set_halign(Gtk.Align.START)
            identity.set_margin_bottom(SPACE_8)

            # Logo placeholder — "L" in accent
            logo = Gtk.Label(label="L")
            logo.add_css_class("luminos-about-logo")
            logo.set_halign(Gtk.Align.START)
            identity.append(logo)

            name = Gtk.Label(label="Luminos")
            name.add_css_class("luminos-about-name")
            name.set_halign(Gtk.Align.START)
            identity.append(name)

            version = Gtk.Label(label=f"Version {_LUMINOS_VERSION}")
            version.add_css_class("luminos-about-version")
            version.set_halign(Gtk.Align.START)
            identity.append(version)

            arch = Gtk.Label(label="Built on Arch Linux")
            arch.add_css_class("luminos-about-arch")
            arch.set_halign(Gtk.Align.START)
            identity.append(arch)

            self.append(identity)

            div1 = Gtk.Box()
            div1.add_css_class("luminos-section-divider")
            self.append(div1)

            # ---- Hardware section ----
            hw_title = Gtk.Label(label="This Device")
            hw_title.add_css_class("luminos-section-title")
            hw_title.set_halign(Gtk.Align.START)
            self.append(hw_title)

            hw = _get_hardware_info()
            hw_grid = Gtk.Grid()
            hw_grid.set_row_spacing(8)
            hw_grid.set_column_spacing(SPACE_6)
            hw_grid.add_css_class("luminos-info-grid")

            hw_items = [
                ("Device", "ASUS ROG Zephyrus G14"),
                ("CPU",     hw["cpu"]),
                ("GPU",     hw["gpu"]),
                ("NPU",     hw["npu"]),
                ("RAM",     f"{hw['ram_gb']} GB"),
                ("Storage", f"{hw['storage_gb']:.0f} GB"),
            ]

            for row, (key, val) in enumerate(hw_items):
                k = Gtk.Label(label=key)
                k.add_css_class("luminos-info-key")
                k.set_halign(Gtk.Align.START)
                hw_grid.attach(k, 0, row, 1, 1)
                v = Gtk.Label(label=str(val))
                v.add_css_class("luminos-info-val")
                v.set_halign(Gtk.Align.START)
                v.set_selectable(True)
                hw_grid.attach(v, 1, row, 1, 1)

            self.append(hw_grid)

            div2 = Gtk.Box()
            div2.add_css_class("luminos-section-divider")
            self.append(div2)

            # ---- Software section ----
            sw_title = Gtk.Label(label="Software")
            sw_title.add_css_class("luminos-section-title")
            sw_title.set_halign(Gtk.Align.START)
            self.append(sw_title)

            sys_info = _get_system_info()
            sw_grid = Gtk.Grid()
            sw_grid.set_row_spacing(8)
            sw_grid.set_column_spacing(SPACE_6)
            sw_grid.add_css_class("luminos-info-grid")

            sw_items = [
                ("Kernel",      sys_info["kernel"]),
                ("Compositor",  sys_info["compositor"]),
                ("Python",      sys_info["python"]),
            ]

            for row, (key, val) in enumerate(sw_items):
                k = Gtk.Label(label=key)
                k.add_css_class("luminos-info-key")
                k.set_halign(Gtk.Align.START)
                sw_grid.attach(k, 0, row, 1, 1)
                v = Gtk.Label(label=str(val))
                v.add_css_class("luminos-info-val")
                v.set_halign(Gtk.Align.START)
                v.set_selectable(True)
                sw_grid.attach(v, 1, row, 1, 1)

            self.append(sw_grid)

            # ---- Legal ----
            legal = Gtk.Label(
                label="Open source. Privacy first. No telemetry."
            )
            legal.add_css_class("luminos-legal")
            legal.set_halign(Gtk.Align.CENTER)
            self.append(legal)

else:
    class AboutPanel:  # type: ignore[no-redef]
        pass
