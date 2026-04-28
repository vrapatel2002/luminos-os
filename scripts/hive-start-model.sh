#!/bin/bash
# [CHANGE: antigravity | 2026-04-28]
# ============================================
# SECTION: HIVE Model Launcher
# PURPOSE: Starts llama-server with strict GPU enforcement.
#          Uses ABSOLUTE PATHS for every binary so this works
#          from kglobalaccel's minimal env (SUPER+SPACE shortcut).
# SAFE FLAGS ONLY: --n-gpu-layers 99 --ctx-size 4096 --port 8080 --host 127.0.0.1
# BANNED: --cache-type-k turbo4, --flash-attn (core dump on this hardware)
# ============================================

# Hardened environment — same reason as luminos-hive-popup
export HOME="${HOME:-/home/shawn}"
export PATH="/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/opt/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/opt/cuda/lib64:/usr/lib:/usr/local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

if [ -z "$1" ]; then
    echo "Usage: $0 <model-name> (nexus|bolt|nova)"
    exit 1
fi

MODEL_NAME=$1

# Model paths — hardcoded, no $HOME expansion issues
case "$MODEL_NAME" in
    "nexus")
        MODEL_PATH="/home/shawn/.local/share/luminos/models/hive/Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf"
        ;;
    "bolt")
        MODEL_PATH="/home/shawn/.local/share/luminos/models/hive/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
        ;;
    "nova")
        MODEL_PATH="/home/shawn/.local/share/luminos/models/hive/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf"
        ;;
    *)
        echo "Unknown model: $MODEL_NAME"
        exit 1
        ;;
esac

# Kill existing server if running (only one model at a time)
if /usr/bin/pgrep -x "llama-server" > /dev/null 2>&1; then
    echo "Killing existing llama-server..."
    /usr/bin/pkill -x "llama-server"
    /usr/bin/sleep 2
fi

/usr/bin/touch /tmp/hive-last-request

echo "Starting llama-server with model $MODEL_PATH..."
# SAFE FLAGS ONLY — --n-gpu-layers 99 is NON-NEGOTIABLE (full GPU)
/usr/local/bin/llama-server \
    -m "$MODEL_PATH" \
    --n-gpu-layers 99 \
    --ctx-size 4096 \
    --port 8080 \
    --host 127.0.0.1 >> /tmp/hive-server.log 2>&1 &

# Wait for server health check
TIMEOUT=30
while [ $TIMEOUT -gt 0 ]; do
    if /usr/bin/curl -s http://localhost:8080/health 2>/dev/null | /usr/bin/grep -q "ok"; then
        echo "ready"
        exit 0
    fi
    /usr/bin/sleep 1
    TIMEOUT=$((TIMEOUT-1))
done

echo "failed — check /tmp/hive-server.log"
exit 1
