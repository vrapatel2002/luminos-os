#!/bin/bash
set -euo pipefail

# ============================================================================
# Luminos OS — Smart Resumable Build
# ============================================================================
# Replaces build_iso.sh. Tracks completed stages with flag files.
# Safe to rerun after any failure — resumes from where it left off.
# ============================================================================

UBUNTU_VERSION="24.04"
UBUNTU_CODENAME="noble"
BUILD_DIR="$(pwd)/build"
CHROOT_DIR="$BUILD_DIR/chroot"
ISO_DIR="$BUILD_DIR/iso"
OUTPUT_ISO="$BUILD_DIR/luminos-os-v0.1.0.iso"
LOG="$BUILD_DIR/build.log"
START_TIME=$(date +%s)

# Flag files inside chroot (survive across runs)
FLAG_BOOTSTRAP="$CHROOT_DIR/.stage1_done"
FLAG_PREPARE="$CHROOT_DIR/.stage2_done"
FLAG_STRIP="$CHROOT_DIR/.strip_done"
FLAG_INSTALL="$CHROOT_DIR/.luminos_installed"
FLAG_CONFIGURE="$CHROOT_DIR/.stage5_done"
FLAG_CLEANUP="$CHROOT_DIR/.stage6_done"

# ============================================================================
# Helpers
# ============================================================================

log_stage() {
  local action=$1 stage=$2 desc=$3
  if [ "$action" = "SKIP" ]; then
    echo "--- Stage $stage: SKIP ($desc) ---" | tee -a "$LOG"
  else
    echo "--- Stage $stage: RUN ($desc) ---" | tee -a "$LOG"
  fi
}

umount_chroot() {
  local chroot=$1
  for mnt in \
    "$chroot/dev/pts" \
    "$chroot/dev/shm" \
    "$chroot/dev/mqueue" \
    "$chroot/dev/hugepages" \
    "$chroot/dev" \
    "$chroot/proc" \
    "$chroot/sys/fs/cgroup" \
    "$chroot/sys" \
    "$chroot/run"; do
    mountpoint -q "$mnt" 2>/dev/null && umount -lf "$mnt" 2>/dev/null || true
  done
  sleep 1
}

is_chroot_mounted() {
  mountpoint -q "$CHROOT_DIR/proc" 2>/dev/null
}

mount_chroot() {
  # Only mount if not already mounted
  if ! is_chroot_mounted; then
    mount --bind /dev "$CHROOT_DIR/dev"
    mount --bind /proc "$CHROOT_DIR/proc"
    mount --bind /sys "$CHROOT_DIR/sys"
    mount --bind /dev/pts "$CHROOT_DIR/dev/pts"
  fi
}

ensure_chroot_ready() {
  # Mount chroot + copy source if needed
  mount_chroot
  if [ ! -d "$CHROOT_DIR/luminos-build/src" ]; then
    mkdir -p "$CHROOT_DIR/luminos-build"
    rsync -a --exclude=build --exclude=.git . "$CHROOT_DIR/luminos-build/"
  fi
  # Network for apt
  cp /etc/resolv.conf "$CHROOT_DIR/etc/" 2>/dev/null || true
}

check_deps() {
  local deps=(debootstrap squashfs-tools \
    xorriso grub-pc-bin grub-efi-amd64-bin \
    mtools dosfstools qemu-utils rsync lsof)
  local missing=()
  for dep in "${deps[@]}"; do
    if ! dpkg -l "$dep" &>/dev/null; then
      missing+=("$dep")
    fi
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "Installing: ${missing[*]}"
    apt install -y "${missing[@]}"
  fi
}

