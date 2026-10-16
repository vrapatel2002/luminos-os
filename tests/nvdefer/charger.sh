#!/usr/bin/env bash
# nvdefer manual charger test — run with sudo AFTER the patched nvidia module is loaded. Needs a human:
# unplug the charger, wait, plug it back in. PASS if the sleeping dGPU is never resumed across both cable
# edges and nv_acpi_deferred rises. Changes no setting; kprobes always removed on exit.
# ---- thresholds (fixed before the first run) ----
SLEEP_WAIT=60      # GPU must be "suspended" before we start
EDGE_WAIT=600      # s allowed for the two cable edges (unplug + replug)
SETTLE=10          # s to keep watching after the second edge (asusd curve write, EC D-notifier)
MAX_WAKES=0        # rpm_resume on 0000:01:00.0 allowed
MIN_GAP=5          # s the human should wait between unplug and replug
# ---------------------------------------------------
set -u
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd); U=${SUDO_USER:-shawn}
. "$HERE/lib.sh"
AC=/sys/class/power_supply/ACAD/online
OUT=$REPO/docs/nvdefer/results/charger-$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
exec > >(tee "$OUT/log.txt") 2>&1
cleanup() {
    trap - EXIT INT TERM; [[ -n ${WP:-} ]] && kill "$WP" 2>/dev/null
    [[ -d $INST ]] && tr_save "$OUT/trace.txt"; probes_off
    table > "$OUT/table.txt"; local rc=$?; cat "$OUT/table.txt"; chown -R "$U" "$OUT"; echo "raw results: $OUT"; exit $rc
}
trap cleanup EXIT; trap 'exit 130' INT TERM

[[ -r $P/nv_acpi_defer && -r $P/nv_acpi_deferred ]] || { row "precondition" FAIL "module param files missing (patched driver not loaded?)"; exit 1; }
[[ $(par nv_acpi_defer) == 1 ]] || { row "precondition" FAIL "nv_acpi_defer=$(par nv_acpi_defer), want 1"; exit 1; }
[[ -r $AC ]] || { row "precondition" FAIL "$AC missing"; exit 1; }
echo "Waiting up to ${SLEEP_WAIT}s for the dGPU to sleep (don't start any GPU program)..."
wait_gpu suspended $SLEEP_WAIT || { row "precondition" FAIL "GPU '$(gpu)' after ${SLEEP_WAIT}s"; exit 1; }
probes_on || { row "kprobes" FAIL "could not arm"; exit 1; }
D0=$(par nv_acpi_deferred); A0=$(cat $AC)
row "precondition" PASS "defer=1, GPU suspended, charger online=$A0, deferred=$D0"
( while :; do echo "$(date +%s.%N),$(cat $AC),$(gpu)"; sleep 0.2; done ) > "$OUT/samples.csv" & WP=$!

prompt() { echo; echo "  >>> $1"; echo; }
if [[ $A0 == 1 ]]; then prompt "UNPLUG the charger now, wait ${MIN_GAP}+ s, then PLUG IT BACK IN."
else prompt "PLUG IN the charger now, wait ${MIN_GAP}+ s, then UNPLUG it again."; fi
cur=$A0; edges=0; t0=$SECONDS
while ((edges < 2 && SECONDS - t0 < EDGE_WAIT)); do
    a=$(cat $AC)
    if [[ $a != "$cur" ]]; then
        edges=$((edges + 1)); cur=$a; echo "  edge $edges: charger online=$a at +$((SECONDS - t0))s"
        ((edges == 1)) && prompt "Got it. Now wait ${MIN_GAP}+ s and $([[ $a == 0 ]] && echo 'PLUG IT BACK IN' || echo 'UNPLUG it')."
    fi
    sleep 0.25
done
((edges == 2)) || { row "cable edges" FAIL "saw $edges/2 edges in ${EDGE_WAIT}s"; exit 1; }
echo "  both edges seen; watching ${SETTLE}s more..."; sleep $SETTLE
NR=$(n_resume); NN=$(n_notify); D1=$(par nv_acpi_deferred); ST=$(gpu)
BLIP=$(cut -d, -f3 "$OUT/samples.csv" | grep -vc '^suspended$')
grep notify: "$INST/trace" | sed -E "s/.*name=\{'(.)','(.)','(.)','(.)'\} value=(0x[0-9a-f]+).*/\1\2\3\4 \5/" | sort | uniq -c > "$OUT/notify_summary.txt"
ok=PASS; ((NR <= MAX_WAKES && BLIP == 0 && D1 > D0)) && [[ $ST == suspended ]] || ok=FAIL
row "cable edges" $ok "notifies=$NN rpm_resume=$NR non-suspended-samples=$BLIP state=$ST deferred $D0->$D1"
echo "notify summary (device value):"; cat "$OUT/notify_summary.txt"
