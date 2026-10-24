// reap_agent.go — the user-session half of the reaper: `luminos-ram reaper`.
// [CHANGE: claude-code | 2026-10-24] DECISION 160.
//
// Runs as the user (systemd/user/luminos-ram-reaper.service) because only the user can see
// the session bus (KWin windows), PipeWire, the real /tmp and the user's systemd units —
// see the header of reap.go. This file does I/O; every decision is in reap.go.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime/pprof"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/godbus/dbus/v5"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
)

const ramSocket = "/run/luminos/ram.sock"

type agent struct {
	c       ReapConfig
	cfgPath string
	ev      *Evaluator
	log     *logger.Logger
	uid     int
	home    string

	bus      *dbus.Conn
	kwinCh   chan string
	kwinJS   string
	lastIn   LiveInputs
	lastFull time.Time
	procs    map[int]*rproc
	pcache   *staticCache

	netPrev   map[string]uint64
	netPrevAt time.Time
	gpuPrev   map[int]map[string]uint64
	gpuPrevAt time.Time

	offloadPID int
	logged     map[string]time.Time // candidate key+rule → last WOULD line
	sysLogged  string
	tmpLogged  map[string]bool
	lastTmpfs  time.Time
	lastTmp    []TmpCandidate
	lastPass    PassResult
	pendingLeft bool
}

// runReaper is the entry point for `luminos-ram reaper [flags]`.
func runReaper(args []string) int {
	fs := flag.NewFlagSet("reaper", flag.ContinueOnError)
	home, _ := os.UserHomeDir()
	cfgPath := fs.String("config", filepath.Join(home, ".config/luminos-ram-reaper.conf"), "config file")
	once := fs.Bool("once", false, "one pass, print JSON, exit")
	force := fs.Bool("force", false, "with --once: ignore idle time + liveness (protection still applies)")
	actOnly := fs.String("act-only", "", "comma list: act on matching groups even in log mode")
	mode := fs.String("mode", "", "override reap_mode (log|act)")
	if err := fs.Parse(args); err != nil {
		return 2
	}

	a := &agent{uid: os.Getuid(), home: home, cfgPath: *cfgPath, logged: map[string]time.Time{}, tmpLogged: map[string]bool{}, netPrev: map[string]uint64{}, gpuPrev: map[int]map[string]uint64{}}
	a.loadConfig()
	if *actOnly != "" {
		a.c.ActOnly = splitList(*actOnly)
	}
	if *mode != "" {
		a.c.Mode = *mode
	}
	logPath := filepath.Join(home, ".local/state/luminos/ram-reaper.log")
	jsonOut := os.Stdout
	if *once {
		os.Stdout = os.Stderr // logger tees to stdout; --once keeps stdout for the JSON alone
	}
	var err error
	if a.log, err = logger.New("luminos-ram-reaper", logPath, logger.INFO); err != nil {
		a.log = logger.NewStdout("luminos-ram-reaper", logger.INFO)
	}
	lg = a.log // reap.go helpers share the daemon's logger variable
	a.ev = NewEvaluator(a.c)
	a.ev.Uptime = func() float64 { return readUptime("/proc") }
	a.initKWin()

	defer os.Remove(a.kwinJS)
	if *once {
		return a.runOnce(*force, jsonOut)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	// Debug aid: LUMINOS_REAPER_CPUPROFILE=/path writes a 60 s CPU profile (go tool pprof -top).
	if p := os.Getenv("LUMINOS_REAPER_CPUPROFILE"); p != "" {
		if f, err := os.Create(p); err == nil && pprof.StartCPUProfile(f) == nil {
			go func() { time.Sleep(60 * time.Second); pprof.StopCPUProfile(); f.Close() }()
		}
	}
	hup := make(chan os.Signal, 1)
	signal.Notify(hup, syscall.SIGHUP)

	a.log.Info("reaper started — mode=%s, idle allowed %.0f→%.0f min across %.1f→%.1f GB available, keep=%v, act_only=%v",
		a.c.Mode, a.c.IdleMaxMin, a.c.IdleMinMin, a.c.AvailHiGB, a.c.AvailLoGB, a.c.Keep, a.c.ActOnly)
	t := time.NewTicker(a.c.Tick)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			a.log.Info("reaper stopped")
			return 0
		case <-hup:
			a.loadConfig()
			a.ev.C = a.c
			a.log.Info("config reloaded — mode=%s act_only=%v", a.c.Mode, a.c.ActOnly)
		case <-t.C:
			a.tick()
		}
	}
}

