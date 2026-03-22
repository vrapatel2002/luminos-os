"""
firecracker_runner.py
Detect Firecracker + KVM and prepare Zone 3 microVM launch configs.
Pure stdlib — no external dependencies.

Real VM launch is stubbed: it requires vmlinux kernel image + rootfs.ext4
which only exist on the Luminos target hardware. All config/session
infrastructure is fully functional so the stub is a thin shim only.
"""

import json
import logging
import os
import stat
import subprocess
import uuid

logger = logging.getLogger("luminos-ai.zone3")

# Firecracker binary search paths
_FC_CANDIDATES = [
    "/usr/bin/firecracker",
    "/usr/local/bin/firecracker",
    os.path.expanduser("~/.local/bin/firecracker"),
]

# KVM device path
_KVM_PATH = "/dev/kvm"

# Luminos kernel image (installed on target)
_VMLINUX_PATH = "/opt/luminos/kernels/vmlinux"

# Base directory for VM session working dirs
SESSION_BASE = "/tmp/luminos-vms/"


# ---------------------------------------------------------------------------
# Firecracker detection
# ---------------------------------------------------------------------------

def _get_firecracker_version(fc_path: str) -> str | None:
    """Run `firecracker --version` and return version string, or None."""
    try:
        result = subprocess.run(
            [fc_path, "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def detect_firecracker() -> dict:
    """
    Probe for the Firecracker binary in standard locations.

    Returns:
        {
            "available": bool,
            "path":      str | None,
            "version":   str | None,
        }
    """
    for candidate in _FC_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            version = _get_firecracker_version(candidate)
            return {"available": True, "path": candidate, "version": version}

    return {"available": False, "path": None, "version": None}


# ---------------------------------------------------------------------------
# KVM detection
# ---------------------------------------------------------------------------

def detect_kvm() -> dict:
    """
    Check whether KVM is available and accessible to the current user.

    Returns:
        {
            "available": bool,
            "reason":    str,   # human-readable explanation
        }
    """
    if not os.path.exists(_KVM_PATH):
        return {
            "available": False,
            "reason":    "/dev/kvm not found — KVM module not loaded or not supported by CPU",
        }

    readable  = os.access(_KVM_PATH, os.R_OK)
    writeable = os.access(_KVM_PATH, os.W_OK)

    if readable and writeable:
        return {
            "available": True,
            "reason":    "KVM accessible at /dev/kvm",
        }

    # Diagnose permission issue
    try:
        st = os.stat(_KVM_PATH)
        kvm_gid = st.st_gid
        import grp
        kvm_group = grp.getgrgid(kvm_gid).gr_name
        reason = (
            f"/dev/kvm exists but current user lacks r/w access. "
            f"Add user to group '{kvm_group}': sudo usermod -aG {kvm_group} $USER"
        )
    except (KeyError, OSError, ImportError):
        reason = "/dev/kvm exists but current user lacks r/w access"

    return {"available": False, "reason": reason}


# ---------------------------------------------------------------------------
# VM config builder
# ---------------------------------------------------------------------------

def build_vm_config(exe_path: str, session_id: str) -> dict:
    """
    Build the Firecracker VM configuration structure for this session.

    The config mirrors Firecracker's JSON API format so it can be written
    directly to vm_config.json and fed to the firecracker --config-file flag.

    Args:
        exe_path:   Path to the Windows executable to run inside the VM.
        session_id: Unique 8-char hex session identifier.

    Returns:
        Config dict with all required fields.
    """
    session_dir  = os.path.join(SESSION_BASE, session_id)
    rootfs_path  = os.path.join(session_dir, "rootfs.ext4")
    socket_path  = os.path.join(session_dir, "firecracker.socket")

    return {
        "kernel_image_path": _VMLINUX_PATH,
        "rootfs_path":       rootfs_path,
        "vcpu_count":        2,
        "mem_size_mib":      512,
        "session_id":        session_id,
        "exe_path":          exe_path,
        "socket_path":       socket_path,
        # Boot args: single-shot execution, serial console
        "boot_args": (
            "console=ttyS0 reboot=k panic=1 pci=off "
            f"luminos.exe={exe_path}"
        ),
    }


# ---------------------------------------------------------------------------
# Full launch pipeline
# ---------------------------------------------------------------------------

def launch_vm(exe_path: str) -> dict:
    """
    Zone 3 VM launch pipeline.

    Steps:
      1. Check Firecracker is installed.
      2. Check KVM is accessible.
      3. Generate a session ID.
      4. Build VM config.
      5. Create session directory and write vm_config.json.
      6. Return stub result — real launch requires vmlinux + rootfs on target.

    Returns on infrastructure failure:
        {"success": False, "error": str, "install_hint"|"reason": str}

    Returns when infra is ready but kernel/rootfs missing (expected on dev):
        {"success": False, "error": "VM kernel not found",
         "note": str, "session_id": str, "config": dict}
    """
    # Step 1 — Firecracker binary
    fc_info = detect_firecracker()
    if not fc_info["available"]:
        return {
            "success":      False,
            "error":        "Firecracker not installed",
            "install_hint": "See https://firecracker-microvm.github.io",
        }

    # Step 2 — KVM
    kvm_info = detect_kvm()
    if not kvm_info["available"]:
        return {
            "success": False,
            "error":   "KVM not available",
            "reason":  kvm_info["reason"],
        }

    # Step 3 — Session ID
    session_id = uuid.uuid4().hex[:8]

    # Step 4 — Build config
    vm_config = build_vm_config(exe_path, session_id)

    # Step 5 — Create session dir + write config
    session_dir = os.path.join(SESSION_BASE, session_id)
    try:
        os.makedirs(session_dir, exist_ok=True)
        config_path = os.path.join(session_dir, "vm_config.json")
        with open(config_path, "w") as f:
            json.dump(vm_config, f, indent=2)
        logger.info(f"Zone 3 session {session_id} configured at {session_dir}")
    except OSError as e:
        return {
            "success": False,
            "error":   f"Failed to create session directory: {e}",
        }

    # Step 6 — Stub: kernel image required on target
    return {
        "success":    False,
        "error":      "VM kernel not found",
        "note":       "Real launch requires vmlinux + rootfs — stub",
        "session_id": session_id,
        "config":     vm_config,
    }
