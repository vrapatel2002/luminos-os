// Snapshot → per-unit target.
// [CHANGE: claude-code | 2026-11-07] Re-plan 4: /proc walked once per distinct pid, reused by the daemon.
package main

import "slices"

type Win struct {
	PID    int
	Active bool
	F      float64
}

type appTree struct { // one app's process tree and the app units it occupies
	PIDs  []int
	Units []string
}

var selfUnit string // the daemon's own unit (set in main); never planned

func trees(wins []Win, proc string) map[int]appTree { // one /proc walk per distinct window pid (pid ≤ 0 skipped)
	t := map[int]appTree{}
	for _, w := range wins {
		if _, done := t[w.PID]; !done && w.PID > 0 {
			pids := Descendants(proc, w.PID)
			t[w.PID] = appTree{pids, unitsOf(proc, pids)}
		}
	}
	return t
}

func Plan(wins []Win, proc string, audio map[int]bool, globs []string) map[string]Want {
	return planFrom(wins, trees(wins, proc), audio, globs)
}

// planFrom: each unit gets its app's best Want; exempt if allow-listed or any tree pid plays/records.
func planFrom(wins []Win, t map[int]appTree, audio map[int]bool, globs []string) map[string]Want {
	out := map[string]Want{}
	for _, w := range wins {
		a := t[w.PID] // absent (pid ≤ 0) → empty tree
		playing := slices.ContainsFunc(a.PIDs, func(p int) bool { return audio[p] })
		for _, u := range a.Units {
			want := Dial(w.F, w.Active, playing || Allowed(u, globs))
			if old, ok := out[u]; u != selfUnit && (!ok || Higher(want, old)) {
				out[u] = want
			}
		}
	}
	return out
}
