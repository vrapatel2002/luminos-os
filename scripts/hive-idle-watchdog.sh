#!/bin/bash
# [CHANGE: gemini-cli | 2026-04-27]
# ============================================
# SECTION: HIVE Idle Watchdog
# PURPOSE: Kills llama-server after 5 minutes of inactivity to free VRAM
# ============================================

IDLE_TIMEOUT=300 # 5 minutes in seconds
REQUEST_FILE="/tmp/hive-last-request"

while true; do
    sleep 60

    if pgrep -x "llama-server" > /dev/null; then
        if [ -f "$REQUEST_FILE" ]; then
            LAST_ACTIVE=$(stat -c %Y "$REQUEST_FILE")
            CURRENT_TIME=$(date +%s)
            TIME_DIFF=$((CURRENT_TIME - LAST_ACTIVE))

            if [ "$TIME_DIFF" -ge "$IDLE_TIMEOUT" ]; then
                echo "HIVE idle timeout — model unloaded"
                pkill -x "llama-server"
            fi
        else
            # Start timer if no file exists but server running
            touch "$REQUEST_FILE"
        fi
    fi
done
