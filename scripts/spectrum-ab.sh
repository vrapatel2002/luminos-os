#!/usr/bin/env bash
# [CHANGE: claude-code | 2026-10-15] spectrum
# spectrum-ab.sh — run ONE arm of the live A/B (docs/spectrum/DESIGN.md §6) and write
# docs/spectrum/ab/<arm>-<timestamp>/{samples.csv,load-*.json,wmi_hist.txt,trace.txt,summary.txt,summary.json}.
#   sudo scripts/spectrum-ab.sh <arm> [--quick] [--compare <other-arm-dir>] [--load <load-binary>]
# It never changes a power setting. It only arms tracefs kprobes, and removes them on exit (trap EXIT INT TERM).
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
ARM=""; Q=1; CMP=""; LOAD=""
while (( $# )); do case "$1" in
    --quick) Q=0.25;; --compare) CMP=${2:-}; shift;; --load) LOAD=${2:-}; shift;;
    -h|--help) sed -n '3,6p' "$0"; exit 0;; -*) echo "unknown flag $1" >&2; exit 2;; *) ARM=$1;; esac; shift; done
[[ -n $ARM ]] || { echo "usage: sudo $0 <arm: A|B|C|...> [--quick] [--compare DIR] [--load BIN]" >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo "spectrum-ab.sh: must run as root (sudo) — RAPL energy_uj and tracefs are root-only" >&2; exit 1; }
[[ -z $CMP || -f $CMP/summary.json ]] || { echo "--compare: $CMP/summary.json not found" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 is required (socket query + summary)" >&2; exit 1; }

OUT=$REPO/docs/spectrum/ab/$ARM-$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT" || exit 1
T=/sys/kernel/tracing; [[ -d $T/events ]] || T=/sys/kernel/debug/tracing
INST=$T/instances/spectrum_ab
RAPL=/sys/class/powercap/intel-rapl:0; PPT=/sys/devices/platform/asus-nb-wmi
DGPU=/sys/bus/pci/devices/0000:01:00.0/power/runtime_status
SOCK=/run/luminos/power.sock
hw() { local h; for h in /sys/class/hwmon/hwmon*; do [[ $(cat "$h/name" 2>/dev/null) == "$1" ]] && { echo "$h"; return; }; done; }
K10=$(hw k10temp); ASUS=$(hw asus)
[[ -n $K10 && -r $RAPL/energy_uj ]] || { echo "k10temp hwmon or RAPL energy_uj missing" >&2; exit 1; }
dur() { awk -v d="$1" -v q="$Q" 'BEGIN{v=int(d*q+0.5); print (v<2?2:v)}'; }

# ---- load tool ----
if [[ -z $LOAD ]]; then
    BUILD=$(mktemp -d); chown "${SUDO_USER:-root}" "$BUILD"
    ( cd "$REPO" && sudo -H -u "${SUDO_USER:-root}" go build -o "$BUILD/load" ./tests/spectrum/load ) \
        || { echo "go build of tests/spectrum/load failed; pass --load <binary>" >&2; exit 1; }
    LOAD=$BUILD/load
fi
[[ -x $LOAD ]] || { echo "load binary $LOAD not executable" >&2; exit 1; }

# ---- kprobes (BUG-198 probes): armed now, always removed on exit ----
probes_off() {
    [[ -d $INST ]] && {
        echo '!hist:keys=method,devid:vals=hitcount:sort=hitcount.descending:size=1024' \
            > "$INST/events/spectrum_ab/wmi/trigger" 2>/dev/null
        echo 0 > "$INST/events/rpm/rpm_resume/enable" 2>/dev/null; echo 0 > "$INST/events/rpm/rpm_resume/filter" 2>/dev/null
        echo 0 > "$INST/events/spectrum_ab/notify/enable" 2>/dev/null
        rmdir "$INST" 2>/dev/null || echo "WARN: could not rmdir $INST" >&2; }
    echo '-:spectrum_ab/wmi' >> "$T/kprobe_events" 2>/dev/null
    echo '-:spectrum_ab/notify' >> "$T/kprobe_events" 2>/dev/null
    grep -q spectrum_ab "$T/kprobe_events" 2>/dev/null && echo "WARN: spectrum_ab kprobes still present in $T/kprobe_events" >&2
}
SPID=""; LPID=""
cleanup() {
    trap - EXIT INT TERM
    [[ -n $LPID ]] && kill "$LPID" 2>/dev/null; [[ -n $SPID ]] && kill "$SPID" 2>/dev/null; wait 2>/dev/null
    if [[ -d $INST ]]; then
        cat "$INST/events/spectrum_ab/wmi/hist" > "$OUT/wmi_hist.txt" 2>/dev/null
        cat "$INST/trace" > "$OUT/trace.txt" 2>/dev/null
    fi
    probes_off; echo "kprobes removed."
    [[ -n ${SUDO_USER:-} ]] && chown -R "$SUDO_USER" "$OUT"
}
probes_off   # clear leftovers from a crashed earlier run
trap cleanup EXIT; trap 'echo interrupted; exit 130' INT TERM
echo 'p:spectrum_ab/wmi asus_wmi_evaluate_method3 method=%di:x32 devid=%si:x32' >> "$T/kprobe_events" \
    || { echo "kprobe on asus_wmi_evaluate_method3 failed" >&2; exit 1; }
echo 'p:spectrum_ab/notify acpi_ev_queue_notify_request value=%si:x32' >> "$T/kprobe_events" \
    || { echo "kprobe on acpi_ev_queue_notify_request failed" >&2; exit 1; }
mkdir "$INST" || exit 1
echo 16384 > "$INST/buffer_size_kb"
echo 'name == "0000:01:00.0"' > "$INST/events/rpm/rpm_resume/filter" && echo 1 > "$INST/events/rpm/rpm_resume/enable" || exit 1
echo 1 > "$INST/events/spectrum_ab/notify/enable" || exit 1
echo 'hist:keys=method,devid:vals=hitcount:sort=hitcount.descending:size=1024' > "$INST/events/spectrum_ab/wmi/trigger" || exit 1

# ---- 1 Hz sampler ----
STAGE=$OUT/.stage; echo setup > "$STAGE"
sockq() {   # level,ppt_w,pmax_w,binding,wmi_writes_total from the daemon's status reply (blank if absent)
    python3 -I - "$SOCK" <<'PY' 2>/dev/null || echo ",,,,"
import json, socket, sys
s = socket.socket(socket.AF_UNIX); s.settimeout(0.5); s.connect(sys.argv[1])
s.sendall(b'{"type":"status"}\n'); buf = b""
while not buf.endswith(b"\n"):
    c = s.recv(65536)
    if not c: break
    buf += c
p = json.loads(buf).get("payload", {})
print(",".join(str(p.get(k, "")) for k in ("level", "ppt_w", "pmax_w", "binding", "wmi_writes_total")))
PY
}
sampler() {
    local e0 t0 e1 t1 w maxe i=0 f1="" f2="" f3=""
    maxe=$(cat "$RAPL/max_energy_range_uj"); e0=$(cat "$RAPL/energy_uj"); t0=$(date +%s.%N)
    echo "ts,stage,tctl_c,pkg_w,ppt_pl1,ppt_pl2,ppt_fppt,dgpu,level,ppt_w,pmax_w,binding,wmi_writes_total,fan1,fan2,fan3"
    while :; do
        sleep "$(date +%N | awk '{printf "%.3f", 1 - $1/1e9}')"
        e1=$(cat "$RAPL/energy_uj"); t1=$(date +%s.%N)
        w=$(awk -v a="$e0" -v b="$e1" -v m="$maxe" -v x="$t0" -v y="$t1" 'BEGIN{d=b-a; if(d<0)d+=m; printf "%.2f", d/1e6/(y-x)}')
        e0=$e1; t0=$t1
        if (( i % 5 == 0 )) && [[ -n $ASUS ]]; then   # each rpm read is a BIOS call (HARDWARE Q5): every 5 s only
            f1=$(cat "$ASUS/fan1_input" 2>/dev/null); f2=$(cat "$ASUS/fan2_input" 2>/dev/null); f3=$(cat "$ASUS/fan3_input" 2>/dev/null)
        else f1=""; f2=""; f3=""; fi
        echo "${t1%.*},$(cat "$STAGE"),$(awk '{printf "%.1f", $1/1000}' "$K10/temp1_input"),$w,$(cat "$PPT/ppt_pl1_spl" 2>/dev/null),$(cat "$PPT/ppt_pl2_sppt" 2>/dev/null),$(cat "$PPT/ppt_fppt" 2>/dev/null),$(cat "$DGPU" 2>/dev/null),$(sockq),$f1,$f2,$f3"
        i=$((i + 1))
    done
}
sampler > "$OUT/samples.csv" & SPID=$!

# ---- ladder (DESIGN §6) ----
stage() {   # stage <name> <seconds> [threads]
    local s; s=$(dur "$2"); echo "$1" > "$STAGE"
    echo "$(date +%s) $(date '+%T') stage $1 ${s}s ${3:+threads=$3}" | tee -a "$OUT/stages.log"
    if [[ -n ${3:-} ]]; then "$LOAD" -threads "$3" -duty 100 -seconds "$s" -json > "$OUT/load-$1.json" & LPID=$!; wait "$LPID"; LPID=""
    else sleep "$s"; fi
}
START=$(date '+%F %T'); echo "arm=$ARM quick=$Q out=$OUT start=$START" | tee "$OUT/stages.log"
stage idle1 300; stage cpu4 120 4; stage cpu8 120 8; stage cpu16 300 16; stage idle2 300
for i in 1 2 3; do stage "burst16_$i" 10 16; stage "gap16_$i" 90; done
for i in 1 2 3; do stage "burst1_$i" 10 1; stage "gap1_$i" 90; done
stage sus16 120 16; echo done > "$STAGE"; sleep 2
kill "$SPID" 2>/dev/null; wait "$SPID" 2>/dev/null; SPID=""
cat "$INST/events/spectrum_ab/wmi/hist" > "$OUT/wmi_hist.txt"; cat "$INST/trace" > "$OUT/trace.txt"
journalctl -u luminos-power --since "$START" --no-pager > "$OUT/journal.txt" 2>/dev/null

# ---- summary ----
python3 -I - "$OUT" "$Q" "$CMP" <<'PY' | tee "$OUT/summary.txt"
import csv, json, re, statistics as st, sys, os
out, q, cmp = sys.argv[1], float(sys.argv[2]), sys.argv[3]
rows = list(csv.DictReader(open(f"{out}/samples.csv")))
def f(r, k):
    try: return float(r.get(k))
    except (TypeError, ValueError): return None
def col(st_, k, last=None):
    rs = [r for r in rows if r["stage"] == st_]; rs = rs[-last:] if last else rs
    return [v for v in (f(r, k) for r in rs) if v is not None]
med = lambda v: round(st.median(v), 2) if v else None
mean = lambda v: round(st.mean(v), 2) if v else None
S, checks = {"stages": {}, "ops": {}}, []
def chk(name, ok, detail): checks.append((name, "n/a" if ok is None else ("PASS" if ok else "FAIL"), detail))
stages = list(dict.fromkeys(r["stage"] for r in rows if r["stage"] not in ("setup", "done")))
print(f"{'stage':10} {'n':>4} {'Tctl med/mean':>14} {'pkgW med/mean':>14} {'fan1 med':>8} {'ppt_w med':>9} {'ops/s':>12}")
for s in stages:
    d = dict(n=len(col(s, "tctl_c")), tctl_med=med(col(s, "tctl_c")), tctl_mean=mean(col(s, "tctl_c")),
             pkg_med=med(col(s, "pkg_w")), pkg_mean=mean(col(s, "pkg_w")), fan_med=med(col(s, "fan1")), ppt_med=med(col(s, "ppt_w")))
    try: d["ops"] = json.load(open(f"{out}/load-{s}.json"))["ops_per_s"]
    except Exception: d["ops"] = None
    S["stages"][s] = d
    print(f"{s:10} {d['n']:>4} {str(d['tctl_med'])+'/'+str(d['tctl_mean']):>14} {str(d['pkg_med'])+'/'+str(d['pkg_mean']):>14} {str(d['fan_med']):>8} {str(d['ppt_med']):>9} {str(d['ops']):>12}")
for k in ("burst16", "burst1"):
    S["ops"][k] = med([S["stages"][f"{k}_{i}"]["ops"] for i in (1, 2, 3) if S["stages"].get(f"{k}_{i}", {}).get("ops")])
for k in ("cpu16", "sus16"): S["ops"][k] = S["stages"].get(k, {}).get("ops")
w = lambda n: max(2, int(n * q + 0.5))
S["idle_w"] = med(col("idle1", "pkg_w", w(180)) + col("idle2", "pkg_w", w(180)))
idle_t = med(col("idle1", "tctl_c", w(180)) + col("idle2", "tctl_c", w(180))); idle_f = med(col("idle1", "fan1", w(180)) + col("idle2", "fan1", w(180)))
hot = col("cpu16", "tctl_c", w(60)); S["mid"] = {s: [S["stages"].get(s, {}).get(k) for k in ("tctl_mean", "fan_med")] for s in ("cpu4", "cpu8")}
trace = open(f"{out}/trace.txt").read() if os.path.exists(f"{out}/trace.txt") else ""
wakes = len(re.findall(r"rpm_resume:", trace)); notes = re.findall(r"notify: .*value=(0x[0-9a-f]+)", trace)
wmi = re.findall(r"method:\s*(0x[0-9a-f]+|\d+),?\s+devid:\s*(0x[0-9a-f]+|\d+)\s*}\s*hitcount:\s*(\d+)", open(f"{out}/wmi_hist.txt").read() if os.path.exists(f"{out}/wmi_hist.txt") else "")
hours = max(len(rows), 1) / 3600; names = {0x53564544: "DEVS", 0x53545344: "DSTS"}
print(f"\ndGPU rpm_resume (0000:01:00.0): {wakes}\nACPI notifies: {len(notes)} {dict((v, notes.count(v)) for v in set(notes))}\nWMI calls by method/devid:")
devs = forb = 0
for m, d, c in wmi:
    m, d, c = int(m, 0), int(d, 0), int(c); print(f"  {names.get(m, hex(m))} devid=0x{d:08x} {c}")
    if names.get(m) == "DEVS": devs += c
    if d in (0x00110024, 0x00120075): forb += c
print("  (DSTS reads include this script's own fan rpm polls every 5 s)")
pp = [(f(r, "ts"), f(r, "ppt_w")) for r in rows]   # W/s per 1 s sample; skips gaps (missing ts/ppt)
dp = [(b - a) / (tb - ta) for (ta, a), (tb, b) in zip(pp, pp[1:]) if None not in (ta, a, tb, b) and tb > ta]
st_t0 = {}   # stage start = unix time the stage line was logged (stages.log), else first sample in it
for ln in open(f"{out}/stages.log") if os.path.exists(f"{out}/stages.log") else []:
    m = re.match(r"(\d+) \S+ stage (\S+)", ln)
    if m: st_t0[m.group(2)] = float(m.group(1))
def step_s(s):   # seconds from stage start to the first sample with socket ppt_w >= 0.9 * socket pmax_w
    rs = [r for r in rows if r["stage"] == s and f(r, "ts") is not None]
    if not rs: return None
    t0 = st_t0.get(s, f(rs[0], "ts") - 1)
    for r in rs:
        if f(r, "ppt_w") is not None and f(r, "pmax_w") and f(r, "ppt_w") >= 0.9 * f(r, "pmax_w"): return f(r, "ts") - t0
    return float("inf") if any(f(r, "pmax_w") for r in rs) else None   # inf = never reached; None = no socket fields (A/C)
jr = open(f"{out}/journal.txt").read() if os.path.exists(f"{out}/journal.txt") else ""
chk("dGPU wakes == 0", wakes == 0, wakes)
chk("WMI DEVS/h <= 1500", devs / hours <= 1500, f"{devs / hours:.0f}/h")
chk("0 fan-curve/profile WMI calls", forb == 0, forb)
chk("idle Tctl <= 55 C", None if idle_t is None else idle_t <= 55, idle_t)
chk("idle fan <= 2500 rpm", None if idle_f is None else idle_f <= 2500, idle_f)
f55 = [f(r, "fan1") for r in rows if f(r, "fan1") is not None and 50 <= f(r, "tctl_c") <= 55]
chk("max fan at 50-55 C <= 2800 rpm (assumes full=7000)", max(f55) <= 2800 if f55 else None, max(f55) if f55 else None)
chk("cpu16 last 60 s Tctl mean <= 90", mean(hot) <= 90 if hot else None, mean(hot))
chk("cpu16 last 60 s Tctl peak <= 93", max(hot) <= 93 if hot else None, max(hot) if hot else None)
for s in ("cpu16", "sus16"): v = step_s(s); chk(f"{s} load-step to 0.9*pmax <= 8 s", None if v is None else v <= 8, v)
chk("ppt_w max rise <= 6 W/s", max(dp) <= 6 if dp else None, max(dp) if dp else None)
chk("ppt_w max fall <= 12 W/s", -min(dp) <= 12 if dp else None, -min(dp) if dp else None)
bad = len(re.findall(r"beast mode|thermal zone|thermal burst|idle → Quiet|burst fan curve", jr, re.I))
chk("journal free of old phase strings (beast mode|thermal zone|thermal burst|idle → Quiet|burst fan curve)", bad == 0 if jr else None, bad)
if cmp:
    o = json.load(open(f"{cmp}/summary.json")); r = lambda a, b: None if a is None or b is None else a / b
    chk("idle W <= other + 0.5", None if S["idle_w"] is None or o["idle_w"] is None else S["idle_w"] <= o["idle_w"] + 0.5, (S["idle_w"], o["idle_w"]))
    for k, t in (("cpu16", .95), ("sus16", .95), ("burst16", .90), ("burst1", 1.0)):
        x = r(S["ops"][k], o["ops"].get(k)); chk(f"{k} ops >= {t} x other", None if x is None else x >= t, x and round(x, 3))
    for s in ("cpu4", "cpu8"):
        a, b = S["mid"][s], o["mid"][s]
        chk(f"{s} Tctl <= other + 5", None if None in (a[0], b[0]) else a[0] <= b[0] + 5, (a[0], b[0]))
        chk(f"{s} fan <= other", None if None in (a[1], b[1]) else a[1] <= b[1], (a[1], b[1]))
print("\nDESIGN §6 thresholds:"); [print(f"  {v:4}  {n}  [{d}]") for n, v, d in checks]
json.dump(S, open(f"{out}/summary.json", "w"), indent=1)
PY
cat <<'TXT'

MANUAL event tests (not automated — DESIGN §6), run with probes of your own or a second short arm:
  [ ] suspend 2 min + resume; then 30 s of 16 threads: journal shows re-assert, package W <= ppt_w + 3
  [ ] ROG key profile cycle under 16-thread load: 're-asserted' within 2 s, W back under ppt_w + 3 within 5 s
  [ ] systemctl restart luminos-power x3: 0 rpm_resume, recovery <= 5 s
  [ ] unplug / replug the charger twice: 0 rpm_resume, no profile change
  [ ] kill -STOP the daemon 30 s (B only): watchdog restart <= 15 s;  kill -9: recovery <= 5 s
  [ ] systemctl stop, then 30 s of 16 threads: package W >= 38 (not left slow)
TXT
echo "results: $OUT"
