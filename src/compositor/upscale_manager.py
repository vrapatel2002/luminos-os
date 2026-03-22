"""
upscale_manager.py
AMD FSR/NIS upscaling configuration for Luminos iGPU display layer.

Rules:
- iGPU owns the display — always.
- Upscaling reduces render resolution; compositor reconstructs to native.
- "off" = native render, no upscaling overhead.
- detect_display() reads /sys first; falls back to xrandr if available.
- Never raises — missing display or tool returns {"available": False, ...}.
"""

import glob
import logging
import os
import re
import subprocess

logger = logging.getLogger("luminos-ai.compositor.upscale")

UPSCALE_MODES = {
    "off":         {"ratio": 1.0,  "quality": "native"},
    "quality":     {"ratio": 0.77, "quality": "FSR Quality"},
    "balanced":    {"ratio": 0.67, "quality": "FSR Balanced"},
    "performance": {"ratio": 0.50, "quality": "FSR Performance"},
}


def detect_display() -> dict:
    """
    Detect connected display via /sys/class/drm or xrandr.

    Tries /sys/class/drm/*/modes first (no display server needed).
    Falls back to `xrandr --current` if available.

    Returns:
        {
            "available":   bool,
            "resolution":  str|None,     e.g. "2560x1440"
            "refresh_hz":  int|None,
            "connector":   str|None,     e.g. "eDP-1"
        }
    """
    # --- /sys/class/drm probe ---
    drm_modes_paths = sorted(glob.glob("/sys/class/drm/*/modes"))
    for modes_path in drm_modes_paths:
        try:
            with open(modes_path) as f:
                content = f.read().strip()
            if not content:
                continue
            first_line = content.splitlines()[0].strip()
            # connector name is the directory component after "card*-"
            connector = os.path.basename(os.path.dirname(modes_path))
            # Strip "card0-", "card1-" prefix → e.g. "eDP-1"
            connector = re.sub(r"^card\d+-", "", connector)
            # resolution is "WIDTHxHEIGHT" — no Hz here in /sys/class/drm/modes
            resolution = first_line if re.match(r"\d+x\d+", first_line) else None
            if resolution:
                logger.debug(f"Display detected via /sys: {connector} {resolution}")
                return {
                    "available":  True,
                    "resolution": resolution,
                    "refresh_hz": None,   # /sys/class/drm/modes doesn't include Hz
                    "connector":  connector,
                }
        except OSError:
            continue

    # --- xrandr fallback ---
    try:
        result = subprocess.run(
            ["xrandr", "--current"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                # e.g. "eDP-1 connected 2560x1440+0+0 (normal left inverted right ...) ... 60Hz"
                m = re.search(r"(\S+) connected.*?(\d+x\d+)\+\d+\+\d+", line)
                if m:
                    connector  = m.group(1)
                    resolution = m.group(2)
                    hz_match   = re.search(r"(\d+)(?:\.\d+)?\*", result.stdout)
                    refresh_hz = int(hz_match.group(1)) if hz_match else None
                    logger.debug(f"Display detected via xrandr: {connector} {resolution}")
                    return {
                        "available":  True,
                        "resolution": resolution,
                        "refresh_hz": refresh_hz,
                        "connector":  connector,
                    }
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    logger.debug("No display detected — headless or no display server")
    return {
        "available":  False,
        "resolution": None,
        "refresh_hz": None,
        "connector":  None,
    }


def _parse_resolution(resolution: str | None) -> tuple[int, int] | None:
    """Parse 'WxH' string → (w, h) or None."""
    if not resolution:
        return None
    m = re.match(r"(\d+)x(\d+)", resolution)
    return (int(m.group(1)), int(m.group(2))) if m else None


class UpscaleManager:
    """
    Manages AMD FSR/NIS upscaling mode for the iGPU display path.

    Setting a mode configures the render resolution ratio — the compositor
    renders at (ratio × native_resolution) and upscales to native.
    """

    def __init__(self):
        self.current_mode:       str         = "off"
        self.target_resolution:  str | None  = None

    def set_mode(self, mode: str) -> dict:
        """
        Set upscaling mode.

        Args:
            mode: One of UPSCALE_MODES keys.

        Returns:
            {
                "mode":         str,
                "quality":      str,
                "render_ratio": float,
                "render_resolution": str|None,
                "note":         str,
            }
            or {"error": str, "valid_modes": list} on bad mode.
        """
        if mode not in UPSCALE_MODES:
            return {
                "error":       f"unknown upscale mode: {mode!r}",
                "valid_modes": list(UPSCALE_MODES.keys()),
            }

        spec             = UPSCALE_MODES[mode]
        self.current_mode = mode

        # Calculate rendered resolution if we know the display
        render_resolution = None
        display = detect_display()
        if display["available"] and display["resolution"]:
            parsed = _parse_resolution(display["resolution"])
            if parsed:
                w, h = parsed
                rw   = int(w * spec["ratio"])
                rh   = int(h * spec["ratio"])
                render_resolution = f"{rw}x{rh}"

        logger.info(
            f"Upscale mode → {mode} ({spec['quality']}) "
            f"ratio={spec['ratio']} render={render_resolution}"
        )
        return {
            "mode":              mode,
            "quality":           spec["quality"],
            "render_ratio":      spec["ratio"],
            "render_resolution": render_resolution,
            "note":              "Applied — takes effect on next frame",
        }

    def get_status(self) -> dict:
        """
        Current upscale state plus live display info.

        Returns:
            {
                "current_mode":    str,
                "display":         detect_display() result,
                "available_modes": list,
            }
        """
        return {
            "current_mode":    self.current_mode,
            "display":         detect_display(),
            "available_modes": list(UPSCALE_MODES.keys()),
        }
