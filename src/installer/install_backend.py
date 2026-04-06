"""
src/installer/install_backend.py
Phase 6 — Installation backend using arch-install-scripts.

Called by luminos_installer.py GUI.
Can also be used headlessly:
  run_install(disk="/dev/sda", partition_mode="auto")

Stages:
  0  Partitioning disk
  1  Formatting partitions
  2  Mounting filesystems
  3  Installing base system
  4  Installing Luminos packages
  5  Copying Luminos OS
  6  Generating fstab
  7  Configuring system
  8  Installing bootloader
  9  Cleaning up
"""

import logging
import os
import subprocess
import sys
import time

logger = logging.getLogger("luminos.installer.backend")

_LUMINOS_PACKAGES = [
    "base", "linux", "linux-firmware", "base-devel",
    "networkmanager", "pipewire", "pipewire-pulse", "wireplumber",
    "polkit", "xdg-user-dirs", "xdg-desktop-portal",
    "asusctl", "supergfxctl", "power-profiles-daemon",
    "nvidia", "nvidia-utils", "mesa", "vulkan-radeon",
    "hyprland", "xdg-desktop-portal-hyprland",
    "qt5-wayland", "qt6-wayland", "waybar", "wofi", "dunst", "swww",
    "greetd", "ttf-inter", "noto-fonts", "noto-fonts-emoji",
    "python", "python-gobject", "gtk4", "libadwaita",
    "wine", "wine-gecko", "wine-mono", "icoutils", "socat",
    "llama-cpp",
]

MOUNT_POINT = "/mnt"
_EFI_SIZE    = "512MiB"
_SWAP_SIZE   = "4GiB"


def run_install(disk: str,
                partition_mode: str = "auto",
                progress_callback=None) -> None:
    """
    Run the full installation to the target disk.

    Args:
        disk:              Target block device (e.g. "/dev/sda").
        partition_mode:    "auto" or "manual".
        progress_callback: Callable(stage_idx: int, stage_name: str) or None.

    Raises:
        RuntimeError on any installation failure.
    """
    stages = [
        ("Partitioning disk",          lambda: _partition(disk, partition_mode)),
        ("Formatting partitions",       lambda: _format(disk, partition_mode)),
        ("Mounting filesystems",        lambda: _mount(disk, partition_mode)),
        ("Installing base system",      lambda: _pacstrap_base()),
        ("Installing Luminos packages", lambda: _pacstrap_luminos()),
        ("Copying Luminos OS",          lambda: _copy_luminos()),
        ("Generating fstab",            lambda: _genfstab()),
        ("Configuring system",          lambda: _configure(disk)),
        ("Installing bootloader",       lambda: _bootloader()),
        ("Cleaning up",                 lambda: _cleanup()),
    ]

    for idx, (name, fn) in enumerate(stages):
        logger.info(f"[{idx+1}/{len(stages)}] {name}")
        if progress_callback:
            progress_callback(idx, name)
        fn()

    logger.info("Installation complete.")


# ===========================================================================
# Stage implementations
# ===========================================================================

