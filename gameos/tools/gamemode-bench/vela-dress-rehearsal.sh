#!/usr/bin/env bash
# VELA dress rehearsal — measure the gaming-OS memory profile WITHOUT building the OS.
# [CHANGE: claude-code | 2026-09-20]
#
# Stops the desktop, clears swap, runs the SAME Lutris game inside `cage`
# (minimal kiosk Wayland compositor), logs everything, restores the desktop.
#
# ONLY ONE VARIABLE CHANGES vs the 2026-09-20 baseline: the desktop is gone.
# Swap architecture, game settings, driver, kernel all identical on purpose.
#
# >>> RUN THIS FROM A REAL TTY (Ctrl+Alt+F3), NOT from a desktop terminal. <<<
# Stopping sddm kills any terminal running inside the desktop, and this script with it.
#
# Baseline to beat (2026-09-20, full desktop):
#   allocstall total 18,143   pswpout 4,232,545   53.6 avg fps / 37.9 1% low
set -uo pipefail

GAME_ID=4
OUT=${HOME}/vela-rehearsal-$(date +%Y%m%d-%H%M%S)
MAXMIN=20
mkdir -p "$OUT"
log(){ printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/run.log"; }

if [ -z "${XDG_VTNR:-}" ] || [ "${XDG_VTNR:-0}" -lt 2 ]; then
  echo "!! Run this from a TTY (Ctrl+Alt+F3), not inside the desktop." >&2
  echo "   XDG_VTNR=${XDG_VTNR:-unset}" >&2
  read -rp "   Continue anyway? [y/N] " a; [ "$a" = y ] || exit 1
fi

DESKTOP_WAS_UP=0
systemctl is-active --quiet sddm && DESKTOP_WAS_UP=1

restore() {
  log "=== RESTORING ==="
  # re-enable any swap device that is no longer active (defensive; nothing should
  # disable swap any more, but losing the user's swapfile once was enough)
  if [ -f "$OUT/swap-devices.txt" ]; then
    while read -r dev _; do
      [ -n "$dev" ] || continue
      if ! swapon --show --noheadings --raw 2>/dev/null | grep -q "^$dev "; then
        log "swap device $dev is missing - re-enabling"
        sudo -n swapon "$dev" 2>/dev/null || log "  FAILED to re-enable $dev - run: sudo luminos-pagefile"
      fi
    done < "$OUT/swap-devices.txt"
  fi
  [ "$DESKTOP_WAS_UP" = 1 ] && sudo -n systemctl start sddm
  log "done. results in $OUT"
}
trap restore EXIT INT TERM

counters() {  # $1 = label
  { echo "--- $1  $(date -Is)"
    grep -E '^(allocstall_|pgscan_direct|pgsteal_direct|pswpin|pswpout|pgmajfault)' /proc/vmstat
    echo "--- meminfo"; grep -E '^(MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree|Cached|AnonPages)' /proc/meminfo
  } >> "$OUT/counters.txt"
}

log "=== VELA DRESS REHEARSAL ==="
log "output: $OUT"
counters BOOT_STATE
free -m | tee -a "$OUT/run.log"

log "stopping any running game + the desktop..."
pkill -f b1-Win64-Shipping 2>/dev/null; pkill -f umu-run 2>/dev/null; sleep 3
systemctl --user stop bmw-bench.service 2>/dev/null
sudo -n systemctl stop sddm
sleep 8
log "desktop stopped. memory now:"; free -m | tee -a "$OUT/run.log"

# [FIX 2026-09-20] The first run used `swapoff -a; swapon -a` and PERMANENTLY DROPPED
# /swapfile.luminos, because that file is enabled by /usr/local/bin/luminos-pagefile and
# is NOT in /etc/fstab - so `swapon -a` had nothing to restore it from. The machine ran
# the whole test on zram alone (8G instead of 41G), which made it MORE memory-constrained
# than the baseline and invalidated the comparison. Never clear swap blindly again.
#
# Swap is now left ALONE. The vmstat counters are deltas, so a non-empty starting swap
# does not invalidate anything - and leaving it intact keeps the test to ONE variable.
log "recording swap layout (NOT clearing it - see FIX note above)"
swapon --show --noheadings --raw > "$OUT/swap-devices.txt" 2>/dev/null
cat "$OUT/swap-devices.txt" | tee -a "$OUT/run.log"

free -m | tee -a "$OUT/run.log"
counters T0_BEFORE_GAME

cat > "$OUT/mangohud.conf" <<EOF
fps
frametime
frame_timing=1
gpu_stats
gpu_temp
gpu_power
gpu_core_clock
vram
ram
swap
cpu_stats
cpu_temp
resolution
pci_dev=0000:01:00.0
output_folder=$OUT
log_interval=100
autostart_log=45
log_duration=240
toggle_logging=Shift_L+F2
position=top-left
EOF

# background sampler: dGPU + memory, every 2s
( while :; do
    printf '%s,%s,%s\n' "$(date +%s)" \
      "$(dgpu-exec-v2 nvidia-smi --query-gpu=memory.used,utilization.gpu,clocks.gr,temperature.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null|tr -d ' ')" \
      "$(free -m|awk '/^Mem:/{printf "%s/%s",$3,$7}/^Swap:/{printf "/%s",$3}')"
    sleep 2
  done > "$OUT/sampler.csv" ) &
SAMP=$!

log "launching game inside cage (no desktop). Play the SAME scene as the baseline."
log "Logging auto-starts 45s in, runs 4 minutes. Quit the game normally when done."
export MANGOHUD=1 MANGOHUD_CONFIGFILE="$OUT/mangohud.conf" XDG_RUNTIME_DIR=/run/user/$(id -u)
timeout "${MAXMIN}m" cage -- lutris lutris:rungameid/$GAME_ID >> "$OUT/cage.log" 2>&1
RC=$?
log "session ended (rc=$RC)"

kill $SAMP 2>/dev/null
counters T1_AFTER_GAME

python3 - "$OUT" <<'PY' | tee -a "$OUT/RESULTS.txt"
import sys,re,os,glob,csv
d=sys.argv[1]
txt=open(f"{d}/counters.txt").read()
def block(tag):
    m=re.search(rf"--- {tag}.*?\n(.*?)(?=--- [A-Z]|\Z)", txt, re.S)
    return dict(l.split()[:2] for l in m.group(1).splitlines() if len(l.split())==2) if m else {}
a,b=block("T0_BEFORE_GAME"),block("T1_AFTER_GAME")
def dl(k):
    try: return int(b.get(k,0))-int(a.get(k,0))
    except: return 0
stalls=sum(dl(k) for k in a if k.startswith("allocstall_"))
print("="*52); print("VELA DRESS REHEARSAL — RESULTS"); print("="*52)
print(f"  allocstall (direct reclaim) : {stalls:>12,}   baseline 18,143")
print(f"  pswpout (pages to swap)     : {dl('pswpout'):>12,}   baseline 4,232,545")
print(f"  pswpin                      : {dl('pswpin'):>12,}")
print(f"  pgscan_direct               : {dl('pgscan_direct'):>12,}")
print(f"  pgmajfault                  : {dl('pgmajfault'):>12,}")
c=sorted(glob.glob(f"{d}/*.csv"))
c=[f for f in c if 'sampler' not in f]
if c:
    rows=list(csv.reader(open(c[-1]))); hdr=None;data=[]
    for i,r in enumerate(rows):
        if r and r[0].strip()=='fps': hdr=[x.strip() for x in r]; data=rows[i+1:]; break
    if hdr:
        ix={x:i for i,x in enumerate(hdr)}
        fs=[]
        for r in data:
            try:
                e=float(r[ix['elapsed']]); e=e/1e9 if e>1e6 else e
                v=float(r[ix['fps']])
                if e>=40 and v>0: fs.append(v)
            except: pass
        if fs:
            fs.sort(); n=len(fs)
            print(f"  avg FPS                     : {sum(fs)/n:>12.1f}   baseline 53.6")
            print(f"  1% low                      : {fs[int(n*.01)]:>12.1f}   baseline 37.9")
            print(f"  min                         : {fs[0]:>12.1f}   baseline 15.4")
print("="*52)
PY
log "RESULTS written to $OUT/RESULTS.txt"
