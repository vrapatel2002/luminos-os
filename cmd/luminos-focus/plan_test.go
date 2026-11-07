package main

// [CHANGE: claude-code | 2026-11-07] Plan tests on a fake /proc tree (CONTRACTS §4 plan.go).

import (
	"math/rand"
	"path/filepath"
	"testing"
)

const (
	tfClaudeScope = "app-com.anthropic.Claude-200.scope"
	tfClaudeSvc   = "app-com.anthropic.Claude@c1.service"
	tfFoxScope    = "app-org.mozilla.firefox-400.scope"
	tfFoxSvc      = "app-org.mozilla.firefox@f1.service"
	tfKate        = "app-org.kde.kate-500.scope"
)

var tfClaudeGlob = []string{"app-com.anthropic.Claude-*.scope"}

// tfTree is the model of tfPlanProc: window pid → its units and its whole process tree.
var tfTree = map[int]struct {
	units []string
	pids  []int
}{
	100: {[]string{tfChromeScope, tfChromeSvc}, []int{100, 101, 102}},
	200: {[]string{tfClaudeScope, tfClaudeSvc}, []int{200, 201}},
	400: {[]string{tfFoxScope, tfFoxSvc}, []int{400, 401, 402}},
	500: {[]string{tfKate}, []int{500}},
}

func tfPlanProc(t *testing.T) string {
	p := tfNewProc(t)
	p.add(100, tfApp+tfChromeScope, 101, 102)
	p.add(101, tfApp+tfChromeSvc)
	p.add(102, tfApp+tfChromeSvc+"/gpu")
	p.add(200, tfApp+tfClaudeScope, 201)
	p.add(201, tfApp+tfClaudeSvc)
	p.add(400, tfApp+tfFoxScope, 401)
	p.add(401, tfApp+tfFoxSvc, 402)
	p.add(402, tfApp+tfFoxSvc)
	p.add(500, tfApp+tfKate)
	p.add(600, "0::/user.slice/user-1000.slice/user@1000.service/session.slice/plasma-plasmashell.service")
	return p.root
}

func tfPlanIs(t *testing.T, name string, got, want map[string]Want) {
	t.Helper()
	ok := len(got) == len(want)
	for u, w := range want {
		g, in := got[u]
		ok = ok && in && tfSame(g, w)
	}
	if !ok {
		t.Errorf("%s: Plan = %+v, want %+v", name, got, want)
	}
}

func TestPlanExamples(t *testing.T) {
	proc := tfPlanProc(t)
	none := map[int]bool{}
	tfPlanIs(t, "focused beats everything per unit",
		Plan([]Win{{100, false, 0.9}, {100, true, 0}, {100, false, 0.2}}, proc, none, nil),
		map[string]Want{tfChromeScope: tfFocus, tfChromeSvc: tfFocus})
	tfPlanIs(t, "best window per unit",
		Plan([]Win{{500, false, 0.1}, {500, false, 0.6}, {500, false, 0}}, proc, none, nil),
		map[string]Want{tfKate: Dial(0.6, false, false)})
	tfPlanIs(t, "hidden app: both scope and service throttled",
		Plan([]Win{{100, false, 0}}, proc, none, nil),
		map[string]Want{tfChromeScope: tfHidden, tfChromeSvc: tfHidden})
	for _, pid := range []int{400, 401, 402} {
		tfPlanIs(t, "audio anywhere in the app tree exempts every unit of it",
			Plan([]Win{{400, false, 0}}, proc, map[int]bool{pid: true}, nil),
			map[string]Want{tfFoxScope: tfDefault, tfFoxSvc: tfDefault})
	}
	tfPlanIs(t, "audio of another process does not exempt",
		Plan([]Win{{400, false, 0}}, proc, map[int]bool{999: true, 101: true}, nil),
		map[string]Want{tfFoxScope: tfHidden, tfFoxSvc: tfHidden})
	tfPlanIs(t, "focused still beats audio exemption",
		Plan([]Win{{400, true, 0}}, proc, map[int]bool{402: true}, nil),
		map[string]Want{tfFoxScope: tfFocus, tfFoxSvc: tfFocus})
	tfPlanIs(t, "allow-listed scope exempt, its renderer service is not",
		Plan([]Win{{200, false, 0}}, proc, none, tfClaudeGlob),
		map[string]Want{tfClaudeScope: tfDefault, tfClaudeSvc: tfHidden})
	tfPlanIs(t, "default allow-list behaves the same for Claude",
		Plan([]Win{{200, false, 0}}, proc, none, LoadAllow(filepath.Join(t.TempDir(), "missing"))),
		map[string]Want{tfClaudeScope: tfDefault, tfClaudeSvc: tfHidden})
	tfPlanIs(t, "pid 0, negative, unknown and non-app pids skipped",
		Plan([]Win{{0, true, 1}, {-1, false, 1}, {9999, true, 1}, {600, true, 1}, {500, false, 0}}, proc, none, nil),
		map[string]Want{tfKate: tfHidden})
	tfPlanIs(t, "apps are independent",
		Plan([]Win{{100, true, 1}, {500, false, 0}, {200, false, 0.5}}, proc, none, nil),
		map[string]Want{tfChromeScope: tfFocus, tfChromeSvc: tfFocus, tfKate: tfHidden,
			tfClaudeScope: Dial(0.5, false, false), tfClaudeSvc: Dial(0.5, false, false)})
	if got := Plan(nil, proc, none, nil); len(got) != 0 {
		t.Errorf("Plan(no windows) = %v, want empty", got)
	}
}

