## STATUS: COMPLETE — Arch migration done. Kept for historical reference.

# LUMINOS OS — MIGRATION & REBUILD PLAN
# Ubuntu → Arch Linux
# Read this before touching any code.

---

## THE CORE QUESTION: Rebuild or Migrate?

### Honest Answer: Rebuild The Base, Salvage The UI

Here is what is worth keeping from the Ubuntu build:
- Hyprland config (needs shadow fix, but structure is good)
- Settings app code (Python/GTK or web-based — port it)
- Any custom scripts that don't use apt/casper/ubuntu paths
- The visual design decisions (dock style, colors, layout)

Here is what gets thrown away:
- Everything Casper-related (all of it)
- Ubuntu package lists and apt scripts
- ISO build pipeline (rewrite for Arch)
- Any script that references the ubuntu user
- dpkg hooks and initramfs patches we tried to fix

---

## PHASE 0 — BEFORE TOUCHING ANYTHING
**Time estimate: 1 session**

```
[ ] Save current Ubuntu build state (snapshot or backup)
[ ] Document every custom file that exists in the project
[ ] List every script in the build pipeline
[ ] Note which scripts are Ubuntu-specific vs generic
[ ] Put LUMINOS_PROJECT_SCOPE.md and LUMINOS_DECISIONS.md in repo root
[ ] Put LUMINOS_AGENT_PROMPT.md in repo root
[ ] Commit everything to git with message "Ubuntu build — final state before Arch migration"
```

Why: You want a clean restore point. If Arch build goes wrong you
can always come back. Never start a migration without a checkpoint.

---

## PHASE 1 — ARCH BASE INSTALL
**Time estimate: 1-2 sessions**

### Step 1: Install Base Arch
```bash
# Use archinstall script — easier than manual
# Boot Arch ISO
archinstall

# Choices during archinstall:
# Profile: minimal (no desktop — we add Hyprland ourselves)
# Bootloader: grub
# Filesystem: ext4 or btrfs (btrfs recommended — snapshots)
# User: luminos (not ubuntu, not root)
# Network: NetworkManager
```

### Step 2: Install Core Tools
```bash
# After first boot into Arch
sudo pacman -Syu

# AUR helper
sudo pacman -S git base-devel
git clone https://aur.archlinux.org/yay.git
cd yay && makepkg -si

# Core system tools
sudo pacman -S networkmanager pipewire pipewire-pulse wireplumber \
               polkit xdg-user-dirs xdg-desktop-portal
```

### Step 3: ROG Hardware Tools
```bash
# asusctl and supergfxctl — these are the whole reason we're on Arch
yay -S asusctl supergfxctl power-profiles-daemon

# Enable services
sudo systemctl enable --now asusd
sudo systemctl enable --now supergfxd

# LOCK GPU to hybrid immediately — do this now, never change it
supergfxctl --mode Hybrid
```

### Step 4: NVIDIA + Wayland Setup
```bash
# NVIDIA drivers for Wayland
sudo pacman -S nvidia nvidia-utils nvidia-settings

# Required env vars for Hyprland + NVIDIA
# Add to /etc/environment:
LIBVA_DRIVER_NAME=nvidia
XDG_SESSION_TYPE=wayland
GBM_BACKEND=nvidia-drm
__GLX_VENDOR_LIBRARY_NAME=nvidia
WLR_NO_HARDWARE_CURSORS=1
```

### Checkpoint After Phase 1
```
[ ] Arch boots cleanly
[ ] luminos user exists and works  
[ ] asusctl running (check: systemctl status asusd)
[ ] supergfxctl set to Hybrid (check: supergfxctl --mode)
[ ] NVIDIA drivers loaded (check: nvidia-smi)
[ ] No boot errors
```

---

## PHASE 2 — HYPRLAND & DESKTOP
**Time estimate: 1-2 sessions**

### Step 1: Install Hyprland
```bash
sudo pacman -S hyprland
yay -S hyprland-git  # if you need bleeding edge

# Required companions
sudo pacman -S waybar wofi dunst swww grim slurp \
               xdg-desktop-portal-hyprland qt5-wayland qt6-wayland
```

### Step 2: Port Hyprland Config
```bash
# Copy your existing hyprland.conf
# Then fix the deprecated shadow options:

# REMOVE these (lines 34-37 in old config):
decoration {
    drop_shadow = yes
    shadow_range = 4
    shadow_render_power = 3
    col.shadow = rgba(1a1a1aee)
}

# REPLACE WITH:
decoration {
    shadow {
        enabled = yes
        range = 4
        render_power = 3
        color = rgba(1a1a1aee)
    }
}
```

### Step 3: Login Manager (greetd)
```bash
yay -S greetd greetd-tuigreet

# Or for custom graphical greeter:
yay -S greetd-gtkgreet
```

**Login screen spec (build this):**
```
- Full screen dark background
- Large clock center (HH:MM format)
- Date below clock (Day, Month DD YYYY)  
- Press Enter → if password set: show password field
- Press Enter → if no password: go straight to desktop
- No username list
- No visible input field until Enter pressed
```

