package main

// [CHANGE: claude-code | 2026-11-07] Glider tests with a fake Setter and a fake clock (CONTRACTS §4 glide.go).

import (
	"errors"
	"math/rand"
	"testing"
	"time"
)

type tfCall struct {
	unit string
	w    Want
}

type tfSetter struct {
	calls []tfCall
	fail  map[string]bool
}

func (s *tfSetter) Set(unit string, w Want) error {
	s.calls = append(s.calls, tfCall{unit, w})
	if s.fail[unit] {
		return errors.New("unit vanished")
	}
	return nil
}

// since returns the values set on unit after call index n ("" = every unit).
func (s *tfSetter) since(n int, unit string) []Want {
	var out []Want
	for _, c := range s.calls[n:] {
		if unit == "" || c.unit == unit {
			out = append(out, c.w)
		}
	}
	return out
}

// cur is what the unit is running with now: the last value set, else systemd's default {100,0}.
func (s *tfSetter) cur(unit string) Want {
	if ws := s.since(0, unit); len(ws) > 0 {
		return ws[len(ws)-1]
	}
	return tfDefault
}

type tfRig struct {
	s   *tfSetter
	g   *Glider
	now time.Time
}

func tfNewRig() *tfRig {
	r := &tfRig{s: &tfSetter{fail: map[string]bool{}}, now: time.Unix(1_800_000_000, 0)}
	r.g = NewGlider(r.s, func() time.Time { return r.now })
	return r
}

// tick advances the fake clock 500 ms per Tick, the daemon's cadence.
func (r *tfRig) tick(n int) {
	for range n {
		r.now = r.now.Add(500 * time.Millisecond)
		r.g.Tick()
	}
}

func (r *tfRig) quiet(t *testing.T, n int, what string) {
	t.Helper()
	if got := r.s.since(n, ""); len(got) != 0 {
		t.Errorf("%s: unexpected Set calls %+v", what, r.s.calls[n:])
	}
}

func TestGliderRaiseIsImmediate(t *testing.T) {
	r := tfNewRig()
	r.g.Apply(map[string]Want{"u": tfFocus})
	if got := r.s.since(0, "u"); len(got) != 1 || !tfSame(got[0], tfFocus) {
		t.Fatalf("raise: Set calls %+v, want exactly one {1000,0} inside Apply", got)
	}
	n := len(r.s.calls)
	r.tick(4)
	r.quiet(t, n, "ticks after a raise")
}

func TestGliderLowerTakesFourTicks(t *testing.T) {
	r := tfNewRig()
	r.g.Apply(map[string]Want{"u": tfHidden})
	if tfSame(r.s.cur("u"), tfHidden) {
		t.Fatal("lower reached the target inside Apply; want 4 steps over 2 s")
	}
	for k := 1; k <= 4; k++ {
		r.tick(1)
		w := r.s.cur("u")
		if want := 100 - 20*k; int(w.Weight) < want-1 || int(w.Weight) > want+1 {
			t.Errorf("after tick %d weight = %d, want ≈ %d (linear 100 → 20)", k, w.Weight, want)
		}
		if Higher(tfHidden, w) {
			t.Errorf("after tick %d %+v grants less than the target %+v", k, w, tfHidden)
		}
		if at := tfSame(w, tfHidden); at != (k == 4) {
			t.Errorf("after tick %d at target = %v, want %v", k, at, k == 4)
		}
	}
	n := len(r.s.calls)
	r.tick(4)
	r.quiet(t, n, "ticks after the glide ended")
}

func TestGliderRaiseCancelsGlide(t *testing.T) {
	r := tfNewRig()
	r.g.Apply(map[string]Want{"u": tfHidden})
	r.tick(2)
	n := len(r.s.calls)
	r.g.Apply(map[string]Want{"u": tfFocus})
	if got := r.s.since(n, "u"); len(got) != 1 || !tfSame(got[0], tfFocus) {
		t.Fatalf("raise mid-glide: Set calls %+v, want exactly one {1000,0} inside Apply", got)
	}
	r.tick(4)
	for _, w := range r.s.since(n, "u") {
		if !tfSame(w, tfFocus) {
			t.Errorf("cancelled glide kept lowering: %+v", r.s.since(n, "u"))
		}
	}
}

