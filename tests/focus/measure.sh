#!/usr/bin/env bash
# measure.sh LABEL [SECONDS] — one A/B sample for luminos-focus. [CHANGE: claude-code | 2026-11-07]
# Prints: package power (RAPL), iGPU busy, VCN load, PSR state, CPU% (of one core) per app cgroup and top processes.
# Needs passwordless sudo for RAPL + debugfs. Output is one block per run, grep-friendly (key=value).
set -u
L=${1:?label}; T=${2:-20}
RAPL=/sys/class/powercap/intel-rapl:0/energy_uj
DBG=/sys/kernel/debug/dri/0000:65:00.0
CG=/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service
HZ=$(getconf CLK_TCK)
snap_cg(){ for f in "$CG"/app.slice/*/cpu.stat "$CG"/session.slice/*/cpu.stat; do
  [ -f "$f" ] || continue; n=${f%/cpu.stat}; echo "${n##*/} $(awk '/^usage_usec/{print $2}' "$f")"; done; }
snap_pid(){ for p in /proc/[0-9]*; do [ -r $p/stat ] || continue
  awk -v p=${p#/proc/} '{s=$0; sub(/^[^)]*\) /,"",s); split(s,a," "); print p, a[12]+a[13]}' $p/stat 2>/dev/null; done; }
e0=$(sudo cat $RAPL); c0=$(snap_cg); p0=$(snap_pid); t0=$(date +%s.%N)
gb=0; vc=0; psr=""; n=0
end=$(( $(date +%s) + T ))
while [ "$(date +%s)" -lt "$end" ]; do
  gb=$(( gb + $(cat /sys/class/drm/card2/device/gpu_busy_percent) ))
  vc=$(( vc + $(sudo awk '/^VCN Load/{print $3}' $DBG/amdgpu_pm_info) ))
  psr="$psr$(sudo cat $DBG/eDP-2/psr_state 2>/dev/null)"; n=$((n+1)); sleep 1
done
e1=$(sudo cat $RAPL); c1=$(snap_cg); p1=$(snap_pid); t1=$(date +%s.%N)
dt=$(echo "$t1 - $t0" | bc -l)
echo "== $L  ($(date +%T), ${dt%.*}s, ac=$(cat /sys/class/power_supply/ACAD/online))"
echo "pkg_mW=$(( (e1-e0) / ${dt%.*} / 1000 )) igpu_busy=$((gb/n))% vcn=$((vc/n))% psr_states=$psr"
LC_ALL=C join <(echo "$c0"|LC_ALL=C sort) <(echo "$c1"|LC_ALL=C sort) | awk -v dt=$dt '{c=($3-$2)/dt/10000; if(c>=0.3) printf "cg %-60s %5.1f%%\n",$1,c}' | sort -k3 -rn
LC_ALL=C join <(echo "$p0"|LC_ALL=C sort) <(echo "$p1"|LC_ALL=C sort) | awk -v dt=$dt -v hz=$HZ '{c=($3-$2)/hz/dt*100; if(c>=0.5) print $1, c}' | sort -k2 -rn | head -10 |
 while read pid c; do printf "pid %-7s %5.1f%% %s\n" $pid $c "$(tr '\0' ' ' </proc/$pid/cmdline 2>/dev/null | cut -c1-70 | sed 's/--crashpad.*//')"; done
