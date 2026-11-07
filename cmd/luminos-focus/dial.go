// Command luminos-focus: KWin window visibility → per-app CPUWeight/CPUQuota on app.slice units.
// [CHANGE: claude-code | 2026-11-07]
package main

import (
	"fmt"
	"math"
)

// Tunables, in one place: hidden apps get hiddenQuota % of one core; fullQuota % (16 threads) = no quota.
const hiddenQuota, fullQuota = 25, 1600

type Want struct { // the CPU share for one unit
	Weight   uint64 `json:"weight"`
	QuotaPct int    `json:"quotaPct"` // 0 = no quota
	Why      string `json:"why"`
}

func Dial(f float64, focused bool, exempt bool) Want { // one continuous dial, no modes
	if focused {
		return Want{1000, 0, "focused"}
	}
	if exempt {
		return Want{100, 0, "exempt"}
	}
	if math.IsNaN(f) || f < 0 {
		f = 0
	}
	f = math.Min(f, 1)
	q := int(math.Round(hiddenQuota + (fullQuota-hiddenQuota)*f))
	if q >= fullQuota {
		q = 0
	}
	return Want{uint64(math.Round(20 + 80*f)), q, fmt.Sprintf("f=%.2f", f)}
}

func Higher(a, b Want) bool { // a grants strictly more than b (weight up, or quota up/removed)
	return a.Weight > b.Weight || quota(a.QuotaPct) > quota(b.QuotaPct)
}

func quota(q int) int { // makes "no quota" (0) comparable: it is fullQuota
	if q == 0 {
		return fullQuota
	}
	return q
}
