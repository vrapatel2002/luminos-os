#!/bin/bash
# [CHANGE: claude-code | 2026-10-24] real-machine check of the reaper's Wine guards (DECISION 160 follow-up).
# 1) fresh prefix (wineboot -i = first-run setup) must not be killed while it builds;
# 2) a program exits, only Wine services remain = "launcher gap": must survive ≥ 55 s, then be reaped.
# Uses a throwaway prefix under /tmp; prints a timeline to $OUT.
OUT=${OUT:-$HOME/.local/state/luminos/ram-reaper-winegap.txt}
PFX=/tmp/lrgap-wine/pfx; rm -rf /tmp/lrgap-wine; mkdir -p /tmp/lrgap-wine
export WINEPREFIX=$PFX WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="   # no mono/gecko prompts
t0=$(date +%s); log(){ echo "$(( $(date +%s) - t0 ))s $*" | tee -a "$OUT"; }
: > "$OUT"
cnt(){ local n=0; for p in $(pgrep -u "$USER" -f 'wine|\.exe'); do tr '\0' '\n' </proc/$p/environ 2>/dev/null | grep -qx "WINEPREFIX=$PFX" && n=$((n+1)); done; echo $n; }
# PERSIST=1: keep wineserver alive on purpose (wineserver -p), so Wine does NOT close the empty prefix by
# itself — the only case where the reaper's wine-no-app rule matters.
[ "${PERSIST:-0}" = 1 ] && { wineserver -p; log "wineserver -p (persistent)"; }
log "wineboot -i start"
wineboot -i >/dev/null 2>&1; rc=$?
log "wineboot -i done rc=$rc, prefix procs=$(cnt)"
log "launcher: wine cmd /c exit"
wine cmd /c exit >/dev/null 2>&1
log "launcher exited, prefix procs=$(cnt) (wineserver + services only)"
gap0=$(date +%s); gone=""
for i in $(seq 1 40); do
  sleep 5; n=$(cnt)
  log "gap +$(( $(date +%s) - gap0 ))s procs=$n"
  if [ "$n" = 0 ]; then gone=$(( $(date +%s) - gap0 )); break; fi
done
log "RESULT prefix gone ${gone:-never} s after the launcher exited"
grep -a 'lrgap-wine' "$HOME/.local/state/luminos/ram-reaper.log" | tail -3 | cut -c1-260 | tee -a "$OUT"
WINEPREFIX=$PFX wineserver -k 2>/dev/null; rm -rf /tmp/lrgap-wine
