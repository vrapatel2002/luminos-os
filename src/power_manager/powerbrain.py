"""
powerbrain.py
Single unified power decision engine for Luminos.

No static profile fallback. No context mapping. One brain.

Philosophy:
- Gaming always wins — max power, full NVIDIA, no questions.
- Thermal emergency always overrides manual mode.
- Battery discipline: <20% → quiet unconditionally.
- Auto mode re-evaluates every 10 seconds via background thread.
- Manual mode is always subject to thermal emergency override.
"""

import logging
import threading
import time

from .ac_monitor          import get_ac_status
from .thermal_monitor     import get_thermal_level
from .process_intelligence import is_gaming_running
from .power_writer        import set_cpu_governor, set_nvidia_power_limit

logger = logging.getLogger("luminos-ai.power_manager.brain")

_MAX_LOG = 30

MANUAL_PROFILES: dict[str, dict] = {
    "quiet": {
        "governor":       "powersave",
        "nvidia_percent": 0,
        "fan":            "auto_quiet",
        "description":    "Silent — typing, music, calls",
    },
    "balanced": {
        "governor":       "schedutil",
        "nvidia_percent": 50,
        "fan":            "auto",
        "description":    "General use — coding, browsing",
    },
    "max": {
        "governor":       "performance",
        "nvidia_percent": 100,
        "fan":            "max",
        "description":    "Full speed — heavy tasks",
    },
}

# Convenience aliases used in _auto_decide
_QUIET   = {"governor": "powersave",    "nvidia_percent": 0,   "fan": "auto_quiet"}
_BALANCED = {"governor": "schedutil",   "nvidia_percent": 50,  "fan": "auto"}
_MAX     = {"governor": "performance",  "nvidia_percent": 100, "fan": "max"}

_VALID_MODES = {"auto", "quiet", "balanced", "max"}


