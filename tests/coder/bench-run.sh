#!/usr/bin/env bash
# [CHANGE: claude-code | 2026-10-23] luminos-coder: start one llama-server config through the dGPU gate, probe it, record JSON, stop it.
# usage: bench-run.sh <label> <prompt_tokens> <gen_tokens> -- <llama-server args…>
set -u
L=$1; PL=$2; GN=$3; shift 4
OUT=~/.local/state/luminos/coder/bench-$L
/usr/local/bin/dgpu-exec-v2 -- "${LLAMA_SERVER:-/usr/bin/llama-server}" "$@" --host 127.0.0.1 --port 8093 --jinja -fa on --no-ui -t 8 >"$OUT.log" 2>&1 &
SP=$!
for i in $(seq 300); do curl -fs 127.0.0.1:8093/health >/dev/null 2>&1 && break; kill -0 $SP 2>/dev/null || break; sleep 2; done
LOADED=$(date +%s)
VRAM=$(/usr/local/bin/dgpu-exec-v2 -- nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null)
MA=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
R=$(python3 ~/luminos-os/tests/coder/bench.py 8093 "$PL" "$GN" 2>&1)
GPU=$(/usr/local/bin/dgpu-exec-v2 -- nvidia-smi --query-gpu=power.draw,clocks.sm,pcie.link.gen.current,temperature.gpu --format=csv,noheader 2>/dev/null)
echo "{\"label\":\"$L\",\"vram\":\"$VRAM\",\"memavail_mb\":$MA,\"result\":$R,\"gpu_after\":\"$GPU\"}" >> ~/.local/state/luminos/coder/bench-results.jsonl
kill $SP; wait $SP 2>/dev/null
