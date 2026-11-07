#!/usr/bin/env bash
# tests/sleep/live.sh — live checks for CONTRACTS.md sections B-E. PM only, after luminos-strong-sleep --install:
#   sudo bash tests/sleep/live.sh
# NEVER suspends. It does unbind and rebind the SD reader once, so it refuses to run that part with a card inserted,
# and moves the panel brightness by 1 % for a moment. Takes about 70 s: the SD reader's re-bind is deferred 60 s.
# [CHANGE: claude-code | 2026-11-06]
set -u
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 2; }
cd "$(dirname "$0")/../.." || exit 2

HOOK=/usr/lib/systemd/system-sleep/luminos-sdreader
DRV=/sys/bus/platform/drivers/rtsx_pci_sdmmc
DEV=rtsx_pci_sdmmc.0
RECORD=/run/luminos/sdreader-unbound
TIMER=luminos-sdreader-rebind.timer
BRIGHT_HOOK=/usr/lib/systemd/system-sleep/luminos-brightness
BACKLIGHT=/sys/class/backlight/amdgpu_bl2
BRIGHT_RECORD=/run/luminos/brightness-amdgpu_bl2
GPU=/sys/bus/pci/devices/0000:01:00.0/power
fails=0

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
is() { # is "what" actual expected
    if [ "$2" = "$3" ]; then pass "$1 = $2"; else fail "$1 = '$2', want '$3'"; fi
}

# --- wake policy
if /usr/local/bin/luminos-wake-policy --check; then pass "luminos-wake-policy --check"; else fail "luminos-wake-policy --check"; fi
if systemctl is-enabled -q luminos-wake-policy; then pass "luminos-wake-policy enabled"; else fail "luminos-wake-policy not enabled"; fi

for pci in 0000:65:00.5 0000:67:00.5; do
    is "$pci wakeup" "$(cat "/sys/bus/pci/devices/$pci/power/wakeup")" disabled
done
is "ACAD wakeup" "$(cat /sys/class/power_supply/ACAD/power/wakeup)" disabled
is "lid PNP0C0D wakeup" "$(cat /sys/bus/platform/devices/PNP0C0D:00/power/wakeup)" enabled
is "power button PNP0C0C wakeup" "$(cat /sys/bus/platform/devices/PNP0C0C:00/power/wakeup)" enabled

for usb in /sys/bus/usb/devices/*; do
    [ -f "$usb/idVendor" ] || continue
    vendor=$(cat "$usb/idVendor")
    # no file or an empty one: the device cannot wake anything, so there is nothing to disable
    wakeup=$(cat "$usb/power/wakeup" 2>/dev/null)
    [ -n "$wakeup" ] || continue
    case "$vendor" in
        # Re-plan 3: not targets. Stock value varies, so show it; the policy leaving them alone is checked below.
        0b05|1d6b) echo "NOTE usb ${usb##*/} ($vendor) left as it is: $wakeup" ;;
        *) is "usb ${usb##*/} ($vendor:$(cat "$usb/idProduct")) wakeup" "$wakeup" disabled ;;
    esac
done
# Re-plan 3 and 4: root hubs and PCIe bridges are not targets. Changing a bridge's wakeup re-wakes the dGPU at sleep.
HANDS_OFF='/usb[0-9]+/power|/0000:00:(01\.1|02\.2|03\.1)/power'
if /usr/local/bin/luminos-wake-policy --check | grep -qE "$HANDS_OFF"; then
    fail "wake policy targets a root hub or PCIe bridge"
else
    pass "wake policy leaves root hubs and PCIe bridges alone"
fi
if grep -qE "$HANDS_OFF" /var/lib/luminos/wake-policy.orig 2>/dev/null; then
    fail "wake-policy.orig holds a root hub or bridge: an older policy touched it, reboot or restore it first"
else
    pass "wake-policy.orig holds no root hubs or bridges"
fi

timer_on() { systemctl is-active -q "$TIMER"; }
timer_off() { ! timer_on; }
eventually() { # the hook's systemd-run and stop are --no-block
    local _
    for _ in 1 2 3 4 5 6 7 8 9 10; do "$@" && return 0; sleep 0.2; done
    return 1
}

# --- whatever happens, the reader ends up bound and the brightness where it was
rebind() { systemctl stop "$TIMER" 2>/dev/null; [ -e "$DRV/$DEV" ] || echo "$DEV" >"$DRV/bind"; rm -f "$RECORD"; }
cleanup() {
    [ -z "$brightness_was" ] || echo "$brightness_was" >"$BACKLIGHT/brightness"
    rm -f "$BRIGHT_RECORD"
    [ -z "$sd_touched" ] || rebind
}
brightness_was="" sd_touched=""
trap cleanup EXIT

# --- section F: brightness round trip, a 1 % change on the internal panel only. nvidia_0 is never read: that would
# wake the dGPU, which is the whole point of the hook.
is "brightness hook matches repo" "$(cmp -s config/system-sleep/luminos-brightness "$BRIGHT_HOOK" && echo same)" same
if systemctl is-enabled -q luminos-brightness.service 2>/dev/null; then
    fail "luminos-brightness.service is still enabled"
else
    pass "luminos-brightness.service not enabled"
fi
if [ -e /etc/systemd/system/luminos-brightness.service ]; then fail "old unit file still in place"; else pass "old unit file moved away"; fi
if [ -e /etc/systemd/system/luminos-brightness.service.disabled-by-strong-sleep ]; then pass "old unit kept for --revert"; else fail "old unit not kept for --revert"; fi

