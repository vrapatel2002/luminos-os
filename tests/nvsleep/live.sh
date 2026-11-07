#!/usr/bin/env bash
# nvsleep v2.1 live test — PM only: `sudo bash tests/nvsleep/live.sh`, lid open, AFTER the reboot that loads the patched
# module and with nv_sleep_skip_idle set to 1 by the PM. Design: docs/sleep/DESIGN-NVSLEEP-V2.md.
# [CHANGE: claude-code | 2026-11-06]
# Five real suspends: idle x3 (slot stays off), busy x1 (nvidia-smi -l 1 holds the card), control x1 (param 0, stock).
# SAFETY INTERLOCK: v1 left the card dead until reboot. After every sleep, before any other check: kernel log clean,
# card suspended, nvidia-smi works, card suspended again. Any failure writes nv_sleep_skip_idle=0 and stops: no more
# sleeps, and the param stays 0 on exit. The param also stays 0 if the run dies between a sleep and its check.
# Moves itself to its own session and logs to /var/tmp/nvsleep-live/<stamp>/: the link drops while asleep, a lost
# terminal does not stop the run. Summary at the end of log.txt + in summary.txt. Exit 0 only if every row passes.
# On any exit restores the tracing knobs, pm_print_times and the RTC alarm. Processes are killed by PID, never pkill -f
# (a pattern from a command line killed the PM's own shell).
# ---- thresholds (fixed before the first run) ----
SLEEP_S=30             # RTC wakes the machine after this many s
RETURN_WAIT=150        # suspend_stats must move within this many s, else interlock
PRE_WAIT=120           # port, card and audio must reach "suspended" before a run within this many s
HOLD_S=210             # busy holder ends by itself after this many s if the kill never reaches it
MAX_RESUMES=0          # idle: real (dep-0) rpm_resume of port + card + audio from PM_SUSPEND_PREPARE to the end of PM_POST_SUSPEND.
                       # dep-1 = runtime PM disabled, returns -EACCES, nothing resumes: logged, not counted.
MAX_PORT_NOIRQ=0       # idle: pci_pm_resume_noirq lines for 0000:00:01.1 (one = the slot was re-powered, the v1 bug)
MAX_POWER_IN_USE=0     # idle: LNXPOWER:00 resource_in_use right after resume
WANT_POWER_STATE=D3cold # idle: card power_state right after resume
MAX_NOTIFIER_MS=200    # idle: nv_pm_notifier at PM_SUSPEND_PREPARE, strictly below (was 2352 ms)
MIN_RESIDENCY_PCT=80   # idle: hardware sleep as % of SLEEP_S, strictly above (34.9 s of 40 s = 87 % before)
D3COLD_WAIT=60         # interlock: card "suspended" within this many s, before and after the deliberate nvidia-smi
SMI_WAIT=60            # interlock: a hung nvidia-smi counts as failed after this many s
SKIPPED_IDLE=1         # nv_sleep_skipped delta: idle runs
SKIPPED_OTHER=0        # nv_sleep_skipped delta: busy and control runs
MIN_STOCK_RESUMES=1    # control: >= this many rpm_resume of the card anywhere and of audio inside dpm_suspend
BAD_RE='Unable to determine the device handle|NVRM: .*status[= ]*0x0*11([^0-9a-fA-F]|$)|GPU has fallen off the bus'
# ---------------------------------------------------
set -u
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
if [[ -z ${NVSLEEP_RUN:-} ]]; then
    export NVSLEEP_RUN; NVSLEEP_RUN=/var/tmp/nvsleep-live/$(date +%Y%m%d-%H%M%S); mkdir -p "$NVSLEEP_RUN"
    setsid --wait bash "$0" > "$NVSLEEP_RUN/log.txt" 2>&1 < /dev/null & CHILD=$!
    echo "log: $NVSLEEP_RUN/log.txt"
    tail --pid=$CHILD -f "$NVSLEEP_RUN/log.txt"
    wait $CHILD; exit $?
