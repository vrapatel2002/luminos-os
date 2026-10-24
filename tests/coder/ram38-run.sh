#!/usr/bin/env bash
# [CHANGE: claude-code | 2026-10-24] Does a bigger Qwen3.8-27B quant fit now (DECISION 157 follow-up)?
# For each GGUF: Dynamic Boost on, bench-run.sh with the gateway's exact reviewer args, a 2 s RAM sampler
# (MemAvailable / Mlocked / swap used / zram), OOM check in the kernel log, then Dynamic Boost off + masked.
# usage: ram38-run.sh <gguf> [<gguf>…]   results → ~/.local/state/luminos/coder/ram38-*.txt + bench-results.jsonl
set -u
M=~/.local/share/luminos/models/coder
S=~/.local/state/luminos/coder; mkdir -p $S
for G in "$@"; do
  L=ram38-${G%.gguf}; OUT=$S/$L.txt; : > $OUT
  echo "== $G $(date +%T)" >> $OUT
  sudo -n systemctl unmask nvidia-powerd && sudo -n systemctl start nvidia-powerd
  ( while :; do awk -v t="$(date +%T)" '/MemAvailable/{a=$2}/Mlocked/{m=$2}/SwapTotal/{st=$2}/SwapFree/{sf=$2}
      END{printf "%s avail=%dMB mlocked=%dMB swap_used=%dMB\n",t,a/1024,m/1024,(st-sf)/1024}' /proc/meminfo >> $OUT; sleep 2; done ) &
  SAMP=$!
  K0=$(journalctl -k -b --no-pager | grep -ciE 'out of memory|oom-kill|earlyoom')
  T0=$(date +%s)
  ~/luminos-os/tests/coder/bench-run.sh $L 2000 128 -- -m $M/$G -c 32768 -ctk q8_0 -ctv q8_0 -np 1 -b 2048 -ub 2048 \
     -fitt 256 -lm mlock --spec-type draft-mtp --spec-draft-n-max 2 --presence-penalty 1.5
  echo "wall $(( $(date +%s) - T0 )) s" >> $OUT
  kill $SAMP
  K1=$(journalctl -k -b --no-pager | grep -ciE 'out of memory|oom-kill|earlyoom')
  echo "kernel OOM lines: before=$K0 after=$K1" >> $OUT
  journalctl -u earlyoom -b --no-pager --since "@$T0" | grep -iE 'kill|sending' | tail -5 >> $OUT
  grep -E 'model buffer size|offloaded|failed|error|mlock' $S/bench-$L.log | head -12 >> $OUT
  tail -1 $S/bench-results.jsonl >> $OUT
  sudo -n systemctl stop nvidia-powerd; sudo -n systemctl mask nvidia-powerd
  echo "== done $(date +%T)" >> $OUT
  sleep 20   # let the page cache settle before the next one
done
