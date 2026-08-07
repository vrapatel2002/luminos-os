#!/usr/bin/env bash
# Install the jobhunt systemd user units. [CHANGE: claude-code | 2026-08-06]
#
# WHY SYMLINKS AND NOT COPIES: the units live in the repo, so editing one and
# running `systemctl --user daemon-reload` is the whole edit cycle, and git
# tracks the change. Copies drift — you fix the running unit, forget the repo,
# and the next machine gets the broken one.
#
# WHAT GETS ENABLED, AND WHAT DELIBERATELY DOES NOT:
#   jobhunt-pipeline.timer     ENABLED — the nightly crawl+score
#   openclaw-gateway.service   ENABLED — the Control UI, so it survives reboot
#   jobhunt-llm.service        NOT enabled — on-demand only. Enabling it would
#                              pin 4.6 GB of VRAM and keep the dGPU awake 24/7,
#                              re-creating BUG-103. score.py starts and stops it.
#   jobhunt-toolproxy.service  NOT enabled — only the OpenClaw agent path needs
#                              it, and it is BindsTo the model server anyway.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/systemd"
DEST="$HOME/.config/systemd/user"
mkdir -p "$DEST"

for unit in "$SRC"/*.service "$SRC"/*.timer; do
  name="$(basename "$unit")"
  # -f so re-running this replaces an old symlink instead of failing. -n so a
  # symlink that already points at a DIRECTORY is replaced rather than followed
  # into it, which would silently install to the wrong path.
  ln -sfn "$unit" "$DEST/$name"
  echo "  linked $name"
done

systemctl --user daemon-reload

# systemd will not tell you a unit is malformed until something tries to start
# it, so verify now rather than at 03:30 tomorrow.
echo
for name in jobhunt-llm jobhunt-toolproxy jobhunt-pipeline openclaw-gateway; do
  if systemctl --user cat "$name" >/dev/null 2>&1; then
    echo "  ok      $name"
  else
    echo "  BROKEN  $name"; exit 1
  fi
done

echo
systemctl --user enable --now jobhunt-pipeline.timer
systemctl --user enable --now openclaw-gateway.service

echo
echo "  next run:"
systemctl --user list-timers jobhunt-pipeline.timer --no-pager | sed -n '1,2p'
