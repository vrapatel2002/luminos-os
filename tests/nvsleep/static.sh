#!/usr/bin/env bash
# nvsleep v2.1 static checks (no reboot, no root, never touches the GPU). Exit 0 only if every check passes.
# [CHANGE: claude-code | 2026-11-06]
# NVSLEEP_COMPILE=1 also builds the patched tree. NVSLEEP_PATCH / NVSLEEP_SCRIPT: self-test overrides only.
# ---- budgets and rules (docs/sleep/DESIGN-NVSLEEP-V2.md, v2.1 section) ----
MAX_ADDED=190; MAX_SCRIPT_LINES=200; MAX_FN_LINES=40; MAX_NESTING=3
ALLOWED='^kernel-open/nvidia/(nv\.c|nv-acpi\.c|nv-pci\.c)$'   # nv-pci.c only to wire .prepare
FORBIDDEN='pm_runtime_(disable|enable|set_active|set_suspended|forbid|allow)\b|pci_(save_state|restore_state|set_power_state)\b|\bdpm_[a-zA-Z_]+|device_set_pm_not_required\b|dev_pm_set_driver_flags\b|\bacpi_device_set_power\b|\bacpi_power_[a-z_]+'
V1_FLAGS='DPM_FLAG_(SMART_SUSPEND|MAY_SKIP_RESUME)'
STOCK_ONLY='\bnv_(suspend|resume)_devices\b'                  # moved or re-indented stock calls are fine, new ones are not
# ---------------------------------------------------
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd); FAIL=0
BASE=$REPO/patches/nvdefer/work
PATCH=${NVSLEEP_PATCH:-$REPO/patches/nvsleep/nvsleep-610.57.04.patch}
SCRIPT=${NVSLEEP_SCRIPT:-$REPO/scripts/luminos-nvidia-defer}
res() { printf '%-4s %-22s %s\n' "$1" "$2" "$3"; [[ $1 == PASS ]] || FAIL=1; }
chk() { if eval "$2"; then res PASS "$1" "$3"; else res FAIL "$1" "$3"; fi; }

