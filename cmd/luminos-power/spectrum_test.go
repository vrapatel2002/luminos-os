// [CHANGE: claude-code | 2026-10-15] properties P1–P15 of docs/spectrum/DESIGN.md §5
//
// Written from docs/spectrum/DESIGN.md (§3.4, §4, §5, §6) and CONTRACTS.md (C1–C6) only, without reading
// spectrum.go. Every helper is prefixed "tsp" so nothing collides with package code. Failures print the seed,
// walk, step and inputs so any case can be replayed.
//
// Two places where DESIGN §5's wording is stronger than §3.4's equations (CONTRACTS: "Semantics = DESIGN §3.4
// steps 0–9 exactly") are tested as the equations dictate:
//   - P5 "I == 0 ± 1e-3 after 120 idle steps": §3.4 step 6 only leaks I with IleakS = 300 s, so a reachable
//     I = −25 W is still ≈ −16.8 W after 120 s. Tested: idle never integrates (pure leak), and |I| ≤ 1e-3 after
//     4 000 idle seconds.
//   - P9 "Resumed ⇒ Demand == 0 ∧ I == 0": step 0 zeroes them, then steps 2 and 6 run in the same tick. Tested:
//     Demand equals that tick's raw demand, |I| ≤ one integration step; exactly 0 for idle input (the §3.4 example).

package main

import (
	"fmt"
	"math"
	"math/rand"
	"testing"
)

const (
	tspHwMax = 5137904
	tspTol   = 1e-6
	tspSeed  = int64(20261015)
	tspSteps = 300
)

var tspDTs = [...]float64{0.5, 1, 1.7, 3, 7}

