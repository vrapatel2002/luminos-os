#!/bin/bash
# [CHANGE: antigravity | 2026-04-28]
# ============================================
# SECTION: HIVE Idle Watchdog
# PURPOSE: Kills llama-server after 5 minutes of inactivity to free VRAM.
#          Uses absolute paths for all binaries so it works from systemd.
# ============================================

IDLE_TIMEOUT=300 # 5 minutes in seconds
REQUEST_FILE="/tmp/hive-last-request"
# [CHANGE: claude-code | 2026-10-23] BUG-212: only HIVE's own llama-server (the one hive-start-model.sh
# starts on --port 8080). The old `pkill -x llama-server` killed EVERY llama-server on the box after 5 min of
# HIVE idle — it took down the luminos-coder models (port 8093) mid-request, and anything else on 8082/8083.
HIVE_LLAMA='^[^ ]*llama-server .*--port 8080( |$)'

while true; do
    /usr/bin/sleep 60

    if /usr/bin/pgrep -f -- "$HIVE_LLAMA" > /dev/null 2>&1; then
        if [ -f "$REQUEST_FILE" ]; then
            LAST_ACTIVE=$(/usr/bin/stat -c %Y "$REQUEST_FILE")
            CURRENT_TIME=$(/usr/bin/date +%s)
            TIME_DIFF=$((CURRENT_TIME - LAST_ACTIVE))

            if [ "$TIME_DIFF" -ge "$IDLE_TIMEOUT" ]; then
                echo "HIVE idle timeout — model unloaded"
                /usr/bin/pkill -f -- "$HIVE_LLAMA"
            fi
        else
            # Start timer if no file exists but server running
            /usr/bin/touch "$REQUEST_FILE"
        fi
    fi
done
