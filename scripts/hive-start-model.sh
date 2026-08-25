#!/bin/bash
# [CHANGE: antigravity | 2026-04-28]
# ============================================
# SECTION: HIVE Model Launcher
# PURPOSE: Starts llama-server with strict GPU enforcement.
#          Uses ABSOLUTE PATHS for every binary so this works
#          from kglobalaccel's minimal env (SUPER+SPACE shortcut).
# SAFE FLAGS ONLY: --n-gpu-layers 99 --ctx-size 16384 --port 8080 --host 127.0.0.1
# BANNED: --cache-type-k turbo4
# ============================================
# [CHANGE: claude-code | 2026-08-24] Three fixes, all verified on hardware:
#
# 1. BINARY: was /usr/local/bin/llama-server — a hand-built Apr-24 copy that
#    aborts on EVERY invocation (even --version) via
#    GGML_ASSERT(params.n_gpu_layers < 0) in common/arg.cpp. That assert tests
#    the compiled-in DEFAULT, so no flag combination could avoid it. The entire
#    HIVE GPU path was dead. Now uses the pacman binary /usr/bin/llama-server
#    (llama.cpp-cuda b10452-1).
#
# 2. DGPU-EXEC: DECISION 25 made /dev/nvidia* root:dgpu 0660 and shawn is
#    deliberately NOT in `dgpu`. Calling llama-server bare gets no GPU at all.
#    Only the setgid `dgpu-exec` grants egid=dgpu.
#
# 3. FLASH-ATTN UNBANNED: the April core dump was this same broken binary, not
#    the hardware. On b10452 `-fa on` works, which unlocks q8_0 KV cache and 4x
#    the context. Measured: 16384 ctx = 5718/6141 MiB, leaving ~73 MiB free.
#
# 4. [CHANGE: claude-code | 2026-08-25] ctx 12288 -> 16384. 12288 existed only
#    to leave room for the forex bot's ~130 MiB; Shawn has dropped that bot, so
#    the GPU is ours alone. This is the ceiling — 73 MiB free fits nothing else,
#    so if any other GPU workload returns, this is the first knob to turn down.
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
/usr/bin/nohup /usr/local/bin/dgpu-exec /usr/bin/llama-server \
    -m "$MODEL_PATH" \
    --n-gpu-layers 99 \
    --ctx-size 16384 \
    --flash-attn on \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --context-shift \
    --port 8080 \
    --host 127.0.0.1 >> /tmp/hive-server.log 2>&1 &

SERVER_PID=$!
# Disown so it survives script exit (especially when called via swap server)
disown $SERVER_PID 2>/dev/null || true

# Wait for server health check
TIMEOUT=90
while [ $TIMEOUT -gt 0 ]; do
    if /usr/bin/curl -s http://localhost:8080/health 2>/dev/null | /usr/bin/grep -q "ok"; then
        echo "ready"
        exit 0
    fi
    /usr/bin/sleep 1
    TIMEOUT=$((TIMEOUT-1))
done

echo "failed — check /tmp/hive-server.log"
# Kill the specific llama-server we just started so it doesn't ghost
/usr/bin/kill $SERVER_PID 2>/dev/null
exit 1
