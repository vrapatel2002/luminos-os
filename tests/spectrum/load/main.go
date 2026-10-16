// [CHANGE: claude-code | 2026-10-15] spectrum
// Command load is the spectrum A/B CPU load generator and benchmark (replaces stress-ng/sysbench).
// Each worker runs a fixed xorshift + multiply-add kernel during the busy part of every 100 ms
// period (-duty %), sleeps the rest, and counts kernel ops. Output: total ops, ops/s and a
// per-second ops series. Deterministic: fixed seeds, fixed chunk size, stdlib only.
//
//	go run ./tests/spectrum/load -threads 16 -duty 100 -seconds 120 -json
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

const (
	period = 100 * time.Millisecond
	chunk  = 4096 // kernel iterations between clock checks; 1 op = 1 iteration
)

var sink atomic.Uint64 // keeps the kernel's result alive so the compiler cannot drop it

type result struct {
	Threads   int      `json:"threads"`
	Duty      int      `json:"duty"`
	Seconds   float64  `json:"seconds"`
	TotalOps  uint64   `json:"total_ops"`
	OpsPerSec float64  `json:"ops_per_s"`
	Series    []uint64 `json:"series"` // ops completed in each whole second
}

// kernel runs n iterations of a 64-bit xorshift feeding a float multiply-add chain.
func kernel(x uint64, f float64, n int) (uint64, float64) {
	for i := 0; i < n; i++ {
		x ^= x << 13
		x ^= x >> 7
		x ^= x << 17
		f = math.FMA(f, 0.9999999, float64(x&0xffff)*1e-9)
	}
	return x, f
}

// worker spins on the kernel during busy windows until deadline, adding ops to ctr.
func worker(id int, duty float64, start, deadline time.Time, ctr *atomic.Uint64, wg *sync.WaitGroup) {
	defer wg.Done()
	runtime.LockOSThread()
	x, f := uint64(0x9E3779B97F4A7C15)^uint64(id+1)*0xBF58476D1CE4E5B9, 1.0
	busy := time.Duration(duty * float64(period))
	for p := start; p.Before(deadline); p = p.Add(period) {
		end := p.Add(busy)
		if end.After(deadline) {
			end = deadline
		}
		for time.Now().Before(end) {
			x, f = kernel(x, f, chunk)
			ctr.Add(chunk)
		}
		if next := p.Add(period); duty < 1 && next.Before(deadline) {
			time.Sleep(time.Until(next))
		}
	}
	sink.Add(x ^ math.Float64bits(f))
}

func main() {
	threads := flag.Int("threads", runtime.NumCPU(), "worker threads")
	duty := flag.Int("duty", 100, "percent of each 100 ms period that is busy (0-100)")
	secs := flag.Float64("seconds", 10, "run time in seconds")
	asJSON := flag.Bool("json", false, "print one JSON object instead of text")
	flag.Parse()
	if *threads < 1 || *duty < 0 || *duty > 100 || *secs <= 0 {
		fmt.Fprintln(os.Stderr, "load: need -threads >= 1, -duty 0..100, -seconds > 0")
		os.Exit(2)
	}
	runtime.GOMAXPROCS(max(runtime.NumCPU(), *threads+1))

	var ctr atomic.Uint64
	var wg sync.WaitGroup
	start := time.Now()
	deadline := start.Add(time.Duration(*secs * float64(time.Second)))
	if *duty > 0 {
		for i := 0; i < *threads; i++ {
			wg.Add(1)
			go worker(i, float64(*duty)/100, start, deadline, &ctr, &wg)
		}
	}

	var series []uint64
	var last uint64
	tick := time.NewTicker(time.Second)
	for t := range tick.C {
		if t.After(deadline) {
			break
		}
		now := ctr.Load()
		series = append(series, now-last)
		last = now
	}
	tick.Stop()
	wg.Wait()
	elapsed := time.Since(start).Seconds()
	total := ctr.Load()
	if rest := total - last; rest > 0 && len(series) < int(math.Ceil(*secs)) {
		series = append(series, rest)
	}

	r := result{Threads: *threads, Duty: *duty, Seconds: math.Round(elapsed*1000) / 1000,
		TotalOps: total, OpsPerSec: math.Round(float64(total) / elapsed), Series: series}
	if *asJSON {
		if err := json.NewEncoder(os.Stdout).Encode(r); err != nil {
			fmt.Fprintln(os.Stderr, "load:", err)
			os.Exit(1)
		}
		return
	}
	fmt.Printf("threads=%d duty=%d%% seconds=%.3f total_ops=%d ops_per_s=%.0f\n",
		r.Threads, r.Duty, r.Seconds, r.TotalOps, r.OpsPerSec)
	for i, v := range r.Series {
		fmt.Printf("  t=%3ds ops=%d\n", i+1, v)
	}
}
