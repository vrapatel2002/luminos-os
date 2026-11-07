package main

// [CHANGE: claude-code | 2026-11-07] Dial/Higher tests, written from CONTRACTS §4 (dial.go) only.
// Test helpers are prefixed "tf" so they cannot collide with names in the implementation (same package).

import (
	"math"
	"math/rand"
	"testing"
	"testing/quick"
)

var (
	tfFocus   = Want{Weight: 1000}
	tfDefault = Want{Weight: 100}
	tfHidden  = Want{Weight: 20, QuotaPct: 25}
)

// tfSame compares the applied values only; Why is free text.
func tfSame(a, b Want) bool { return a.Weight == b.Weight && a.QuotaPct == b.QuotaPct }

// tfF maps a quick-generated uint16 onto [-0.1, 1.1] so the clamp edges get exercised too.
func tfF(x uint16) float64 { return float64(x)/65535*1.2 - 0.1 }

func tfClamp(f float64) float64 {
	if math.IsNaN(f) || f < 0 {
		return 0
	}
	return math.Min(f, 1)
}

// tfQuotaRank orders quotas by how much they grant: 0 means "no quota", the most.
func tfQuotaRank(w Want) int {
	if w.QuotaPct == 0 {
		return math.MaxInt
	}
	return w.QuotaPct
}

func tfCheck(t *testing.T, name string, prop any, n int) {
	t.Helper()
	if err := quick.Check(prop, &quick.Config{MaxCount: n}); err != nil {
		t.Errorf("%s: %v", name, err)
	}
}

func TestDialExamples(t *testing.T) {
	cases := []struct {
		f               float64
		focused, exempt bool
		want            Want
	}{
		{0, false, false, tfHidden},
		{0.25, false, false, Want{Weight: 40, QuotaPct: 419}},
		{0.5, false, false, Want{Weight: 60, QuotaPct: 813}},
		{0.9996, false, false, Want{Weight: 100, QuotaPct: 1599}},
		{0.9997, false, false, tfDefault}, // round(25+1575f) reaches 1600 → no quota
		{1, false, false, tfDefault},
		{math.NaN(), false, false, tfHidden},
		{-3, false, false, tfHidden},
		{math.Inf(-1), false, false, tfHidden},
		{7, false, false, tfDefault},
		{math.Inf(1), false, false, tfDefault},
		{0, true, false, tfFocus},
		{0.4, true, false, tfFocus},
		{0, false, true, tfDefault},
		{0.7, false, true, tfDefault},
		{0, true, true, tfFocus},
	}
	for _, c := range cases {
		if got := Dial(c.f, c.focused, c.exempt); !tfSame(got, c.want) {
			t.Errorf("Dial(%v, %v, %v) = %+v, want %+v", c.f, c.focused, c.exempt, got, c.want)
		}
	}
}

func TestDialProperties(t *testing.T) {
	tfCheck(t, "exact formula, quota 0 iff round(25+1575f) >= 1600", func(x uint16) bool {
		f := tfF(x)
		c := tfClamp(f)
		q := int(math.Round(25 + 1575*c))
		if q >= 1600 {
			q = 0
		}
		got := Dial(f, false, false)
		return got.Weight == uint64(math.Round(20+80*c)) && got.QuotaPct == q
	}, 5000)
	tfCheck(t, "raw floats clamp to [0,1], NaN as 0", func(raw float64) bool {
		return tfSame(Dial(raw, false, false), Dial(tfClamp(raw), false, false))
	}, 2000)
	tfCheck(t, "weight in [20,1000], quota 0 or in [25,1599]", func(x uint16, foc, ex bool) bool {
		d := Dial(tfF(x), foc, ex)
		return d.Weight >= 20 && d.Weight <= 1000 && (d.QuotaPct == 0 || d.QuotaPct >= 25 && d.QuotaPct <= 1599)
	}, 5000)
	tfCheck(t, "monotone non-decreasing in f", func(a, b uint16) bool {
		fa, fb := tfF(a), tfF(b)
		if fa > fb {
			fa, fb = fb, fa
		}
		da, db := Dial(fa, false, false), Dial(fb, false, false)
		return da.Weight <= db.Weight && tfQuotaRank(da) <= tfQuotaRank(db) && !Higher(da, db)
	}, 5000)
	tfCheck(t, "focused always {1000,0}, exempt always {100,0}", func(x uint16, raw float64) bool {
		for _, f := range []float64{tfF(x), raw, math.NaN()} {
			if !tfSame(Dial(f, true, false), tfFocus) || !tfSame(Dial(f, true, true), tfFocus) ||
				!tfSame(Dial(f, false, true), tfDefault) {
				return false
			}
		}
		return true
	}, 2000)
}

