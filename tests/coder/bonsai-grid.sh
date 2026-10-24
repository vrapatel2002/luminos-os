#!/bin/bash
# [CHANGE: claude-code | 2026-10-24] how many Bonsai layers fit on the 6 GB RTX 4050, and what each costs in t/s.
S=~/.local/state/luminos/coder; OUT=$S/bonsai-grid.txt; : > $OUT
B=~/.local/share/luminos/llama-prism/src/build/bin/llama-server; M=~/.local/share/luminos/models/bonsai/Ternary-Bonsai-2-27B-PTQ1_0.gguf
sudo -n systemctl unmask nvidia-powerd && sudo -n systemctl start nvidia-powerd
run(){ # label, args…
  L=$1; shift
  /usr/local/bin/dgpu-exec-v2 -- $B -m $M -np 1 -fa on --port 8093 --host 127.0.0.1 --jinja --no-ui -t 8 \
     --presence-penalty 0.0 --temp 1.0 --top-k 20 --top-p 0.95 --min-p 0.05 "$@" > $S/grid-$L.log 2>&1 &
  P=$!
  for i in $(seq 120); do curl -fs 127.0.0.1:8093/health >/dev/null 2>&1 && break; kill -0 $P 2>/dev/null || break; sleep 1; done
  OFF=$(grep -ao 'offloaded [0-9]*/[0-9]* layers' $S/grid-$L.log)
  R=$(python3 ~/luminos-os/tests/coder/bench.py 8093 2000 128 2>&1 | tr -d '\n')
  echo "$L | $OFF | $R" >> $OUT
  kill $P; wait $P 2>/dev/null; sleep 2
}
run c8k-q4-fitt64-ub512   -c 8192  -ctk q4_0 -ctv q4_0 -fitt 64 -ub 512
run c16k-q4-fitt64-ub512  -c 16384 -ctk q4_0 -ctv q4_0 -fitt 64 -ub 512
run c32k-q4-fitt64-ub512  -c 32768 -ctk q4_0 -ctv q4_0 -fitt 64 -ub 512
run c16k-q8-fitt64-ub512  -c 16384 -ctk q8_0 -ctv q8_0 -fitt 64 -ub 512
sudo -n systemctl stop nvidia-powerd; sudo -n systemctl mask nvidia-powerd
echo GRID-DONE >> $OUT
