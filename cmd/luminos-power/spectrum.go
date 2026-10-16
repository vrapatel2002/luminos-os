// [CHANGE: claude-code | 2026-10-15] DESIGN docs/spectrum/DESIGN.md — continuous power dial
package main

import "math"

// Params holds every constant of the dial (DESIGN §3.4); DefaultParams gives v1 values.
type Params struct {
	TickS, PminW, PmaxAcW, PmaxBatHiW, PmaxBatLoW, PmaxDgpuW, ThiAcC, ThiBatC, ThiDgpuC,
	T0C, RthCPerW, KpWPerC, KiWPerCS, IminW, ImaxW, IleakS, TauTempS, TauDemandS, TauGpuS, D0, D1,
	SlewUpWS, SlewDownWS, SlewDownHotWS, WriteDeadbandW, RefreshS float64
	FreqBatFloorKHz, FreqBatCeilKHz, FreqSlewKHzS, FreqDeadbandKHz, HwMaxKHz int
	EPP                                                                      string
}

// Inputs is one tick of sensor facts from the I/O layer (DESIGN §3.3).
type Inputs struct {
	DT, UtilAvg, UtilMax, IGPUBusy, TempC, SOC                float64
	OnAC, DGPUBusy, PPTOwnerExternal, ProfileChanged, Resumed bool
}

// State is the core's memory, passed and returned by value.
type State struct {
	TempS, Demand, I, Gpu, P, SinceRefreshS float64
	F, PptWritten, FreqWritten              int
	Seeded                                  bool
}

// Outputs tells the I/O layer what to write and what to show.
type Outputs struct {
	Level, TargetTempC, PmaxW, Demand float64
	PptW, FreqCapKHz                  int
	EPP, Binding                      string
	WritePPT, WriteFreq, WriteEPP     bool
}

// DefaultParams returns the DESIGN §3.4 table; hwMaxKHz is cpuinfo_max_freq.
func DefaultParams(hwMaxKHz int) Params {
	return Params{
		TickS: 1, PminW: 15, PmaxAcW: 45, PmaxBatHiW: 25, PmaxBatLoW: 15, PmaxDgpuW: 30,
		ThiAcC: 88, ThiBatC: 80, ThiDgpuC: 85, T0C: 42, RthCPerW: 1.3,
		KpWPerC: 0.75, KiWPerCS: 0.05, IminW: -25, ImaxW: 10, IleakS: 300,
		TauTempS: 2, TauDemandS: 6, TauGpuS: 5, D0: 0.08, D1: 0.80,
		SlewUpWS: 6, SlewDownWS: 3, SlewDownHotWS: 12, WriteDeadbandW: 2, RefreshS: 60,
		FreqBatFloorKHz: 3000000, FreqBatCeilKHz: 4000000, FreqSlewKHzS: 200000,
		FreqDeadbandKHz: 100000, HwMaxKHz: hwMaxKHz, EPP: "balance_power",
	}
}

func clamp(x, lo, hi float64) float64 { return math.Max(lo, math.Min(hi, x)) }
func clamp01(x float64) float64       { return clamp(x, 0, 1) }
func lerp(a, b, x float64) float64    { return a + (b-a)*x }
func b2f(b bool) float64 {
	if b {
		return 1
	}
	return 0
}

// seed is step 0: fresh start or resume resets the filters (C1, C5).
func seed(p Params, s State, in Inputs) State {
	s.TempS, s.Demand, s.I, s.Gpu = in.TempC, 0, 0, b2f(in.DGPUBusy)
	if !s.Seeded {
		s.P, s.F = p.PminW, p.HwMaxKHz
	}
	s.Seeded = true
	return s
}

// smooth is steps 1–3 (filters): Tctl EMA, demand peak-hold, dGPU blend. Returns Ldem.
func smooth(p Params, s State, in Inputs, dt float64) (State, float64) {
	s.TempS += (1 - math.Exp(-dt/p.TauTempS)) * (in.TempC - s.TempS) // 1
	dRaw := math.Max(in.UtilAvg, math.Max(in.UtilMax/4, 0.8*in.IGPUBusy))
	s.Demand = math.Max(dRaw, s.Demand*math.Exp(-dt/p.TauDemandS)) // 2
	if s.Demand < 0.005 {
		s.Demand = 0
	}
	s.Gpu += (1 - math.Exp(-dt/p.TauGpuS)) * (b2f(in.DGPUBusy) - s.Gpu) // 3
	return s, clamp01((s.Demand - p.D0) / (p.D1 - p.D0))
}

// ceilings is step 3: source top (AC or SOC taper), then the blended dGPU yield.
func ceilings(p Params, s State, in Inputs) (pmaxSrc, pmax, thi float64) {
	pmaxSrc = p.PmaxAcW
	thiSrc := p.ThiAcC
	if !in.OnAC {
		pmaxSrc = lerp(p.PmaxBatLoW, p.PmaxBatHiW, clamp01((in.SOC-0.15)/0.35))
		thiSrc = p.ThiBatC
	}
	pmax = lerp(pmaxSrc, math.Min(pmaxSrc, p.PmaxDgpuW), s.Gpu)
	thi = lerp(thiSrc, math.Min(thiSrc, p.ThiDgpuC), s.Gpu)
	return pmaxSrc, pmax, thi
}

