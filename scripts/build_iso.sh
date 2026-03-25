#!/bin/bash
set -euo pipefail

UBUNTU_VERSION="24.04"
UBUNTU_CODENAME="noble"
BUILD_DIR="$(pwd)/build"
CHROOT_DIR="$BUILD_DIR/chroot"
ISO_DIR="$BUILD_DIR/iso"
OUTPUT_ISO="$BUILD_DIR/luminos-os-v0.1.0.iso"
LOG="$BUILD_DIR/build.log"
START_TIME=$(date +%s)

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
    umount -lf "$mnt" 2>/dev/null || true
  done
  sleep 2
}

safe_cleanup() {
  local chroot=$1
  [ -z "$chroot" ] && return 0
  [ "$chroot" = "/" ] && return 0
  [ ! -d "$chroot" ] && return 0

  echo "Cleaning up chroot: $chroot"

  # Step 1: Kill anything running in chroot
  for pid in $(lsof +D "$chroot" 2>/dev/null \
    | awk 'NR>1 {print $2}' | sort -u); do
    kill -9 $pid 2>/dev/null || true
  done
  sleep 2

  # Step 2: Lazy force unmount everything
  # Order matters — children before parents
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
    umount -lf "$mnt" 2>/dev/null || true
  done
  sleep 2

  # Step 3: Check if proc is really unmounted
  if mountpoint -q "$chroot/proc" 2>/dev/null
  then
    echo "WARNING: proc still mounted, forcing"
    umount -lf "$chroot/proc" 2>/dev/null || true
    sleep 3
  fi

  # Step 4: Remove everything EXCEPT proc/sys/dev
  # using find with pruning
  find "$chroot" \
    -mindepth 1 -maxdepth 1 \
    ! -name "proc" \
    ! -name "sys" \
    ! -name "dev" \
    -exec rm -rf {} + 2>/dev/null || true

  # Step 5: Now proc/sys/dev should be empty
  # virtual dirs — safe to rmdir
  rmdir "$chroot/proc" 2>/dev/null || true
  rmdir "$chroot/sys" 2>/dev/null || true
  rmdir "$chroot/dev" 2>/dev/null || true
  rmdir "$chroot" 2>/dev/null || true

  echo "Cleanup complete"
}

echo "=== Luminos OS ISO Builder ===" | tee $LOG
echo "Ubuntu base: $UBUNTU_VERSION ($UBUNTU_CODENAME)"
echo "Output: $OUTPUT_ISO"

# Check dependencies
check_deps() {
  local deps=(debootstrap squashfs-tools \
    xorriso grub-pc-bin grub-efi-amd64-bin \
    mtools dosfstools qemu-utils rsync lsof)
  local missing=()
  for dep in "${deps[@]}"; do
    if ! dpkg -l $dep &>/dev/null; then
      missing+=($dep)
    fi
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "Installing: ${missing[*]}"
    apt install -y "${missing[@]}"
  fi
}

# Stage 1: Bootstrap Ubuntu base
stage1_bootstrap() {
  echo "--- Stage 1: Bootstrap Ubuntu $UBUNTU_CODENAME ---"
  # Just unmount — never rm -rf at start (BUG-012)
  umount_chroot $CHROOT_DIR 2>/dev/null || true
  # debootstrap will overwrite existing chroot
  mkdir -p $CHROOT_DIR
  export http_proxy=""
  export https_proxy=""
  export no_proxy=""
  # Remove any cached partial downloads (BUG-015)
  rm -rf $CHROOT_DIR/debootstrap 2>/dev/null || true
  debootstrap --arch=amd64 \
    $UBUNTU_CODENAME \
    $CHROOT_DIR \
    http://ca.archive.ubuntu.com/ubuntu/
  echo "Stage 1 complete" | tee -a $LOG
}

# Stage 2: Prepare chroot
stage2_prepare() {
  echo "--- Stage 2: Prepare chroot ---"
  mount --bind /dev $CHROOT_DIR/dev
  mount --bind /proc $CHROOT_DIR/proc
  mount --bind /sys $CHROOT_DIR/sys
  mount --bind /dev/pts $CHROOT_DIR/dev/pts

  # Copy Luminos source into chroot
  mkdir -p $CHROOT_DIR/luminos-build
  rsync -a --exclude=build --exclude=.git . $CHROOT_DIR/luminos-build/

  # Network for apt
  cp /etc/resolv.conf $CHROOT_DIR/etc/
  echo "Stage 2 complete" | tee -a $LOG
}

# Stage 3: Strip Ubuntu + install Sway stack
stage3_strip() {
  echo "--- Stage 3: Strip Ubuntu ---"
  chroot $CHROOT_DIR /bin/bash \
    /luminos-build/scripts/strip_ubuntu.sh \
    2>&1 | tee -a $LOG
  echo "Stage 3 complete" | tee -a $LOG
}

# Stage 4: Install Luminos
stage4_install() {
  echo "--- Stage 4: Install Luminos ---"
  chroot $CHROOT_DIR /bin/bash \
    /luminos-build/scripts/install_luminos.sh \
    2>&1 | tee -a $LOG
  echo "Stage 4 complete" | tee -a $LOG
}

