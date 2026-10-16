# Shared helpers for tests/nvdefer/{live,charger}.sh (sourced, run as root).
# Kprobe instance "nvdefer_t": Notify(device,value) + rpm_resume on the dGPU. Always removed by probes_off.
T=/sys/kernel/tracing; INST=$T/instances/nvdefer_t
PCI=0000:01:00.0; DGPU=/sys/bus/pci/devices/$PCI/power/runtime_status
P=/sys/module/nvidia/parameters
gpu() { cat "$DGPU" 2>/dev/null || echo missing; }
par() { cat "$P/$1" 2>/dev/null || echo missing; }
probes_off() {
    if [[ -d $INST ]]; then
        echo 0 > "$INST/events/rpm/rpm_resume/enable"; echo 0 > "$INST/events/rpm/rpm_resume/filter"
        echo 0 > "$INST/events/nvdefer_t/notify/enable"; rmdir "$INST"
    fi
    echo '-:nvdefer_t/notify' >> $T/kprobe_events 2>/dev/null
    grep -q nvdefer_t/ $T/kprobe_events && echo "WARN: kprobe nvdefer_t left behind" >&2
    return 0
}
probes_on() {
    probes_off 2>/dev/null
    echo 'p:nvdefer_t/notify acpi_ev_queue_notify_request name=+12(%di):char[4] value=%si:x32' >> $T/kprobe_events || return 1
    mkdir "$INST" && echo 4096 > "$INST/buffer_size_kb" || return 1
    echo "name == \"$PCI\"" > "$INST/events/rpm/rpm_resume/filter" && echo 1 > "$INST/events/rpm/rpm_resume/enable" || return 1
    echo 1 > "$INST/events/nvdefer_t/notify/enable"
}
tr_clear() { : > "$INST/trace"; }
tr_save() { cat "$INST/trace" >> "$1"; }           # append current trace to a file
n_resume() { grep -c 'rpm_resume:' "$INST/trace"; }
n_notify() { grep -c 'notify:' "$INST/trace"; }
n_npcf()   { grep "notify:" "$INST/trace" | grep "'N','P','C','F'" | grep -c 'value=0xc0'; }
wait_gpu() {   # wait_gpu <state> <secs> -> 0 if reached
    local i; for ((i = 0; i < $2 * 2; i++)); do [[ $(gpu) == "$1" ]] && return 0; sleep 0.5; done; [[ $(gpu) == "$1" ]]
}
RES=()   # table rows: step|PASS/FAIL|detail
row() { RES+=("$1|$2|$3"); printf '%-22s %-4s %s\n' "$1" "$2" "$3"; }
table() {
    local r fail=0; echo; printf '%-22s %-4s %s\n' STEP RESULT DETAIL; printf '%.0s-' {1..72}; echo
    for r in "${RES[@]}"; do IFS='|' read -r a b c <<< "$r"; printf '%-22s %-4s %s\n' "$a" "$b" "$c"; [[ $b == PASS ]] || fail=1; done
    return $fail
}
