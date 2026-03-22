#!/bin/bash
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
  bluetooth  # re-enable after bluez install

# Install Sway stack
apt install -y sway swaybar swaybg swayidle \
  swaylock waybar xwayland \
  wl-clipboard grim slurp \
  alacritty foot \
  wofi \
  mako-notifier \
  network-manager nm-tui \
  bluez blueman \
  pavucontrol pipewire pipewire-pulse \
  flatpak \
  gtk4 libadwaita-1-dev \
  python3-pip python3-venv \
  python3-gi gir1.2-gtk-4.0 \
  gir1.2-adw-1

# Add Flathub
flatpak remote-add --if-not-exists flathub \
  https://flathub.org/repo/flathub.flatpakrepo

# Install fonts
apt install -y fonts-inter fonts-noto
# Papirus icons
apt install -y papirus-icon-theme

# gtk4-layer-shell (build from source or PPA)
apt install -y libgtk4-layer-shell-dev || \
  build_gtk4_layer_shell

# swww for wallpaper
apt install -y swww || build_swww_from_source

# python-pam for lock screen
pip3 install python-pam --break-system-packages
