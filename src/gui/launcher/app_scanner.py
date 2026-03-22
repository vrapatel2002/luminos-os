"""
src/gui/launcher/app_scanner.py
Discovers installed applications from .desktop files and scores search results.

Rules:
- scan_applications() caches results for 60s — rescan on stale.
- predict_zone() uses exec heuristics first; classifier if available.
- search_apps() scores across name/comment/categories/exec, max 12 results.
- All functions never raise — return safe defaults on error.
"""

import configparser
import logging
import os
import re
import shutil
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
