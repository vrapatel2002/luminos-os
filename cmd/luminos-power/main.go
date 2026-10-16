// Command luminos-power turns ONE continuous dial — the CPU package power limit (PPT,
// asus-nb-wmi ppt_*) — toward min(demand hand, heat hand, battery/dGPU ceilings) at a
// bounded rate of watts per second. Every decision lives in spectrum.go (pure Step);
// this file is the I/O layer only: config, socket, fixed 1 Hz loop, sensors, writers,
// sd_notify. docs/spectrum/DESIGN.md is the spec of record; CONTRACTS.md is binding.
//
// [CHANGE: claude-code | 2026-10-15] spectrum — v5.0. Deleted: beast mode, quiet idle,
// thermal zones/emergency/burst, GPU TGP manager, Conductor (conductor.go, fan_control.go),
// exec/input watchers, PSI sleep bands, SPI index, RAM bonus, every tick-counter constant,
// every platform_profile / fan-curve / nvidia-smi write at startup and in the loop.
// Kept: socket request/reply shapes, offload_* pin path, report_power, AC side effects
// (Wi-Fi power save, KSM, display Hz), setProfile choke point (unused unless assert_profile).
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"os/user"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/BurntSushi/toml"
	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
)

// PowerState is the status payload (socket `status`, report_power to luminos-ai).
// Every pre-spectrum key is kept; the dial fields are DESIGN §3.10.
// [CHANGE: claude-code | 2026-10-15] spectrum — dial fields added
type PowerState struct {
	OnAC      bool      `json:"on_ac"`
	CPUTempC  float64   `json:"cpu_temp_c"`
	GPULoad   float64   `json:"gpu_load"` // kept for consumers; always 0 (nvidia-smi polling is gone)
	EPP       string    `json:"epp"`
	Profile   string    `json:"profile"`
	UpdatedAt time.Time `json:"updated_at"`

	Level          float64 `json:"level"`
	PptW           int     `json:"ppt_w"`
	PptTargetW     int     `json:"ppt_target_w"`
	PmaxW          float64 `json:"pmax_w"`
	TempTargetC    float64 `json:"temp_target_c"`
	Demand         float64 `json:"demand"`
	Binding        string  `json:"binding"`
	FreqCapKHz     int     `json:"freq_cap_khz"`
	DGPU           string  `json:"dgpu"`
	PPTOwner       string  `json:"ppt_owner"`
	WMIWritesTotal int     `json:"wmi_writes_total"`
	PPTWriteOK     bool    `json:"ppt_write_ok"` // false while the last ppt_* write failed (retried every tick)
}

const (
	wifiIface = "wlp3s0"
	// kscreen output ID for the built-in eDP panel
	displayOutputID = "1"

	// [CHANGE: claude-code | 2026-10-15] spectrum — the dial's files and event sources (DESIGN §3.3, §3.8).
	pptDir           = "/sys/devices/platform/asus-nb-wmi"
	profilePath      = "/sys/firmware/acpi/platform_profile"
	suspendStatsPath = "/sys/power/suspend_stats/success"
	dgpuStatusPath   = "/sys/bus/pci/devices/0000:01:00.0/power/runtime_status"
	powerdInvocation = "/run/systemd/units/invocation:nvidia-powerd.service"
	configFile       = "/etc/luminos/config.toml" // [power] overrides of Params (DESIGN §3.11)
	// offload_start reply shape is frozen (CURRENT.md §5); the TGP manager that used it is gone.
	offloadTGPTargetW = 90.0
	logEvery          = 30 * time.Second
	reportEvery       = 60 * time.Second
	reportLevelDelta  = 0.05
	sideEffectTimeout = 5 * time.Second  // iw / kscreen-doctor must never block the loop
	fanRecheckAfter   = 60 * time.Second // asusd may apply curves after us at boot
	eppRewriteTicks   = 3                // asusd's linked-EPP lands up to a few ticks after a profile change
)

// pptFiles are written in this order with the same value (CONTRACTS.md); each is one WMI call.
var pptFiles = [3]string{"ppt_pl1_spl", "ppt_pl2_sppt", "ppt_fppt"}

// fanCurveV6 is the cpu-fan duty % per EC point (DESIGN §3.5) — verified read-only, never written.
var fanCurveV6 = [8]int{0, 10, 20, 35, 52, 72, 88, 100}

var (
	lg                 *logger.Logger
	cfg                *config.Config
	cpuHardwareMaxFreq int // read from sysfs at startup, kHz

	// /proc/stat snapshots for delta-based CPU load calculation
	lastCPUStatIdle  uint64
	lastCPUStatTotal uint64
	lastCoreIdle     []uint64 // per-core idle snapshot (busiest-core detection)
	lastCoreTotal    []uint64 // per-core total snapshot

	// [CHANGE: claude-code | 2026-06-28] v4.3 — weight-offload session pin (DECISION 23)
	// Set true while the weight-offload inference engine holds a session open; the dial
	// treats it as "dGPU busy" (DESIGN §3.7). Set from the socket goroutine, read by the loop.
	offloadActive atomic.Bool

	// [CHANGE: claude-code | 2026-10-15] spectrum — status snapshot (DESIGN §4): the loop
	// writes it, the socket handler only ever reads it.
	stateMu  sync.RWMutex
	snapshot PowerState

	wmiWrites   int       // successful ppt_* file writes since start (DESIGN §3.9)
	lastPPTWarn time.Time // ppt write failures warn at most once per minute
	notifyConn  *net.UnixConn
	acWant      = make(chan bool, 1) // latest requested AC state for the side-effect worker (coalesced)
)

// dial is the I/O layer's memory around the pure core. One instance, touched only by the
// loop goroutine (startup runs its first tick before the goroutine starts).
// [CHANGE: claude-code | 2026-10-15] spectrum
type dial struct {
	p             Params
	s             State
	assertProfile string // config assert_profile; "" = never write the profile (default)
	tctlPath      string // k10temp temp1_input, resolved by hwmon name
	igpuPath      string // gpu_busy_percent of the DRM card with vendor 0x1002
	socPath       string // BAT*/capacity

	last          time.Time
	profile       string // raw sysfs platform_profile seen last tick
	suspends      string // suspend_stats/success seen last tick
	dgpu          string // runtime_status this tick
	onAC          bool
	extOwner      bool
	pptOK         bool // last ppt_* write succeeded on all three files
	pptLastOK     int  // last value successfully written (status ppt_w)
	eppTicks      int  // remaining forced EPP re-writes after a profile change
	event         bool // something worth a log line happened this tick
	lastLog       time.Time
	lastReport    time.Time
	reportedLevel float64
}

