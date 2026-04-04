"""
src/classifier/launch.py
Entry point for launching Windows applications through the compatibility router.

This is what runs when a user double-clicks any .exe file.
The user sees nothing except the app opening — all routing is invisible.

Pipeline:
  1. Router classifies the binary (cached after first analysis)
  2. Router returns layer decision
  3. Correct layer launches the app
  4. Result reported to daemon

Usage:
  python3 -m classifier.launch /path/to/app.exe
  luminos-run-windows /path/to/app.exe
"""

import logging
import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

logger = logging.getLogger("luminos-ai.launcher")


def launch(exe_path: str) -> dict:
    """
    Full end-to-end pipeline: classify → route → launch.

    Args:
        exe_path: Path to the Windows executable.

    Returns:
        Result dict with success status, pid, runner, etc.
    """
    from classifier import classify_binary

    if not os.path.isfile(exe_path):
        return {"success": False, "error": f"File not found: {exe_path}"}

    # Step 1 — Classify
    decision = classify_binary(exe_path)
    layer = decision.get("layer", "proton")

    logger.info(
        f"Router decision: {layer} (confidence={decision.get('confidence', 0):.2f}, "
        f"reason={decision.get('reason', 'unknown')})"
    )

    # Step 2 — Route to correct layer
    if layer == "native":
        return _launch_native(exe_path)
    elif layer in ("wine", "proton"):
        return _launch_zone2(exe_path, runner=layer)
    elif layer == "lutris":
        return _launch_zone2_lutris(exe_path)
    elif layer == "firecracker":
        return _launch_zone3(exe_path)
    elif layer == "kvm":
        return _launch_zone4(exe_path)
    else:
        # Fallback: try proton
        logger.warning(f"Unknown layer '{layer}' — falling back to proton")
        return _launch_zone2(exe_path, runner="proton")


def _launch_native(exe_path: str) -> dict:
    """Launch a native Linux binary directly."""
    import subprocess
    try:
        proc = subprocess.Popen(
            [exe_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"success": True, "pid": proc.pid, "runner": "native", "cmd": [exe_path]}
    except (FileNotFoundError, OSError) as e:
        return {"success": False, "error": str(e)}


def _launch_zone2(exe_path: str, runner: str = "auto") -> dict:
    """Launch via Wine/Proton (Zone 2)."""
    from zone2 import run_in_zone2
    return run_in_zone2(exe_path, runner=runner)


def _launch_zone2_lutris(exe_path: str) -> dict:
    """Launch via Lutris (Zone 2)."""
    from zone2 import run_in_zone2
    return run_in_zone2(exe_path, runner="lutris")


def _launch_zone3(exe_path: str) -> dict:
    """Launch via Firecracker microVM (Zone 3)."""
    from zone3 import run_in_zone3
    return run_in_zone3(exe_path)


def _launch_zone4(exe_path: str) -> dict:
    """Launch via KVM/QEMU full VM (Zone 4 — last resort)."""
    from zone4 import run_in_zone4
    return run_in_zone4(exe_path)


def main() -> int:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: luminos-run-windows <path-to-exe>", file=sys.stderr)
        return 1

    exe_path = os.path.abspath(sys.argv[1])
    result = launch(exe_path)

    if result.get("success"):
        logger.info(f"Launched {os.path.basename(exe_path)} via {result.get('runner')} (pid={result.get('pid')})")
        return 0
    else:
        error = result.get("error", "Unknown error")
        setup = result.get("setup_message")
        hint = result.get("install_hint")

        logger.error(f"Failed to launch: {error}")
        if setup:
            print(setup, file=sys.stderr)
        elif hint:
            print(f"Install hint: {hint}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
