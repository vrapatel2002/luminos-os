#!/bin/bash
set -euo pipefail

# ============================================================================
# Luminos OS — ISO Builder (Arch Linux / archiso)
# ============================================================================
# Builds a bootable Luminos OS ISO using archiso.
# Requires: archiso package installed on the build host.
# ============================================================================

BUILD_DIR="$(pwd)/build"
PROFILE_DIR="$BUILD_DIR/luminos-profile"
WORK_DIR="$BUILD_DIR/work"
OUTPUT_DIR="$BUILD_DIR/out"
LOG="$BUILD_DIR/build.log"
START_TIME=$(date +%s)

echo "=== Luminos OS ISO Builder (Arch) ===" | tee "$LOG"
echo "Output: $OUTPUT_DIR/" | tee -a "$LOG"

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------
check_deps() {
  local deps=(archiso mtools dosfstools libisoburn squashfs-tools)
  local missing=()
  for dep in "${deps[@]}"; do
    if ! pacman -Qi "$dep" &>/dev/null; then
      missing+=("$dep")
    fi
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "Installing: ${missing[*]}"
    sudo pacman -S --noconfirm --needed "${missing[@]}"
  fi
}

# ---------------------------------------------------------------------------
# Stage 1: Create archiso profile from releng template
# ---------------------------------------------------------------------------
stage1_profile() {
  echo "--- Stage 1: Create archiso profile ---" | tee -a "$LOG"

  if [ -d "$PROFILE_DIR" ]; then
    echo "Profile exists — refreshing"
    rm -rf "$PROFILE_DIR"
  fi

  # Start from the official releng profile
  cp -r /usr/share/archiso/configs/releng/ "$PROFILE_DIR"

  # Append Luminos packages to the package list
  cat >> "$PROFILE_DIR/packages.x86_64" << 'PACKAGES'

# --- Luminos OS packages ---
# Compositor & desktop
hyprland
xdg-desktop-portal-hyprland
xdg-desktop-portal-gtk
qt5-wayland
qt6-wayland
waybar
wofi
dunst
grim
slurp
foot
swww

# Login manager
greetd
greetd-tuigreet

# Fonts & themes
inter-font
ttf-jetbrains-mono-nerd
papirus-icon-theme
adwaita-icon-theme

# ROG hardware tools
asusctl
supergfxctl
power-profiles-daemon

# GPU drivers
nvidia
nvidia-utils
nvidia-settings
mesa
vulkan-radeon
vulkan-icd-loader
lib32-vulkan-radeon
lib32-vulkan-icd-loader
lib32-mesa

# Audio
pipewire
pipewire-pulse
pipewire-alsa
wireplumber

# Network
networkmanager

# System
polkit
xdg-user-dirs
python
python-pip
python-gobject
gtk4
libadwaita

# Wine / compatibility
wine
wine-mono
wine-gecko
winetricks
lutris

# Gaming
steam

# Firecracker
firecracker

# AI runtime
llama-cpp

# Misc tools
rsync
wget
curl
git
base-devel
zstd
unzip
PACKAGES

  echo "Stage 1 complete" | tee -a "$LOG"
}

