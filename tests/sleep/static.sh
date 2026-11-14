#!/usr/bin/env bash
# tests/sleep/static.sh — static checks for CONTRACTS.md sections B-E, then test_lid.py.
# Run: bash tests/sleep/static.sh
# No root needed, changes nothing outside a temp dir, never suspends.
# [CHANGE: claude-code | 2026-11-06]
set -u
cd "$(dirname "$0")/../.." || exit 2

PY=/home/shawn/.local/share/luminos/coder-venv/bin/python
LID=scripts/luminos-lid
HOOK=config/system-sleep/luminos-sdreader
BRIGHT=config/system-sleep/luminos-brightness
POSTER=scripts/luminos-wallpaper-poster
WEBMODE=src/wallpapers/org.luminos.livewallpaper/contents/ui/WebMode.qml
POLICY=scripts/luminos-wake-policy
INSTALL=scripts/luminos-strong-sleep
RULE=config/udev/71-luminos-wake.rules
UNIT=systemd/luminos-wake-policy.service

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
check() { # check "what" command...
    local what=$1; shift
    if "$@" >"$tmp/out" 2>&1; then pass "$what"; else fail "$what"; sed 's/^/     /' "$tmp/out"; fi
}

syntax() { # by shebang: the contract only fixes the language of B (python) and C (sh)
    case "$(head -n1 "$1")" in
        *python*) PYTHONPYCACHEPREFIX=$tmp "$PY" -m py_compile "$1" ;;
        *bash*) bash -n "$1" ;;
        *sh*) sh -n "$1" ;;
        *) echo "no usable shebang"; false ;;
    esac
}
budget() { # budget file max
    local n; n=$(wc -l <"$1") || return 1
    echo "$n lines, budget $2"; [ "$n" -le "$2" ]
}

for f in "$LID" "$POLICY" "$INSTALL" "$HOOK" "$BRIGHT" "$POSTER"; do
    check "syntax: $f" syntax "$f"
done
check "hook is plain sh" grep -qE '^#!.*[/ ]sh$' "$HOOK"
check "brightness hook is plain sh" grep -qE '^#!.*[/ ]sh$' "$BRIGHT"

check "budget: $LID" budget "$LID" 235 # Re-plan 10 (2026-11-13): the poweroff failsafe
check "budget: $POSTER" budget "$POSTER" 80
check "budget: $HOOK" budget "$HOOK" 40 # Re-plan 7
check "budget: $POLICY" budget "$POLICY" 120
check "budget: $BRIGHT" budget "$BRIGHT" 40
check "budget: $INSTALL" budget "$INSTALL" 95 # Re-plan 6

# --- udev rule: a single rule, USB add, vendor not ASUS, sets wakeup disabled
if ! command -v udevadm >/dev/null || ! udevadm verify --help >/dev/null 2>&1; then
    echo "NOTE udevadm verify unavailable, skipped"
else
    check "udevadm verify: $RULE" udevadm verify "$RULE"
fi
rule_only_usb() {
    local rules
    rules=$(sed -e ':a' -e '/\\$/{N;s/\\\n//;ba' -e '}' "$1" | grep -vE '^[[:space:]]*(#|$)') || return 1
    [ "$(printf '%s\n' "$rules" | wc -l)" -eq 1 ] || { echo "expected exactly one rule"; return 1; }
    # add, or add|bind: usbhid re-enables wakeup while binding, after the add event
    printf '%s\n' "$rules" | grep -qE 'ACTION=="([a-z]+\|)*add(\|[a-z]+)*"' || { echo "no add in: $rules"; return 1; }
    local want
    for want in 'SUBSYSTEM=="usb"' 'ATTR{power/wakeup}="disabled"'; do
        printf '%s\n' "$rules" | grep -qF "$want" || { echo "missing $want in: $rules"; return 1; }
    done
    # Re-plan 3: root hubs (1d6b) stay as they are, like the internal keyboard (0b05). Two matches or one a|b match.
    for want in 0b05 1d6b; do
        printf '%s\n' "$rules" | grep -qE "ATTR\{idVendor\}!=\"([0-9a-f]+\|)*$want(\|[0-9a-f]+)*\"" \
            || { echo "does not exclude $want: $rules"; return 1; }
    done
}
check "rule only matches USB, excluding 0b05 and 1d6b" rule_only_usb "$RULE"

# --- service
unit_ok() {
    grep -q '^Type=oneshot' "$1" && grep -qE '^ExecStart=.*luminos-wake-policy +--apply' "$1" \
        && grep -qE '^(After=.*udev-settle|ExecStartPre=.*udevadm settle)' "$1" && grep -q '^WantedBy=' "$1"
}
check "unit: oneshot --apply after udev settle, enableable" unit_ok "$UNIT"