func main() {
	var err error
	cfg, err = config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "luminos-power: config load: %v\n", err)
		os.Exit(1)
	}
	lg, err = logger.New("luminos-power", cfg.Log.Dir+"/power.log", logger.INFO)
	if err != nil {
		lg = logger.NewStdout("luminos-power", logger.INFO)
	}
	cpuHardwareMaxFreq = readCPUHardwareMax()
	lg.Info("CPU hardware max freq: %d kHz (%.2f GHz)", cpuHardwareMaxFreq, float64(cpuHardwareMaxFreq)/1e6)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	l := listen()
	d := newDial()
	lg.Info("luminos-power v5.0 spectrum started — one dial %g–%g W, thi %g C, listening on %s",
		d.p.PminW, d.p.PmaxAcW, d.p.ThiAcC, cfg.Sockets.Power)
	d.startup()

	loopDone := make(chan struct{})
	go func() {
		defer close(loopDone)
		d.run(ctx)
	}()
	socket.Serve(ctx, l, handleMessage)
	<-loopDone
	shutdown()
	os.Remove(cfg.Sockets.Power)
	lg.Info("luminos-power stopped")
}

// listen creates /run/luminos and the power socket, or exits.
func listen() net.Listener {
	if err := os.MkdirAll("/run/luminos", 0755); err != nil {
		lg.Error("create /run/luminos: %v", err)
		os.Exit(1)
	}
	l, err := socket.NewListener(cfg.Sockets.Power)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}
	return l
}

func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "ping":
		return replyOK(msg, map[string]string{"pong": "ok", "daemon": "luminos-power"})
	case "status":
		b, _ := json.Marshal(getSnapshot())
		return socket.Message{
			Type:      "status_response",
			Payload:   json.RawMessage(b),
			Timestamp: time.Now(),
			Source:    "luminos-power",
		}
	// [CHANGE: claude-code | 2026-06-28] v4.3 — weight-offload session pin (DECISION 23, Phase 1).
	// The offload inference engine sends offload_start before streaming weights and
	// offload_stop on teardown. The pin is fully reversible.
	case "offload_start":
		applyOffloadPin(true)
		return replyOK(msg, map[string]interface{}{"offload": "started", "tgp_target_w": offloadTGPTargetW})
	case "offload_stop":
		applyOffloadPin(false)
		return replyOK(msg, map[string]string{"offload": "stopped"})
	case "offload_status":
		return replyOK(msg, map[string]bool{"active": offloadActive.Load()})
	default:
		return replyError(msg, fmt.Sprintf("unknown type: %s", msg.Type))
	}
}

// --- the loop: sense → Step → apply → publish ---
// [CHANGE: claude-code | 2026-10-15] spectrum (DESIGN §3.2, §3.3, §3.8)

// newDial resolves every sensor path once, by name/vendor, never by card or hwmon number.
func newDial() *dial {
	d := &dial{p: DefaultParams(cpuHardwareMaxFreq)}
	d.assertProfile = loadParamOverrides(&d.p)
	if h := hwmonByName("k10temp"); h != "" {
		d.tctlPath = h + "/temp1_input"
	}
	d.igpuPath = igpuBusyPath()
	if bats, _ := filepath.Glob("/sys/class/power_supply/BAT*/capacity"); len(bats) > 0 {
		d.socPath = bats[0]
	}
	d.profile, d.suspends, d.onAC = readTrim(profilePath), readTrim(suspendStatsPath), readACState()
	if d.tctlPath == "" || d.igpuPath == "" {
		lg.Warn("sensor missing (reads 0): tctl=%q igpu=%q — check k10temp hwmon / DRM vendor 0x1002", d.tctlPath, d.igpuPath)
	}
	lg.Info("sensors: tctl=%s (%s) igpu=%s soc=%s profile=%s", d.tctlPath,
		readTrim(filepath.Dir(d.tctlPath)+"/temp1_label"), d.igpuPath, d.socPath, titleCase(d.profile))
	return d
}

// startup is DESIGN §3.8: governor once, AC side effects, one forced tick (writes EPP,
// cap = hwmax and PPT = PminW), read-only fan-curve check, READY=1. No profile write,
// no curve write, no nvidia-smi.
func (d *dial) startup() {
	setAllGovernor("powersave")
	if d.assertProfile != "" { // off by default (DESIGN §3.5, §7 Q10)
		setProfile(d.assertProfile)
	}
	d.tick(time.Now())
	if !checkFanCurve(false) {
		time.AfterFunc(fanRecheckAfter, func() { checkFanCurve(true) })
	}
	sdNotify("READY=1")
	go acWorker()
	requestAC(d.onAC) // side effects run after READY=1, off the loop goroutine
	if cfg.Power.PollIntervalSecs != 1 {
		lg.Info("poll_interval_secs=%d ignored — the tick is fixed at %gs (re-plan ruling)", cfg.Power.PollIntervalSecs, d.p.TickS)
	}
}

// run is the fixed ticker at p.TickS; config poll_interval_secs is ignored (re-plan ruling).
func (d *dial) run(ctx context.Context) {
	t := time.NewTicker(time.Duration(d.p.TickS * float64(time.Second)))
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case now := <-t.C:
			d.tick(now)
			sdNotify("WATCHDOG=1")
		}
	}
}

func (d *dial) tick(now time.Time) {
	in := d.sense(now)
	if in.OnAC != d.onAC {
		d.onAC, d.event = in.OnAC, true
		requestAC(in.OnAC)
	}
	var o Outputs
	d.s, o = Step(d.p, d.s, in)
	d.apply(o)
	d.publish(now, in, o)
}

// sense builds Inputs from the six cheap reads of DESIGN §3.3. Never ppt_* read-back,
// never fan rpm, never nvidia-smi.
func (d *dial) sense(now time.Time) Inputs {
	dt := d.p.TickS
	if !d.last.IsZero() {
		dt = now.Sub(d.last).Seconds() // monotonic
	}
	d.last = now
	avg, maxCore := readCPULoad()
	in := Inputs{DT: dt, UtilAvg: avg / 100, UtilMax: maxCore / 100, SOC: 1,
		TempC: readFloat(d.tctlPath) / 1000, IGPUBusy: readFloat(d.igpuPath) / 100, OnAC: readACState()}
	if !in.OnAC && d.socPath != "" {
		in.SOC = readFloat(d.socPath) / 100
	}
	d.dgpu = readTrim(dgpuStatusPath)
	in.DGPUBusy = d.dgpu == "active" && (offloadActive.Load() || dgpuHasClients())
	_, err := os.Stat(powerdInvocation)
	in.PPTOwnerExternal = err == nil
	in.ProfileChanged, in.Resumed = d.events(readTrim(profilePath), readTrim(suspendStatsPath), dt, in.PPTOwnerExternal)
	return in
}

