"""
src/zone4/kvm_runner.py
KVM/QEMU last-resort Windows VM launcher.

This is Layer 3 (the heaviest layer) — used only for apps that require
a full Windows environment (anticheat games, enterprise apps).

Checks:
  - /dev/kvm exists and is accessible
  - qemu-system-x86_64 is installed
  - A Windows VM disk image exists at the expected path
  - GPU passthrough via NVIDIA RTX 4050 if available

If no VM image exists, returns a one-time setup message instead of failing.
Pure stdlib — no external dependencies.
"""

import logging
import os
import subprocess

logger = logging.getLogger("luminos-ai.zone4")

_KVM_PATH = "/dev/kvm"
_QEMU_CANDIDATES = [
    "/usr/bin/qemu-system-x86_64",
    "/usr/local/bin/qemu-system-x86_64",
]

# Default location for the Windows VM disk image
_VM_IMAGE_DIR = os.path.expanduser("~/.luminos/vms/")
_VM_IMAGE_NAME = "windows.qcow2"
_VM_OVMF_PATH = "/usr/share/edk2/x64/OVMF.fd"

# NVIDIA GPU PCI address for passthrough (detected at runtime)
_NVIDIA_VFIO_PATTERN = "NVIDIA"


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def detect_kvm() -> dict:
    """
    Check whether KVM is available and accessible.

    Returns:
        {"available": bool, "reason": str}
    """
    if not os.path.exists(_KVM_PATH):
        return {
            "available": False,
            "reason": "/dev/kvm not found — KVM module not loaded or CPU lacks virtualization",
        }

    readable = os.access(_KVM_PATH, os.R_OK)
    writeable = os.access(_KVM_PATH, os.W_OK)

    if readable and writeable:
        return {"available": True, "reason": "KVM accessible"}

    try:
        import grp
        st = os.stat(_KVM_PATH)
        group_name = grp.getgrgid(st.st_gid).gr_name
        return {
            "available": False,
            "reason": f"/dev/kvm exists but no access. Run: sudo usermod -aG {group_name} $USER",
        }
    except (KeyError, OSError, ImportError):
        return {"available": False, "reason": "/dev/kvm exists but no access"}


def detect_qemu() -> dict:
    """
    Check whether qemu-system-x86_64 is installed.

    Returns:
        {"available": bool, "path": str | None, "version": str | None}
    """
    for candidate in _QEMU_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                version = result.stdout.strip().splitlines()[0] if result.returncode == 0 else None
            except (subprocess.TimeoutExpired, OSError):
                version = None
            return {"available": True, "path": candidate, "version": version}

    return {"available": False, "path": None, "version": None}


def find_windows_vm() -> dict:
    """
    Look for an existing Windows VM disk image.

    Returns:
        {"exists": bool, "path": str | None, "size_gb": float | None}
    """
    image_path = os.path.join(_VM_IMAGE_DIR, _VM_IMAGE_NAME)
    if os.path.isfile(image_path):
        try:
            size_bytes = os.path.getsize(image_path)
            size_gb = round(size_bytes / (1024 ** 3), 1)
        except OSError:
            size_gb = None
        return {"exists": True, "path": image_path, "size_gb": size_gb}
    return {"exists": False, "path": None, "size_gb": None}


def _detect_nvidia_pci() -> str | None:
    """Find the NVIDIA GPU PCI address for VFIO passthrough."""
    try:
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if _NVIDIA_VFIO_PATTERN in line and ("3D" in line or "VGA" in line):
                # Extract PCI address (first field, e.g. "01:00.0")
                pci_addr = line.split()[0]
                return pci_addr
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# VM launch
# ---------------------------------------------------------------------------