func (a *agent) loadConfig() {
	c := defaultReapConfig(a.home)
	if b, err := os.ReadFile(a.cfgPath); err == nil {
		var warn []string
		c, warn = parseReapConfig(string(b), c)
		for _, w := range warn {
			if a.log != nil {
				a.log.Warn("config %s: %s", a.cfgPath, w)
			}
		}
	}
	a.c = c
}

func (a *agent) runOnce(force bool, out *os.File) int {
	a.scan(true)
	time.Sleep(2 * time.Second)
	a.scan(true)
	a.collect()
	res := a.pass(true, force)
	if res.PendingLeft && !force {
		// Leftovers must stay leftovers for the grace period before they count — wait it out.
		time.Sleep(a.c.LeftoverGrace + time.Second)
		a.scan(true)
		a.collect()
		res = a.pass(true, force)
	}
	acted := []string{}
	for i := range res.Candidates {
		measure(&res.Candidates[i])
	}
	for _, c := range res.Candidates {
		if c.Test || a.c.Mode == "act" {
			acted = append(acted, a.act(c))
		}
	}
	doc := map[string]any{"pass": res, "acted": acted, "tmpfs": a.tmpfs(true)}
	enc := json.NewEncoder(out)
	enc.SetIndent("", "  ")
	enc.Encode(doc)
	return 0
}

// scan reads /proc through the static cache. On a full tick it re-reads cgroups and the fds
// of the processes the reaper could actually reap (GPU check) — not of the whole desktop.
func (a *agent) scan(full bool) {
	if a.pcache == nil {
		a.pcache = newStaticCache()
	}
	a.pcache.refreshCgroup = full
	a.procs = readProcsC("/proc", a.uid, a.home, a.pcache)
	groups := buildGroups(a.procs)
	if full {
		var pids []int
		pc := protCtx{OffloadPID: a.offloadPID}
		for _, g := range groups {
			if eligibleForIdle(g) && hardProtected(g, a.c, pc) == "" {
				pids = append(pids, g.pids()...)
			}
		}
		fillFDs("/proc", a.procs, pids)
	}
	a.ev.Observe(groups, a.procs, time.Now())
}

func (a *agent) pass(haveFull, force bool) PassResult {
	groups := buildGroups(a.procs)
	pc := protCtx{OffloadPID: a.offloadPID, SteamGameRunning: steamGameRunning(a.procs)}
	return a.ev.Pass(groups, a.procs, a.lastIn, haveFull, readMemAvailableGB("/proc"), pc, time.Now(), force)
}

// measure fills PSS + swap (smaps_rollup) — only for candidates being logged, acted on or
// reported, not on every 2-second tick.
func measure(c *Candidate) {
	c.PSSMB, c.SwapMB = 0, 0
	for _, pid := range c.PIDs {
		pss, sw := procMemMB("/proc", pid)
		c.PSSMB += pss
		c.SwapMB += sw
	}
}

func (a *agent) tick() {
	now := time.Now()
	// A full collect (windows, audio, sockets, GPU, fds) every FullEvery, and on every tick
	// while a leftover is waiting out its grace — so "app died" is judged on fresh data and
	// reaped within ~grace+tick seconds.
	full := now.Sub(a.lastFull) >= a.c.FullEvery || a.pendingLeft
	a.scan(full)
	if full {
		a.collect()
	}
	res := a.pass(time.Since(a.lastFull) < a.c.FullEvery+a.c.Tick, false)
	a.pendingLeft = res.PendingLeft
	a.handle(res)
	if now.Sub(a.lastTmpfs) >= a.c.TmpfsEvery {
		a.lastTmp = a.tmpfs(false)
		a.lastTmpfs = now
	}
	if full {
		a.pushReport(res)
	}
	a.lastPass = res
}

