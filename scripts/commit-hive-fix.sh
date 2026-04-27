#!/bin/bash
# Run this to deploy and commit the HIVE popup fix
# Usage: bash ~/luminos-os/scripts/commit-hive-fix.sh
# [CHANGE: antigravity | 2026-04-26]

set -e

REPO="$HOME/luminos-os"

# 1. Deploy to /usr/local/bin
echo ">>> Deploying popup script..."
sudo cp "$REPO/scripts/luminos-hive-popup" /usr/local/bin/luminos-hive-popup
sudo chmod +x /usr/local/bin/luminos-hive-popup
echo "    Deployed to /usr/local/bin/luminos-hive-popup"

# 2. Update luminos notes
echo ">>> Updating luminos notes..."
bash "$REPO/scripts/luminos-notes.sh" add hive-popup \
  "BUG-043/044 fix: Python/GTK4 replaced with bash/kdialog. Wayland env CRITICAL SECTION added. Desktop Exec redirected to repo path."
echo "    Notes updated"

# 3. Git commit
echo ">>> Committing..."
cd "$REPO"
git add scripts/luminos-hive-popup \
       scripts/deploy-hive-popup.sh \
       scripts/commit-hive-fix.sh \
       config/luminos-hive-popup.desktop \
       LUMINOS_STATUS.md \
       docs/BUGS.md

git commit -m "fix(hive): SUPER+SPACE popup Wayland fix (BUG-043/044)

Root cause 1: Script was Python/GTK4 (banned), crashes as bash syntax error
Root cause 2: kglobalaccel on Wayland strips WAYLAND_DISPLAY env vars
Fix: Bash/kdialog rewrite with CRITICAL SECTION for Wayland env resolution
Desktop Exec redirected from /usr/local/bin to repo script path
Critical section marked in script - DO NOT MODIFY
Model paths section marked safe to update

Agent: antigravity
Task: Fix HIVE popup SUPER+SPACE on Wayland"

git push origin main

echo ""
echo "=== ALL DONE ==="
echo "Test: Press SUPER+SPACE now to verify"