# --- hook never blocks sleep. 'pre' and 'post' only ever run on the fake below: the real reader may be inside its
# 60 s window, and stopping the real timer then would leave it unbound.
check "hook exits 0 for unknown args" sh "$HOOK" bogus bogus
check "hook exits 0 with no args" sh "$HOOK"
check "hook has the card guard" grep -qE 'mmc_host.*mmc\*:' "$HOOK"

# Re-plan 3 and 7: a temp copy is pointed at a fake sysfs made of plain files and at a fake systemd on PATH.
fake_hook() { # fake_hook dir: dir/hook, dir/drv/<dev>, dir/state, dir/bin; refuses a copy that still reaches the real system
    mkdir -p "$1/drv/rtsx_pci_sdmmc.0/mmc_host/mmc0" "$1/state" "$1/bin"
    : >"$1/drv/unbind"; : >"$1/drv/bind"
    # Like the real ones: a timer's name stays taken until it is stopped, and systemd-run refuses a taken name.
    cat >"$1/bin/systemctl" <<EOF
#!/bin/sh
echo "\${0##*/} \$*" >>"$1/calls"
if [ "\${0##*/}" = systemctl ]; then
    case "\$*" in *stop*) rm -f "$1/timer" ;; esac
else
    [ ! -e "$1/timer" ] || exit 1
    true >"$1/timer"
    printf '%s\0' "\$@" >"$1/scheduled"
