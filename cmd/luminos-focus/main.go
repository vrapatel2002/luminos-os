// Wiring: bus name, one goroutine owning all state, timers only while something needs them.
// [CHANGE: claude-code | 2026-11-07]
package main

import (
	"encoding/json"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/godbus/dbus/v5"
)

const recheck = 15 * time.Second // [CHANGE: claude-code | 2026-11-07] PM, Re-plan 5: 5 s cost 0.42 % of a core

type daemon struct {
	updates            chan string
	states             chan chan string
	g                  *Glider
	globs              []string
	wins               []Win
	trees              map[int]appTree // from the last Update
	audio              map[int]bool
	needAudio, showing bool // showing: KWin's Show Desktop is on
	lastPw, lastUpdate time.Time
}

func main() {
	log.SetFlags(0)
	selfUnit, _ = AppUnit("/proc", os.Getpid())
	conn, err := dbus.ConnectSessionBus()
	if err != nil {
		log.Fatal(err)
	}
	sd := systemd{conn}
	d := &daemon{updates: make(chan string, 16), states: make(chan chan string), g: NewGlider(sd, time.Now)}
	cfg, _ := os.UserConfigDir()
	d.globs = LoadAllow(filepath.Join(cfg, "luminos", "focus-allow.conf"))
	if err := conn.Export(d, "/org/luminos/Focus", "org.luminos.Focus"); err != nil {
		log.Fatal(err)
	}
	reply, err := conn.RequestName("org.luminos.Focus", dbus.NameFlagDoNotQueue)
	if err != nil || reply != dbus.RequestNameReplyPrimaryOwner {
		log.Printf("org.luminos.Focus is taken (%v)", err)
		os.Exit(1)
	}
	sd.resetLeftovers()
	// [CHANGE: claude-code | 2026-11-07] Re-plan 6: Show Desktop is only on the bus; subscribe, then read it once.
	kwin := make(chan *dbus.Signal, 16)
	_ = conn.AddMatchSignal(dbus.WithMatchObjectPath("/KWin"), dbus.WithMatchInterface("org.kde.KWin"),
		dbus.WithMatchMember("showingDesktopChanged"))
	conn.Signal(kwin)
	v, _ := conn.Object("org.kde.KWin", "/KWin").GetProperty("org.kde.KWin.showingDesktop")
	d.showing, d.audio = v.Value() == true, pwDump() // M7: a real audio map before the first plan
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	d.run(sig, kwin)
}

func (d *daemon) Update(s string) *dbus.Error {
	d.updates <- s
	return nil
}

func (d *daemon) State() (string, *dbus.Error) {
	r := make(chan string)
	d.states <- r
	return <-r, nil
}

func (d *daemon) run(sig chan os.Signal, kwin chan *dbus.Signal) {
	fast, slow := time.NewTicker(glideEvery), time.NewTicker(recheck)
	fastOn, slowOn := true, true // the first toggles stop both, long before either could fire
	for {
		toggle(fast, glideEvery, &fastOn, len(d.g.glides) > 0)
		toggle(slow, recheck, &slowOn, d.needAudio || throttles(d.g.applied))
		select {
		case s := <-d.updates:
			d.update(s)
		case s := <-kwin: // also carries bus noise such as NameAcquired
			if s.Name == "org.kde.KWin.showingDesktopChanged" && len(s.Body) == 1 {
				d.showing = s.Body[0] == true
				d.replan(false)
			}
		case r := <-d.states:
			b, _ := json.Marshal(map[string]any{"units": d.g.applied})
			r <- string(b)
		case <-fast.C:
			d.g.Tick()
		case <-slow.C:
			d.check()
		case <-sig:
			d.g.ResetAll()
			os.Exit(0)
		}
	}
}

func (d *daemon) update(s string) {
	var snap struct {
		V       int
		Windows []Win
	}
	if err := json.Unmarshal([]byte(s), &snap); err != nil || snap.V != 1 {
		log.Printf("snapshot ignored (v=%d): %v", snap.V, err)
		return
	}
	d.wins, d.trees, d.lastUpdate = snap.Windows, trees(snap.Windows, "/proc"), time.Now() // the only /proc walk
	d.replan(false)
}

// check (every 15 s while throttled): fail open if KWin went quiet, else re-read PipeWire. No /proc.
func (d *daemon) check() {
	if throttles(d.g.applied) && time.Since(d.lastUpdate) > 60*time.Second {
		log.Print("no snapshot for 60 s: releasing everything")
		d.g.ResetAll()
		d.wins = nil
		return
	}
	d.replan(true)
}

// replan asks PipeWire only when something would be throttled without the audio exemption.
func (d *daemon) replan(fresh bool) {
	wins := d.wins
	if d.showing { // [CHANGE: claude-code | 2026-11-07] Re-plan 6: Show Desktop → nothing visible, nothing focused
		wins = make([]Win, len(d.wins))
		for i, w := range d.wins {
			wins[i].PID = w.PID
		}
	}
	d.needAudio = throttles(planFrom(wins, d.trees, nil, d.globs))
	if d.needAudio && (fresh || time.Since(d.lastPw) >= recheck) {
		d.lastPw = time.Now()
		if a := pwDump(); a != nil { // [CHANGE: claude-code | 2026-11-07] keep the last map on failure
			d.audio = a
		}
	}
	d.g.Apply(planFrom(wins, d.trees, d.audio, d.globs))
}