class PowerBrain:
    """
    The single power authority for Luminos.

    Modes:
      "auto"     — self-driving: reads AC, thermal, gaming every 10s
      "quiet"    — user override, still subject to thermal emergency
      "balanced" — user override, still subject to thermal emergency
      "max"      — user override, still subject to thermal emergency
    """

    def __init__(self):
        self.mode:          str        = "auto"
        self.last_decision: dict       = {}
        self.decision_log:  list[dict] = []   # capped at _MAX_LOG

    # ------------------------------------------------------------------
    # Public: mode selection
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> dict:
        """
        Set operating mode. Triggers an immediate decision apply.

        Args:
            mode: "auto" | "quiet" | "balanced" | "max"

        Returns:
            {"mode": str, "description": str, "decision": dict}
            or {"error": str, "valid_modes": list}
        """
        if mode not in _VALID_MODES:
            return {
                "error":       f"Unknown mode: {mode!r}",
                "valid_modes": sorted(_VALID_MODES),
            }

        self.mode = mode
        logger.info(f"PowerBrain mode → {mode}")

        if mode == "auto":
            description = "Smart automatic switching"
        else:
            description = MANUAL_PROFILES[mode]["description"]

        decision = self.apply_current_decision()
        return {
            "mode":        mode,
            "description": description,
            "decision":    decision,
        }

    # ------------------------------------------------------------------
    # Core: auto decision logic
    # ------------------------------------------------------------------

    def _auto_decide(self, ac: dict, thermal: str, gaming: bool) -> dict:
        """
        Pure decision function — no side effects, no I/O.

        Args:
            ac:      Result of get_ac_status()
            thermal: Result of get_thermal_level()
            gaming:  Result of is_gaming_running()

        Returns:
            Decision dict: {"governor", "nvidia_percent", "fan", "reason"}
        """
        # Gaming always wins — unconditionally
        if gaming:
            return {**_MAX, "reason": "gaming detected"}

        plugged_in = ac.get("plugged_in", True)
        bat_pct    = ac.get("battery_percent")

        if plugged_in:
            if thermal == "emergency":
                return {**_QUIET,    "reason": f"plugged in — thermal emergency ({thermal})"}
            elif thermal in ("warn", "throttle"):
                return {**_BALANCED, "reason": f"plugged in — thermal {thermal}, reduced load"}
            else:
                return {**_MAX,      "reason": "plugged in — thermal normal, full power"}
        else:
            # Battery path
            if thermal == "emergency":
                return {**_QUIET, "reason": f"battery — thermal emergency ({thermal}), forced quiet"}

            if bat_pct is not None and bat_pct < 20:
                logger.warning(f"Battery critical: {bat_pct}%")
                return {**_QUIET, "reason": f"battery critical ({bat_pct}%) — quiet forced"}

            if bat_pct is None or bat_pct <= 50:
                return {**_QUIET, "reason": f"battery ({bat_pct}%) — quiet to preserve charge"}

            # >50% and no thermal concern
            return {**_BALANCED, "reason": f"battery ({bat_pct}%) — balanced to preserve charge"}

    # ------------------------------------------------------------------
    # Core: apply
    # ------------------------------------------------------------------

    def apply_current_decision(self) -> dict:
        """
        Evaluate current state and apply the appropriate power settings.

        Returns:
            The decision dict that was applied.
        """
        if self.mode == "auto":
            ac      = get_ac_status()
            thermal = get_thermal_level()
            gaming  = is_gaming_running()
            decision = self._auto_decide(ac, thermal, gaming)
        else:
            # Manual mode — copy profile, still check thermal emergency
            decision = dict(MANUAL_PROFILES[self.mode])
            thermal  = get_thermal_level()
            if thermal == "emergency":
                logger.warning(
                    f"Thermal emergency while in manual mode '{self.mode}' "
                    "— overriding to quiet"
                )
                decision = {
                    **_QUIET,
                    "reason": "thermal emergency override — manual ignored",
                }
            else:
                decision["reason"] = f"manual mode: {self.mode}"

        # Apply via power_writer
        set_cpu_governor(decision["governor"])
        set_nvidia_power_limit(decision["nvidia_percent"])

        logger.info(
            f"[PowerBrain] mode={self.mode} governor={decision['governor']} "
            f"nvidia={decision['nvidia_percent']}% reason={decision.get('reason','')!r}"
        )

        # Record in log
        entry = {**decision, "timestamp": time.monotonic(), "mode": self.mode}
        self.decision_log.append(entry)
        if len(self.decision_log) > _MAX_LOG:
            self.decision_log = self.decision_log[-_MAX_LOG:]

        self.last_decision = decision
        return decision

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Full snapshot of current power state.

        Returns:
            {
                "mode":             str,
                "auto_or_manual":   "auto"|"manual",
                "last_decision":    dict,
                "ac":               get_ac_status(),
                "thermal":          get_thermal_level(),
                "gaming_detected":  bool,
                "recent_log":       last 5 decision_log entries,
            }
        """
        return {
            "mode":            self.mode,
            "auto_or_manual":  "auto" if self.mode == "auto" else "manual",
            "last_decision":   self.last_decision,
            "ac":              get_ac_status(),
            "thermal":         get_thermal_level(),
            "gaming_detected": is_gaming_running(),
            "recent_log":      self.decision_log[-5:],
        }

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def start_loop(self):
        """
        Start the background auto-apply thread.

        Runs apply_current_decision() every 10 seconds.
        Thread is daemon=True — dies with the process.
        """
        def _loop():
            while True:
                time.sleep(10)
                try:
                    self.apply_current_decision()
                except Exception as e:
                    logger.error(f"[PowerBrain] loop error: {e}")

        t = threading.Thread(target=_loop, daemon=True, name="luminos-powerbrain")
        t.start()
        logger.info("PowerBrain background loop started (10s interval)")


# Module-level singleton — starts loop on import
_brain = PowerBrain()
_brain.start_loop()
