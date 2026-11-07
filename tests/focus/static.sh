#!/usr/bin/env bash
# [CHANGE: claude-code | 2026-11-07] luminos-focus static gate: tests, vet, gofmt and the CONTRACTS budgets.
# Prints PASS/FAIL per check; exits non-zero if any check fails.
cd "$(dirname "$0")/../.." || exit 2
export GOFLAGS=-mod=mod GOPROXY=off
D=cmd/luminos-focus
JS=config/kwin-scripts/luminos-focus/contents/code/main.js
SRC=$(ls $D/*.go 2>/dev/null | grep -v '_test\.go$')
fail=0

check() { # check <name> <command...>: run quietly, show output only on failure
	local name=$1 out
	shift
	if out=$("$@" 2>&1); then
		echo "PASS $name"
	else
		echo "FAIL $name"
		echo "$out" | sed 's/^/    /'
		fail=1
	fi
}

gofmt_clean() { local l; l=$(gofmt -l $D) && [ -z "$l" ] || { echo "$l"; return 1; }; }
have_src() { [ -n "$SRC" ] || { echo "no non-test .go files in $D"; return 1; }; }
total_lines() { have_src || return 1; local n; n=$(cat $SRC | wc -l); echo "$n lines"; [ "$n" -le 600 ]; }
file_lines() { have_src || return 1; wc -l $SRC | awk '$2 != "total" && $1 > 150 { print; bad = 1 } END { exit bad }'; }
js_lines() { local n; n=$(wc -l <"$JS") || return 1; echo "$n lines"; [ "$n" -le 150 ]; }
func_awk() { # from "^func " to the closing "^}", inclusive; one-line funcs skipped
	awk 'FNR == 1 { start = 0 }
	     /^func / && !/}[[:space:]]*$/ { start = FNR; name = $0 }
	     /^}/ && start { if (FNR - start + 1 > 40) { print FILENAME ": " FNR - start + 1 " lines: " name; bad = 1 }; start = 0 }
	     END { exit bad }' "$@"
}
func_lines() { have_src || return 1; func_awk $SRC; }
# [CHANGE: claude-code | 2026-11-07] self-test: the same awk must flag exactly the fixture's 41-line func
func_selftest() {
	local out
	out=$(func_awk tests/focus/fixtures/longfunc.go.txt) && { echo "41-line func not flagged"; return 1; }
	echo "$out"
	[ "$out" = "tests/focus/fixtures/longfunc.go.txt: 41 lines: func tooLong() int {" ]
}

check "go vet" go vet ./$D
check "go test" go test -count=1 ./$D
check "node --test" node --test tests/focus/
check "gofmt -l empty" gofmt_clean
check "Go total <= 600 lines" total_lines
check "each Go file <= 150 lines" file_lines
check "func-length check catches a 41-line func" func_selftest
check "each Go func <= 40 lines" func_lines
check "main.js <= 150 lines" js_lines
exit $fail
