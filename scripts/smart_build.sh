#!/bin/bash
set -euo pipefail

# ============================================================================
# Luminos OS — Smart Resumable Build (Arch Linux / archiso)
# ============================================================================
# Tracks completed stages with flag files.
# Safe to rerun after any failure — resumes from where it left off.
# ============================================================================

BUILD_DIR="$(pwd)/build"
PROFILE_DIR="$BUILD_DIR/luminos-profile"
WORK_DIR="$BUILD_DIR/work"
OUTPUT_DIR="$BUILD_DIR/out"
LOG="$BUILD_DIR/build.log"
START_TIME=$(date +%s)

# Flag files (survive across runs)
FLAG_PROFILE="$BUILD_DIR/.stage1_profile_done"
FLAG_CUSTOMIZE="$BUILD_DIR/.stage2_customize_done"
FLAG_CONFIGS="$BUILD_DIR/.stage3_configs_done"
FLAG_ISO="$BUILD_DIR/.stage4_iso_done"

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

check_deps() {
  local deps=(archiso mtools dosfstools libisoburn squashfs-tools rsync)
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

# ============================================================================
# Stage 1: Create archiso profile with Luminos packages
# ============================================================================
stage1_profile() {
  if [ -f "$FLAG_PROFILE" ] && [ -d "$PROFILE_DIR" ]; then
    log_stage SKIP 1 "profile already created"
    return 0
  fi

  log_stage RUN 1 "create archiso profile"

  [ -d "$PROFILE_DIR" ] && rm -rf "$PROFILE_DIR"
  cp -r /usr/share/archiso/configs/releng/ "$PROFILE_DIR"

  # Append Luminos packages
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

  touch "$FLAG_PROFILE"
  echo "Stage 1 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 2: Customize airootfs (users, services, directories)
# ============================================================================
stage2_customize() {
  if [ -f "$FLAG_CUSTOMIZE" ]; then
    log_stage SKIP 2 "airootfs already customized"
    return 0
  fi

  log_stage RUN 2 "customize airootfs"
  local AIROOTFS="$PROFILE_DIR/airootfs"

  # ---- Hostname ----
  echo "luminos-os" > "$AIROOTFS/etc/hostname"

  # ---- Locale ----
  echo "en_US.UTF-8 UTF-8" > "$AIROOTFS/etc/locale.gen"
  echo "LANG=en_US.UTF-8" > "$AIROOTFS/etc/locale.conf"

  # ---- Timezone ----
  ln -sf /usr/share/zoneinfo/UTC "$AIROOTFS/etc/localtime"

  # ---- NVIDIA + Wayland env ----
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

  # ---- Create luminos user ----
  mkdir -p "$AIROOTFS/etc/sysusers.d"
  cat > "$AIROOTFS/etc/sysusers.d/luminos.conf" << 'SYSUSERS'
u luminos - "Luminos User" /home/luminos /bin/bash
m luminos wheel
m luminos video
m luminos audio
m luminos input
m luminos kvm
SYSUSERS

  # ---- Sudoers ----
  mkdir -p "$AIROOTFS/etc/sudoers.d"
  echo "%wheel ALL=(ALL:ALL) ALL" > "$AIROOTFS/etc/sudoers.d/wheel"
  chmod 440 "$AIROOTFS/etc/sudoers.d/wheel"

  # ---- Enable systemd services ----
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
command = "luminos-greeter"
user = "greeter"
GREETD

  touch "$FLAG_CUSTOMIZE"
  echo "Stage 2 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 3: Copy Luminos configs, source, launchers into airootfs
# ============================================================================
stage3_configs() {
  if [ -f "$FLAG_CONFIGS" ]; then
    log_stage SKIP 3 "configs already copied"
    return 0
  fi

  log_stage RUN 3 "copy Luminos configs and source"
  local AIROOTFS="$PROFILE_DIR/airootfs"
  local WANTS="$AIROOTFS/etc/systemd/system/multi-user.target.wants"

  # ---- Copy Luminos source ----
  mkdir -p "$AIROOTFS/opt/luminos"
  rsync -a --exclude=build --exclude=.git --exclude='__pycache__' \
    "$(pwd)/" "$AIROOTFS/opt/luminos/"

  # ---- systemd service ----
  cp "$(pwd)/systemd/luminos-ai.service" "$AIROOTFS/etc/systemd/system/"
  ln -sf /etc/systemd/system/luminos-ai.service "$WANTS/luminos-ai.service" 2>/dev/null || true

  # ---- Wayland session entry ----
  mkdir -p "$AIROOTFS/usr/share/wayland-sessions"
  cat > "$AIROOTFS/usr/share/wayland-sessions/luminos.desktop" << 'SESSION'
[Desktop Entry]
Name=Luminos
Comment=Luminos OS Desktop
Exec=/usr/local/bin/luminos-session
Type=Application
SESSION

  # ---- Session script ----
  mkdir -p "$AIROOTFS/usr/local/bin"
  cat > "$AIROOTFS/usr/local/bin/luminos-session" << 'SESSIONSCRIPT'
#!/bin/bash
python3 /opt/luminos/src/daemon/main.py &
sleep 2
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
    "luminos-run-windows:src/zone2/wine_runner.py" \
    "luminos-greeter:src/gui/greeter/greeter_app.py"; do
    local name="${pair%%:*}"
    local script="${pair#*:}"
    cat > "$AIROOTFS/usr/local/bin/$name" << LAUNCHER
#!/bin/bash
exec python3 /opt/luminos/src/$script "\$@"
LAUNCHER
    chmod +x "$AIROOTFS/usr/local/bin/$name"
  done

  # ---- .desktop handler for .exe files ----
  mkdir -p "$AIROOTFS/usr/share/applications"
  cp "$(pwd)/config/luminos-windows.desktop" "$AIROOTFS/usr/share/applications/" 2>/dev/null || true

  # ---- GPU hybrid mode init service ----
  cat > "$AIROOTFS/usr/local/bin/luminos-gpu-init" << 'GPUINIT'
#!/bin/bash
supergfxctl --mode Hybrid 2>/dev/null || true
GPUINIT
  chmod +x "$AIROOTFS/usr/local/bin/luminos-gpu-init"

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
  ln -sf /etc/systemd/system/luminos-gpu-init.service "$WANTS/" 2>/dev/null || true

  # ---- Hyprland config (from project or embedded) ----
  mkdir -p "$AIROOTFS/etc/skel/.config/hypr"
  if [ -d "$(pwd)/config/hypr" ]; then
    cp -r "$(pwd)/config/hypr/"* "$AIROOTFS/etc/skel/.config/hypr/"
  else
    # Embedded default Hyprland config
    cat > "$AIROOTFS/etc/skel/.config/hypr/hyprland.conf" << 'HYPRCONF'
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
  shadow {
    enabled = true
    range = 20
    render_power = 3
    color = rgba(00000055)
  }
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

bind = , XF86MonBrightnessUp, exec, brightnessctl set +10%
bind = , XF86MonBrightnessDown, exec, brightnessctl set 10%-

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
  fi

  # ---- Waybar config ----
  mkdir -p "$AIROOTFS/etc/skel/.config/waybar"
  cat > "$AIROOTFS/etc/skel/.config/waybar/config" << 'WAYBAR'
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
    "hyprland/workspaces"
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
  "hyprland/workspaces": {
    "format": "{name}",
    "on-click": "activate"
  },
  "clock": {
    "format": "{:%H:%M}",
    "format-alt": "{:%A, %B %d %Y  %H:%M}",
    "tooltip-format": "<big>{:%Y %B}</big>\n<tt>{calendar}</tt>"
  },
  "cpu": { "format": " {usage}%", "interval": 5, "tooltip": false },
  "memory": { "format": " {percentage}%", "interval": 10 },
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
    "states": { "warning": 30, "critical": 15 }
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
    "format-icons": { "default": ["", "", ""] },
    "on-click": "pactl set-sink-mute @DEFAULT_SINK@ toggle"
  },
  "tray": { "spacing": 8 }
}
WAYBAR

  cat > "$AIROOTFS/etc/skel/.config/waybar/style.css" << 'WAYBARCSS'
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

#workspaces button.active {
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

  # ---- Wofi config ----
  mkdir -p "$AIROOTFS/etc/skel/.config/wofi"
  cat > "$AIROOTFS/etc/skel/.config/wofi/config" << 'WOFICONF'
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

  cat > "$AIROOTFS/etc/skel/.config/wofi/style.css" << 'WOFICSS'
* { font-family: "Inter", sans-serif; }
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
#scroll { margin: 4px 8px 10px 8px; }
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
#entry:hover { background-color: rgba(255,255,255,0.07); }
#img { margin-right: 8px; }
#text { color: rgba(255,255,255,0.88); font-size: 14px; }
WOFICSS

  # ---- Foot terminal config ----
  mkdir -p "$AIROOTFS/etc/skel/.config/foot"
  cat > "$AIROOTFS/etc/skel/.config/foot/foot.ini" << 'FOOTINI'
[main]
font=JetBrains Mono Nerd Font:size=13
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
FOOTINI

  # ---- GTK settings ----
  mkdir -p "$AIROOTFS/etc/skel/.config/gtk-3.0"
  cat > "$AIROOTFS/etc/skel/.config/gtk-3.0/settings.ini" << 'GTK3'
[Settings]
gtk-theme-name=Adwaita-dark
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 11
gtk-cursor-theme-name=Adwaita
gtk-cursor-theme-size=24
gtk-application-prefer-dark-theme=1
gtk-decoration-layout=close,minimize,maximize:
GTK3

  mkdir -p "$AIROOTFS/etc/skel/.config/gtk-4.0"
  cat > "$AIROOTFS/etc/skel/.config/gtk-4.0/settings.ini" << 'GTK4'
[Settings]
gtk-theme-name=Adwaita-dark
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 11
gtk-cursor-theme-name=Adwaita
gtk-cursor-theme-size=24
gtk-application-prefer-dark-theme=1
gtk-decoration-layout=close,minimize,maximize:
GTK4

  # ---- Shell config ----
  cat > "$AIROOTFS/etc/skel/.bashrc" << 'BASHRC'
export PS1='\[\033[38;5;75m\]luminos\[\033[0m\] \[\033[38;5;245m\]\W\[\033[0m\] \[\033[38;5;75m\]❯\[\033[0m\] '
alias ls='ls --color=auto'
alias ll='ls -la'
alias grep='grep --color=auto'
alias luminos-status='python3 /opt/luminos/src/daemon/main.py --status'
export PATH="/opt/luminos/src:$PATH"
BASHRC

  cat > "$AIROOTFS/etc/skel/.bash_profile" << 'BASHPROFILE'
[[ -f ~/.bashrc ]] && . ~/.bashrc
# Auto-start Hyprland on tty1
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
  exec Hyprland
fi
BASHPROFILE

  # ---- Hyprpaper config ----
  cat > "$AIROOTFS/etc/skel/.config/hypr/hyprpaper.conf" << 'HYPRPAPER'
preload = /usr/share/backgrounds/luminos-default.png
wallpaper = ,/usr/share/backgrounds/luminos-default.png
splash = false
HYPRPAPER

  # ---- Hyprlock config ----
  cat > "$AIROOTFS/etc/skel/.config/hypr/hyprlock.conf" << 'HYPRLOCK'
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
  cat > "$AIROOTFS/etc/skel/.config/hypr/hypridle.conf" << 'HYPRIDLE'
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

  touch "$FLAG_CONFIGS"
  echo "Stage 3 complete" | tee -a "$LOG"
}

# ============================================================================
# Stage 4: Build ISO with mkarchiso
# ============================================================================
stage4_build_iso() {
  if [ -f "$FLAG_ISO" ] && ls "$OUTPUT_DIR"/*.iso &>/dev/null; then
    log_stage SKIP 4 "ISO already built"
    return 0
  fi

  log_stage RUN 4 "build ISO with mkarchiso"
  mkdir -p "$WORK_DIR" "$OUTPUT_DIR"

  sudo mkarchiso -v \
    -w "$WORK_DIR" \
    -o "$OUTPUT_DIR" \
    "$PROFILE_DIR" \
    2>&1 | tee -a "$LOG"

  touch "$FLAG_ISO"
  echo "Stage 4 complete" | tee -a "$LOG"
}

# ============================================================================
# Main
# ============================================================================
echo "=== Luminos OS Smart Build (Arch) ===" | tee "$LOG"
mkdir -p "$BUILD_DIR"

check_deps
stage1_profile
stage2_customize
stage3_configs
stage4_build_iso

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ISO_FILE=$(ls -t "$OUTPUT_DIR"/*.iso 2>/dev/null | head -1)

echo ""
echo "=== BUILD COMPLETE ==="
if [ -n "${ISO_FILE:-}" ]; then
  ISO_SIZE=$(du -sh "$ISO_FILE" | cut -f1)
  echo "ISO: $ISO_FILE"
  echo "Size: $ISO_SIZE"
fi
echo "Time: $((ELAPSED/60))m $((ELAPSED%60))s"
echo "Log: $LOG"
