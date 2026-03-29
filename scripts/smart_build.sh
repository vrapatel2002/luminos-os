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
OUTPUT_ISO="$BUILD_DIR/luminos-os-v1.1.0.iso"
LOG="$BUILD_DIR/build.log"
START_TIME=$(date +%s)

# Flag files inside chroot (survive across runs)
FLAG_BOOTSTRAP="$CHROOT_DIR/.stage1_done"
FLAG_PREPARE="$CHROOT_DIR/.stage2_done"
FLAG_STRIP="$CHROOT_DIR/.strip_done"
FLAG_INSTALL="$CHROOT_DIR/.luminos_installed"
FLAG_CONFIGURE="$CHROOT_DIR/.stage5_done"
FLAG_CLEANUP="$CHROOT_DIR/.stage6_done"
FLAG_HYPRLAND="$CHROOT_DIR/.hyprland_done"

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

  # ==================================================================
  # BUG-029: macOS Sequoia visual styling
  # ==================================================================

  # ---- Install Inter font ----
  chroot "$CHROOT_DIR" bash << 'FONTS'
apt-get install -y fonts-inter 2>/dev/null || \
(mkdir -p /usr/share/fonts/inter && \
 wget -q "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip" \
   -O /tmp/inter.zip && \
 unzip -q /tmp/inter.zip -d /tmp/inter && \
 find /tmp/inter -name "*.ttf" -exec cp {} /usr/share/fonts/inter/ \; && \
 rm -rf /tmp/inter /tmp/inter.zip && \
 fc-cache -f)
FONTS

  # ---- Install Pillow and generate Sequoia-style wallpaper ----
  chroot "$CHROOT_DIR" pip3 install Pillow \
    --break-system-packages -q 2>/dev/null || true
  
  mkdir -p "$CHROOT_DIR/usr/share/backgrounds"
  chroot "$CHROOT_DIR" python3 << 'WALLPAPER'
try:
  from PIL import Image
  import math

  w, h = 2560, 1600
  img = Image.new("RGB", (w, h))
  pixels = []

  for y in range(h):
    for x in range(w):
      # Base dark background
      nx = x / w
      ny = y / h

      # Deep blue-purple center (top left)
      d1 = math.sqrt((nx-0.2)**2 + (ny-0.2)**2)
      # Teal accent (bottom right)
      d2 = math.sqrt((nx-0.85)**2 + (ny-0.85)**2)
      # Purple (top right)
      d3 = math.sqrt((nx-0.9)**2 + (ny-0.1)**2)

      # Blend colors
      blue = max(0, min(255,
        int(20 + 60 * max(0, 1-d1*2.5))))
      purple = max(0, min(255,
        int(15 + 40 * max(0, 1-d3*2.5))))
      teal = max(0, min(255,
        int(30 * max(0, 1-d2*2))))

      r = max(8, min(40, 8 + purple//2))
      g = max(8, min(35, 8 + teal//2))
      b = max(20, min(80, 20 + blue + teal//3))

      pixels.append((r, g, b))

  img.putdata(pixels)
  img.save("/usr/share/backgrounds/luminos-default.png")
  print("Wallpaper created successfully")
except Exception as e:
  print(f"PIL failed: {e} — using fallback")
  # Fallback: solid dark color
  import subprocess
  subprocess.run([
    "convert", "-size", "2560x1600",
    "gradient:#0d0d1a-#0a1628",
    "/usr/share/backgrounds/luminos-default.png"
  ], capture_output=True)
WALLPAPER

  # ---- Waybar config — macOS menu bar style ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/waybar"
  cat > "$CHROOT_DIR/home/luminos/.config/waybar/config" << 'WAYBAR'
{
  "layer": "top",
  "position": "top",
  "height": 32,
  "spacing": 0,
  "margin-top": 0,
  "margin-left": 0,
  "margin-right": 0,
  "exclusive": true,
  "passthrough": false,
  "modules-left": [
    "custom/logo",
    "sway/workspaces",
    "sway/mode"
  ],
  "modules-center": ["clock"],
  "modules-right": [
    "custom/luminos-ai",
    "temperature",
    "cpu",
    "memory",
    "battery",
    "network",
    "pulseaudio",
    "tray"
  ],
  "custom/logo": {
    "format": "  Luminos",
    "tooltip": false,
    "on-click": "wofi --show drun"
  },
  "custom/luminos-ai": {
    "exec": "python3 /opt/luminos/src/gui/waybar/luminos_status.py",
    "interval": 5,
    "return-type": "json",
    "format": "{}",
    "tooltip": true,
    "on-click": "python3 /opt/luminos/src/gui/settings/settings_app.py"
  },
  "sway/workspaces": {
    "disable-scroll": true,
    "all-outputs": true,
    "format": "{name}"
  },
  "clock": {
    "format": "{:%H:%M}",
    "format-alt": "{:%A, %B %d %Y  %H:%M}",
    "tooltip-format": "<big>{:%Y %B}</big>\n<tt>{calendar}</tt>"
  },
  "cpu": {
    "format": " {usage}%",
    "interval": 5,
    "tooltip": false
  },
  "memory": {
    "format": " {percentage}%",
    "interval": 10
  },
  "temperature": {
    "format": " {temperatureC}°C",
    "critical-threshold": 85,
    "format-critical": " {temperatureC}°C",
    "interval": 5
  },
  "battery": {
    "format": "{icon} {capacity}%",
    "format-charging": " {capacity}%",
    "format-plugged": " {capacity}%",
    "format-icons": ["", "", "", "", ""],
    "states": {"warning": 30, "critical": 15}
  },
  "network": {
    "format-wifi": " {signalStrength}%",
    "format-ethernet": " {ifname}",
    "format-disconnected": " offline",
    "tooltip-format": "{essid} ({signalStrength}%)"
  },
  "pulseaudio": {
    "format": "{icon} {volume}%",
    "format-muted": " muted",
    "format-icons": {"default": ["", "", ""]},
    "on-click": "pactl set-sink-mute @DEFAULT_SINK@ toggle"
  },
  "tray": {"spacing": 8}
}
WAYBAR

  cat > "$CHROOT_DIR/home/luminos/.config/waybar/style.css" << 'WAYBARCSS'
* {
  font-family: "Inter", "SF Pro Display", sans-serif;
  font-size: 13px;
  border: none;
  border-radius: 0;
  min-height: 0;
}

window#waybar {
  background: rgba(20, 20, 22, 0.92);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  color: #ffffff;
}

.modules-left, .modules-center, .modules-right {
  background: transparent;
}

#workspaces button {
  padding: 0 10px;
  color: rgba(255,255,255,0.6);
  background: transparent;
  border-radius: 6px;
  margin: 4px 2px;
}

#workspaces button.focused {
  color: #ffffff;
  background: rgba(255,255,255,0.12);
}

#workspaces button:hover {
  background: rgba(255,255,255,0.08);
  color: #ffffff;
}

#clock {
  color: #ffffff;
  font-weight: 500;
  padding: 0 12px;
}

#cpu, #memory, #temperature,
#battery, #network, #pulseaudio, #tray {
  padding: 0 10px;
  color: rgba(255,255,255,0.8);
}

