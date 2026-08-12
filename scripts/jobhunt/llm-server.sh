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
# [CHANGE: claude-code | 2026-08-07] With LLM_MOE=1 the default becomes the 26B MoE,
# and specifically the IQ4_XS quant — NOT the Q4_K_XL that was downloaded first.
# Measured head-to-head, keep=3, 1947-token prompt + 200 generated:
#   IQ4_XS  12.66 GiB   4588 MiB VRAM   8.2 GB RAM   206 t/s read  17.5 t/s write  21.0 s  loads in 15 s
#   Q4_K_XL 15.84 GiB   4918 MiB VRAM  12.4 GB RAM   134 t/s read  22.3 t/s write  23.6 s  loads in 8+ min
# IQ4_XS is faster overall and leaves 4.2 GB more RAM, which is the whole point: the
# Q4_K_XL needs ~12.4 GB resident and cannot coexist with a browser on a 15.3 GiB box.
# It writes ~22% slower because IQ quants decode through a codebook and the experts
# run on the CPU during generation — that is the trade being made on purpose.
# Q5/Q6/Q8 of this model are 19.7/21.6/25.0 GiB and are not runnable here at all,
# so IQ4_XS is the quality ceiling, not a compromise pick.
if [ "${LLM_MOE:-0}" = "1" ]; then
  MODEL="${LLM_MODEL:-$MODELS/gemma-4-26B-A4B-it-UD-IQ4_XS.gguf}"
else
  MODEL="${LLM_MODEL:-$MODELS/Qwen3-4B-Instruct-2507-Q4_K_M.gguf}"
fi
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
# -1 = every layer on the GPU, which is what you want whenever the model fits.
# A POSITIVE NUMBER SPLITS THE MODEL: that many layers on the card, the rest left in
# system RAM. That is the only way a 12B runs on a 6 GB card at all.
#
# THE COST IS RAM BANDWIDTH, NOT PCIe. A CPU-resident layer is COMPUTED on the CPU;
# only a small activation vector crosses the bus. What costs real time is the CPU
# reading that layer's weights out of system RAM, once per token. So the only lever
# that matters is BYTES LEFT IN RAM — push ngl as high as it still loads.
# Measured 2026-08-06 on gemma-4-12b-it-qat-q4_0 at ctx 8192: ngl=0 -> 5.6 tok/s,
# ngl=25 -> 9.6, ngl=29 -> 10.7. ngl=31 will not load.
#
# THIS OFFLOADS WEIGHTS, NOT THE KV CACHE. Do not also reach for --offload_kqv false
# to buy headroom: measured on Qwen3-4B that cost 25% on an empty cache and 57% at
# 5.5k tokens, because the cache is re-read on every token. Drop a layer instead.
NGL="${LLM_NGL:--1}"

# [CHANGE: claude-code | 2026-08-07] MoE path. Set LLM_MOE=1 to serve a
# mixture-of-experts model whose weights do not fit on the card, by pinning the
# expert banks to system RAM (DECISION 58, scripts/luminos_moe_offload.py).
#
# This is NOT a general "make big models fit" switch — it only helps MoE, because
# only MoE has weights that are idle on most tokens. Turning it on for a DENSE model
# does nothing (no tensor matches `_exps.`) and the model will simply fail to load.
#
# Measured 2026-08-07, gemma-4-26b-a4b, 1947-token prompt + 200 generated:
#   LLM_MOE_KEEP=0 -> 3556 MiB, 72.2 t/s read, 17.21 t/s write, 38.73 s
#   LLM_MOE_KEEP=3 -> 4918 MiB, 134.5 t/s read, 22.31 t/s write, 23.60 s  <- default
#   LLM_MOE_KEEP=4 -> 5372 MiB, 121.2 t/s read, 22.92 t/s write, 24.95 s
#   LLM_MOE_KEEP=5 -> OOM
# Note 4 is WORSE than 3 despite holding more on the card. Not monotonic — if you
# swap models, re-measure rather than assuming the number carries over.
MOE="${LLM_MOE:-0}"

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

# The MoE launcher takes the SAME arguments — it only patches how the model loads.
# It also forces n_gpu_layers to ALL, deliberately: the expert override is
# subtractive, so every layer must start on the card for it to subtract from.
ENTRY=(-m llama_cpp.server)
MOE_ENV=()
if [ "$MOE" = "1" ]; then
  ENTRY=("$(dirname "$(readlink -f "$0")")/moe-server.py")
  NGL=-1

  # GGML_CUDA_NO_PINNED=1 IS LOAD-BEARING AND COST A KERNEL PANIC TO LEARN.
  # [CHANGE: claude-code | 2026-08-07] BUG-111.
  #
  # llama.cpp hands CPU-side offloaded weights to CUDA as PINNED (page-locked)
  # host memory via cudaHostRegister, because pinned pages can be DMA'd across
  # PCIe without a bounce buffer. Pinned pages are also, by definition,
  # UNEVICTABLE AND UNSWAPPABLE.
  #
  # That silently deletes the bottom tier of this box's memory hierarchy. The
  # design is VRAM -> RAM -> NVMe; pinning turns RAM into a hard wall instead of
  # a spill point. The panic dump is unambiguous:
  #     unevictable:14512768kB   mlocked:12347344kB
  #     Free swap = 8041640kB        <-- 8 GB of spill space, untouched
  #     Out of memory and no killable processes... Kernel panic
  # Eight gigabytes of swap sat free while the machine starved, because not one
  # page of the model was legally movable.
  #
  # With this unset the ONLY symptom is the process being OOM-killed mid-load
  # with no error in its own log -- it looks like a crash in llama.cpp. It is not.
  MOE_ENV=(GGML_CUDA_NO_PINNED=1)
  echo "MoE mode: expert banks -> system RAM (keep=${LLM_MOE_KEEP:-3} layers on GPU)"
  echo "MoE mode: pinned host memory DISABLED so RAM can spill to swap/NVMe"

  # A model whose CPU-side half exceeds free RAM + swap cannot be rescued by
  # paging -- it just thrashes. Refuse rather than take the box down with it.
  # This is not the "models must fit in RAM" caveat: NVMe is a legitimate tier.
  # It is a check that the tier BELOW RAM is actually big enough to hold the
  # spill, which on 2026-08-07 it was not.
  need_mb=$(( $(stat -c %s "$MODEL") / 1048576 ))
  have_mb=$(( $(awk '/MemAvailable/{print $2}' /proc/meminfo) / 1024
              + $(awk '/SwapFree/{print $2}' /proc/meminfo) / 1024 ))
  if [ "$need_mb" -gt "$have_mb" ]; then
    echo "REFUSING: model is ${need_mb} MiB but only ${have_mb} MiB of RAM+swap is free."
    echo "  Close something, or raise LLM_MOE_KEEP to hold more experts on the card."
    exit 1
  fi
fi

echo "serving $(basename "$MODEL") as '$ALIAS' on http://$HOST:$PORT  (ctx=$CTX, all layers on GPU)"
exec env "${MOE_ENV[@]}" dgpu-exec-v2 "$VENV/bin/python" "${ENTRY[@]}" \
  --model "$MODEL" \
  --model_alias "$ALIAS" \
  --host "$HOST" --port "$PORT" \
  --n_gpu_layers "$NGL" \
  --n_ctx "$CTX" \
  --flash_attn true \
  --type_k "$KV_TYPE" --type_v "$KV_TYPE" \
  --logits_all false \
  "${FORMAT_ARGS[@]}"
