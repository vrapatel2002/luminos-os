#!/usr/bin/env bash
# Smoothness + charger test for the spectrum power manager (run with sudo).
#   run.sh <outdir> smooth        light 20s -> 4K video 20s -> video + 7B LLM on CPU -> video 10s
#   run.sh <outdir> watch <secs>  only watch (for plug/unplug moments)
# Records: page video drops + late screen frames (page.jsonl), power/temp/PPT/dGPU (samples.csv),
# ACPI notifies + dGPU wakes + asus WMI calls (kprobes, always removed on exit). Changes no setting.
set -u
OUT=$1; MODE=$2; SECS=${3:-60}; HERE=$(cd "$(dirname "$0")" && pwd); U=${SUDO_USER:-shawn}
mkdir -p "$OUT"; : > "$OUT/page.jsonl"; chown -R "$U" "$OUT"   # server.py runs as the user and must write page.jsonl
T=/sys/kernel/tracing; INST=$T/instances/smooth
RAPL=/sys/class/powercap/intel-rapl:0; PPT=/sys/devices/platform/asus-nb-wmi
DGPU=/sys/bus/pci/devices/0000:01:00.0/power/runtime_status
hw() { local h; for h in /sys/class/hwmon/hwmon*; do [[ $(cat "$h/name" 2>/dev/null) == "$1" ]] && { echo "$h"; return; }; done; }
K10=$(hw k10temp)
probes_off() {
    [[ -d $INST ]] && { echo '!hist:keys=method,devid:vals=hitcount:sort=hitcount.descending:size=1024' > "$INST/events/smooth/wmi/trigger" 2>/dev/null
        echo 0 > "$INST/events/rpm/rpm_resume/enable"; echo 0 > "$INST/events/rpm/rpm_resume/filter"; echo 0 > "$INST/events/smooth/notify/enable"; echo 0 > "$INST/events/smooth/wmi/enable"; rmdir "$INST"; }
    echo '-:smooth/wmi' >> $T/kprobe_events 2>/dev/null; echo '-:smooth/notify' >> $T/kprobe_events 2>/dev/null
    grep -q smooth/ $T/kprobe_events && echo "WARN: kprobes left" >&2
}
PIDS=()
cleanup() {
    trap - EXIT INT TERM
    for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; pkill -u "$U" -f 'user-data-dir=/tmp/smooth-chromium' 2>/dev/null; fuser -k 18098/tcp 2>/dev/null; wait 2>/dev/null
    [[ -d $INST ]] && { cat "$INST/events/smooth/wmi/hist" > "$OUT/wmi_hist.txt"; cat "$INST/trace" > "$OUT/trace.txt"; }
    probes_off; chown -R "$U" "$OUT"; echo "kprobes removed."
}
probes_off 2>/dev/null; trap cleanup EXIT; trap 'exit 130' INT TERM
echo 'p:smooth/wmi asus_wmi_evaluate_method3 method=%di:x32 devid=%si:x32' >> $T/kprobe_events || exit 1
echo 'p:smooth/notify acpi_ev_queue_notify_request value=%si:x32' >> $T/kprobe_events || exit 1
mkdir "$INST"; echo 8192 > "$INST/buffer_size_kb"
echo 'name == "0000:01:00.0"' > "$INST/events/rpm/rpm_resume/filter"; echo 1 > "$INST/events/rpm/rpm_resume/enable"
echo 1 > "$INST/events/smooth/notify/enable"; echo 1 > "$INST/events/smooth/wmi/enable"   # who made each WMI call (comm) next to each notify
echo 'hist:keys=method,devid:vals=hitcount:sort=hitcount.descending:size=1024' > "$INST/events/smooth/wmi/trigger"
PH=$OUT/phase; echo light > "$PH"
fuser -k 18098/tcp 2>/dev/null; sleep 0.3   # a stale server from an earlier run would answer with ITS phase file
sampler() {   # 2 Hz
    local e0 t0 e1 t1 maxe; maxe=$(cat $RAPL/max_energy_range_uj); e0=$(cat $RAPL/energy_uj); t0=$(date +%s.%N)
    echo "ts,phase,ac,tctl_c,pkg_w,ppt_pl1,ppt_pl2,dgpu,mhz_max"
    while :; do sleep 0.5; e1=$(cat $RAPL/energy_uj); t1=$(date +%s.%N)
        echo "$t1,$(cat $PH),$(cat /sys/class/power_supply/ACAD/online),$(awk '{printf "%.1f",$1/1000}' $K10/temp1_input),$(awk -v a=$e0 -v b=$e1 -v m=$maxe -v x=$t0 -v y=$t1 'BEGIN{d=b-a;if(d<0)d+=m;printf "%.1f",d/1e6/(y-x)}'),$(cat $PPT/ppt_pl1_spl),$(cat $PPT/ppt_pl2_sppt),$(cat $DGPU),$(awk '/MHz/{if($4>m)m=$4}END{printf "%d",m}' /proc/cpuinfo)"
        e0=$e1; t0=$t1; done
}
sampler > "$OUT/samples.csv" & PIDS+=($!)
if [[ $MODE == watch ]]; then echo watch > "$PH"; sleep "$SECS"; exit 0; fi
E="WAYLAND_DISPLAY=wayland-0 XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1) XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus"
sudo -u "$U" python3 -I "$HERE/server.py" "$OUT/page.jsonl" "$PH" & PIDS+=($!); sleep 1
rm -rf /tmp/smooth-chromium
sudo -u "$U" env $E chromium --user-data-dir=/tmp/smooth-chromium --no-first-run --kiosk --autoplay-policy=no-user-gesture-required \
  --ozone-platform=wayland --enable-features=AcceleratedVideoDecodeLinuxGL,VaapiVideoDecoder http://127.0.0.1:18098/index.html >"$OUT/chromium.log" 2>&1 & PIDS+=($!)
for i in $(seq 30); do [[ -s $OUT/page.jsonl ]] && break; sleep 1; done; [[ -s $OUT/page.jsonl ]] || { echo "page never reported - aborting" >&2; exit 1; }
sleep 20; echo video > "$PH"; sleep 20
echo video+llm > "$PH"; sudo -u "$U" env CUDA_VISIBLE_DEVICES= python3 "$HERE/llm.py" 150 > "$OUT/llm.json" 2>"$OUT/llm.err"
echo after > "$PH"; sleep 10