fi
HERE=$(cd "$(dirname "$0")" && pwd); RUN=$NVSLEEP_RUN; U=${SUDO_USER:-shawn}
. "$HERE/../nvdefer/lib.sh"    # T PCI P gpu par wait_gpu row table
PORT=0000:00:01.1; AUDIO=0000:01:00.1; SMI=/usr/local/bin/dgpu-exec-v2; RTC=/sys/class/rtc/rtc0/wakealarm; STATS=/sys/power/suspend_stats
PCIDEV=/sys/bus/pci/devices; PG00=/sys/bus/acpi/devices/LNXPOWER:00/resource_in_use; S0IX=/sys/kernel/debug/amd_pmc/s0ix_stats
RPM=$T/events/rpm/rpm_resume; KNOBS="tracing_on options/funcgraph-abstime current_tracer max_graph_depth events/rpm/rpm_resume/enable events/power/suspend_resume/enable"
WATCH="name == \"$PCI\" || name == \"$AUDIO\" || name == \"$PORT\""; TRIGGER="stacktrace if $WATCH"
declare -A SAVED; for k in $KNOBS; do SAVED[$k]=$(cat "$T/$k"); done
SAVED_GRAPH=$(grep -v '^#' "$T/set_graph_function"); SAVED_FILTER=$(cat "$RPM/filter"); SKIP_ORIG=$(par nv_sleep_skip_idle)
PRINT_TIMES=/sys/power/pm_print_times; SAVED_PRINT=$(cat "$PRINT_TIMES")
SAFE=1; TRIPPED=0; BUSY=""; TIMES=()   # SAFE=0 from the start of a sleep until its interlock passes

