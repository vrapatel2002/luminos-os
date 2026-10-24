#!/bin/bash
# [CHANGE: claude-code | 2026-10-24] Ternary Bonsai 2 27B speed/VRAM on the RTX 4050 (PrismML fork), gateway-like args.
S=~/.local/state/luminos/coder; OUT=$S/bonsai-bench.txt; : > $OUT
sudo -n systemctl unmask nvidia-powerd && sudo -n systemctl start nvidia-powerd
export LLAMA_SERVER=~/.local/share/luminos/llama-prism/src/build/bin/llama-server
CTX=${CTX:-65536}
~/luminos-os/tests/coder/bench-run.sh bonsai-c$CTX 2000 256 -- -m ~/.local/share/luminos/models/bonsai/Ternary-Bonsai-2-27B-PTQ1_0.gguf \
   -c $CTX -ctk q8_0 -ctv q8_0 -np 1 -b 2048 -ub 2048 -fitt 256 --reasoning-budget 8192 \
   --presence-penalty 0.0 --temp 1.0 --top-k 20 --top-p 0.95 --min-p 0.05
L=$S/bench-bonsai-c$CTX.log
grep -aE 'offloaded|model buffer size|KV buffer|compute buffer|CUDA0|error|Segmentation|failed' $L | head -14 >> $OUT
tail -1 $S/bench-results.jsonl >> $OUT
sudo -n systemctl stop nvidia-powerd; sudo -n systemctl mask nvidia-powerd
echo BENCH-DONE >> $OUT
