"""
src/zone3/__init__.py
Public API for the Luminos Zone 3 Firecracker microVM quarantine layer.

Usage:
    from zone3 import run_in_zone3
    result = run_in_zone3("/path/to/anticheat_game.exe")
    # On success: {"success": True, "session_id": "a1b2c3d4", ...}
    # On failure: {"success": False, "error": str, "session_id": str}
    #
    # Caller is responsible for cleanup when the session is done:
    from zone3.session_manager import destroy_session
    destroy_session(result["session_id"])
"""

from .firecracker_runner import launch_vm
from .session_manager import create_session, destroy_session


def run_in_zone3(exe_path: str) -> dict:
    """
    Full Zone 3 pipeline:
      1. Create an isolated session directory.
      2. Attempt VM launch (Firecracker + KVM).
      3. On launch failure: destroy the session and return error.
      4. On success: return result with session_id for caller to track.

    Args:
        exe_path: Path to the Windows executable requiring isolation.

    Returns:
        Always a dict containing at minimum: "success", "session_id".
        On success:  {"success": True,  "session_id": str, ...}
        On failure:  {"success": False, "session_id": str, "error": str, ...}
    """
    # Step 1 — Allocate session
    try:
        session_id = create_session()
    except OSError as e:
        return {
            "success":    False,
            "session_id": None,
            "error":      f"Failed to create session: {e}",
        }

    # Step 2 — Attempt VM launch (launch_vm creates its own session dir via
    #           firecracker_runner; session_manager.create_session() above
    #           gives us the tracking handle)
    result = launch_vm(exe_path)

    # Step 3 — On failure, clean up the session we allocated
    if not result.get("success", False):
        destroy_session(session_id)
        result.setdefault("session_id", session_id)
        return result

    # Step 4 — Success: caller owns the session lifetime
    result["session_id"] = session_id
    return result
