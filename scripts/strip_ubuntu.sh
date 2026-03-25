#!/bin/bash

# Fix locale
export DEBIAN_FRONTEND=noninteractive
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# Fix apt sources with universe repo
cat > /etc/apt/sources.list << 'EOF'
deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-security main restricted universe multiverse
EOF
apt-get update -qq

# Install pip manually since not in minimal
apt-get install -y python3-pip python3-venv || \
  apt-get install -y python3 && \
  curl -sS https://bootstrap.pypa.io/get-pip.py | python3

# Remove snap entirely
apt purge -y snapd
rm -rf /snap /var/snap /var/lib/snapd
apt-mark hold snapd

# Remove Ubuntu Pro / Advantage
apt purge -y ubuntu-advantage-tools \
  ubuntu-pro-client

# Remove telemetry
apt purge -y whoopsie apport \
  popularity-contest ubuntu-report \
  kerneloops

# Remove GNOME shell (replaced by Sway)
apt purge -y gnome-shell gdm3 \
  gnome-session ubuntu-desktop \
  gnome-terminal nautilus

# Remove unnecessary services
systemctl disable --now \
  apport whoopsie ModemManager \
  bluetooth 2>/dev/null || true  # re-enable after bluez install

# Install Sway stack
apt-get install -y --no-install-recommends \
  sway swaybg swayidle waybar xwayland \
  wl-clipboard grim slurp foot wofi \
  mako-notifier network-manager bluez \
  pipewire pipewire-pulse wireplumber \
  libgtk-4-dev libadwaita-1-dev \
  python3-gi python3-gi-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 \
  fonts-noto-core papirus-icon-theme \
  flatpak curl wget git unzip \
  python3-pip build-essential || true

# Add Flathub
which flatpak && flatpak remote-add \
  --if-not-exists flathub \
  https://flathub.org/repo/flathub.flatpakrepo \
  2>/dev/null || true

# Install fonts
# Papirus icons
apt install -y papirus-icon-theme

# Inter font
mkdir -p /usr/share/fonts/inter
wget -q "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip" \
  -O /tmp/inter.zip || true
unzip -q /tmp/inter.zip -d /tmp/inter 2>/dev/null || true
find /tmp/inter -name "*.ttf" -exec cp {} \
  /usr/share/fonts/inter/ \; 2>/dev/null || true
fc-cache -f 2>/dev/null || true

# gtk4-layer-shell (build from source)
apt-get install -y meson ninja-build \
  libwayland-dev gobject-introspection \
  libgirepository1.0-dev || true
git clone --depth 1 \
  https://github.com/wmww/gtk4-layer-shell.git \
  /tmp/gtk4-layer-shell 2>/dev/null || true
cd /tmp/gtk4-layer-shell
meson setup build \
  -Dexamples=false -Ddocs=false 2>/dev/null || true
ninja -C build 2>/dev/null || true
ninja -C build install 2>/dev/null || true
ldconfig || true
cd /

# swww for wallpaper
wget -q "https://github.com/LGFae/swww/releases/\
latest/download/swww-x86_64-unknown-linux-musl.tar.gz" \
  -O /tmp/swww.tar.gz || true
tar -xf /tmp/swww.tar.gz -C /tmp/ 2>/dev/null || true
cp /tmp/swww /usr/local/bin/ 2>/dev/null || true
cp /tmp/swww-daemon /usr/local/bin/ 2>/dev/null || true
chmod +x /usr/local/bin/swww* 2>/dev/null || true

# python-pam for lock screen
python3 -m pip install python-pam \
  --break-system-packages 2>/dev/null || \
pip3 install python-pam \
  --break-system-packages 2>/dev/null || true
