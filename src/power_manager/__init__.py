"""
src/power_manager/__init__.py
Public API for the Luminos PowerBrain.

One brain. No static profiles. No context mapping.

Usage:
    from power_manager import set_mode, get_status, list_modes
    result = set_mode("quiet")
    # {"mode": "quiet", "description": "Silent — typing, music, calls", "decision": {...}}
"""

from .powerbrain           import _brain, MANUAL_PROFILES
from .ac_monitor           import get_ac_status
from .thermal_monitor      import get_thermal_level, get_cpu_temp, get_gpu_temp
from .process_intelligence import is_gaming_running


def set_mode(mode: str) -> dict:
    """Set power mode: 'auto' | 'quiet' | 'balanced' | 'max'."""
    return _brain.set_mode(mode)


def get_status() -> dict:
    """Full snapshot: mode, last decision, AC, thermal, gaming, recent log."""
    return _brain.get_status()


def force_apply() -> dict:
    """Immediately re-evaluate and apply power settings."""
    return _brain.apply_current_decision()


def list_modes() -> dict:
    """Return all available modes with descriptions."""
    return {
        "auto": "Smart automatic switching",
        **{k: v["description"] for k, v in MANUAL_PROFILES.items()},
    }
