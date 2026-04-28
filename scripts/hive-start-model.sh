#!/bin/bash
# [CHANGE: gemini-cli | 2026-04-27]
# ============================================
# SECTION: HIVE Model Launcher
# PURPOSE: Starts llama-server with strict GPU enforcement
# ============================================

if [ -z "$1" ]; then
    echo "Usage: $0 <model-name> (nexus|bolt|nova)"
    exit 1
fi

MODEL_NAME=$1

case "$MODEL_NAME" in
    "nexus")
        MODEL_PATH="$HOME/.local/share/luminos/models/hive/dolphin3.0-llama3.1-8b-Q4_K_M.gguf"
        ;;
    "bolt")
        MODEL_PATH="$HOME/.local/share/luminos/models/hive/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
        ;;
    "nova")
        MODEL_PATH="$HOME/.local/share/luminos/models/hive/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf"
        ;;
    *)
        echo "Unknown model: $MODEL_NAME"
        exit 1
        ;;
esac

if pgrep -x "llama-server" > /dev/null; then
    echo "Killing existing llama-server..."
    pkill -x "llama-server"
    sleep 2
fi

echo "Starting llama-server with model $MODEL_PATH..."
/usr/local/bin/llama-server \
    -m "$MODEL_PATH" \
    --n-gpu-layers 99 \
    --ctx-size 4096 \
    --port 8080 \
    --host 127.0.0.1 \
    --cache-type-k turbo4 \
    --flash-attn > /dev/null 2>&1 &

# Wait for server to be ready
TIMEOUT=30
while [ $TIMEOUT -gt 0 ]; do
    if curl -s http://localhost:8080/health | grep -q "ok"; then
        echo "ready"
        exit 0
    fi
    sleep 1
    TIMEOUT=$((TIMEOUT-1))
done

echo "failed"
exit 1
