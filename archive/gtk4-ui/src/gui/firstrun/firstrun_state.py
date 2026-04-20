"""
src/gui/firstrun/firstrun_state.py
Phase 5.9 — First Run Experience state management.

Flag file:  ~/.config/luminos/first_run_complete
State file: ~/.config/luminos/firstrun_state.json

Rules:
- save_state() / load_state() never raise — fallback to defaults.
- mark_complete() creates parent dirs as needed.
- is_complete() is the single source of truth.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("luminos.firstrun.state")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIRST_RUN_FLAG = os.path.expanduser("~/.config/luminos/first_run_complete")
_STATE_PATH    = os.path.expanduser("~/.config/luminos/firstrun_state.json")

SCREENS: list[str] = ["welcome", "account", "wallpaper", "ready"]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class FirstRunState:
    """Values collected across the 4 first-run screens."""

    current_screen:  str  = "welcome"
    completed:       bool = False

    # Screen 2 — Account
    username:        str  = ""
    password:        str  = ""

    # Screen 3 — Wallpaper
    wallpaper_type:  str  = ""   # "static" | "video" | "live"
    wallpaper_value: str  = ""   # file path or preset name
    wallpaper_index: int  = -1   # selected thumbnail index (-1 = none)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_complete() -> bool:
    """Return True if first_run_complete flag file exists."""
    return os.path.exists(FIRST_RUN_FLAG)


def mark_complete() -> None:
    """Create the first_run_complete flag file."""
    try:
        os.makedirs(os.path.dirname(FIRST_RUN_FLAG), exist_ok=True)
        with open(FIRST_RUN_FLAG, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S\n"))
        logger.info("First run complete flag written.")
    except OSError as e:
        logger.warning(f"Failed to write first_run_complete: {e}")


def save_state(state: FirstRunState) -> None:
    """Persist state to disk (best-effort)."""
    try:
        os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, indent=2)
    except OSError as e:
        logger.debug(f"Failed to save firstrun state: {e}")


def load_state() -> FirstRunState:
    """Load state from disk, returning fresh state on any error."""
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return FirstRunState()
        known = set(FirstRunState.__dataclass_fields__)
        return FirstRunState(**{k: v for k, v in data.items() if k in known})
    except FileNotFoundError:
        return FirstRunState()
    except Exception as e:
        logger.debug(f"Failed to load firstrun state: {e}")
        return FirstRunState()
