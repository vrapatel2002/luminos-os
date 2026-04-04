"""
src/gui/dock/dock_config.py
Persists the Luminos dock pinned apps list to ~/.config/luminos/dock.json.

Rules:
- load_pinned() never raises — falls back to DEFAULT_PINNED on any error.
- save_pinned() creates parent dirs if needed.
- Duplicate detection uses the "exec" field as the unique key.
"""

import json
import logging
import os

logger = logging.getLogger("luminos-ai.gui.dock.config")

CONFIG_PATH = os.path.expanduser("~/.config/luminos/dock.json")

DEFAULT_PINNED: list[dict] = [
    {"name": "Files",    "exec": "nautilus",         "icon": "system-file-manager"},
    {"name": "Terminal", "exec": "foot",             "icon": "terminal"},
    {"name": "Firefox",  "exec": "firefox",          "icon": "firefox"},
    {"name": "Store",    "exec": "luminos-store",    "icon": "system-software-install"},
    {"name": "Settings", "exec": "luminos-settings", "icon": "preferences-system"},
]


def load_pinned() -> list:
    """
    Load pinned apps from CONFIG_PATH.

    Returns:
        List of app dicts (name, exec, icon).
        Falls back to DEFAULT_PINNED if file is missing or corrupt.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
        logger.debug("dock.json empty or wrong type — using defaults")
    except FileNotFoundError:
        logger.debug("dock.json not found — using defaults")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read dock.json: {e} — using defaults")
    return list(DEFAULT_PINNED)


def save_pinned(apps: list) -> bool:
    """
    Write pinned apps list to CONFIG_PATH.

    Args:
        apps: List of app dicts to persist.

    Returns:
        True on success, False on error.
    """
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)
        return True
    except OSError as e:
        logger.warning(f"Failed to save dock.json: {e}")
        return False


def add_pinned(app: dict) -> list:
    """
    Add an app to the pinned list if not already present.

    Uniqueness is determined by the "exec" field.

    Args:
        app: Dict with at minimum {"name": ..., "exec": ..., "icon": ...}.

    Returns:
        Updated pinned list.
    """
    apps = load_pinned()
    exec_name = app.get("exec", "")
    if not any(a.get("exec") == exec_name for a in apps):
        apps.append(app)
        save_pinned(apps)
    return apps


def remove_pinned(exec_name: str) -> list:
    """
    Remove an app from the pinned list by exec name.

    Args:
        exec_name: The "exec" value of the app to remove.

    Returns:
        Updated pinned list (unchanged if exec_name not found).
    """
    apps = load_pinned()
    updated = [a for a in apps if a.get("exec") != exec_name]
    if len(updated) != len(apps):
        save_pinned(updated)
    return updated
