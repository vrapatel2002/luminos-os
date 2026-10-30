#!/usr/bin/env bash
# Diagnose why the legacy launcher starts the beta, then optionally remove the beta.
# Phase 1 is read-only. Nothing is removed without you typing YES.
set -uo pipefail
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "What is /usr/local/bin/claude-desktop-legacy ?"
ls -la /usr/local/bin/claude-desktop-legacy
file /usr/local/bin/claude-desktop-legacy
if head -c2 /usr/local/bin/claude-desktop-legacy | grep -q '#!'; then
  echo "--- it is a script, contents: ---"
  cat /usr/local/bin/claude-desktop-legacy
else
  echo "--- binary; strings referencing claude-desktop: ---"
  strings /usr/local/bin/claude-desktop-legacy 2>/dev/null | grep -i 'claude-desktop' | head -20
fi

say "Where does it actually resolve to"
readlink -f /usr/local/bin/claude-desktop-legacy

say "Does the legacy app payload still exist"
for d in /opt/claude-desktop-legacy /usr/local/lib/claude-desktop-legacy /opt/claude-legacy /usr/local/share/claude-desktop-legacy; do
  [ -e "$d" ] && echo "  FOUND $d" && ls "$d" | head -5
done
echo "  (nothing listed above means the legacy payload is gone)"

say "Who owns the files pacman-wise"
pacman -Qo /usr/local/bin/claude-desktop-legacy 2>&1 | head -2

say "What is running right now"
pgrep -af claude | head -20

say "PHASE 2 - remove the beta package"
echo "Only do this if a legacy payload was FOUND above."
read -r -p "Type YES to run 'sudo pacman -Rns claude-desktop': " ans
if [ "$ans" = "YES" ]; then
  sudo pacman -Rns claude-desktop
  say "Remaining claude packages"
  pacman -Qs claude || echo "  (none)"
else
  echo "Skipped. Nothing was removed."
fi
