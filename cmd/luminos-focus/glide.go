// Applies targets: raises at once, lowers in 4 steps over 2 s, releases forgotten units.
// [CHANGE: claude-code | 2026-11-07]
package main

import "time"

const glideSteps, glideEvery = 4, 500 * time.Millisecond

var rest = Want{100, 0, "release"} // systemd's default share: what every unit goes back to

// Setter applies a Want to a unit (systemd in production, a fake in tests). It logs its own errors.
type Setter interface {
	Set(unit string, w Want) error
}

type glide struct {
	from, to Want
	step     int
	next     time.Time
}

type Glider struct {
	s       Setter
	now     func() time.Time
	applied map[string]Want
	glides  map[string]*glide
	target  map[string]Want
}

func NewGlider(s Setter, now func() time.Time) *Glider {
	return &Glider{s: s, now: now, applied: map[string]Want{}, glides: map[string]*glide{}}
}

// Apply aims every unit at its target; touched units absent from target aim at rest, then are forgotten.
func (g *Glider) Apply(target map[string]Want) {
	g.target = target
	for u := range g.applied {
		if _, ok := target[u]; !ok {
			g.aim(u, rest)
		}
	}
	for u, w := range target {
		g.aim(u, w)
	}
}

func (g *Glider) aim(u string, w Want) {
	cur, ok := g.applied[u]
	if !ok {
		cur = rest
	}
	gl := g.glides[u]
	switch {
	case Higher(w, cur):
		delete(g.glides, u)
		g.set(u, w)
	case same(w, cur):
		delete(g.glides, u)
		g.forget(u)
	case gl == nil || !same(gl.to, w):
		g.applied[u] = cur // tracked from now on, so dropping it from target cancels the glide
		g.glides[u] = &glide{from: cur, to: w, next: g.now().Add(glideEvery)}
	}
}

func (g *Glider) Tick() {
	now := g.now()
	for u, gl := range g.glides {
		if now.Before(gl.next) {
			continue
		}
		gl.step++
		gl.next = gl.next.Add(glideEvery)
		if gl.step == glideSteps {
			delete(g.glides, u)
		}
		g.set(u, lerp(gl.from, gl.to, gl.step))
	}
}

func (g *Glider) ResetAll() {
	for u := range g.applied {
		_ = g.s.Set(u, rest)
	}
	g.applied, g.glides, g.target = map[string]Want{}, map[string]*glide{}, nil
}

func (g *Glider) set(u string, w Want) {
	_ = g.s.Set(u, w) // a vanished unit is logged by the Setter and otherwise ignored
	g.applied[u] = w
	g.forget(u)
}

func (g *Glider) forget(u string) { // drops a unit back at rest, no longer wanted and not gliding
	_, wanted := g.target[u]
	if !wanted && g.glides[u] == nil && same(g.applied[u], rest) {
		delete(g.applied, u)
	}
}

func same(a, b Want) bool { return a.Weight == b.Weight && a.QuotaPct == b.QuotaPct }

func lerp(a, b Want, i int) Want { // step i of glideSteps from a to b, linear in weight and quota
	w := int(a.Weight) + (int(b.Weight)-int(a.Weight))*i/glideSteps
	q := quota(a.QuotaPct) + (quota(b.QuotaPct)-quota(a.QuotaPct))*i/glideSteps
	if q >= fullQuota {
		q = 0
	}
	return Want{uint64(w), q, b.Why}
}

func throttles(units map[string]Want) bool {
	for _, w := range units {
		if w.Weight < 100 {
			return true
		}
	}
	return false
}

func toggle(t *time.Ticker, every time.Duration, on *bool, want bool) { // only on a change: never restarts a period
	if want == *on {
		return
	}
	if want {
		t.Reset(every)
	} else {
		t.Stop()
	}
	*on = want
}