state() { cat "$PCIDEV/$1/power/runtime_status" 2>/dev/null || echo missing; }
ok() { (($1)) && echo PASS || echo FAIL; }
stat_() { cat "$STATS/$1"; }
tracing_restore() {
    echo 0 > "$T/tracing_on"
    echo "!$TRIGGER" > "$RPM/trigger" 2>/dev/null
    [[ $SAVED_FILTER == none ]] && echo 0 > "$RPM/filter" || echo "$SAVED_FILTER" > "$RPM/filter"
    echo "$SAVED_GRAPH" > "$T/set_graph_function"
    for k in $KNOBS; do [[ $k == tracing_on ]] || echo "${SAVED[$k]}" > "$T/$k"; done
    echo "${SAVED[tracing_on]}" > "$T/tracing_on"
    echo "$SAVED_PRINT" > "$PRINT_TIMES"
}
tracing_arm() {
    echo 0 > "$T/tracing_on"; : > "$T/trace"
    echo pm_notifier_call_chain_robust pm_notifier_call_chain > "$T/set_graph_function"
    echo 5 > "$T/max_graph_depth"; echo function_graph > "$T/current_tracer"; echo 1 > "$T/options/funcgraph-abstime"
    echo "$WATCH" > "$RPM/filter"; echo "$TRIGGER" > "$RPM/trigger"
    echo 1 > "$RPM/enable"; echo 1 > "$T/events/power/suspend_resume/enable"; echo 1 > "$T/tracing_on"
    echo 1 > "$PRINT_TIMES"
}
drop_holder() { [[ -n $BUSY ]] || return 0; kill "$BUSY" 2>/dev/null; wait "$BUSY" 2>/dev/null; BUSY=""; }
cleanup() {
    trap - EXIT INT TERM HUP
    drop_holder; tracing_restore; echo 0 > "$RTC"
    local want=0; ((SAFE)) && want=$SKIP_ORIG
    [[ $want =~ ^[01]$ ]] && echo "$want" > "$P/nv_sleep_skip_idle"
    local k bad=""; for k in $KNOBS; do [[ $(cat "$T/$k") == "${SAVED[$k]}" ]] || bad+="$k "; done
    [[ $(cat "$RPM/filter") == "$SAVED_FILTER" ]] || bad+="filter "
    grep -q '^stacktrace' "$RPM/trigger" && bad+="trigger "
    [[ $(grep -v '^#' "$T/set_graph_function") == "$SAVED_GRAPH" ]] || bad+="set_graph_function "
    [[ $(par nv_sleep_skip_idle) == "$want" ]] || bad+="nv_sleep_skip_idle "
    [[ $(cat "$PRINT_TIMES") == "$SAVED_PRINT" ]] || bad+="pm_print_times "
    row "restore" "$(ok "${#bad} == 0")" "${bad:-all knobs back}, nv_sleep_skip_idle=$(par nv_sleep_skip_idle) (want $want)"
    echo "port=$(state $PORT) card=$(gpu) audio=$(state $AUDIO) raw results: $RUN"
    table > "$RUN/summary.txt"; local rc=$?
    { echo; printf '%s\n' "${TIMES[@]}"; ((TRIPPED)) && echo "INTERLOCK TRIPPED: nv_sleep_skip_idle left at 0, run stopped"; } >> "$RUN/summary.txt"
    cat "$RUN/summary.txt"; chown -R "$U" "$RUN" /var/tmp/nvsleep-live; exit $rc
}
trap cleanup EXIT; trap 'exit 130' INT TERM HUP

# Trace parsing. Timestamps are funcgraph-abstime seconds (field 1).
graph_span() {   # graph_span <trace> <func> <nth> -> "start end" of the nth call, nothing if absent
    awk -v f="$2" -v want="$3" '
        !/\|/ { next }
        open { s = $0; sub(/^.*\|/, "", s); if (match(s, /[^ ]/) == at && substr(s, at, 1) == "}") { print t0, $1; exit } next }
        index($0, f "();") && ++n == want { match($0, /[0-9.]+ us/); printf "%s %.6f\n", $1, $1 + substr($0, RSTART, RLENGTH - 3) / 1e6; exit }
        index($0, f "() {") && ++n == want { t0 = $1; s = $0; sub(/^.*\|/, "", s); at = match(s, /[^ ]/); open = 1 }' "$1"
}
marker() { awk -v n="suspend_resume: $2[" -v w="] $3 " 'index($0, n) && index($0, w) { print $1; exit }' "$1"; }   # marker <trace> <phase> <begin|end> -> first timestamp
n_rpm() {   # n_rpm <trace> <dev> <from> <to> [dep=0] -> rpm_resume events of dev in the window with that disable depth
    awk -v d="rpm_resume: $2 " -v t=" dep-${5:-0} " -v a="$3" -v b="$4" 'index($0, d) && index($0, t) && $1 + 0 >= a + 0 && $1 + 0 <= b + 0 { n++ } END { print n + 0 }' "$1"
}
secs() { [[ -n ${1:-} && -n ${2:-} ]] && awk -v a="$1" -v b="$2" 'BEGIN { printf "%.3f", b - a }' || printf 'n/a'; }

# One suspend woken by the RTC. Sets DS DF (suspend_stats success/fail deltas), DH (hw sleep us), DSKIP, TR, KLOG, WALL,
# and POWER_STATE + IN_USE, read before anything else can touch the slot.
sleep_once() {
    local name=$1 s0 f0 h0 k0 t0=$SECONDS; s0=$(stat_ success); f0=$(stat_ fail); h0=$(stat_ total_hw_sleep); k0=$(par nv_sleep_skipped); WALL=$(date +%s)
    TR=$RUN/$name-trace.txt; KLOG=$RUN/$name-kernel.txt; SAFE=0
    cat "$S0IX" > "$RUN/$name-s0ix-before.txt"
    tracing_arm
    echo 0 > "$RTC"; echo "+$SLEEP_S" > "$RTC"
    echo "== $name: suspending at $(date +%T)"
    echo nvsleep-entry-start > "$T/trace_marker"
    systemctl suspend -i; echo "systemctl suspend -i rc=$?"
    until [[ $(stat_ success) != "$s0" || $(stat_ fail) != "$f0" ]] || ((SECONDS - t0 > RETURN_WAIT)); do sleep 0.2; done
    POWER_STATE=$(cat "$PCIDEV/$PCI/power_state"); IN_USE=$(cat "$PG00")
    echo "== $name: back at $(date +%T) port=$(state $PORT) card=$(gpu) audio=$(state $AUDIO) power_state=$POWER_STATE LNXPOWER:00 in_use=$IN_USE"
    echo 0 > "$T/tracing_on"; cat "$T/trace" > "$TR"; tracing_restore; echo 0 > "$RTC"
    cat "$S0IX" > "$RUN/$name-s0ix-after.txt"
    DS=$(($(stat_ success) - s0)); DF=$(($(stat_ fail) - f0)); DH=$(($(stat_ total_hw_sleep) - h0)); DSKIP=$(($(par nv_sleep_skipped) - k0))
    local start; start=$(awk '/nvsleep-entry-start/ { print $1; exit }' "$TR")
    local t="$name: entry $(secs "$start" "$(marker "$TR" suspend_enter end)")s (to hw sleep $(secs "$start" "$(marker "$TR" timekeeping_freeze begin)")s)"
    t+=" resume $(secs "$(marker "$TR" timekeeping_freeze end)" "$(marker "$TR" thaw_processes end)")s success +$DS fail +$DF skipped +$DSKIP"
    TIMES+=("$t"); echo "$t"
}
wait_off() {   # port, card and audio runtime-suspended within $1 s
    local i; for ((i = 0; i < $1 * 2; i++)); do [[ $(state $PORT) == suspended && $(gpu) == suspended && $(state $AUDIO) == suspended ]] && return 0; sleep 0.5; done
    [[ $(state $PORT) == suspended && $(gpu) == suspended && $(state $AUDIO) == suspended ]]
}
trip() { echo 0 > "$P/nv_sleep_skip_idle"; TRIPPED=1; SAFE=0; row "$1 INTERLOCK" FAIL "$2; nv_sleep_skip_idle=0, no more sleeps"; }
ready() { wait_off "$PRE_WAIT" && return 0; trip "$1" "port=$(state $PORT) card=$(gpu) audio=$(state $AUDIO) after ${PRE_WAIT}s, not sleeping"; exit 1; }
klog_bad() { sleep 2; journalctl -k -S "@$WALL" > "$KLOG" 2>&1; grep -m3 -E "$BAD_RE" "$KLOG"; }   # the log is re-read after nvidia-smi: v1's errors came only then
# The only deliberate wake of a runtime-suspended card (BUG-078): this nvidia-smi and aplay -l right after it.
interlock() {
    local name=$1 hit rc; hit=$(klog_bad)
    [[ -z $hit ]] || { trip "$name" "kernel log: $hit"; return; }
    ((DS + DF > 0)) || { trip "$name" "no suspend_stats outcome in ${RETURN_WAIT}s"; return; }
    wait_gpu suspended "$D3COLD_WAIT" || { trip "$name" "card=$(gpu), not suspended within ${D3COLD_WAIT}s"; return; }
    timeout "$SMI_WAIT" sudo -u "$U" "$SMI" nvidia-smi > "$RUN/$name-smi.txt" 2>&1; rc=$?
    ((rc == 0)) || { trip "$name" "nvidia-smi rc=$rc: $(head -1 "$RUN/$name-smi.txt")"; return; }
    hit=$(klog_bad)
    [[ -z $hit ]] || { trip "$name" "kernel log after nvidia-smi: $hit"; return; }
    aplay -l > "$RUN/$name-aplay.txt" 2>&1; rc=$?
    row "$name aplay" "$(grep -qi nvidia "$RUN/$name-aplay.txt" && echo PASS || echo FAIL)" "aplay -l rc=$rc, NVIDIA lines: $(grep -ci nvidia "$RUN/$name-aplay.txt")"
    wait_gpu suspended "$D3COLD_WAIT" || { trip "$name" "card=$(gpu), not back to suspended within ${D3COLD_WAIT}s of nvidia-smi"; return; }
    row "$name card check" PASS "log clean, suspended, nvidia-smi rc=0, suspended again"
    SAFE=1
}
stop_if_tripped() { ((TRIPPED == 0)) || exit 1; }

run_idle() {
    local n=idle$1 a b r0 r1 r2 ms nv
    ready "$n"; sleep_once "$n"; interlock "$n"
    row "$n suspended" "$(ok "DS == 1 && DF == 0")" "suspend_stats success +$DS fail +$DF"
    a=$(graph_span "$TR" pm_notifier_call_chain_robust 1); b=$(graph_span "$TR" pm_notifier_call_chain 1)
    if [[ -n $a && -n $b ]]; then
        r0=$(n_rpm "$TR" $PORT "${a% *}" "${b#* }"); r1=$(n_rpm "$TR" "$PCI" "${a% *}" "${b#* }"); r2=$(n_rpm "$TR" $AUDIO "${a% *}" "${b#* }")
        row "$n rpm_resume" "$(ok "r0 + r1 + r2 <= MAX_RESUMES")" "dep-0: port $r0 card $r1 audio $r2 (max $MAX_RESUMES); card dep-1 ignored: $(n_rpm "$TR" "$PCI" "${a% *}" "${b#* }" 1); stacks in $n-trace.txt"
    else row "$n rpm_resume" FAIL "no PREPARE/POST window in $n-trace.txt"; fi
    r0=$(grep -c "$PORT: PM: pci_pm_resume_noirq returned" "$KLOG"); r1=$(grep -c 'PM: pci_pm_resume_noirq returned' "$KLOG")
    row "$n port noirq" "$(ok "r0 <= MAX_PORT_NOIRQ && r1 > 0")" "$r0 lines for $PORT (max $MAX_PORT_NOIRQ), $r1 for all devices (0 = pm_print_times output missing, proves nothing)"
    row "$n LNXPOWER:00" "$(ok "${IN_USE:-1} <= MAX_POWER_IN_USE")" "resource_in_use=$IN_USE right after resume (max $MAX_POWER_IN_USE)"
    row "$n power_state" "$([[ $POWER_STATE == "$WANT_POWER_STATE" ]] && echo PASS || echo FAIL)" "card $POWER_STATE right after resume (want $WANT_POWER_STATE)"
    nv=$(graph_span "$TR" 'nv_pm_notifier [nvidia]' 1)
    if [[ -n $nv ]]; then
        ms=$(awk -v s="$nv" 'BEGIN { split(s, a, " "); printf "%.3f", (a[2] - a[1]) * 1000 }')
        row "$n notifier" "$(awk -v m="$ms" -v x="$MAX_NOTIFIER_MS" 'BEGIN { print (m < x) ? "PASS" : "FAIL" }')" "nv_pm_notifier $ms ms (limit $MAX_NOTIFIER_MS)"
    else row "$n notifier" FAIL "nv_pm_notifier not in $n-trace.txt"; fi
    row "$n S0i3" "$(ok "DH * 100 > MIN_RESIDENCY_PCT * SLEEP_S * 1000000")" "hw sleep ${DH}us of ${SLEEP_S}s = $((DH / (SLEEP_S * 10000))) % (needs > $MIN_RESIDENCY_PCT)"
    row "$n skipped" "$(ok "DSKIP == SKIPPED_IDLE")" "nv_sleep_skipped +$DSKIP (want +$SKIPPED_IDLE)"
    stop_if_tripped
}
run_busy() {
    ready busy
    sudo -u "$U" timeout "$HOLD_S" "$SMI" nvidia-smi -l 1 > "$RUN/busy-held-smi.txt" 2>&1 & BUSY=$!
    wait_gpu active 30 || { trip busy "card=$(gpu), holder did not wake it within 30s"; exit 1; }
    row "busy held" PASS "card=$(gpu), holder pid $BUSY"
    sleep_once busy; drop_holder; interlock busy
    row "busy outcome" "$(ok "DS + DF == 1")" "$( ((DS)) && echo slept || { ((DF)) && echo 'aborted cleanly' || echo 'no outcome'; }) (success +$DS fail +$DF, reason in busy-kernel.txt)"
    row "busy skipped" "$(ok "DSKIP == SKIPPED_OTHER")" "nv_sleep_skipped +$DSKIP (want +$SKIPPED_OTHER)"
    stop_if_tripped
}
# A syscore flag left on the subtree would hide audio's pci_pm_suspend rpm_resume, so that resume is the check.
run_control() {
    local nr na
    ready control; echo 0 > "$P/nv_sleep_skip_idle"
    sleep_once control; interlock control
    ((TRIPPED)) || echo "$SKIP_ORIG" > "$P/nv_sleep_skip_idle"
    row "control suspended" "$(ok "DS == 1 && DF == 0")" "suspend_stats success +$DS fail +$DF"
    nr=$(n_rpm "$TR" "$PCI" 0 999999999)
    na=$(n_rpm "$TR" $AUDIO "$(marker "$TR" dpm_suspend begin)" "$(marker "$TR" dpm_suspend end)")
    row "control stock wake" "$(ok "nr >= MIN_STOCK_RESUMES")" "$nr rpm_resume on $PCI (want >= $MIN_STOCK_RESUMES)"
    row "control syscore" "$(ok "na >= MIN_STOCK_RESUMES")" "$na rpm_resume on $AUDIO in dpm_suspend (want >= $MIN_STOCK_RESUMES; 0 = flag left set)"
    row "control skipped" "$(ok "DSKIP == SKIPPED_OTHER")" "nv_sleep_skipped +$DSKIP (want +$SKIPPED_OTHER)"
    stop_if_tripped
}

[[ $SKIP_ORIG == 1 && -r $P/nv_sleep_skipped ]] || { row "precondition" FAIL "nv_sleep_skip_idle='$SKIP_ORIG' (PM sets it to 1; patched module loaded?)"; exit 1; }
row "precondition" PASS "skip_idle=1 skipped=$(par nv_sleep_skipped)"
run_idle 1; run_idle 2; run_idle 3
run_busy
run_control
