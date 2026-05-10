#!/bin/bash
# [CHANGE: gemini-cli | 2026-05-10] Automated Tahoe theme apply script

# Plasma theme
plasma-apply-desktoptheme AppleDark-ALL 2>/dev/null

# Color scheme
plasma-apply-colorscheme MkosBigSurDark 2>/dev/null

# Window decoration
kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key library "org.kde.kwin.aurorae"
kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key theme "__aurorae__svg__MacTahoe-Dark"
kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key NoPlugin false

# Icons
kwriteconfig6 --file kdeglobals --group Icons --key Theme "MacTahoe-dark"

# Font - SF Pro Text Regular 10
kwriteconfig6 --file kdeglobals --group General --key font "SF Pro Text,10,-1,5,50,0,0,0,0,0"
kwriteconfig6 --file kdeglobals --group General --key fixed "SF Mono,10,-1,5,50,0,0,0,0,0"
kwriteconfig6 --file kdeglobals --group General --key menuFont "SF Pro Text,10,-1,5,50,0,0,0,0,0"
kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "SF Pro Text,8,-1,5,50,0,0,0,0,0"
kwriteconfig6 --file kdeglobals --group General --key toolBarFont "SF Pro Text,10,-1,5,50,0,0,0,0,0"
kwriteconfig6 --file kdeglobals --group WM --key activeFont "SF Pro Text,10,-1,5,56,0,0,0,0,0"

# Cursor theme
kwriteconfig6 --file kcminputrc --group Mouse --key cursorTheme "Bibata-Modern-Classic"

# Wallpaper
if [ -f ~/luminos-os/config/themes/TahoeDusk.webp ]; then
    plasma-apply-wallpaperimage ~/luminos-os/config/themes/TahoeDusk.webp 2>/dev/null
fi

# Blur/Contrast settings
kwriteconfig6 --file kwinrc --group Plugins --key blurEnabled true
kwriteconfig6 --file kwinrc --group Plugins --key contrastEnabled true
kwriteconfig6 --file kwinrc --group Effect-blur --key BlurStrength 7
kwriteconfig6 --file kwinrc --group Effect-blur --key NoiseStrength 0
kwriteconfig6 --file kwinrc --group Effect-contrast --key Contrast 0.3
kwriteconfig6 --file kwinrc --group Effect-contrast --key Intensity 0.4
kwriteconfig6 --file kwinrc --group Effect-contrast --key Saturation 1.7

# Panel transparency
kwriteconfig6 --file plasmashellrc --group "PlasmaViews" --key panelOpacity 1

# Rebuild icon cache
kbuildsycoca6 --noincremental 2>/dev/null
gtk-update-icon-cache -f -t ~/.local/share/icons/MacTahoe-dark/ 2>/dev/null
kwriteconfig6 --file kdeglobals --group KDE --key AnimationDurationFactor 1.0

# Notify running processes
qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null
qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.refreshCurrentShell 2>/dev/null

echo "Tahoe theme applied successfully."