def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """Run a command, raise RuntimeError on failure."""
    logger.debug(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        **kwargs,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def _partition(disk: str, mode: str) -> None:
    if mode == "manual":
        # Open GParted for manual partitioning
        try:
            subprocess.Popen(["gparted", disk])
        except FileNotFoundError:
            raise RuntimeError("GParted not found — install gparted first")
        input("Press Enter when partitioning is complete...")
        return

    # Auto: EFI + swap + root
    # Wipe GPT
    _run(["sgdisk", "--zap-all", disk])
    # EFI partition (1)
    _run(["sgdisk", f"--new=1:0:+{_EFI_SIZE}", "--typecode=1:ef00",
          "--change-name=1:EFI", disk])
    # Swap partition (2)
    _run(["sgdisk", f"--new=2:0:+{_SWAP_SIZE}", "--typecode=2:8200",
          "--change-name=2:swap", disk])
    # Root partition (3) — rest of disk
    _run(["sgdisk", "--new=3:0:0", "--typecode=3:8304",
          "--change-name=3:root", disk])
    # Notify kernel
    _run(["partprobe", disk])
    time.sleep(1)


def _part(disk: str, n: int) -> str:
    """Return partition path (handles nvme0n1p1 vs sda1)."""
    if "nvme" in disk or "mmcblk" in disk:
        return f"{disk}p{n}"
    return f"{disk}{n}"


def _format(disk: str, mode: str) -> None:
    if mode == "manual":
        return   # user already formatted in GParted

    efi  = _part(disk, 1)
    swap = _part(disk, 2)
    root = _part(disk, 3)

    _run(["mkfs.fat", "-F32", "-n", "EFI", efi])
    _run(["mkswap", "-L", "swap", swap])
    _run(["mkfs.ext4", "-L", "root", "-F", root])


def _mount(disk: str, mode: str) -> None:
    root = _part(disk, 3) if mode == "auto" else f"{disk}3"
    efi  = _part(disk, 1) if mode == "auto" else f"{disk}1"
    swap = _part(disk, 2) if mode == "auto" else f"{disk}2"

    os.makedirs(MOUNT_POINT, exist_ok=True)
    _run(["mount", root, MOUNT_POINT])
    os.makedirs(f"{MOUNT_POINT}/boot/efi", exist_ok=True)
    _run(["mount", efi, f"{MOUNT_POINT}/boot/efi"])
    _run(["swapon", swap])


def _pacstrap_base() -> None:
    base_pkgs = ["base", "linux", "linux-firmware", "base-devel"]
    _run(["pacstrap", "-K", MOUNT_POINT] + base_pkgs)


def _pacstrap_luminos() -> None:
    _run(["pacstrap", "-K", MOUNT_POINT] + _LUMINOS_PACKAGES)


def _copy_luminos() -> None:
    luminos_src = "/opt/luminos"
    if os.path.isdir(luminos_src):
        os.makedirs(f"{MOUNT_POINT}/opt/luminos", exist_ok=True)
        _run(["rsync", "-a",
              "--exclude=__pycache__", "--exclude=*.pyc",
              "--exclude=build", "--exclude=.git",
              f"{luminos_src}/", f"{MOUNT_POINT}/opt/luminos/"])
    else:
        logger.warning("Luminos source not found at /opt/luminos — skipping copy")


def _genfstab() -> None:
    result = subprocess.run(
        ["genfstab", "-U", MOUNT_POINT],
        capture_output=True, text=True,
    )
    with open(f"{MOUNT_POINT}/etc/fstab", "a") as f:
        f.write(result.stdout)


def _configure(disk: str) -> None:
    """Run post-install configuration inside chroot."""
    script = r"""#!/bin/bash
set -e
# Locale
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf

# Hostname
echo "luminos" > /etc/hostname

# Set timezone UTC
ln -sf /usr/share/zoneinfo/UTC /etc/localtime
hwclock --systohc

# Enable services
systemctl enable NetworkManager
systemctl enable asusd       2>/dev/null || true
systemctl enable supergfxd   2>/dev/null || true
systemctl enable greetd
systemctl enable luminos-ai  2>/dev/null || true

# Set GPU to Hybrid on first boot
systemctl enable luminos-gpu-init 2>/dev/null || true

# Create luminos user (no password — first-run wizard sets it)
if ! id luminos &>/dev/null; then
    useradd -m -G wheel,video,audio,input,storage,kvm luminos
fi
passwd -d luminos
echo "luminos ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/luminos
chmod 440 /etc/sudoers.d/luminos
"""
    _run(["arch-chroot", MOUNT_POINT, "bash", "-c", script])


def _bootloader() -> None:
    """Install systemd-boot EFI bootloader."""
    _run(["arch-chroot", MOUNT_POINT,
          "bootctl", "--path=/boot/efi", "install"])

    # Write bootloader entry
    entries_dir = f"{MOUNT_POINT}/boot/efi/loader/entries"
    os.makedirs(entries_dir, exist_ok=True)

    # Get root UUID
    try:
        result = subprocess.run(
            ["blkid", "-s", "UUID", "-o", "value",
             f"{MOUNT_POINT}/etc/fstab"],
            capture_output=True, text=True,
        )
        root_uuid = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "PARTUUID"
    except Exception:
        root_uuid = "PARTUUID"

    with open(f"{entries_dir}/luminos.conf", "w") as f:
        f.write(f"""title   Luminos OS
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=LABEL=root rw quiet splash
""")

    with open(f"{MOUNT_POINT}/boot/efi/loader/loader.conf", "w") as f:
        f.write("default luminos\ntimeout 3\neditor no\n")


def _cleanup() -> None:
    """Unmount all filesystems."""
    try:
        subprocess.run(["umount", "-R", MOUNT_POINT], check=False)
        subprocess.run(["swapoff", "-a"], check=False)
    except Exception:
        pass
