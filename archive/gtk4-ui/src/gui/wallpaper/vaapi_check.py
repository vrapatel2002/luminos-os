"""
src/gui/wallpaper/vaapi_check.py
Detects VA-API hardware decode capability on the AMD iGPU.

Uses /dev/dri/renderD128 and `vainfo` CLI tool.
Never raises — returns {"available": False} on any error.
"""

import logging
import re
import subprocess

logger = logging.getLogger(__name__)

_DRI_DEVICE = "/dev/dri/renderD128"

# VA-API codec profile patterns in vainfo output
_CODEC_PATTERNS = {
    "H264": re.compile(r"VAProfile.*H264", re.IGNORECASE),
    "HEVC": re.compile(r"VAProfile.*HEVC|VAProfile.*H265", re.IGNORECASE),
    "VP9":  re.compile(r"VAProfile.*VP9",  re.IGNORECASE),
    "AV1":  re.compile(r"VAProfile.*AV1",  re.IGNORECASE),
}

_DRIVER_RE = re.compile(r"VA-API version.*\n.*Driver version:\s*(.+)", re.MULTILINE)
_DRIVER_RE_ALT = re.compile(r"vainfo:.*Driver:\s*(.+)", re.IGNORECASE)


def check_vaapi() -> dict:
    """
    Probe VA-API hardware decode capability.

    Returns:
        {
            "available": bool,
            "device":    str | None,   # /dev/dri/renderD128 or None
            "codecs":    list[str],    # ["H264", "HEVC", ...]
            "driver":    str | None,   # e.g. "iHD" or "radeonsi"
        }
    """
    import os as _os
    if not _os.path.exists(_DRI_DEVICE):
        return {"available": False, "device": None, "codecs": [], "driver": None}

    try:
        result = subprocess.run(
            ["vainfo", "--display", "drm", "--device", _DRI_DEVICE],
            capture_output=True,
            text=True,
            timeout=8,
        )
        output = result.stdout + result.stderr

        if result.returncode != 0 and not output.strip():
            return {"available": False, "device": None, "codecs": [], "driver": None}

        # Parse codecs
        codecs = [
            name for name, pattern in _CODEC_PATTERNS.items()
            if pattern.search(output)
        ]

        # Parse driver name
        driver: str | None = None
        m = _DRIVER_RE.search(output)
        if m:
            driver = m.group(1).strip()
        else:
            m2 = _DRIVER_RE_ALT.search(output)
            if m2:
                driver = m2.group(1).strip()

        available = bool(codecs)
        return {
            "available": available,
            "device":    _DRI_DEVICE if available else None,
            "codecs":    codecs,
            "driver":    driver,
        }

    except FileNotFoundError:
        # vainfo not installed
        logger.debug("vaapi_check: vainfo not found — VA-API unavailable")
        return {"available": False, "device": None, "codecs": [], "driver": None}
    except Exception as e:
        logger.debug(f"vaapi_check: probe failed — {e}")
        return {"available": False, "device": None, "codecs": [], "driver": None}


def get_decode_flags() -> list:
    """
    Return mpv decode flags based on VA-API availability.

    VA-API available  → hardware decode on iGPU via DRM/Wayland
    VA-API missing    → software CPU decode (still Wayland output)
    """
    info = check_vaapi()
    if info["available"]:
        return [
            "--hwdec=vaapi",
            "--vo=gpu",
            "--gpu-context=wayland",
        ]
    return [
        "--vo=gpu",
        "--gpu-context=wayland",
    ]
