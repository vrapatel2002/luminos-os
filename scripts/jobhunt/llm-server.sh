#!/usr/bin/env bash
# Serve the jobhunt LLM over an OpenAI-compatible HTTP API, on the dGPU.
# [CHANGE: claude-code | 2026-08-05] Phase 0b — infrastructure for OpenClaw et al.
#
# WHY THIS AND NOT `llama-server`: the llama-server BINARY is unstartable on this
# box (BUG-097 — libggml-cuda.so.0 and six other shared libs are missing from disk
# entirely). llama-cpp-python ships its own equivalent server as a Python module,
# which is built from the wheel we compiled ourselves, so it has no such problem.
#
# WHY dgpu-exec-v2: the RTX 4050's device nodes are default-deny (DECISION 25).
# Without the gate this server starts happily and silently runs on the CPU.
#
# BINDS TO 127.0.0.1 ONLY. An OpenAI-compatible endpoint with no auth must never
# be reachable off-box; anything on the LAN could drive it. Remote access is
# Tailscale's job, not this script's.
set -euo pipefail

VENV=/opt/luminos/venv-jobhunt
MODELS="$HOME/.local/share/luminos/models/hive"
# DEFAULT IS THE 4B, NOT THE 7B. An agent harness (OpenClaw) spends ~20k tokens on
# its system prompt and tool schemas before the user says a word, so a 4096-token
# model cannot host one at all. Measured: the 7B OOMs at ctx=16384 (cudaMalloc
# fails on a 958 MiB compute buffer). The 4B reaches 24576. The 7B is still the
# better writer — keep it for single-shot resume tailoring in Phase 3, where the
# prompt is one job posting and 4096 is plenty.
MODEL="${LLM_MODEL:-$MODELS/Qwen3-4B-Instruct-2507-Q4_K_M.gguf}"
HOST=127.0.0.1
PORT="${LLM_PORT:-8081}"
# 24576 is chosen against the VRAM ceiling, not picked round: it measures 4606 MiB
# total, just under the 4.6 GB safe budget in CLAUDE.md. Raising it to 32768 costs
# ~5.2 GB, which still loads but breaks that rule.
CTX="${LLM_CTX:-24576}"
# KV cache is the real VRAM cost here, not the weights: 144 KiB per token at f16,
# so 32k of context wants 4608 MiB on a card that only has ~5.7 GiB usable and has
# to hold the model too. q8_0 halves it for no meaningful quality loss.
# 8 = GGML_TYPE_Q8_0, 1 = GGML_TYPE_F16. A quantized V cache REQUIRES flash
# attention; without it llama.cpp falls back and the saving silently disappears.
KV_TYPE="${LLM_KV_TYPE:-8}"
# EMPTY BY DESIGN — do not "fix" this by naming a format. All three options were
# measured against a real tools payload:
#   chatml                  -> no tool support. The model narrates a tool call as
#                              markdown prose and waits forever. Looks like a dumb
#                              model; is actually a misconfigured server.
#   chatml-function-calling -> returns EMPTY content (6 tokens, finish_reason=stop).
#   (unset)                 -> uses the template baked into the GGUF, and Qwen3
#                              emits a CORRECT <tool_call>{...}</tool_call>.
# Unset wins, but llama-cpp-python leaves that call as raw text instead of parsing
# it into tool_calls[]. toolcall-proxy.py exists to do that parsing. So: leave this
# empty and point agent clients at the proxy, not at this port.
CHAT_FORMAT="${LLM_CHAT_FORMAT:-}"
# Clients address the model by this name, not by its path. Without an alias the
# served id is the absolute .gguf path, so every client config would break the
# moment a model moves or gets swapped for the 4B.
ALIAS="${LLM_ALIAS:-luminos-local}"

[ -x "$VENV/bin/python" ] || { echo "FAIL: $VENV missing — run build-cuda-venv.sh"; exit 1; }
[ -f "$MODEL" ] || { echo "FAIL: model not found: $MODEL"; exit 1; }

if ss -tln 2>/dev/null | grep -q "127.0.0.1:$PORT "; then
  echo "FAIL: 127.0.0.1:$PORT already in use. (HIVE's daemon owns 8078 — don't take it.)"
  exit 1
fi

# --logits_all false IS LOAD-BEARING. llama-cpp-python's server defaults it to
# TRUE, which keeps the logit vector for EVERY prompt token in SYSTEM RAM:
#   19,000 tokens x 151,936 vocab x 4 bytes = ~11.5 GB
# This box has 14 GB and 5 GB of zram. So short prompts work perfectly and long
# ones get the process SIGKILLed by the OOM killer partway through prefill.
#
# It is a nasty failure to read: uvicorn prints a tidy "Shutting down", the client
# just sees a dropped connection, nothing appears in the CUDA logs, and VRAM is
# nowhere near full — measured RSS climbing 4.9 -> 8.8 GB, swap to zero, then rc=137.
# Every symptom points at the GPU; the GPU is innocent.
#
# Only prompt-scoring/perplexity work needs the full logits. Chat does not.

# Only pass --chat_format when one was explicitly asked for; passing an empty
# string is NOT the same as omitting the flag (it fails to match any handler).
FORMAT_ARGS=()
[ -n "$CHAT_FORMAT" ] && FORMAT_ARGS=(--chat_format "$CHAT_FORMAT")

echo "serving $(basename "$MODEL") as '$ALIAS' on http://$HOST:$PORT  (ctx=$CTX, all layers on GPU)"
exec dgpu-exec-v2 "$VENV/bin/python" -m llama_cpp.server \
  --model "$MODEL" \
  --model_alias "$ALIAS" \
  --host "$HOST" --port "$PORT" \
  --n_gpu_layers -1 \
  --n_ctx "$CTX" \
  --flash_attn true \
  --type_k "$KV_TYPE" --type_v "$KV_TYPE" \
  --logits_all false \
  "${FORMAT_ARGS[@]}"