func TestGliderDroppedUnits(t *testing.T) {
	r := tfNewRig() // dropped while throttled: back to {100,0} is a raise → at once
	r.g.Apply(map[string]Want{"u": tfHidden})
	r.tick(4)
	n := len(r.s.calls)
	r.g.Apply(map[string]Want{})
	if got := r.s.since(n, "u"); len(got) == 0 || !tfSame(got[len(got)-1], tfDefault) {
		t.Errorf("dropped throttled unit: Set calls %+v, want {100,0} inside Apply", got)
	}
	n = len(r.s.calls)
	r.tick(4)
	r.g.Apply(map[string]Want{})
	r.tick(4)
	r.quiet(t, n, "dropped unit must be forgotten")

	r = tfNewRig() // dropped while focused: glides down to {100,0}
	r.g.Apply(map[string]Want{"u": tfFocus})
	r.g.Apply(map[string]Want{})
	r.tick(3)
	if tfSame(r.s.cur("u"), tfDefault) {
		t.Error("dropped focused unit reached {100,0} before 4 ticks")
	}
	r.tick(1)
	if !tfSame(r.s.cur("u"), tfDefault) {
		t.Errorf("dropped focused unit at %+v after 4 ticks, want {100,0}", r.s.cur("u"))
	}
	n = len(r.s.calls)
	r.tick(4)
	r.g.Apply(map[string]Want{})
	r.tick(2)
	r.quiet(t, n, "dropped unit must be forgotten")
	r.g.Apply(map[string]Want{"u": tfFocus})
	if !tfSame(r.s.cur("u"), tfFocus) {
		t.Error("a forgotten unit must be raisable again")
	}
}

func TestGliderResetAll(t *testing.T) {
	r := tfNewRig()
	r.g.ResetAll()
	r.quiet(t, 0, "ResetAll with nothing touched")
	half := Dial(0.5, false, false)
	r.g.Apply(map[string]Want{"a": tfFocus, "b": tfHidden, "c": half})
	r.tick(2) // b and c mid-glide
	n := len(r.s.calls)
	r.g.ResetAll()
	for _, u := range []string{"a", "b", "c"} {
		if got := r.s.since(n, u); len(got) == 0 || !tfSame(got[len(got)-1], tfDefault) {
			t.Errorf("ResetAll: %s got %+v, want a Set {100,0} now", u, got)
		}
	}
	n = len(r.s.calls)
	r.tick(6)
	r.quiet(t, n, "ticks after ResetAll (glides must be dropped)")
}

func TestGliderSetErrorsAndIdleTicks(t *testing.T) {
	r := tfNewRig()
	r.tick(4)
	r.quiet(t, 0, "Tick with nothing pending")
	r.s.fail["gone"] = true
	r.g.Apply(map[string]Want{"gone": tfFocus, "ok": tfFocus})
	if !tfSame(r.s.cur("ok"), tfFocus) {
		t.Error("a failing unit must not stop the others")
	}
	r.g.Apply(map[string]Want{"gone": tfHidden, "ok": tfHidden})
	r.tick(5)
	r.g.Apply(map[string]Want{})
	r.g.ResetAll()
}

// Random Apply/Tick sequences: never under-grant the current target, settle exactly 4 ticks after the last Apply.
func TestGliderProperty(t *testing.T) {
	units := []string{"app-a.scope", "app-b@x.service", "app-c.scope"}
	prop := func(seed int64) bool {
		rnd := rand.New(rand.NewSource(seed))
		r := tfNewRig()
		target := map[string]Want{}
		for step := 0; step < 40; step++ {
			if step == 0 || rnd.Intn(3) == 0 {
				target = map[string]Want{}
				for _, u := range units {
					if rnd.Intn(4) != 0 {
						target[u] = tfDialPick(rnd)
					}
				}
				r.g.Apply(target)
			} else {
				r.tick(1)
			}
			for u, w := range target {
				if Higher(w, r.s.cur(u)) {
					return false
				}
			}
		}
		r.tick(4)
		for _, u := range units {
			want, in := target[u]
			if !in {
				want = tfDefault
			}
			if !tfSame(r.s.cur(u), want) {
				return false
			}
		}
		return true
	}
	tfCheck(t, "glider never under-grants and settles on target", prop, 1000)
}
