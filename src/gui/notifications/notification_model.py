"""
src/gui/notifications/notification_model.py
Notification data model — pure Python, no GTK, no display required.

Enums, dataclass, and pre-built constructor functions for common events.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class NotifLevel(Enum):
    INFO    = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER  = "danger"


class NotifCategory(Enum):
    SYSTEM  = "system"
    SENTINEL = "sentinel"
    AI      = "ai"
    POWER   = "power"
    NETWORK = "network"
    GAMING  = "gaming"
    ZONE    = "zone"


@dataclass
class Notification:
    """
    A single notification event.

    Fields:
        title:           Header text.
        body:            Detail text.
        level:           Visual severity (INFO / SUCCESS / WARNING / DANGER).
        category:        Source category for filtering.
        id:              8-hex-char unique identifier (auto-generated).
        timestamp:       Unix epoch float (auto-generated).
        auto_dismiss_ms: 0 = never auto-dismiss (e.g. Sentinel alerts).
        actions:         List of {"label": str, "key": str} dicts.
        dismissed:       True after the toast has been closed.
        read:            True after appearing in the history drawer.
    """
    title:           str
    body:            str
    level:           NotifLevel    = NotifLevel.INFO
    category:        NotifCategory = NotifCategory.SYSTEM
    id:              str           = field(
                         default_factory=lambda: uuid.uuid4().hex[:8]
                     )
    timestamp:       float         = field(default_factory=time.time)
    auto_dismiss_ms: int           = 5000
    actions:         list          = field(default_factory=list)
    dismissed:       bool          = False
    read:            bool          = False


# ===========================================================================
# Pre-built constructors for common events
# ===========================================================================

def sentinel_alert(process: str, threat: str) -> Notification:
    """Sentinel flagged a process — never auto-dismisses, has 3 actions."""
    return Notification(
        title="⚠ Sentinel Alert",
        body=f"{process} flagged as {threat}",
        level=NotifLevel.DANGER,
        category=NotifCategory.SENTINEL,
        auto_dismiss_ms=0,
        actions=[
            {"label": "Allow",      "key": "allow"},
            {"label": "Block",      "key": "block"},
            {"label": "Quarantine", "key": "quarantine"},
        ],
    )


def gaming_mode_on() -> Notification:
    """NVIDIA freed for gaming — GPU manager entered gaming mode."""
    return Notification(
        title="🎮 Gaming Mode Active",
        body="NVIDIA freed · AI models unloaded · Max performance",
        level=NotifLevel.INFO,
        category=NotifCategory.GAMING,
        auto_dismiss_ms=3000,
    )


def gaming_mode_off() -> Notification:
    """Game closed — GPU manager exited gaming mode."""
    return Notification(
        title="💤 Gaming Mode Off",
        body="Returning to idle · HIVE models reloading",
        level=NotifLevel.INFO,
        category=NotifCategory.GAMING,
        auto_dismiss_ms=3000,
    )


def zone3_launch(exe: str) -> Notification:
    """App requires kernel-level access — launching in Firecracker VM."""
    return Notification(
        title="⚠ Quarantine Launch",
        body=f"{exe} requires kernel access — running in VM",
        level=NotifLevel.WARNING,
        category=NotifCategory.ZONE,
        auto_dismiss_ms=8000,
        actions=[
            {"label": "OK",     "key": "ok"},
            {"label": "Cancel", "key": "cancel"},
        ],
    )


def thermal_warning(temp: float) -> Notification:
    """CPU/GPU temperature exceeded throttle threshold."""
    return Notification(
        title="🌡 High Temperature",
        body=f"System at {temp:.0f}°C · Reducing performance",
        level=NotifLevel.WARNING,
        category=NotifCategory.POWER,
        auto_dismiss_ms=8000,
    )


def model_loaded(model: str, quant: str) -> Notification:
    """AI model successfully loaded into VRAM."""
    return Notification(
        title="🤖 AI Model Ready",
        body=f"{model}-{quant} loaded to NVIDIA VRAM",
        level=NotifLevel.SUCCESS,
        category=NotifCategory.AI,
        auto_dismiss_ms=2000,
    )