fi
exit "\$(cat "$1/rc" 2>/dev/null || echo 0)"
EOF
    cp "$1/bin/systemctl" "$1/bin/systemd-run"
    chmod +x "$1/bin/systemctl" "$1/bin/systemd-run"
    sed -E -e "s#/sys/bus/platform/drivers/rtsx_pci_sdmmc#$1/drv#g" -e "s#/run/luminos#$1/state#g" \
        -e "s#/usr/lib/systemd/system-sleep/luminos-sdreader#$1/hook#g" \
        -e "s#(/usr)?/bin/(systemd-run|systemctl)#$1/bin/\2#g" "$HOOK" >"$1/hook"
    chmod +x "$1/hook"
    if sed -e "s#$1/bin/##g" -e "s#$1#FAKE#g" "$1/hook" | grep -v '^[[:space:]]*#' | grep -qE '/sys/|/run/|/usr/lib/|/bin/system'; then
        echo "copy still names a real path"; return 1
    fi
}
fhook() { PATH=$1/bin:$PATH timeout 10 sh "$1/hook" "$2" suspend; }
unbound_state() { rm -r "$1/drv/rtsx_pci_sdmmc.0"; : >"$1/state/sdreader-unbound"; } # where the reader is after a post
run_scheduled() { # what systemd-run was asked to run later, without systemd-run's own options
    local a cmd=()
    while IFS= read -r -d '' a; do
        case "$a" in -*) [ ${#cmd[@]} -eq 0 ] || cmd+=("$a") ;; *) cmd+=("$a") ;; esac
    done <"$1/scheduled"
    PATH=$1/bin:$PATH timeout 10 "${cmd[@]}"
}
hook_no_card_unbinds() {
    local d=$tmp/nocard; fake_hook "$d" || return 1
    fhook "$d" pre || return 1
    grep -qx rtsx_pci_sdmmc.0 "$d/drv/unbind" && [ -e "$d/state/sdreader-unbound" ]
}
hook_card_leaves_it_alone() {
    local d=$tmp/card; fake_hook "$d" || return 1
    mkdir "$d/drv/rtsx_pci_sdmmc.0/mmc_host/mmc0/mmc0:aaaa"
    fhook "$d" pre || return 1
    [ ! -s "$d/drv/unbind" ] && [ ! -e "$d/state/sdreader-unbound" ]
}
hook_failed_unbind_removes_record() {
    local d=$tmp/nounbind; fake_hook "$d" || return 1
    rm "$d/drv/unbind"; mkdir "$d/drv/unbind" # writing to a directory fails
    fhook "$d" pre || return 1
    [ ! -e "$d/state/sdreader-unbound" ]
}
hook_no_record_no_unbind() { # the record comes first: without one the reader could never be re-bound
    local d=$tmp/norecord; fake_hook "$d" || return 1
    rm -r "$d/state"; : >"$d/state" # a file where the directory should be
    fhook "$d" pre || return 1
    [ ! -s "$d/drv/unbind" ]
}
hook_unwritable_record_no_unbind() { # the directory is there, the record still cannot be written
    local d=$tmp/readonly rc=0; fake_hook "$d" || return 1
    : >"$d/state/sdreader-unbound"; chmod 444 "$d/state/sdreader-unbound"
    fhook "$d" pre || rc=$?
    chmod 644 "$d/state/sdreader-unbound"
    [ "$rc" -eq 0 ] || { echo "exit code $rc"; return 1; }
    [ ! -s "$d/drv/unbind" ]
}
hook_post_no_record_does_nothing() {
    local d=$tmp/post-none; fake_hook "$d" || return 1
    fhook "$d" post || return 1
    [ ! -s "$d/drv/bind" ] || { echo "bound without a record"; return 1; }
    [ ! -e "$d/calls" ] || { echo "called: $(cat "$d/calls")"; return 1; }
}
hook_post_schedules_does_not_bind() {
    local d=$tmp/post-sched; fake_hook "$d" || return 1
    unbound_state "$d"
    fhook "$d" post || return 1
    [ ! -s "$d/drv/bind" ] || { echo "bound right away"; return 1; }
    grep -qE '^systemd-run .*--on-active=60s?( |$)' "$d/calls" || { echo "no 60 s timer: $(cat "$d/calls")"; return 1; }
    grep -qE '^systemd-run .*--unit=luminos-sdreader-rebind( |$)' "$d/calls" || { echo "wrong unit: $(cat "$d/calls")"; return 1; }
    [ -e "$d/state/sdreader-unbound" ] || { echo "record gone before the bind"; return 1; }
}
hook_scheduled_command_rebinds() { # runs what the timer would run, so the deferred half is tested too
    local d=$tmp/post-later; fake_hook "$d" || return 1
    unbound_state "$d"
    fhook "$d" post || return 1
    run_scheduled "$d" || { echo "scheduled command failed"; return 1; }
    grep -qx rtsx_pci_sdmmc.0 "$d/drv/bind" || { echo "scheduled command did not bind"; return 1; }
    [ ! -e "$d/state/sdreader-unbound" ] || { echo "record left behind"; return 1; }
}
hook_pre_unbound_cancels() {
    local d=$tmp/pre-cancel; fake_hook "$d" || return 1
    unbound_state "$d"
    fhook "$d" pre || return 1
    [ ! -s "$d/drv/unbind" ] || { echo "tried to unbind again"; return 1; }
    # the .timer by name: a bare unit name would stop the .service and leave the timer running
    grep -qE '^systemctl .*stop.*luminos-sdreader-rebind\.timer' "$d/calls" || { echo "no cancel: $(cat "$d/calls" 2>/dev/null)"; return 1; }
    [ -e "$d/state/sdreader-unbound" ] || { echo "record gone: the next post would never re-bind"; return 1; }
}
hook_pre_unbound_no_record() { # unbound, but not by us
    local d=$tmp/pre-other; fake_hook "$d" || return 1
    rm -r "$d/drv/rtsx_pci_sdmmc.0"
    fhook "$d" pre || return 1
    [ ! -s "$d/drv/unbind" ] && [ ! -e "$d/state/sdreader-unbound" ]
}
hook_full_cycle() { # sleep, wake, sleep again inside the minute, wake
    local d=$tmp/cycle; fake_hook "$d" || return 1
    fhook "$d" pre || return 1
    rm -r "$d/drv/rtsx_pci_sdmmc.0" # what the real driver does on that unbind
    fhook "$d" post && fhook "$d" pre && fhook "$d" post || return 1
    [ "$(wc -l <"$d/drv/unbind")" -eq 1 ] || { echo "unbound more than once"; return 1; }
    [ "$(grep -c '^systemd-run' "$d/calls")" -eq 2 ] || { echo "$(cat "$d/calls")"; return 1; }
    [ ! -s "$d/drv/bind" ] || { echo "bound before the timer"; return 1; }
}
hook_cancel_fails_exit_0() {
    local d=$tmp/cancel-fail; fake_hook "$d" || return 1
    unbound_state "$d"; echo 1 >"$d/rc"
    fhook "$d" pre || { echo "exit code $?"; return 1; }
    [ ! -s "$d/drv/unbind" ]
}
hook_schedule_fails_binds_now() { # beyond the contract's exit 0: otherwise the reader would stay unbound until the next sleep
    local d=$tmp/sched-fail; fake_hook "$d" || return 1
    unbound_state "$d"; echo 1 >"$d/rc"
    fhook "$d" post || { echo "exit code $?"; return 1; }
    grep -qx rtsx_pci_sdmmc.0 "$d/drv/bind" || { echo "left unbound with no timer"; return 1; }
    [ ! -e "$d/state/sdreader-unbound" ] || { echo "record left behind"; return 1; }
}
hook_post_replaces_a_leftover_timer() {
    local d=$tmp/leftover; fake_hook "$d" || return 1
    unbound_state "$d"; : >"$d/timer"
    fhook "$d" post || return 1
    [ -s "$d/scheduled" ] || { echo "not rescheduled: $(cat "$d/calls")"; return 1; }
    [ ! -s "$d/drv/bind" ] || { echo "bound right away"; return 1; }
}
hook_pre_bound_with_record_still_unbinds() { # the timer's bind worked, its record did not go: still sleep unbound
    local d=$tmp/stale; fake_hook "$d" || return 1
    : >"$d/state/sdreader-unbound"
    fhook "$d" pre || return 1
    grep -qx rtsx_pci_sdmmc.0 "$d/drv/unbind" && [ -e "$d/state/sdreader-unbound" ]
}
check "hook, no card: unbinds and records" hook_no_card_unbinds
check "hook, card present: no unbind, no record" hook_card_leaves_it_alone
check "hook, unbind fails: record removed" hook_failed_unbind_removes_record
check "hook, record cannot be written: no unbind" hook_no_record_no_unbind
if [ "$(id -u)" -ne 0 ]; then # root writes through the read-only bit
    check "hook, record file read-only: exit 0, no unbind" hook_unwritable_record_no_unbind
fi
check "hook, post, no record: nothing at all" hook_post_no_record_does_nothing
check "hook, post: schedules in 60 s, does not bind" hook_post_schedules_does_not_bind
check "hook, the scheduled command binds and clears the record" hook_scheduled_command_rebinds
check "hook, pre while unbound: no unbind, cancels the timer" hook_pre_unbound_cancels
check "hook, pre, unbound with no record: no unbind" hook_pre_unbound_no_record
check "hook, pre post pre post: one unbind, two timers, no bind" hook_full_cycle
check "hook, cancel fails: exit 0, no unbind" hook_cancel_fails_exit_0
check "hook, scheduling fails: exit 0, binds at once" hook_schedule_fails_binds_now
check "hook, post: a leftover timer does not stop the new one" hook_post_replaces_a_leftover_timer
check "hook, pre, bound with an old record: still unbinds" hook_pre_bound_with_record_still_unbinds

# --- section F, brightness hook. Only ever run 'pre' and 'post' on a fake sysfs: a wrong read of the real
# nvidia_0 would wake the dGPU. bright_overrides refuses a hook that could reach the real one.
code_of() { sed -e '/^[[:space:]]*#/d' -e 's/[[:space:]]#.*//' "$1"; }
bright_overrides() {
    grep -q BACKLIGHT_ROOT "$BRIGHT" && grep -q RUN_DIR "$BRIGHT" || { echo "no env overrides"; return 1; }
    local real
    real=$(code_of "$BRIGHT" | grep -E '/sys/|/run/' | grep -vE 'BACKLIGHT_ROOT|RUN_DIR')
    [ -z "$real" ] || { echo "hard-coded path: $real"; return 1; }
}
OLD=2000-01-01
add_backlight() { # add_backlight dir name gpu driver value: the same symlink shape as the real /sys/class/backlight
    local b=$1/devices/$3/backlight/$2 f
    mkdir -p "$b"
    [ -z "$4" ] || ln -s "../../bus/pci/drivers/$4" "$1/devices/$3/driver"
    ln -s ../.. "$b/device"
    ln -s "../../devices/$3/backlight/$2" "$1/class/backlight/$2"
    for f in brightness actual_brightness; do
        echo "$5" >"$b/$f"
        touch -a -d "$OLD" "$b/$f"; touch -m -d "$OLD" "$b/$f"
    done
}
fake_backlight() { # acpi_video0 is there because the driver decides, not the name
    bright_overrides || return 1
    mkdir -p "$1/class/backlight" "$1/bus/pci/drivers/amdgpu" "$1/bus/pci/drivers/nvidia" "$1/run"
    add_backlight "$1" amdgpu_bl2 gpu0 amdgpu 1000
    add_backlight "$1" nvidia_0 gpu1 nvidia 500
    add_backlight "$1" acpi_video0 gpu2 nvidia 500
    add_backlight "$1" panel0 connector0 "" 700 # a DRM connector has no driver link: not nvidia, so it is saved
}
bright() { BACKLIGHT_ROOT=$1/class/backlight RUN_DIR=$1/run timeout 10 sh "$BRIGHT" "$2" suspend; }
amd() { echo "$1/class/backlight/amdgpu_bl2/brightness"; }
nvidia_stamps() { # access time, change time and size of every nvidia file: a read moves the first, a write the others
    local n f
    for n in nvidia_0 acpi_video0; do
        for f in brightness actual_brightness; do stat -L -c '%n %X %Y %s' "$1/class/backlight/$n/$f"; done
    done
}

bright_names() {
    local bad
    bad=$(code_of "$BRIGHT" | grep nvidia_ | grep -vE 'nvidia_[^ ]*\)|continue')
    [ -z "$bad" ] || { echo "uses nvidia_ outside an exclusion: $bad"; return 1; }
    if code_of "$BRIGHT" | grep actual_brightness; then echo "reads actual_brightness"; return 1; fi
}
bright_args() {
    local d=$tmp/bl-args; fake_backlight "$d" || return 1
    bright "$d" bogus && BACKLIGHT_ROOT=$d/class/backlight RUN_DIR=$d/run sh "$BRIGHT"
}
bright_pre_saves() {
    local d=$tmp/bl-pre; fake_backlight "$d" || return 1
    bright "$d" pre || return 1
    [ "$(cat "$d/run/brightness-amdgpu_bl2")" = 1000 ] || { echo "amdgpu_bl2 not saved"; return 1; }
    [ "$(cat "$d/run/brightness-panel0")" = 700 ] || { echo "backlight with no driver link not saved"; return 1; }
    [ ! -e "$d/run/brightness-nvidia_0" ] || { echo "nvidia_0 saved"; return 1; }
    [ ! -e "$d/run/brightness-acpi_video0" ] || { echo "nvidia-driven acpi_video0 saved"; return 1; }
}
bright_stale_nvidia_record() { # pre never writes one, so this is post defending itself against a leftover
    local d=$tmp/bl-stale before; fake_backlight "$d" || return 1
    before=$(nvidia_stamps "$d")
    echo 5 >"$d/run/brightness-nvidia_0"; echo 5 >"$d/run/brightness-acpi_video0"
    bright "$d" post || return 1
    [ "$(nvidia_stamps "$d")" = "$before" ] || { echo "nvidia file touched:"; nvidia_stamps "$d"; return 1; }
}
bright_nvidia_untouched() { # reading amdgpu_bl2 is the control: it proves atime moves on this filesystem
    local d=$tmp/bl-untouched before; fake_backlight "$d" || return 1
    before=$(nvidia_stamps "$d")
    local old; old=$(stat -L -c %X "$(amd "$d")")
    bright "$d" pre || return 1
    [ "$(stat -L -c %X "$(amd "$d")")" != "$old" ] || { echo "control: reading a file did not move its atime"; return 1; }
    echo 900 >"$(amd "$d")"
    bright "$d" post || return 1
    [ "$(nvidia_stamps "$d")" = "$before" ] || { echo "nvidia file touched:"; nvidia_stamps "$d"; return 1; }
    [ "$(cat "$d/class/backlight/nvidia_0/brightness")" = 500 ] || { echo "nvidia_0 changed"; return 1; }
}
bright_post_restores() {
    local d=$tmp/bl-post; fake_backlight "$d" || return 1
    bright "$d" pre || return 1
    echo 900 >"$(amd "$d")"
    bright "$d" post || return 1
    [ "$(cat "$(amd "$d")")" = 1000 ] || { echo "not restored: $(cat "$(amd "$d")")"; return 1; }
    [ ! -e "$d/run/brightness-amdgpu_bl2" ] || { echo "record left behind"; return 1; }
}
bright_post_same_value_no_write() {
    local d=$tmp/bl-same before; fake_backlight "$d" || return 1
    bright "$d" pre || return 1
    before=$(stat -L -c %Y "$(amd "$d")")
    bright "$d" post || return 1
    [ "$(stat -L -c %Y "$(amd "$d")")" = "$before" ] || { echo "wrote an unchanged value"; return 1; }
    [ ! -e "$d/run/brightness-amdgpu_bl2" ] || { echo "record left behind"; return 1; }
}
bright_post_no_record_no_write() {
    local d=$tmp/bl-none before; fake_backlight "$d" || return 1
    before=$(stat -L -c %Y "$(amd "$d")")
    bright "$d" post || return 1
    [ "$(stat -L -c %Y "$(amd "$d")")" = "$before" ]
}
bright_makes_run_dir() {
    local d=$tmp/bl-mkdir; fake_backlight "$d" || return 1
    rmdir "$d/run"
    bright "$d" pre || return 1
    [ "$(cat "$d/run/brightness-amdgpu_bl2")" = 1000 ]
}
bright_no_run_dir_exit_0() { # a file where the directory should be
    local d=$tmp/bl-norun; fake_backlight "$d" || return 1
    rmdir "$d/run"; : >"$d/run"
    bright "$d" pre && bright "$d" post
}
bright_readonly_record_exit_0() { # the sh special-builtin trap: a failed ': > file' kills the shell
    local d=$tmp/bl-rorecord rc=0; fake_backlight "$d" || return 1
    echo 7 >"$d/run/brightness-amdgpu_bl2"; chmod 444 "$d/run/brightness-amdgpu_bl2"
    bright "$d" pre || rc=$?
    chmod 644 "$d/run/brightness-amdgpu_bl2"
    [ "$rc" -eq 0 ] || { echo "exit code $rc"; return 1; }
}
bright_readonly_brightness_exit_0() {
    local d=$tmp/bl-robright rc=0; fake_backlight "$d" || return 1
    bright "$d" pre || return 1
    echo 900 >"$(amd "$d")"; chmod 444 "$(amd "$d")"
    bright "$d" post || rc=$?
    chmod 644 "$(amd "$d")"
    [ "$rc" -eq 0 ] || { echo "exit code $rc"; return 1; }
}
bright_failed_read_never_clobbers() { # a value that could not be saved must not come back as an empty write
    local d=$tmp/bl-noread rc=0; fake_backlight "$d" || return 1
    chmod 000 "$(amd "$d")"
    bright "$d" pre || rc=$?
    chmod 644 "$(amd "$d")"
    [ "$rc" -eq 0 ] || { echo "pre exit code $rc"; return 1; }
    bright "$d" post || { echo "post failed"; return 1; }
    [ "$(cat "$(amd "$d")")" = 1000 ] || { echo "value now: '$(cat "$(amd "$d")")'"; return 1; }
}
bright_no_backlights() {
    local d=$tmp/bl-empty; fake_backlight "$d" || return 1
    rm "$d/class/backlight/"*
    bright "$d" pre && bright "$d" post || return 1
    [ -z "$(ls -A "$d/run")" ] || { echo "records for nothing: $(ls -A "$d/run")"; return 1; }
}
bright_backlight_gone_at_post() {
    local d=$tmp/bl-gone; fake_backlight "$d" || return 1
    bright "$d" pre || return 1
    rm "$d/class/backlight/amdgpu_bl2"
    bright "$d" post
}
check "brightness: nvidia_ only in an exclusion, no actual_brightness" bright_names
check "brightness: exits 0 for unknown and no args" bright_args
check "brightness, pre: saves amdgpu_bl2, nothing nvidia-driven" bright_pre_saves
check "brightness: nvidia files never read or written" bright_nvidia_untouched
check "brightness, post: leftover nvidia record still touches nothing" bright_stale_nvidia_record
check "brightness, post: restores, removes the record" bright_post_restores
check "brightness, post: unchanged value is not written" bright_post_same_value_no_write
check "brightness, post: no record, no write" bright_post_no_record_no_write
check "brightness, pre: creates a missing run dir" bright_makes_run_dir
check "brightness: run dir impossible, still exit 0" bright_no_run_dir_exit_0
check "brightness, no backlights: exit 0, no records" bright_no_backlights
check "brightness, post: backlight gone, still exit 0" bright_backlight_gone_at_post
if [ "$(id -u)" -ne 0 ]; then # root reads and writes through these modes
    check "brightness, pre: read-only record, still exit 0" bright_readonly_record_exit_0
    check "brightness, post: read-only brightness, still exit 0" bright_readonly_brightness_exit_0
    check "brightness: failed read never clobbers the value" bright_failed_read_never_clobbers
fi

# --- section H: read only. Nothing here starts a browser or a WebEngineView; test_poster.py fakes the browser.
qml_code() { sed -e '/^[[:space:]]*\/\//d' -e 's/[[:space:]]\/\/ .*//' "$WEBMODE"; }
webmode_console() { # both WebGL strings set the flag that outlives a reload: the GPU stays off for the process's life
    local body
    body=$(qml_code | sed -n '/onJavaScriptConsoleMessage/,/noWebGL = true/p')
    for want in 'WebGL context could not be created' 'Error creating WebGL context' 'noWebGL = true'; do
        printf '%s\n' "$body" | grep -qF "$want" || { echo "console handler has no: $want"; return 1; }
    done
    if qml_code | grep -q InfoMessageLevel; then echo "Info-level js: lines are dropped from the journal"; return 1; fi
}
webmode_renderer() { # a normal exit is ignored, an abnormal one shows the poster and then reloads
    local body
    body=$(qml_code | sed -n '/onRenderProcessTerminated/,/^        }/p')
    printf '%s\n' "$body" | grep -A1 'status === WebEngineView.NormalTerminationStatus' | grep -q return \
        || { echo "NormalTerminationStatus is not ignored"; return 1; }
    printf '%s\n' "$body" | awk '
        /NormalTerminationStatus/ { normal = 1 }
        normal && /rendererDead = true/ { dead = 1 }
        dead && /revive\.restart\(\)/ { ok = 1 }
        END { exit !ok }' || { echo "no poster, then reload, after the normal check: $body"; return 1; }
    qml_code | grep -A3 'id: revive' | grep -qE 'onTriggered:.*web\.reload\(\)' || { echo "the timer does not reload"; return 1; }
    qml_code | grep -A3 'id: revive' | grep -qE 'interval: *[1-9][0-9]{2,}' || { echo "no delay before the reload"; return 1; }
}
webmode_recovery() { # a successful load clears a dead renderer, never a missing GPU; a new URL clears both
    local load source
    load=$(qml_code | sed -n '/onLoadingChanged/,/lively.ready/p')
    printf '%s\n' "$load" | grep -q 'rendererDead = false' || { echo "a reload does not bring the page back"; return 1; }
    if printf '%s\n' "$load" | grep -q 'noWebGL = false'; then echo "the WebGL error comes before LoadSucceeded, this clears it"; return 1; fi
    source=$(qml_code | sed -n '/onWebSourceChanged/,/^    }/p')
    for want in revive.stop 'noWebGL = false' 'rendererDead = false'; do
        printf '%s\n' "$source" | grep -qF "$want" || { echo "a new URL does not: $want"; return 1; }
    done
}
webmode_covers_the_view() {
    qml_code | grep -qE 'visible: *!webRoot\.failed' || { echo "the web view is not hidden"; return 1; }
    qml_code | grep -q PreserveAspectCrop || { echo "no PreserveAspectCrop"; return 1; }
    qml_code | grep -A2 'function logFailure' | grep -q '!webRoot.failed' || { echo "does not log once"; return 1; }
}
webmode_lookup_order() { # poster.png first; the Lively thumbnail only when the poster failed to load
    qml_code | grep -qF 'webRoot.thumbnailUrl || webRoot.pageDir + "poster.png"' || { echo "poster.png is not the first choice"; return 1; }
    qml_code | grep -A1 'status === Image.Error && !webRoot.thumbnailUrl' | grep -q 'thumbnail.read()' || { echo "thumbnail not limited to a failed poster.png"; return 1; }
    qml_code | sed -n '/function read()/,/^        }/p' | grep -q 'LivelyInfo.json' || { echo "not read from LivelyInfo.json"; return 1; }
    qml_code | sed -n '/function read()/,/^        }/p' | grep -q 'Thumbnail' || { echo "no Thumbnail in the lookup"; return 1; }
}
check "WebMode: both console strings set the lasting flag, js: lines kept" webmode_console
check "WebMode: normal renderer exit ignored, abnormal shows the poster then reloads" webmode_renderer
check "WebMode: load clears a dead renderer only, new URL clears both" webmode_recovery
check "WebMode: poster covers the hidden view, cropped, logged once" webmode_covers_the_view
check "WebMode: looks up poster.png, then LivelyInfo Thumbnail" webmode_lookup_order

# --- flags
has_flags() { # file flag...
    local f=$1 flag; shift
    for flag in "$@"; do grep -qF -e "$flag" "$f" || { echo "$f has no $flag"; return 1; }; done
}
check "$POLICY has --apply/--check/--revert" has_flags "$POLICY" --apply --check --revert
check "$INSTALL has --install/--check/--revert" has_flags "$INSTALL" --install --check --revert

# --- exit codes. Another worker's scripts run here, so sudo is stubbed out and they get a time limit.
mkdir "$tmp/bin" && printf '#!/bin/sh\nexit 1\n' >"$tmp/bin/sudo" && chmod +x "$tmp/bin/sudo"
run() { # run script args...: through its shebang, the installer sets the exec bit and the repo copy may lack it
    local shebang; read -r shebang <"$1" || return 127
    PATH=$tmp/bin:$PATH timeout 30 ${shebang#\#!} "$@" >"$tmp/run" 2>&1
}
exit_code_ok() { # exit_code_ok script: ran to a verdict rather than crashing
    local rc=0
    run "$1" --check || rc=$?
    cat "$tmp/run"
    if grep -q Traceback "$tmp/run" || [ "$rc" -ge 124 ]; then echo "crashed, rc=$rc"; return 1; fi
    echo "rc=$rc"
}
rejects_unknown() { ! run "$1" --bogus; }
installer_tells_truth() { # the lid script is not deployed, so --check cannot say all is well
    cmp -s "$LID" /usr/local/bin/luminos-lid && { echo "deployed, nothing to compare"; return 0; }
    ! run "$INSTALL" --check
}
for f in "$POLICY" "$INSTALL"; do
    check "$f --check runs to a verdict" exit_code_ok "$f"
    check "$f rejects an unknown flag" rejects_unknown "$f"
done
check "$INSTALL --check fails while v3 is not deployed" installer_tells_truth

# Re-plan 3: never run --install here. --check also calls is-active, so look inside install_all only.
install_checks_liveness() {
    sed -n '/^install_all()/,/^}/p' "$INSTALL" | awk '
        /restart luminos-lid/ { restarted = 1 }
        restarted && /sleep +[2-9]/ { waited = 1 }
        waited && /is-active.*luminos-lid/ { checked = 1 }
        checked && /exit 1/ { ok = 1 }
        END { exit !ok }'
}
check "--install: lid active 2 s after restart, else exit 1" install_checks_liveness

# Re-plan 6: same rule, --install and --revert are only read. The old unit must be disabled while it still exists.
function_of() { sed -n "/^$2()/,/^}/p" "$1"; }
install_has_brightness() {
    grep -qE '^ +"755 config/system-sleep/luminos-brightness ' "$INSTALL" || { echo "hook not in FILES"; return 1; }
    local away # the moved-aside name, literal or through the variable holding it
    away=$(sed -n 's/^\([A-Z_]*\)=.*\.disabled-by-strong-sleep"\{0,1\}$/\1/p' "$INSTALL")
    away="disabled-by-strong-sleep${away:+|$away}"
    function_of "$INSTALL" install_all | awk -v away="mv .*($away)\"?\$" '
        /disable.*luminos-brightness/ { disabled = 1 }
        disabled && $0 ~ away { ok = 1 }
        END { exit !ok }' || { echo "--install: no disable, then move aside"; return 1; }
    function_of "$INSTALL" revert | grep -qE "mv( -f)? \"?[^ ]*($away)\"? " || { echo "--revert does not move the unit back"; return 1; }
    function_of "$INSTALL" revert | grep -qE 'enable.*luminos-brightness' || { echo "--revert does not enable it again"; return 1; }
    function_of "$INSTALL" revert | grep -E '^ +rm ' | grep -qiE 'bright' || { echo "--revert leaves the new hook behind"; return 1; }
}
check "$INSTALL retires luminos-brightness.service, --revert restores it" install_has_brightness

# Re-plan 3: ask the policy itself which USB devices it targets, on the real sysfs (--check only reads).
policy_skips_hubs_and_keyboard() {
    local table usb vendor
    run "$POLICY" --check
    table=$(grep -oE '/sys/bus/usb/devices/[^/]+' "$tmp/run" | sort -u)
    for usb in $table; do
        vendor=$(cat "$usb/idVendor")
        case "$vendor" in 0b05|1d6b) echo "$usb ($vendor) is a target"; return 1 ;; esac
    done
    grep -qE 'PNP0C0D' "$tmp/run" || { echo "no table from --check"; return 1; }
}
check "$POLICY does not target root hubs or 0b05" policy_skips_hubs_and_keyboard
check "$POLICY names 1d6b" grep -q 1d6b "$POLICY"

# Re-plan 4: changing a PCIe bridge's wakeup re-wakes the dGPU at every sleep.
policy_targets_as_contracted() {
    run "$POLICY" --check
    if grep -E '0000:00:(01\.1|02\.2|03\.1)' "$tmp/run"; then echo "a bridge is a target"; return 1; fi
    local want
    for want in 0000:65:00.5 0000:67:00.5 ACAD PNP0C0D PNP0C0C; do
        grep -qF "$want" "$tmp/run" || { echo "$want is not in the table"; return 1; }
    done
}
check "$POLICY targets no PCIe bridge, and everything it should" policy_targets_as_contracted

# --- pure core
PYTHONDONTWRITEBYTECODE=1 HYPOTHESIS_STORAGE_DIRECTORY=$tmp/hypothesis \
    timeout 300 "$PY" -m pytest -q -p no:cacheprovider --show-capture=no --tb=short \
    tests/sleep/test_lid.py tests/sleep/test_png_stats.py tests/sleep/test_poster.py
if [ $? -eq 0 ]; then pass "pytest tests/sleep"; else fail "pytest tests/sleep"; fi
check "broken copies of luminos-lid fail the tests" timeout 600 "$PY" tests/sleep/mutate.py

echo
if [ "$fails" -eq 0 ]; then echo "static.sh: all passed"; else echo "static.sh: $fails failed"; exit 1; fi
