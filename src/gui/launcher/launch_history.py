"""
src/gui/launcher/launch_history.py
Tracks recently launched applications for the Luminos launcher.

Rules:
- add_to_history() never raises.
- Duplicate exec entries are removed before prepending (most-recent-wins).
- Capped at MAX_HISTORY entries at all times.
- get_recent() returns [] if file is missing or corrupt.
"""

import json
import logging
import os
import time

logger = logging.getLogger("luminos-ai.gui.launcher.history")

HISTORY_PATH = os.path.expanduser("~/.config/luminos/launch_history.json")
MAX_HISTORY  = 20


def _load() -> list:
    """Load history list from disk. Returns [] on any error."""
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"History load error: {e}")
    return []


def _save(entries: list) -> None:
    """Persist history list to disk. Silently ignores errors."""
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
    except OSError as e:
        logger.debug(f"History save error: {e}")


def add_to_history(app: dict) -> None:
    """
    Prepend an app to the launch history.

    Removes any existing entry with the same exec field first (dedup).
    Trims to MAX_HISTORY after insertion.

    Args:
        app: App dict (name, exec, icon, …).
    """
    exec_key = app.get("exec", "")
    entries  = _load()

    # Remove existing entry for this exec
    entries = [e for e in entries if e.get("exec") != exec_key]

    # Prepend with timestamp
    entry = dict(app)
    entry["_launched_at"] = time.time()
    entries.insert(0, entry)

    # Enforce cap
    entries = entries[:MAX_HISTORY]
    _save(entries)


def get_recent(n: int = 8) -> list:
    """
    Return the n most recently launched apps.

    Args:
        n: Maximum entries to return (default 8).

    Returns:
        List of app dicts, most recent first. [] if history is empty.
    """
    return _load()[:n]


def clear_history() -> None:
    """Erase all launch history."""
    _save([])