// handle logs (log mode) or acts (act mode / act_only) on every candidate.
func (a *agent) handle(res PassResult) {
	current := map[string]bool{}
	for _, c := range res.Candidates {
		k := c.Key + "|" + c.Rule
		current[k] = true
		if a.c.Mode == "act" || c.Test {
			measure(&c)
			a.log.Info("%s", a.act(c))
			delete(a.logged, k)
			continue
		}
		if t, ok := a.logged[k]; ok && time.Since(t) < 30*time.Minute {
			continue
		}
		a.logged[k] = time.Now()
		measure(&c)
		a.log.Info("WOULD-REAP app=%q rule=%s reason=%q pids=%v freed≈%.0f MB (PSS %.0f + swap %.0f) action=%s",
			c.Name, c.Rule, c.Reason, c.PIDs, c.PSSMB+c.SwapMB, c.PSSMB, c.SwapMB, c.Action)
	}
	for k := range a.logged {
		if !current[k] {
			delete(a.logged, k)
		}
	}
}

// ───────────────────────────── acting ─────────────────────────────

func sameProc(pid int, start uint64) bool {
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err != nil {
		return false
	}
	s := string(b)
	rp := strings.LastIndexByte(s, ')')
	if rp < 0 {
		return false
	}
	f := strings.Fields(s[rp+1:])
	if len(f) < 20 {
		return false
	}
	st, _ := strconv.ParseUint(f[19], 10, 64)
	if st != start {
		return false
	}
	return f[0] != "Z" // a zombie already freed its memory
}

func (a *agent) alive(c Candidate) []int {
	var out []int
	for _, pid := range c.PIDs {
		if sameProc(pid, c.Starts[pid]) {
			out = append(out, pid)
		}
	}
	return out
}

