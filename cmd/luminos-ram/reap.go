// reap.go — the luminos-ram APP REAPER (DECISION 160).
// [CHANGE: claude-code | 2026-10-24]
//
// Shawn: "If the app/software/code is not live and working, remove it from RAM. Stop
// wasting RAM. Do not keep leftovers in RAM: when a process/app dies, get out, remove
// everything related to it."
//
// This file is an ADDITION. The LIRS / HotSet / madvise algorithm in main.go is untouched.
//
// WHY THE REAPER RUNS AS THE USER, NOT INSIDE THE ROOT DAEMON
//   The root daemon (luminos-ram.service) runs with exactly CAP_SYS_PTRACE, CAP_SYS_NICE and
//   CAP_KILL and PrivateTmp=true. Measured 2026-10-24, that means it
//     - sees its own private /tmp, not the tmpfs where the 576 MB of MW4 debug files sit,
//     - cannot open /run/user/1000 (no CAP_DAC_OVERRIDE), so no session bus, no KWin, no
//       PipeWire, no `systemctl --user`  (its own KWin listener has logged ZERO focus events
//       since the 2026-10-22 boot — BUG-214),
//   and every one of those is needed to decide "is this app live" and to stop an app's unit.
//   So the same binary runs a second time as `luminos-ram reaper` under the user manager
//   (systemd/user/luminos-ram-reaper.service). That half measures, decides and acts on the
//   user's own processes. The root half does only what needs root: the one system unit on
//   the list (proton.VPN.service), and it serves the `/reap` report on ram.sock + :9091.
//
// SHAPE
//   - Everything that decides is a pure function over a snapshot (procs, windows, audio,
//     sockets, GPU, MemAvailable) so reap_test.go can drive it with a fake /proc tree.
//   - "Live" is MEASURED: a window, recent focus, audio, network traffic, a listen socket
//     with a client, CPU, disk I/O, a busy GPU fd, or the keep-list. Never a name guess.
//   - Grouping is by APP: the systemd unit (cgroup) of the user manager; Wine is regrouped
//     by WINEPREFIX across units; leftovers are judged inside their group.
//   - The idle time an app may sit before it is reaped is a smooth function of MemAvailable
//     (idleAllowed). There is no "aggressive mode".
//   - reap_mode = "log" (default) only logs WOULD-REAP lines. "act" acts.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const clkTck = 100 // USER_HZ on x86_64 Linux

// ───────────────────────────── configuration ─────────────────────────────

// ReapConfig is read from ~/.config/luminos-ram-reaper.conf (key = value, # comments).
type ReapConfig struct {
	Mode            string        // "log" | "act"
	Tick            time.Duration // proc scan + leftover rules
	FullEvery       time.Duration // windows/audio/net/GPU refresh + idle rule
	IdleMaxMin      float64       // idle allowed when MemAvailable >= AvailHiGB
	IdleMinMin      float64       // idle allowed when MemAvailable <= AvailLoGB
	AvailHiGB       float64
	AvailLoGB       float64
	CPUPct          float64 // live if group CPU >= this (% of one core) averaged over WindowSec
	IOMBps          float64 // live if read+write >= this
	DownloadKBps    float64 // live if write >= this ("active download")
	NetKBps         float64 // live if established TCP traffic >= this
	GPUPct          float64 // live if a render-node fd's engines are busy >= this
	FocusRecentMin  float64
	ListenClientMin float64
	WindowSec       float64       // averaging window for CPU / I/O / net
	LeftoverGrace   time.Duration // how long a leftover must stay a leftover before it is reaped
	TermWait        time.Duration // SIGTERM → SIGKILL
	TmpfsMinMB      float64
	TmpfsAgeMin     float64
	TmpfsDirs       []string
	TmpfsEvery      time.Duration
	Keep            []string // never reap anything matching (unit, comm, argv0, prefix)
	ActOnly         []string // in "log" mode, still ACT on groups matching these (tests)
	TestIdleSec     float64  // when > 0, idle allowed for ActOnly groups only
	MaxProfileDir   string   // the Claude Max app's profile — never reaped
	Home            string
}

func defaultReapConfig(home string) ReapConfig {
	return ReapConfig{
		Mode:            "log",
		Tick:            2 * time.Second,
		// Windows, audio (pw-dump), sockets (ss), GPU: every 30 s, or every tick while a leftover
		// waits out its grace. At 10 s the agent cost ~0.9 % of a core, half of it pw-dump + ss.
		FullEvery:       30 * time.Second,
		IdleMaxMin:      60,
		IdleMinMin:      2,
		AvailHiGB:       6,
		AvailLoGB:       1,
		CPUPct:          2,
		IOMBps:          1,
		DownloadKBps:    100,
		NetKBps:         1,
		GPUPct:          1,
		FocusRecentMin:  5,
		ListenClientMin: 10,
		WindowSec:       60,
		LeftoverGrace:   4 * time.Second,
		TermWait:        5 * time.Second,
		TmpfsMinMB:      50,
		TmpfsAgeMin:     30,
		TmpfsDirs:       []string{"/tmp", "/dev/shm"},
		TmpfsEvery:      60 * time.Second,
		// Defaults that must survive an empty config. Shawn's own entries are ADDED to these.
		// metatrader/terminal64/xvfb: the forex bot runs MT5 under Wine on a headless Xvfb —
		// it has no KWin window by design, and it must never be "tidied away".
		Keep:          []string{"metatrader", "terminal64.exe", "metaeditor64.exe", "xvfb"},
		MaxProfileDir: filepath.Join(home, ".config/Claude"),
		Home:          home,
	}
}

func splitList(v string) []string {
	var out []string
	for _, s := range strings.Split(v, ",") {
		if s = strings.TrimSpace(s); s != "" {
			out = append(out, s)
		}
	}
	return out
}

// parseReapConfig applies `key = value` lines on top of the defaults. Unknown keys and bad
// values are returned as warnings rather than silently ignored.
func parseReapConfig(text string, base ReapConfig) (ReapConfig, []string) {
	c := base
	var warn []string
	sc := bufio.NewScanner(strings.NewReader(text))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			warn = append(warn, "no '=' in: "+line)
			continue
		}
		if i := strings.Index(v, "#"); i >= 0 {
			v = v[:i] // inline comment
		}
		k, v = strings.TrimSpace(k), strings.Trim(strings.TrimSpace(v), `"`)
		f, ferr := strconv.ParseFloat(v, 64)
		num := func(dst *float64) {
			if ferr != nil || f < 0 {
				warn = append(warn, fmt.Sprintf("%s: not a non-negative number: %q", k, v))
				return
			}
			*dst = f
		}
		dur := func(dst *time.Duration) {
			if ferr != nil || f <= 0 {
				warn = append(warn, fmt.Sprintf("%s: not a positive number of seconds: %q", k, v))
				return
			}
			*dst = time.Duration(f * float64(time.Second))
		}
		switch k {
		case "reap_mode":
			if v != "log" && v != "act" {
				warn = append(warn, fmt.Sprintf("reap_mode must be log or act, got %q — staying %q", v, c.Mode))
			} else {
				c.Mode = v
			}
		case "idle_max_min":
			num(&c.IdleMaxMin)
		case "idle_min_min":
			num(&c.IdleMinMin)
		case "avail_hi_gb":
			num(&c.AvailHiGB)
		case "avail_lo_gb":
			num(&c.AvailLoGB)
		case "cpu_pct":
			num(&c.CPUPct)
		case "io_mbps":
			num(&c.IOMBps)
		case "download_kbps":
			num(&c.DownloadKBps)
		case "net_kbps":
			num(&c.NetKBps)
		case "gpu_pct":
			num(&c.GPUPct)
		case "focus_recent_min":
			num(&c.FocusRecentMin)
		case "listen_client_min":
			num(&c.ListenClientMin)
		case "window_s":
			num(&c.WindowSec)
		case "tick_s":
			dur(&c.Tick)
		case "full_every_s":
			dur(&c.FullEvery)
		case "leftover_grace_s":
			dur(&c.LeftoverGrace)
		case "term_wait_s":
			dur(&c.TermWait)
		case "tmpfs_min_mb":
			num(&c.TmpfsMinMB)
		case "tmpfs_age_min":
			num(&c.TmpfsAgeMin)
		case "tmpfs_every_s":
			dur(&c.TmpfsEvery)
		case "tmpfs_dirs":
			c.TmpfsDirs = splitList(v)
		case "keep":
			c.Keep = append(c.Keep, splitList(v)...)
		case "act_only":
			c.ActOnly = splitList(v)
		case "test_idle_s":
			num(&c.TestIdleSec)
		case "max_profile_dir":
			c.MaxProfileDir = filepath.Clean(v)
		default:
			warn = append(warn, "unknown key: "+k)
		}
	}
	if c.AvailHiGB <= c.AvailLoGB {
		warn = append(warn, fmt.Sprintf("avail_hi_gb (%.1f) must be above avail_lo_gb (%.1f) — using 6/1", c.AvailHiGB, c.AvailLoGB))
		c.AvailHiGB, c.AvailLoGB = 6, 1
	}
	if c.IdleMinMin > c.IdleMaxMin {
		c.IdleMinMin, c.IdleMaxMin = c.IdleMaxMin, c.IdleMinMin
	}
	return c, warn
}