gpu_was=$(cat "$GPU/runtime_status")
gpu_active_was=$(cat "$GPU/runtime_active_time")
now=$(cat "$BACKLIGHT/brightness")
max=$(cat "$BACKLIGHT/max_brightness")
step=$((max / 100))
if [ "$now" -gt "$step" ]; then changed=$((now - step)); else changed=$((now + step)); fi
brightness_was=$now
sh "$BRIGHT_HOOK" pre suspend
is "brightness pre exit code" "$?" 0
is "brightness saved" "$(cat "$BRIGHT_RECORD" 2>/dev/null)" "$now"
if compgen -G '/run/luminos/brightness-*nvidia*' >/dev/null; then fail "an nvidia backlight was saved"; else pass "no nvidia backlight saved"; fi
echo "$changed" >"$BACKLIGHT/brightness"
is "brightness changed for the test" "$(cat "$BACKLIGHT/brightness")" "$changed"
sh "$BRIGHT_HOOK" post suspend
is "brightness post exit code" "$?" 0
is "brightness restored" "$(cat "$BACKLIGHT/brightness")" "$now"
if [ -e "$BRIGHT_RECORD" ]; then fail "brightness record left behind"; else pass "brightness record removed"; fi
if [ "$gpu_was" = suspended ]; then
    is "dGPU stayed asleep through the hook" "$(cat "$GPU/runtime_status")" suspended
    is "dGPU active time did not move" "$(cat "$GPU/runtime_active_time")" "$gpu_active_was"
else
    echo "NOTE dGPU was $gpu_was at the start, cannot tell whether the hook woke it"
fi

# --- SD reader round trip
if compgen -G '/dev/mmcblk*' >/dev/null; then
    fail "SD round trip not run: remove the SD card and run again"
elif [ ! -e "$DRV/$DEV" ]; then
    fail "SD round trip not run: $DEV is not bound to start with (just woke? its re-bind takes 60 s, run again after that)"
else
    sd_touched=1
    sh "$HOOK" pre suspend
    is "hook pre exit code" "$?" 0
    if [ -e "$DRV/$DEV" ]; then fail "pre: $DEV still bound"; else pass "pre: $DEV unbound"; fi
    if [ -e "$RECORD" ]; then pass "pre: recorded in $RECORD"; else fail "pre: no record in $RECORD"; fi

    # Re-plan 7: post only schedules the bind
    sh "$HOOK" post suspend
    is "hook post exit code" "$?" 0
    if [ -e "$DRV/$DEV" ]; then fail "post: $DEV bound right away"; else pass "post: $DEV still unbound"; fi
    if [ -e "$RECORD" ]; then pass "post: record kept until the bind"; else fail "post: record gone before the bind"; fi
    if eventually timer_on; then pass "post: $TIMER exists"; else fail "post: no $TIMER"; fi

    # the lid shuts again inside the minute: pre cancels and does nothing else, fast
    started=$(date +%s%N)
    sh "$HOOK" pre suspend
    code=$? took=$((($(date +%s%N) - started) / 1000000))
    is "second pre exit code" "$code" 0
    if [ "$took" -le 2000 ]; then pass "second pre took $took ms"; else fail "second pre took $took ms, want <= 2000"; fi
    if eventually timer_off; then pass "second pre: $TIMER cancelled"; else fail "second pre: $TIMER not cancelled"; fi
    if [ -e "$DRV/$DEV" ]; then fail "second pre: $DEV bound"; else pass "second pre: $DEV still unbound"; fi
    if [ -e "$RECORD" ]; then pass "second pre: record kept"; else fail "second pre: record gone"; fi

    sh "$HOOK" post suspend
    is "second post exit code" "$?" 0
    if eventually timer_on; then pass "second post: $TIMER exists"; else fail "second post: no $TIMER"; fi

    echo "waiting up to 70 s for the re-bind"
    waited=0
    until [ -e "$DRV/$DEV" ] || [ "$waited" -ge 70 ]; do sleep 2; waited=$((waited + 2)); done
    if [ -e "$DRV/$DEV" ]; then pass "$DEV back under the driver after $waited s"; else fail "$DEV not re-bound after $waited s"; fi
    [ "$waited" -ge 50 ] || fail "$DEV re-bound after only $waited s, want about 60"
    sleep 2 # the service removes the record just after the bind
    if [ -e "$RECORD" ]; then fail "$RECORD left behind"; else pass "record removed"; fi
    if timer_on; then fail "$TIMER still there"; else pass "$TIMER gone"; fi
fi

# --- lid supervisor: the running one, not just the file on disk
if cmp -s scripts/luminos-lid /usr/local/bin/luminos-lid; then pass "deployed luminos-lid matches repo"; else fail "deployed luminos-lid differs from repo"; fi
if [ -e /usr/local/bin/luminos-lid.pre-v3 ]; then pass "old luminos-lid backed up"; else fail "no luminos-lid.pre-v3 backup"; fi
if systemctl is-active -q luminos-lid; then pass "luminos-lid active"; else fail "luminos-lid not active"; fi
invocation=$(systemctl show -p InvocationID --value luminos-lid)
if journalctl --no-pager -o cat "_SYSTEMD_INVOCATION_ID=$invocation" | grep -q v3; then
    pass "journal shows a v3 line"
else
    fail "journal of this luminos-lid run has no line containing v3"
fi

echo
if [ "$fails" -eq 0 ]; then echo "live.sh: all passed"; else echo "live.sh: $fails failed"; exit 1; fi
