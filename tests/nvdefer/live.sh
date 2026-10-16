#!/usr/bin/env bash
# nvdefer functional test — run with sudo AFTER the patched nvidia module is loaded.
# Wakes the dGPU exactly twice on purpose (step d nvidia-smi, step f control). Restores nv_acpi_defer,
# the fan-curve enabled state and removes its kprobes on any exit.
# Note: nv_acpi_replayed may also rise on a system suspend/resume, not only on step d's wake; avoid suspending
# the laptop during the run (thresholds unchanged: step d only requires it to rise).
# ---- thresholds (fixed before the first run) ----
SLEEP_WAIT=60        # a) GPU must be "suspended" within this many s
TRIGGERS=3           # c) asusctl fan-curve re-enables (proven Notify(NPCF,0xC0) source)
TRIGGER_GAP=5        # c) s between triggers
SETTLE=5             # c,f) s to wait after the last trigger before counting
MIN_NPCF=1           # c) >= this many Notify(NPCF,0xC0) must be seen (proves the trigger fired)
MAX_WAKES=0          # c) rpm_resume on 0000:01:00.0 allowed while deferring
REPLAY_WAIT=10       # d) nv_acpi_replayed must rise within this many s of nvidia-smi
RESUSPEND_WAIT=90    # e,f) GPU back to "suspended" within this many s
CONTROL_MIN_WAKES=1  # f) with nv_acpi_defer=0, >= this many rpm_resume (stock behaviour)
# ---------------------------------------------------
set -u
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd); U=${SUDO_USER:-shawn}
. "$HERE/lib.sh"
OUT=$REPO/docs/nvdefer/results/live-$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
exec > >(tee "$OUT/log.txt") 2>&1
DEFER0=$(par nv_acpi_defer); PROFILE=$(asusctl profile get | awk '/Active profile/{print $3}')
asusctl fan-curve --get-enabled > "$OUT/fan_enabled_before.txt" 2>&1
cleanup() {
    trap - EXIT INT TERM
    [[ -d $INST ]] && tr_save "$OUT/trace.txt"
    [[ $DEFER0 =~ ^[01]$ ]] && echo "$DEFER0" > "$P/nv_acpi_defer"
    local f ok=PASS; for f in CPU GPU MID; do   # g) only curves that were disabled need switching back
        grep -q "^$f: enabled: false" "$OUT/fan_enabled_before.txt" &&
            asusctl fan-curve --mod-profile "$PROFILE" --enable-fan-curve false --fan "${f,,}" >> "$OUT/asusctl.txt" 2>&1
    done
    asusctl fan-curve --get-enabled > "$OUT/fan_enabled_after.txt" 2>&1
    cmp -s "$OUT/fan_enabled_before.txt" "$OUT/fan_enabled_after.txt" || ok=FAIL
    probes_off; grep -q nvdefer_t/ $T/kprobe_events && ok=FAIL
    row "g restore" $ok "fan-curve state identical=$( [[ $ok == PASS ]] && echo yes || echo no), defer=$(par nv_acpi_defer), kprobes removed"
    table > "$OUT/table.txt"; local rc=$?; cat "$OUT/table.txt"; chown -R "$U" "$OUT"; echo "raw results: $OUT"; exit $rc
}
trap cleanup EXIT; trap 'exit 130' INT TERM
trigger() { asusctl fan-curve --mod-profile "$PROFILE" --enable-fan-curves true >> "$OUT/asusctl.txt" 2>&1; }
watch_gpu() { while :; do echo "$(date +%s.%N),$(gpu)"; sleep 0.2; done; }   # proves no blip between checks

# a) precondition
[[ -r $P/nv_acpi_defer && -r $P/nv_acpi_deferred && -r $P/nv_acpi_replayed ]] || { row "a precondition" FAIL "module param files missing (patched driver not loaded?)"; exit 1; }
[[ $(par nv_acpi_defer) == 1 ]] || { row "a precondition" FAIL "nv_acpi_defer=$(par nv_acpi_defer), want 1"; exit 1; }
[[ -n $PROFILE ]] || { row "a precondition" FAIL "could not read active asusctl profile"; exit 1; }
wait_gpu suspended $SLEEP_WAIT || { row "a precondition" FAIL "GPU '$(gpu)' after ${SLEEP_WAIT}s"; exit 1; }
row "a precondition" PASS "params present, defer=1, GPU suspended, profile=$PROFILE"