### Step 4: Dock & Bar
```bash
# Port existing waybar config
# Fix alignment issues from old build
# Dock: center bottom, floating
# Bar: top, full width
```

### Checkpoint After Phase 2
```
[ ] Hyprland launches without config errors
[ ] No shadow deprecation warnings
[ ] greetd shows custom login screen
[ ] Login works with and without password
[ ] Dock visible and centered
[ ] Top bar working
[ ] Wallpaper loads
```

---

## PHASE 3 — SETTINGS APP & CORE UI
**Time estimate: 1-2 sessions**

### What To Port
```
[ ] Appearance settings (theme, accent color, font size, animations)
[ ] Wallpaper picker
[ ] Display settings
[ ] Power settings (show battery/performance mode status — no manual switch)
[ ] Sound settings
[ ] Network settings
[ ] Privacy settings
[ ] About Luminos page
```

### What To Add (New)
```
[ ] Zones tab (compatibility layer management — placeholder for now)
[ ] AI & HIVE tab (placeholder for now)
```

### What To Remove
```
[ ] Any Ubuntu Software Center references
[ ] Any snap store references
[ ] Any ubuntu-advantage / pro references
[ ] Release upgrade settings
```

### Checkpoint After Phase 3
```
[ ] Settings app opens
[ ] Theme switching works
[ ] Wallpaper picker works
[ ] Display settings work
[ ] Power shows current mode (battery/performance)
[ ] No Ubuntu references visible anywhere
```

---

## PHASE 4 — WINDOWS COMPATIBILITY STACK
**Time estimate: 3-4 sessions**

### Step 1: Layer 1 (Proton/Wine/Lutris)
```bash
sudo pacman -S wine wine-gecko wine-mono
sudo pacman -S lutris
yay -S proton-ge-custom  # better than stock Proton for most games

# Steam for Proton
sudo pacman -S steam
```

### Step 2: Layer 2 (Firecracker microVM)
```bash
# Firecracker binary
yay -S firecracker-bin

# Setup microVM images
# This needs its own dedicated session — complex setup
```

### Step 3: Layer 3 (KVM/QEMU)
```bash
sudo pacman -S qemu-full virt-manager libvirt
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt luminos
```

### Step 4: Compatibility Router (The AI Part)
```bash
# This is a dedicated project — needs its own sessions
# Components needed:
# 1. PE header parser
# 2. Windows API detector  
# 3. Rule engine (handles 80% of decisions)
# 4. Small quantized model (handles 20% edge cases)
# 5. Unix socket daemon
# 6. App launch interceptor
```

---

## PHASE 5 — AI LAYER
**Time estimate: 2-3 sessions**

### llama.cpp Daemon
```bash
# Build llama.cpp for your hardware
yay -S llama-cpp

# Run as system service via Unix socket
# Config: use CPU for router model, GPU for heavy inference
```

### Sentinel (NPU)
```bash
# XDNA NPU drivers
yay -S xdna-driver-git  # or whatever AUR package has latest

# SmolLM2-360M quantized model
# Convert to GGUF format for llama.cpp
# Deploy as NPU inference target
```

---

## PHASE 6 — POLISH & ISO BUILD
**Time estimate: 2-3 sessions**

### Arch ISO Build (replaces the Ubuntu casper pipeline)
```bash
# Use archiso — Arch's own ISO builder
sudo pacman -S archiso

# Start from releng profile
cp -r /usr/share/archiso/configs/releng/ ~/luminos-iso

# Customize:
# - Add all our packages to packages.x86_64
# - Add our configs to airootfs/
# - Set default user to luminos (no ubuntu user, no casper, no hardcoding)
# - Add our systemd services

# Build
sudo mkarchiso -v -w /tmp/luminos-work -o ~/luminos-output ~/luminos-iso
```

---

## OVERALL TIMELINE

| Phase | What | Sessions | Priority |
|-------|------|----------|----------|
| 0 | Backup and prep | 1 | DO FIRST |
| 1 | Arch base + ROG tools | 1-2 | Critical |
| 2 | Hyprland + login + desktop | 1-2 | Critical |
| 3 | Settings app + core UI | 1-2 | High |
| 4 | Compatibility stack | 3-4 | High |
| 5 | AI layer | 2-3 | Medium |
| 6 | Polish + ISO build | 2-3 | Last |

**Total: roughly 11-17 Claude Code sessions**

---

## THE DECISION: Rebuild vs Migrate

| Approach | Pros | Cons |
|----------|------|------|
| Full rebuild on Arch | Clean, no Ubuntu artifacts, correct foundation | More work upfront |
| Migrate Ubuntu → Arch | Keeps existing work | Ubuntu patterns buried everywhere, will cause bugs |

**Recommendation: Full rebuild on Arch (Phase 1 fresh install)**
Port the UI code and configs manually.
Do NOT try to convert the Ubuntu build — too many Ubuntu assumptions buried in it.

The Ubuntu build took weeks because we kept hitting Ubuntu walls.
The Arch build will go faster because the tools actually cooperate.