def _build_qemu_cmd(qemu_path: str, image_path: str, exe_path: str,
                    gpu_passthrough: bool = False,
                    nvidia_pci: str | None = None) -> list[str]:
    """
    Build the QEMU command line for launching the Windows VM.

    Uses OVMF UEFI firmware if available, shared folder for exe access,
    and optional VFIO GPU passthrough.
    """
    cmd = [
        qemu_path,
        "-enable-kvm",
        "-m", "4G",
        "-smp", "4",
        "-cpu", "host",
        "-drive", f"file={image_path},format=qcow2,if=virtio",
    ]

    # UEFI firmware
    if os.path.isfile(_VM_OVMF_PATH):
        cmd.extend(["-bios", _VM_OVMF_PATH])

    # Shared folder: expose the exe's parent directory read-only inside the VM
    exe_dir = os.path.dirname(os.path.abspath(exe_path))
    cmd.extend([
        "-virtfs",
        f"local,path={exe_dir},mount_tag=luminosshare,security_model=mapped-xattr,readonly=on",
    ])

    # GPU passthrough via VFIO
    if gpu_passthrough and nvidia_pci:
        cmd.extend([
            "-device", f"vfio-pci,host={nvidia_pci}",
            "-vga", "none",
            "-nographic",
        ])
    else:
        cmd.extend(["-vga", "virtio", "-display", "gtk,gl=on"])

    # Network (user-mode NAT — no host access beyond internet)
    cmd.extend(["-nic", "user,model=virtio-net-pci"])

    return cmd


def launch_kvm_vm(exe_path: str) -> dict:
    """
    Full KVM/QEMU launch pipeline.

    Steps:
      1. Check KVM is available
      2. Check QEMU is installed
      3. Check Windows VM image exists
      4. Detect NVIDIA GPU for passthrough
      5. Launch VM

    Returns:
        On success: {"success": True, "pid": int, "runner": "kvm", "cmd": list}
        On infra missing: {"success": False, "error": str, ...}
        On no VM image: {"success": False, "error": str, "setup_message": str}
    """
    # Step 1 — KVM
    kvm = detect_kvm()
    if not kvm["available"]:
        return {
            "success": False,
            "error":   "KVM not available",
            "reason":  kvm["reason"],
            "install_hint": "sudo pacman -S qemu-full libvirt",
        }

    # Step 2 — QEMU
    qemu = detect_qemu()
    if not qemu["available"]:
        return {
            "success":      False,
            "error":        "QEMU not installed",
            "install_hint": "sudo pacman -S qemu-full",
        }

    # Step 3 — VM image
    vm = find_windows_vm()
    if not vm["exists"]:
        return {
            "success": False,
            "error":   "No Windows VM image found",
            "setup_message": (
                "To use KVM mode, create a Windows VM image:\n"
                f"  1. mkdir -p {_VM_IMAGE_DIR}\n"
                f"  2. qemu-img create -f qcow2 {_VM_IMAGE_DIR}{_VM_IMAGE_NAME} 64G\n"
                "  3. Install Windows from ISO using virt-manager\n"
                "  4. Install virtio drivers inside the VM\n"
                "This only needs to be done once. After setup, Luminos will\n"
                "use this VM automatically for apps that need it."
            ),
        }

    # Step 4 — GPU passthrough detection
    nvidia_pci = _detect_nvidia_pci()
    gpu_passthrough = nvidia_pci is not None

    # Step 5 — Launch
    cmd = _build_qemu_cmd(
        qemu["path"], vm["path"], exe_path,
        gpu_passthrough=gpu_passthrough,
        nvidia_pci=nvidia_pci,
    )

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info(f"Zone 4 KVM VM launched (pid={proc.pid}, gpu_passthrough={gpu_passthrough})")
        return {
            "success":         True,
            "pid":             proc.pid,
            "runner":          "kvm",
            "cmd":             cmd,
            "gpu_passthrough": gpu_passthrough,
        }
    except FileNotFoundError:
        return {"success": False, "error": f"QEMU binary not found: {qemu['path']}"}
    except OSError as e:
        return {"success": False, "error": f"Failed to launch VM: {e}"}