// events detects profile change, resume and PPT-owner edges, logging each once.
func (d *dial) events(profile, suspends string, dt float64, ext bool) (changed, resumed bool) {
	if profile != d.profile {
		lg.Info("profile changed externally %s → %s — PPT and EPP re-asserted", titleCase(d.profile), titleCase(profile))
		d.profile, changed = profile, true
	}
	switch {
	case suspends != d.suspends:
		lg.Info("resumed (suspend_stats %s→%s, dt=%.0fs) — PPT, EPP and cap re-asserted", d.suspends, suspends, dt)
		d.suspends, resumed = suspends, true
	case dt > 5:
		lg.Warn("loop stalled %.0fs — re-seeded, PPT, EPP and cap re-asserted", dt)
		resumed = true
	}
	if changed {
		d.eppTicks = eppRewriteTicks
	}
	if ext != d.extOwner {
		lg.Info("ppt owner → %s", ownerName(ext))
		d.extOwner = ext
		d.event = true
	}
	d.event = d.event || changed || resumed
	return changed, resumed
}

// apply writes exactly what Outputs says and nothing else (CONTRACTS.md boundary).
// A failed PPT write is retried next tick by invalidating the core's PptWritten (state only;
// spectrum.go is untouched). EPP is re-written for a few ticks after a profile change
// because asusd's platform_profile_linked_epp lands asynchronously (cheap sysfs, no BIOS).
func (d *dial) apply(o Outputs) {
	if o.WritePPT {
		if d.pptOK = writePPT(o.PptW, o.PptW, o.PptW); d.pptOK {
			d.pptLastOK = o.PptW
		} else {
			d.s.PptWritten = -1
		}
	}
	if o.WriteFreq {
		setAllMaxFreq(o.FreqCapKHz)
	}
	if o.WriteEPP {
		setAllEPP(o.EPP)
	} else if d.eppTicks > 0 {
		setAllEPP(o.EPP)
		d.eppTicks--
	}
}

// publish updates the snapshot, logs every 30 s or on an event, and reports to luminos-ai
// on a ≥ 5 % level change or every 60 s (DESIGN §3.10, fixes NEW-5).
func (d *dial) publish(now time.Time, in Inputs, o Outputs) {
	ps := PowerState{OnAC: in.OnAC, CPUTempC: in.TempC, EPP: o.EPP, Profile: titleCase(d.profile), UpdatedAt: now,
		Level: o.Level, PptW: d.pptLastOK, PptTargetW: o.PptW, PPTWriteOK: d.pptOK, PmaxW: o.PmaxW, TempTargetC: o.TargetTempC,
		Demand: o.Demand, Binding: o.Binding, FreqCapKHz: o.FreqCapKHz, DGPU: d.dgpu,
		PPTOwner: ownerName(in.PPTOwnerExternal), WMIWritesTotal: wmiWrites}
	setSnapshot(ps)
	if d.event || now.Sub(d.lastLog) >= logEvery {
		lg.Info("%s", spectrumLine(ps))
		d.lastLog = now
	}
	if d.event || math.Abs(ps.Level-d.reportedLevel) >= reportLevelDelta || now.Sub(d.lastReport) >= reportEvery {
		reportToAI(ps)
		d.lastReport, d.reportedLevel = now, ps.Level
	}
	d.event = false
}

// spectrumLine is the CONTRACTS.md log format; `profile=` keeps the Plasma widget alive.
func spectrumLine(ps PowerState) string {
	ac := 0
	if ps.OnAC {
		ac = 1
	}
	return fmt.Sprintf("spectrum: level=%.0f%% ppt=%dW tgt=%dW pmax=%.0fW temp=%.1fC thi=%.0fC demand=%.2f binding=%s dgpu=%s profile=%s epp=%s ac=%d writes=%d",
		ps.Level*100, ps.PptW, ps.PptTargetW, ps.PmaxW, ps.CPUTempC, ps.TempTargetC, ps.Demand, ps.Binding,
		ps.DGPU, ps.Profile, ps.EPP, ac, ps.WMIWritesTotal)
}

// shutdown is the SIGTERM path (DESIGN §3.8): dial wide open and stock-like, no cap.
// The firmware's own table can only be restored by a profile write (a wake) — left to a human.
func shutdown() {
	writePPT(45, 54, 65)
	setAllMaxFreq(0)
	lg.Info("shutdown: PPT 45/54/65 W, cap → hardware max")
}

// --- writers and systemd ---

// writePPT writes spl, sppt, fppt in that order. Each is ~33 ms of WMI and no dGPU wake
// (HARDWARE.md Q12). Errors warn at most once per minute; successes count into wmi_writes_total.
func writePPT(spl, sppt, fppt int) (ok bool) {
	ok = true
	for i, w := range [3]int{spl, sppt, fppt} {
		if err := writeSysfs(pptDir+"/"+pptFiles[i], strconv.Itoa(w)); err != nil {
			if time.Since(lastPPTWarn) > time.Minute {
				lg.Warn("ppt %s → %dW: %v (retrying every tick)", pptFiles[i], w, err)
				lastPPTWarn = time.Now()
			}
			ok = false
			continue
		}
		wmiWrites++
	}
	return ok
}

// sdNotify sends one state line to $NOTIFY_SOCKET (abstract '@' names supported). No-op outside systemd.
func sdNotify(state string) {
	addr := os.Getenv("NOTIFY_SOCKET")
	if addr == "" {
		return
	}
	if notifyConn == nil {
		if addr[0] == '@' {
			addr = "\x00" + addr[1:]
		}
		c, err := net.DialUnix("unixgram", nil, &net.UnixAddr{Name: addr, Net: "unixgram"})
		if err != nil {
			return
		}
		notifyConn = c
	}
	notifyConn.Write([]byte(state))
}

