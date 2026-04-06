"""
src/startup/startup_timer.py
Phase 5.12 Task 2 — Session startup timing.

Records timestamps at each startup stage.
Logs to ~/.local/share/luminos/startup.log.
Target: T3 - T0 < 10 seconds.

Stages:
  T0: session script starts
  T1: Hyprland launched
  T2: login screen visible
  T3: desktop fully loaded (dock + bar rendering)

Usage (from shell script):
  python3 -m startup.startup_timer record T0
  python3 -m startup.startup_timer record T1
  python3 -m startup.startup_timer record T2
  python3 -m startup.startup_timer record T3
  python3 -m startup.startup_timer summary

Pure helpers:
  record_stage(stage, t)     → None
  load_timings()             → dict[str, float]
  compute_summary(timings)   → dict
"""

import json
import logging
import os
import sys
import time

logger = logging.getLogger("luminos.startup.timer")

_LOG_PATH = os.path.expanduser("~/.local/share/luminos/startup.log")
_STATE_PATH = os.path.expanduser("~/.local/share/luminos/startup_current.json")

STAGES = ("T0", "T1", "T2", "T3")
STAGE_LABELS = {
    "T0": "session script starts",
    "T1": "Hyprland launched",
    "T2": "login screen visible",
    "T3": "desktop fully loaded",
}
TARGET_SECONDS = 10.0


# ===========================================================================
# Pure helpers
# ===========================================================================

def record_stage(stage: str, t: float | None = None) -> None:
    """
    Record a startup stage timestamp.

    Saves current timestamps to _STATE_PATH for summary later.

    Args:
        stage: One of T0, T1, T2, T3.
        t:     Unix timestamp. Uses time.time() if None.
    """
    if stage not in STAGES:
        logger.warning(f"Unknown startup stage: {stage}")
        return

    if t is None:
        t = time.time()

    timings = _load_state()
    timings[stage] = t
    _save_state(timings)
    logger.debug(f"Startup stage {stage} recorded at {t:.3f}")


def load_timings() -> dict:
    """Load current startup timings from state file."""
    return _load_state()


def compute_summary(timings: dict) -> dict:
    """
    Compute human-readable startup summary.

    Args:
        timings: Dict mapping stage → unix timestamp.

    Returns:
        Dict with keys:
          total_seconds: float (T3 - T0, or None)
          met_target: bool
          stages: list of {stage, label, elapsed_ms, wall_time}
          target_seconds: float
    """
    t0 = timings.get("T0")
    t3 = timings.get("T3")

    total_seconds = (t3 - t0) if (t0 is not None and t3 is not None) else None
    met_target    = (total_seconds is not None and
                     total_seconds <= TARGET_SECONDS)

    stages_out = []
    prev_t = t0
    for stage in STAGES:
        ts = timings.get(stage)
        elapsed_ms = None
        if ts is not None and t0 is not None:
            elapsed_ms = round((ts - t0) * 1000)
        stages_out.append({
            "stage":      stage,
            "label":      STAGE_LABELS[stage],
            "elapsed_ms": elapsed_ms,
            "wall_time":  _fmt_time(ts) if ts else None,
        })
        prev_t = ts

    return {
        "total_seconds": round(total_seconds, 3) if total_seconds else None,
        "met_target":    met_target,
        "target_seconds": TARGET_SECONDS,
        "stages":        stages_out,
    }


def write_log_entry(timings: dict) -> None:
    """
    Append a summary line to the startup log.

    Args:
        timings: Dict mapping stage → unix timestamp.
    """
    summary = compute_summary(timings)
    t0 = timings.get("T0")
    ts_str = _fmt_time(t0) if t0 else "?"
    total  = summary.get("total_seconds")
    status = "OK" if summary.get("met_target") else "SLOW"

    line = (
        f"{ts_str} | {status} | "
        f"total={total}s | "
        f"T0={timings.get('T0','?'):.3f} "
        f"T1={timings.get('T1','?'):.3f} "
        f"T2={timings.get('T2','?'):.3f} "
        f"T3={timings.get('T3','?'):.3f}"
    )

    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        logger.warning(f"Failed to write startup log: {e}")


# ===========================================================================
# Internal
# ===========================================================================

def _load_state() -> dict:
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k in STAGES}
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _save_state(timings: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(timings, f)
    except OSError as e:
        logger.debug(f"Failed to save startup state: {e}")


def _fmt_time(t: float | None) -> str:
    if t is None:
        return "?"
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


# ===========================================================================
# CLI entry point
# ===========================================================================

def main() -> int:
    """
    CLI usage:
      startup_timer record T0
      startup_timer record T1
      startup_timer summary
      startup_timer reset
    """
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: startup_timer <record|summary|reset> [STAGE]")
        return 1

    cmd = sys.argv[1]

    if cmd == "record":
        if len(sys.argv) < 3:
            print("Usage: startup_timer record <T0|T1|T2|T3>")
            return 1
        stage = sys.argv[2].upper()
        record_stage(stage)
        print(f"Recorded {stage} at {time.time():.3f}")
        # If T3 recorded — write full log entry
        if stage == "T3":
            timings = load_timings()
            write_log_entry(timings)
            summary = compute_summary(timings)
            total = summary.get("total_seconds")
            if total is not None:
                status = "OK" if summary["met_target"] else f"SLOW (target={TARGET_SECONDS}s)"
                print(f"Startup total: {total:.2f}s — {status}")
        return 0

    elif cmd == "summary":
        timings = load_timings()
        summary = compute_summary(timings)
        print(f"Startup summary:")
        for s in summary["stages"]:
            ms = s.get("elapsed_ms")
            ms_str = f"+{ms}ms" if ms is not None else "(not recorded)"
            print(f"  {s['stage']}: {s['label']} — {ms_str}")
        total = summary.get("total_seconds")
        if total is not None:
            status = "✓ under target" if summary["met_target"] else "✗ over target"
            print(f"  Total: {total:.2f}s ({status} — target {TARGET_SECONDS}s)")
        return 0

    elif cmd == "reset":
        if os.path.isfile(_STATE_PATH):
            os.remove(_STATE_PATH)
            print("Startup timing state cleared.")
        return 0

    else:
        print(f"Unknown command: {cmd}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
