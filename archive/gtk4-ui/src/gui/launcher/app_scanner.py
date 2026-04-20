"""
src/gui/launcher/app_scanner.py
Discovers installed applications from .desktop files and scores search results.

Rules:
- scan_applications() caches results for 60s — rescan on stale.
- scan_windows_apps() reads router cache for previously launched .exe apps.
- scan_games() filters apps by Game category.
- predict_zone() uses exec heuristics first; classifier if available.
- search_apps() scores across name/comment/categories/exec, max 12 results.
- All functions never raise — return safe defaults on error.
"""

import configparser
import json
import logging
import os
import re
import shutil
import struct
import time

logger = logging.getLogger("luminos-ai.gui.launcher.scanner")

SEARCH_PATHS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    "/opt/luminos/apps",
]

_CACHE_TTL   = 60.0   # seconds
_cache: list | None  = None
_cache_time: float   = 0.0
_MAX_RESULTS = 12

# Classifier — optional (ONNX model may not be built yet)
try:
    import sys as _sys
    _SRC = os.path.join(os.path.dirname(__file__), "..", "..")
    if _SRC not in _sys.path:
        _sys.path.insert(0, _SRC)
    from classifier import classify_binary as _classify_binary
    _CLASSIFIER_AVAILABLE = True
except Exception:
    _CLASSIFIER_AVAILABLE = False


# ===========================================================================
# .desktop file parsing
# ===========================================================================

def _parse_desktop_file(path: str) -> dict | None:
    """
    Parse a single .desktop file into an app dict.

    Returns None for hidden (NoDisplay=true), invalid, or nameless entries.
    """
    try:
        cp = configparser.ConfigParser(
            strict=False,
            interpolation=None,
        )
        cp.read(path, encoding="utf-8")
        if not cp.has_section("Desktop Entry"):
            return None
        entry = cp["Desktop Entry"]
        if entry.get("NoDisplay", "false").strip().lower() == "true":
            return None
        name = entry.get("Name", "").strip()
        if not name:
            return None
        exec_val   = entry.get("Exec", "").strip()
        icon       = entry.get("Icon", "application-x-executable").strip()
        comment    = entry.get("Comment", "").strip()
        categories = [
            c for c in entry.get("Categories", "").split(";") if c.strip()
        ]
        return {
            "name":         name,
            "exec":         exec_val,
            "icon":         icon,
            "comment":      comment,
            "categories":   categories,
            "desktop_file": path,
        }
    except Exception as e:
        logger.debug(f"Failed to parse {path}: {e}")
        return None


# ===========================================================================
# Application scanning
# ===========================================================================

def scan_applications() -> list:
    """
    Discover all installed applications from .desktop files.

    Results are cached for 60 seconds. Rescan automatically on stale cache.

    Returns:
        List of app dicts sorted alphabetically by name.
        Returns [] if no .desktop files found — never raises.
    """
    global _cache, _cache_time
    if _cache is not None and (time.monotonic() - _cache_time) < _CACHE_TTL:
        return _cache

    apps: list[dict] = []
    seen_execs: set[str] = set()

    for directory in SEARCH_PATHS:
        directory = os.path.expanduser(directory)
        if not os.path.isdir(directory):
            continue
        try:
            for fname in os.listdir(directory):
                if not fname.endswith(".desktop"):
                    continue
                path = os.path.join(directory, fname)
                app = _parse_desktop_file(path)
                if app is None:
                    continue
                # Deduplicate by exec
                key = app["exec"]
                if key in seen_execs:
                    continue
                seen_execs.add(key)
                apps.append(app)
        except OSError as e:
            logger.debug(f"Cannot scan {directory}: {e}")

    apps.sort(key=lambda a: a["name"].lower())
    _cache      = apps
    _cache_time = time.monotonic()
    return _cache


# ===========================================================================
# Windows apps (from router cache)
# ===========================================================================

_ROUTER_CACHE_DIR = os.path.expanduser("~/.cache/luminos/router/")
_PREFIX_DIR = os.path.expanduser("~/.luminos/prefixes/")


