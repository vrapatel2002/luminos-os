"""
src/gui/wallpaper/swww_controller.py
Controls the swww Wayland wallpaper daemon.

All functions are headless-safe and never raise —
failures are returned as {"success": False, "error": ...}.
"""

import logging
import os
import struct
import subprocess
import tempfile
import time

logger = logging.getLogger(__name__)

_SWWW_SOCKET_GLOB = "/tmp/swww-*.socket"
_DEVNULL = subprocess.DEVNULL


def _find_swww_socket() -> str | None:
    """Return the path of the swww socket if it exists, else None."""
    import glob
    matches = glob.glob(_SWWW_SOCKET_GLOB)
    return matches[0] if matches else None


def is_swww_running() -> bool:
    """
    Return True if swww-daemon process is running.
    Uses `pgrep swww-daemon` — no exceptions.
    """
    try:
        result = subprocess.run(
            ["pgrep", "swww-daemon"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


def start_swww() -> bool:
    """
    Start swww-daemon if it isn't already running.
    Waits up to 2 seconds for the socket to appear.
    Returns True when swww is ready, False on failure.
    """
    if is_swww_running():
        return True
    try:
        subprocess.Popen(
            ["swww-daemon"],
            stdout=_DEVNULL,
            stderr=_DEVNULL,
        )
    except FileNotFoundError:
        logger.debug("start_swww: swww-daemon not found")
        return False
    except Exception as e:
        logger.debug(f"start_swww: Popen failed — {e}")
        return False

    # Wait up to 2 s for socket to appear
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if is_swww_running():
            return True
        time.sleep(0.1)
    return is_swww_running()


def set_image_wallpaper(
    path: str,
    transition: str = "fade",
    duration_ms: int = 800,
) -> dict:
    """
    Set a static image wallpaper via `swww img`.

    Args:
        path:         Absolute path to the image file.
        transition:   swww transition type (fade / wipe / grow).
        duration_ms:  Transition duration in milliseconds.

    Returns:
        {"success": bool, "error": str | None}
    """
    if not start_swww():
        return {"success": False, "error": "swww-daemon could not be started"}

    duration_s = duration_ms / 1000.0
    cmd = [
        "swww", "img", path,
        "--transition-type",     transition,
        "--transition-duration", str(duration_s),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {"success": True, "error": None}
        return {"success": False, "error": result.stderr.strip() or "swww img failed"}
    except FileNotFoundError:
        return {"success": False, "error": "swww not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def set_color_wallpaper(hex_color: str) -> dict:
    """
    Set a solid colour wallpaper.

    Creates a 1×1 PNG of the given hex colour in /tmp/ and passes it to
    set_image_wallpaper().

    Args:
        hex_color: CSS hex colour, e.g. "#1c1c1e" or "1c1c1e".

    Returns:
        {"success": bool, "error": str | None}
    """
    color = hex_color.lstrip("#")
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
    except (ValueError, IndexError):
        return {"success": False, "error": f"Invalid hex colour: {hex_color}"}

    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, dir="/tmp"
        )
        tmp_path = tmp.name
        tmp.close()

        # Write a minimal 1×1 8-bit RGB PNG
        _write_1x1_png(tmp_path, r, g, b)

        result = set_image_wallpaper(tmp_path, transition="none", duration_ms=0)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def kill_swww() -> None:
    """Terminate swww-daemon and clean up its socket."""
    try:
        subprocess.run(["pkill", "swww-daemon"], capture_output=True, timeout=5)
    except Exception:
        pass
    import glob
    for sock in glob.glob(_SWWW_SOCKET_GLOB):
        try:
            os.unlink(sock)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Internal PNG writer (stdlib only — no Pillow dependency)
# ---------------------------------------------------------------------------

def _write_1x1_png(path: str, r: int, g: int, b: int) -> None:
    """
    Write a valid 1×1 RGB PNG file using only stdlib (zlib + struct).
    This avoids requiring Pillow/imagemagick for the colour-wallpaper path.
    """
    import zlib

    def _chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        crc = zlib.crc32(name + data) & 0xFFFFFFFF
        return c + struct.pack(">I", crc)

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    # Scanline: filter byte 0 + RGB
    raw_row   = bytes([0, r, g, b])
    idat_data = zlib.compress(raw_row)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr_data)
        + _chunk(b"IDAT", idat_data)
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)
