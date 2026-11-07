package main

// [CHANGE: claude-code | 2026-11-07] Descendants/AppUnit/UnitsForApp tests on a fake /proc tree (CONTRACTS §4).

import (
	"math/rand"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"
)

const (
	tfApp     = "0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
	tfSession = "0::/user.slice/user-1000.slice/user@1000.service/session.slice/plasma-kwin_wayland.service"
)

// tfProc writes a fake /proc: <root>/<pid>/cgroup and <root>/<pid>/task/<tid>/children.
type tfProc struct {
	t    *testing.T
	root string
}

func tfNewProc(t *testing.T) *tfProc { return &tfProc{t, t.TempDir()} }

func (p *tfProc) write(rel, data string) {
	path := filepath.Join(p.root, rel)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		p.t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(data), 0o644); err != nil {
		p.t.Fatal(err)
	}
}

// add creates a process whose main thread lists children (kernel format: "101 102 ", no newline).
func (p *tfProc) add(pid int, cgroup string, children ...int) {
	p.write(strconv.Itoa(pid)+"/cgroup", cgroup+"\n")
	p.thread(pid, pid, children...)
}

func (p *tfProc) thread(pid, tid int, children ...int) {
	var b strings.Builder
	for _, c := range children {
		b.WriteString(strconv.Itoa(c) + " ")
	}
	p.write(filepath.Join(strconv.Itoa(pid), "task", strconv.Itoa(tid), "children"), b.String())
}

// tfWithin fails instead of hanging when a walk does not terminate (cycle safety).
func tfWithin(t *testing.T, fn func()) {
	t.Helper()
	done := make(chan struct{})
	go func() { defer close(done); fn() }()
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		t.Fatal("did not finish within 10 s (cycle in the process tree?)")
	}
}

const (
	tfChromeScope = "app-com.google.Chrome-100.scope"
	tfChromeSvc   = "app-com.google.Chrome@a1.service"
)

// tfChrome: window pid in a .scope, renderer/GPU children in an @.service (one in a sub-cgroup),
// a child outside app.slice, a vanished child (listed, no directory) and a cycle back to the root.
func tfChrome(t *testing.T) *tfProc {
	p := tfNewProc(t)
	p.add(100, tfApp+tfChromeScope, 101, 104, 105)
	p.add(101, tfApp+tfChromeSvc, 102)
	p.add(102, tfApp+tfChromeSvc+"/renderer", 103)
	p.add(103, tfApp+tfChromeSvc, 100, 103)
	p.add(104, tfSession)
	return p
}

func tfSet(pids []int) (map[int]bool, bool) {
	s := map[int]bool{}
	for _, p := range pids {
		if s[p] {
			return s, false
		}
		s[p] = true
	}
	return s, true
}

func TestDescendantsChromeTree(t *testing.T) {
	p := tfChrome(t)
	var got []int
	tfWithin(t, func() { got = Descendants(p.root, 100) })
	s, unique := tfSet(got)
	if !unique {
		t.Errorf("Descendants returned duplicates: %v", got)
	}
	for _, want := range []int{100, 101, 102, 103, 104} {
		if !s[want] {
			t.Errorf("Descendants(100) = %v, missing %d", got, want)
		}
	}
	for pid := range s {
		if pid < 100 || pid > 105 {
			t.Errorf("Descendants(100) = %v, unexpected %d", got, pid)
		}
	}
}

func TestDescendantsReadsEveryThread(t *testing.T) {
	p := tfNewProc(t)
	p.add(300, tfApp+"app-x-300.scope", 301)
	p.thread(300, 302, 303) // second thread of 300 forked 303
	p.add(301, tfApp+"app-x-300.scope")
	p.add(303, tfApp+"app-x@y.service")
	got := Descendants(p.root, 300)
	s, _ := tfSet(got)
	if !s[300] || !s[301] || !s[303] || s[302] {
		t.Errorf("Descendants(300) = %v, want 300 301 303 (302 is a thread, not a process)", got)
	}
	if u := UnitsForApp(p.root, 300); !slices.Equal(u, []string{"app-x-300.scope", "app-x@y.service"}) {
		t.Errorf("UnitsForApp(300) = %v", u)
	}
}