// checkFanCurve compares the EC's cpu-fan points with v6 (DESIGN §3.5). Read-only — the
// read is driver-cached (HARDWARE.md Q2) and the daemon never writes a curve.
// At boot asusd may apply its curves after us, so the first check only announces a
// re-check; MISMATCH is logged when the second (final) check still differs.
func checkFanCurve(final bool) bool {
	h := hwmonByName("asus_custom_fan_curve")
	if h == "" {
		lg.Warn("fan curve: asus_custom_fan_curve hwmon not found — cannot verify v6")
		return true
	}
	var got [8]int
	ok := true
	for i, pct := range fanCurveV6 {
		got[i] = int(readFloat(fmt.Sprintf("%s/pwm1_auto_point%d_pwm", h, i+1)))
		if abs(got[i]-pct*255/100) > 4 {
			ok = false
		}
	}
	switch {
	case ok:
		lg.Info("fan curve: v6 OK")
	case final:
		lg.Warn("fan curve: MISMATCH (run luminos-fan-curve-install) — pwm1 points %v", got)
	default:
		lg.Info("fan curve: differs from v6 at start (pwm1 points %v) — re-checking in %s", got, fanRecheckAfter)
	}
	return ok
}

func setSnapshot(ps PowerState) {
	stateMu.Lock()
	snapshot = ps
	stateMu.Unlock()
}

func getSnapshot() PowerState {
	stateMu.RLock()
	defer stateMu.RUnlock()
	return snapshot
}

// loadParamOverrides applies the optional [power] keys of DESIGN §3.11 and returns assert_profile.
// Unknown keys are ignored; missing file = defaults. epp_mode/ppt_burst_headroom_w are not in v1 (A4, Q9).
func loadParamOverrides(p *Params) string {
	var raw struct {
		Power map[string]interface{} `toml:"power"`
	}
	if _, err := toml.DecodeFile(configFile, &raw); err != nil {
		raw.Power = nil // absent/unreadable file = defaults (config.Load already rejected a bad parse)
	}
	overrides := countOverrides(raw.Power)
	floats := map[string]*float64{"pmin_w": &p.PminW, "pmax_ac_w": &p.PmaxAcW, "pmax_bat_hi_w": &p.PmaxBatHiW,
		"pmax_bat_lo_w": &p.PmaxBatLoW, "pmax_dgpu_w": &p.PmaxDgpuW, "t_hi_ac_c": &p.ThiAcC, "t_hi_bat_c": &p.ThiBatC,
		"t_hi_dgpu_c": &p.ThiDgpuC, "slew_up_w_s": &p.SlewUpWS, "slew_down_w_s": &p.SlewDownWS, "refresh_s": &p.RefreshS}
	for k, dst := range floats {
		if v, ok := tomlFloat(raw.Power[k]); ok {
			*dst = clampKey(k, v, *dst)
		}
	}
	orderCeilings(p)
	if v, ok := tomlFloat(raw.Power["freq_bat_floor_mhz"]); ok {
		p.FreqBatFloorKHz = int(v * 1000)
	}
	if v, ok := tomlFloat(raw.Power["freq_bat_ceil_mhz"]); ok {
		p.FreqBatCeilKHz = int(v * 1000)
	}
	if s, ok := raw.Power["epp"].(string); ok && s != "" {
		p.EPP = s
	}
	s, _ := raw.Power["assert_profile"].(string)
	if overrides == 0 && *p != DefaultParams(p.HwMaxKHz) {
		lg.Error("params drifted from DefaultParams with no [power] overrides — clamp bug")
	}
	lg.Info("params: pmin=%g pmax ac/bat-hi/bat-lo/dgpu=%g/%g/%g/%g thi ac/bat/dgpu=%g/%g/%g slew up/down=%g/%g refresh=%gs freq bat %d–%d kHz epp=%s assert_profile=%q",
		p.PminW, p.PmaxAcW, p.PmaxBatHiW, p.PmaxBatLoW, p.PmaxDgpuW, p.ThiAcC, p.ThiBatC, p.ThiDgpuC,
		p.SlewUpWS, p.SlewDownWS, p.RefreshS, p.FreqBatFloorKHz, p.FreqBatCeilKHz, p.EPP, s)
	return s
}

// countOverrides counts the Params keys present in [power] (for the defaults-unchanged check).
func countOverrides(m map[string]interface{}) (n int) {
	for _, k := range []string{"pmin_w", "pmax_ac_w", "pmax_bat_hi_w", "pmax_bat_lo_w", "pmax_dgpu_w", "t_hi_ac_c",
		"t_hi_bat_c", "t_hi_dgpu_c", "slew_up_w_s", "slew_down_w_s", "refresh_s", "freq_bat_floor_mhz", "freq_bat_ceil_mhz", "epp"} {
		if _, ok := m[k]; ok {
			n++
		}
	}
	return n
}

// orderCeilings enforces the ceiling invariants (DESIGN §3.4: bat-lo may equal PminW):
// PmaxBatLoW ≥ PminW; PmaxAcW, PmaxBatHiW, PmaxDgpuW ≥ PminW+5; BatLo ≤ BatHi ≤ Ac.
// DefaultParams already satisfies all of them, so with no overrides nothing changes.
func orderCeilings(p *Params) {
	raise := func(name string, v *float64, floor float64) {
		if *v < floor {
			lg.Warn("config %s=%g is below its floor — using %g", name, *v, floor)
			*v = floor
		}
	}
	raise("pmax_bat_lo_w", &p.PmaxBatLoW, p.PminW)
	raise("pmax_ac_w", &p.PmaxAcW, p.PminW+5)
	raise("pmax_bat_hi_w", &p.PmaxBatHiW, p.PminW+5)
	raise("pmax_dgpu_w", &p.PmaxDgpuW, p.PminW+5)
	raise("pmax_bat_hi_w", &p.PmaxBatHiW, p.PmaxBatLoW)
	raise("pmax_ac_w", &p.PmaxAcW, p.PmaxBatHiW)
}

// paramRange is the tested range per config key (HARDWARE.md: PPT tested 15–65 W; DESIGN §3.4).
var paramRange = map[string][2]float64{"pmin_w": {10, 30}, "pmax_ac_w": {15, 65}, "pmax_bat_hi_w": {15, 65},
	"pmax_bat_lo_w": {15, 65}, "pmax_dgpu_w": {15, 65}, "t_hi_ac_c": {60, 92}, "t_hi_bat_c": {60, 92},
	"t_hi_dgpu_c": {60, 92}, "refresh_s": {10, 600}, "slew_up_w_s": {1, 20}, "slew_down_w_s": {1, 20}}

// clampKey rejects a config value outside its tested range (keeps the default, warns).
func clampKey(k string, v, def float64) float64 {
	r := paramRange[k]
	if v < r[0] || v > r[1] || v != v {
		lg.Warn("config %s=%g outside tested range [%g, %g] — keeping %g", k, v, r[0], r[1], def)
		return def
	}
	return v
}

