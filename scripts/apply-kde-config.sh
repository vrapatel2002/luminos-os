#!/bin/bash
# Luminos OS — Auto-apply KDE config on login
# [CHANGE: claude-code | 2026-04-20]

REPO=~/luminos-os/config/kde
CONFIG=~/.config

# Apply all KDE configs
cp $REPO/kdeglobals $CONFIG/
cp $REPO/kwinrc $CONFIG/
cp $REPO/plasma-org.kde.plasma.desktop-appletsrc $CONFIG/

# Apply wallpaper
plasma-apply-wallpaperimage \
  ~/.local/share/wallpapers/MacTahoe-Dark/contents/images/3840x2160.jpeg \
  2>/dev/null || true

# Apply icon theme
kwriteconfig6 --file kdeglobals \
  --group Icons --key Theme "MacTahoe-dark"

sleep 2

echo "Luminos KDE config applied successfully"
