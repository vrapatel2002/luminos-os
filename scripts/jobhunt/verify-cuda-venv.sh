#!/usr/bin/env bash
# Prove the jobhunt CUDA venv actually runs a model ON the GPU.
# [CHANGE: claude-code | 2026-08-05] Phase 0 verification, PLAN.md
#
# WHY THIS EXISTS SEPARATELY FROM THE BUILD:
# `llama_supports_gpu_offload() == True` only reports how the wheel was COMPILED.
# A CUDA-enabled build falls back to CPU silently when the device is denied — and
# on this machine the device is denied by default (DECISION 25). So the build flag
# is not proof. This runs a real generation and reads VRAM back off the card.
#
# It also negative-tests: the same check WITHOUT the gate must fail, otherwise the
# check cannot distinguish "working" from "always says yes".
set -uo pipefail

VENV=/opt/luminos/venv-jobhunt
MODEL="${1:-$HOME/.local/share/luminos/models/hive/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf}"
CTX="${2:-4096}"

[ -x "$VENV/bin/python" ] || { echo "FAIL: $VENV missing — run build-cuda-venv.sh"; exit 1; }
[ -f "$MODEL" ]           || { echo "FAIL: model not found: $MODEL"; exit 1; }

echo "=== NEGATIVE TEST — without the gate this MUST report False"
ungated="$("$VENV/bin/python" -c \
  'import llama_cpp; print(llama_cpp.llama_supports_gpu_offload())' 2>/dev/null)"
if [ "$ungated" = "True" ]; then
  echo "FAIL: reports GPU support with the gate CLOSED — the check is meaningless."
  echo "      Either the gate is open to everyone (check /dev/nvidiactl perms) or"
  echo "      someone added a user to the dgpu group."
  exit 1
fi
echo "  ok: ungated = $ungated (denied, as designed)"

echo "=== REAL GENERATION through dgpu-exec-v2 (model: $(basename "$MODEL"), ctx=$CTX)"
dgpu-exec-v2 "$VENV/bin/python" - "$MODEL" "$CTX" <<'PY'
import sys, ctypes, llama_cpp
from llama_cpp import Llama

model, ctx = sys.argv[1], int(sys.argv[2])
assert llama_cpp.llama_supports_gpu_offload(), "build has no GPU support"

llm = Llama(model_path=model, n_gpu_layers=-1, n_ctx=ctx, verbose=False)
out = llm("List three Python web frameworks, comma separated:",
          max_tokens=48, temperature=0.0)
text = out["choices"][0]["text"].strip()
assert text, "FAIL: model returned empty text"
print("  generated:", text.replace("\n", " ")[:120])

# Read VRAM off the driver itself rather than trusting nvidia-smi parsing.
try:
    cu = ctypes.CDLL("libcuda.so.1")
    free, total = ctypes.c_size_t(), ctypes.c_size_t()
    cu.cuInit(0)
    dev = ctypes.c_int()
    cu.cuDeviceGet(ctypes.byref(dev), 0)
    pctx = ctypes.c_void_p()
    cu.cuCtxCreate_v2(ctypes.byref(pctx), 0, dev)
    cu.cuMemGetInfo_v2(ctypes.byref(free), ctypes.byref(total))
    used_mb = (total.value - free.value) // (1024*1024)
    total_mb = total.value // (1024*1024)
    print(f"  VRAM in use: {used_mb} MiB of {total_mb} MiB")
    if used_mb < 500:
        print("  FAIL: almost no VRAM in use — the model is on the CPU."); sys.exit(1)
    if used_mb > 4700:
        print(f"  WARN: {used_mb} MiB exceeds the 4.6 GB safe-VRAM budget (CLAUDE.md).")
except OSError as e:
    print("  WARN: could not query VRAM:", e)

print("  PASS: real generation ran on the GPU.")
PY
rc=$?
echo "=== exit: $rc"
exit $rc