# ---------------------------------------------------------------------------
# Stage 2: Customize airootfs (configs, users, services)
# ---------------------------------------------------------------------------
stage2_customize() {
  echo "--- Stage 2: Customize airootfs ---" | tee -a "$LOG"
  local AIROOTFS="$PROFILE_DIR/airootfs"

  # ---- Hostname ----
  echo "luminos-os" > "$AIROOTFS/etc/hostname"

  # ---- Locale ----
  mkdir -p "$AIROOTFS/etc"
  echo "en_US.UTF-8 UTF-8" > "$AIROOTFS/etc/locale.gen"
  echo "LANG=en_US.UTF-8" > "$AIROOTFS/etc/locale.conf"

  # ---- Timezone ----
  ln -sf /usr/share/zoneinfo/UTC "$AIROOTFS/etc/localtime"

  # ---- NVIDIA + Wayland environment ----
  cat > "$AIROOTFS/etc/environment" << 'ENVFILE'
LIBVA_DRIVER_NAME=nvidia
XDG_SESSION_TYPE=wayland
GBM_BACKEND=nvidia-drm
__GLX_VENDOR_LIBRARY_NAME=nvidia
WLR_NO_HARDWARE_CURSORS=1
MOZ_ENABLE_WAYLAND=1
ELECTRON_OZONE_PLATFORM_HINT=wayland
QT_QPA_PLATFORMTHEME=qt5ct
QT_AUTO_SCREEN_SCALE_FACTOR=1
GTK_THEME=Adwaita:dark
XCURSOR_THEME=Adwaita
XCURSOR_SIZE=24
ENVFILE

  # ---- Create luminos user via systemd-sysusers ----
  mkdir -p "$AIROOTFS/etc/sysusers.d"
  cat > "$AIROOTFS/etc/sysusers.d/luminos.conf" << 'SYSUSERS'
u luminos - "Luminos User" /home/luminos /bin/bash
m luminos wheel
m luminos video
m luminos audio
m luminos input
m luminos kvm
SYSUSERS

  # ---- Sudoers for wheel group ----
  mkdir -p "$AIROOTFS/etc/sudoers.d"
  echo "%wheel ALL=(ALL:ALL) ALL" > "$AIROOTFS/etc/sudoers.d/wheel"
  chmod 440 "$AIROOTFS/etc/sudoers.d/wheel"

  # ---- Enable services ----
  mkdir -p "$AIROOTFS/etc/systemd/system/multi-user.target.wants"
  local WANTS="$AIROOTFS/etc/systemd/system/multi-user.target.wants"
  ln -sf /usr/lib/systemd/system/NetworkManager.service "$WANTS/"
  ln -sf /usr/lib/systemd/system/asusd.service "$WANTS/"
  ln -sf /usr/lib/systemd/system/supergfxd.service "$WANTS/"
  ln -sf /usr/lib/systemd/system/greetd.service "$WANTS/"

  # ---- greetd config ----
  mkdir -p "$AIROOTFS/etc/greetd"
  cat > "$AIROOTFS/etc/greetd/config.toml" << 'GREETD'
[terminal]
vt = 1

[default_session]
command = "tuigreet --cmd Hyprland --time --remember --asterisks"
user = "greeter"
GREETD

  # ---- Copy Luminos source into the ISO ----
  mkdir -p "$AIROOTFS/opt/luminos"
  rsync -a --exclude=build --exclude=.git --exclude='__pycache__' \
    "$(pwd)/" "$AIROOTFS/opt/luminos/"

  # ---- Copy systemd service ----
  mkdir -p "$AIROOTFS/etc/systemd/system"
  cp "$(pwd)/systemd/luminos-ai.service" "$AIROOTFS/etc/systemd/system/"
  ln -sf /etc/systemd/system/luminos-ai.service "$WANTS/luminos-ai.service"

  # ---- Luminos session desktop entry ----
  mkdir -p "$AIROOTFS/usr/share/wayland-sessions"
  cat > "$AIROOTFS/usr/share/wayland-sessions/luminos.desktop" << 'SESSION'
[Desktop Entry]
Name=Luminos
Comment=Luminos OS Desktop
Exec=/usr/local/bin/luminos-session
Type=Application
SESSION

  # ---- Luminos session script ----
  mkdir -p "$AIROOTFS/usr/local/bin"
  cat > "$AIROOTFS/usr/local/bin/luminos-session" << 'SESSIONSCRIPT'
#!/bin/bash
# Start Luminos AI daemon
python3 /opt/luminos/src/daemon/main.py &
sleep 2

# Check first run
if [ ! -f ~/.config/luminos/.setup_complete ]; then
  python3 /opt/luminos/src/gui/firstrun/firstrun_app.py
fi
SESSIONSCRIPT
  chmod +x "$AIROOTFS/usr/local/bin/luminos-session"

  # ---- Launcher scripts ----
  for pair in \
    "luminos-bar:src/gui/bar/bar_app.py" \
    "luminos-dock:src/gui/dock/dock_app.py" \
    "luminos-store:src/gui/store/store_app.py" \
    "luminos-settings:src/gui/settings/settings_app.py" \
    "luminos-firstrun:src/gui/firstrun/firstrun_app.py" \
    "luminos-run-windows:src/zone2/wine_runner.py"; do
    local name="${pair%%:*}"
    local script="${pair#*:}"
    cat > "$AIROOTFS/usr/local/bin/$name" << LAUNCHER
#!/bin/bash
exec python3 /opt/luminos/src/$script "\$@"
LAUNCHER
    chmod +x "$AIROOTFS/usr/local/bin/$name"
  done

  # ---- Copy Hyprland config ----
  mkdir -p "$AIROOTFS/etc/skel/.config/hypr"
  cp -r "$(pwd)/config/hypr/"* "$AIROOTFS/etc/skel/.config/hypr/" 2>/dev/null || true

  # ---- Copy desktop file for .exe handler ----
  mkdir -p "$AIROOTFS/usr/share/applications"
  cp "$(pwd)/config/luminos-windows.desktop" "$AIROOTFS/usr/share/applications/" 2>/dev/null || true

  # ---- Lock GPU to hybrid via supergfxctl on first boot ----
  cat > "$AIROOTFS/usr/local/bin/luminos-gpu-init" << 'GPUINIT'
#!/bin/bash
# Set GPU to Hybrid mode — run once at install, never changed
supergfxctl --mode Hybrid 2>/dev/null || true
GPUINIT
  chmod +x "$AIROOTFS/usr/local/bin/luminos-gpu-init"

  mkdir -p "$AIROOTFS/etc/systemd/system"
  cat > "$AIROOTFS/etc/systemd/system/luminos-gpu-init.service" << 'GPUSERVICE'
[Unit]
Description=Luminos GPU Hybrid Mode Init
After=supergfxd.service
Requires=supergfxd.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/luminos-gpu-init
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
GPUSERVICE
  ln -sf /etc/systemd/system/luminos-gpu-init.service "$WANTS/"

  echo "Stage 2 complete" | tee -a "$LOG"
}

# ---------------------------------------------------------------------------
# Stage 3: Build ISO with mkarchiso
# ---------------------------------------------------------------------------
stage3_build() {
  echo "--- Stage 3: Build ISO ---" | tee -a "$LOG"
  mkdir -p "$WORK_DIR" "$OUTPUT_DIR"

  sudo mkarchiso -v \
    -w "$WORK_DIR" \
    -o "$OUTPUT_DIR" \
    "$PROFILE_DIR" \
    2>&1 | tee -a "$LOG"

  echo "Stage 3 complete" | tee -a "$LOG"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
mkdir -p "$BUILD_DIR"

check_deps
stage1_profile
stage2_customize
stage3_build

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ISO_FILE=$(ls -t "$OUTPUT_DIR"/*.iso 2>/dev/null | head -1)

echo ""
echo "=== BUILD COMPLETE ==="
if [ -n "$ISO_FILE" ]; then
  ISO_SIZE=$(du -sh "$ISO_FILE" | cut -f1)
  echo "ISO: $ISO_FILE"
  echo "Size: $ISO_SIZE"
fi
echo "Time: $((ELAPSED/60))m $((ELAPSED%60))s"
echo "Log: $LOG"
