#!/usr/bin/env bash
# [CHANGE: claude-code | 2026-10-24] Reviewer quality by quant (DECISION 157 follow-up).
# Same start as every earlier arm (runA-v0, 91/107), same grounded cross-review + Qwen3.6 fix (proof.py --arms
# cross), only the reviewer GGUF changes, via a gateway drop-in. Baseline: Q2_K_XL runD cross = 95/107.
# usage: quant-compare.sh <tag>=<gguf> …      log → ~/.local/state/luminos/coder/quant-compare.log
set -u
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
S=~/.local/state/luminos/coder; LOG=$S/quant-compare.log
INIT=$S/proof/runA-v0-7ecwu1c_
D=~/.config/systemd/user/luminos-coder-gateway.service.d; mkdir -p $D
HERE=$(dirname "$(readlink -f "$0")")
for pair in "$@"; do
  tag=${pair%%=*}; gguf=${pair#*=}
  echo "== $tag $gguf start $(date +%T)" >> $LOG
  printf '[Service]\nEnvironment=CODER_REVIEWER_GGUF=%s\n' "$gguf" > $D/reviewer-quant.conf
  systemctl --user daemon-reload && systemctl --user restart luminos-coder-gateway
  ( while :; do awk -v t="$(date +%T)" '/MemAvailable/{a=$2}/Mlocked/{m=$2}/SwapTotal/{st=$2}/SwapFree/{sf=$2}
      END{printf "%s avail=%d mlocked=%d swap=%d\n",t,a/1024,m/1024,(st-sf)/1024}' /proc/meminfo >> $S/quant-compare-ram-$tag.txt; sleep 5; done ) &
  SAMP=$!
  ~/.pyenv/shims/python3 $HERE/proof.py "q-$tag" --init-from "$INIT" --arms cross >> $LOG 2>&1
  echo "rc=$? end $(date +%T)" >> $LOG
  kill $SAMP
  awk '{split($2,a,"=");split($4,s,"=");if(min==""||a[2]+0<min)min=a[2]+0;if(s[2]+0>mx)mx=s[2]+0}END{print "min avail",min,"MB, max swap",mx,"MB"}' \
      $S/quant-compare-ram-$tag.txt >> $LOG
  journalctl -k -b --no-pager | grep -ciE 'oom-kill' | sed 's/^/kernel oom-kill lines this boot: /' >> $LOG
done
rm -f $D/reviewer-quant.conf; systemctl --user daemon-reload
systemctl --user stop luminos-coder-gateway      # stop = model unloaded, nvidia-powerd stopped + masked
echo "QUANT-COMPARE-DONE $(date +%T)" >> $LOG