code_only() {   # stdin with C comments removed, so a comment naming a forbidden call does not count
    awk '{ s = $0 }
        c { if (sub(/^.*\*\//, "", s)) c = 0; else next }
        { gsub(/\/\*[^*]*\*\//, "", s); sub(/\/\/.*/, "", s); if (sub(/\/\*.*/, "", s)) c = 1; print s }'
}
changed_in() {  # changed_in <file>: added and removed lines of that file, without the +/-
    awk -v f="$1" '/^\+\+\+ / { on = ($2 == "b/" f || $2 == f); next } /^--- / { next } on && /^[-+]/ { print substr($0, 2) }' "$PATCH"
}
# "count longest deepest" over the C functions the patch adds. A brace matched to a context line still closes the function.
fn_stats() {
    awk '
        !in_fn && (/^\+\{/ || /^\+[A-Za-z_].*\)[ \t]*\{[ \t]*$/) { in_fn = 1; fns++; lines = depth = peak = 0 }
        in_fn && /^[+ ]/ {
            l = $0; o = gsub(/\{/, "{", l); e = gsub(/\}/, "}", l)
            lines++; depth += o; if (depth > peak) peak = depth; depth -= e
            if (depth <= 0) { in_fn = 0; if (lines > long) long = lines; if (peak - 1 > deep) deep = peak - 1 }
        }
        END { print fns + 0, long + 0, deep + 0 }' "$1"
}
# Text reachable from a case arm of the script: the arm plus the functions it calls, transitively.
fn_body() { awk -v f="$1()" 'index($0, f) == 1 { p = 1; print; if (/}[[:space:]]*$/) exit; next } p { print } p && /^}/ { exit }' "$SCRIPT"; }
reach() {
    local text f more=1 seen=" "
    text=$(grep -E -- "^[[:space:]]*$1\)" "$SCRIPT")
    while ((more)); do more=0
        for f in $(grep -oE '^[A-Za-z_][A-Za-z0-9_]*\(\)' "$SCRIPT" | tr -d '()'); do
            [[ $seen == *" $f "* ]] || ! grep -qw "$f" <<< "$text" && continue
            text+=$'\n'$(fn_body "$f"); seen+="$f "; more=1
        done
    done
    echo "$text"
}

# --- patch ---
if [[ ! -f $PATCH ]]; then res FAIL "patch file" "missing: $PATCH"
else
    res PASS "patch file" "$PATCH"
    FILES=$(grep -E '^\+\+\+ ' "$PATCH" | awk '{print $2}' | sed -E 's#^b/##')
    BAD=$(grep -vE "$ALLOWED" <<< "$FILES" | xargs)
    chk "patch file list" '[[ -n $FILES && -z $BAD ]]' "$(xargs <<< "$FILES")${BAD:+ — disallowed: $BAD}"
    ADD=$(grep -E '^\+' "$PATCH" | grep -vcE '^\+\+\+ ')
    chk "patch size" '((ADD <= MAX_ADDED))' "$ADD added lines (max $MAX_ADDED)"
    read -r H UNMARKED < <(awk '/^(diff |--- |\+\+\+ )/ { next } /^@@ / { if (h && !m) bad++; h++; m = 0; next }
        /^\+.*LUMINOS-NVSLEEP/ { m = 1 } END { if (h && !m) bad++; print h + 0, bad + 0 }' "$PATCH")
    chk "hunk markers" '((H > 0 && UNMARKED == 0))' "$H hunks, $UNMARKED without LUMINOS-NVSLEEP on an added line"
    ADDED=$(grep -vE '^\+\+\+ ' "$PATCH" | sed -n 's/^+//p')
    CODE=$(code_only <<< "$ADDED")
    REMOVED=$(grep -vE '^--- ' "$PATCH" | sed -n 's/^-//p' | code_only)
    chk "param skip_idle" 'grep -qE "^(static )?int nv_sleep_skip_idle[[:space:]]*=[[:space:]]*1;" <<< "$CODE" && grep -qE "module_param\(nv_sleep_skip_idle,[[:space:]]*int,[[:space:]]*0644\)" <<< "$CODE"' "int, 0644, default 1"
    chk "param skipped" 'grep -qE "module_param\(nv_sleep_skipped,[[:space:]]*ulong,[[:space:]]*0444\)" <<< "$CODE"' "ulong, 0444"
    read -r FN LONG DEEP < <(fn_stats "$PATCH")
    chk "fn budgets" '((LONG <= MAX_FN_LINES && DEEP <= MAX_NESTING))' "$FN new functions, longest $LONG lines (max $MAX_FN_LINES), nesting $DEEP (max $MAX_NESTING)"
    chk ".prepare op" 'grep -qE "\.prepare[[:space:]]*=" <<< "$CODE"' "added to nv_pm_ops"
    chk "prepare -EBUSY" 'grep -q -- "-EBUSY" <<< "$CODE"' "abort path, not -EAGAIN (main.c:2247 swallows it)"
    chk "no -EAGAIN" '! grep -q -- "-EAGAIN" <<< "$CODE"' "not in added code"
    chk "pm_system_wakeup" 'grep -qE "\bpm_system_wakeup\(" <<< "$CODE"' "race guard"
    HITS=$(grep -oE "$V1_FLAGS" <<< "$CODE" | sort -u | xargs)
    chk "no v1 flags" '[[ -z $HITS ]]' "${HITS:-no DPM_FLAG_SMART_SUSPEND / MAY_SKIP_RESUME added}"
    HITS=$(grep -oE "$FORBIDDEN" <<< "$CODE" | sort -u | xargs)
    chk "no forbidden calls" '[[ -z $HITS ]]' "${HITS:-none in added code}"
    HITS=$(comm -23 <(grep -oE "$STOCK_ONLY" <<< "$CODE" | sort) <(grep -oE "$STOCK_ONLY" <<< "$REMOVED" | sort) | sort -u | xargs)
    chk "no new stock calls" '[[ -z $HITS ]]' "${HITS:-no new nv_suspend_devices / nv_resume_devices}"
    T1=$(grep -cE 'dev_pm_syscore_device\([^,]*,[[:space:]]*(true|TRUE|NV_TRUE)[[:space:]]*\)' <<< "$CODE")
    F1=$(grep -cE 'dev_pm_syscore_device\([^,]*,[[:space:]]*(false|FALSE|NV_FALSE)[[:space:]]*\)' <<< "$CODE")
    V1=$(grep -E 'dev_pm_syscore_device\(' <<< "$CODE" | grep -vcE ',[[:space:]]*(true|TRUE|NV_TRUE|false|FALSE|NV_FALSE)[[:space:]]*\)')
    chk "syscore true+false" '((T1 + V1 > 0 && F1 + V1 > 0))' "literal true $T1, false $F1, variable arg $V1$( ((V1)) && echo ' (a walker passing the value: both values not proven here, the live control run checks it)')"
    chk "pci refs dropped" '! grep -qE "pci_get_(slot|domain_bus_and_slot)" <<< "$CODE" || grep -q pci_dev_put <<< "$CODE"' "every pci_get_* patch also has pci_dev_put"
    ACPI=$(changed_in kernel-open/nvidia/nv-acpi.c | code_only)
    chk "nv-acpi.c gated" 'grep -q nv_sleep_skipping <<< "$ACPI"' "ACPI handlers look at nv_sleep_skipping (v2.1 item 2)"
    PCIW=$(changed_in kernel-open/nvidia/nv-pci.c | code_only | grep -vE '^[[:space:]]*(#.*)?$' | grep -v prepare | head -3 | paste -sd ';')
    chk "nv-pci.c wiring only" '[[ -z $PCIW ]]' "${PCIW:-no change, or only .prepare wiring}"

    TMP=$(mktemp -d "${TMPDIR:-/var/tmp}/nvsleep-static.XXXXXX"); trap 'rm -rf "$TMP"' EXIT
    W=$TMP/work; cp -a "$BASE" "$W"
    if OUTP=$(cd "$W" && patch -p1 -F0 --no-backup-if-mismatch -s -f < "$PATCH" 2>&1); then
        res PASS "patch applies" "patch -p1 -F0 on a fresh copy of patches/nvdefer/work"
        TOUCHED=$(diff -rq --no-dereference "$BASE" "$W" | sed -E "s#^Files .* and $W/(.*) differ\$#\1#; s#^Only in $W/?(.*): (.*)\$#\1/\2 (new)#" | xargs)
        OTHER=$(tr ' ' '\n' <<< "$TOUCHED" | grep -vE "$ALLOWED" | xargs)
        chk "only allowed files" '[[ -n $TOUCHED && -z $OTHER ]]' "changed: $TOUCHED"
        chk "NO_DIRECT_COMPLETE" 'grep -q "DPM_FLAG_NO_DIRECT_COMPLETE" "$W/kernel-open/nvidia/nv-pci.c"' "still set in nv-pci.c"
        if [[ ${NVSLEEP_COMPILE:-0} == 1 ]]; then
            WRE='nvidia/nv(-pci|-acpi)?\.c:[0-9]+:[0-9]+: warning:'
            make -C "$W" -j"$(nproc)" modules > "$TMP/build.log" 2>&1; rc=$?
            chk "compile" '((rc == 0))' "make modules rc=$rc$( ((rc)) && echo ": $(grep -m3 -E 'error|Error' "$TMP/build.log" | paste -sd ';')")"
            WN=$(grep -cE "$WRE" "$TMP/build.log"); WB=$(grep -cE "$WRE" "$REPO/patches/nvdefer/build.log")
            chk "no new warnings" '((WN <= WB))' "nv.c + nv-acpi.c + nv-pci.c warnings: $WN (nvdefer baseline $WB)"
        else echo "SKIP compile                NVSLEEP_COMPILE=1 to build"; fi
    else
        res FAIL "patch applies" "patch -p1 -F0: $(grep -iE 'fail|reject|error|reversed|can.t find|missing' <<< "$OUTP" | head -3 | paste -sd ';')"
    fi
fi

# --- apply/revert script ---
if [[ ! -f $SCRIPT ]]; then res FAIL "script" "missing: $SCRIPT"
else
    E=$(bash -n "$SCRIPT" 2>&1); chk "script syntax" '[[ -z $E ]]' "${E:-bash -n clean}"
    L=$(wc -l < "$SCRIPT"); chk "script size" '((L <= MAX_SCRIPT_LINES))' "$L lines (max $MAX_SCRIPT_LINES)"
    NVVARS=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=.*nvsleep' "$SCRIPT" | cut -d= -f1 | paste -sd '|')
    for o in --apply --revert --check; do
        T=$(reach "$o")
        chk "script $o" 'grep -q nvsleep <<< "$T" || { [[ -n $NVVARS ]] && grep -qE "\\$\{?($NVVARS)\b" <<< "$T"; }' "mentions nvsleep"
    done
    T=$(reach --check)
    chk "script --check parms" 'grep -q nv_sleep_skip_idle <<< "$T" && grep -q nv_sleep_skipped <<< "$T"' "reports both loaded params"
fi
echo; ((FAIL == 0)) && echo "static: ALL PASS" || echo "static: FAILED"
exit $FAIL
