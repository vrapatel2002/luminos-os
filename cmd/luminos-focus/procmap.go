// Process tree → app.slice units, read from a /proc root (tests pass a fake tree).
// [CHANGE: claude-code | 2026-11-07]
package main

import (
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
)

func Descendants(proc string, pid int) []int { // pid + every descendant, via <proc>/<pid>/task/*/children
	out, seen := []int{pid}, map[int]bool{pid: true}
	for i := 0; i < len(out); i++ {
		for _, c := range children(proc, out[i]) {
			if !seen[c] {
				seen[c] = true
				out = append(out, c)
			}
		}
	}
	return out
}

func children(proc string, pid int) []int {
	files, _ := filepath.Glob(filepath.Join(proc, strconv.Itoa(pid), "task", "*", "children"))
	var out []int
	for _, f := range files {
		b, _ := os.ReadFile(f)
		for _, s := range strings.Fields(string(b)) {
			if n, err := strconv.Atoi(s); err == nil {
				out = append(out, n)
			}
		}
	}
	return out
}

// AppUnit: <unit> of …/user@<uid>.service/app.slice/<unit>[/…] if it starts with "app-" (as resetLeftovers).
func AppUnit(proc string, pid int) (string, bool) {
	b, err := os.ReadFile(filepath.Join(proc, strconv.Itoa(pid), "cgroup"))
	if err != nil {
		return "", false
	}
	for _, line := range strings.Split(string(b), "\n") {
		if cg, ok := strings.CutPrefix(line, "0::"); ok {
			_, after, ok := strings.Cut(cg, ".service/app.slice/") // only user@<uid>.service has app.slice
			unit, _, _ := strings.Cut(after, "/")
			return unit, ok && strings.HasPrefix(unit, "app-") // [CHANGE: claude-code | 2026-11-07] plain user services never
		}
	}
	return "", false
}

func UnitsForApp(proc string, pid int) []string {
	return unitsOf(proc, Descendants(proc, pid))
}

func unitsOf(proc string, pids []int) []string {
	set := map[string]bool{}
	for _, p := range pids {
		if u, ok := AppUnit(proc, p); ok {
			set[u] = true
		}
	}
	return slices.Sorted(maps.Keys(set))
}
