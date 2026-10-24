// [CHANGE: claude-code | 2026-10-24] DECISION 160 — reaper unit tests.
//
// Every test builds a FAKE /proc tree (stat, status, cmdline, cgroup, environ, io, exe and fd
// symlinks) in a temp dir — the same files readProcs parses on the real machine — and drives
// the pure decision code. Most cases are negative: the protected classes must never become
// candidates, and an open tmpfs file must never be listed.
package main

import (
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const tuid = 1000
const thome = "/home/shawn"

type fp struct {
	pid, ppid, tty int
	comm           string
	exe            string
	args           []string
	cg             string // cgroup path after 0::
	env            []string
	cpu            uint64
	start          uint64
	rd, wr         uint64
	fds            []string
	uid            int
}

const appSlice = "/user.slice/user-1000.slice/user@1000.service/app.slice/"

func writeProc(t *testing.T, root string, p fp) {
	t.Helper()
	d := filepath.Join(root, fmt.Sprint(p.pid))
	if err := os.MkdirAll(filepath.Join(d, "fd"), 0755); err != nil {
		t.Fatal(err)
	}
	uid := p.uid
	if uid == 0 {
		uid = tuid
	}
	start := p.start
	if start == 0 {
		start = 1000
	}
	w := func(name, s string) {
		if err := os.WriteFile(filepath.Join(d, name), []byte(s), 0644); err != nil {
			t.Fatal(err)
		}
	}
	w("stat", fmt.Sprintf("%d (%s) S %d 0 0 %d 0 0 0 0 0 0 %d 0 0 0 20 0 1 0 %d 0 0", p.pid, p.comm, p.ppid, p.tty, p.cpu, start))
	w("status", fmt.Sprintf("Name:\t%s\nUid:\t%d\t%d\t%d\t%d\n", p.comm, uid, uid, uid, uid))
	args := p.args
	if len(args) == 0 {
		args = []string{p.comm}
	}
	w("cmdline", strings.Join(args, "\x00")+"\x00")
	w("cgroup", "0::"+p.cg+"\n")
	w("environ", strings.Join(p.env, "\x00")+"\x00")
	w("io", fmt.Sprintf("rchar: 0\nwchar: 0\nread_bytes: %d\nwrite_bytes: %d\n", p.rd, p.wr))
	os.Remove(filepath.Join(d, "exe"))
	if p.exe != "" {
		os.Symlink(p.exe, filepath.Join(d, "exe"))
	}
	for i, f := range p.fds {
		os.Symlink(f, filepath.Join(d, "fd", fmt.Sprint(i+3)))
	}
}

func fakeTree(t *testing.T, ps ...fp) string {
	root := t.TempDir()
	for _, p := range ps {
		writeProc(t, root, p)
	}
	os.WriteFile(filepath.Join(root, "uptime"), []byte("100000.00 1.00\n"), 0644)
	return root
}

func cfg() ReapConfig {
	c := defaultReapConfig(thome)
	return c
}

func noInputs() LiveInputs {
	return LiveInputs{WindowsOK: true, WindowPIDs: map[int]bool{}, WindowClasses: map[string]bool{}, AudioPIDs: map[int]bool{}, GPUBusyPIDs: map[int]bool{}, NetBps: map[int]float64{}, ListenClient: map[int]bool{}}
}

// runPasses observes the tree at t0, then passes at t0+after.
func evalAt(t *testing.T, root string, c ReapConfig, in LiveInputs, avail float64, after time.Duration, pc protCtx) (PassResult, *Evaluator) {
	t.Helper()
	e := NewEvaluator(c)
	e.Uptime = func() float64 { return readUptime(root) }
	t0 := time.Unix(1_800_000_000, 0)
	procs := readProcs(root, tuid, true, thome)
	e.Observe(buildGroups(procs), procs, t0)
	e.Pass(buildGroups(procs), procs, in, true, avail, pc, t0, false)
	e.Observe(buildGroups(procs), procs, t0.Add(after))
	r := e.Pass(buildGroups(procs), procs, in, true, avail, pc, t0.Add(after), false)
	return r, e
}

func candFor(r PassResult, sub string) *Candidate {
	for i, c := range r.Candidates {
		if strings.Contains(c.Key, sub) || strings.Contains(c.Name, sub) {
			return &r.Candidates[i]
		}
	}
	return nil
}

func viewFor(r PassResult, sub string) *GroupView {
	for i, g := range r.Groups {
		if strings.Contains(g.Key, sub) {
			return &r.Groups[i]
		}
	}
	return nil
}

// ───────── gradient ─────────

func TestIdleAllowedGradient(t *testing.T) {
	c := cfg()
	cases := []struct{ gb, want float64 }{{12, 60}, {6, 60}, {3.5, 31}, {1, 2}, {0.3, 2}}
	for _, k := range cases {
		if got := idleAllowed(k.gb, c).Minutes(); math.Abs(got-k.want) > 0.01 {
			t.Errorf("idleAllowed(%.1f GB) = %.2f min, want %.2f", k.gb, got, k.want)
		}
	}
	// Continuous: no step anywhere — 10 MB less RAM never costs more than a few seconds.
	prev := idleAllowed(7, c)
	for gb := 7.0; gb >= 0; gb -= 0.01 {
		cur := idleAllowed(gb, c)
		if cur > prev {
			t.Fatalf("not monotonic at %.2f GB", gb)
		}
		if (prev - cur) > 10*time.Second {
			t.Fatalf("jump of %v at %.2f GB — that is a mode switch, not a gradient", prev-cur, gb)
		}
		prev = cur
	}
}

func TestParseConfig(t *testing.T) {
	c, warn := parseReapConfig("# x\nreap_mode = act\nkeep = discord, Steam\nidle_max_min=90\nact_only=lrtest\nbogus=1\nreap_mode=yolo\ncpu_pct=-3\n", cfg())
	if c.Mode != "act" {
		t.Errorf("mode = %q", c.Mode)
	}
	if c.IdleMaxMin != 90 || len(c.ActOnly) != 1 || c.ActOnly[0] != "lrtest" {
		t.Errorf("parsed %+v", c)
	}
	if matchAnyLower("Discord", c.Keep) == "" || matchAnyLower("metatrader", c.Keep) == "" {
		t.Error("keep-list must ADD to the built-in keep entries, not replace them")
	}
	if len(warn) != 3 {
		t.Errorf("want 3 warnings (unknown key, bad mode, negative number), got %v", warn)
	}
	if c2, w2 := parseReapConfig("cpu_pct = 5   # % of one core\nkeep =\n", cfg()); c2.CPUPct != 5 || len(w2) != 0 {
		t.Errorf("inline comments / empty keep: cpu=%v warn=%v", c2.CPUPct, w2)
	}
	if d := defaultReapConfig(thome); d.Mode != "log" {
		t.Error("the first install must default to log (dry-run)")
	}
}

func TestParseCgroup(t *testing.T) {
	_, s, u := parseCgroup("0::"+appSlice+`app-luminos\x2dkeyboard\x2dsmart@autostart.service`, 1000)
	if s != "app.slice" || u != "app-luminos-keyboard-smart@autostart.service" {
		t.Errorf("got slice=%q unit=%q", s, u)
	}
	_, s, u = parseCgroup("0::/user.slice/user-1000.slice/session-4.scope", 1000)
	if s != "" || u != "session-4.scope" {
		t.Errorf("login session: slice=%q unit=%q", s, u)
	}
}

// ───────── grouping ─────────

func TestGroupingByCgroupAndPrefix(t *testing.T) {
	root := fakeTree(t,
		fp{pid: 10, ppid: 1, comm: "claude-desktop", exe: "/usr/lib/claude-desktop/claude-desktop", cg: appSlice + "app-com.anthropic.Claude-10.scope"},
		fp{pid: 11, ppid: 10, comm: "claude-desktop", exe: "/usr/lib/claude-desktop/claude-desktop", args: []string{"/usr/lib/claude-desktop/claude-desktop", "--type=renderer"}, cg: appSlice + "app-com.anthropic.Claude-10.scope"},
		// The 2026-10-24 shape: orphaned Wine of two prefixes, in the scope of a DEAD Claude.
		fp{pid: 20, ppid: 1, comm: "services.exe", exe: "/usr/bin/wine64-preloader", args: []string{`C:\windows\system32\services.exe`}, cg: appSlice + "app-com.anthropic.Claude-19426.scope", env: []string{"WINEPREFIX=/home/shawn/Games/mw4-syswine"}},
		fp{pid: 21, ppid: 1, comm: "plugplay.exe", exe: "/usr/bin/wine64-preloader", args: []string{`C:\windows\system32\plugplay.exe`}, cg: appSlice + "app-com.anthropic.Claude-19426.scope", env: []string{"WINEPREFIX=/home/shawn/Games/mw4-syswine/"}},
		fp{pid: 22, ppid: 1, comm: "services.exe", exe: "/usr/bin/wine64-preloader", args: []string{`C:\windows\system32\services.exe`}, cg: appSlice + "app-other.scope", env: []string{"WINEPREFIX=/home/shawn/Games/mw4"}},
		fp{pid: 30, ppid: 5, comm: "openclaw-gatewa", cg: appSlice + "openclaw-gateway.service"},
		fp{pid: 40, ppid: 1, comm: "sleep", cg: appSlice + "x.scope", uid: 1001}, // other user: not ours
	)
	g := buildGroups(readProcs(root, tuid, false, thome))
	if len(g["unit:app-com.anthropic.Claude-10.scope"].Procs) != 2 {
		t.Error("Claude main + renderer must be one app")
	}
	if w := g["wine:/home/shawn/Games/mw4-syswine"]; w == nil || len(w.Procs) != 2 {
		t.Errorf("one WINEPREFIX = one group (trailing slash normalised): %+v", w)
	}
	if g["wine:/home/shawn/Games/mw4"] == nil {
		t.Error("second prefix must be its own group")
	}
	if _, ok := g["unit:app-com.anthropic.Claude-19426.scope"]; ok {
		t.Error("Wine processes must be carved out of the dead scope, leaving no unit group")
	}
	if g["unit:openclaw-gateway.service"] == nil {
		t.Error("services are their own units")
	}
	if g["unit:x.scope"] != nil {
		t.Error("another user's process was grouped")
	}
	// No WINEPREFIX → ~/.wine
	root2 := fakeTree(t, fp{pid: 50, ppid: 1, comm: "explorer.exe", exe: "/usr/bin/wine64-preloader", args: []string{`C:\windows\explorer.exe`, "/desktop"}, cg: appSlice + "a.scope"})
	if buildGroups(readProcs(root2, tuid, false, thome))["wine:/home/shawn/.wine"] == nil {
		t.Error("unset WINEPREFIX must default to ~/.wine")
	}
}

// ───────── idle rule + every live signal ─────────

func idleApp() fp {
	return fp{pid: 100, ppid: 1, comm: "someapp", exe: "/usr/bin/someapp", cg: appSlice + "app-someapp-100.scope", fds: []string{"/dev/null"}}
}

func TestIdleReapedAfterThresholdOnly(t *testing.T) {
	root := fakeTree(t, idleApp())
	c := cfg()
	// 9 GB available → 60 min allowed. 59 min idle: not yet.
	r, _ := evalAt(t, root, c, noInputs(), 9, 59*time.Minute, protCtx{})
	if candFor(r, "someapp") != nil {
		t.Fatal("reaped before the gradient threshold")
	}
	r, _ = evalAt(t, root, c, noInputs(), 9, 61*time.Minute, protCtx{})
	cd := candFor(r, "someapp")
	if cd == nil || cd.Rule != "idle" || cd.Action != "stop-unit" || cd.Unit != "app-someapp-100.scope" {
		t.Fatalf("want idle stop-unit candidate, got %+v", cd)
	}
	if !strings.Contains(cd.Reason, "for 61 min") || !strings.Contains(cd.Reason, "allowed 60 min") {
		t.Errorf("reason must say why: %q", cd.Reason)
	}
	// Same 5 min idle: kept at 9 GB, reaped at 1.2 GB (allowed ≈ 3.2 min).
	r, _ = evalAt(t, root, c, noInputs(), 9, 5*time.Minute, protCtx{})
	if candFor(r, "someapp") != nil {
		t.Error("5 min idle with plenty of RAM must be kept")
	}
	r, _ = evalAt(t, root, c, noInputs(), 1.2, 5*time.Minute, protCtx{})
	if candFor(r, "someapp") == nil {
		t.Error("5 min idle under pressure must be reaped")
	}
}

func TestEachLiveSignalKeepsApp(t *testing.T) {
	c := cfg()
	root := fakeTree(t, idleApp())
	type mod func(in *LiveInputs)
	cases := map[string]mod{
		"window":        func(in *LiveInputs) { in.WindowPIDs[100] = true },
		"focus":         func(in *LiveInputs) { in.FocusPID = 100 },
		"audio":         func(in *LiveInputs) { in.AudioPIDs[100] = true },
		"gpu":           func(in *LiveInputs) { in.GPUBusyPIDs[100] = true },
		"network":       func(in *LiveInputs) { in.NetBps[100] = 5 * 1024 },
		"listen client": func(in *LiveInputs) { in.ListenClient[100] = true },
	}
	for name, m := range cases {
		in := noInputs()
		m(&in)
		e := NewEvaluator(c)
		procs := readProcs(root, tuid, false, thome)
		t0 := time.Unix(1_800_000_000, 0)
		e.Observe(buildGroups(procs), procs, t0)
		// The signal is present for the whole 2 hours.
		r := e.Pass(buildGroups(procs), procs, in, true, 0.5, protCtx{}, t0.Add(2*time.Hour), false)
		if candFor(r, "someapp") != nil {
			t.Errorf("%s: a live app was reaped", name)
		}
		if v := viewFor(r, "someapp"); v == nil || v.State != "live" {
			t.Errorf("%s: want state live, got %+v", name, v)
		}
	}
	// A trickle of keep-alive traffic below the threshold is NOT live.
	in := noInputs()
	in.NetBps[100] = 100
	r, _ := evalAt(t, root, c, in, 0.5, 10*time.Minute, protCtx{})
	if candFor(r, "someapp") == nil {
		t.Error("100 B/s of keep-alives must not count as live traffic")
	}
}

func TestFocusAndListenAreRemembered(t *testing.T) {
	c := cfg()
	root := fakeTree(t, idleApp())
	procs := readProcs(root, tuid, false, thome)
	e := NewEvaluator(c)
	t0 := time.Unix(1_800_000_000, 0)
	e.Observe(buildGroups(procs), procs, t0)
	in := noInputs()
	in.ListenClient[100] = true
	e.Pass(buildGroups(procs), procs, in, true, 0.5, protCtx{}, t0, false)
	// 5 min later the client is gone but it was there within listen_client_min (10).
	r := e.Pass(buildGroups(procs), procs, noInputs(), true, 0.5, protCtx{}, t0.Add(5*time.Minute), false)
	if candFor(r, "someapp") != nil {
		t.Error("a listen socket that had a client 5 min ago must keep the app")
	}
	r = e.Pass(buildGroups(procs), procs, noInputs(), true, 0.5, protCtx{}, t0.Add(16*time.Minute), false)
	if candFor(r, "someapp") == nil {
		t.Error("16 min after the last client (allowed 2+10) the app must go")
	}
}

func TestCPUAndDiskAreMeasured(t *testing.T) {
	c := cfg()
	for _, k := range []struct {
		name         string
		cpu, rd, wr  uint64
		wantLive     bool
	}{
		{"cpu 10%", 600, 0, 0, true},  // 600 ticks over 60 s = 10 %
		{"cpu 1%", 60, 0, 0, false},   // 1 % < 2 %
		{"disk 2MB/s", 0, 120 << 20, 0, true},
		{"download 200KB/s", 0, 0, 12000 << 10, true},
		{"quiet", 0, 0, 0, false},
	} {
		root := fakeTree(t, idleApp())
		e := NewEvaluator(c)
		t0 := time.Unix(1_800_000_000, 0)
		procs := readProcs(root, tuid, false, thome)
		e.Observe(buildGroups(procs), procs, t0)
		p := idleApp()
		p.cpu, p.rd, p.wr = k.cpu, k.rd, k.wr
		writeProc(t, root, p)
		procs = readProcs(root, tuid, false, thome)
		now := t0.Add(60 * time.Second)
		e.Observe(buildGroups(procs), procs, now)
		e.States["unit:app-someapp-100.scope"].LastActive = now.Add(-3 * time.Hour) // long idle before this minute
		r := e.Pass(buildGroups(procs), procs, noInputs(), true, 0.5, protCtx{}, now, false)
		if got := candFor(r, "someapp") == nil; got != k.wantLive {
			t.Errorf("%s: live=%v want %v (%+v)", k.name, got, k.wantLive, viewFor(r, "someapp"))
		}
	}
}

func TestNoWindowListMeansNoIdleReap(t *testing.T) {
	root := fakeTree(t, idleApp())
	in := noInputs()
	in.WindowsOK = false
	r, _ := evalAt(t, root, cfg(), in, 0.5, 3*time.Hour, protCtx{})
	if candFor(r, "someapp") != nil {
		t.Fatal("without a window list the reaper cannot know an app is windowless — it must not guess")
	}
}

func TestActOnlyAndTestIdle(t *testing.T) {
	c := cfg()
	c.ActOnly, c.TestIdleSec = []string{"lrtest"}, 30
	p := idleApp()
	p.cg = appSlice + "lrtest-idle.scope"
	root := fakeTree(t, p, fp{pid: 200, ppid: 1, comm: "other", cg: appSlice + "app-other.scope"})
	r, _ := evalAt(t, root, c, noInputs(), 9, 40*time.Second, protCtx{})
	cd := candFor(r, "lrtest")
	if cd == nil || !cd.Test {
		t.Fatalf("test group must use test_idle_s and be flagged Test: %+v", cd)
	}
	if candFor(r, "app-other") != nil {
		t.Error("test_idle_s must not shorten the threshold for real apps")
	}
}

// ───────── protected classes (negative tests) ─────────

func TestProtectedNeverReaped(t *testing.T) {
	c := cfg()
	c.Keep = append(c.Keep, "keepme")
	sess := "/user.slice/user-1000.slice/user@1000.service/session.slice/"
	cases := []struct {
		name string
		p    fp
		pc   protCtx
	}{
		{"kwin (session.slice)", fp{pid: 300, ppid: 1, comm: "kwin_wayland", cg: sess + "plasma-kwin_wayland.service"}, protCtx{}},
		{"plasmashell", fp{pid: 300, ppid: 1, comm: "plasmashell", cg: sess + "plasma-plasmashell.service"}, protCtx{}},
		{"pipewire", fp{pid: 300, ppid: 1, comm: "pipewire", cg: sess + "pipewire.service"}, protCtx{}},
		{"luminos user unit", fp{pid: 300, ppid: 1, comm: "python3", cg: appSlice + "luminos-coder-gateway.service"}, protCtx{}},
		{"mcp-share broker", fp{pid: 300, ppid: 1, comm: "python3", cg: appSlice + "luminos-mcp-share-mempalace.service"}, protCtx{}},
		{"escaped luminos autostart", fp{pid: 300, ppid: 1, comm: "luminos-keyboar", cg: appSlice + `app-luminos\x2dkeyboard\x2dsmart@autostart.service`}, protCtx{}},
		{"cowork service", fp{pid: 300, ppid: 1, comm: "cowork-svc-linu", cg: appSlice + "claude-cowork.service"}, protCtx{}},
		{"hive watchdog", fp{pid: 300, ppid: 1, comm: "hive-idle-watch", cg: appSlice + "hive-idle-watchdog.service"}, protCtx{}},
		{"gnome-keyring", fp{pid: 300, ppid: 1, comm: "gnome-keyring-d", cg: appSlice + "gnome-keyring-daemon.service"}, protCtx{}},
		{"xvfb (forex bot display)", fp{pid: 300, ppid: 1, comm: "Xvfb", cg: appSlice + "xvfb.service"}, protCtx{}},
		{"Claude Max app", fp{pid: 300, ppid: 1, comm: "claude-desktop", exe: "/usr/lib/claude-desktop/claude-desktop", args: []string{"/usr/lib/claude-desktop/claude-desktop", "--ozone-platform=wayland"}, cg: appSlice + "app-com.anthropic.Claude-300.scope"}, protCtx{}},
		{"Claude Max app explicit dir", fp{pid: 300, ppid: 1, comm: "claude-desktop", exe: "/usr/lib/claude-desktop/claude-desktop", args: []string{"/usr/lib/claude-desktop/claude-desktop", "--user-data-dir=/home/shawn/.config/Claude/"}, cg: appSlice + "app-x.scope"}, protCtx{}},
		{"qemu Cowork VM", fp{pid: 300, ppid: 1, comm: "qemu-system-x86", cg: appSlice + "app-qemu.scope"}, protCtx{}},
		{"llama-server", fp{pid: 300, ppid: 1, comm: "llama-server", cg: appSlice + "jobhunt-llm.service"}, protCtx{}},
		{"offload pid", fp{pid: 300, ppid: 1, comm: "python3", cg: appSlice + "app-train.scope"}, protCtx{OffloadPID: 300}},
		{"keep-list", fp{pid: 300, ppid: 1, comm: "keepme-daemon", cg: appSlice + "app-k.scope"}, protCtx{}},
		{"terminal emulator", fp{pid: 300, ppid: 1, comm: "konsole", cg: appSlice + "app-org.kde.konsole-300.scope"}, protCtx{}},
		{"shell with a tty", fp{pid: 300, ppid: 1, comm: "bash", tty: 34817, cg: appSlice + "app-term.scope"}, protCtx{}},
		{"Steam while a game runs", fp{pid: 300, ppid: 1, comm: "steam", cg: appSlice + "app-steam.scope"}, protCtx{SteamGameRunning: true}},
		{"MT5 under Wine (keep default)", fp{pid: 300, ppid: 1, comm: "terminal64.exe", exe: "/usr/bin/wine64-preloader", args: []string{`C:\Program Files\MetaTrader 5\terminal64.exe`}, cg: appSlice + "app-mt5.scope", env: []string{"WINEPREFIX=/home/shawn/.mt5"}}, protCtx{}},
	}
	for _, k := range cases {
		root := fakeTree(t, k.p)
		r, e := evalAt(t, root, c, noInputs(), 0.2, 24*time.Hour, k.pc)
		if len(r.Candidates) != 0 {
			t.Errorf("%s: protected app became a candidate: %+v", k.name, r.Candidates)
		}
		// And a forced pass (ignores idle + liveness) must still refuse.
		procs := readProcs(root, tuid, false, thome)
		fr := e.Pass(buildGroups(procs), procs, noInputs(), true, 0.2, k.pc, time.Unix(1_900_000_000, 0), true)
		if len(fr.Candidates) != 0 {
			t.Errorf("%s: forced pass reaped a protected app: %+v", k.name, fr.Candidates)
		}
	}
}

func TestExtraClaudeProfilesAreNotProtected(t *testing.T) {
	for _, dir := range []string{"/home/shawn/.config/Claude-glm", "/home/shawn/.config/Claude-local"} {
		root := fakeTree(t, fp{pid: 400, ppid: 1, comm: "claude-desktop", exe: "/usr/lib/claude-desktop/claude-desktop", args: []string{"/usr/bin/claude-desktop", "--user-data-dir=" + dir}, cg: appSlice + "app-claude-x.scope"})
		r, _ := evalAt(t, root, cfg(), noInputs(), 9, 61*time.Minute, protCtx{})
		if candFor(r, "app-claude-x") == nil {
			t.Errorf("%s with no window for 61 min must be reaped", dir)
		}
	}
}

// ───────── leftovers ─────────

func wineOrphans(prefix string, tty int) []fp {
	cg := appSlice + "app-com.anthropic.Claude-19426.scope"
	mk := func(pid int, exe string, extra ...string) fp {
		return fp{pid: pid, ppid: 1, tty: tty, comm: exe, exe: "/usr/bin/wine64-preloader", args: append([]string{`C:\windows\system32\` + exe}, extra...), cg: cg, env: []string{"WINEPREFIX=" + prefix}}
	}
	return []fp{mk(501, "services.exe"), mk(502, "plugplay.exe"), mk(503, "svchost.exe", "-k", "LocalServiceNetworkRestricted"), mk(504, "rpcss.exe"), mk(505, "explorer.exe", "/desktop")}
}

func TestWineWithoutServerIsLeftover(t *testing.T) {
	root := fakeTree(t, wineOrphans("/home/shawn/Games/mw4", 0)...)
	r, _ := evalAt(t, root, cfg(), noInputs(), 9, 1*time.Second, protCtx{})
	if candFor(r, "wine:") != nil {
		t.Error("reaped inside the grace period")
	}
	if !r.PendingLeft {
		t.Error("a pending leftover must ask for a fresh collect")
	}
	r, _ = evalAt(t, root, cfg(), noInputs(), 9, 5*time.Second, protCtx{})
	cd := candFor(r, "wine:/home/shawn/Games/mw4")
	if cd == nil || cd.Rule != "wine-no-server" || len(cd.PIDs) != 5 || cd.Action != "signal" {
		t.Fatalf("want all 5 orphans, got %+v", cd)
	}
	// Plenty of RAM does not matter for a leftover, and neither does a tty.
	root = fakeTree(t, wineOrphans("/home/shawn/Games/mw4", 34817)...)
	if r, _ = evalAt(t, root, cfg(), noInputs(), 15, 5*time.Second, protCtx{}); candFor(r, "wine:") == nil {
		t.Error("a wine process with no wineserver is dead weight even from a terminal")
	}
	// The keep-list still wins.
	c := cfg()
	c.Keep = append(c.Keep, "mw4")
	if r, _ = evalAt(t, root, c, noInputs(), 15, 5*time.Second, protCtx{}); candFor(r, "wine:") != nil {
		t.Error("keep-list must protect even leftovers")
	}
}

func TestWineServicesOnlyMeansWineserverK(t *testing.T) {
	ps := wineOrphans("/tmp/lrtest-wine", 0)
	ps = append(ps, fp{pid: 510, ppid: 1, comm: "wineserver", exe: "/usr/bin/wineserver", args: []string{"/usr/bin/wineserver"}, cg: appSlice + "x.scope", env: []string{"WINEPREFIX=/tmp/lrtest-wine"}, start: 100})
	root := fakeTree(t, ps...)
	r, _ := evalAt(t, root, cfg(), noInputs(), 9, 5*time.Second, protCtx{})
	cd := candFor(r, "wine:/tmp/lrtest-wine")
	if cd == nil || cd.Rule != "wine-no-app" || cd.Action != "wineserver-k" || cd.Server != "/usr/bin/wineserver" {
		t.Fatalf("want wineserver -k, got %+v", cd)
	}
	// With the program still running, it is an app — judged by the idle rule, which a window keeps.
	ps = append(ps, fp{pid: 520, ppid: 510, comm: "mw4.exe", exe: "/usr/bin/wine64-preloader", args: []string{`C:\Games\MW4\mw4.exe`}, cg: appSlice + "x.scope", env: []string{"WINEPREFIX=/tmp/lrtest-wine"}})
	root = fakeTree(t, ps...)
	in := noInputs()
	in.WindowClasses["mw4.exe"] = true // Wine sets WM_CLASS to the exe name; _NET_WM_PID may be 0
	r, _ = evalAt(t, root, cfg(), in, 0.2, 3*time.Hour, protCtx{})
	if candFor(r, "wine:") != nil {
		t.Error("a running game with a window was reaped")
	}
}

func TestBrowserHelpersOutliveMain(t *testing.T) {
	cg := appSlice + "app-google-chrome-700.scope"
	main := fp{pid: 700, ppid: 1, comm: "chrome", exe: "/opt/google/chrome/chrome", args: []string{"/opt/google/chrome/chrome"}, cg: cg}
	helpers := []fp{
		{pid: 701, ppid: 1, comm: "chrome_crashpad", exe: "/opt/google/chrome/chrome_crashpad_handler", cg: cg},
		{pid: 702, ppid: 1, comm: "chrome", exe: "/opt/google/chrome/chrome", args: []string{"/opt/google/chrome/chrome", "--type=gpu-process"}, cg: cg},
	}
	root := fakeTree(t, append([]fp{main}, helpers...)...)
	in := noInputs()
	in.WindowPIDs[700] = true
	if r, _ := evalAt(t, root, cfg(), in, 9, 10*time.Second, protCtx{}); len(r.Candidates) != 0 {
		t.Error("helpers with their main alive were reaped")
	}
	root = fakeTree(t, helpers...)
	r, _ := evalAt(t, root, cfg(), noInputs(), 9, 10*time.Second, protCtx{})
	cd := candFor(r, "chrome")
	if cd == nil || cd.Rule != "browser-helpers" || len(cd.PIDs) != 2 {
		t.Fatalf("want crashpad + gpu-process reaped, got %+v", cd)
	}
}

func TestAppDiedReapsLeftoversWithin10s(t *testing.T) {
	cg := appSlice + "lrtest-app.scope"
	parent := fp{pid: 800, ppid: 1, comm: "bash", cg: cg, start: 100}
	kids := []fp{
		{pid: 801, ppid: 800, comm: "sleep", cg: cg, start: 110},
		{pid: 802, ppid: 800, comm: "sleep", cg: cg, start: 111},
		{pid: 803, ppid: 800, comm: "sleep", cg: cg, start: 112},
		{pid: 804, ppid: 1, comm: "sleep", cg: cg, start: 113}, // double-forked orphan
	}
	root := fakeTree(t, append([]fp{parent}, kids...)...)
	c := cfg()
	e := NewEvaluator(c)
	t0 := time.Unix(1_800_000_000, 0)
	procs := readProcs(root, tuid, false, thome)
	e.Observe(buildGroups(procs), procs, t0)
	if e.States["unit:lrtest-app.scope"].MainPID != 800 {
		t.Fatalf("main should be the oldest top-level process, got %d", e.States["unit:lrtest-app.scope"].MainPID)
	}
	os.RemoveAll(filepath.Join(root, "800")) // parent killed
	for i := range kids {
		kids[i].ppid = 1
		writeProc(t, root, kids[i])
	}
	procs = readProcs(root, tuid, false, thome)
	e.Observe(buildGroups(procs), procs, t0.Add(2*time.Second))
	r := e.Pass(buildGroups(procs), procs, noInputs(), true, 9, protCtx{}, t0.Add(2*time.Second), false)
	if candFor(r, "lrtest-app") != nil || !r.PendingLeft {
		t.Fatal("must wait out the grace, flagged pending")
	}
	r = e.Pass(buildGroups(procs), procs, noInputs(), true, 9, protCtx{}, t0.Add(6*time.Second), false)
	cd := candFor(r, "lrtest-app")
	if cd == nil || cd.Rule != "app-died" || len(cd.PIDs) != 4 {
		t.Fatalf("want all 4 leftovers within 10 s, got %+v", cd)
	}
}

func TestAppDiedKeepsLiveSurvivorAndServicesExcluded(t *testing.T) {
	cg := appSlice + "app-steam-900.scope"
	root := fakeTree(t, fp{pid: 900, ppid: 1, comm: "bash", cg: cg, start: 100}, fp{pid: 901, ppid: 900, comm: "steam", cg: cg, start: 110})
	e := NewEvaluator(cfg())
	t0 := time.Unix(1_800_000_000, 0)
	procs := readProcs(root, tuid, false, thome)
	e.Observe(buildGroups(procs), procs, t0)
	os.RemoveAll(filepath.Join(root, "900")) // launcher script exits, steam keeps going
	procs = readProcs(root, tuid, false, thome)
	e.Observe(buildGroups(procs), procs, t0.Add(2*time.Second))
	in := noInputs()
	in.NetBps[901] = 50 * 1024 // steam is busy
	r := e.Pass(buildGroups(procs), procs, in, true, 9, protCtx{}, t0.Add(6*time.Second), false)
	if len(r.Candidates) != 0 {
		t.Fatal("a launcher exiting must not take a live app with it")
	}
	if e.States["unit:app-steam-900.scope"].MainPID != 901 {
		t.Error("main must be re-elected to the survivor")
	}
	// .service units: systemd already cleans up after a service's main — app-died is scopes only.
	root = fakeTree(t, fp{pid: 950, ppid: 1, comm: "svc", cg: appSlice + "thing.service", start: 100}, fp{pid: 951, ppid: 950, comm: "child", cg: appSlice + "thing.service", start: 110})
	e = NewEvaluator(cfg())
	procs = readProcs(root, tuid, false, thome)
	e.Observe(buildGroups(procs), procs, t0)
	os.RemoveAll(filepath.Join(root, "950"))
	procs = readProcs(root, tuid, false, thome)
	e.Observe(buildGroups(procs), procs, t0.Add(2*time.Second))
	if r := e.Pass(buildGroups(procs), procs, noInputs(), true, 9, protCtx{}, t0.Add(6*time.Second), false); len(r.Candidates) != 0 {
		t.Errorf("app-died must not fire on a .service (Restart= would make it fight systemd): %+v", r.Candidates)
	}
}

func TestMCPOrphans(t *testing.T) {
	cg := appSlice + "app-com.anthropic.Claude-19426.scope"
	mgr := fp{pid: 2, ppid: 1, comm: "systemd", cg: "/user.slice/user-1000.slice/user@1000.service/init.scope"}
	disc := fp{pid: 600, ppid: 2, comm: "disclaimer", args: []string{"/usr/lib/claude-desktop/resources/disclaimer", "--pgroup", "--", "/home/shawn/.mempalace-venv/bin/python3", "-m", "mempalace.mcp_server"}, cg: cg}
	srv := fp{pid: 601, ppid: 600, comm: "python3", args: []string{"/home/shawn/.mempalace-venv/bin/python3", "-m", "mempalace.mcp_server"}, cg: cg}
	root := fakeTree(t, mgr, disc, srv)
	r, _ := evalAt(t, root, cfg(), noInputs(), 9, 5*time.Second, protCtx{})
	cd := candFor(r, "MCP server mempalace")
	if cd == nil || cd.Rule != "mcp-orphan" || len(cd.PIDs) != 2 {
		t.Fatalf("server + its disclaimer wrapper must go: %+v", r.Candidates)
	}
	// Client alive (a non-wrapper parent): kept.
	client := fp{pid: 590, ppid: 2, comm: "claude", cg: cg}
	disc.ppid = 590
	root = fakeTree(t, mgr, client, disc, srv)
	if r, _ = evalAt(t, root, cfg(), noInputs(), 9, 5*time.Second, protCtx{}); candFor(r, "MCP server") != nil {
		t.Error("an MCP server with a live client was reaped")
	}
	// A DECISION 159 broker is never touched.
	broker := fp{pid: 610, ppid: 2, comm: "python3", args: []string{"python3", "/home/shawn/luminos-os/scripts/luminos-mcp-share", "broker", "--", "python3", "-m", "mempalace.mcp_server"}, cg: appSlice + "app-y.scope"}
	child := fp{pid: 611, ppid: 610, comm: "python3", args: []string{"python3", "-m", "mempalace.mcp_server"}, cg: appSlice + "app-y.scope"}
	root = fakeTree(t, mgr, broker, child)
	if r, _ = evalAt(t, root, cfg(), noInputs(), 9, 5*time.Second, protCtx{}); candFor(r, "MCP server") != nil {
		t.Error("the shared broker's server was reaped")
	}
}

// ───────── tmpfs ─────────

func TestTmpfsRules(t *testing.T) {
	dir := t.TempDir()
	c := cfg()
	c.TmpfsMinMB = 1
	mk := func(name string, mb int, age time.Duration) string {
		p := filepath.Join(dir, name)
		if err := os.WriteFile(p, make([]byte, mb<<20), 0644); err != nil {
			t.Fatal(err)
		}
		mt := time.Now().Add(-age)
		os.Chtimes(p, mt, mt)
		return p
	}
	big := mk("mw4.core", 3, 2*time.Hour)
	open := mk("held-open.log", 3, 2*time.Hour)
	mk("small.log", 0, 2*time.Hour)
	mk("young.log", 3, 5*time.Minute)
	// The "open" file is held by a process in the fake /proc (fd symlink).
	root := fakeTree(t, fp{pid: 700, ppid: 1, comm: "tail", cg: appSlice + "a.scope", fds: []string{open}})
	procs := readProcs(root, tuid, true, thome)
	openSet := openPaths(root, procs, []string{dir})
	if !openSet[open] {
		t.Fatalf("open-file scan missed %s", open)
	}
	got := tmpfsCandidates([]string{dir}, os.Getuid(), openSet, time.Now(), c)
	if len(got) != 1 || got[0].Path != big {
		t.Fatalf("want only %s, got %+v", big, got)
	}
	// Mapped (not fd) files count as open too.
	os.WriteFile(filepath.Join(root, "700", "maps"), []byte("7f00-7f10 r--s 00000000 00:1f 42 "+big+"\n"), 0644)
	if o := openPaths(root, procs, []string{dir}); !o[big] {
		t.Error("an mmapped file must count as open")
	}
}

// ───────── parsers ─────────

func TestParsers(t *testing.T) {
	pw := `[{"id":40,"type":"PipeWire:Interface:Client","info":{"props":{"application.process.id":"4242"}}},
	{"id":41,"type":"PipeWire:Interface:Node","info":{"state":"running","props":{"media.class":"Stream/Output/Audio","client.id":40}}},
	{"id":42,"type":"PipeWire:Interface:Node","info":{"state":"idle","props":{"media.class":"Stream/Output/Audio","application.process.id":"77"}}},
	{"id":43,"type":"PipeWire:Interface:Node","info":{"state":"running","props":{"media.class":"Audio/Sink","application.process.id":"88"}}}]`
	a := parsePwDump([]byte(pw))
	if !a[4242] || a[77] || a[88] {
		t.Errorf("audio pids: %v (want only 4242: running stream; idle stream and the sink itself excluded)", a)
	}
	ss := "0      0      127.0.0.1:41234   127.0.0.1:18789 users:((\"node\",pid=55,fd=3))\n\t cubic rto:204 bytes_sent:1000 bytes_acked:1001 bytes_received:500 segs_out:4\n" +
		"0      0      127.0.0.1:18789   127.0.0.1:41234 users:((\"openclaw-gatewa\",pid=66,fd=9))\n\t cubic bytes_sent:500 bytes_received:1000\n"
	socks := parseSS(ss)
	if len(socks) != 2 || socks[0].Bytes != 1500 || socks[0].PIDs[0] != 55 {
		t.Fatalf("ss parse: %+v", socks)
	}
	lst := parseListen("LISTEN 0 511 127.0.0.1:18789 0.0.0.0:* users:((\"openclaw-gatewa\",pid=66,fd=22))\n")
	if !listenWithClient(lst, socks)[66] || listenWithClient(lst, socks)[55] {
		t.Error("listen-with-client must credit the server (66), not the client")
	}
	pids, cls, act, err := parseWindows(`{"windows":[{"pid":10,"cls":"Google-chrome"},{"pid":0,"cls":"mw4.exe"}],"active":10}`)
	if err != nil || !pids[10] || pids[0] || !cls["mw4.exe"] || !cls["google-chrome"] || act != 10 {
		t.Errorf("windows: %v %v %d %v", pids, cls, act, err)
	}
}

// ───────── root side ─────────

func TestVPNSystemDecision(t *testing.T) {
	if in, _ := vpnInUse([]string{"lo", "wlan0", "proton0"}, nil); !in {
		t.Error("proton0 up = in use")
	}
	if in, _ := vpnInUse([]string{"lo", "wlan0"}, []string{"/usr/bin/python3 /usr/bin/protonvpn-app"}); !in {
		t.Error("GUI open = in use")
	}
	if in, _ := vpnInUse([]string{"lo", "wlan0", "tailscale0"}, nil); in {
		t.Error("tailscale0 is not Proton")
	}
	now := time.Now()
	if systemDecision(true, false, now.Add(-30*time.Minute), now, time.Hour) {
		t.Error("stopped before the gradient's time")
	}
	if !systemDecision(true, false, now.Add(-61*time.Minute), now, time.Hour) {
		t.Error("unused daemon past the threshold must be stopped")
	}
	if systemDecision(true, true, now.Add(-5*time.Hour), now, time.Hour) {
		t.Error("never stop a VPN that is in use")
	}
}

func TestProcCacheRevalidatesOnPidReuse(t *testing.T) {
	root := fakeTree(t, fp{pid: 100, ppid: 1, comm: "a", cg: appSlice + "app-a.scope", start: 500})
	pc := newStaticCache()
	if p := readProcsC(root, tuid, thome, pc)[100]; p == nil || p.Unit != "app-a.scope" {
		t.Fatalf("first read: %+v", p)
	}
	// Same pid, new process (different start time) in another unit: the cache must not lie.
	writeProc(t, root, fp{pid: 100, ppid: 1, comm: "b", cg: appSlice + "app-b.scope", start: 900})
	if p := readProcsC(root, tuid, thome, pc)[100]; p == nil || p.Unit != "app-b.scope" {
		t.Fatalf("pid reuse served stale static data: %+v", p)
	}
	// A process moved to another cgroup is seen on a refresh tick.
	writeProc(t, root, fp{pid: 100, ppid: 1, comm: "b", cg: appSlice + "app-c.scope", start: 900})
	pc.refreshCgroup = true
	if p := readProcsC(root, tuid, thome, pc)[100]; p.Unit != "app-c.scope" {
		t.Fatalf("cgroup move missed on refresh: %s", p.Unit)
	}
	os.RemoveAll(filepath.Join(root, "100"))
	readProcsC(root, tuid, thome, pc)
	if len(pc.m) != 0 {
		t.Error("cache must forget exited pids")
	}
}

func TestFastTickSkipsOthersAndCarriesIO(t *testing.T) {
	p := idleApp()
	p.rd = 1000
	root := fakeTree(t, p, fp{pid: 101, ppid: 1, comm: "rootd", cg: "/system.slice/x.service", uid: 1})
	pc := newStaticCache()
	pc.refreshCgroup = true
	full := readProcsC(root, tuid, thome, pc)
	if !full[100].IOValid || full[100].IORead != 1000 || full[101] != nil {
		t.Fatalf("full tick: %+v", full[100])
	}
	pc.refreshCgroup = false
	fast := readProcsC(root, tuid, thome, pc)
	if fast[100] == nil || fast[100].IOValid {
		t.Fatal("fast tick must still see our process, without io")
	}
	// I/O measured across fast ticks must not jump: full(1000) → fast → full(1000 + 60 MiB over 60 s).
	e := NewEvaluator(cfg())
	t0 := time.Unix(1_800_000_000, 0)
	e.Observe(buildGroups(full), full, t0)
	e.Observe(buildGroups(fast), fast, t0.Add(30*time.Second))
	p.rd = 1000 + 60<<20
	writeProc(t, root, p)
	pc.refreshCgroup = true
	full2 := readProcsC(root, tuid, thome, pc)
	e.Observe(buildGroups(full2), full2, t0.Add(60*time.Second))
	r := e.States["unit:app-someapp-100.scope"].rates(t0.Add(60*time.Second), 60)
	if r.ReadBps < 0.9*(1<<20) || r.ReadBps > 1.1*(1<<20) {
		t.Fatalf("read rate %.0f B/s, want ~1 MiB/s", r.ReadBps)
	}
}
