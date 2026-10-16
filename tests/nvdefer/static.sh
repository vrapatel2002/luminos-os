#!/usr/bin/env bash
# nvdefer static checks (no reboot, no root, never touches the GPU). Exit 0 only if every check passes.
# ---- budgets (docs/nvdefer/CONTRACTS.md, Re-plan 1) ----
MAX_ADDED=180; MAX_SCRIPT_LINES=150
ALLOWED='^kernel-open/nvidia/(nv-acpi\.c|nv\.c|nv-linux\.h)$'   # + a NEW header under kernel-open/nvidia/
# ---------------------------------------------------
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd); FAIL=0
res() { printf '%-4s %-22s %s\n' "$1" "$2" "$3"; [[ $1 == PASS ]] || FAIL=1; }
# Every `patch` command line must carry fuzz 0: literally (-F0, -F 0, --fuzz=0) or by expanding a variable/array whose
# assignment contains it (e.g. PATCH_OPTS=(-p1 -F0 ...); patch "${PATCH_OPTS[@]}"). FAIL if any call lacks it.
FZ='(-F[[:space:]]*0|--fuzz[= ]0)([^0-9]|$)'
fuzz0_check() {
    local code vars v line n=0 bad=""
    code=$(grep -vE '^[[:space:]]*#' "$1")
    vars=$(grep -E '^[[:space:]]*(local[[:space:]]+|readonly[[:space:]]+|declare[^=]*[[:space:]])?[A-Za-z_][A-Za-z0-9_]*=' <<< "$code" \
        | grep -E "$FZ" | sed -E 's/^[[:space:]]*(local|readonly|declare[^=]*)?[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=.*/\2/' | sort -u)
    while IFS= read -r line; do
        n=$((n + 1)); grep -qE "$FZ" <<< "$line" && continue
        for v in $vars; do grep -qE "\\\$(\{)?$v([^A-Za-z0-9_]|$)" <<< "$line" && continue 2; done
        bad+="[$(sed -E 's/^[[:space:]]+//' <<< "$line" | cut -c1-60)] "
    done < <(grep -E '(^|[;&|(!]|\bif|\bthen|\bdo|\belse)[[:space:]]*patch[[:space:]]' <<< "$code")
    if ((n == 0)); then res FAIL "script patch -F0" "no patch call found"
    elif [[ -n $bad ]]; then res FAIL "script patch -F0" "patch call(s) without fuzz 0: $bad"
    else res PASS "script patch -F0" "all $n patch call(s) use fuzz 0${vars:+ (via: $(echo $vars))}"; fi
}
VER=$(pacman -Q nvidia-open-dkms 2>/dev/null | awk '{print $2}' | sed 's/-[^-]*$//')
SRC=/usr/src/nvidia-$VER; PATCH=${NVDEFER_PATCH:-$REPO/patches/nvdefer/nvdefer-$VER.patch}  # env override: self-test only
SCRIPT=$REPO/scripts/luminos-nvidia-defer; HOOK=$REPO/config/pacman-hooks/80-luminos-nvidia-defer.hook; OLDHOOK=$REPO/config/pacman-hooks/luminos-nvidia-defer.hook
[[ -n $VER && -d $SRC ]] && res PASS "driver source" "$SRC" || res FAIL "driver source" "missing (nvidia-open-dkms '$VER')"

