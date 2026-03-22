"""
window_manager.py
Zone-aware window management for Luminos compositor layer.

Rules:
- Each zone has fixed visual treatment (border, XWayland, label, opacity).
- Zone 3 always gets red border + QUARANTINE label — no exceptions.
- WindowManager is stateful; one instance lives for the daemon lifetime.
- Never raises — all failures returned as structured dicts.
"""

import time
import logging

logger = logging.getLogger("luminos-ai.compositor.window_manager")

# Zone → display rules. Immutable policy — do not override per-window.
ZONE_WINDOW_RULES = {
    1: {"border": "none",  "xwayland": False, "label": None,          "opacity": 1.0},
    2: {"border": "blue",  "xwayland": True,  "label": "Wine",        "opacity": 1.0},
    3: {"border": "red",   "xwayland": False, "label": "QUARANTINE",  "opacity": 0.95},
}


class WindowManager:
    """
    Tracks live windows and their zone-derived display properties.

    Windows are keyed by PID. A window is registered when its process
    launches and unregistered when it exits.
    """

    def __init__(self):
        self.windows: dict[int, dict] = {}   # pid → window_info
        self.active_pid: int | None = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_window(self, pid: int, exe_path: str, zone: int) -> dict:
        """
        Register a new window and assign zone-derived display rules.

        Args:
            pid:      Process ID of the window owner.
            exe_path: Path to the executable being displayed.
            zone:     Zone number (1, 2, or 3).

        Returns:
            window_info dict with all display properties.
        """
        rules = ZONE_WINDOW_RULES.get(zone, ZONE_WINDOW_RULES[1])
        window_info = {
            "pid":           pid,
            "exe":           exe_path,
            "zone":          zone,
            "border":        rules["border"],
            "xwayland":      rules["xwayland"],
            "label":         rules["label"],
            "opacity":       rules["opacity"],
            "registered_at": time.monotonic(),
        }
        self.windows[pid] = window_info
        logger.info(
            f"Window registered: pid={pid} zone={zone} "
            f"border={rules['border']} xwayland={rules['xwayland']} "
            f"label={rules['label']!r}"
        )
        return window_info

    def unregister_window(self, pid: int) -> dict:
        """
        Remove a window from tracking.

        Returns:
            {"removed": bool, "pid": int}
        """
        removed = pid in self.windows
        if removed:
            self.windows.pop(pid)
            logger.info(f"Window unregistered: pid={pid}")
            if self.active_pid == pid:
                self.active_pid = None
                logger.info("Active window cleared (process exited)")
        else:
            logger.debug(f"unregister_window: pid={pid} not found — no-op")
        return {"removed": removed, "pid": pid}

    # ------------------------------------------------------------------
    # Focus
    # ------------------------------------------------------------------

    def focus_window(self, pid: int) -> dict:
        """
        Set the active (focused) window.

        Returns:
            {"focused": int, "zone": int, "label": str|None}
            or {"error": str, "pid": int} if pid unknown.
        """
        if pid not in self.windows:
            logger.warning(f"focus_window: pid={pid} not registered")
            return {"error": "window not registered", "pid": pid}
        self.active_pid = pid
        info = self.windows[pid]
        logger.info(f"Focus: pid={pid} zone={info['zone']}")
        return {
            "focused": pid,
            "zone":    info["zone"],
            "label":   info["label"],
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_windows(self) -> list:
        """Return all registered window_info dicts as a list."""
        return list(self.windows.values())

    def get_zone_summary(self) -> dict:
        """
        Count registered windows per zone.

        Returns:
            {"zone1": int, "zone2": int, "zone3": int, "total": int}
        """
        counts = {1: 0, 2: 0, 3: 0}
        for info in self.windows.values():
            z = info.get("zone", 1)
            if z in counts:
                counts[z] += 1
        return {
            "zone1": counts[1],
            "zone2": counts[2],
            "zone3": counts[3],
            "total": len(self.windows),
        }
