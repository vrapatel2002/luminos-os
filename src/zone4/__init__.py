"""
src/zone4/__init__.py
Public API for the Luminos Zone 4 KVM/QEMU last-resort Windows VM layer.

Usage:
    from zone4 import run_in_zone4
    result = run_in_zone4("/path/to/anticheat_game.exe")
"""

from .kvm_runner import launch_kvm_vm, detect_kvm, detect_qemu, find_windows_vm


def run_in_zone4(exe_path: str) -> dict:
    """
    Full Zone 4 pipeline: check KVM + QEMU, launch Windows VM if available.

    Args:
        exe_path: Path to the Windows executable (passed into VM via shared folder).

    Returns:
        On success: {"success": True, "pid": int, "runner": "kvm", ...}
        On failure: {"success": False, "error": str, ...}
    """
    return launch_kvm_vm(exe_path)