func tomlFloat(v interface{}) (float64, bool) {
	switch x := v.(type) {
	case int64:
		return float64(x), true
	case float64:
		return x, true
	}
	return 0, false
}

// --- small readers and resolvers ---

func readTrim(path string) string {
	d, _ := os.ReadFile(path)
	return strings.TrimSpace(string(d))
}

func readFloat(path string) float64 {
	v, _ := strconv.ParseFloat(readTrim(path), 64)
	return v
}

// hwmonByName returns the hwmon directory whose name file matches, or "".
func hwmonByName(name string) string {
	names, _ := filepath.Glob("/sys/class/hwmon/hwmon*/name")
	for _, n := range names {
		if readTrim(n) == name {
			return filepath.Dir(n)
		}
	}
	return ""
}

// igpuBusyPath finds gpu_busy_percent on the DRM card whose device vendor is AMD (0x1002).
func igpuBusyPath() string {
	vendors, _ := filepath.Glob("/sys/class/drm/card[0-9]/device/vendor")
	for _, v := range vendors {
		p := filepath.Dir(v) + "/gpu_busy_percent"
		if _, err := os.Stat(p); err == nil && readTrim(v) == "0x1002" {
			return p
		}
	}
	return ""
}

// titleCase renders the sysfs profile as the Quiet/Balanced/Performance the status always showed.
func titleCase(s string) string {
	if s == "" {
		return "unknown"
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

func ownerName(external bool) string {
	if external {
		return "nvidia-powerd"
	}
	return "luminos-power"
}

// applyACTransition applies the NON-power AC side effects, unchanged from v4.x, at startup
// and on every plug/unplug. The profile/EPP/cap writes that used to live here are gone:
// the dial's ceilings blend on AC change (DESIGN §3.4) and the daemon never writes
// platform_profile (§3.5). Governor is set once at startup.
// It runs on the acWorker goroutine only (never the loop): iw and kscreen-doctor fork and
// can hang, so each has a 5 s timeout, and requests are coalesced to the latest state.
// [CHANGE: claude-code | 2026-10-15] spectrum
func applyACTransition(onAC bool) {
	if onAC {
		lg.Info("AC plugged — applying AC side effects")
		setWiFiPowerSave(false)
		setKSM(true)
		setDisplayHz(120)
		return
	}
	lg.Info("AC unplugged — applying battery side effects")
	setWiFiPowerSave(true)
	setKSM(false)
	setDisplayHz(60)
}

// requestAC hands the latest AC state to acWorker, replacing any not-yet-applied one.
func requestAC(onAC bool) {
	select {
	case <-acWant: // drop the stale request
	default:
	}
	acWant <- onAC
}

// acWorker applies AC side effects one at a time, in order, off the loop goroutine.
func acWorker() {
	for onAC := range acWant {
		applyACTransition(onAC)
	}
}

// runCmdTimeout is runCmd with a deadline, for the AC side-effect commands.
func runCmdTimeout(d time.Duration, name string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), d)
	defer cancel()
	out, err := exec.CommandContext(ctx, name, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s %v: %w\noutput: %s", name, args, err, strings.TrimSpace(string(out)))
	}
	return nil
}

// [CHANGE: claude-code | 2026-09-15] BUG-161 follow-up: every profile write goes
// through here now, instead of seven scattered runCmd("asusctl", "profile", "set", …)
// calls that each decided on their own.
//
// Two reasons. First, a write that changes nothing is not free: asusd still writes the
// ASUS platform profile, the firmware still answers with an ACPI NVPCF notify, and the
// nvidia driver still resumes the dGPU out of D3cold to hear it. The emergency-thermal
// branch re-sent "Quiet" on every 2s tick for as long as the machine was hot, which
// would have pinned the card awake for the whole overheat. Nobody noticed because until
// 2026-09-14 the dGPU never slept at all, so there was never anything to wake.
//
// Second, the truth lives in sysfs, not in our own prevState — that struct is restored
// from a file across restarts and can disagree with the hardware. We compare against
// /sys/firmware/acpi/platform_profile, which is what the firmware actually thinks.
//
// Deliberately NOT a rate limiter. Skipping a profile change the thermal code asked for
// could leave the laptop cooking in the wrong profile with no retry, since every caller
// `continue`s straight after. Hysteresis is what stops oscillation (see quietExit*);
// this only stops pointless repeats.
func setProfile(name string) {
	if cur, err := os.ReadFile("/sys/firmware/acpi/platform_profile"); err == nil {
		if strings.EqualFold(strings.TrimSpace(string(cur)), name) {
			return
		}
	}
	runCmd("asusctl", "profile", "set", name)
	noteProfileChange()
}

// noteProfileChange makes a flap visible in the log while it is happening. BUG-161 sat
// here for almost four months precisely because nothing counted: each switch looked
// reasonable on its own line, and only the *rate* was wrong. Four changes in ten minutes
// on an idle desktop is not tuning, it is oscillation, and each one wakes the dGPU.
func noteProfileChange() {
	now := time.Now()
	kept := recentProfileChanges[:0]
	for _, t := range recentProfileChanges {
		if now.Sub(t) < 10*time.Minute {
			kept = append(kept, t)
		}
	}
	recentProfileChanges = append(kept, now)
	if len(recentProfileChanges) > 4 {
		lg.Warn("profile flapping: %d changes in 10min — each one wakes the dGPU via ACPI NVPCF (BUG-161)",
			len(recentProfileChanges))
	}
}

var recentProfileChanges []time.Time

// --- sysfs writers ---

func setAllGovernor(gov string) {
	matches, _ := filepath.Glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
	var failed int
	for _, p := range matches {
		if err := writeSysfs(p, gov); err != nil {
			failed++
		}
	}
	if failed > 0 {
		lg.Warn("governor → %s: %d/%d cores failed", gov, failed, len(matches))
	} else {
		lg.Info("governor → %s (%d cores)", gov, len(matches))
	}
}

func setAllEPP(epp string) {
	matches, _ := filepath.Glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference")
	var failed int
	for _, p := range matches {
		if err := writeSysfs(p, epp); err != nil {
			failed++
		}
	}
	if failed > 0 {
		lg.Warn("EPP → %s: %d/%d cores failed", epp, failed, len(matches))
	} else {
		lg.Info("EPP → %s (%d cores)", epp, len(matches))
	}
}