# --- patch ---
if [[ ! -f $PATCH ]]; then res FAIL "patch file" "missing: $PATCH"
else
    res PASS "patch file" "$PATCH"
    FILES=$(grep -E '^\+\+\+ ' "$PATCH" | awk '{print $2}' | sed -E 's#^b/##')
    OLDS=$(grep -E '^--- ' "$PATCH" | awk '{print $2}')
    BAD=""; NEW=""
    while read -r f; do [[ -z $f ]] && continue
        [[ $f =~ $ALLOWED ]] && continue
        if [[ $f =~ ^kernel-open/nvidia/[A-Za-z0-9_-]+\.h$ ]] && [[ ! -e $SRC/$f ]]; then NEW+="$f "; continue; fi
        BAD+="$f "
    done <<< "$FILES"
    [[ -n $FILES && -z $BAD ]] && res PASS "patch file list" "$(echo $FILES)${NEW:+ (new: $NEW)}" \
        || res FAIL "patch file list" "${BAD:+disallowed: $BAD}$([[ -z $FILES ]] && echo 'no files found in patch')"
    grep -qE '^(\+\+\+|---) (a/|b/)?src/' "$PATCH" && res FAIL "no RM core" "patch touches src/" || res PASS "no RM core" "src/ untouched"
    ADD=$(grep -E '^\+' "$PATCH" | grep -vcE '^\+\+\+ ')
    ((ADD <= MAX_ADDED)) && res PASS "patch size" "$ADD added lines (max $MAX_ADDED)" || res FAIL "patch size" "$ADD added lines > $MAX_ADDED"
    if [[ -d $SRC ]]; then
        TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
        cp -a "$SRC/kernel-open" "$TMP/"
        # if --apply already patched /usr/src, test against the pristine copies it keeps
        for o in $(cd "$TMP" && find kernel-open -name '*.nvdefer-orig'); do cp "$TMP/$o" "$TMP/${o%.nvdefer-orig}"; done
        OUTP=$(cd "$TMP" && patch -p1 --dry-run --batch < "$PATCH" 2>&1); rc=$?
        ((rc == 0)) && res PASS "patch applies" "dry-run clean on $SRC (pristine)" \
            || res FAIL "patch applies" "patch -p1 --dry-run rc=$rc: $(echo "$OUTP" | grep -iE 'fail|reject|error|reversed|can.t find|missing' | head -3 | paste -sd ';')"
    else res FAIL "patch applies" "missing source tree"; fi
fi

# --- apply/revert script ---
if [[ ! -f $SCRIPT ]]; then res FAIL "script" "missing: $SCRIPT"
else
    L=$(wc -l < "$SCRIPT")
    ((L <= MAX_SCRIPT_LINES)) && res PASS "script size" "$L lines (max $MAX_SCRIPT_LINES)" || res FAIL "script size" "$L lines > $MAX_SCRIPT_LINES"
    E=$(bash -n "$SCRIPT" 2>&1) && res PASS "script syntax" "bash -n clean" || res FAIL "script syntax" "$E"
    MISS=""; for o in --install --apply --revert --check; do grep -q -- "$o" "$SCRIPT" || MISS+="$o "; done
    [[ -z $MISS ]] && res PASS "script options" "--install --apply --revert --check" || res FAIL "script options" "missing: $MISS"
    grep -vE '^[[:space:]]*#' "$SCRIPT" | grep -qE 'mkinitcpio[[:space:]]+-P' && res PASS "script mkinitcpio" "calls mkinitcpio -P" || res FAIL "script mkinitcpio" "no mkinitcpio -P call"
    fuzz0_check "$SCRIPT"
    [[ -x $SCRIPT ]] && res PASS "script executable" "+x" || res FAIL "script executable" "not executable"
fi

# --- pacman hook ---
if [[ ! -f $HOOK ]]; then res FAIL "pacman hook" "missing: $HOOK"
else
    MISS=""
    grep -qE '^[[:space:]]*Target[[:space:]]*=[[:space:]]*nvidia-open-dkms[[:space:]]*$' "$HOOK" || MISS+="Target=nvidia-open-dkms "
    grep -qE '^[[:space:]]*When[[:space:]]*=[[:space:]]*PostTransaction' "$HOOK" || MISS+="When=PostTransaction "
    grep -qE '^[[:space:]]*Exec[[:space:]]*=.*LUMINOS_FROM_HOOK=1.*/usr/local/bin/luminos-nvidia-defer[[:space:]]+--apply' "$HOOK" \
        || MISS+="Exec=...LUMINOS_FROM_HOOK=1 .../usr/local/bin/luminos-nvidia-defer --apply "
    [[ -z $MISS ]] && res PASS "pacman hook" "80- name, targets nvidia-open-dkms, PostTransaction, LUMINOS_FROM_HOOK=1 + --apply" || res FAIL "pacman hook" "missing: $MISS"
fi
[[ -e $OLDHOOK ]] && res FAIL "old hook gone" "$OLDHOOK still exists" || res PASS "old hook gone" "luminos-nvidia-defer.hook absent"
echo; ((FAIL == 0)) && echo "static: ALL PASS" || echo "static: FAILED"
exit $FAIL