func TestHigherExamples(t *testing.T) {
	cases := []struct {
		a, b Want
		want bool
	}{
		{tfFocus, tfDefault, true},
		{tfDefault, tfFocus, false},
		{tfDefault, Want{Weight: 100, QuotaPct: 500}, true}, // quota removed
		{Want{Weight: 100, QuotaPct: 500}, tfDefault, false},
		{Want{Weight: 20, QuotaPct: 50}, tfHidden, true}, // quota up
		{tfHidden, Want{Weight: 20, QuotaPct: 50}, false},
		{tfDefault, tfHidden, true},
		{tfHidden, tfDefault, false},
		{Want{Weight: 1000, QuotaPct: 25}, tfDefault, true}, // weight up counts
		{Want{Weight: 60, QuotaPct: 813, Why: "a"}, Want{Weight: 60, QuotaPct: 813, Why: "b"}, false},
		// subtract-free: extremes must not wrap around
		{Want{Weight: math.MaxUint64}, Want{Weight: 0}, true},
		{Want{Weight: 0}, Want{Weight: math.MaxUint64}, false},
		{Want{Weight: 20, QuotaPct: math.MaxInt}, Want{Weight: 20, QuotaPct: 1}, true},
		{Want{Weight: 20, QuotaPct: 1}, Want{Weight: 20, QuotaPct: math.MaxInt}, false},
		{Want{Weight: 20}, Want{Weight: 20, QuotaPct: 1599}, true},
		{Want{Weight: 20, QuotaPct: 1599}, Want{Weight: 20}, false},
	}
	for _, c := range cases {
		if got := Higher(c.a, c.b); got != c.want {
			t.Errorf("Higher(%+v, %+v) = %v, want %v", c.a, c.b, got, c.want)
		}
	}
}

// tfDialPick draws from everything Dial can return, including focused/exempt.
func tfDialPick(r *rand.Rand) Want {
	f := []float64{0, 1, r.Float64(), r.Float64()}[r.Intn(4)]
	return Dial(f, r.Intn(5) == 0, r.Intn(5) == 0)
}

func TestHigherProperties(t *testing.T) {
	tfCheck(t, "irreflexive", func(w Want) bool { return !Higher(w, w) }, 2000)
	tfCheck(t, "strict total order on Dial outputs", func(seed int64) bool {
		r := rand.New(rand.NewSource(seed))
		a, b, c := tfDialPick(r), tfDialPick(r), tfDialPick(r)
		if tfSame(a, b) != (!Higher(a, b) && !Higher(b, a)) || (Higher(a, b) && Higher(b, a)) {
			return false
		}
		return !(Higher(a, b) && Higher(b, c)) || Higher(a, c)
	}, 5000)
	tfCheck(t, "focused beats every non-focused Dial output", func(x uint16, ex bool) bool {
		return Higher(tfFocus, Dial(tfF(x), false, ex))
	}, 2000)
	tfCheck(t, "exempt beats every unfocused Dial output except {100,0}", func(x uint16) bool {
		d := Dial(tfF(x), false, false)
		return Higher(tfDefault, d) == !tfSame(d, tfDefault)
	}, 5000)
}