// idleAllowed is the gradient: how long an app may sit idle before it is reaped. It slides
// linearly from IdleMaxMin (MemAvailable >= AvailHiGB) to IdleMinMin (<= AvailLoGB).
// One continuous dial, no modes — the same rule Shawn set for power (DECISION 146).
func idleAllowed(availGB float64, c ReapConfig) time.Duration {
	f := (availGB - c.AvailLoGB) / (c.AvailHiGB - c.AvailLoGB)
	if f < 0 {
		f = 0
	}
	if f > 1 {
		f = 1
	}
	min := c.IdleMinMin + f*(c.IdleMaxMin-c.IdleMinMin)
	return time.Duration(min * float64(time.Minute))
}

// ───────────────────────────── /proc model ─────────────────────────────

type rproc struct {
	PID, PPID, UID, TTY int
	Comm                string
	Exe                 string // readlink /proc/<pid>/exe ("" if unreadable)
	Args                []string
	Cgroup              string
	Unit, Slice         string // under user@UID.service: slice + unit (\x2d unescaped)
	Start               uint64 // starttime, clock ticks since boot
	CPU                 uint64 // utime+stime ticks
	IORead, IOWrite     uint64 // bytes
	IOValid             bool   // io was read this scan (fast ticks skip it)
	Wine                bool
	Prefix              string
	FDs                 []string // readlink of every fd (full collects only)
	cl                  string   // cached joined command line
}

func (p *rproc) arg0() string {
	if len(p.Args) > 0 {
		return p.Args[0]
	}
	return p.Comm
}