#battery.warning { color: #ff9f0a; }
#battery.critical { color: #ff453a; }
#temperature.critical { color: #ff453a; }

tooltip {
  background: rgba(28,28,30,0.95);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: #ffffff;
}
WAYBARCSS

  # ---- Wofi config — Spotlight launcher ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/wofi"
  cat > "$CHROOT_DIR/home/luminos/.config/wofi/config" << 'WOFICONF'
width=580
height=420
location=center
show=drun
prompt=Search apps and commands...
filter_rate=100
allow_markup=true
no_actions=true
halign=fill
orientation=vertical
content_halign=fill
insensitive=true
allow_images=true
image_size=36
term=foot
hide_scroll=true
WOFICONF

  cat > "$CHROOT_DIR/home/luminos/.config/wofi/style.css" << 'WOFICSS'
* {
  font-family: "Inter", sans-serif;
}

window {
  background-color: rgba(28, 28, 30, 0.94);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
}

#input {
  background-color: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  color: rgba(255,255,255,0.9);
  padding: 11px 16px;
  margin: 14px 14px 8px 14px;
  font-size: 16px;
  caret-color: #0a84ff;
}

#input:focus {
  border-color: rgba(10,132,255,0.6);
  background-color: rgba(255,255,255,0.09);
  outline: none;
}

#scroll {
  margin: 4px 8px 10px 8px;
}

#entry {
  padding: 8px 10px;
  border-radius: 8px;
  color: rgba(255,255,255,0.82);
  margin: 1px 0;
}

#entry:selected {
  background-color: rgba(10,132,255,0.28);
  color: rgba(255,255,255,0.96);
}

#entry:hover {
  background-color: rgba(255,255,255,0.07);
}

#img {
  margin-right: 8px;
}

#text {
  color: rgba(255,255,255,0.88);
  font-size: 14px;
}
WOFICSS

  # ---- Foot Terminal config — macOS dark colors ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/foot"
  cat > "$CHROOT_DIR/home/luminos/.config/foot/foot.ini" << 'FOOTINI'