func (a *agent) waitGone(c Candidate, d time.Duration) []int {
	deadline := time.Now().Add(d)
	for {
		left := a.alive(c)
		if len(left) == 0 || time.Now().After(deadline) {
			return left
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func (a *agent) signalAll(pids []int, starts map[int]uint64, sig syscall.Signal) {
	for _, pid := range pids {
		if sameProc(pid, starts[pid]) {
			syscall.Kill(pid, sig)
		}
	}
}

func systemctlUser(args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	return exec.CommandContext(ctx, "systemctl", append([]string{"--user"}, args...)...).Run()
}

// act reaps one candidate and verifies by pid. Returns the log line.
func (a *agent) act(c Candidate) string {
	start := time.Now()
	how := ""
	switch c.Action {
	case "stop-unit":
		how = "systemctl --user stop " + c.Unit
		if err := systemctlUser("stop", "--no-block", c.Unit); err != nil {
			how += fmt.Sprintf(" (failed: %v → signals)", err)
			a.signalAll(c.PIDs, c.Starts, syscall.SIGTERM)
		}
		if left := a.waitGone(c, a.c.TermWait); len(left) > 0 {
			systemctlUser("kill", "-s", "SIGKILL", c.Unit)
			a.signalAll(left, c.Starts, syscall.SIGKILL)
			how += " + SIGKILL"
		}
	case "wineserver-k":
		srv := c.Server
		if srv == "" {
			srv = "wineserver"
		}
		how = "WINEPREFIX=" + c.Prefix + " " + srv + " -k"
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		cmd := exec.CommandContext(ctx, srv, "-k")
		cmd.Env = append(os.Environ(), "WINEPREFIX="+c.Prefix)
		if err := cmd.Run(); err != nil {
			how += fmt.Sprintf(" (failed: %v → signals)", err)
			a.signalAll(c.PIDs, c.Starts, syscall.SIGTERM)
		}
		cancel()
		if left := a.waitGone(c, a.c.TermWait); len(left) > 0 {
			a.signalAll(left, c.Starts, syscall.SIGKILL)
			how += " + SIGKILL"
		}
	default:
		how = "SIGTERM"
		a.signalAll(c.PIDs, c.Starts, syscall.SIGTERM)
		if left := a.waitGone(c, a.c.TermWait); len(left) > 0 {
			a.signalAll(left, c.Starts, syscall.SIGKILL)
			how += " + SIGKILL"
		}
	}
	left := a.waitGone(c, 2*time.Second)
	// Wine: verify by prefix, not just by the pids we knew — anything else of that world counts.
	if c.Prefix != "" && (c.Rule == "wine-no-server" || c.Rule == "wine-no-app" || strings.HasPrefix(c.Key, "wine:")) {
		for _, p := range readProcs("/proc", a.uid, false, a.home) {
			if p.Wine && p.Prefix == c.Prefix {
				left = append(left, p.PID)
			}
		}
		left = uniqInts(left)
	}
	verdict := "REAPED"
	if len(left) > 0 {
		verdict = "PARTIAL"
	}
	return fmt.Sprintf("%s app=%q rule=%s reason=%q pids=%v via %s in %.1fs — left=%v freed≈%.0f MB (PSS %.0f + swap %.0f)",
		verdict, c.Name, c.Rule, c.Reason, c.PIDs, how, time.Since(start).Seconds(), left, c.PSSMB+c.SwapMB, c.PSSMB, c.SwapMB)
}

func uniqInts(in []int) []int {
	sort.Ints(in)
	out := in[:0]
	for i, v := range in {
		if i == 0 || v != in[i-1] {
			out = append(out, v)
		}
	}
	return out
}

// ───────────────────────────── tmpfs ─────────────────────────────

func (a *agent) tmpfs(dry bool) []TmpCandidate {
	// Cheap first: walk the dirs. Only if something is big and old do we pay for a full
	// fd + maps scan of every process to prove nothing holds it.
	cands := tmpfsCandidates(a.c.TmpfsDirs, a.uid, map[string]bool{}, time.Now(), a.c)
	if len(cands) == 0 {
		return nil
	}
	// In log mode, a file already reported (same size + age class) needs no new proof every
	// minute; the full open-file scan reads every process's maps and is the costliest thing here.
	if a.c.Mode != "act" && !dry {
		fresh := false
		for _, t := range cands {
			if !a.tmpLogged[t.Path] || t.Test {
				fresh = true
			}
		}
		if !fresh {
			return a.lastTmp
		}
	}
	open := openPaths("/proc", readProcs("/proc", a.uid, true, a.home), a.c.TmpfsDirs)
	cands = tmpfsCandidates(a.c.TmpfsDirs, a.uid, open, time.Now(), a.c)
	// [CHANGE: claude-code | 2026-10-24] Return only what is still on disk — the report used to
	// list files it had just deleted ("738 MB reapable" after they were gone).
	var left []TmpCandidate
	for _, t := range cands {
		if !dry && (a.c.Mode == "act" || t.Test) {
			if err := os.Remove(t.Path); err != nil {
				a.log.Warn("TMPFS delete %s (%.0f MB) failed: %v", t.Path, t.SizeMB, err)
				left = append(left, t)
			} else {
				a.log.Info("TMPFS deleted %s — %.0f MB, untouched %.0f min, not open by any process", t.Path, t.SizeMB, t.AgeMin)
			}
			continue
		}
		left = append(left, t)
		if !a.tmpLogged[t.Path] {
			a.tmpLogged[t.Path] = true
			a.log.Info("TMPFS WOULD-DELETE %s — %.0f MB, untouched %.0f min, not open by any process", t.Path, t.SizeMB, t.AgeMin)
		}
	}
	return left
}


// ───────────────────────────── report to root ─────────────────────────────

func (a *agent) pushReport(res PassResult) {
	for i := range res.Candidates {
		measure(&res.Candidates[i])
	}
	rep := map[string]any{
		"at": res.At, "mode": a.c.Mode, "act_only": a.c.ActOnly, "avail_gb": res.AvailGB,
		"idle_allowed_min": res.IdleAllowed, "windows_known": res.WindowsOK,
		"candidates": res.Candidates, "groups": res.Groups, "tmpfs": a.lastTmp,
	}
	msg, err := socket.NewMessage("reap_report", "luminos-ram-reaper", rep)
	if err != nil {
		return
	}
	resp, err := socket.Send(ramSocket, msg)
	if err != nil || resp == nil {
		return
	}
	var r struct {
		System     []SysCandidate `json:"system"`
		OffloadPID int            `json:"offload_pid"`
	}
	if json.Unmarshal(resp.Payload, &r) == nil {
		a.offloadPID = r.OffloadPID
		for _, s := range r.System {
			line := fmt.Sprintf("SYSTEM %s unit=%s reason=%q ≈%.0f MB (PSS %.0f + swap %.0f)", strings.ToUpper(s.Action), s.Unit, s.Reason, s.PSSMB+s.SwapMB, s.PSSMB, s.SwapMB)
			key := s.Unit + s.Action
			if key != a.sysLogged {
				a.sysLogged = key
				a.log.Info("%s", line)
			}
		}
	}
}

// ───────────────────────────── collectors ─────────────────────────────

func (a *agent) collect() {
	now := time.Now()
	in := LiveInputs{WindowPIDs: map[int]bool{}, WindowClasses: map[string]bool{}, AudioPIDs: map[int]bool{}, GPUBusyPIDs: map[int]bool{}, NetBps: map[int]float64{}, ListenClient: map[int]bool{}, ProcOK: true}

	if pids, classes, focus, err := a.windows(); err == nil {
		in.WindowsOK, in.WindowPIDs, in.WindowClasses, in.FocusPID = true, pids, classes, focus
	} else if a.lastIn.WindowsOK || a.lastFull.IsZero() {
		a.log.Warn("window list unavailable: %v — idle reaping paused until it returns", err)
	}
	if out, err := exec.Command("pw-dump").Output(); err == nil {
		in.AudioPIDs = parsePwDump(out)
	}
	if out, err := exec.Command("ss", "-tinpH", "state", "established").Output(); err == nil {
		socks := parseSS(string(out))
		dt := now.Sub(a.netPrevAt).Seconds()
		next := map[string]uint64{}
		for _, s := range socks {
			k := s.Local + ">" + s.Peer
			next[k] = s.Bytes
			if prev, ok := a.netPrev[k]; ok && dt > 0 && s.Bytes >= prev {
				for _, pid := range s.PIDs {
					in.NetBps[pid] += float64(s.Bytes-prev) / dt
				}
			}
		}
		a.netPrev, a.netPrevAt = next, now
		if lo, err := exec.Command("ss", "-tlnpH").Output(); err == nil {
			for pid := range listenWithClient(parseListen(string(lo)), socks) {
				in.ListenClient[pid] = true
			}
		}
	}
	a.collectGPU(&in, now)
	a.lastIn, a.lastFull = in, now
}

// collectGPU: an open /dev/nvidia* is a GPU client (the dGPU is default-deny, so holding it
// means compute); a render node counts when its fdinfo engine time moved >= GPUPct.
func (a *agent) collectGPU(in *LiveInputs, now time.Time) {
	dt := now.Sub(a.gpuPrevAt).Seconds()
	next := map[int]map[string]uint64{}
	for pid, p := range a.procs {
		for _, l := range p.FDs {
			if strings.HasPrefix(l, "/dev/nvidia") && l != "/dev/nvidia-modeset" {
				in.GPUBusyPIDs[pid] = true
			}
		}
		eng := renderEngineNs(pid, p.FDs)
		if len(eng) == 0 {
			continue
		}
		next[pid] = eng
		if prev := a.gpuPrev[pid]; prev != nil && dt > 0 {
			var busy uint64
			for k, v := range eng {
				if pv, ok := prev[k]; ok && v >= pv {
					busy += v - pv
				}
			}
			if float64(busy)/(dt*1e9)*100 >= a.c.GPUPct {
				in.GPUBusyPIDs[pid] = true
			}
		}
	}
	a.gpuPrev, a.gpuPrevAt = next, now
}

// renderEngineNs sums drm-engine-* ns per DRM client of a process (deduped by client id).
func renderEngineNs(pid int, fds []string) map[string]uint64 {
	hasRender := false
	for _, l := range fds {
		if strings.HasPrefix(l, "/dev/dri/renderD") || strings.HasPrefix(l, "/dev/dri/card") {
			hasRender = true
			break
		}
	}
	if !hasRender {
		return nil
	}
	out := map[string]uint64{}
	ents, _ := os.ReadDir(fmt.Sprintf("/proc/%d/fdinfo", pid))
	for _, e := range ents {
		b, err := os.ReadFile(fmt.Sprintf("/proc/%d/fdinfo/%s", pid, e.Name()))
		if err != nil || !strings.Contains(string(b), "drm-engine-") {
			continue
		}
		client := e.Name()
		vals := map[string]uint64{}
		for _, line := range strings.Split(string(b), "\n") {
			if v, ok := strings.CutPrefix(line, "drm-client-id:"); ok {
				client = strings.TrimSpace(v)
			}
			if strings.HasPrefix(line, "drm-engine-") && !strings.HasPrefix(line, "drm-engine-capacity") {
				k, v, _ := strings.Cut(line, ":")
				n, _ := strconv.ParseUint(strings.Fields(strings.TrimSpace(v)+" 0")[0], 10, 64)
				vals[k] = n
			}
		}
		for k, v := range vals {
			out[client+"/"+k] = v
		}
	}
	return out
}

// parsePwDump returns pids of clients with a RUNNING audio stream (playback or capture).
func parsePwDump(b []byte) map[int]bool {
	var objs []struct {
		ID   int    `json:"id"`
		Type string `json:"type"`
		Info struct {
			State string         `json:"state"`
			Props map[string]any `json:"props"`
		} `json:"info"`
	}
	out := map[int]bool{}
	if json.Unmarshal(b, &objs) != nil {
		return out
	}
	clientPID := map[int]int{}
	toInt := func(v any) int {
		switch x := v.(type) {
		case float64:
			return int(x)
		case string:
			n, _ := strconv.Atoi(x)
			return n
		}
		return 0
	}
	for _, o := range objs {
		if strings.HasSuffix(o.Type, ":Client") {
			pid := toInt(o.Info.Props["application.process.id"])
			if pid == 0 {
				pid = toInt(o.Info.Props["pipewire.sec.pid"])
			}
			clientPID[o.ID] = pid
		}
	}
	for _, o := range objs {
		if !strings.HasSuffix(o.Type, ":Node") || o.Info.State != "running" {
			continue
		}
		mc, _ := o.Info.Props["media.class"].(string)
		if !strings.HasPrefix(mc, "Stream/") || !strings.Contains(mc, "Audio") {
			continue
		}
		pid := toInt(o.Info.Props["application.process.id"])
		if pid == 0 {
			pid = clientPID[toInt(o.Info.Props["client.id"])]
		}
		if pid > 0 {
			out[pid] = true
		}
	}
	return out
}

type ssSock struct {
	Local, Peer string
	PIDs        []int
	Bytes       uint64
}

var ssPidRe = regexp.MustCompile(`pid=(\d+)`)

func isNum(s string) bool { _, err := strconv.Atoi(s); return err == nil }

// parseSS parses `ss -tinpH state established`: a header line per socket followed by an
// indented info line carrying bytes_sent / bytes_received.
func parseSS(out string) []ssSock {
	var socks []ssSock
	var cur *ssSock
	sc := bufio.NewScanner(strings.NewReader(out))
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	for sc.Scan() {
		line := sc.Text()
		if strings.TrimSpace(line) == "" {
			continue
		}
		if line[0] == ' ' || line[0] == '\t' {
			if cur != nil {
				for _, f := range strings.Fields(line) {
					for _, key := range []string{"bytes_sent:", "bytes_received:"} {
						if v, ok := strings.CutPrefix(f, key); ok {
							n, _ := strconv.ParseUint(v, 10, 64)
							cur.Bytes += n
						}
					}
				}
			}
			continue
		}
		f := strings.Fields(line)
		i := 0
		if len(f) > 0 && !isNum(f[0]) {
			i = 1 // a State column is present
		}
		if len(f) < i+4 {
			cur = nil
			continue
		}
		socks = append(socks, ssSock{Local: f[i+2], Peer: f[i+3]})
		cur = &socks[len(socks)-1]
		for _, m := range ssPidRe.FindAllStringSubmatch(line, -1) {
			n, _ := strconv.Atoi(m[1])
			cur.PIDs = append(cur.PIDs, n)
		}
	}
	return socks
}

func portOf(addr string) string {
	if i := strings.LastIndexByte(addr, ':'); i >= 0 {
		return addr[i+1:]
	}
	return ""
}

// parseListen: pid → listening ports, from `ss -tlnpH`.
func parseListen(out string) map[int][]string {
	res := map[int][]string{}
	for _, line := range strings.Split(out, "\n") {
		f := strings.Fields(line)
		i := 0
		if len(f) > 0 && !isNum(f[0]) {
			i = 1
		}
		if len(f) < i+4 {
			continue
		}
		port := portOf(f[i+2])
		for _, m := range ssPidRe.FindAllStringSubmatch(line, -1) {
			n, _ := strconv.Atoi(m[1])
			res[n] = append(res[n], port)
		}
	}
	return res
}

// listenWithClient: pids that own a listen port AND an established socket on that local port
// (an accepted client connection).
func listenWithClient(listen map[int][]string, socks []ssSock) map[int]bool {
	out := map[int]bool{}
	for _, s := range socks {
		lp := portOf(s.Local)
		for _, pid := range s.PIDs {
			for _, p := range listen[pid] {
				if p == lp {
					out[pid] = true
				}
			}
		}
	}
	return out
}

// ───────────────────────────── windows ─────────────────────────────

// Each reaper process owns its OWN bus name: a `--once` run must never steal the running
// agent's name, or the agent's window list would silently go dark.
func kwinBusName() string { return fmt.Sprintf("org.luminos.RamReaper.p%d", os.Getpid()) }

// kwinReceiver is the D-Bus object the KWin script calls back with its window list.
type kwinReceiver struct{ ch chan string }

func (k *kwinReceiver) Windows(js string) *dbus.Error {
	select {
	case k.ch <- js:
	default:
	}
	return nil
}

// The script asks KWin for every window's pid + class and the active window, and hands the
// list back over D-Bus. KWin 6 calls them windows, KWin 5 clients — both handled.
const kwinScript = `
var list = workspace.windowList ? workspace.windowList() : workspace.clientList();
var out = [];
for (var i = 0; i < list.length; i++) {
  var w = list[i];
  out.push({pid: w.pid, cls: String(w.resourceClass || ""), min: !!w.minimized});
}
var a = workspace.activeWindow !== undefined ? workspace.activeWindow : workspace.activeClient;
callDBus("@BUS@", "/Reaper", "org.luminos.RamReaper", "Windows",
         JSON.stringify({windows: out, active: a ? a.pid : 0}));
`

func (a *agent) initKWin() {
	conn, err := dbus.ConnectSessionBus()
	if err != nil {
		return
	}
	a.bus = conn
	a.kwinCh = make(chan string, 1)
	conn.Export(&kwinReceiver{ch: a.kwinCh}, "/Reaper", "org.luminos.RamReaper")
	conn.RequestName(kwinBusName(), dbus.NameFlagDoNotQueue)
	dir := filepath.Join(os.Getenv("XDG_RUNTIME_DIR"), "luminos-ram-reaper")
	if os.Getenv("XDG_RUNTIME_DIR") == "" {
		dir = fmt.Sprintf("/run/user/%d/luminos-ram-reaper", a.uid)
	}
	os.MkdirAll(dir, 0700)
	a.kwinJS = filepath.Join(dir, fmt.Sprintf("windows-%d.js", os.Getpid()))
	os.WriteFile(a.kwinJS, []byte(strings.ReplaceAll(kwinScript, "@BUS@", kwinBusName())), 0600)
}

type winList struct {
	Windows []struct {
		PID int    `json:"pid"`
		Cls string `json:"cls"`
	} `json:"windows"`
	Active int `json:"active"`
}

func parseWindows(js string) (map[int]bool, map[string]bool, int, error) {
	var wl winList
	if err := json.Unmarshal([]byte(js), &wl); err != nil {
		return nil, nil, 0, err
	}
	pids, cls := map[int]bool{}, map[string]bool{}
	for _, w := range wl.Windows {
		if w.PID > 0 {
			pids[w.PID] = true
		}
		if w.Cls != "" {
			cls[strings.ToLower(w.Cls)] = true
		}
	}
	return pids, cls, wl.Active, nil
}

func (a *agent) windows() (map[int]bool, map[string]bool, int, error) {
	if a.bus != nil {
		if js, err := a.kwinWindows(); err == nil {
			return parseWindows(js)
		} else if !errors.Is(err, errNoKWin) {
			return nil, nil, 0, err
		}
	}
	return hyprWindows(a.uid)
}

var errNoKWin = errors.New("KWin not on the session bus")

func (a *agent) kwinWindows() (string, error) {
	var owner string
	if err := a.bus.BusObject().Call("org.freedesktop.DBus.GetNameOwner", 0, "org.kde.KWin").Store(&owner); err != nil {
		return "", errNoKWin
	}
	plugin := fmt.Sprintf("luminos-ram-reaper-windows-%d", os.Getpid())
	sc := a.bus.Object("org.kde.KWin", "/Scripting")
	sc.Call("org.kde.kwin.Scripting.unloadScript", 0, plugin)
	var id int32
	if err := sc.Call("org.kde.kwin.Scripting.loadScript", 0, a.kwinJS, plugin).Store(&id); err != nil {
		return "", fmt.Errorf("loadScript: %w", err)
	}
	defer sc.Call("org.kde.kwin.Scripting.unloadScript", 0, plugin)
	if id < 0 {
		return "", fmt.Errorf("loadScript returned %d", id)
	}
	select { // drop any stale reply
	case <-a.kwinCh:
	default:
	}
	path := dbus.ObjectPath(fmt.Sprintf("/Scripting/Script%d", id))
	if call := a.bus.Object("org.kde.KWin", path).Call("org.kde.kwin.Script.run", 0); call.Err != nil {
		return "", fmt.Errorf("Script.run: %w", call.Err)
	}
	select {
	case js := <-a.kwinCh:
		return js, nil
	case <-time.After(2 * time.Second):
		return "", errors.New("KWin script did not answer in 2 s")
	}
}

// hyprWindows: the Hyprland session (DECISION 39) — hyprctl clients -j.
func hyprWindows(uid int) (map[int]bool, map[string]bool, int, error) {
	socks, _ := filepath.Glob(fmt.Sprintf("/run/user/%d/hypr/*/.socket.sock", uid))
	if len(socks) == 0 {
		return nil, nil, 0, errors.New("no KWin and no Hyprland instance")
	}
	sig := filepath.Base(filepath.Dir(socks[0]))
	run := func(args ...string) ([]byte, error) {
		cmd := exec.Command("hyprctl", args...)
		cmd.Env = append(os.Environ(), "HYPRLAND_INSTANCE_SIGNATURE="+sig)
		return cmd.Output()
	}
	out, err := run("clients", "-j")
	if err != nil {
		return nil, nil, 0, fmt.Errorf("hyprctl clients: %w", err)
	}
	var cl []struct {
		PID   int    `json:"pid"`
		Class string `json:"class"`
	}
	if err := json.Unmarshal(out, &cl); err != nil {
		return nil, nil, 0, err
	}
	pids, cls := map[int]bool{}, map[string]bool{}
	for _, c := range cl {
		pids[c.PID] = true
		cls[strings.ToLower(c.Class)] = true
	}
	focus := 0
	if aw, err := run("activewindow", "-j"); err == nil {
		var w struct {
			PID int `json:"pid"`
		}
		json.Unmarshal(aw, &w)
		focus = w.PID
	}
	return pids, cls, focus, nil
}
