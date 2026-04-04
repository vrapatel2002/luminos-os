#!/bin/bash
set -e

LUMINOS_SRC="/opt/luminos"
LUMINOS_CONF="/etc/luminos"
LUMINOS_DATA="/usr/share/luminos"
LUMINOS_LIB="/usr/lib/luminos"
LUMINOS_BIN="/usr/local/bin"

echo "=== Installing Luminos OS Components ==="

# 1. Create directory structure
mkdir -p $LUMINOS_SRC $LUMINOS_CONF \
  $LUMINOS_DATA/wallpapers \
  $LUMINOS_LIB/models \
  $LUMINOS_LIB/kernels

# 2. Copy source
cp -r /luminos-build/src $LUMINOS_SRC/
cp -r /luminos-build/config $LUMINOS_SRC/
cp -r /luminos-build/systemd $LUMINOS_SRC/

# 3. Install Python dependencies
pip3 install -r /luminos-build/requirements.txt \
  --break-system-packages \
  --ignore-installed \
  2>&1 || true

# 4. Install systemd services
cp $LUMINOS_SRC/systemd/luminos-ai.service \
  /etc/systemd/system/
systemctl enable luminos-ai || true

# 5. Install compatibility layer
bash /luminos-build/scripts/install_compatibility.sh

# 6. Install Firecracker
if ! command -v firecracker &>/dev/null; then
  # Try pacman first (available via archiso profile)
  pacman -S --noconfirm --needed firecracker 2>/dev/null || {
    # Fallback: download binary directly
    FIRECRACKER_VER="1.7.0"
    wget -q "https://github.com/firecracker-microvm/firecracker/releases/download/v${FIRECRACKER_VER}/firecracker-v${FIRECRACKER_VER}-x86_64.tgz" \
      -O /tmp/firecracker.tgz
    tar -xf /tmp/firecracker.tgz -C /tmp/
    cp "/tmp/release-v${FIRECRACKER_VER}-x86_64/firecracker-v${FIRECRACKER_VER}-x86_64" \
      "$LUMINOS_BIN/firecracker"
    chmod +x "$LUMINOS_BIN/firecracker"
    rm -f /tmp/firecracker.tgz
  }
fi

# 7. Create launcher scripts
create_launcher() {
  local name=$1 script=$2
  cat > $LUMINOS_BIN/$name << EOF
#!/bin/bash
exec python3 $LUMINOS_SRC/$script "\$@"
EOF
  chmod +x $LUMINOS_BIN/$name
}

create_launcher "luminos-bar" "src/gui/bar/bar_app.py"
create_launcher "luminos-dock" "src/gui/dock/dock_app.py"
create_launcher "luminos-store" "src/gui/store/store_app.py"
create_launcher "luminos-settings" "src/gui/settings/settings_app.py"
create_launcher "luminos-firstrun" "src/gui/firstrun/firstrun_app.py"
create_launcher "luminos-run-windows" "src/classifier/launch.py"

# 8. Register MIME handler
cp $LUMINOS_SRC/config/luminos-windows.desktop \
  /usr/share/applications/
update-desktop-database 2>/dev/null || \
  mkdir -p /usr/share/applications && \
  echo "Desktop database update skipped"

# 9. Copy default wallpaper
cp /luminos-build/assets/wallpaper-default.jpg \
  $LUMINOS_DATA/wallpapers/ 2>/dev/null || true

# 10. Set permissions
chown -R root:root $LUMINOS_SRC
chmod -R 755 $LUMINOS_SRC

echo "=== Luminos Installation Complete ==="