// setAllMaxFreq sets scaling_max_freq on all CPU cores.
// freqKHz=0 restores the hardware maximum (no cap).
func setAllMaxFreq(freqKHz int) {
	target := freqKHz
	if target == 0 {
		target = cpuHardwareMaxFreq
	}
	matches, _ := filepath.Glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq")
	var failed int
	for _, p := range matches {
		if err := writeSysfs(p, strconv.Itoa(target)); err != nil {
			failed++
		}
	}
	capGHz := float64(target) / 1e6
	if failed > 0 {
		lg.Warn("max_freq → %.1f GHz: %d/%d cores failed", capGHz, failed, len(matches))
	} else {
		lg.Info("max_freq → %.1f GHz (%d cores)", capGHz, len(matches))
	}
}

// readCPUHardwareMax returns the hardware max frequency of cpu0 in kHz.
// Falls back to 5137904 (Ryzen 9 8845HS spec) if unreadable.
func readCPUHardwareMax() int {
	d, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
	if err != nil {
		return 5137904
	}
	v, err := strconv.Atoi(strings.TrimSpace(string(d)))
	if err != nil || v <= 0 {
		return 5137904
	}
	return v
}

// writeSysfs writes a value to a sysfs file using O_WRONLY (no truncate/create flags).
// Sysfs files need a trailing newline for the kernel to accept the value.
func writeSysfs(path, value string) error {
	f, err := os.OpenFile(path, os.O_WRONLY, 0)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = fmt.Fprintf(f, "%s\n", value)
	return err
}

func setWiFiPowerSave(enable bool) {
	val := "off"
	if enable {
		val = "on"
	}
	if err := runCmdTimeout(sideEffectTimeout, "/usr/bin/iw", "dev", wifiIface, "set", "power_save", val); err != nil {
		lg.Warn("WiFi power_save %s: %v", val, err)
	} else {
		lg.Info("WiFi power_save → %s", val)
	}
}

func setKSM(enable bool) {
	val := "1"
	if !enable {
		val = "0"
	}
	if err := writeSysfs("/sys/kernel/mm/ksm/run", val); err != nil {
		lg.Warn("KSM run=%s: %v", val, err)
	} else {
		lg.Info("KSM → %s", val)
	}
}

func setDisplayHz(hz int) {
	mode := fmt.Sprintf("2880x1800@%d", hz)
	arg := fmt.Sprintf("output.%s.mode.%s", displayOutputID, mode)
	// kscreen-doctor requires a running Wayland session — run as the display user
	uid, wayland, dbus := findSessionEnv()
	if uid == "" {
		lg.Warn("setDisplayHz: no active user session found")
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), sideEffectTimeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, "runuser", "-u", uid, "--",
		"env",
		"WAYLAND_DISPLAY="+wayland,
		"DBUS_SESSION_BUS_ADDRESS="+dbus,
		"kscreen-doctor", arg,
	)
	if out, err := cmd.CombinedOutput(); err != nil {
		lg.Warn("kscreen-doctor %s: %v — %s", mode, err, strings.TrimSpace(string(out)))
	} else {
		lg.Info("display → %s", mode)
	}
}

// findSessionEnv returns (username, WAYLAND_DISPLAY, DBUS_SESSION_BUS_ADDRESS)
// for the first active graphical session found in /run/user/*/wayland-*.
func findSessionEnv() (username, wayland, dbus string) {
	sockets, _ := filepath.Glob("/run/user/*/wayland-[0-9]")
	if len(sockets) == 0 {
		return
	}
	// e.g. /run/user/1000/wayland-0 → uid dir = /run/user/1000
	uidDir := filepath.Dir(sockets[0])
	uid := filepath.Base(uidDir) // "1000"
	// Look up username from /etc/passwd
	if d, err := os.ReadFile("/etc/passwd"); err == nil {
		for _, line := range strings.Split(string(d), "\n") {
			fields := strings.Split(line, ":")
			if len(fields) >= 4 && fields[2] == uid {
				username = fields[0]
				break
			}
		}
	}
	if username == "" {
		username = uid // fall back to numeric uid
	}
	wayland = filepath.Base(sockets[0]) // e.g. "wayland-0"
	dbus = "unix:path=" + uidDir + "/bus"
	return
}

// --- sensors ---

func readACState() bool {
	entries, _ := filepath.Glob("/sys/class/power_supply/*/type")
	for _, p := range entries {
		d, _ := os.ReadFile(p)
		if strings.TrimSpace(string(d)) == "Mains" {
			on, _ := os.ReadFile(filepath.Join(filepath.Dir(p), "online"))
			return strings.TrimSpace(string(on)) == "1"
		}
	}
	return true
}

// dgpuHasClients reports whether any process holds an NVIDIA device node open — a game
// under PRIME offload, a CUDA job, anything. It is a /proc walk: it never contacts the
// card, which is the whole point. nvidia-smi cannot answer this question because asking
// it wakes the GPU, and a 2s poll then keeps the autosuspend timer from ever expiring.
// Called only while the card is already awake, so the walk stops early in the case that
// matters (something IS using the GPU) and the exhaustive case costs a few ms on an
// otherwise idle machine.
// [CHANGE: claude-code | 2026-09-14] BUG-160
func dgpuHasClients() bool {
	procs, err := os.ReadDir("/proc")
	if err != nil {
		return true // can't tell — assume in use rather than stop managing a live GPU
	}
	for _, p := range procs {
		fdDir := "/proc/" + p.Name() + "/fd"
		fds, err := os.ReadDir(fdDir)
		if err != nil {
			continue // not a pid, or exited mid-walk
		}
		for _, fd := range fds {
			if target, err := os.Readlink(fdDir + "/" + fd.Name()); err == nil &&
				strings.HasPrefix(target, "/dev/nvidia") {
				return true
			}
		}
	}
	return false
}

