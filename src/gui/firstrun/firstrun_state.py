"""
src/gui/firstrun/firstrun_state.py
Manages setup state across all First Run steps.

Rules:
- save_setup_state() / load_setup_state() never raise — fallback to defaults.
- mark_setup_complete() creates parent dirs if needed.
- is_setup_complete() is the single source of truth for whether firstrun ran.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("luminos-ai.gui.firstrun.state")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SETUP_STEPS: list[str] = [
    "welcome",
    "hardware",
    "display",
    "account",
    "appearance",
    "privacy",
    "ai_setup",
    "done",
]

SETUP_FLAG  = "~/.config/luminos/.setup_complete"
_STATE_PATH = "~/.config/luminos/setup_state.json"


# ---------------------------------------------------------------------------
# SetupState dataclass
# ---------------------------------------------------------------------------

@dataclass
class SetupState:
    """Holds all values collected during the First Run wizard."""

    current_step:      str  = "welcome"
    completed_steps:   list = field(default_factory=list)

    # Collected values
    username:          str  = ""
    password:          str  = ""
    avatar_color:      str  = "#0a84ff"
    dark_mode:         str  = "auto"   # "auto" | "dark" | "light"
    accent_color:      str  = "#0a84ff"
    brightness:        int  = 60
    scaling:           str  = "100%"
    telemetry_enabled: bool = False
    hive_enabled:      bool = True
    npu_detected:      bool = False
    nvidia_detected:   bool = False
    setup_complete:    bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_setup_complete() -> bool:
    """
    Return True if the first-run setup flag file exists.

    Returns:
        True if setup has already been completed, False otherwise.
    """
    return os.path.exists(os.path.expanduser(SETUP_FLAG))


def mark_setup_complete() -> None:
    """
    Create the setup flag file with a timestamp.

    Creates parent directories as needed.
    """
    path = os.path.expanduser(SETUP_FLAG)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"setup_complete={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        logger.info("Setup complete flag written.")
    except OSError as e:
        logger.warning(f"Failed to write setup flag: {e}")


def save_setup_state(state: SetupState) -> bool:
    """
    Persist the current SetupState to ~/.config/luminos/setup_state.json.

    Args:
        state: The SetupState instance to save.

    Returns:
        True on success, False on error.
    """
    path = os.path.expanduser(_STATE_PATH)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = asdict(state)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError as e:
        logger.warning(f"Failed to save setup state: {e}")
        return False


def load_setup_state() -> SetupState:
    """
    Load SetupState from ~/.config/luminos/setup_state.json.

    Returns:
        Populated SetupState on success, fresh SetupState on any error.
    """
    path = os.path.expanduser(_STATE_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return SetupState()
        # Only copy known fields, ignore extras
        known = {k for k in SetupState.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return SetupState(**filtered)
    except FileNotFoundError:
        return SetupState()
    except (json.JSONDecodeError, TypeError, OSError) as e:
        logger.warning(f"Failed to load setup state: {e}")
        return SetupState()