func tspClamp(x, lo, hi float64) float64 { return math.Max(lo, math.Min(hi, x)) }
func tspClamp01(x float64) float64       { return tspClamp(x, 0, 1) }
func tspLerp(a, b, x float64) float64    { return a + (b-a)*x }
func tspDT(in Inputs) float64            { return tspClamp(in.DT, 0.5, 3) }
func tspB2F(b bool) float64 {
	if b {
		return 1
	}
	return 0
}
func tspAbsI(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// tspN returns the normal count, or the short count under -short.
func tspN(normal, short int) int {
	if testing.Short() {
		return short
	}
	return normal
}

// tspFast removes the slew limiter so that the returned P equals Ptarget (step 5) — makes Ptarget observable.
func tspFast(p Params) Params {
	p.SlewUpWS, p.SlewDownWS, p.SlewDownHotWS = 1e9, 1e9, 1e9
	return p
}

func tspRun(p Params, s State, in Inputs, n int) (State, Outputs) {
	var o Outputs
	for i := 0; i < n; i++ {
		s, o = Step(p, s, in)
	}
	return s, o
}

// tspLoad: steady inputs with every core at util, cool or hot as given.
func tspLoad(onAC bool, util, temp float64) Inputs {
	return Inputs{DT: 1, UtilAvg: util, UtilMax: util, TempC: temp, SOC: 1, OnAC: onAC}
}

// tspPlant is DESIGN §5's model-perfect plant: T += dt/60·(T0 + Rth·P − T).
func tspPlant(p Params, T, P, dt float64) float64 { return T + dt/60*(p.T0C+p.RthCPerW*P-T) }

// ---------------------------------------------------------------- reference model of DESIGN §3.4 steps 0–8

type tspRef struct {
	s                                                     State
	dt, pmaxSrc, pmax, thi, pthRaw, pth, pdem, ptarget, f float64
}

func tspReference(p Params, s State, in Inputs) tspRef {
	r := tspRef{dt: tspDT(in)}
	if !s.Seeded || in.Resumed {
		s.TempS, s.Demand, s.I, s.Gpu = in.TempC, 0, 0, tspB2F(in.DGPUBusy)
		if !s.Seeded {
			s.P, s.F = p.PminW, p.HwMaxKHz
		}
		s.Seeded = true
	}
	dt := r.dt
	s.TempS += (1 - math.Exp(-dt/p.TauTempS)) * (in.TempC - s.TempS)
	dRaw := math.Max(in.UtilAvg, math.Max(in.UtilMax/4, 0.8*in.IGPUBusy))
	s.Demand = math.Max(dRaw, s.Demand*math.Exp(-dt/p.TauDemandS))
	if s.Demand < 0.005 {
		s.Demand = 0
	}
	tspRefCeilings(p, &s, in, &r)
	e := r.thi - s.TempS
	r.pthRaw = (r.thi-p.T0C)/p.RthCPerW + p.KpWPerC*e + s.I
	r.pth = tspClamp(r.pthRaw, p.PminW, r.pmax)
	r.pdem = p.PminW + tspClamp01((s.Demand-p.D0)/(p.D1-p.D0))*(r.pmax-p.PminW)
	r.ptarget = math.Min(r.pdem, r.pth)
	if (r.pth <= r.pdem || e < 0) && (r.pthRaw < r.pmax || e < 0) && (r.pthRaw > p.PminW || e > 0) {
		s.I = tspClamp(s.I+p.KiWPerCS*e*dt, p.IminW, p.ImaxW)
	} else {
		s.I *= math.Exp(-dt / p.IleakS)
	}
	down := p.SlewDownWS + (p.SlewDownHotWS-p.SlewDownWS)*tspClamp01((s.TempS-r.thi)/3)
	s.P = tspClamp(r.ptarget, s.P-down*dt, s.P+p.SlewUpWS*dt)
	r.f = tspRefFreq(p, s, in, r)
	r.s = s
	return r
}

func tspRefCeilings(p Params, s *State, in Inputs, r *tspRef) {
	s.Gpu += (1 - math.Exp(-r.dt/p.TauGpuS)) * (tspB2F(in.DGPUBusy) - s.Gpu)
	r.pmaxSrc, r.thi = p.PmaxAcW, p.ThiAcC
	if !in.OnAC {
		r.pmaxSrc = tspLerp(p.PmaxBatLoW, p.PmaxBatHiW, tspClamp01((in.SOC-0.15)/0.35))
		r.thi = p.ThiBatC
	}
	r.pmax = tspLerp(r.pmaxSrc, math.Min(r.pmaxSrc, p.PmaxDgpuW), s.Gpu)
	r.thi = tspLerp(r.thi, math.Min(r.thi, p.ThiDgpuC), s.Gpu)
}

// tspRefFreq is step 8's cap glide with C3's denominator and range clamp; s.P is the new P, s.F the previous F.
func tspRefFreq(p Params, s State, in Inputs, r tspRef) float64 {
	target, lo := float64(p.HwMaxKHz), 0.0
	if !in.OnAC {
		lo, target = float64(p.FreqBatFloorKHz), float64(p.FreqBatFloorKHz)
		if r.pmaxSrc-p.PminW >= 0.5 {
			target += tspClamp01((s.P-p.PminW)/(r.pmaxSrc-p.PminW)) * float64(p.FreqBatCeilKHz-p.FreqBatFloorKHz)
		}
	}
	slew := float64(p.FreqSlewKHzS) * r.dt
	f := tspClamp(target, float64(s.F)-slew, float64(s.F)+slew)
	return tspClamp(f, lo, float64(p.HwMaxKHz))
}

// ---------------------------------------------------------------- per-step checks

type tspCtx struct {
	p          Params
	seed       int64
	walk, step int
	prev       State
	in         Inputs
}

func (c tspCtx) String() string {
	return fmt.Sprintf("seed=%d walk=%d step=%d\n  in=%+v\n  prev=%+v", c.seed, c.walk, c.step, c.in, c.prev)
}

func tspCheckAll(c tspCtx, n State, o Outputs) error {
	r := tspReference(c.p, c.prev, c.in)
	for _, f := range []func(tspCtx, State, Outputs, tspRef) error{
		tspCheckOracle, tspCheckBinding, tspCheckBounds, tspCheckWrites, tspCheckEvents, tspCheckPurity, tspCheckMonotone,
	} {
		if err := f(c, n, o, r); err != nil {
			return fmt.Errorf("%v\n  next=%+v\n  out=%+v", err, n, o)
		}
	}
	return nil
}

// tspCheckOracle: the state and outputs equal DESIGN §3.4 steps 0–8 (C1–C4).
func tspCheckOracle(c tspCtx, n State, o Outputs, r tspRef) error {
	type q struct {
		name      string
		got, want float64
	}
	for _, v := range []q{{"TempS", n.TempS, r.s.TempS}, {"Demand", n.Demand, r.s.Demand}, {"I", n.I, r.s.I},
		{"Gpu", n.Gpu, r.s.Gpu}, {"P", n.P, r.s.P}, {"Outputs.Demand", o.Demand, r.s.Demand},
		{"PmaxW", o.PmaxW, r.pmax}, {"TargetTempC", o.TargetTempC, r.thi}} {
		if math.IsNaN(v.got) || math.Abs(v.got-v.want) > tspTol {
			return fmt.Errorf("§3.4: %s = %.9g, want %.9g", v.name, v.got, v.want)
		}
	}
	if math.Abs(float64(n.F)-r.f) > 1 {
		return fmt.Errorf("§3.4 step 8/C3: F = %d, want %.1f", n.F, r.f)
	}
	switch {
	case !n.Seeded:
		return fmt.Errorf("step 0: Seeded false after Step")
	case o.FreqCapKHz != n.F:
		return fmt.Errorf("C4: FreqCapKHz %d != State.F %d", o.FreqCapKHz, n.F)
	case o.PptW != int(math.Round(n.P)):
		return fmt.Errorf("C4: PptW %d != round(P=%.6f)", o.PptW, n.P)
	case o.EPP != c.p.EPP:
		return fmt.Errorf("C4: EPP %q != %q", o.EPP, c.p.EPP)
	}
	return nil
}

// tspCheckBinding: Binding ∈ {demand, thermal, battery, dgpu} as step 5 defines it (display only, ties tolerated).
func tspCheckBinding(c tspCtx, _ State, o Outputs, r tspRef) error {
	base := "demand"
	if r.pth <= r.pdem {
		base = "thermal"
	}
	tie := math.Abs(r.pth-r.pdem) < 1e-9
	capBand := r.pmax < c.p.PmaxAcW-1e-9 && r.ptarget >= r.pmax-1e-9
	switch o.Binding {
	case "battery":
		if !capBand || c.in.OnAC {
			return fmt.Errorf("binding battery: on AC or Ptarget %.4f below Pmax %.4f", r.ptarget, r.pmax)
		}
	case "dgpu":
		if !capBand || r.pmax >= r.pmaxSrc {
			return fmt.Errorf("binding dgpu: dGPU is not lowering Pmax (%.4f vs src %.4f)", r.pmax, r.pmaxSrc)
		}
	case "thermal", "demand":
		if !tie && o.Binding != base {
			return fmt.Errorf("binding %q, want %q (Pth %.4f Pdem %.4f)", o.Binding, base, r.pth, r.pdem)
		}
	default:
		return fmt.Errorf("binding %q not in {demand, thermal, battery, dgpu}", o.Binding)
	}
	return nil
}

func tspPrevP(c tspCtx) float64 {
	if c.prev.Seeded {
		return c.prev.P
	}
	return c.p.PminW
}

// tspCheckBounds: P1 bounded, P2 slew, P10 cap range and slew, P11 level — from the outputs alone.
func tspCheckBounds(c tspCtx, n State, o Outputs, _ tspRef) error {
	p, dt, pp := c.p, tspDT(c.in), tspPrevP(c)
	if n.P < p.PminW-tspTol || n.P > p.PmaxAcW+tspTol {
		return fmt.Errorf("P1: P = %.6f outside [%g, %g]", n.P, p.PminW, p.PmaxAcW)
	}
	if n.P > o.PmaxW+tspTol && !(n.P < pp) {
		return fmt.Errorf("P1: P = %.6f above Pmax %.6f and not gliding down (prev %.6f)", n.P, o.PmaxW, pp)
	}
	down := p.SlewDownWS + (p.SlewDownHotWS-p.SlewDownWS)*tspClamp01((n.TempS-o.TargetTempC)/3)
	if n.P < pp-down*dt-tspTol || n.P > pp+p.SlewUpWS*dt+tspTol {
		return fmt.Errorf("P2: P %.6f → %.6f exceeds slew (down %.3f W/s, up %g W/s, dt %g)", pp, n.P, down, p.SlewUpWS, dt)
	}
	if lvl := tspClamp01((n.P - p.PminW) / (p.PmaxAcW - p.PminW)); math.Abs(o.Level-lvl) > tspTol {
		return fmt.Errorf("P11: Level %.9f, want %.9f", o.Level, lvl)
	}
	prevF := float64(p.HwMaxKHz)
	if c.prev.Seeded {
		prevF = float64(c.prev.F)
	}
	if math.Abs(float64(n.F)-prevF) > float64(p.FreqSlewKHzS)*dt+1 {
		return fmt.Errorf("P10: F %.0f → %d faster than %d kHz/s", prevF, n.F, p.FreqSlewKHzS)
	}
	lo := 0
	if !c.in.OnAC {
		lo = p.FreqBatFloorKHz
	}
	if n.F < lo || n.F > p.HwMaxKHz {
		return fmt.Errorf("P10/C3: F %d outside [%d, %d]", n.F, lo, p.HwMaxKHz)
	}
	return nil
}

// tspCheckWrites: P7 + step 9 exactly (WritePPT, WriteFreq, WriteEPP and the written/refresh bookkeeping, C6).
func tspCheckWrites(c tspCtx, n State, o Outputs, _ tspRef) error {
	p, prev, in := c.p, c.prev, c.in
	force := !prev.Seeded || in.Resumed
	since := prev.SinceRefreshS + tspDT(in)
	wantPPT := force || in.ProfileChanged || since >= p.RefreshS ||
		float64(tspAbsI(o.PptW-prev.PptWritten)) >= p.WriteDeadbandW
	wantPPT = wantPPT && !in.PPTOwnerExternal
	if o.WritePPT != wantPPT {
		return fmt.Errorf("P7: WritePPT %v, want %v (force %v since %.3f written %d ppt %d)",
			o.WritePPT, wantPPT, force, since, prev.PptWritten, o.PptW)
	}
	if o.WritePPT && (n.PptWritten != o.PptW || n.SinceRefreshS != 0) {
		return fmt.Errorf("step 9: after a PPT write PptWritten %d (want %d), SinceRefreshS %.3f (want 0)",
			n.PptWritten, o.PptW, n.SinceRefreshS)
	}
	// C6: under an external owner SinceRefreshS may instead be parked at "refresh due" (≥ RefreshS) — the only
	// State-carried way to make the release tick re-assert (TestExampleExternalShortRelease).
	parked := in.PPTOwnerExternal && n.SinceRefreshS >= p.RefreshS
	if !o.WritePPT && (n.PptWritten != prev.PptWritten || (math.Abs(n.SinceRefreshS-since) > tspTol && !parked)) {
		return fmt.Errorf("step 9/C6: no PPT write but PptWritten %d→%d, SinceRefreshS %.3f (want %.3f)",
			prev.PptWritten, n.PptWritten, n.SinceRefreshS, since)
	}
	wantF := force || tspAbsI(o.FreqCapKHz-prev.FreqWritten) >= p.FreqDeadbandKHz
	if o.WriteFreq != wantF {
		return fmt.Errorf("step 9: WriteFreq %v, want %v", o.WriteFreq, wantF)
	}
	if (o.WriteFreq && n.FreqWritten != o.FreqCapKHz) || (!o.WriteFreq && n.FreqWritten != prev.FreqWritten) {
		return fmt.Errorf("step 9: FreqWritten %d (prev %d, F %d, write %v)", n.FreqWritten, prev.FreqWritten, n.F, o.WriteFreq)
	}
	if o.WriteEPP != (force || in.ProfileChanged) {
		return fmt.Errorf("step 9: WriteEPP %v, want %v", o.WriteEPP, force || in.ProfileChanged)
	}
	return nil
}

// tspCheckEvents: P9. Events force writes; a resume zeroes Demand and I before this tick's steps 2 and 6.
func tspCheckEvents(c tspCtx, n State, o Outputs, _ tspRef) error {
	in := c.in
	if (in.Resumed || in.ProfileChanged) && !(o.WriteEPP && (o.WritePPT || in.PPTOwnerExternal)) {
		return fmt.Errorf("P9: event without WritePPT/WriteEPP (%v/%v)", o.WritePPT, o.WriteEPP)
	}
	if !in.Resumed {
		return nil
	}
	dRaw := math.Max(in.UtilAvg, math.Max(in.UtilMax/4, 0.8*in.IGPUBusy))
	if dRaw < 0.005 {
		dRaw = 0
	}
	if math.Abs(n.Demand-dRaw) > tspTol || math.Abs(n.TempS-in.TempC) > tspTol {
		return fmt.Errorf("P9: after resume Demand %.6f (want %.6f), TempS %.4f (want %.4f)", n.Demand, dRaw, n.TempS, in.TempC)
	}
	if lim := c.p.KiWPerCS*math.Abs(o.TargetTempC-n.TempS)*tspDT(in) + tspTol; math.Abs(n.I) > lim {
		return fmt.Errorf("P9: after resume |I| = %.6f > one integration step %.6f", math.Abs(n.I), lim)
	}
	return nil
}

// tspCheckPurity: P8 — same arguments, same answer.
func tspCheckPurity(c tspCtx, n State, o Outputs, _ tspRef) error {
	n2, o2 := Step(c.p, c.prev, c.in)
	if n2 != n || o2 != o {
		return fmt.Errorf("P8: second identical call differs:\n  %+v %+v", n2, o2)
	}
	return nil
}

// tspCheckMonotone: P3 (more demand never lowers Ptarget or P; battery F follows P — P10) and P4 (hotter never
// raises Ptarget or P). Ptarget is observed through tspFast params.
func tspCheckMonotone(c tspCtx, n State, o Outputs, _ tspRef) error {
	fast := tspFast(c.p)
	tgt, _ := Step(fast, c.prev, c.in)
	bumps := []func(*Inputs){
		func(i *Inputs) { i.UtilAvg = math.Min(1, i.UtilAvg+0.17) },
		func(i *Inputs) { i.UtilMax = math.Min(1, i.UtilMax+0.29) },
		func(i *Inputs) { i.IGPUBusy = math.Min(1, i.IGPUBusy+0.23) },
	}
	for k, bump := range bumps {
		in := c.in
		bump(&in)
		hi, _ := Step(c.p, c.prev, in)
		hiT, _ := Step(fast, c.prev, in)
		if hi.P < n.P-tspTol || hiT.P < tgt.P-tspTol {
			return fmt.Errorf("P3: demand bump %d lowered P %.6f→%.6f / Ptarget %.6f→%.6f", k, n.P, hi.P, tgt.P, hiT.P)
		}
		if !in.OnAC && hi.F < n.F {
			return fmt.Errorf("P10: battery cap fell with more P (F %d→%d, P %.4f→%.4f)", n.F, hi.F, n.P, hi.P)
		}
	}
	in := c.in
	in.TempC = math.Min(105, in.TempC+7)
	hot, _ := Step(c.p, c.prev, in)
	hotT, _ := Step(fast, c.prev, in)
	if hot.P > n.P+tspTol || hotT.P > tgt.P+tspTol {
		return fmt.Errorf("P4: hotter (%.2f°C) raised P %.6f→%.6f / Ptarget %.6f→%.6f", in.TempC, n.P, hot.P, tgt.P, hotT.P)
	}
	return nil
}

// ---------------------------------------------------------------- random walks (P1–P4, P7–P11 + §3.4)

func tspDraw(rng *rand.Rand, lo, hi float64) float64 {
	switch rng.Intn(12) {
	case 0:
		return lo
	case 1:
		return hi
	}
	return lo + (hi-lo)*rng.Float64()
}

// tspNextInputs: each field is held from the last tick with probability 0.7 (so steady states are reached),
// otherwise redrawn over DESIGN §5's ranges; events are rare one-tick pulses.
func tspNextInputs(rng *rand.Rand, in Inputs, first bool) Inputs {
	redraw := func() bool { return first || rng.Float64() < 0.3 }
	if redraw() {
		in.UtilAvg = tspDraw(rng, 0, 1)
	}
	if redraw() {
		in.UtilMax = tspDraw(rng, 0, 1)
	}
	if redraw() {
		in.IGPUBusy = tspDraw(rng, 0, 1)
	}
	if redraw() {
		in.TempC = tspDraw(rng, 20, 105)
	}
	if redraw() {
		in.SOC = tspDraw(rng, 0, 1)
	}
	if redraw() {
		in.OnAC = rng.Intn(2) == 0
	}
	if redraw() {
		in.DGPUBusy = rng.Intn(2) == 0
	}
	if redraw() {
		in.PPTOwnerExternal = rng.Intn(5) == 0
	}
	in.DT = tspDTs[rng.Intn(len(tspDTs))]
	in.ProfileChanged = rng.Intn(20) == 0
	in.Resumed = rng.Intn(30) == 0
	return in
}

func tspRunWalk(p Params, w int) error {
	seed := tspSeed + int64(w)
	rng := rand.New(rand.NewSource(seed))
	var s State
	var in Inputs
	for k := 0; k < tspSteps; k++ {
		in = tspNextInputs(rng, in, k == 0)
		c := tspCtx{p: p, seed: seed, walk: w, step: k, prev: s, in: in}
		n, o := Step(p, s, in)
		if err := tspCheckAll(c, n, o); err != nil {
			return fmt.Errorf("%v\n%v", c, err)
		}
		s = n
	}
	return nil
}

// tspWalkState returns a reachable State: the end of random walk w of the given length (its own seed family).
func tspWalkState(p Params, w, steps int) State {
	rng := rand.New(rand.NewSource(tspSeed + 1_000_000 + int64(w)))
	var s State
	var in Inputs
	for k := 0; k < steps; k++ {
		in = tspNextInputs(rng, in, k == 0)
		s, _ = Step(p, s, in)
	}
	return s
}

// TestSpectrumRandomWalks: P1, P2, P3, P4, P7, P8, P9, P10, P11 and §3.4 step-by-step on ≥ 2 000 seeded walks ×
// 300 steps (200 under -short), sharded across parallel subtests so -race sees concurrent callers (P8).
func TestSpectrumRandomWalks(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	walks := tspN(2000, 200)
	const shards = 8
	for sh := 0; sh < shards; sh++ {
		sh := sh
		t.Run(fmt.Sprintf("shard%d", sh), func(t *testing.T) {
			t.Parallel()
			for w := sh; w < walks; w += shards {
				if err := tspRunWalk(p, w); err != nil {
					t.Fatal(err)
				}
			}
		})
	}
}

// ---------------------------------------------------------------- targeted properties

// TestDefaultParams: every constant of the DESIGN §3.4 table.
func TestDefaultParams(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	want := Params{TickS: 1, PminW: 15, PmaxAcW: 45, PmaxBatHiW: 25, PmaxBatLoW: 15, PmaxDgpuW: 30,
		ThiAcC: 88, ThiBatC: 80, ThiDgpuC: 85, T0C: 42, RthCPerW: 1.3, KpWPerC: 0.75, KiWPerCS: 0.05,
		IminW: -25, ImaxW: 10, IleakS: 300, TauTempS: 2, TauDemandS: 6, TauGpuS: 5, D0: 0.08, D1: 0.80,
		SlewUpWS: 6, SlewDownWS: 3, SlewDownHotWS: 12, WriteDeadbandW: 2, RefreshS: 60,
		FreqBatFloorKHz: 3000000, FreqBatCeilKHz: 4000000, FreqSlewKHzS: 200000, FreqDeadbandKHz: 100000,
		HwMaxKHz: tspHwMax, EPP: "balance_power"}
	if p != want {
		t.Fatalf("DefaultParams(%d)\n got %+v\nwant %+v", tspHwMax, p, want)
	}
	if q := DefaultParams(4200000); q.HwMaxKHz != 4200000 {
		t.Fatalf("DefaultParams ignores hwMaxKHz: %d", q.HwMaxKHz)
	}
}

// TestP5IdleFixedPoint: from reachable states, 120 idle steps (Util 0, Temp 45) end at P == PminW; idle never
// integrates (I only leaks once TempS has settled); writes only on refresh ticks; I → 0 ± 1e-3 by 4 000 s.
func TestP5IdleFixedPoint(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for w := 0; w < tspN(200, 40); w++ {
		rng := rand.New(rand.NewSource(tspSeed + 2_000_000 + int64(w)))
		s := tspWalkState(p, w, 50+rng.Intn(250))
		in := Inputs{DT: 1, TempC: 45, SOC: rng.Float64(), OnAC: rng.Intn(2) == 0}
		for k := 0; k < 120; k++ {
			n, _ := Step(p, s, in)
			if k >= 20 && math.Abs(n.I-s.I*math.Exp(-1/p.IleakS)) > tspTol {
				t.Fatalf("P5 walk %d step %d: idle integrated I %.6f→%.6f (in %+v)", w, k, s.I, n.I, in)
			}
			s = n
		}
		for k := 0; k < 200; k++ {
			n, o := Step(p, s, in)
			due := s.SinceRefreshS+1 >= p.RefreshS
			if math.Abs(n.P-p.PminW) > tspTol || o.PptW != int(p.PminW) || o.WritePPT != due {
				t.Fatalf("P5 walk %d idle step %d: P %.6f ppt %d WritePPT %v (refresh due %v)", w, 120+k, n.P, o.PptW, o.WritePPT, due)
			}
			s = n
		}
		if s, _ = tspRun(p, s, in, 4000); math.Abs(s.I) > 1e-3 {
			t.Fatalf("P5 walk %d: |I| = %.6f after 4 320 idle s", w, math.Abs(s.I))
		}
	}
}

// TestP6HotConvergence: Temp held at Thi+5 with full demand drives P to PminW within 90 steps and keeps it there.
func TestP6HotConvergence(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	cases := []struct {
		name       string
		onAC, dgpu bool
		thi        float64
	}{{"ac", true, false, 88}, {"battery", false, false, 80}, {"dgpu", true, true, 85}}
	for _, tc := range cases {
		in := tspLoad(tc.onAC, 1, 60)
		in.DGPUBusy = tc.dgpu
		s, o := tspRun(p, State{}, in, 30)
		if math.Abs(s.P-o.PmaxW) > 0.05 {
			t.Fatalf("P6 %s: cool full load did not open the dial: P %.3f Pmax %.3f", tc.name, s.P, o.PmaxW)
		}
		in.TempC = tc.thi + 5
		for k := 1; k <= 400; k++ {
			s, o = Step(p, s, in)
			if k >= 90 && (s.P > p.PminW+0.1 || o.PptW != int(p.PminW)) {
				t.Fatalf("P6 %s: step %d at Thi+5: P %.4f ppt %d, want PminW (I %.3f)", tc.name, k, s.P, o.PptW, s.I)
			}
		}
	}
}

// TestP8DeterministicAcrossGoroutines: the same walk run concurrently ends in the same State (no hidden globals).
func TestP8DeterministicAcrossGoroutines(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	ch := make(chan State, 6)
	for g := 0; g < cap(ch); g++ {
		go func() { ch <- tspWalkState(p, 7, 2000) }()
	}
	first := <-ch
	for g := 1; g < cap(ch); g++ {
		if s := <-ch; s != first {
			t.Fatalf("P8: concurrent runs disagree:\n%+v\n%+v", first, s)
		}
	}
}

// TestP10FrequencyCap: AC converges to hwmax at ≤ 200 MHz/s; battery sits in [floor, ceil] and C3's degenerate
// battery top (SOC ≤ 15 % → PmaxSrc == PminW) pins the floor.
func TestP10FrequencyCap(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	s, _ := tspRun(p, State{}, tspLoad(false, 1, 50), 60)
	if s.F != p.FreqBatCeilKHz || math.Abs(s.P-p.PmaxBatHiW) > tspTol {
		t.Fatalf("P10: battery full load F %d P %.3f, want %d / %g", s.F, s.P, p.FreqBatCeilKHz, p.PmaxBatHiW)
	}
	for k := 1; k <= 12; k++ {
		s, _ = Step(p, s, tspLoad(true, 1, 50))
		if want := min(p.HwMaxKHz, p.FreqBatCeilKHz+k*p.FreqSlewKHzS); s.F != want {
			t.Fatalf("P10: AC glide step %d F %d, want %d", k, s.F, want)
		}
	}
	idle := tspLoad(false, 0, 50)
	if s, _ = tspRun(p, s, idle, 60); s.F != p.FreqBatFloorKHz {
		t.Fatalf("P10: battery idle F %d, want floor %d", s.F, p.FreqBatFloorKHz)
	}
	low := tspLoad(false, 1, 50)
	low.SOC = 0.1
	if s, _ = tspRun(p, s, low, 60); s.F != p.FreqBatFloorKHz || math.Abs(s.P-p.PminW) > tspTol {
		t.Fatalf("P10/C3: SOC 10%% full load F %d P %.3f, want floor and PminW", s.F, s.P)
	}
}

// TestP12DtRobustness: from settled reachable states, two dt=0.5 steps ≈ one dt=1 step.
func TestP12DtRobustness(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for w := 0; w < tspN(1000, 100); w++ {
		rng := rand.New(rand.NewSource(tspSeed + 3_000_000 + int64(w)))
		s := tspWalkState(p, w, 150)
		in := tspNextInputs(rng, Inputs{}, true)
		in.ProfileChanged, in.Resumed, in.DT = false, false, 1
		s, _ = tspRun(p, s, in, 60)
		a, _ := Step(p, s, in)
		in.DT = 0.5
		b, _ := tspRun(p, s, in, 2)
		if math.Abs(a.P-b.P) > 0.5 || math.Abs(a.TempS-b.TempS) > 0.5 {
			t.Fatalf("P12 walk %d: 1×1 s vs 2×0.5 s: P %.4f/%.4f TempS %.4f/%.4f\n  in=%+v\n  s=%+v", w, a.P, b.P, a.TempS, b.TempS, in, s)
		}
	}
}

// TestP13CeilingChangeIsAGlide: from reachable states, flipping OnAC or DGPUBusy never moves P by more than the
// slew allows; P2 in the walks covers every flip there too.
func TestP13CeilingChangeIsAGlide(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for w := 0; w < tspN(500, 50); w++ {
		s := tspWalkState(p, w, 200)
		in := tspLoad(w%2 == 0, 1, 50)
		in.DGPUBusy = w%4 < 2
		s, _ = tspRun(p, s, in, 30)
		if w%3 == 0 {
			in.OnAC = !in.OnAC
		} else {
			in.DGPUBusy = !in.DGPUBusy
		}
		for k := 0; k < 30; k++ {
			n, o := Step(p, s, in)
			down := p.SlewDownWS + (p.SlewDownHotWS-p.SlewDownWS)*tspClamp01((n.TempS-o.TargetTempC)/3)
			if n.P < s.P-down-tspTol || n.P > s.P+p.SlewUpWS+tspTol {
				t.Fatalf("P13 walk %d step %d: P %.4f → %.4f after ceiling flip (in %+v)", w, k, s.P, n.P, in)
			}
			s = n
		}
	}
}

// TestP14AntiWindup: 1 000 steps at 20 °C or 105 °C keep I inside its clamp; back on a model-perfect plant,
// |Thi − TempS| < 1 °C within 300 steps and stays.
func TestP14AntiWindup(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for _, hold := range []float64{20, 105} {
		in := tspLoad(true, 1, hold)
		var s State
		for k := 0; k < 1000; k++ {
			if s, _ = Step(p, s, in); s.I > p.ImaxW+tspTol || s.I < p.IminW-tspTol {
				t.Fatalf("P14 hold %g: step %d I = %.4f outside [%g, %g]", hold, k, s.I, p.IminW, p.ImaxW)
			}
		}
		T, last := hold, -1
		for k := 0; k < 900; k++ {
			in.TempC = T
			var o Outputs
			s, o = Step(p, s, in)
			T = tspPlant(p, T, s.P, 1)
			if math.Abs(o.TargetTempC-s.TempS) >= 1 {
				last = k
			}
		}
		if last >= 300 {
			t.Fatalf("P14 hold %g: |e| ≥ 1 °C still at plant step %d (want settled within 300)", hold, last)
		}
	}
}

// tspPlantRun runs full load on the plant for n s from (s, T) and returns peak overshoot of T above Thi and the
// last second at which |T − Thi| ≥ 1.
func tspPlantRun(p Params, s State, in Inputs, T float64, n int) (over float64, last int) {
	last = -1
	for k := 0; k < n; k++ {
		in.TempC = T
		var o Outputs
		s, o = Step(p, s, in)
		T = tspPlant(p, T, s.P, in.DT)
		over = math.Max(over, T-o.TargetTempC)
		if math.Abs(T-o.TargetTempC) >= 1 {
			last = k
		}
	}
	return over, last
}

// TestP14PlantOvershootAndSettle: DESIGN §5's tuning regression — from a cool idle machine, full load on the
// plant overshoots Thi by ≤ 4 °C and settles (|T − Thi| < 1 °C, for good) within 180 s. That needs the heat hand
// to bind (AC, no dGPU: T0 + Rth·45 = 100.5 °C > 88). On battery / with the dGPU the model's T at Pmax is below Thi
// (74.5 < 80, 81 < 85), so there the check is no overshoot at all and the dial stays at Pmax.
func TestP14PlantOvershootAndSettle(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for _, ac := range []bool{true, false} {
		for _, dgpu := range []bool{false, true} {
			idle := tspLoad(ac, 0, 50)
			idle.DGPUBusy = dgpu
			s, _ := tspRun(p, State{}, idle, 30)
			full := idle
			full.UtilAvg, full.UtilMax = 1, 1
			over, last := tspPlantRun(p, s, full, 50, 900)
			binds := ac && !dgpu
			if over > 4 || (binds && last >= 180) || (!binds && over > 0) {
				t.Errorf("plant ac=%v dgpu=%v: overshoot %.2f °C, last |T−Thi| ≥ 1 at %d s (want ≤ 4 °C, < 180 s)", ac, dgpu, over, last)
			}
		}
	}
}

// TestLoadStepFromIdle: DESIGN §6 load-step — from a cool idle dial, full demand reaches ppt ≥ 0.9·Pmax in ≤ 8 s.
func TestLoadStepFromIdle(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for _, ac := range []bool{true, false} {
		in := tspLoad(ac, 0, 45)
		s, _ := tspRun(p, State{}, in, 60)
		in.UtilAvg, in.UtilMax = 1, 1
		T, reached := 45.0, -1
		for k := 1; k <= 8 && reached < 0; k++ {
			in.TempC = T
			var o Outputs
			s, o = Step(p, s, in)
			T = tspPlant(p, T, s.P, 1)
			if float64(o.PptW) >= 0.9*o.PmaxW {
				reached = k
			}
		}
		if reached < 0 {
			t.Fatalf("load step ac=%v: ppt never reached 0.9·Pmax within 8 s (P %.2f)", ac, s.P)
		}
	}
}

// TestP15BatteryTaper: Pmax is non-decreasing and continuous in SOC (≤ 0.3 W per 1 %), at every dGPU blend.
func TestP15BatteryTaper(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	for _, gpu := range []float64{0, 0.5, 1} {
		prev := 0.0
		for i := 0; i <= 1000; i++ {
			s := State{Seeded: true, TempS: 50, P: 20, Gpu: gpu, F: 3500000, PptWritten: 20, FreqWritten: 3500000}
			in := Inputs{DT: 1, TempC: 50, SOC: float64(i) / 1000, DGPUBusy: gpu >= 0.5}
			_, o := Step(p, s, in)
			if i > 0 && (o.PmaxW < prev-tspTol || o.PmaxW-prev > 0.03+tspTol) {
				t.Fatalf("P15 gpu %.1f SOC %.3f: Pmax %.4f after %.4f", gpu, in.SOC, o.PmaxW, prev)
			}
			prev = o.PmaxW
		}
	}
	for _, c := range []struct{ soc, want float64 }{{0, 15}, {0.15, 15}, {0.325, 20}, {0.5, 25}, {1, 25}} {
		_, o := Step(p, State{Seeded: true, TempS: 50, P: 20}, Inputs{DT: 1, TempC: 50, SOC: c.soc})
		if math.Abs(o.PmaxW-c.want) > tspTol {
			t.Fatalf("P15: SOC %.3f Pmax %.4f, want %g", c.soc, o.PmaxW, c.want)
		}
	}
}

// ---------------------------------------------------------------- DESIGN §3.4 worked trajectories

// TestExampleIdleDesktop: idle → 15 W, level 0, one PPT write every 60 s, EPP and cap written once.
func TestExampleIdleDesktop(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	in := tspLoad(true, 0.05, 50)
	var s State
	var ppt, other []int
	for k := 0; k < 200; k++ {
		var o Outputs
		s, o = Step(p, s, in)
		if math.Abs(s.P-15) > tspTol || o.PptW != 15 || o.Level != 0 || o.Binding != "demand" {
			t.Fatalf("idle step %d: P %.4f ppt %d level %.3f binding %q", k, s.P, o.PptW, o.Level, o.Binding)
		}
		if o.WritePPT {
			ppt = append(ppt, k)
		}
		if o.WriteEPP || o.WriteFreq {
			other = append(other, k)
		}
	}
	if fmt.Sprint(ppt) != "[0 60 120 180]" || fmt.Sprint(other) != "[0]" {
		t.Fatalf("idle writes: PPT at %v (want [0 60 120 180]), EPP/freq at %v (want [0])", ppt, other)
	}
}

// TestExampleClickAndOneBusyCore: one core at 100 % → 15→21 W in the first second, ~22 W held, released at
// ≤ 3 W/s back to 15 W.
func TestExampleClickAndOneBusyCore(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	idle := tspLoad(true, 0.02, 50)
	s, _ := tspRun(p, State{}, idle, 100)
	core := idle
	core.UtilMax, core.UtilAvg = 1, 1.0/16
	s, _ = Step(p, s, core)
	if math.Abs(s.P-21) > tspTol || math.Abs(s.Demand-0.25) > tspTol {
		t.Fatalf("click: first second P %.4f Demand %.4f, want 21 W / 0.25", s.P, s.Demand)
	}
	s, o := tspRun(p, s, core, 30)
	if math.Abs(s.P-22) > 1.5 || o.PptW != 22 || o.Binding != "demand" {
		t.Fatalf("one busy core: P %.3f ppt %d binding %q, want ~22 W demand-bound", s.P, o.PptW, o.Binding)
	}
	for k := 1; k <= 15; k++ {
		n, _ := Step(p, s, idle)
		if n.P > s.P+tspTol || n.P < s.P-3-tspTol {
			t.Fatalf("release step %d: P %.4f → %.4f (must fall at ≤ 3 W/s)", k, s.P, n.P)
		}
		s = n
	}
	if math.Abs(s.P-15) > tspTol {
		t.Fatalf("release: P %.4f after 15 s, want 15", s.P)
	}
}

// TestExampleUnplugGlide: unplug at 45 W, cool → P glides 45→25 at exactly 3 W/s; F glides to 4 GHz at
// 200 MHz/s; the battery top is the binding hand.
func TestExampleUnplugGlide(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	s := State{Seeded: true, TempS: 50, Demand: 1, P: 45, F: tspHwMax, PptWritten: 45, FreqWritten: tspHwMax}
	in := tspLoad(false, 1, 50)
	var o Outputs
	for k := 1; k <= 10; k++ {
		s, o = Step(p, s, in)
		wantP := math.Max(25, 45-3*float64(k))
		wantF := max(p.FreqBatCeilKHz, tspHwMax-k*p.FreqSlewKHzS)
		if math.Abs(s.P-wantP) > tspTol || s.F != wantF || o.PmaxW != 25 {
			t.Fatalf("unplug step %d: P %.4f (want %g) F %d (want %d) Pmax %.3f", k, s.P, wantP, s.F, wantF, o.PmaxW)
		}
	}
	if o.Binding != "battery" {
		t.Fatalf("unplug: binding %q, want battery", o.Binding)
	}
}

// TestExampleHotReleaseRate: the release rate is 3 W/s at Thi, 12 W/s at Thi+3 and beyond, linear between.
func TestExampleHotReleaseRate(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	pff := (p.ThiAcC - p.T0C) / p.RthCPerW
	base := State{Seeded: true, Demand: 1, P: 45, F: tspHwMax, PptWritten: 45, FreqWritten: tspHwMax}
	for _, c := range []struct{ temp, wantP float64 }{{100, 33}, {89.5, 37.5}, {88.5, 40.5}, {88, 42}} {
		s := base
		s.TempS = c.temp
		n, o := Step(p, s, tspLoad(true, 1, c.temp))
		want := math.Max(c.wantP, pff+p.KpWPerC*(p.ThiAcC-c.temp))
		if math.Abs(n.P-want) > tspTol || o.Binding != "thermal" {
			t.Fatalf("hot release at %.1f °C: P %.4f binding %q, want %.4f thermal", c.temp, n.P, o.Binding, want)
		}
	}
	s := base
	s.TempS = 100
	s, _ = tspRun(p, s, tspLoad(true, 1, 100), 2)
	if want := pff + p.KpWPerC*(p.ThiAcC-100) - 0.6; math.Abs(s.P-want) > tspTol {
		t.Fatalf("hot release second tick: P %.4f, want Ptarget %.4f (I −0.6 after one tick)", s.P, want)
	}
}

// TestExampleDGPUBlend: the RTX 4050 waking blends Pmax 45→30 and Thi 88→85 over TauGpu = 5 s; P follows
// without a jump.
func TestExampleDGPUBlend(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	s := State{Seeded: true, TempS: 50, Demand: 1, P: 45, F: tspHwMax, PptWritten: 45, FreqWritten: tspHwMax}
	in := tspLoad(true, 1, 50)
	in.DGPUBusy = true
	for k := 1; k <= 40; k++ {
		n, o := Step(p, s, in)
		g := 1 - math.Exp(-float64(k)/p.TauGpuS)
		if math.Abs(o.PmaxW-(45-15*g)) > tspTol || math.Abs(o.TargetTempC-(88-3*g)) > tspTol {
			t.Fatalf("dGPU step %d: Pmax %.4f Thi %.4f, want %.4f / %.4f", k, o.PmaxW, o.TargetTempC, 45-15*g, 88-3*g)
		}
		if math.Abs(n.P-o.PmaxW) > tspTol || n.P > s.P || s.P-n.P > 3+tspTol || o.Binding != "dgpu" {
			t.Fatalf("dGPU step %d: P %.4f → %.4f (Pmax %.4f) binding %q", k, s.P, n.P, o.PmaxW, o.Binding)
		}
		s = n
	}
	if math.Abs(s.P-30) > 0.01 {
		t.Fatalf("dGPU: P %.4f after 40 s, want ≈ 30", s.P)
	}
}

// TestExampleResumed: resume re-seeds TempS, zeroes Demand and I, keeps P (then slews), forces every write.
func TestExampleResumed(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	s, _ := tspRun(p, State{}, tspLoad(true, 1, 100), 100)
	if s.I > -1 {
		t.Fatalf("setup: hot full load should wind I negative, I = %.3f", s.I)
	}
	for _, ext := range []bool{false, true} {
		in := tspLoad(true, 0, 50)
		in.Resumed, in.PPTOwnerExternal = true, ext
		n, o := Step(p, s, in)
		if n.Demand != 0 || o.Demand != 0 || n.I != 0 || n.TempS != 50 {
			t.Fatalf("resume ext=%v: Demand %g/%g I %g TempS %g, want 0/0/0/50", ext, n.Demand, o.Demand, n.I, n.TempS)
		}
		if o.WritePPT == ext || !o.WriteEPP || !o.WriteFreq || math.Abs(n.P-math.Max(15, s.P-3)) > tspTol {
			t.Fatalf("resume ext=%v: writes ppt/epp/freq %v/%v/%v, P %.4f→%.4f", ext, o.WritePPT, o.WriteEPP, o.WriteFreq, s.P, n.P)
		}
	}
}

// TestExampleExternalOwner: under PPTOwnerExternal the core keeps computing but never writes PPT and leaves
// PptWritten alone (C6); on release a moved dial or a due refresh is re-asserted on the very next tick.
func TestExampleExternalOwner(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	idle := tspLoad(true, 0, 50)
	s0, _ := tspRun(p, State{}, idle, 30)
	for _, c := range []struct {
		name  string
		util  float64
		ticks int
	}{{"dial moved", 1, 10}, {"refresh due", 0, 70}} {
		in := idle
		in.UtilAvg, in.UtilMax, in.PPTOwnerExternal = c.util, c.util, true
		s := s0
		for k := 0; k < c.ticks; k++ {
			n, o := Step(p, s, in)
			if o.WritePPT || n.PptWritten != s0.PptWritten || n.SinceRefreshS < s.SinceRefreshS {
				t.Fatalf("%s tick %d: external owner but WritePPT %v PptWritten %d since %.1f→%.1f", c.name, k, o.WritePPT, n.PptWritten, s.SinceRefreshS, n.SinceRefreshS)
			}
			s = n
		}
		in.PPTOwnerExternal = false
		n, o := Step(p, s, in)
		if !o.WritePPT || n.PptWritten != o.PptW {
			t.Fatalf("%s: release tick WritePPT %v (ppt %d, written %d)", c.name, o.WritePPT, o.PptW, n.PptWritten)
		}
	}
}

// TestExampleExternalShortRelease is C6's literal "next tick with PPTOwnerExternal=false must WritePPT=true", in
// the hard case: a 3-tick external hold, dial unmoved, no refresh due. State has no "owner" field, so the core can
// only satisfy it by parking SinceRefreshS at RefreshS while external (tolerated by tspCheckWrites); a core that
// just lets SinceRefreshS accumulate fails here.
func TestExampleExternalShortRelease(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	idle := tspLoad(true, 0, 50)
	s, _ := tspRun(p, State{}, idle, 30)
	ext := idle
	ext.PPTOwnerExternal = true
	s, _ = tspRun(p, s, ext, 3)
	if _, o := Step(p, s, idle); !o.WritePPT {
		t.Fatal("C6: no PPT re-assert on the tick after the external owner released the dial")
	}
}

// TestExampleProfileChanged: a platform-profile change re-writes PPT and EPP (EPP even under an external owner),
// and is not a reason to re-write the frequency cap.
func TestExampleProfileChanged(t *testing.T) {
	t.Parallel()
	p := DefaultParams(tspHwMax)
	s, _ := tspRun(p, State{}, tspLoad(true, 1, 60), 40)
	for _, ext := range []bool{false, true} {
		in := tspLoad(true, 1, 60)
		in.ProfileChanged, in.PPTOwnerExternal = true, ext
		_, o := Step(p, s, in)
		if o.WritePPT == ext || !o.WriteEPP || o.WriteFreq {
			t.Fatalf("profile change ext=%v: WritePPT %v WriteEPP %v WriteFreq %v", ext, o.WritePPT, o.WriteEPP, o.WriteFreq)
		}
	}
}