func TestAppUnit(t *testing.T) {
	p := tfChrome(t)
	p.add(200, tfApp+`app-google\x2dchrome@abc.service`)
	p.add(201, "0::/system.slice/sshd.service")
	// [CHANGE: claude-code | 2026-11-07] Re-plan 2: plain user services in app.slice are not apps.
	p.add(202, tfApp+"luminos-hive.service")
	p.add(203, tfApp+"claude-cowork.service/qemu")
	p.add(204, tfApp+"luminos-focus.service")
	p.add(205, tfApp+"xdg-desktop-portal.service")
	cases := []struct {
		pid  int
		unit string
		ok   bool
	}{
		{100, tfChromeScope, true},
		{101, tfChromeSvc, true},
		{102, tfChromeSvc, true},                        // sub-cgroup below the unit
		{200, `app-google\x2dchrome@abc.service`, true}, // returned as-is, not unescaped
		{104, "", false},                                // session.slice
		{201, "", false},                                // system service
		{105, "", false},                                // vanished
		{999, "", false},                                // never existed
		{202, "", false},                                // app.slice but no "app-" prefix
		{203, "", false},
		{204, "", false}, // the daemon itself
		{205, "", false},
	}
	for _, c := range cases {
		unit, ok := AppUnit(p.root, c.pid)
		if ok != c.ok || (ok && unit != c.unit) {
			t.Errorf("AppUnit(%d) = %q, %v; want %q, %v", c.pid, unit, ok, c.unit, c.ok)
		}
	}
}

func TestUnitsForApp(t *testing.T) {
	p := tfChrome(t)
	var got []string
	tfWithin(t, func() { got = UnitsForApp(p.root, 100) })
	if want := []string{tfChromeScope, tfChromeSvc}; !slices.Equal(got, want) {
		t.Errorf("UnitsForApp(100) = %v, want %v (scope AND service)", got, want)
	}
	// [CHANGE: claude-code | 2026-11-07] Re-plan 2: a child in a plain user service is never returned.
	p.add(300, tfApp+"app-x-300.scope", 301)
	p.add(301, tfApp+"claude-cowork.service")
	if got := UnitsForApp(p.root, 300); !slices.Equal(got, []string{"app-x-300.scope"}) {
		t.Errorf("UnitsForApp(300) = %v, want only app-x-300.scope", got)
	}
	for _, pid := range []int{104, 105, 999, 0, -1, 301} {
		if got := UnitsForApp(p.root, pid); len(got) != 0 {
			t.Errorf("UnitsForApp(%d) = %v, want none", pid, got)
		}
	}
}

// Random process graphs (shared children, self-loops, cycles, vanished and non-app pids) against a BFS model.
func TestProcmapProperty(t *testing.T) {
	base := t.TempDir()
	cgroups := []string{tfApp + "app-a-1.scope", tfApp + "app-b@x.service", tfApp + "app-b@x.service/sub",
		tfApp + `app-google\x2dchrome@abc.service`, tfSession, tfApp + "luminos-hive.service", ""} // "" = vanished
	iter := 0
	prop := func(seed int64) bool {
		iter++
		r := rand.New(rand.NewSource(seed))
		p := &tfProc{t, filepath.Join(base, strconv.Itoa(iter))}
		n := 2 + r.Intn(18)
		cg := make([]string, n)
		kids := make([][]int, n)
		for i := range n {
			cg[i] = cgroups[r.Intn(len(cgroups))]
			for j := range n {
				if r.Intn(6) == 0 {
					kids[i] = append(kids[i], 1000+j)
				}
			}
		}
		cg[0] = cgroups[r.Intn(len(cgroups)-1)]
		for i := range n {
			if cg[i] == "" {
				continue
			}
			half := len(kids[i]) / 2
			p.add(1000+i, cg[i], kids[i][:half]...)
			p.thread(1000+i, 50000+i, kids[i][half:]...)
		}
		reach := map[int]bool{1000: true}
		units := map[string]bool{}
		for queue := []int{1000}; len(queue) > 0; queue = queue[1:] {
			i := queue[0] - 1000
			if after, ok := strings.CutPrefix(cg[i], tfApp+"app-"); ok { // Re-plan 2: only app-* units
				after = "app-" + after
				units[strings.Split(after, "/")[0]] = true
			}
			for _, k := range kids[i] {
				if !reach[k] && cg[k-1000] != "" {
					reach[k] = true
					queue = append(queue, k)
				}
			}
		}
		got, unique := tfSet(Descendants(p.root, 1000))
		for pid := range reach {
			unique = unique && got[pid]
		}
		for pid := range got {
			unique = unique && pid >= 1000 && pid < 1000+n && (reach[pid] || cg[pid-1000] == "")
		}
		want := make([]string, 0, len(units))
		for u := range units {
			want = append(want, u)
		}
		slices.Sort(want)
		return unique && slices.Equal(UnitsForApp(p.root, 1000), want) // nil and empty compare equal
	}
	tfWithin(t, func() { tfCheck(t, "Descendants/UnitsForApp match a BFS model", prop, 300) })
}