# Stage 5: Configure system
stage5_configure() {
  echo "--- Stage 5: Configure system ---"

  # Hostname
  echo "luminos-os" > $CHROOT_DIR/etc/hostname

  # Locale
  chroot $CHROOT_DIR locale-gen en_US.UTF-8
  chroot $CHROOT_DIR update-locale \
    LANG=en_US.UTF-8

  # Timezone default UTC
  chroot $CHROOT_DIR ln -sf \
    /usr/share/zoneinfo/UTC \
    /etc/localtime

  # Create live user
  chroot $CHROOT_DIR useradd -m -s /bin/bash \
    -G sudo,video,audio,input,kvm luminos
  echo "luminos:luminos" | \
    chroot $CHROOT_DIR chpasswd
  # First run will change this

  # Auto-login for live session
  mkdir -p $CHROOT_DIR/etc/lightdm
  cat > $CHROOT_DIR/etc/lightdm/lightdm.conf << EOF
[Seat:*]
autologin-user=luminos
autologin-user-timeout=0
user-session=luminos
EOF

  # Luminos session file
  mkdir -p $CHROOT_DIR/usr/share/wayland-sessions
  cat > $CHROOT_DIR/usr/share/wayland-sessions/luminos.desktop << EOF
[Desktop Entry]
Name=Luminos
Comment=Luminos OS Desktop
Exec=/usr/local/bin/luminos-session
Type=Application
EOF

  # Copy sway config
  mkdir -p $CHROOT_DIR/etc/sway
  chroot $CHROOT_DIR python3 -c "
from sys import path
path.insert(0, '/opt/luminos')
from src.compositor.compositor_config import write_config
write_config('/etc/sway/config')
"
  echo "Stage 5 complete" | tee -a $LOG
}

# Stage 6: Cleanup chroot
stage6_cleanup() {
  echo "--- Stage 6: Cleanup ---"
  chroot $CHROOT_DIR apt clean
  chroot $CHROOT_DIR apt autoremove -y
  rm -rf $CHROOT_DIR/luminos-build
  rm -rf $CHROOT_DIR/tmp/*
  rm -f $CHROOT_DIR/etc/resolv.conf

  # Unmount only — chroot files still needed for squashfs
  umount_chroot $CHROOT_DIR
  echo "Stage 6 complete" | tee -a $LOG
}

# Stage 7: Build squashfs
stage7_squashfs() {
  echo "--- Stage 7: Build squashfs ---"
  mkdir -p $ISO_DIR/casper
  mksquashfs $CHROOT_DIR \
    $ISO_DIR/casper/filesystem.squashfs \
    -comp xz -b 1M -no-progress \
    -e $CHROOT_DIR/proc \
    -e $CHROOT_DIR/sys \
    -e $CHROOT_DIR/dev \
    -e $CHROOT_DIR/run \
    -e $CHROOT_DIR/tmp \
    2>&1 | tee -a $LOG

  # Filesystem size for installer
  printf $(du -sx --block-size=1 \
    $CHROOT_DIR | cut -f1) > \
    $ISO_DIR/casper/filesystem.size

  echo "Stage 7 complete" | tee -a $LOG
}

# Stage 8: Build bootable ISO
stage8_iso() {
  echo "--- Stage 8: Build ISO ---"
  mkdir -p $ISO_DIR/boot/grub
  mkdir -p $ISO_DIR/EFI/boot

  # GRUB config
  cp build/grub.cfg $ISO_DIR/boot/grub/

  # Copy kernel + initrd from chroot
  cp $CHROOT_DIR/boot/vmlinuz \
    $ISO_DIR/casper/vmlinuz
  cp $CHROOT_DIR/boot/initrd.img \
    $ISO_DIR/casper/initrd

  # Build EFI image
  grub-mkstandalone \
    --format=x86_64-efi \
    --output=$ISO_DIR/EFI/boot/bootx64.efi \
    --modules="part_gpt fat" \
    boot/grub/grub.cfg=$ISO_DIR/boot/grub/grub.cfg

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
      $ISO_DIR/EFI/boot/efiboot.img \
    -output $OUTPUT_ISO \
    -graft-points $ISO_DIR \
    2>&1 | tee -a $LOG

  echo "Stage 8 complete" | tee -a $LOG
}

# Main
# Only unmount at start — never rm -rf (BUG-012)
umount_chroot "$CHROOT_DIR" 2>/dev/null || true
mkdir -p $BUILD_DIR $CHROOT_DIR $ISO_DIR

check_deps
stage1_bootstrap
stage2_prepare
stage3_strip
stage4_install
stage5_configure
stage7_squashfs
stage6_cleanup
stage8_iso
# Only safe to delete chroot AFTER squashfs + ISO are built (BUG-012)
safe_cleanup $CHROOT_DIR

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ISO_SIZE=$(du -sh $OUTPUT_ISO | cut -f1)

echo ""
echo "=== BUILD COMPLETE ==="
echo "ISO: $OUTPUT_ISO"
echo "Size: $ISO_SIZE"
echo "Time: $((ELAPSED/60))m $((ELAPSED%60))s"
echo "Log: $LOG"