// [CHANGE: claude-code | 2026-11-07] Round 2: the package var selfUnit (plan.go) names the daemon's own unit.
func TestPlanNeverReturnsOwnUnit(t *testing.T) {
	proc := tfPlanProc(t)
	old := selfUnit
	defer func() { selfUnit = old }()
	for _, own := range []string{tfClaudeScope, tfFoxSvc, tfKate} {
		selfUnit = own
		got := Plan([]Win{{200, true, 1}, {400, true, 1}, {500, true, 1}, {500, false, 0}}, proc,
			map[int]bool{201: true, 402: true, 500: true}, append([]string{own}, tfClaudeGlob...))
		if _, in := got[own]; in || len(got) != 4 {
			t.Errorf("selfUnit=%q: Plan = %+v, want the other 4 units and never its own", own, got)
		}
	}
}

// Exact oracle: per unit, the max-granting Dial over every window whose app owns that unit.
func TestPlanProperty(t *testing.T) {
	proc := tfPlanProc(t)
	pids := []int{100, 200, 400, 500, 600, 9999, 0}
	audioPool := []int{100, 101, 102, 200, 201, 400, 401, 402, 500, 600, 999}
	prop := func(seed int64) bool {
		r := rand.New(rand.NewSource(seed))
		var wins []Win
		for range r.Intn(7) {
			f := []float64{0, 1, r.Float64(), r.Float64()}[r.Intn(4)]
			wins = append(wins, Win{PID: pids[r.Intn(len(pids))], Active: r.Intn(6) == 0, F: f})
		}
		audio := map[int]bool{}
		for _, p := range audioPool {
			if r.Intn(5) == 0 {
				audio[p] = true
			}
		}
		globs := [][]string{nil, tfClaudeGlob, {"app-org.kde.*"}}[r.Intn(3)]
		want := map[string]Want{}
		for _, w := range wins {
			app := tfTree[w.PID] // unknown pid → no units
			heard := false
			for _, p := range app.pids {
				heard = heard || audio[p]
			}
			for _, u := range app.units {
				d := Dial(w.F, w.Active, heard || Allowed(u, globs))
				if old, seen := want[u]; !seen || Higher(d, old) {
					want[u] = d
				}
			}
		}
		got := Plan(wins, proc, audio, globs)
		ok := len(got) == len(want)
		for u, w := range want {
			ok = ok && tfSame(got[u], w)
		}
		return ok
	}
	tfCheck(t, "Plan equals the per-unit max of Dial over windows", prop, 2000)
}