// integrate is step 6: conditional integration (anti-windup), else leak toward 0.
func integrate(p Params, s State, e, pthRaw, pth, pdem, pmax, dt float64) float64 {
	onDial := pth <= pdem || e < 0
	notPinned := (pthRaw < pmax || e < 0) && (pthRaw > p.PminW || e > 0)
	if onDial && notPinned {
		return clamp(s.I+p.KiWPerCS*e*dt, p.IminW, p.ImaxW)
	}
	return s.I * math.Exp(-dt/p.IleakS)
}

// slew is step 7: the one rate limiter; release speeds up continuously above Thi.
func slew(p Params, s State, ptarget, thi, dt float64) float64 {
	down := p.SlewDownWS + (p.SlewDownHotWS-p.SlewDownWS)*clamp01((s.TempS-thi)/3)
	return clamp(ptarget, s.P-down*dt, s.P+p.SlewUpWS*dt)
}

// freqCap is step 8 (C3): AC → hwmax; battery → floor..ceil by P over the battery's span, glided.
func freqCap(p Params, s State, in Inputs, pmaxSrc, dt float64) int {
	ft, lo := float64(p.HwMaxKHz), 0.0
	if !in.OnAC {
		lo, ft = float64(p.FreqBatFloorKHz), float64(p.FreqBatFloorKHz)
		if span := pmaxSrc - p.PminW; span >= 0.5 {
			ft += clamp01((s.P-p.PminW)/span) * float64(p.FreqBatCeilKHz-p.FreqBatFloorKHz)
		}
	}
	step := float64(p.FreqSlewKHzS) * dt
	f := clamp(ft, float64(s.F)-step, float64(s.F)+step)
	return int(math.Round(math.Min(math.Max(f, lo), float64(p.HwMaxKHz))))
}

// bindingOf is step 5's display label: which hand holds the dial.
func bindingOf(p Params, pth, pdem, ptarget, pmax, pmaxSrc float64) string {
	if pmax < p.PmaxAcW && math.Abs(ptarget-pmax) < 1e-9 {
		if pmax < pmaxSrc {
			return "dgpu"
		}
		return "battery"
	}
	if pth <= pdem {
		return "thermal"
	}
	return "demand"
}

// writes is step 9: deadbands, refresh, events, and the external-owner yield (C6).
func writes(p Params, s State, in Inputs, o Outputs, force bool, dt float64) (State, Outputs) {
	s.SinceRefreshS += dt
	dPpt := math.Abs(float64(o.PptW - s.PptWritten))
	o.WritePPT = force || in.ProfileChanged || s.SinceRefreshS >= p.RefreshS || dPpt >= p.WriteDeadbandW
	o.WriteFreq = force || math.Abs(float64(s.F-s.FreqWritten)) >= float64(p.FreqDeadbandKHz)
	o.WriteEPP = force || in.ProfileChanged
	if in.PPTOwnerExternal {
		// C6: yield; keep a refresh owed so the first internal tick re-asserts.
		o.WritePPT = false
		s.SinceRefreshS = math.Max(s.SinceRefreshS, p.RefreshS)
	}
	if o.WritePPT {
		s.PptWritten, s.SinceRefreshS = o.PptW, 0
	}
	if o.WriteFreq {
		s.FreqWritten = s.F
	}
	return s, o
}

// Step is the whole decision (DESIGN §3.4 steps 0–9). Pure: no I/O, no clock but in.DT.
func Step(p Params, s State, in Inputs) (State, Outputs) {
	dt := clamp(in.DT, 0.5, 3) // C1
	force := !s.Seeded || in.Resumed
	if force {
		s = seed(p, s, in) // 0
	}
	s, ldem := smooth(p, s, in, dt)
	pmaxSrc, pmax, thi := ceilings(p, s, in)
	e := thi - s.TempS // 4
	pthRaw := (thi-p.T0C)/p.RthCPerW + p.KpWPerC*e + s.I
	pth := clamp(pthRaw, p.PminW, pmax)
	pdem := p.PminW + ldem*(pmax-p.PminW) // 5
	ptarget := math.Min(pdem, pth)
	s.I = integrate(p, s, e, pthRaw, pth, pdem, pmax, dt) // 6
	s.P = slew(p, s, ptarget, thi, dt)                    // 7
	s.F = freqCap(p, s, in, pmaxSrc, dt)                  // 8
	o := Outputs{
		Level: clamp01((s.P - p.PminW) / (p.PmaxAcW - p.PminW)), TargetTempC: thi, PmaxW: pmax,
		Demand: s.Demand, PptW: int(math.Round(s.P)), FreqCapKHz: s.F, EPP: p.EPP,
		Binding: bindingOf(p, pth, pdem, ptarget, pmax, pmaxSrc),
	}
	return writes(p, s, in, o, force, dt) // 9
}
