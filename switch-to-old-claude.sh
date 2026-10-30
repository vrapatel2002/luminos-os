#!/usr/bin/env bash
# Switch back to the old (native) Claude Cowork backend.
# Safe + idempotent. Nothing is deleted.
set -uo pipefail

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "Stopping the beta desktop app and its helper"
pkill -f -i 'claude-desktop'        2>/dev/null
pkill -f 'cowork-linux-helper'      2>/dev/null
pkill -f 'qemu-system'              2>/dev/null
sleep 2

say "Re-enabling the old native backend"
systemctl --user enable --now claude-cowork.service
sleep 2
systemctl --user status claude-cowork.service --no-pager -l | head -12

say "Running processes"
pgrep -af cowork || echo "  (none)"
pgrep -af qemu   || echo "  (none)"

say "Installed Claude packages"
pacman -Qs claude 2>/dev/null || echo "  (pacman found nothing)"

say "Launchers available"
ls /usr/share/applications ~/.local/share/applications 2>/dev/null | grep -i claude || echo "  (none found)"

say "Claude binaries on PATH"
for b in claude claude-desktop claude-native; do
  command -v "$b" >/dev/null && printf '  %-16s %s\n' "$b" "$(command -v "$b")"
done

say "Done. Launch the OLD app only - do not start the beta alongside it."