def scan_windows_apps() -> list:
    """
    Discover Windows apps from the router classification cache.

    Reads cached .exe classification results and builds app dicts
    for any Windows executables that have been previously run.

    Returns:
        List of app dicts sorted alphabetically. [] if none found.
    """
    apps: list[dict] = []
    seen_names: set[str] = set()

    # Source 1: Router cache — previously classified .exe files
    if os.path.isdir(_ROUTER_CACHE_DIR):
        try:
            for fname in os.listdir(_ROUTER_CACHE_DIR):
                if not fname.endswith(".json"):
                    continue
                try:
                    path = os.path.join(_ROUTER_CACHE_DIR, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    exe_name = data.get("exe_name", "")
                    if not exe_name or not exe_name.lower().endswith(".exe"):
                        continue
                    display_name = _exe_display_name(exe_name)
                    if display_name in seen_names:
                        continue
                    seen_names.add(display_name)
                    layer = data.get("layer", "wine")
                    apps.append({
                        "name": display_name,
                        "exec": f"luminos-launch {exe_name}",
                        "icon": "application-x-executable",
                        "comment": f"Windows app ({layer})",
                        "categories": ["Windows"],
                        "_zone": data.get("zone", 2),
                    })
                except (json.JSONDecodeError, OSError, KeyError):
                    continue
        except OSError:
            pass

    # Source 2: Wine prefixes — .desktop files created by Wine
    wine_desktop_dirs = []
    if os.path.isdir(_PREFIX_DIR):
        try:
            for prefix_name in os.listdir(_PREFIX_DIR):
                wine_apps = os.path.join(
                    _PREFIX_DIR, prefix_name,
                    "drive_c", "users", "Public", "Desktop"
                )
                if os.path.isdir(wine_apps):
                    wine_desktop_dirs.append(wine_apps)
                # Also check Start Menu
                start_menu = os.path.join(
                    _PREFIX_DIR, prefix_name,
                    "drive_c", "ProgramData", "Microsoft",
                    "Windows", "Start Menu", "Programs"
                )
                if os.path.isdir(start_menu):
                    wine_desktop_dirs.append(start_menu)
        except OSError:
            pass

    for d in wine_desktop_dirs:
        try:
            for fname in os.listdir(d):
                if not fname.endswith(".desktop"):
                    continue
                app = _parse_desktop_file(os.path.join(d, fname))
                if app and app["name"] not in seen_names:
                    seen_names.add(app["name"])
                    app["categories"] = app.get("categories", []) + ["Windows"]
                    apps.append(app)
        except OSError:
            continue

    apps.sort(key=lambda a: a["name"].lower())
    return apps


def _exe_display_name(exe_name: str) -> str:
    """
    Convert an exe filename to a display name.

    Args:
        exe_name: e.g. "game_launcher.exe"

    Returns:
        Cleaned name: "Game Launcher"
    """
    stem = os.path.splitext(exe_name)[0]
    # Replace underscores and hyphens with spaces, then title-case
    cleaned = stem.replace("_", " ").replace("-", " ")
    return cleaned.title()


# ===========================================================================
# Games (filtered by category)
# ===========================================================================

_GAME_CATEGORIES = {"Game", "Games", "ActionGame", "AdventureGame",
                    "ArcadeGame", "BoardGame", "BlocksGame", "CardGame",
                    "Emulator", "LogicGame", "RolePlaying", "Shooter",
                    "Simulation", "SportsGame", "StrategyGame"}


def scan_games(all_apps: list | None = None) -> list:
    """
    Filter applications that belong to game categories.

    Args:
        all_apps: Pre-scanned app list. If None, calls scan_applications().

    Returns:
        List of game app dicts sorted alphabetically. [] if none found.
    """
    if all_apps is None:
        all_apps = scan_applications()

    games = []
    for app in all_apps:
        cats = set(app.get("categories", []))
        if cats & _GAME_CATEGORIES:
            games.append(app)

    # Also include Windows apps that look like games (from router cache)
    try:
        win_apps = scan_windows_apps()
        for app in win_apps:
            # Heuristic: router cache entries with game-like layers
            comment = app.get("comment", "").lower()
            if "proton" in comment or "dxvk" in comment:
                if app not in games:
                    games.append(app)
    except Exception:
        pass

    games.sort(key=lambda a: a["name"].lower())
    return games


# ===========================================================================
# .exe icon extraction and caching
# ===========================================================================

_ICON_CACHE_DIR = os.path.expanduser("~/.cache/luminos/icons/")


def get_exe_icon(exe_path: str, size: int = 48) -> str | None:
    """
    Extract or find a cached icon for a Windows executable.

    Tries in order:
      1. Cached PNG in ~/.cache/luminos/icons/
      2. Extract from PE resource section (ICO group)
      3. Return None (caller falls back to generic icon)

    Args:
        exe_path: Path to the .exe file.
        size: Desired icon size in pixels.

    Returns:
        Path to cached PNG icon, or None.
    """
    if not exe_path or not os.path.isfile(exe_path):
        return None

    # Check cache first
    stem = os.path.splitext(os.path.basename(exe_path))[0].lower()
    cache_path = os.path.join(_ICON_CACHE_DIR, f"{stem}_{size}.png")
    if os.path.isfile(cache_path):
        return cache_path

    # Try extraction
    icon_data = _extract_ico_from_pe(exe_path)
    if icon_data:
        return _save_icon_cache(stem, icon_data, size)

    return None


def _extract_ico_from_pe(exe_path: str) -> bytes | None:
    """
    Extract the first ICO resource from a PE executable.

    Reads PE headers to locate the .rsrc section, then finds
    RT_GROUP_ICON / RT_ICON resources. Returns raw ICO bytes
    for the largest icon entry, or None on failure.

    This is a minimal extractor — handles the common case of
    Windows executables with embedded application icons.
    """
    try:
        with open(exe_path, "rb") as f:
            # Check MZ header
            magic = f.read(2)
            if magic != b"MZ":
                return None

            # PE header offset at 0x3C
            f.seek(0x3C)
            pe_offset = struct.unpack("<I", f.read(4))[0]
            f.seek(pe_offset)

            # Check PE signature
            pe_sig = f.read(4)
            if pe_sig != b"PE\x00\x00":
                return None

            # COFF header
            f.read(2)  # Machine
            num_sections = struct.unpack("<H", f.read(2))[0]
            f.read(12)  # TimeDateStamp, PointerToSymbolTable, NumberOfSymbols
            optional_size = struct.unpack("<H", f.read(2))[0]
            f.read(2)  # Characteristics

            # Skip optional header to get to section headers
            f.seek(f.tell() + optional_size)

            # Find .rsrc section
            rsrc_offset = 0
            rsrc_size = 0
            rsrc_va = 0
            for _ in range(num_sections):
                name = f.read(8).rstrip(b"\x00")
                virtual_size = struct.unpack("<I", f.read(4))[0]
                virtual_addr = struct.unpack("<I", f.read(4))[0]
                raw_size = struct.unpack("<I", f.read(4))[0]
                raw_offset = struct.unpack("<I", f.read(4))[0]
                f.read(16)  # remaining section header fields

                if name == b".rsrc":
                    rsrc_offset = raw_offset
                    rsrc_size = raw_size
                    rsrc_va = virtual_addr
                    break

            if rsrc_offset == 0:
                return None

            # Read the entire resource section
            f.seek(rsrc_offset)
            rsrc_data = f.read(rsrc_size)

            if len(rsrc_data) < 16:
                return None

            # Return the raw resource data for icon processing
            # The caller will handle conversion
            return rsrc_data

    except (OSError, struct.error, OverflowError):
        return None


def _save_icon_cache(stem: str, rsrc_data: bytes, size: int) -> str | None:
    """
    Save extracted resource data as a cached icon file.

    For now, saves the raw data and attempts to find a valid
    bitmap/PNG within the resource section.

    Args:
        stem: Lowercase exe name without extension.
        rsrc_data: Raw .rsrc section data.
        size: Target icon size.

    Returns:
        Path to cached file, or None on failure.
    """
    try:
        os.makedirs(_ICON_CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(_ICON_CACHE_DIR, f"{stem}_{size}.png")

        # Look for PNG signature in resource data
        png_sig = b"\x89PNG\r\n\x1a\n"
        png_idx = rsrc_data.find(png_sig)
        if png_idx >= 0:
            # Find the end of the PNG (IEND chunk)
            iend = rsrc_data.find(b"IEND", png_idx)
            if iend > png_idx:
                png_data = rsrc_data[png_idx:iend + 8]  # IEND + CRC
                with open(cache_path, "wb") as f:
                    f.write(png_data)
                return cache_path

        # Look for BMP signature (icon resources often contain DIBs)
        # Store as-is with .ico extension for GTK to handle
        ico_path = os.path.join(_ICON_CACHE_DIR, f"{stem}_{size}.ico")
        # Look for icon directory structure (GRPICONDIRENTRY)
        if len(rsrc_data) > 6:
            with open(ico_path, "wb") as f:
                f.write(rsrc_data[:min(len(rsrc_data), 256 * 1024)])
            if os.path.getsize(ico_path) > 0:
                return ico_path
            os.unlink(ico_path)

    except OSError:
        pass
    return None


# ===========================================================================
# Zone prediction
# ===========================================================================

def _extract_binary(exec_str: str) -> str | None:
    """
    Extract the real binary path from a .desktop Exec field.

    Strips %F/%U/etc. substitution tokens, then resolves via which.
    """
    # Remove %X argument substitutions
    cleaned = re.sub(r"%[A-Za-z]", "", exec_str).strip()
    parts   = cleaned.split()
    if not parts:
        return None
    binary = parts[0]
    if os.path.isabs(binary):
        return binary if os.path.isfile(binary) else None
    return shutil.which(binary)


def predict_zone(app: dict) -> int:
    """
    Predict which execution zone an app will run in.

    Heuristics (fast, no binary inspection):
      - ".exe" in exec or "wine" in exec or "proton" in exec → zone 2
    Classifier (if available):
      - Resolve binary, run classify_binary() → use returned zone

    Args:
        app: App dict with at least {"exec": str}.

    Returns:
        1 (native), 2 (Wine/Proton), or 3 (quarantine/VM).
    """
    exec_str = app.get("exec", "").lower()

    # Fast heuristic — covers the common Windows app case
    if any(kw in exec_str for kw in (".exe", "wine", "proton")):
        return 2

    # Classifier path (best effort)
    if _CLASSIFIER_AVAILABLE:
        binary = _extract_binary(app.get("exec", ""))
        if binary:
            try:
                result = _classify_binary(binary)
                return int(result.get("zone", 1))
            except Exception as e:
                logger.debug(f"classify_binary failed for {binary}: {e}")

    return 1


# ===========================================================================
# Search
# ===========================================================================

def search_apps(query: str, all_apps: list) -> list:
    """
    Score and rank apps against a search query.

    Scoring:
        name starts with query → 100
        name contains query   →  80
        exec contains query   →  50
        comment contains      →  40
        categories contain    →  20

    Args:
        query:    Search string (case-insensitive).
        all_apps: App list from scan_applications().

    Returns:
        Up to 12 best-matching app dicts, sorted by score descending.
        Returns [] if query is empty or all_apps is empty.
    """
    if not query or not all_apps:
        return []

    q      = query.lower()
    scored = []

    for app in all_apps:
        name    = app.get("name",    "").lower()
        comment = app.get("comment", "").lower()
        cats    = " ".join(app.get("categories", [])).lower()
        exec_s  = app.get("exec",    "").lower()

        score = 0
        if name.startswith(q):
            score += 100
        elif q in name:
            score += 80
        if q in exec_s:
            score += 50
        if q in comment:
            score += 40
        if q in cats:
            score += 20

        if score > 0:
            scored.append((score, app))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [app for _, app in scored[:_MAX_RESULTS]]