// exeBase is the lowercase basename of argv0, splitting on / and \ (Wine argv0 is a
// Windows path like C:\windows\system32\services.exe).
func (p *rproc) exeBase() string {
	a := p.arg0()
	if i := strings.LastIndexAny(a, `/\`); i >= 0 {
		a = a[i+1:]
	}
	return strings.ToLower(a)
}

func (p *rproc) hasArgPrefix(pre string) bool {
	for _, a := range p.Args[min(1, len(p.Args)):] {
		if strings.HasPrefix(a, pre) {
			return true
		}
	}
	return false
}

func (p *rproc) argValue(key string) string {
	for i, a := range p.Args {
		if strings.HasPrefix(a, key+"=") {
			return a[len(key)+1:]
		}
		if a == key && i+1 < len(p.Args) {
			return p.Args[i+1]
		}
	}
	return ""
}

func (p *rproc) cmdline() string {
	if p.cl == "" && len(p.Args) > 0 {
		p.cl = strings.Join(p.Args, " ")
	}
	return p.cl
}

// unescapeUnit turns systemd's \x2d escapes back into characters.
func unescapeUnit(s string) string {
	if !strings.Contains(s, `\x`) {
		return s
	}
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == '\\' && i+3 < len(s) && s[i+1] == 'x' {
			if v, err := strconv.ParseUint(s[i+2:i+4], 16, 8); err == nil {
				b.WriteByte(byte(v))
				i += 3
				continue
			}
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

// parseCgroup returns (slice, unit) for a cgroup-v2 line "0::/user.slice/…".
// Under user@UID.service the first component is the slice and the first .scope/.service
// after it is the unit. Outside the user manager (a login session scope) the unit is the
// last component and the slice is "".
func parseCgroup(content string, uid int) (path, slice, unit string) {
	for _, line := range strings.Split(strings.TrimSpace(content), "\n") {
		if strings.HasPrefix(line, "0::") {
			path = strings.TrimPrefix(line, "0::")
			break
		}
	}
	if path == "" {
		return
	}
	marker := fmt.Sprintf("/user@%d.service/", uid)
	if i := strings.Index(path, marker); i >= 0 {
		parts := strings.Split(path[i+len(marker):], "/")
		for j, c := range parts {
			if j == 0 && strings.HasSuffix(c, ".slice") {
				slice = c
				continue
			}
			if strings.HasSuffix(c, ".scope") || strings.HasSuffix(c, ".service") {
				unit = unescapeUnit(c)
				return
			}
		}
		return
	}
	parts := strings.Split(path, "/")
	unit = unescapeUnit(parts[len(parts)-1])
	return
}

func isWineProc(comm, exe string, args []string) bool {
	if comm == "wineserver" {
		return true
	}
	if strings.Contains(filepath.Base(exe), "wine") || strings.Contains(exe, "/wine/") {
		return true
	}
	if len(args) > 0 {
		a := args[0]
		if len(a) > 2 && a[1] == ':' && (a[2] == '\\' || a[2] == '/') {
			return true
		}
		if strings.HasSuffix(strings.ToLower(a), ".exe") {
			return true
		}
	}
	return false
}

func readEnvKey(root string, pid int, key string) (string, bool) {
	b, err := os.ReadFile(fmt.Sprintf("%s/%d/environ", root, pid))
	if err != nil {
		return "", false
	}
	for _, kv := range strings.Split(string(b), "\x00") {
		if strings.HasPrefix(kv, key+"=") {
			return kv[len(key)+1:], true
		}
	}
	return "", false
}

// procStatic is what does not change while a pid lives (keyed by pid + start time), so the
// 2-second scan re-reads only stat and io. Measured 2026-10-24: re-reading cmdline, status,
// cgroup, exe and environ for every process every tick cost the agent 2.4 % of a core.
type procStatic struct {
	start             uint64
	skip              bool // not ours, or a kernel thread
	uid               int
	args              []string
	cl                string
	cgroup, slice     string
	unit, exe, prefix string
	wine              bool
}

type staticCache struct {
	m             map[int]*procStatic
	refreshCgroup bool // full tick: re-read cgroups + io, re-validate other users' pids
}

func newStaticCache() *staticCache { return &staticCache{m: map[int]*procStatic{}} }

// readProc reads one /proc/<pid> entry. Returns nil if the process vanished or is not ours.
func readProc(root string, pid, uid int, home string, pc *staticCache) *rproc {
	// Fast tick: a pid already known to be another user's (or a kernel thread) is not even
	// stat'ed. Full ticks re-validate them, so a reused pid is noticed within FullEvery.
	if pc != nil && !pc.refreshCgroup {
		if c, ok := pc.m[pid]; ok && c.skip {
			return nil
		}
	}
	dir := fmt.Sprintf("%s/%d", root, pid)
	st, err := os.ReadFile(dir + "/stat")
	if err != nil {
		return nil
	}
	s := string(st)
	lp, rp := strings.IndexByte(s, '('), strings.LastIndexByte(s, ')')
	if lp < 0 || rp < lp {
		return nil
	}
	p := &rproc{PID: pid, Comm: s[lp+1 : rp]}
	f := strings.Fields(s[rp+1:])
	if len(f) < 20 {
		return nil
	}
	p.PPID, _ = strconv.Atoi(f[1])
	p.TTY, _ = strconv.Atoi(f[4])
	ut, _ := strconv.ParseUint(f[11], 10, 64)
	stt, _ := strconv.ParseUint(f[12], 10, 64)
	p.CPU = ut + stt
	p.Start, _ = strconv.ParseUint(f[19], 10, 64)

	var ps *procStatic
	if pc != nil {
		if c, ok := pc.m[pid]; ok && c.start == p.Start {
			ps = c
		}
	}
	if ps == nil {
		ps = &procStatic{start: p.Start, uid: -1}
		if b, err := os.ReadFile(dir + "/status"); err == nil {
			for _, line := range strings.Split(string(b), "\n") {
				if strings.HasPrefix(line, "Uid:") {
					if ff := strings.Fields(line); len(ff) > 1 {
						ps.uid, _ = strconv.Atoi(ff[1])
					}
					break
				}
			}
		}
		switch {
		case uid >= 0 && ps.uid != uid:
			ps.skip = true
		default:
			if b, err := os.ReadFile(dir + "/cmdline"); err == nil && len(b) > 0 {
				ps.args = strings.Split(strings.TrimRight(string(b), "\x00"), "\x00")
				ps.cl = strings.Join(ps.args, " ")
			} else {
				ps.skip = true // kernel thread or zombie — nothing to free
			}
		}
		if !ps.skip {
			if b, err := os.ReadFile(dir + "/cgroup"); err == nil {
				ps.cgroup, ps.slice, ps.unit = parseCgroup(string(b), ps.uid)
			}
			ps.exe, _ = os.Readlink(dir + "/exe")
			if isWineProc(p.Comm, ps.exe, ps.args) {
				ps.wine = true
				if v, ok := readEnvKey(root, pid, "WINEPREFIX"); ok && v != "" {
					ps.prefix = filepath.Clean(v)
				} else {
					ps.prefix = filepath.Join(home, ".wine")
				}
			}
		}
		if pc != nil {
			pc.m[pid] = ps
		}
	} else if pc.refreshCgroup && !ps.skip {
		if b, err := os.ReadFile(dir + "/cgroup"); err == nil {
			ps.cgroup, ps.slice, ps.unit = parseCgroup(string(b), ps.uid)
		}
	}
	if ps.skip {
		return nil
	}
	p.UID, p.Args, p.Cgroup, p.Slice, p.Unit, p.Exe, p.cl = ps.uid, ps.args, ps.cgroup, ps.slice, ps.unit, ps.exe, ps.cl
	p.Wine, p.Prefix = ps.wine, ps.prefix
	if pc != nil && !pc.refreshCgroup {
		return p // fast tick: CPU from stat is enough; I/O rates come from full ticks
	}
	if b, err := os.ReadFile(dir + "/io"); err == nil {
		p.IOValid = true
		for _, line := range strings.Split(string(b), "\n") {
			if v, ok := strings.CutPrefix(line, "read_bytes: "); ok {
				p.IORead, _ = strconv.ParseUint(strings.TrimSpace(v), 10, 64)
			} else if v, ok := strings.CutPrefix(line, "write_bytes: "); ok {
				p.IOWrite, _ = strconv.ParseUint(strings.TrimSpace(v), 10, 64)
			}
		}
	}
	return p
}

// fillFDs reads the fd links of the given processes only (GPU and open-file checks).
func fillFDs(root string, procs map[int]*rproc, pids []int) {
	for _, pid := range pids {
		p := procs[pid]
		if p == nil {
			continue
		}
		p.FDs = p.FDs[:0]
		dir := fmt.Sprintf("%s/%d/fd", root, pid)
		ents, _ := os.ReadDir(dir)
		for _, e := range ents {
			if l, err := os.Readlink(dir + "/" + e.Name()); err == nil {
				p.FDs = append(p.FDs, l)
			}
		}
	}
}

// readProcsC scans /proc using (and pruning) the static cache.
func readProcsC(root string, uid int, home string, pc *staticCache) map[int]*rproc {
	out := make(map[int]*rproc)
	ents, err := os.ReadDir(root)
	if err != nil {
		return out
	}
	seen := map[int]bool{}
	for _, e := range ents {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		seen[pid] = true
		if p := readProc(root, pid, uid, home, pc); p != nil {
			out[pid] = p
		}
	}
	if pc != nil {
		for pid := range pc.m {
			if !seen[pid] {
				delete(pc.m, pid)
			}
		}
	}
	return out
}

// readProcs is the uncached scan (tests, one-shot checks). withFDs reads every fd link.
func readProcs(root string, uid int, withFDs bool, home string) map[int]*rproc {
	out := readProcsC(root, uid, home, nil)
	if withFDs {
		pids := make([]int, 0, len(out))
		for pid := range out {
			pids = append(pids, pid)
		}
		fillFDs(root, out, pids)
	}
	return out
}

func readUptime(root string) float64 {
	b, err := os.ReadFile(root + "/uptime")
	if err != nil {
		return 0
	}
	f := strings.Fields(string(b))
	if len(f) == 0 {
		return 0
	}
	v, _ := strconv.ParseFloat(f[0], 64)
	return v
}

func readMemAvailableGB(root string) float64 {
	b, err := os.ReadFile(root + "/meminfo")
	if err != nil {
		return -1
	}
	for _, line := range strings.Split(string(b), "\n") {
		if strings.HasPrefix(line, "MemAvailable:") {
			return parseKb(line) / 1024 / 1024
		}
	}
	return -1
}

// procMemMB returns PSS and SwapPss (MB) from smaps_rollup — the honest per-process numbers
// (RSS double-counts shared pages; luminos-mem-report explains why).
func procMemMB(root string, pid int) (pss, swap float64) {
	b, err := os.ReadFile(fmt.Sprintf("%s/%d/smaps_rollup", root, pid))
	if err != nil {
		return 0, 0
	}
	var swapPlain float64
	sawSwapPss := false
	for _, line := range strings.Split(string(b), "\n") {
		switch {
		case strings.HasPrefix(line, "Pss:"):
			pss = parseKb(line) / 1024
		case strings.HasPrefix(line, "SwapPss:"):
			swap, sawSwapPss = parseKb(line)/1024, true
		case strings.HasPrefix(line, "Swap:"):
			swapPlain = parseKb(line) / 1024
		}
	}
	if !sawSwapPss {
		swap = swapPlain
	}
	return
}

// ───────────────────────────── grouping ─────────────────────────────

type rgroup struct {
	Key, Kind, Name string // Kind: "unit" | "wine"
	Unit, Slice     string
	Prefix          string
	Procs           []*rproc
}

func (g *rgroup) pids() []int {
	out := make([]int, 0, len(g.Procs))
	for _, p := range g.Procs {
		out = append(out, p.PID)
	}
	sort.Ints(out)
	return out
}

// buildGroups groups processes by APP. Wine processes are regrouped by WINEPREFIX across
// units (one prefix = one wineserver = one app world); everything else by systemd unit.
func buildGroups(procs map[int]*rproc) map[string]*rgroup {
	out := make(map[string]*rgroup)
	pids := make([]int, 0, len(procs))
	for pid := range procs {
		pids = append(pids, pid)
	}
	sort.Ints(pids)
	for _, pid := range pids {
		p := procs[pid]
		var key string
		var g *rgroup
		switch {
		case p.Wine:
			key = "wine:" + p.Prefix
			if g = out[key]; g == nil {
				g = &rgroup{Key: key, Kind: "wine", Name: "wine " + p.Prefix, Prefix: p.Prefix, Unit: p.Unit, Slice: p.Slice}
			}
		case p.Unit != "":
			key = "unit:" + p.Unit
			if g = out[key]; g == nil {
				g = &rgroup{Key: key, Kind: "unit", Name: p.Unit, Unit: p.Unit, Slice: p.Slice}
			}
		default:
			continue
		}
		g.Procs = append(g.Procs, p)
		out[key] = g
	}
	return out
}

// topLevel returns the processes whose parent is outside the group, oldest first.
func topLevel(g *rgroup) []*rproc {
	in := make(map[int]bool, len(g.Procs))
	for _, p := range g.Procs {
		in[p.PID] = true
	}
	var out []*rproc
	for _, p := range g.Procs {
		if !in[p.PPID] {
			out = append(out, p)
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Start != out[j].Start {
			return out[i].Start < out[j].Start
		}
		return out[i].PID < out[j].PID
	})
	return out
}

// ───────────────────────────── protection ─────────────────────────────

// Hard protection: never reaped by ANY rule. Matched against the unescaped unit name.
// Session infrastructure that lives in app.slice because it is D-Bus or socket activated.
var protectedUnitSubstr = []string{
	"luminos-", "hive", "claude-cowork", "dbus", "dconf", "gnome-keyring", "xdg-", "at-spi",
	"gvfs", "plasma-", "org.kde.plasma", "pipewire", "wireplumber", "xvfb", "ssh-agent",
	"gpg-agent", "kwallet", "ksecretd", "obex", "polkit", "ydotool", "earlyoom",
}

// Process names that are always protected (the daemon's isProtectedAlways list, plus the
// system services the reaper prompt names). Matched as substrings of comm, like main.go.
var protectedCommSubstr = []string{
	"sshd", "tailscaled", "NetworkManager", "sddm", "earlyoom", "Xvfb", "qemu-system",
	"llama-server", "hive-daemon", "kwalletd", "ksecretd",
}

var terminalComms = []string{"konsole", "kitty", "alacritty", "foot", "wezterm", "xterm", "gnome-terminal", "tmux", "yakuake", "terminator", "ptyxis"}

type protCtx struct {
	OffloadPID       int
	SteamGameRunning bool
}

func matchAnyLower(s string, pats []string) string {
	ls := strings.ToLower(s)
	for _, p := range pats {
		if p != "" && strings.Contains(ls, strings.ToLower(p)) {
			return p
		}
	}
	return ""
}

// claudeMaxMain reports whether p is the main process of the Claude Max app (default
// profile). It hosts the Cowork VM and the remote/bridge sessions even with no window.
func claudeMaxMain(p *rproc, maxDir string) bool {
	if !strings.Contains(filepath.Base(p.Exe)+" "+p.Comm, "claude-desktop") {
		return false
	}
	if p.hasArgPrefix("--type=") {
		return false
	}
	udd := p.argValue("--user-data-dir")
	return udd == "" || filepath.Clean(udd) == filepath.Clean(maxDir)
}

// hardProtected: never touched by any rule (keep-list, session infrastructure, Max app,
// offload process, the named system services, qemu Cowork VM).
func hardProtected(g *rgroup, c ReapConfig, pc protCtx) string {
	for _, p := range g.Procs {
		for _, field := range []string{p.Comm, p.exeBase(), g.Unit, g.Prefix} {
			if k := matchAnyLower(field, c.Keep); k != "" {
				return "keep-list: " + k
			}
		}
	}
	if g.Kind == "unit" {
		if s := matchAnyLower(g.Unit, protectedUnitSubstr); s != "" {
			return "session/luminos unit (" + s + ")"
		}
	}
	for _, p := range g.Procs {
		if pc.OffloadPID != 0 && p.PID == pc.OffloadPID {
			return "offload inference process"
		}
		if isProtectedAlways(p.PID, p.Comm) {
			return "protected process " + p.Comm
		}
		if s := matchAnyLower(p.Comm, protectedCommSubstr); s != "" {
			return "protected process " + p.Comm
		}
		if claudeMaxMain(p, c.MaxProfileDir) {
			return "Claude Max app (hosts the Cowork VM + bridge sessions)"
		}
	}
	return ""
}

// softProtected: guards the idle rule and the app-died rule, but not the pure leftover rules
// (a wine process with no wineserver is dead weight even if it was started from a terminal).
func softProtected(g *rgroup, pc protCtx) string {
	for _, p := range g.Procs {
		if s := matchAnyLower(p.Comm, terminalComms); s != "" {
			return "terminal (" + p.Comm + ")"
		}
		if p.TTY != 0 {
			return "attached to a terminal (" + p.Comm + ")"
		}
		if pc.SteamGameRunning && (p.Comm == "steam" || strings.HasPrefix(p.Comm, "steamwebhelper")) {
			return "Steam while a game runs"
		}
	}
	return ""
}

func steamGameRunning(procs map[int]*rproc) bool {
	for _, p := range procs {
		cl := p.cmdline()
		if strings.Contains(cl, "SteamLaunch") || strings.Contains(cl, "/steamapps/common/") {
			return true
		}
	}
	return false
}

// eligibleForIdle: only app units (app.slice) and Wine worlds are ever idle-reaped. Units
// in session.slice / background.slice are the desktop itself.
func eligibleForIdle(g *rgroup) bool {
	return g.Kind == "wine" || g.Slice == "app.slice"
}

// ───────────────────────────── liveness ─────────────────────────────

// LiveInputs is everything measured outside /proc stat/io for one full collect.
type LiveInputs struct {
	WindowsOK     bool
	WindowPIDs    map[int]bool
	WindowClasses map[string]bool // lowercase resource classes (Wine sets them to the .exe name)
	FocusPID      int
	AudioPIDs     map[int]bool
	GPUBusyPIDs   map[int]bool
	NetBps        map[int]float64 // established TCP bytes/s per pid
	ListenClient  map[int]bool    // pid owns a listen socket with an accepted connection right now
	ProcOK        bool
}

type groupRates struct{ CPUPct, ReadBps, WriteBps float64 }

// liveReason returns why a group is live ("" = idle). Every signal is a measurement.
func liveReason(g *rgroup, in LiveInputs, r groupRates, lastFocus, lastListen time.Time, now time.Time, c ReapConfig) string {
	var net float64
	for _, p := range g.Procs {
		if in.WindowPIDs[p.PID] {
			return "has a window"
		}
		if g.Kind == "wine" && p.Comm != "wineserver" {
			b := strings.TrimSuffix(p.exeBase(), ".exe")
			if in.WindowClasses[p.exeBase()] || (b != "" && in.WindowClasses[b]) {
				return "has a window (" + p.exeBase() + ")"
			}
		}
		if in.AudioPIDs[p.PID] {
			return "playing/recording audio"
		}
		if in.GPUBusyPIDs[p.PID] {
			return "GPU client in use (" + p.Comm + ")"
		}
		net += in.NetBps[p.PID]
	}
	if !lastFocus.IsZero() && now.Sub(lastFocus) < time.Duration(c.FocusRecentMin*float64(time.Minute)) {
		return fmt.Sprintf("focused %.0f s ago", now.Sub(lastFocus).Seconds())
	}
	if net >= c.NetKBps*1024 {
		return fmt.Sprintf("network traffic %.1f KB/s", net/1024)
	}
	if !lastListen.IsZero() && now.Sub(lastListen) < time.Duration(c.ListenClientMin*float64(time.Minute)) {
		return fmt.Sprintf("listen socket had a client %.0f s ago", now.Sub(lastListen).Seconds())
	}
	if r.CPUPct >= c.CPUPct {
		return fmt.Sprintf("CPU %.1f %%", r.CPUPct)
	}
	if r.WriteBps >= c.DownloadKBps*1024 {
		return fmt.Sprintf("writing %.0f KB/s (download?)", r.WriteBps/1024)
	}
	if r.ReadBps+r.WriteBps >= c.IOMBps*1024*1024 {
		return fmt.Sprintf("disk I/O %.1f MB/s", (r.ReadBps+r.WriteBps)/1024/1024)
	}
	return ""
}

// ───────────────────────────── wine / browser / MCP shapes ─────────────────────────────

// Wine's own plumbing. A prefix with only these left has no app in it any more.
var wineServiceExes = map[string]bool{
	"services.exe": true, "plugplay.exe": true, "svchost.exe": true, "rpcss.exe": true,
	"winedevice.exe": true, "conhost.exe": true, "wineboot.exe": true, "winemenubuilder.exe": true,
	"start.exe": true, "tabtip.exe": true, "mscorsvw.exe": true, "wineserver": true,
}

func wineIsService(p *rproc) bool {
	b := p.exeBase()
	if p.Comm == "wineserver" || wineServiceExes[b] {
		return true
	}
	if b == "explorer.exe" {
		for _, a := range p.Args[1:] {
			if strings.HasPrefix(strings.ToLower(a), "/desktop") {
				return true
			}
		}
	}
	return false
}

func wineServers(g *rgroup) []*rproc {
	var out []*rproc
	for _, p := range g.Procs {
		if p.Comm == "wineserver" {
			out = append(out, p)
		}
	}
	return out
}

func wineRealExes(g *rgroup) []*rproc {
	var out []*rproc
	for _, p := range g.Procs {
		if !wineIsService(p) {
			out = append(out, p)
		}
	}
	return out
}

func isChromiumHelper(p *rproc) bool {
	return p.hasArgPrefix("--type=") || strings.Contains(p.Comm, "crashpad") || strings.Contains(filepath.Base(p.Exe), "crashpad")
}

// browserLeftovers returns Chromium/Electron helpers (renderers, zygotes, GPU process,
// crashpad) whose main browser process — same install dir, no --type= — is gone.
func browserLeftovers(g *rgroup) []*rproc {
	mainsByDir := map[string]bool{}
	helpersByDir := map[string][]*rproc{}
	for _, p := range g.Procs {
		if p.Exe == "" {
			continue
		}
		dir := filepath.Dir(p.Exe)
		if isChromiumHelper(p) {
			helpersByDir[dir] = append(helpersByDir[dir], p)
		} else {
			mainsByDir[dir] = true
		}
	}
	var out []*rproc
	for dir, hs := range helpersByDir {
		if mainsByDir[dir] {
			continue
		}
		// Only Chromium-shaped trees: at least one helper must carry --type= or be crashpad.
		out = append(out, hs...)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].PID < out[j].PID })
	return out
}

// MCP servers are stdio children of a client (Claude Desktop, Claude Code, Antigravity…).
var mcpServerMarks = []string{"mempalace.mcp_server", "code-review-graph serve", "claude-host-shell/server.py", "luminos-coder-review-mcp", "mcp_server", "mcp-server"}

// Launch wrappers that sit between a client and its MCP server and are not clients.
var mcpWrapperComms = map[string]bool{"disclaimer": true, "sh": true, "bash": true, "dash": true, "env": true, "timeout": true, "setsid": true, "nohup": true, "uv": true, "uvx": true}

func isMCPServer(p *rproc) bool {
	if mcpWrapperComms[p.Comm] {
		return false // a wrapper's argv names the server; the server itself is the one to judge
	}
	cl := p.cmdline()
	if strings.Contains(cl, "luminos-mcp-share") {
		return false // DECISION 159 brokers manage their own idle
	}
	for _, m := range mcpServerMarks {
		if strings.Contains(cl, m) {
			return true
		}
	}
	return false
}

// mcpClientGone walks up the parent chain. The server is orphaned if no ancestor (below
// init / the user manager) is anything other than a launch wrapper — i.e. its client died.
func mcpClientGone(p *rproc, procs map[int]*rproc) bool {
	seen := map[int]bool{}
	cur := p.PPID
	for cur > 1 && !seen[cur] {
		seen[cur] = true
		a, ok := procs[cur]
		if !ok {
			return false // parent belongs to another user/root: not ours to judge
		}
		if strings.Contains(a.cmdline(), "luminos-mcp-share") {
			return false
		}
		if a.Comm == "systemd" || strings.HasPrefix(a.Comm, "systemd") {
			return true // reached the user manager (a subreaper) without meeting a client
		}
		if !mcpWrapperComms[a.Comm] {
			return false // a real client process is alive above us
		}
		cur = a.PPID
	}
	return true
}

// ───────────────────────────── decisions ─────────────────────────────

// Candidate is one thing the reaper would reap (log) or reaps (act).
type Candidate struct {
	Key     string  `json:"key"`
	Name    string  `json:"app"`
	Rule    string  `json:"rule"` // idle | app-died | wine-no-server | wine-no-app | browser-helpers | mcp-orphan
	Reason  string  `json:"reason"`
	IdleMin float64 `json:"idle_min,omitempty"`
	PIDs    []int   `json:"pids"`
	PSSMB   float64 `json:"pss_mb"`
	SwapMB  float64 `json:"swap_mb"`
	Action  string  `json:"action"` // stop-unit | wineserver-k | signal
	Unit    string  `json:"unit,omitempty"`
	Prefix  string  `json:"prefix,omitempty"`
	Server  string  `json:"wineserver,omitempty"` // path of the running wineserver binary
	Test    bool    `json:"test,omitempty"`
	Starts  map[int]uint64 `json:"-"`
}

type gstate struct {
	FirstSeen, LastActive time.Time
	LastReason            string
	LastFocus, LastListen time.Time
	MainPID               int
	MainStart             uint64
	MainName              string
	MainDiedAt            time.Time
	LeftoverSince         map[string]time.Time
	ring                  []rateSample
	LoggedState           string
	LoggedAt              time.Time
}

type rateSample struct {
	At                  time.Time
	DT                  float64
	CPUTicks, Rd, Wr    float64
}

func (st *gstate) rates(now time.Time, windowSec float64) groupRates {
	var dt, cpu, rd, wr float64
	for _, s := range st.ring {
		if now.Sub(s.At).Seconds() <= windowSec {
			dt += s.DT
			cpu += s.CPUTicks
			rd += s.Rd
			wr += s.Wr
		}
	}
	if dt <= 0 {
		return groupRates{}
	}
	return groupRates{CPUPct: cpu / clkTck / dt * 100, ReadBps: rd / dt, WriteBps: wr / dt}
}

func matchesActOnly(g *rgroup, c ReapConfig) bool {
	if len(c.ActOnly) == 0 {
		return false
	}
	if matchAnyLower(g.Unit, c.ActOnly) != "" || matchAnyLower(g.Prefix, c.ActOnly) != "" || matchAnyLower(g.Key, c.ActOnly) != "" {
		return true
	}
	for _, p := range g.Procs {
		if matchAnyLower(p.cmdline(), c.ActOnly) != "" {
			return true
		}
	}
	return false
}

func since(m map[string]time.Time, k string, now time.Time) time.Duration {
	t, ok := m[k]
	if !ok {
		m[k] = now
		return 0
	}
	return now.Sub(t)
}

// GroupView is how every group was classified on the last pass (for /reap and for tests).
type GroupView struct {
	Key     string  `json:"key"`
	State   string  `json:"state"` // live | idle | protected | ineligible | candidate
	Reason  string  `json:"reason"`
	IdleMin float64 `json:"idle_min"`
	PIDs    int     `json:"procs"`
}

// Evaluator holds the reaper's memory between passes. All decision logic is in Pass.
type Evaluator struct {
	C       ReapConfig
	States  map[string]*gstate
	prev    map[int]procSample
	prevAt  time.Time
	Uptime  func() float64
	mu      sync.Mutex
}

type procSample struct {
	Start       uint64
	CPU, Rd, Wr uint64
	IOValid     bool
}

func NewEvaluator(c ReapConfig) *Evaluator {
	return &Evaluator{C: c, States: map[string]*gstate{}, prev: map[int]procSample{}}
}

// Observe folds a fresh proc scan into per-group rate history and main-process tracking.
// Called every tick (fast), independent of the full collect.
func (e *Evaluator) Observe(groups map[string]*rgroup, procs map[int]*rproc, now time.Time) {
	dt := 0.0
	if !e.prevAt.IsZero() {
		dt = now.Sub(e.prevAt).Seconds()
	}
	for key, g := range groups {
		st := e.States[key]
		if st == nil {
			st = &gstate{FirstSeen: now, LastActive: now, LeftoverSince: map[string]time.Time{}}
			e.States[key] = st
		}
		if dt > 0 {
			var cpu, rd, wr float64
			for _, p := range g.Procs {
				if prev, ok := e.prev[p.PID]; ok && prev.Start == p.Start {
					if p.CPU >= prev.CPU {
						cpu += float64(p.CPU - prev.CPU)
					}
					if p.IOValid && prev.IOValid {
						if p.IORead >= prev.Rd {
							rd += float64(p.IORead - prev.Rd)
						}
						if p.IOWrite >= prev.Wr {
							wr += float64(p.IOWrite - prev.Wr)
						}
					}
				}
			}
			st.ring = append(st.ring, rateSample{At: now, DT: dt, CPUTicks: cpu, Rd: rd, Wr: wr})
			cut := 0
			for cut < len(st.ring) && now.Sub(st.ring[cut].At).Seconds() > e.C.WindowSec+e.C.FullEvery.Seconds() {
				cut++
			}
			st.ring = st.ring[cut:]
		}
		// Main-process tracking for the app-died rule (scopes only).
		if st.MainPID != 0 {
			if p, ok := procs[st.MainPID]; !ok || p.Start != st.MainStart {
				if st.MainDiedAt.IsZero() {
					st.MainDiedAt = now
				}
			}
		}
		if st.MainPID == 0 {
			if tl := topLevel(g); len(tl) > 0 {
				st.MainPID, st.MainStart, st.MainName = tl[0].PID, tl[0].Start, tl[0].Comm
			}
		}
	}
	for key := range e.States {
		if _, ok := groups[key]; !ok && !strings.HasPrefix(key, "mcp:") {
			delete(e.States, key)
		}
	}
	next := make(map[int]procSample, len(procs))
	for pid, p := range procs {
		ns := procSample{Start: p.Start, CPU: p.CPU, Rd: p.IORead, Wr: p.IOWrite, IOValid: p.IOValid}
		if old, ok := e.prev[pid]; !p.IOValid && ok && old.Start == p.Start {
			ns.Rd, ns.Wr, ns.IOValid = old.Rd, old.Wr, old.IOValid // carry I/O across fast ticks
		}
		next[pid] = ns
	}
	e.prev = next
	e.prevAt = now
}

// PassResult is one evaluation.
type PassResult struct {
	At           time.Time   `json:"at"`
	Mode         string      `json:"mode"`
	AvailGB      float64     `json:"avail_gb"`
	IdleAllowed  float64     `json:"idle_allowed_min"`
	WindowsOK    bool        `json:"windows_known"`
	Candidates   []Candidate `json:"candidates"`
	Groups       []GroupView `json:"groups"`
	PendingLeft  bool        `json:"-"`
}

// Pass decides. haveFull says `in` is fresh enough to judge liveness (otherwise rules that
// need it wait). force=true ignores idle time and liveness (protected-class test only).
func (e *Evaluator) Pass(groups map[string]*rgroup, procs map[int]*rproc, in LiveInputs, haveFull bool, availGB float64, pc protCtx, now time.Time, force bool) PassResult {
	c := e.C
	allowed := idleAllowed(availGB, c)
	res := PassResult{At: now, Mode: c.Mode, AvailGB: availGB, IdleAllowed: allowed.Minutes(), WindowsOK: in.WindowsOK}
	uptime := 0.0
	if e.Uptime != nil {
		uptime = e.Uptime()
	}
	taken := map[int]bool{}

	keys := make([]string, 0, len(groups))
	for k := range groups {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	for _, key := range keys {
		g := groups[key]
		st := e.States[key]
		if st == nil {
			st = &gstate{FirstSeen: now, LastActive: now, LeftoverSince: map[string]time.Time{}}
			e.States[key] = st
		}
		r := st.rates(now, c.WindowSec)
		test := matchesActOnly(g, c)
		view := GroupView{Key: key, PIDs: len(g.Procs)}

		// Update focus / listen memory and LastActive from fresh measurements.
		for _, p := range g.Procs {
			if in.FocusPID != 0 && p.PID == in.FocusPID {
				st.LastFocus = now
			}
			if in.ListenClient[p.PID] {
				st.LastListen = now
			}
		}
		live := ""
		if haveFull {
			live = liveReason(g, in, r, st.LastFocus, st.LastListen, now, c)
			if live != "" {
				st.LastActive, st.LastReason = now, live
			}
		}
		idle := now.Sub(st.LastActive)
		view.IdleMin = idle.Minutes()

		hard := hardProtected(g, c, pc)
		soft := softProtected(g, pc)
		emit := func(rule, reason, action string, procsToReap []*rproc) {
			cand := Candidate{Key: key, Name: g.Name, Rule: rule, Reason: reason, Action: action, Unit: g.Unit, Prefix: g.Prefix, Test: test, IdleMin: idle.Minutes(), Starts: map[int]uint64{}}
			for _, p := range procsToReap {
				if taken[p.PID] {
					continue
				}
				taken[p.PID] = true
				cand.PIDs = append(cand.PIDs, p.PID)
				cand.Starts[p.PID] = p.Start
			}
			if len(cand.PIDs) == 0 {
				return
			}
			if action == "wineserver-k" {
				if s := wineServers(g); len(s) > 0 {
					cand.Server = s[0].Exe
				}
			}
			res.Candidates = append(res.Candidates, cand)
			view.State, view.Reason = "candidate", rule+": "+reason
		}

		switch {
		case hard != "":
			view.State, view.Reason = "protected", hard
		case g.Kind == "wine":
			servers, real := wineServers(g), wineRealExes(g)
			switch {
			case len(servers) == 0:
				d := since(st.LeftoverSince, "wine-no-server", now)
				if force || d >= c.LeftoverGrace {
					emit("wine-no-server", fmt.Sprintf("wineserver for %s is gone; %d wine process(es) orphaned", g.Prefix, len(g.Procs)), "signal", g.Procs)
				} else {
					res.PendingLeft = true
				}
			case len(real) == 0 && (force || uptime-float64(servers[0].Start)/clkTck > 60):
				d := since(st.LeftoverSince, "wine-no-app", now)
				if force || d >= c.LeftoverGrace {
					emit("wine-no-app", fmt.Sprintf("no program left in %s, only Wine services (%s)", g.Prefix, commList(g.Procs)), "wineserver-k", g.Procs)
				} else {
					res.PendingLeft = true
				}
			default:
				delete(st.LeftoverSince, "wine-no-server")
				delete(st.LeftoverSince, "wine-no-app")
				e.idleRule(g, st, &view, live, soft, haveFull, in, r, allowed, test, force, now, emit)
			}
		default:
			// app-died: a scope whose main process we SAW exit; whatever is left and not live goes.
			if strings.HasSuffix(g.Unit, ".scope") && !st.MainDiedAt.IsZero() && soft == "" {
				if force || now.Sub(st.MainDiedAt) >= c.LeftoverGrace {
					if !haveFull || !in.WindowsOK {
						res.PendingLeft = true
					} else {
						if live == "" || force {
							emit("app-died", fmt.Sprintf("main process %s (pid %d) exited %.0f s ago; %d left, none live", st.MainName, st.MainPID, now.Sub(st.MainDiedAt).Seconds(), len(g.Procs)), "stop-unit", g.Procs)
						}
						st.MainPID, st.MainDiedAt = 0, time.Time{} // re-elect next Observe
						if tl := topLevel(g); len(tl) > 0 {
							st.MainPID, st.MainStart, st.MainName = tl[0].PID, tl[0].Start, tl[0].Comm
						}
					}
				} else {
					res.PendingLeft = true
				}
			}
			if view.State == "" {
				if hs := browserLeftovers(g); len(hs) > 0 && soft == "" {
					d := since(st.LeftoverSince, "browser", now)
					if force || d >= c.LeftoverGrace {
						if haveFull && in.WindowsOK && (live == "" || force) {
							emit("browser-helpers", fmt.Sprintf("browser helpers (%s) outlived their main process", commList(hs)), "signal", hs)
						} else if !haveFull {
							res.PendingLeft = true
						}
					} else {
						res.PendingLeft = true
					}
				} else {
					delete(st.LeftoverSince, "browser")
				}
			}
			if view.State == "" {
				e.idleRule(g, st, &view, live, soft, haveFull, in, r, allowed, test, force, now, emit)
			}
		}
		res.Groups = append(res.Groups, view)
	}

	// MCP servers whose client is gone, wherever they live (except hard-protected groups).
	hardKeys := map[string]bool{}
	for _, gv := range res.Groups {
		if gv.State == "protected" {
			hardKeys[gv.Key] = true
		}
	}
	pidKey := map[int]string{}
	for k, g := range groups {
		for _, p := range g.Procs {
			pidKey[p.PID] = k
		}
	}
	seenMCP := map[string]bool{}
	pids := make([]int, 0, len(procs))
	for pid := range procs {
		pids = append(pids, pid)
	}
	sort.Ints(pids)
	for _, pid := range pids {
		p := procs[pid]
		if taken[pid] || !isMCPServer(p) || hardKeys[pidKey[pid]] {
			continue
		}
		key := fmt.Sprintf("mcp:%d:%d", pid, p.Start)
		seenMCP[key] = true
		if !mcpClientGone(p, procs) {
			delete(e.States, key)
			continue
		}
		st := e.States[key]
		if st == nil {
			st = &gstate{FirstSeen: now, LastActive: now, LeftoverSince: map[string]time.Time{}}
			e.States[key] = st
		}
		if !force && now.Sub(st.FirstSeen) < c.LeftoverGrace {
			res.PendingLeft = true
			continue
		}
		// Take the server and its wrapper chain up to the subreaper.
		victims := []*rproc{p}
		for cur := p.PPID; cur > 1; {
			a, ok := procs[cur]
			if !ok || !mcpWrapperComms[a.Comm] {
				break
			}
			victims = append(victims, a)
			cur = a.PPID
		}
		cand := Candidate{Key: key, Name: "MCP server " + mcpName(p), Rule: "mcp-orphan", Reason: "its Claude/agent client is gone (parent chain reaches the user manager)", Action: "signal", Starts: map[int]uint64{}}
		cand.Test = matchAnyLower(p.cmdline(), c.ActOnly) != ""
		for _, v := range victims {
			if !taken[v.PID] {
				taken[v.PID] = true
				cand.PIDs = append(cand.PIDs, v.PID)
				cand.Starts[v.PID] = v.Start
			}
		}
		res.Candidates = append(res.Candidates, cand)
	}
	for k := range e.States {
		if strings.HasPrefix(k, "mcp:") && !seenMCP[k] {
			delete(e.States, k)
		}
	}
	return res
}

func (e *Evaluator) idleRule(g *rgroup, st *gstate, view *GroupView, live, soft string, haveFull bool, in LiveInputs, r groupRates, allowed time.Duration, test, force bool, now time.Time, emit func(string, string, string, []*rproc)) {
	c := e.C
	switch {
	case !eligibleForIdle(g):
		view.State, view.Reason = "ineligible", "not an app ("+orDash(g.Slice)+") — desktop/session infrastructure"
		return
	case soft != "":
		view.State, view.Reason = "protected", soft
		return
	case live != "":
		view.State, view.Reason = "live", live
		return
	case !haveFull || !in.WindowsOK:
		view.State, view.Reason = "unknown", "window list unavailable — will not judge idle"
		return
	}
	limit := allowed
	if test && c.TestIdleSec > 0 {
		limit = time.Duration(c.TestIdleSec * float64(time.Second))
	}
	idle := now.Sub(st.LastActive)
	if force || idle >= limit {
		action := "stop-unit"
		if g.Kind == "wine" {
			action = "wineserver-k"
		}
		net := 0.0
		for _, p := range g.Procs {
			net += in.NetBps[p.PID]
		}
		reason := fmt.Sprintf("no window/audio/traffic for %s, %.1f %% CPU, net %.1f KB/s (allowed %s)", humanDur(idle), r.CPUPct, net/1024, humanDur(limit))
		emit("idle", reason, action, g.Procs)
		return
	}
	view.State, view.Reason = "idle", fmt.Sprintf("idle %.1f of %.1f min allowed", idle.Minutes(), limit.Minutes())
}

func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}

func commList(ps []*rproc) string {
	seen := map[string]bool{}
	var out []string
	for _, p := range ps {
		n := p.Comm
		if p.Wine {
			n = p.exeBase()
		}
		if !seen[n] {
			seen[n] = true
			out = append(out, n)
		}
	}
	sort.Strings(out)
	if len(out) > 6 {
		out = append(out[:6], "…")
	}
	return strings.Join(out, ",")
}

func mcpName(p *rproc) string {
	cl := p.cmdline()
	for _, m := range mcpServerMarks {
		if strings.Contains(cl, m) {
			return strings.Fields(m)[0]
		}
	}
	return p.Comm
}

// ───────────────────────────── tmpfs ─────────────────────────────

type TmpCandidate struct {
	Path   string  `json:"path"`
	SizeMB float64 `json:"size_mb"`
	AgeMin float64 `json:"age_min"`
	Test   bool    `json:"test,omitempty"`
}

// openPaths builds the set of paths held open (fd) or mapped by any of procs.
func openPaths(root string, procs map[int]*rproc, dirs []string) map[string]bool {
	out := map[string]bool{}
	inDirs := func(s string) bool {
		for _, d := range dirs {
			if strings.HasPrefix(s, d+"/") {
				return true
			}
		}
		return false
	}
	for pid, p := range procs {
		for _, l := range p.FDs {
			if inDirs(l) {
				out[strings.TrimSuffix(l, " (deleted)")] = true
			}
		}
		if b, err := os.ReadFile(fmt.Sprintf("%s/%d/maps", root, pid)); err == nil {
			for _, line := range strings.Split(string(b), "\n") {
				f := strings.Fields(line)
				if len(f) >= 6 && inDirs(f[5]) {
					out[f[5]] = true
				}
			}
		}
	}
	return out
}

// tmpfsCandidates lists files on the RAM-backed dirs that are ours, big, old and closed.
func tmpfsCandidates(dirs []string, uid int, open map[string]bool, now time.Time, c ReapConfig) []TmpCandidate {
	var out []TmpCandidate
	minB := int64(c.TmpfsMinMB * 1024 * 1024)
	age := time.Duration(c.TmpfsAgeMin * float64(time.Minute))
	for _, d := range dirs {
		filepath.WalkDir(d, func(path string, de os.DirEntry, err error) error {
			if err != nil {
				if de != nil && de.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
			if de.IsDir() {
				if path != d && (strings.HasPrefix(de.Name(), "systemd-private-") || de.Name() == ".X11-unix") {
					return filepath.SkipDir
				}
				return nil
			}
			if !de.Type().IsRegular() {
				return nil
			}
			info, err := de.Info()
			if err != nil || info.Size() < minB || now.Sub(info.ModTime()) < age {
				return nil
			}
			if uid >= 0 && fileUID(info) != uid {
				return nil
			}
			if open[path] {
				return nil
			}
			out = append(out, TmpCandidate{Path: path, SizeMB: float64(info.Size()) / 1024 / 1024, AgeMin: now.Sub(info.ModTime()).Minutes(), Test: matchAnyLower(path, c.ActOnly) != ""})
			return nil
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].SizeMB > out[j].SizeMB })
	return out
}

// ───────────────────────────── root side: system units ─────────────────────────────
// Runs inside the ROOT daemon. The list is closed on purpose: root stops nothing else.

type SysCandidate struct {
	Unit   string  `json:"unit"`
	Reason string  `json:"reason"`
	PSSMB  float64 `json:"pss_mb"`
	SwapMB float64 `json:"swap_mb"`
	Action string  `json:"action"` // "would-stop" | "stopped" | "stop-failed: …" | "kept: …"
}

var vpnIfacePrefixes = []string{"tun", "wg", "proton", "pvpn", "ipv6leakintrf"}

// vpnInUse: a tunnel interface exists or the Proton GUI is open.
func vpnInUse(ifaces []string, cmdlines []string) (bool, string) {
	for _, i := range ifaces {
		for _, p := range vpnIfacePrefixes {
			if strings.HasPrefix(i, p) {
				return true, "tunnel interface " + i + " is up"
			}
		}
	}
	for _, cl := range cmdlines {
		if strings.Contains(cl, "protonvpn-app") || strings.Contains(cl, "proton.vpn.app") {
			return true, "Proton VPN app is open"
		}
	}
	return false, ""
}

// systemDecision: stop proton.VPN.service once nothing has used it for the gradient's time.
func systemDecision(active, inUse bool, lastUsed, now time.Time, allowed time.Duration) bool {
	return active && !inUse && now.Sub(lastUsed) >= allowed
}

type rootReaper struct {
	mu          sync.Mutex
	report      json.RawMessage
	reportAt    time.Time
	vpnLastUsed time.Time
	sys         []SysCandidate
	stopping    bool
}

var rootReap = &rootReaper{}

// agentHeader is the part of the agent's report root needs.
type agentHeader struct {
	Mode           string   `json:"mode"`
	IdleAllowedMin float64  `json:"idle_allowed_min"`
	ActOnly        []string `json:"act_only"`
}

func listIfaces() []string {
	ents, _ := os.ReadDir("/sys/class/net")
	var out []string
	for _, e := range ents {
		out = append(out, e.Name())
	}
	return out
}

func allCmdlines() []string {
	var out []string
	ents, _ := os.ReadDir("/proc")
	for _, e := range ents {
		if _, err := strconv.Atoi(e.Name()); err != nil {
			continue
		}
		if b, err := os.ReadFile("/proc/" + e.Name() + "/cmdline"); err == nil {
			out = append(out, strings.ReplaceAll(string(b), "\x00", " "))
		}
	}
	return out
}

// handleAgentReport stores the agent's latest report and evaluates the system units.
func (rr *rootReaper) handleAgentReport(raw json.RawMessage) []SysCandidate {
	var h agentHeader
	_ = json.Unmarshal(raw, &h)
	now := time.Now()
	rr.mu.Lock()
	rr.report, rr.reportAt = append(json.RawMessage(nil), raw...), now
	if rr.vpnLastUsed.IsZero() {
		rr.vpnLastUsed = now // fresh daemon: give it a full idle window
	}
	rr.mu.Unlock()

	const unit = "proton.VPN.service"
	active := exec.Command("systemctl", "is-active", "--quiet", unit).Run() == nil
	inUse, why := vpnInUse(listIfaces(), allCmdlines())
	rr.mu.Lock()
	defer rr.mu.Unlock()
	if inUse {
		rr.vpnLastUsed = now
	}
	var out []SysCandidate
	if active {
		allowed := time.Duration(h.IdleAllowedMin * float64(time.Minute))
		if allowed <= 0 {
			allowed = time.Hour
		}
		sc := SysCandidate{Unit: unit}
		if b, err := exec.Command("systemctl", "show", "-p", "MainPID", "--value", unit).Output(); err == nil {
			if pid, _ := strconv.Atoi(strings.TrimSpace(string(b))); pid > 0 {
				sc.PSSMB, sc.SwapMB = procMemMB("/proc", pid)
			}
		}
		if systemDecision(active, inUse, rr.vpnLastUsed, now, allowed) {
			sc.Reason = fmt.Sprintf("no VPN tunnel and no Proton app for %.0f min (allowed %.0f min)", now.Sub(rr.vpnLastUsed).Minutes(), allowed.Minutes())
			act := h.Mode == "act" || matchAnyLower(unit, h.ActOnly) != ""
			if act && !rr.stopping {
				rr.stopping = true
				go func() {
					err := exec.Command("systemctl", "stop", unit).Run()
					still := exec.Command("systemctl", "is-active", "--quiet", unit).Run() == nil
					rr.mu.Lock()
					rr.stopping = false
					res := "stopped"
					if err != nil || still {
						res = fmt.Sprintf("stop-failed: err=%v still-active=%v", err, still)
					}
					rr.sys = []SysCandidate{{Unit: unit, Reason: sc.Reason, PSSMB: sc.PSSMB, SwapMB: sc.SwapMB, Action: res}}
					rr.mu.Unlock()
					lg.Info("reaper: %s %s — %s (freed ≈ %.0f MB PSS+swap)", res, unit, sc.Reason, sc.PSSMB+sc.SwapMB)
				}()
				sc.Action = "stopping"
			} else {
				sc.Action = "would-stop"
			}
		} else if inUse {
			sc.Action, sc.Reason = "kept", why
		} else {
			sc.Action, sc.Reason = "kept", fmt.Sprintf("unused for %.0f of %.0f min", now.Sub(rr.vpnLastUsed).Minutes(), allowed.Minutes())
		}
		out = append(out, sc)
		rr.sys = out
	} else if len(rr.sys) > 0 && rr.sys[0].Action == "stopped" {
		out = rr.sys
	} else {
		rr.sys = nil
	}
	return out
}

// reapJSON is what `/reap` returns: the agent's last report + the system units.
func (rr *rootReaper) reapJSON() map[string]any {
	rr.mu.Lock()
	defer rr.mu.Unlock()
	out := map[string]any{"system": rr.sys, "agent_reported": rr.report != nil}
	if rr.report != nil {
		out["agent"] = rr.report
		out["agent_age_s"] = time.Since(rr.reportAt).Seconds()
	}
	return out
}

func fileUID(info os.FileInfo) int {
	if st, ok := info.Sys().(*syscall.Stat_t); ok {
		return int(st.Uid)
	}
	return -1
}

// humanDur: "45 s" under two minutes, "31 min" above — so a 30 s test threshold never reads "0 min".
func humanDur(d time.Duration) string {
	if d < 2*time.Minute {
		return fmt.Sprintf("%.0f s", d.Seconds())
	}
	return fmt.Sprintf("%.0f min", d.Minutes())
}