// readCPULoad returns system-wide average utilisation and the busiest single-core
// utilisation (both 0-100), from /proc/stat deltas.
// maxCore is the value a frequency ceiling must respect: scaling_max_freq caps every
// core's peak clock, so one pinned core (7-zip, Wine, compiler) needs the ceiling
// raised even when the 16-core average is near idle.
// First call returns (0, 0) — no previous snapshot to diff against.
// [CHANGE: claude-code | 2026-05-31] ROOT-BUG fix: cap driven by busiest core, not avg
func readCPULoad() (avg, maxCore float64) {
	data, err := os.ReadFile("/proc/stat")
	if err != nil {
		return 0, 0
	}
	lines := strings.Split(string(data), "\n")

	parse := func(fields []string) (idle, total uint64) {
		var vals [10]uint64
		for i, f := range fields[1:] {
			if i >= 10 {
				break
			}
			vals[i], _ = strconv.ParseUint(f, 10, 64)
		}
		idle = vals[3] + vals[4] // idle + iowait
		for _, v := range vals {
			total += v
		}
		return
	}

	// Aggregate line (first): "cpu user nice system idle iowait ..."
	agg := strings.Fields(lines[0])
	if len(agg) < 5 || agg[0] != "cpu" {
		return 0, 0
	}
	aggIdle, aggTotal := parse(agg)

	// Per-core lines: cpu0, cpu1, ... (contiguous block after the aggregate line)
	type coreSample struct{ idle, total uint64 }
	var cores []coreSample
	for _, ln := range lines[1:] {
		if !strings.HasPrefix(ln, "cpu") {
			break
		}
		i, t := parse(strings.Fields(ln))
		cores = append(cores, coreSample{i, t})
	}

	// Seed on first call or core-count change — return (0,0), no delta yet.
	if lastCPUStatTotal == 0 || len(lastCoreTotal) != len(cores) {
		lastCPUStatIdle, lastCPUStatTotal = aggIdle, aggTotal
		lastCoreIdle = make([]uint64, len(cores))
		lastCoreTotal = make([]uint64, len(cores))
		for i, c := range cores {
			lastCoreIdle[i], lastCoreTotal[i] = c.idle, c.total
		}
		return 0, 0
	}

	// Aggregate delta → system-wide average
	if dT := aggTotal - lastCPUStatTotal; dT > 0 {
		avg = float64(dT-(aggIdle-lastCPUStatIdle)) / float64(dT) * 100.0
	}
	lastCPUStatIdle, lastCPUStatTotal = aggIdle, aggTotal

	// Per-core deltas → find busiest core
	for i, c := range cores {
		dT := c.total - lastCoreTotal[i]
		dI := c.idle - lastCoreIdle[i]
		lastCoreIdle[i], lastCoreTotal[i] = c.idle, c.total
		if dT == 0 {
			continue
		}
		if u := float64(dT-dI) / float64(dT) * 100.0; u > maxCore {
			maxCore = u
		}
	}
	return avg, maxCore
}

// abs returns the absolute value of an int.
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// --- dGPU control (offload_* only — never called by the loop or at startup) ---

// unprivUID is the uid that read-only nvidia-smi polls are dropped to. 65534 = nobody.
// It only needs to be some uid that is not root; all of the access comes from the gid.
const unprivUID = 65534

var (
	dgpuGIDOnce sync.Once
	dgpuGIDVal  int
)

// dgpuGID resolves the numeric gid of the 'dgpu' group once, or -1 if it does not exist.
// Looked up by name rather than hardcoded: the gid happens to be 948 on this machine but
// nothing guarantees that on a rebuild.
// [CHANGE: claude-code | 2026-08-29] BUG-146
func dgpuGID() int {
	dgpuGIDOnce.Do(func() {
		dgpuGIDVal = -1
		g, err := user.LookupGroup("dgpu")
		if err != nil {
			lg.Warn("dgpu group not found (%v) — nvidia-smi polls will run as root and "+
				"will re-open the UVM nodes (BUG-146)", err)
			return
		}
		n, err := strconv.Atoi(g.Gid)
		if err != nil {
			lg.Warn("dgpu group gid %q is not numeric: %v", g.Gid, err)
			return
		}
		dgpuGIDVal = n
	})
	return dgpuGIDVal
}

// nvidiaQuery runs a READ-ONLY `nvidia-smi --query-gpu=` with root dropped: uid nobody,
// gid dgpu. Use it for every poll; use plain runCmd for the control calls that genuinely
// need root (-pl, -pm, --lock-gpu-clocks, --reset-gpu-clocks).
//
// WHY THIS EXISTS — BUG-146, and the reason is NOT the obvious one.
// [CHANGE: claude-code | 2026-08-29]
//
// This daemon was re-opening /dev/nvidia-uvm{,-tools} to 0666 root:root every time it
// polled the card, silently undoing DECISION 25 for as long as the dGPU was awake. The
// recorded cause was "luminos-power runs as root". That was WRONG, and dropping privileges
// alone does NOT fix it. Measured truth table, 2026-08-29:
//
//	caller     nvidia-modprobe setuid   gate holds?
//	non-root   yes                      NO
//	non-root   no                       YES
//	root       yes                      NO
//	root       no                       NO
//
// The agent re-applying the driver's hardcoded device-file defaults is the SETUID-ROOT
// helper /usr/bin/nvidia-modprobe, which any nvidia-smi invocation may call — not the
// privilege level of the caller. So the fix is a PAIR, and this function is only half of
// it; the other half is stripping the setuid bit from nvidia-modprobe (see the pacman hook
// at pacman-hooks/luminos-nvidia-modprobe-setuid.hook, which re-strips it after upgrades).
// Neither half works alone. Verified with both applied: 10 polls over 30 s returned real
// data while /dev/nvidia-uvm held 0660 root:dgpu throughout.
//
// The gid is what grants access — DECISION 25 makes the nodes root:dgpu 0660 — so this
// drops to a NON-root uid while ADDING the dgpu group, exactly as dgpu-exec-v2 does.
func nvidiaQuery(query string) ([]byte, error) {
	return nvidiaRead("--query-gpu="+query, "--format=csv,noheader,nounits")
}

// nvidiaRead runs an arbitrary READ-ONLY nvidia-smi with the same privilege drop as
// nvidiaQuery. Every read that is not a --query-gpu must come through here rather than a
// bare exec.Command: per the BUG-146 truth table above, a ROOT nvidia-smi re-applies the
// driver's 0666 root:root device-file defaults by itself, with no setuid helper involved,
// so a "harmless read-only query" run as root still tears open the DECISION 25 gate.
// [CHANGE: claude-code | 2026-09-13]
func nvidiaRead(args ...string) ([]byte, error) {
	cmd := exec.Command("nvidia-smi", args...)
	if gid := dgpuGID(); gid >= 0 && os.Geteuid() == 0 {
		cmd.SysProcAttr = &syscall.SysProcAttr{
			Credential: &syscall.Credential{
				Uid:    unprivUID,
				Gid:    uint32(gid),
				Groups: []uint32{uint32(gid)},
			},
		}
	}
	return cmd.Output()
}

// uvmNodes are the two device nodes the nvidia module's NVreg_DeviceFile* parameters do
// not cover, so they are the only part of the DECISION 25 gate that has to be maintained
// from userspace. See scripts/dgpu-gate/luminos-uvm-gate.sh (BUG-146).
var uvmNodes = []string{"/dev/nvidia-uvm", "/dev/nvidia-uvm-tools"}

