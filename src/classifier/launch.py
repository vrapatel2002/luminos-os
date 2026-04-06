"""
src/classifier/launch.py
Phase 5.10 Task 1 — Launch .exe files with full error handling and layer retries.

Pipeline:
  1. Check app_overrides.json — respect any manual layer override.
  2. Classify binary (router + rule engine).
  3. Launch via chosen layer.
  4. On failure: escalate automatically per spec:
       Layer 1 (Wine/Proton) failure → notify, retry Layer 2 after 3s
       Layer 2 (Firecracker) failure → notify, escalate to Layer 3
       Layer 3 (KVM) failure → notify user, log, offer "View details"
  5. Log all events to ~/.local/share/luminos/compat.log.

Usage:
  python3 -m classifier.launch /path/to/app.exe
  luminos-run-windows /path/to/app.exe
"""

import json
import logging
import os
import sys
import time

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

logger = logging.getLogger("luminos.launcher")

_OVERRIDES_PATH = os.path.expanduser("~/.config/luminos/app_overrides.json")
_COMPAT_LOG     = os.path.expanduser("~/.local/share/luminos/compat.log")


# ===========================================================================
# Public API
# ===========================================================================

def launch(exe_path: str) -> dict:
    """
    Full end-to-end pipeline: check overrides → classify → launch.

    Error handling:
      - Layer 1 failure → notify + auto-retry Layer 2 after 3s
      - Layer 2 failure → notify + escalate Layer 3
      - Layer 3 failure → notify user "not compatible"

    Args:
        exe_path: Path to the Windows executable.

    Returns:
        Result dict with at minimum: {"success": bool, "runner": str}
    """
    if not os.path.isfile(exe_path):
        return {"success": False, "error": f"File not found: {exe_path}"}

    app_name = os.path.basename(exe_path)

    # Step 1 — Check manual override
    layer = _check_override(exe_path)

    # Step 2 — Router decision (if no override)
    if layer == "auto" or layer is None:
        from classifier import classify_binary
        decision = classify_binary(exe_path)
        layer = decision.get("layer", "proton")
        logger.info(
            f"Router: {layer} (confidence={decision.get('confidence', 0):.2f},"
            f" reason={decision.get('reason', 'unknown')})"
        )
        _log_compat(app_name, f"router decision: {layer}")

    # Step 3 — Launch with retry chain
    return _launch_with_retry(exe_path, app_name, layer)


# ===========================================================================
# Override check
# ===========================================================================

def _check_override(exe_path: str) -> str | None:
    """
    Check ~/.config/luminos/app_overrides.json for a manual layer override.

    Matches on basename (.exe filename).

    Returns:
        Layer string if override found, None otherwise.
    """
    if not os.path.isfile(_OVERRIDES_PATH):
        return None
    try:
        with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        if not isinstance(overrides, dict):
            return None
        basename = os.path.basename(exe_path).lower()
        # Try exact match, then without extension
        for key, layer in overrides.items():
            if key.lower() == basename or key.lower() == basename.replace(".exe", ""):
                logger.info(f"Override: {basename} → {layer}")
                _log_compat(basename, f"override applied: {layer}")
                return str(layer)
    except Exception as e:
        logger.debug(f"Override check error: {e}")
    return None


# ===========================================================================
# Launch with retry chain
# ===========================================================================

def _launch_with_retry(exe_path: str, app_name: str, layer: str) -> dict:
    """
    Launch the exe, handling failures with the spec-defined retry chain.
    """
    # Map layer string to attempt sequence
    if layer in ("wine", "proton", "lutris"):
        return _try_zone1(exe_path, app_name, layer)
    elif layer == "firecracker":
        return _try_zone2(exe_path, app_name)
    elif layer == "kvm":
        return _try_zone3(exe_path, app_name)
    elif layer == "native":
        return _launch_native(exe_path)
    else:
        # Unknown layer → start at Zone 1
        logger.warning(f"Unknown layer '{layer}' — defaulting to proton")
        return _try_zone1(exe_path, app_name, "proton")


def _try_zone1(exe_path: str, app_name: str, runner: str) -> dict:
    """
    Attempt Layer 1 (Wine/Proton). On failure → notify + retry Zone 2.
    """
    result = _run_zone1(exe_path, runner)
    if result.get("success"):
        _log_compat(app_name, f"launched via {runner}")
        return result

    # Layer 1 failed
    error = result.get("error", "Unknown error")
    _log_compat(app_name, f"layer1 FAILED ({runner}): {error}")
    _notify(
        title=f"Could not launch {app_name}",
        body=f"Trying a different method in 3 seconds...",
        urgency="normal",
    )

    # Wait 3s then try Zone 2
    time.sleep(3)
    _notify(
        title=app_name,
        body="Trying another method...",
        urgency="normal",
    )
    return _try_zone2(exe_path, app_name, from_retry=True)