# ============================================================================
# Stage 1: Bootstrap Ubuntu base
# ============================================================================
stage1_bootstrap() {
  # Valid chroot = python3 exists from a completed debootstrap
  if [ -f "$FLAG_BOOTSTRAP" ] && [ -x "$CHROOT_DIR/usr/bin/python3" ]; then
    log_stage SKIP 1 "valid chroot exists with python3"
    return 0
  fi

  log_stage RUN 1 "bootstrap Ubuntu $UBUNTU_CODENAME"

  # Unmount any leftover mounts — never rm -rf
  umount_chroot "$CHROOT_DIR" 2>/dev/null || true
  mkdir -p "$CHROOT_DIR"

  export http_proxy=""
  export https_proxy=""
  export no_proxy=""

  # Remove any cached partial downloads (BUG-015)
  rm -rf "$CHROOT_DIR/debootstrap" 2>/dev/null || true

  debootstrap --arch=amd64 \
    "$UBUNTU_CODENAME" \
    "$CHROOT_DIR" \
    http://ca.archive.ubuntu.com/ubuntu/

  touch "$FLAG_BOOTSTRAP"
  echo "Stage 1 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 2: Prepare chroot (mounts + copy source)
# ============================================================================
stage2_prepare() {
  if [ -f "$FLAG_PREPARE" ] && [ -d "$CHROOT_DIR/luminos-build/src" ]; then
    log_stage SKIP 2 "chroot already prepared"
    # Still ensure mounts are up for later stages
    mount_chroot
    cp /etc/resolv.conf "$CHROOT_DIR/etc/" 2>/dev/null || true
    return 0
  fi

  log_stage RUN 2 "prepare chroot"
  ensure_chroot_ready

  touch "$FLAG_PREPARE"
  echo "Stage 2 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 3: Strip Ubuntu + install Sway stack
# ============================================================================
stage3_strip() {
  if [ -f "$FLAG_STRIP" ]; then
    log_stage SKIP 3 "strip already done"
    return 0
  fi

  log_stage RUN 3 "strip Ubuntu + install Sway stack"
  ensure_chroot_ready

  chroot "$CHROOT_DIR" /bin/bash \
    /luminos-build/scripts/strip_ubuntu.sh \
    2>&1 | tee -a "$LOG"

  touch "$FLAG_STRIP"
  echo "Stage 3 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 4: Install Luminos components
# ============================================================================
stage4_install() {
  if [ -f "$FLAG_INSTALL" ]; then
    log_stage SKIP 4 "Luminos already installed"
    return 0
  fi

  log_stage RUN 4 "install Luminos components"
  ensure_chroot_ready

  chroot "$CHROOT_DIR" /bin/bash \
    /luminos-build/scripts/install_luminos.sh \
    2>&1 | tee -a "$LOG"

  touch "$FLAG_INSTALL"
  echo "Stage 4 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 5: Configure system (kernel, locale, user, sessions)
# ============================================================================
stage5_configure() {
  if [ -f "$FLAG_CONFIGURE" ]; then
    log_stage SKIP 5 "system already configured"
    return 0
  fi

  log_stage RUN 5 "configure system"
  ensure_chroot_ready

  # Hostname
  echo "luminos-os" > "$CHROOT_DIR/etc/hostname"

  # Locale
  chroot "$CHROOT_DIR" locale-gen en_US.UTF-8
  chroot "$CHROOT_DIR" update-locale LANG=en_US.UTF-8

  # Timezone default UTC
  chroot "$CHROOT_DIR" ln -sf /usr/share/zoneinfo/UTC /etc/localtime

  # Create live user (BUG-020: check if exists first)
  chroot "$CHROOT_DIR" id luminos &>/dev/null || \
    chroot "$CHROOT_DIR" useradd -m -s /bin/bash \
    -G sudo,video,audio,input,kvm luminos
  echo "luminos:luminos" | chroot "$CHROOT_DIR" chpasswd || true

  # Auto-login for live session
  mkdir -p "$CHROOT_DIR/etc/lightdm"
  cat > "$CHROOT_DIR/etc/lightdm/lightdm.conf" << EOF
[Seat:*]
autologin-user=luminos
autologin-user-timeout=0
user-session=luminos
EOF

  # Luminos session file
  mkdir -p "$CHROOT_DIR/usr/share/wayland-sessions"
  cat > "$CHROOT_DIR/usr/share/wayland-sessions/luminos.desktop" << EOF
[Desktop Entry]
Name=Luminos
Comment=Luminos OS Desktop
Exec=/usr/local/bin/luminos-session
Type=Application
EOF

  # Copy sway config
  mkdir -p "$CHROOT_DIR/etc/sway"
  chroot "$CHROOT_DIR" python3 -c "
from sys import path
path.insert(0, '/opt/luminos')
from src.compositor.compositor_config import write_config
write_config('/etc/sway/config')
" 2>/dev/null || echo "WARN: sway config generation failed (non-fatal)"

  # Install kernel + live boot packages (BUG-017, BUG-021)
  chroot "$CHROOT_DIR" apt-get install -y \
    linux-image-generic \
    initramfs-tools \
    casper \
    os-prober || true \
    2>&1 | tee -a "$LOG"

  # Verify kernel installed
  if ! ls "$CHROOT_DIR"/boot/vmlinuz* &>/dev/null; then
    echo "ERROR: Kernel not found after install — stage 5 failed"
    exit 1
  fi
  echo "OK: Kernel found at $(ls "$CHROOT_DIR"/boot/vmlinuz* | head -1)"

  touch "$FLAG_CONFIGURE"
  echo "Stage 5 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 6: Cleanup chroot (apt clean, unmount)
# ============================================================================
stage6_cleanup() {
  if [ -f "$FLAG_CLEANUP" ]; then
    log_stage SKIP 6 "cleanup already done"
    return 0
  fi

  log_stage RUN 6 "cleanup chroot"

  # Only run apt clean if chroot is mounted
  if is_chroot_mounted; then
    chroot "$CHROOT_DIR" apt clean 2>/dev/null || true
    chroot "$CHROOT_DIR" apt autoremove -y 2>/dev/null || true
  fi

  rm -rf "$CHROOT_DIR/luminos-build" 2>/dev/null || true
  rm -rf "$CHROOT_DIR/tmp/"* 2>/dev/null || true
  rm -f "$CHROOT_DIR/etc/resolv.conf" 2>/dev/null || true

  umount_chroot "$CHROOT_DIR"

  touch "$FLAG_CLEANUP"
  echo "Stage 6 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 7: Build squashfs
# ============================================================================
stage7_squashfs() {
  if [ -f "$ISO_DIR/casper/filesystem.squashfs" ]; then
    log_stage SKIP 7 "squashfs already exists"
    return 0
  fi

  log_stage RUN 7 "build squashfs"

  # Verify kernel is present before building squashfs
  if ! ls "$CHROOT_DIR"/boot/vmlinuz* &>/dev/null; then
    echo "ERROR: No kernel in chroot — cannot build squashfs"
    echo "Run: reset_build.sh 5  (then rerun smart_build.sh)"
    exit 1
  fi

  # Ensure chroot is unmounted before squashfs (cleaner image)
  umount_chroot "$CHROOT_DIR" 2>/dev/null || true

  mkdir -p "$ISO_DIR/casper"
  mksquashfs "$CHROOT_DIR" \
    "$ISO_DIR/casper/filesystem.squashfs" \
    -comp xz -b 1M -no-progress \
    -e "$CHROOT_DIR/proc" \
    -e "$CHROOT_DIR/sys" \
    -e "$CHROOT_DIR/dev" \
    -e "$CHROOT_DIR/run" \
    -e "$CHROOT_DIR/tmp" \
    2>&1 | tee -a "$LOG"

  # Filesystem size for installer
  printf "$(du -sx --block-size=1 "$CHROOT_DIR" | cut -f1)" > \
    "$ISO_DIR/casper/filesystem.size"

  echo "Stage 7 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 8: Build bootable ISO
# ============================================================================
stage8_iso() {
  if [ -f "$OUTPUT_ISO" ]; then
    log_stage SKIP 8 "ISO already exists: $OUTPUT_ISO"
    return 0
  fi

  log_stage RUN 8 "build ISO"

  mkdir -p "$ISO_DIR/boot/grub"
  mkdir -p "$ISO_DIR/EFI/boot"

  # GRUB config — copy if exists, generate inline if missing (BUG-016)
  cp build/grub.cfg "$ISO_DIR/boot/grub/" 2>/dev/null || \
  cat > "$ISO_DIR/boot/grub/grub.cfg" << 'GRUBEOF'
set default=0
set timeout=5

menuentry "Luminos OS" {
  insmod all_video
  linux /casper/vmlinuz boot=casper quiet splash
  initrd /casper/initrd
}

menuentry "Luminos OS (Safe Graphics)" {
  linux /casper/vmlinuz boot=casper nomodeset
  initrd /casper/initrd
}

menuentry "Install Luminos to Disk" {
  linux /casper/vmlinuz boot=casper only-ubiquity quiet splash
  initrd /casper/initrd
}
GRUBEOF

  # Find vmlinuz and initrd (BUG-017)
  VMLINUZ=$(find "$CHROOT_DIR/boot" -name "vmlinuz*" 2>/dev/null | head -1)
  INITRD=$(find "$CHROOT_DIR/boot" -name "initrd*" 2>/dev/null | head -1)

  if [ -z "$VMLINUZ" ]; then
    echo "ERROR: No kernel found in chroot/boot"
    echo "Run: reset_build.sh 5  (then rerun smart_build.sh)"
    exit 1
  fi

  cp "$VMLINUZ" "$ISO_DIR/casper/vmlinuz"
  cp "$INITRD" "$ISO_DIR/casper/initrd"

  # Build EFI image
  grub-mkstandalone \
    --format=x86_64-efi \
    --output="$ISO_DIR/EFI/boot/bootx64.efi" \
    --modules="part_gpt fat" \
    "boot/grub/grub.cfg=$ISO_DIR/boot/grub/grub.cfg"

  # Build ISO with xorriso
  xorriso -as mkisofs \
    -iso-level 3 \
    -full-iso9660-filenames \
    -volid "LUMINOS_OS" \
    -eltorito-boot boot/grub/bios.img \
    -no-emul-boot -boot-load-size 4 \
    -boot-info-table --eltorito-catalog \
      boot/grub/boot.cat \
    --grub2-boot-info --grub2-mbr \
      /usr/lib/grub/i386-pc/boot_hybrid.img \
    -eltorito-alt-boot \
    -e EFI/boot/efiboot.img \
    -no-emul-boot \
    -append_partition 2 0xef \
      "$ISO_DIR/EFI/boot/efiboot.img" \
    -output "$OUTPUT_ISO" \
    -graft-points "$ISO_DIR" \
    2>&1 | tee -a "$LOG"

  echo "Stage 8 complete" | tee -a "$LOG"
}

# ============================================================================
# Main
# ============================================================================
echo "=== Luminos OS Smart Builder ===" | tee "$LOG"
echo "Ubuntu base: $UBUNTU_VERSION ($UBUNTU_CODENAME)"
echo "Output: $OUTPUT_ISO"
echo ""

# Safety: unmount any stale mounts from previous crashed runs
umount_chroot "$CHROOT_DIR" 2>/dev/null || true
mkdir -p "$BUILD_DIR" "$CHROOT_DIR" "$ISO_DIR"

check_deps

# Run stages in correct order — each stage skips if already done
stage1_bootstrap
stage2_prepare
stage3_strip
stage4_install
stage5_configure
stage6_cleanup     # cleanup + unmount BEFORE squashfs
stage7_squashfs    # reads files from chroot (no mounts needed)
stage8_iso         # reads kernel from chroot/boot

echo ""
echo "=== BUILD COMPLETE ==="
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
if [ -f "$OUTPUT_ISO" ]; then
  ISO_SIZE=$(du -sh "$OUTPUT_ISO" | cut -f1)
  echo "ISO: $OUTPUT_ISO"
  echo "Size: $ISO_SIZE"
fi
echo "Time: $((ELAPSED/60))m $((ELAPSED%60))s"
echo "Log: $LOG"
