#!/bin/bash
# Toggle wofi: uses a lock file because wofi closes on focus-loss
# before the click handler can detect it's running.

LOCKFILE="/tmp/wofi-toggle.lock"

if [ -f "$LOCKFILE" ]; then
    pkill -x wofi 2>/dev/null
    rm -f "$LOCKFILE"
else
    touch "$LOCKFILE"
    wofi --show drun
    rm -f "$LOCKFILE"
fi