def _try_zone2(exe_path: str, app_name: str, from_retry: bool = False) -> dict:
    """
    Attempt Layer 2 (Firecracker). On failure → escalate to Zone 3.
    """
    result = _run_zone2(exe_path)
    if result.get("success"):
        _log_compat(app_name, "launched via firecracker")
        return result

    error = result.get("error", "Unknown error")
    _log_compat(app_name, f"layer2 FAILED (firecracker): {error}")

    _notify(
        title=app_name,
        body="Trying another method...",
        urgency="normal",
    )
    return _try_zone3(exe_path, app_name)


def _try_zone3(exe_path: str, app_name: str) -> dict:
    """
    Attempt Layer 3 (KVM). On failure → final failure notification.
    """
    result = _run_zone3(exe_path)
    if result.get("success"):
        _log_compat(app_name, "launched via kvm")
        return result

    error = result.get("error", "Unknown error")
    _log_compat(app_name, f"layer3 FAILED (kvm): {error}")

    _notify(
        title=f"Could not launch {app_name}",
        body="This app may not be compatible",
        urgency="critical",
        action_label="View details",
        action_cmd=f"luminos-compat-log",
    )
    return {
        "success": False,
        "error":   error,
        "runner":  "kvm",
        "log_path": _COMPAT_LOG,
    }


# ===========================================================================
# Layer runners
# ===========================================================================

def _launch_native(exe_path: str) -> dict:
    import subprocess
    try:
        proc = subprocess.Popen(
            [exe_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"success": True, "pid": proc.pid, "runner": "native"}
    except (FileNotFoundError, OSError) as e:
        return {"success": False, "error": str(e)}


def _run_zone1(exe_path: str, runner: str) -> dict:
    try:
        from zone2 import run_in_zone2
        return run_in_zone2(exe_path, runner=runner)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_zone2(exe_path: str) -> dict:
    try:
        from zone3 import run_in_zone3
        return run_in_zone3(exe_path)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_zone3(exe_path: str) -> dict:
    try:
        from zone4 import run_in_zone4
        return run_in_zone4(exe_path)
    except Exception as e:
        return {"success": False, "error": str(e)}


# ===========================================================================
# Notification
# ===========================================================================

def _notify(title: str, body: str, urgency: str = "normal",
            action_label: str = "", action_cmd: str = "") -> None:
    """
    Send a desktop notification via the Luminos notification system.

    Falls back to notify-send if the daemon is not available.
    """
    try:
        from notifications.system_notifier import send_notification
        send_notification(
            title=title,
            body=body,
            urgency=urgency,
            app_name="Luminos Compatibility",
        )
        return
    except Exception:
        pass

    # Fallback: notify-send
    import subprocess
    urgency_map = {"normal": "normal", "critical": "critical", "low": "low"}
    try:
        cmd = [
            "notify-send",
            f"--urgency={urgency_map.get(urgency, 'normal')}",
            "--app-name=Luminos",
            title,
            body,
        ]
        if action_label and action_cmd:
            cmd += [f"--action={action_label}={action_cmd}"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.debug(f"notify-send error: {e}")


# ===========================================================================
# Compat log
# ===========================================================================

def _log_compat(app_name: str, event: str) -> None:
    """
    Append one line to ~/.local/share/luminos/compat.log.

    Format: ISO timestamp | app_name | event
    """
    try:
        os.makedirs(os.path.dirname(_COMPAT_LOG), exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(_COMPAT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {app_name} | {event}\n")
    except OSError as e:
        logger.debug(f"compat log write error: {e}")


# ===========================================================================
# CLI entry point
# ===========================================================================

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: luminos-run-windows <path-to-exe>", file=sys.stderr)
        return 1

    exe_path = os.path.abspath(sys.argv[1])
    result   = launch(exe_path)

    if result.get("success"):
        logger.info(
            f"Launched {os.path.basename(exe_path)} via {result.get('runner')}"
            f" (pid={result.get('pid')})"
        )
        return 0
    else:
        error = result.get("error", "Unknown error")
        logger.error(f"Failed to launch: {error}")
        print(f"Failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