[main]
font=Inter Mono:size=13
font-bold=Inter Mono:size=13:weight=Bold
pad=14x10
word-delimiters=,│`|:"'()[]{}<>
selection-target=primary

[scrollback]
lines=5000

[cursor]
style=beam
blink=yes

[colors]
alpha=0.94
background=1c1c1e
foreground=dcdcdc

regular0=3a3a3c
regular1=ff453a
regular2=32d74b
regular3=ffd60a
regular4=0a84ff
regular5=bf5af2
regular6=5ac8fa
regular7=dcdcdc

bright0=636366
bright1=ff6961
bright2=30db5b
bright3=ffd426
bright4=409cff
bright5=da8fff
bright6=70d7ff
bright7=f2f2f7

[key-bindings]
clipboard-copy=Control+c
clipboard-paste=Control+v
search-start=Control+r
FOOTINI

  # ---- GTK3 settings ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/gtk-3.0"
  cat > "$CHROOT_DIR/home/luminos/.config/gtk-3.0/settings.ini" << 'GTK3'
[Settings]
gtk-theme-name=Adwaita-dark
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 11
gtk-cursor-theme-name=Adwaita
gtk-cursor-theme-size=24
gtk-application-prefer-dark-theme=1
gtk-decoration-layout=close,minimize,maximize:
GTK3

  # ---- GTK4 settings ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/gtk-4.0"
  cat > "$CHROOT_DIR/home/luminos/.config/gtk-4.0/settings.ini" << 'GTK4'
[Settings]
gtk-theme-name=Adwaita-dark
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 11
gtk-cursor-theme-name=Adwaita
gtk-cursor-theme-size=24
gtk-application-prefer-dark-theme=1
gtk-decoration-layout=close,minimize,maximize:
GTK4

  # ---- Wayland environment variables ----
  cat >> "$CHROOT_DIR/home/luminos/.bash_profile" << 'ENV'
export GTK_THEME=Adwaita:dark
export XCURSOR_THEME=Adwaita
export XCURSOR_SIZE=24
export QT_QPA_PLATFORMTHEME=qt5ct
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export MOZ_ENABLE_WAYLAND=1
export ELECTRON_OZONE_PLATFORM_HINT=wayland
ENV

  # ---- Fix entire luminos home directory ownership ----
  chroot "$CHROOT_DIR" chown -R luminos:luminos /home/luminos/

  # ---- Full Sway config — macOS Sequoia style (BUG-028 + BUG-029) ----
  mkdir -p "$CHROOT_DIR/etc/sway"
  cat > "$CHROOT_DIR/etc/sway/config" << 'SWAYCONFIG'
# Luminos OS — macOS Sequoia Style
set $mod Mod4
set $term foot
set $menu wofi --show drun

# Font
font pango:Inter 11

# Wallpaper
output * bg /usr/share/backgrounds/luminos-default.png fill

# Window appearance
default_border pixel 1
default_floating_border pixel 1
gaps inner 8
gaps outer 4
smart_gaps on
smart_borders on

# Colors — macOS dark style
# class                 border              bg                  text                indicator           child_border
client.focused          #0a84ff             #1c1c1e             #ffffff             #0a84ff             #0a84ff
client.unfocused        rgba(255,255,255,0.08) #1c1c1e          rgba(255,255,255,0.6) #1c1c1e           rgba(255,255,255,0.08)
client.focused_inactive rgba(255,255,255,0.05) #1c1c1e          rgba(255,255,255,0.4) #1c1c1e           rgba(255,255,255,0.05)
client.urgent           #ff453a             #1c1c1e             #ffffff             #ff453a             #ff453a

# Input
input "type:keyboard" {
  xkb_layout us
  repeat_delay 300
  repeat_rate 50
}

input "type:touchpad" {
  tap enabled
  natural_scroll enabled
  dwt enabled
  scroll_factor 0.8
}

# Key bindings
bindsym $mod+Return exec $term
bindsym $mod+Space exec $menu
bindsym $mod+q kill
bindsym $mod+Shift+r reload
bindsym $mod+Shift+e exit

# Focus
bindsym $mod+Left focus left
bindsym $mod+Right focus right
bindsym $mod+Up focus up
bindsym $mod+Down focus down

# Move
bindsym $mod+Shift+Left move left
bindsym $mod+Shift+Right move right
bindsym $mod+Shift+Up move up
bindsym $mod+Shift+Down move down

# Workspaces
bindsym $mod+1 workspace number 1
bindsym $mod+2 workspace number 2
bindsym $mod+3 workspace number 3
bindsym $mod+4 workspace number 4
bindsym $mod+5 workspace number 5

bindsym $mod+Shift+1 move container to workspace number 1
bindsym $mod+Shift+2 move container to workspace number 2
bindsym $mod+Shift+3 move container to workspace number 3

# Layout
bindsym $mod+f fullscreen toggle
bindsym $mod+Shift+space floating toggle

# Volume
bindsym XF86AudioRaiseVolume exec pactl set-sink-volume @DEFAULT_SINK@ +5%
bindsym XF86AudioLowerVolume exec pactl set-sink-volume @DEFAULT_SINK@ -5%
bindsym XF86AudioMute exec pactl set-sink-mute @DEFAULT_SINK@ toggle

# Brightness
bindsym XF86MonBrightnessUp exec bash -c \
  'echo $(($(cat /sys/class/backlight/amdgpu_bl1/brightness)+1000)) | \
  sudo tee /sys/class/backlight/amdgpu_bl1/brightness'
bindsym XF86MonBrightnessDown exec bash -c \
  'echo $(($(cat /sys/class/backlight/amdgpu_bl1/brightness)-1000)) | \
  sudo tee /sys/class/backlight/amdgpu_bl1/brightness'

# Auto-start
exec swaylock -f -c 1c1c1e --indicator-idle-visible
exec python3 /opt/luminos/src/daemon/main.py

# Status bar
bar {
  swaybar_command waybar
}
SWAYCONFIG

  # ==================================================================
  # BUG-030: macOS UX features — animations, switcher, terminal, shell
  # ==================================================================

  # ---- Install swayfx (animated sway fork) ----
  chroot "$CHROOT_DIR" bash << 'FX'
apt-get install -y swayfx 2>/dev/null || true
# Fallback: use regular sway (already installed)
FX

  # ---- Install swayr (Alt+Tab window switcher) ----
  chroot "$CHROOT_DIR" bash << 'SWAYR'
apt-get install -y swayr 2>/dev/null || \
cargo install swayr 2>/dev/null || true
SWAYR

  # ---- Install screenshot tools ----
  chroot "$CHROOT_DIR" apt-get install -y \
    grim slurp 2>/dev/null || true

  # ---- Append swayfx animations + extra bindings to sway config ----
  cat >> "$CHROOT_DIR/etc/sway/config" << 'EXTRA'

# Alt+Tab window switcher using swayr
bindsym $mod+Tab exec swayr switch-window

# Super key shows wofi (like macOS Spotlight)
bindsym $mod+Space exec wofi --show drun

# Screenshot
bindsym Print exec grim ~/screenshot.png
bindsym $mod+Print exec grim -g "$(slurp)" ~/screenshot.png

# Auto-start Luminos GUI components
exec_always python3 /opt/luminos/src/gui/bar/bar_app.py
exec_always python3 /opt/luminos/src/gui/dock/dock_app.py
EXTRA

  # ==================================================================
  # BUG-032: Hyprland compositor (primary, Sway as fallback)
  # ==================================================================

  # ---- Install Hyprland ----
  chroot "$CHROOT_DIR" bash << 'HYPR'
export DEBIAN_FRONTEND=noninteractive

# Try official Ubuntu package first
apt-get install -y hyprland hyprpaper \
  hyprlock hypridle \
  xdg-desktop-portal-hyprland \
  xdg-desktop-portal-gtk \
  qt5-wayland qt6-wayland \
  libqt5waylandclient5 2>/dev/null || true

# Check if installed
if command -v Hyprland >/dev/null 2>&1; then
  echo "Hyprland installed successfully"
else
  echo "Hyprland not in apt — keeping Sway as fallback"
fi
HYPR

  # ---- Hyprland config ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/hypr"

  cat > "$CHROOT_DIR/home/luminos/.config/hypr/hyprland.conf" << 'HYPRCONF'
monitor=,preferred,auto,1

$terminal = foot
$menu = wofi --show drun

exec-once = waybar
exec-once = hyprpaper
exec-once = hypridle
exec-once = python3 /opt/luminos/src/daemon/main.py
exec-once = python3 /opt/luminos/src/gui/bar/bar_app.py
exec-once = python3 /opt/luminos/src/gui/dock/dock_app.py

general {
  gaps_in = 8
  gaps_out = 12
  border_size = 1
  col.active_border = rgba(0a84ffee) rgba(5e9effee) 45deg
  col.inactive_border = rgba(ffffff15)
  layout = dwindle
}

decoration {
  rounding = 12
  blur {
    enabled = true
    size = 8
    passes = 3
    new_optimizations = true
    noise = 0.02
    contrast = 1.1
    brightness = 1.0
    vibrancy = 0.2
  }
  drop_shadow = true
  shadow_range = 20
  shadow_render_power = 3
  col.shadow = rgba(00000055)
  active_opacity = 1.0
  inactive_opacity = 0.95
  dim_inactive = true
  dim_strength = 0.08
}

animations {
  enabled = true
  bezier = overshot, 0.05, 0.9, 0.1, 1.05
  bezier = smoothIn, 0.25, 1, 0.5, 1
  bezier = smoothOut, 0.36, 0, 0.66, -0.56
  bezier = snappy, 0.5, 0, 0.5, 1
  animation = windows, 1, 4, overshot, slide
  animation = windowsOut, 1, 3, smoothOut, slide
  animation = windowsMove, 1, 3, snappy
  animation = fade, 1, 4, smoothIn
  animation = fadeOut, 1, 3, smoothOut
  animation = workspaces, 1, 4, overshot, slidevert
}

input {
  kb_layout = us
  follow_mouse = 1
  sensitivity = 0
  touchpad {
    natural_scroll = true
    tap-to-click = true
    disable_while_typing = true
    scroll_factor = 0.8
  }
}

gestures {
  workspace_swipe = true
  workspace_swipe_fingers = 3
}

dwindle {
  pseudotile = true
  preserve_split = true
}

misc {
  force_default_wallpaper = 0
  disable_hyprland_logo = true
  disable_splash_rendering = true
  animate_manual_resizes = true
}

$mainMod = SUPER

bind = $mainMod, Return, exec, $terminal
bind = $mainMod, Space, exec, $menu
bind = $mainMod, Q, killactive
bind = $mainMod, F, fullscreen, 0
bind = $mainMod SHIFT, F, togglefloating
bind = $mainMod SHIFT, R, exec, hyprctl reload
bind = $mainMod SHIFT, E, exit

bind = , Print, exec, grim ~/screenshot.png
bind = $mainMod, Print, exec, grim -g "$(slurp)" ~/screenshot.png

bind = , XF86AudioRaiseVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ +5%
bind = , XF86AudioLowerVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ -5%
bind = , XF86AudioMute, exec, pactl set-sink-mute @DEFAULT_SINK@ toggle

bind = , XF86MonBrightnessUp, exec, bash -c 'b=$(cat /sys/class/backlight/amdgpu_bl1/brightness); echo $((b+1000)) | sudo tee /sys/class/backlight/amdgpu_bl1/brightness'
bind = , XF86MonBrightnessDown, exec, bash -c 'b=$(cat /sys/class/backlight/amdgpu_bl1/brightness); echo $((b>1000?b-1000:100)) | sudo tee /sys/class/backlight/amdgpu_bl1/brightness'

bind = $mainMod, left, movefocus, l
bind = $mainMod, right, movefocus, r
bind = $mainMod, up, movefocus, u
bind = $mainMod, down, movefocus, d

bind = $mainMod SHIFT, left, movewindow, l
bind = $mainMod SHIFT, right, movewindow, r
bind = $mainMod SHIFT, up, movewindow, u
bind = $mainMod SHIFT, down, movewindow, d

bind = ALT, Tab, cyclenext
bind = ALT SHIFT, Tab, cyclenext, prev

bind = $mainMod, 1, workspace, 1
bind = $mainMod, 2, workspace, 2
bind = $mainMod, 3, workspace, 3
bind = $mainMod, 4, workspace, 4
bind = $mainMod, 5, workspace, 5

bind = $mainMod SHIFT, 1, movetoworkspace, 1
bind = $mainMod SHIFT, 2, movetoworkspace, 2
bind = $mainMod SHIFT, 3, movetoworkspace, 3

bindm = $mainMod, mouse:272, movewindow
bindm = $mainMod, mouse:273, resizewindow

windowrulev2 = opacity 0.96 0.88, class:^(foot)$
windowrulev2 = opacity 0.98 0.90, class:^(firefox)$
HYPRCONF

  # ---- Hyprpaper config ----
  cat > "$CHROOT_DIR/home/luminos/.config/hypr/hyprpaper.conf" << 'HYPRPAPER'
preload = /usr/share/backgrounds/luminos-default.png
wallpaper = ,/usr/share/backgrounds/luminos-default.png
splash = false
HYPRPAPER

  # ---- Hyprlock config ----
  cat > "$CHROOT_DIR/home/luminos/.config/hypr/hyprlock.conf" << 'HYPRLOCK'
background {
  monitor =
  path = /usr/share/backgrounds/luminos-default.png
  blur_passes = 4
  blur_size = 10
  brightness = 0.7
  vibrancy = 0.2
}

label {
  monitor =
  text = cmd[update:1000] echo "$(date +"%H:%M")"
  color = rgba(255, 255, 255, 0.92)
  font_size = 80
  font_family = Inter
  position = 0, 120
  halign = center
  valign = center
}

label {
  monitor =
  text = cmd[update:60000] echo "$(date +"%A, %B %d")"
  color = rgba(255, 255, 255, 0.55)
  font_size = 18
  font_family = Inter
  position = 0, 40
  halign = center
  valign = center
}

input-field {
  monitor =
  size = 280, 48
  outline_thickness = 2
  dots_size = 0.25
  dots_center = true
  outer_color = rgba(0a84ffcc)
  inner_color = rgba(28, 28, 30, 0.85)
  font_color = rgb(255, 255, 255)
  fade_on_empty = true
  placeholder_text = Enter password
  hide_input = false
  position = 0, -60
  halign = center
  valign = center
  check_color = rgba(50, 215, 75, 0.9)
  fail_color = rgba(255, 69, 58, 0.9)
  fail_text = Incorrect password
}
HYPRLOCK

  # ---- Hypridle config ----
  cat > "$CHROOT_DIR/home/luminos/.config/hypr/hypridle.conf" << 'HYPRIDLE'
general {
  lock_cmd = pidof hyprlock || hyprlock
  before_sleep_cmd = loginctl lock-session
  after_sleep_cmd = hyprctl dispatch dpms on
}

listener {
  timeout = 300
  on-timeout = loginctl lock-session
}

listener {
  timeout = 600
  on-timeout = hyprctl dispatch dpms off
  on-resume = hyprctl dispatch dpms on
}
HYPRIDLE

  # ---- Foot terminal — macOS dark style ----
  mkdir -p "$CHROOT_DIR/home/luminos/.config/foot"
  cat > "$CHROOT_DIR/home/luminos/.config/foot/foot.ini" << 'FOOT'
[main]
font=Inter Mono:size=13
pad=12x12

[colors]
background=1c1c1e
foreground=e0e0e0
alpha=0.95

regular0=3a3a3c
regular1=ff453a
regular2=32d74b
regular3=ff9f0a
regular4=0a84ff
regular5=bf5af2
regular6=5ac8fa
regular7=e0e0e0

bright0=636366
bright1=ff6961
bright2=5cdb76
bright3=ffb340
bright4=409cff
bright5=da8fff
bright6=70d7ff
bright7=ffffff
FOOT

  # ---- Shell config (.bashrc) ----
  cat > "$CHROOT_DIR/home/luminos/.bashrc" << 'BASHRC'
# Luminos OS shell config
export PS1='\[\033[38;5;75m\]luminos\[\033[0m\] \[\033[38;5;245m\]\W\[\033[0m\] \[\033[38;5;75m\]❯\[\033[0m\] '

alias ls='ls --color=auto'
alias ll='ls -la'
alias grep='grep --color=auto'

# Luminos shortcuts
alias luminos-status='python3 /opt/luminos/src/daemon/main.py --status'

export PATH="/opt/luminos/src:$PATH"
BASHRC

  # ---- Set ownership on ALL user files (BUG-029 + BUG-030 + BUG-032) ----
  chroot "$CHROOT_DIR" chown -R luminos:luminos /home/luminos/

  # ---- Auto-login on tty1 (BUG-028) ----
  mkdir -p "$CHROOT_DIR/etc/systemd/system/getty@tty1.service.d/"
  cat > "$CHROOT_DIR/etc/systemd/system/getty@tty1.service.d/autologin.conf" << 'AUTOEOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin luminos --noclear %I $TERM
AUTOEOF

  # ---- .bash_profile auto-starts Hyprland/Sway on tty1 (BUG-028 + BUG-032) ----
  cat > "$CHROOT_DIR/home/luminos/.bash_profile" << 'BASHEOF'
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
  if command -v Hyprland >/dev/null 2>&1; then
    exec Hyprland
  else
    exec sway
  fi
fi
BASHEOF
  chown 1000:1000 "$CHROOT_DIR/home/luminos/.bash_profile"

  # ---- luminos-session script (BUG-028) ----
  cat > "$CHROOT_DIR/usr/local/bin/luminos-session" << 'SESSIONEOF'
#!/bin/bash
# Start Luminos AI daemon
python3 /opt/luminos/src/daemon/main.py &

# Wait for daemon socket
sleep 2

# Check first run
if [ ! -f ~/.config/luminos/.setup_complete ]; then
  python3 /opt/luminos/src/gui/firstrun/firstrun_app.py
fi
SESSIONEOF
  chmod +x "$CHROOT_DIR/usr/local/bin/luminos-session"

  # Install kernel (BUG-017)
  chroot "$CHROOT_DIR" apt-get install -y \
    linux-image-generic \
    initramfs-tools \
    os-prober || true \
    2>&1 | tee -a "$LOG"

  # Step 1: Install live-boot packages FIRST (BUG-023, BUG-022, BUG-021)
  # These MUST be installed before initrd regeneration so hooks are present
  chroot "$CHROOT_DIR" apt-get install -y \
    live-boot \
    live-boot-initramfs-tools \
    live-config \
    live-config-systemd \
    casper \
    2>&1 | tee -a "$LOG"

  # Step 2: Create initramfs hook for live filesystem (BUG-023)
  mkdir -p "$CHROOT_DIR/etc/initramfs-tools/hooks"
  cat > "$CHROOT_DIR/etc/initramfs-tools/hooks/live_hook" << 'HOOK'
#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case $1 in prereqs) prereqs; exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
copy_exec /bin/mount /bin
copy_exec /bin/umount /bin
HOOK
  chmod +x "$CHROOT_DIR/etc/initramfs-tools/hooks/live_hook"

  # Step 3: Force regenerate initrd AFTER live-boot install (BUG-023)
  chroot "$CHROOT_DIR" \
    env -i HOME=/root TERM=linux PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    update-initramfs -u -k all -v \
    2>&1 | tee -a "$LOG"

  # Step 4: Verify initrd has live modules (BUG-023)
  echo "Verifying initrd contains live-boot hooks..."
  LIVE_CHECK=$(chroot "$CHROOT_DIR" sh -c \
    "lsinitramfs /boot/initrd.img-* | grep live | head -5" 2>/dev/null || true)
  if [ -z "$LIVE_CHECK" ]; then
    echo "ERROR: live-boot hooks NOT found in initrd — BUG-023 not fixed"
    echo "initrd was regenerated but contains no live/* files"
    exit 1
  fi
  echo "OK: live-boot hooks found in initrd:"
  echo "$LIVE_CHECK"

  # Step 5: Copy fresh initrd to ISO casper folder (BUG-023)
  mkdir -p "$ISO_DIR/casper"
  NEW_INITRD=$(find "$CHROOT_DIR/boot" -name "initrd*" | head -1)
  cp "$NEW_INITRD" "$ISO_DIR/casper/initrd"
  chmod 644 "$ISO_DIR/casper/initrd"
  echo "New initrd copied: $(ls -lh "$ISO_DIR/casper/initrd")"

  # Create required root directories for live boot (BUG-022)
  mkdir -p "$CHROOT_DIR/root/dev"
  mkdir -p "$CHROOT_DIR/root/proc"
  mkdir -p "$CHROOT_DIR/root/sys"
  mkdir -p "$CHROOT_DIR/root/run"
  mkdir -p "$CHROOT_DIR/root/tmp"
  mkdir -p "$CHROOT_DIR/cdrom"

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
# Stage Hyprland: Build Hyprland from source (BUG-035, BUG-036)
# ============================================================================
stage_hyprland() {
  if [ -f "$FLAG_HYPRLAND" ]; then
    echo "--- Hyprland: SKIP (already built) ---"
    return
  fi
  echo "--- Building Hyprland from source (comprehensive) ---"
  ensure_chroot_ready

  # ---- Main build: all deps in correct order ----
  chroot "$CHROOT_DIR" bash << 'BUILDALL'
export DEBIAN_FRONTEND=noninteractive
export PKG_CONFIG_PATH=\
/usr/local/lib/pkgconfig:\
/usr/local/lib/x86_64-linux-gnu/pkgconfig:\
/usr/lib/pkgconfig:\
/usr/lib/x86_64-linux-gnu/pkgconfig:\
/usr/share/pkgconfig

# Helper function to build a hyprwm library
build_hypr_lib() {
  local name=$1
  local repo=$2
  local verify=$3
  echo "=== Building $name ==="
  cd /tmp && rm -rf $name
  git clone --depth 1 --recursive \
    https://github.com/hyprwm/$repo.git $name \
    2>&1 | tail -2
  [ ! -d /tmp/$name ] && \
    echo "FAIL clone $name" && return 1
  cd /tmp/$name
  cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_PREFIX_PATH=/usr \
    2>&1 | grep -iE "error|not found" | head -10
  cmake --build build -j$(nproc) 2>&1 | tail -3
  cmake --install build 2>&1 | tail -3
  ldconfig 2>/dev/null || true
  export PKG_CONFIG_PATH=\
/usr/local/lib/pkgconfig:\
/usr/local/lib/x86_64-linux-gnu/pkgconfig:\
/usr/lib/pkgconfig:\
/usr/lib/x86_64-linux-gnu/pkgconfig:\
/usr/share/pkgconfig
  [ -n "$verify" ] && \
    pkg-config --modversion $verify 2>/dev/null \
    && echo "OK: $verify" \
    || echo "WARN: $verify not found in pkg-config"
  echo "=== done: $name ==="
}

echo "========================================"
echo "  HYPRLAND COMPREHENSIVE BUILD"
echo "  Build order: 10 steps"
echo "========================================"

# ---- Install all build deps upfront ----
echo "[deps] Installing core build tools..."
apt-get install -y \
  meson cmake ninja-build \
  pkg-config git curl \
  re2c glslang-tools \
  spirv-tools 2>&1 || true

echo "[deps] Installing Wayland core..."
apt-get install -y \
  libwayland-dev \
  libwayland-egl-backend-dev \
  wayland-protocols \
  libxkbcommon-dev \
  libxkbcommon-x11-dev \
  2>&1 || true

echo "[deps] Installing graphics libs..."
apt-get install -y \
  libpixman-1-dev \
  libdrm-dev \
  libgbm-dev \
  libegl-dev \
  libgles2-mesa-dev \
  libvulkan-dev \
  libglslang-dev \
  2>&1 || true

echo "[deps] Installing input/seat..."
apt-get install -y \
  libseat-dev \
  libinput-dev \
  libudev-dev \
  libsystemd-dev \
  libdisplay-info-dev \
  2>&1 || true

echo "[deps] Installing XCB for Xwayland..."
apt-get install -y \
  libxcb1-dev \
  libxcb-render-util0-dev \
  libxcb-icccm4-dev \
  libxcb-image0-dev \
  libxcb-keysyms1-dev \
  libxcb-randr0-dev \
  libxcb-xfixes0-dev \
  libxcb-composite0-dev \
  libxcb-ewmh-dev \
  libxcb-present-dev \
  libxcb-glx0-dev \
  libxwayland-dev \
  2>&1 || true

echo "[deps] Installing rendering/extra libs..."
apt-get install -y \
  libtomlplusplus-dev \
  libpango1.0-dev \
  libcairo2-dev \
  hwdata \
  libzip-dev \
  libliftoff-dev \
  libxxhash-dev \
  libudis86-dev \
  libfmt-dev \
  libspdlog-dev \
  libwebp-dev \
  librsvg2-dev \
  2>&1 || true

echo "[deps] Installing aquamarine/hyprcursor deps..."
apt-get install -y \
  libdisplay-info-dev \
  libseat-dev libinput-dev \
  libudev-dev libdrm-dev \
  libgbm-dev libegl-dev \
  libwayland-dev wayland-protocols \
  libxkbcommon-dev \
  libzip-dev libwebp-dev librsvg2-dev \
  2>/dev/null || true

echo "[deps] Installing hyprlock deps..."
apt-get install -y \
  libpam0g-dev libmagic-dev \
  2>/dev/null || true

# ---- Install CMake 3.30+ from Kitware ----
echo ""
echo "=== Installing CMake 3.30+ from Kitware ==="
apt-get install -y ca-certificates gpg wget 2>&1 || true
wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc \
  2>/dev/null | gpg --dearmor - \
  | tee /usr/share/keyrings/kitware-archive-keyring.gpg \
  >/dev/null
echo "deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] \
  https://apt.kitware.com/ubuntu/ noble main" \
  | tee /etc/apt/sources.list.d/kitware.list
apt-get update -qq 2>/dev/null
apt-get install -y cmake 2>/dev/null
echo "CMake version: $(cmake --version 2>&1 | head -1)"

# ================================================================
# Step 1: hyprwayland-scanner (code generator — no deps)
# ================================================================
build_hypr_lib \
  hyprwayland-scanner \
  hyprwayland-scanner \
  ""

# ================================================================
# Step 2: hyprutils (utility library)
# ================================================================
build_hypr_lib \
  hyprutils \
  hyprutils \
  "hyprutils"

# ================================================================
# Step 3: hyprlang (config parser — needs hyprutils)
# ================================================================
build_hypr_lib \
  hyprlang \
  hyprlang \
  "hyprlang"

# ================================================================
# Step 4: hyprcursor (cursor theme — needs hyprlang, hyprutils)
# ================================================================
apt-get install -y \
  libzip-dev libwebp-dev librsvg2-dev \
  libcairo2-dev libgdk-pixbuf-2.0-dev \
  2>/dev/null || true
build_hypr_lib \
  hyprcursor \
  hyprcursor \
  "hyprcursor"

# ================================================================
# Step 5: glslang (cmake config files)
# ================================================================
echo "=== Building glslang ==="
cd /tmp
rm -rf glslang
git clone --depth 1 \
  https://github.com/KhronosGroup/glslang.git 2>&1 | tail -2
cd /tmp/glslang
python3 update_glslang_sources.py 2>/dev/null || true
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -DBUILD_SHARED_LIBS=OFF \
  -DENABLE_GLSLANG_BINARIES=OFF \
  2>&1 | tail -3
cmake --build build -j$(nproc) 2>&1 | tail -3
cmake --install build 2>&1 | tail -3
ldconfig 2>/dev/null || true
export PKG_CONFIG_PATH=\
/usr/local/lib/pkgconfig:\
/usr/local/lib/x86_64-linux-gnu/pkgconfig:\
/usr/lib/pkgconfig:\
/usr/lib/x86_64-linux-gnu/pkgconfig:\
/usr/share/pkgconfig
ls /usr/lib/cmake/glslang/ 2>/dev/null \
  && echo "OK: glslang cmake files" \
  || echo "WARN: glslang cmake files not found"
echo "=== done: glslang ==="

# ================================================================
# Step 6: aquamarine (display backend — needs hyprutils, hyprwayland-scanner)
# ================================================================
build_hypr_lib \
  aquamarine \
  aquamarine \
  "aquamarine"

# Verify aquamarine before proceeding — it's critical
pkg-config --modversion aquamarine 2>/dev/null || {
  echo "FATAL: aquamarine still not found after build"
  echo "PKG_CONFIG_PATH=$PKG_CONFIG_PATH"
  find /usr -name "aquamarine.pc" 2>/dev/null
  exit 1
}

# ================================================================
# Step 7: Build Hyprland (main compositor)
# ================================================================
echo "=== Building Hyprland ==="
cd /tmp && rm -rf Hyprland
git clone --depth 1 --recursive \
  https://github.com/hyprwm/Hyprland.git \
  2>&1 | tail -2

cd /tmp/Hyprland
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_PREFIX_PATH=/usr \
  2>&1 | grep -iE "error|not found|missing" | head -20

if [ $? -ne 0 ]; then
  echo "FATAL: Hyprland cmake failed"
  exit 1
fi

echo "Hyprland cmake OK — compiling..."
cmake --build build -j$(nproc) 2>&1 | tail -10
cmake --install build 2>&1 | tail -5

ldconfig 2>/dev/null || true
export PKG_CONFIG_PATH=\
/usr/local/lib/pkgconfig:\
/usr/local/lib/x86_64-linux-gnu/pkgconfig:\
/usr/lib/pkgconfig:\
/usr/lib/x86_64-linux-gnu/pkgconfig:\
/usr/share/pkgconfig

if [ -x /usr/bin/Hyprland ] || command -v Hyprland >/dev/null 2>&1; then
  echo "SUCCESS: Hyprland installed"
  Hyprland --version 2>&1 || true
else
  echo "FAILED: Hyprland binary not found"
  echo "Sway will remain as fallback"
fi

# ================================================================
# Step 8: hyprpaper (wallpaper)
# ================================================================
build_hypr_lib hyprpaper hyprpaper ""

# ================================================================
# Step 9: hyprlock (lock screen)
# ================================================================
build_hypr_lib hyprlock hyprlock ""

# ================================================================
# Step 10: hypridle (idle daemon)
# ================================================================
build_hypr_lib hypridle hypridle ""

# ================================================================
# Final verification
# ================================================================
echo ""
echo "=== FINAL VERIFICATION ==="
which Hyprland && Hyprland --version \
  && echo "SUCCESS: Hyprland installed" \
  || echo "FAILED: Hyprland not found"

which hyprpaper && echo "OK: hyprpaper" \
  || echo "MISSING: hyprpaper"
which hyprlock && echo "OK: hyprlock" \
  || echo "MISSING: hyprlock"
which hypridle && echo "OK: hypridle" \
  || echo "MISSING: hypridle"

# Cleanup build dirs to save space
rm -rf /tmp/hyprwayland-scanner \
  /tmp/hyprutils /tmp/hyprlang \
  /tmp/hyprcursor /tmp/aquamarine \
  /tmp/Hyprland /tmp/hyprpaper \
  /tmp/hyprlock /tmp/hypridle \
  /tmp/glslang

echo "=== Hyprland ecosystem complete ==="
BUILDALL

  # Only mark done if Hyprland actually installed
  if sudo chroot "$CHROOT_DIR" \
    which Hyprland >/dev/null 2>&1; then
    echo "VERIFIED: Hyprland installed successfully"
    touch "$FLAG_HYPRLAND"
  else
    echo "FAILED: Hyprland not installed"
    echo "Sway will be used as fallback"
  fi
  echo "--- Hyprland stage complete ---"
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
# Stage 7: Build squashfs (BUG-027: preserve mount point directories)
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

  # ---- BUG-027: Create required mount point directories ----
  # casper's /init mounts these into the squashfs root.
  # They MUST exist as empty directories inside the squashfs.
  # Previous bug: mksquashfs -e excluded them entirely.
  for dir in dev proc sys run tmp; do
    mkdir -p "$CHROOT_DIR/$dir"
  done
  chmod 1777 "$CHROOT_DIR/tmp"
  mkdir -p "$CHROOT_DIR/root"
  chmod 700 "$CHROOT_DIR/root"
  # Ensure /etc/fstab exists (casper checks for it)
  touch "$CHROOT_DIR/etc/fstab" 2>/dev/null || true
  # Ensure /cdrom mount point exists for casper
  mkdir -p "$CHROOT_DIR/cdrom"

  mkdir -p "$ISO_DIR/casper"

  # ---- Build squashfs ----
  # IMPORTANT: Use wildcard exclusions (dir/*) NOT directory exclusions (dir)
  # so that the empty mount point directories are preserved in the squashfs.
  # casper needs /dev /proc /sys /run /tmp to exist as empty dirs.
  mksquashfs "$CHROOT_DIR" \
    "$ISO_DIR/casper/filesystem.squashfs" \
    -comp xz -b 1M -no-progress \
    -wildcards \
    -e "proc/*" \
    -e "sys/*" \
    -e "dev/*" \
    -e "run/*" \
    -e "tmp/*" \
    2>&1 | tee -a "$LOG"

  # Filesystem size for installer
  printf "$(du -sx --block-size=1 "$CHROOT_DIR" | cut -f1)" > \
    "$ISO_DIR/casper/filesystem.size"

  echo "Stage 7 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 8: Build bootable ISO (BUG-025, BUG-026: grub-mkrescue)
# ============================================================================
stage8_iso() {
  if [ -f "$OUTPUT_ISO" ]; then
    log_stage SKIP 8 "ISO already exists: $OUTPUT_ISO"
    return 0
  fi

  log_stage RUN 8 "build ISO"

  mkdir -p "$ISO_DIR/boot/grub"

  # ---- Find vmlinuz and initrd (BUG-017) ----
  VMLINUZ=$(find "$CHROOT_DIR/boot" -name "vmlinuz*" 2>/dev/null | head -1)
  INITRD=$(find "$CHROOT_DIR/boot" -name "initrd*" 2>/dev/null | head -1)

  if [ -z "$VMLINUZ" ]; then
    echo "ERROR: No kernel found in chroot/boot"
    echo "Run: reset_build.sh 5  (then rerun smart_build.sh)"
    exit 1
  fi

  mkdir -p "$ISO_DIR/casper"
  cp "$VMLINUZ" "$ISO_DIR/casper/vmlinuz"
  cp "$INITRD" "$ISO_DIR/casper/initrd"

  # ---- Main grub.cfg (lives on ISO at /boot/grub/grub.cfg) ----
  # grub-mkrescue picks this up automatically from the ISO directory.
  # Uses search --file to find the boot device at runtime (BUG-025).
  cat > "$ISO_DIR/boot/grub/grub.cfg" << 'GRUBEOF'
set default=0
set timeout=5

insmod all_video
insmod gfxterm
insmod png

# Find the device containing our kernel
search --no-floppy --set=root --file /casper/vmlinuz

menuentry "Luminos OS" {
  set gfxpayload=keep
  linux /casper/vmlinuz \
    boot=casper \
    live-media-path=/casper \
    quiet splash \
    fsck.mode=skip \
    noprompt \
    ---
  initrd /casper/initrd
}

menuentry "Luminos OS (Safe Graphics)" {
  set gfxpayload=keep
  linux /casper/vmlinuz \
    boot=casper \
    live-media-path=/casper \
    nomodeset \
    fsck.mode=skip \
    noprompt \
    ---
  initrd /casper/initrd
}

menuentry "Install Luminos to Disk" {
  set gfxpayload=keep
  linux /casper/vmlinuz \
    boot=casper \
    live-media-path=/casper \
    only-ubiquity \
    quiet splash \
    fsck.mode=skip \
    noprompt \
    ---
  initrd /casper/initrd
}
GRUBEOF

  # ---- Build ISO with grub-mkrescue (BUG-026) ----
  # grub-mkrescue handles everything automatically:
  #   - Resolves all GRUB modules (no manual search_file vs search_fs_file)
  #   - Creates BIOS boot image (i386-pc) with correct cdboot.img
  #   - Creates EFI boot image (x86_64-efi) with correct embedded config
  #   - Creates efiboot.img FAT image
  #   - Invokes xorriso with correct parameters
  #   - Reads boot/grub/grub.cfg from ISO_DIR automatically
  echo "Building ISO with grub-mkrescue..."
  grub-mkrescue \
    --modules="all_video boot cat chain configfile echo \
               fat iso9660 linux loadenv normal \
               part_gpt part_msdos reboot search \
               search_label search_fs_file search_fs_uuid \
               squash4 gfxterm png" \
    --output="$OUTPUT_ISO" \
    "$ISO_DIR" \
    -- \
    -volid "LUMINOS_OS" \
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
stage_hyprland     # build Hyprland from source (BUG-035)
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
