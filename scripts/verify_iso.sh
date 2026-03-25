#!/bin/bash
ISO=$1
PASS=0 FAIL=0

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
mount -o loop,ro $ISO $MOUNT

# Checks
check "ISO exists and > 500MB" \
  $([ -f "$ISO" ] && \
    [ $(stat -c%s "$ISO") -gt 524288000 ] \
    && echo true || echo false)

check "Kernel present" \
  $([ -f "$MOUNT/casper/vmlinuz" ] \
    && echo true || echo false)

check "Squashfs present" \
  $([ -f "$MOUNT/casper/filesystem.squashfs" ] \
    && echo true || echo false)

check "GRUB config present" \
  $([ -f "$MOUNT/boot/grub/grub.cfg" ] \
    && echo true || echo false)

# Mount squashfs and check internals
SQMOUNT=$(mktemp -d)
mount -t squashfs $MOUNT/casper/filesystem.squashfs $SQMOUNT

check "Luminos daemon present" \
  $([ -f "$SQMOUNT/opt/luminos/src/daemon/main.py" ] \
    && echo true || echo false)

check "systemd service present" \
  $([ -f "$SQMOUNT/etc/systemd/system/luminos-ai.service" ] \
    && echo true || echo false)

check "Sway installed" \
  $([ -f "$SQMOUNT/usr/bin/sway" ] \
    && echo true || echo false)

check "Wine64 installed" \
  $([ -f "$SQMOUNT/usr/bin/wine" ] \
    && echo true || echo false)

check "Firecracker installed" \
  $([ -f "$SQMOUNT/usr/local/bin/firecracker" ] \
    && echo true || echo false)

check "GTK4 present" \
  $([ -d "$SQMOUNT/usr/lib/x86_64-linux-gnu/" ] && \
    ls "$SQMOUNT/usr/lib/x86_64-linux-gnu"/libgtk-4* >/dev/null 2>&1 \
    && echo true || echo false)

check "Papirus icons present" \
  $([ -d "$SQMOUNT/usr/share/icons/Papirus" ] \
    && echo true || echo false)

check "First run launcher present" \
  $([ -f "$SQMOUNT/usr/local/bin/luminos-firstrun" ] \
    && echo true || echo false)

# Cleanup
umount $SQMOUNT $MOUNT
rmdir $SQMOUNT $MOUNT

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] && exit 0 || exit 1
