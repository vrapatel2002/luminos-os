#!/bin/bash
# [CHANGE: antigravity | 2026-04-28]
# ============================================
# SECTION: HIVE Idle Watchdog
# PURPOSE: Kills llama-server after 5 minutes of inactivity to free VRAM.
#          Uses absolute paths for all binaries so it works from systemd.
# ============================================

IDLE_TIMEOUT=300 # 5 minutes in seconds
REQUEST_FILE="/tmp/hive-last-request"

while true; do
    /usr/bin/sleep 60

    if /usr/bin/pgrep -x "llama-server" > /dev/null 2>&1; then
        if [ -f "$REQUEST_FILE" ]; then
            LAST_ACTIVE=$(/usr/bin/stat -c %Y "$REQUEST_FILE")
            CURRENT_TIME=$(/usr/bin/date +%s)
            TIME_DIFF=$((CURRENT_TIME - LAST_ACTIVE))

            if [ "$TIME_DIFF" -ge "$IDLE_TIMEOUT" ]; then
                echo "HIVE idle timeout — model unloaded"
                /usr/bin/pkill -x "llama-server"
            fi
        else
            # Start timer if no file exists but server running
            /usr/bin/touch "$REQUEST_FILE"
        fi
    fi
done