# b) arm probes
probes_on || { row "b kprobes" FAIL "could not arm"; exit 1; }
D0=$(par nv_acpi_deferred); R0=$(par nv_acpi_replayed)
row "b kprobes" PASS "armed; deferred=$D0 replayed=$R0"

# c) NPCF trigger while asleep
tr_clear; watch_gpu > "$OUT/c_gpu_state.csv" & WP=$!
for ((i = 1; i <= TRIGGERS; i++)); do trigger || echo "asusctl trigger $i exit $?"; sleep $TRIGGER_GAP; done
sleep $SETTLE; kill $WP; wait $WP 2>/dev/null
NP=$(n_npcf); NN=$(n_notify); NR=$(n_resume); D1=$(par nv_acpi_deferred); ST=$(gpu)
BLIP=$(grep -vc ',suspended$' "$OUT/c_gpu_state.csv"); tr_save "$OUT/c_trace.txt"
ok=PASS; ((NP >= MIN_NPCF && NR <= MAX_WAKES && BLIP == 0 && D1 > D0)) && [[ $ST == suspended ]] || ok=FAIL
row "c defer NPCF" $ok "NPCF0xC0=$NP notifies=$NN rpm_resume=$NR non-suspended-samples=$BLIP state=$ST deferred $D0->$D1"

# d) real use -> replay once
tr_clear; R1=$(par nv_acpi_replayed)
nvidia-smi -q -d POWER > "$OUT/d_nvidia_smi.txt" 2>&1; SMI=$?
for ((i = 0; i < REPLAY_WAIT * 2; i++)); do (($(par nv_acpi_replayed) > R1)) && break; sleep 0.5; done
R2=$(par nv_acpi_replayed)
LIM=$(grep -iE 'power limit' "$OUT/d_nvidia_smi.txt" | sed 's/  */ /g' | paste -sd ';')
NUM=$(grep -iE 'power limit' "$OUT/d_nvidia_smi.txt" | grep -cE ':[[:space:]]*[0-9]+(\.[0-9]+)?[[:space:]]*W')
ok=PASS; ((R2 > R1 && SMI == 0 && NUM >= 1)) || ok=FAIL
row "d replay" $ok "replayed $R1->$R2, nvidia-smi rc=$SMI, numeric limits=$NUM"
echo "    limits: ${LIM:-none found}"

# e) back to sleep
t0=$SECONDS; wait_gpu suspended $RESUSPEND_WAIT && ok=PASS || ok=FAIL
row "e re-suspend" $ok "state=$(gpu) after $((SECONDS - t0))s (limit ${RESUSPEND_WAIT}s)"
tr_save "$OUT/de_trace.txt"

# f) control: stock behaviour must wake
wait_gpu suspended $RESUSPEND_WAIT || { row "f control" FAIL "GPU not suspended before control"; exit 1; }
echo 0 > "$P/nv_acpi_defer"; tr_clear; trigger || echo "asusctl control trigger exit $?"; sleep $((SETTLE + 5))
NR=$(n_resume); NP=$(n_npcf); tr_save "$OUT/f_trace.txt"; echo 1 > "$P/nv_acpi_defer"
ok=PASS; ((NR >= CONTROL_MIN_WAKES)) || ok=FAIL
row "f control defer=0" $ok "NPCF0xC0=$NP rpm_resume=$NR (want >=$CONTROL_MIN_WAKES)"
t0=$SECONDS; wait_gpu suspended $RESUSPEND_WAIT && ok=PASS || ok=FAIL
row "f re-suspend" $ok "defer=$(par nv_acpi_defer) state=$(gpu) after $((SECONDS - t0))s"
echo "final counters: deferred=$(par nv_acpi_deferred) replayed=$(par nv_acpi_replayed)" | tee "$OUT/counters.txt"
