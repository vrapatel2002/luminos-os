#!/bin/bash
ISO=$1
PASS=0 FAIL=0

if [ -z "$ISO" ]; then
  echo "Usage: verify_iso.sh <path-to-iso>"
  exit 1
fi

check() {
  local desc=$1 result=$2
  if [ "$result" = "true" ]; then
    echo "✓ $desc"
    PASS=$((PASS+1))
  else
    echo "✗ $desc"
    FAIL=$((FAIL+1))
  fi
}

# Mount ISO
MOUNT=$(mktemp -d)
mount -o loop,ro "$ISO" "$MOUNT"

# Basic ISO checks
check "ISO exists and > 500MB" \
  $([ -f "$ISO" ] && \
    [ $(stat -c%s "$ISO") -gt 524288000 ] \
    && echo true || echo false)

check "Kernel present (arch/boot)" \
  $(ls "$MOUNT"/arch/boot/x86_64/vmlinuz* &>/dev/null \
    && echo true || echo false)

check "Initramfs present (arch/boot)" \
  $(ls "$MOUNT"/arch/boot/x86_64/initramfs* &>/dev/null \
    && echo true || echo false)

check "Root filesystem image present" \
  $([ -f "$MOUNT/arch/x86_64/airootfs.sfs" ] || \
   [ -f "$MOUNT/arch/x86_64/airootfs.erofs" ] \
    && echo true || echo false)

check "GRUB config present" \
  $([ -f "$MOUNT/boot/grub/grub.cfg" ] \
    && echo true || echo false)

# Mount the root filesystem and check internals
SQMOUNT=$(mktemp -d)
if [ -f "$MOUNT/arch/x86_64/airootfs.sfs" ]; then
  mount -t squashfs "$MOUNT/arch/x86_64/airootfs.sfs" "$SQMOUNT"
elif [ -f "$MOUNT/arch/x86_64/airootfs.erofs" ]; then
  mount -t erofs "$MOUNT/arch/x86_64/airootfs.erofs" "$SQMOUNT"
else
  echo "✗ Could not find root filesystem image"
  FAIL=$((FAIL+1))
fi

if mountpoint -q "$SQMOUNT"; then
  check "Luminos daemon present" \
    $([ -f "$SQMOUNT/opt/luminos/src/daemon/main.py" ] \
      && echo true || echo false)

  check "systemd service present" \
    $([ -f "$SQMOUNT/etc/systemd/system/luminos-ai.service" ] \
      && echo true || echo false)

  check "Hyprland installed" \
    $([ -f "$SQMOUNT/usr/bin/Hyprland" ] \
      && echo true || echo false)

  check "Wine installed" \
    $([ -f "$SQMOUNT/usr/bin/wine" ] || [ -f "$SQMOUNT/usr/bin/wine64" ] \
      && echo true || echo false)

  check "Firecracker installed" \
    $([ -f "$SQMOUNT/usr/bin/firecracker" ] || \
     [ -f "$SQMOUNT/usr/local/bin/firecracker" ] \
      && echo true || echo false)

  check "GTK4 present" \
    $(ls "$SQMOUNT/usr/lib"/libgtk-4* &>/dev/null \
      && echo true || echo false)

  check "Papirus icons present" \
    $([ -d "$SQMOUNT/usr/share/icons/Papirus" ] \
      && echo true || echo false)

  check "First run launcher present" \
    $([ -f "$SQMOUNT/usr/local/bin/luminos-firstrun" ] \
      && echo true || echo false)

  check "greetd config present" \
    $([ -f "$SQMOUNT/etc/greetd/config.toml" ] \
      && echo true || echo false)

  check "asusctl available" \
    $([ -f "$SQMOUNT/usr/bin/asusctl" ] \
      && echo true || echo false)

  umount "$SQMOUNT"
fi

# Cleanup
umount "$MOUNT"
rmdir "$SQMOUNT" "$MOUNT"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] && exit 0 || exit 1