// regateUVM re-applies root:dgpu 0660 to the UVM nodes.
// [CHANGE: claude-code | 2026-08-29] BUG-146
//
// WHY A POLL-SIDE FIX WAS NOT ENOUGH.
// nvidiaQuery drops root, and with nvidia-modprobe's setuid bit stripped that keeps the
// gate intact across the periodic polls — which is nearly every nvidia-smi call this daemon
// makes. But four calls CANNOT drop root, because they change hardware state: -pm, -pl,
// --lock-gpu-clocks, --reset-gpu-clocks. Measured 2026-08-29, with setuid already stripped:
// a single root `nvidia-smi -pl 55` still reset both nodes to 0666 root:root. Root does not
// need the setuid helper; it re-applies the driver defaults itself.
//
// So those four calls are an irreducible hole, and the honest fix is to close it
// immediately after rather than pretend it is not there. The nodes are open for the
// duration of one nvidia-smi invocation (~200 ms), a handful of times per session, instead
// of continuously for as long as the card is awake.
//
// This does NOT shell out to luminos-uvm-gate: that script's job is boot-time creation and
// it exits non-zero when it finds a node already open, which is the normal case here and
// would log a false alarm every time. This only repairs ownership on nodes that exist.
func regateUVM() {
	gid := dgpuGID()
	if gid < 0 || os.Geteuid() != 0 {
		return
	}
	for _, n := range uvmNodes {
		if _, err := os.Stat(n); err != nil {
			continue // module not loaded yet; the boot unit owns creation, not us
		}
		if err := os.Chown(n, 0, gid); err != nil {
			lg.Warn("BUG-146: chown %s root:dgpu failed: %v — node left world-open", n, err)
			continue
		}
		if err := os.Chmod(n, 0o660); err != nil {
			lg.Warn("BUG-146: chmod %s 0660 failed: %v — node left world-open", n, err)
		}
	}
}

// nvidiaCtl runs a root nvidia-smi CONTROL call and re-closes the UVM gate behind it.
// Every root nvidia-smi invocation must go through here, not runCmd, or BUG-146 reopens.
// [CHANGE: claude-code | 2026-08-29]
func nvidiaCtl(args ...string) error {
	err := runCmd("nvidia-smi", args...)
	regateUVM()
	return err
}

// offloadSignalFile is the shared cross-daemon signal for an active weight-offload
// session (DECISION 23). luminos-power writes it on offload_start and removes it on
// offload_stop; luminos-ram (Phase 2) reads it to know when to exempt the pinned
// weight region from MADV_PAGEOUT/zram. Contents are advisory (writer + timestamp).
const offloadSignalFile = "/run/luminos/offload.active"

// readGPUMaxGraphicsClock returns the dGPU's max graphics clock in MHz (0 if unknown).
// [CHANGE: claude-code | 2026-06-28] v4.3
func readGPUMaxGraphicsClock() int {
	out, err := nvidiaQuery("clocks.max.graphics")
	if err != nil {
		return 0
	}
	v, err := strconv.Atoi(strings.TrimSpace(string(out)))
	if err != nil {
		return 0
	}
	return v
}

// applyOffloadPin starts/stops a weight-offload GPU performance pin (Phase 1, DECISION 23).
//
// On start it:
//   - enables persistence mode so the driver/CUDA context stays resident between calls,
//   - locks the GPU graphics clock to its max so the sub-millisecond gaps between streamed
//     layers can't trigger a P-state downclock mid-token,
//   - flips offloadActive so the dial counts the dGPU as busy (DESIGN §3.7).
//
// The PCIe link is deliberately NOT pinned: Phase 0 measurement proved it holds Gen4 x8
// under sustained streaming on its own (DPM Gen1 is an idle-only state), so the link
// self-manages and only the GPU core clocks needed an explicit pin.
//
// On stop it reverses everything: clears the flag,
// resets the GPU clocks, and removes the shared signal file. Requires root (nvidia-smi).
// [CHANGE: claude-code | 2026-06-28] v4.3
func applyOffloadPin(on bool) {
	if on {
		if err := nvidiaCtl("-pm", "1"); err != nil {
			lg.Warn("offload: persistence mode on failed: %v", err)
		}
		if maxClk := readGPUMaxGraphicsClock(); maxClk > 0 {
			if err := nvidiaCtl(fmt.Sprintf("--lock-gpu-clocks=%d", maxClk)); err != nil {
				lg.Warn("offload: lock GPU clocks to %d MHz failed: %v", maxClk, err)
			} else {
				lg.Info("offload: GPU graphics clock locked to %d MHz", maxClk)
			}
		} else {
			lg.Warn("offload: could not read max graphics clock — clocks left unlocked")
		}
		offloadActive.Store(true)
		marker := fmt.Sprintf("power pid=%d started=%s\n", os.Getpid(), time.Now().Format(time.RFC3339))
		if err := os.WriteFile(offloadSignalFile, []byte(marker), 0644); err != nil {
			lg.Warn("offload: write signal file %s: %v", offloadSignalFile, err)
		}
		lg.Info("offload session START — dGPU pinned for weight streaming (dial treats dGPU as busy)") // [CHANGE: claude-code | 2026-10-15] spectrum
		return
	}
	offloadActive.Store(false)
	if err := nvidiaCtl("--reset-gpu-clocks"); err != nil {
		lg.Warn("offload: reset GPU clocks failed: %v", err)
	}
	if err := os.Remove(offloadSignalFile); err != nil && !os.IsNotExist(err) {
		lg.Warn("offload: remove signal file: %v", err)
	}
	lg.Info("offload session STOP — GPU clocks reset") // [CHANGE: claude-code | 2026-10-15] spectrum
}

func runCmd(name string, args ...string) error {
	out, err := exec.Command(name, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s %v: %w\noutput: %s", name, args, err, strings.TrimSpace(string(out)))
	}
	return nil
}

// reportToAI sends the snapshot to luminos-ai (report_power); luminos-ai serves it under "power".
func reportToAI(ps PowerState) {
	msg, _ := socket.NewMessage("report_power", "luminos-power", ps)
	socket.Send(cfg.Sockets.AI, msg)
}

func replyOK(req socket.Message, payload interface{}) socket.Message {
	b, _ := json.Marshal(payload)
	return socket.Message{Type: req.Type + "_response", Payload: json.RawMessage(b), Timestamp: time.Now(), Source: "luminos-power"}
}

func replyError(req socket.Message, errMsg string) socket.Message {
	b, _ := json.Marshal(map[string]string{"error": errMsg})
	return socket.Message{Type: "error", Payload: json.RawMessage(b), Timestamp: time.Now(), Source: "luminos-power"}
}
