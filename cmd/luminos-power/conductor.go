// The Conductor — a single per-component power/thermal policy engine (DECISION 24).
//
// The old model moved ONE coarse asusctl profile, so every component shifted to the
// same power level together. The Conductor replaces that with independent *levers*
// (fan, PCIe/GPU-pin, …) driven from a single workload *Intent*, so we can e.g.
// "unlock PCIe but keep the rest normal" instead of dragging everything up at once.
//
// SAFETY: the whole engine is gated OFF by default. Committing, pushing, or
// restarting the daemon does NOT change live cooling. It only takes over the fan
// and PCIe levers when the user deliberately runs the daemon with
// `LUMINOS_CONDUCTOR=1` and watches it. Until then monitorLoop behaves exactly as
// before (asusctl curves + thermal burst), and every guard below short-circuits.
//
// Single-writer discipline: when the Conductor owns the fan, the legacy
// applyAggressiveFanCurve / applyBurstFanCurve calls no-op (see conductorOwnsFan),
// so only ONE code path ever writes the asus_custom_fan_curve hwmon points.
// [CHANGE: claude-code | 2026-06-30] v0 — Conductor policy engine (Phases 1-3).
// [CHANGE: claude-code | 2026-07-01] Phase 4 — intent broadcast + per-tick telemetry.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/luminos-os/luminos/internal/socket"
)

// conductorEnabled gates the entire DECISION 24 engine. Default OFF — see file header.
var conductorEnabled = os.Getenv("LUMINOS_CONDUCTOR") == "1"

// conductor is the live engine instance (nil until main() builds it when enabled).
var conductor *Conductor

// Phase 4 cross-daemon coordination surfaces. [CHANGE: claude-code | 2026-07-01]
const (
	// intentSignalFile is the broadcast Intent, generalising /run/luminos/offload.active
	// into a full posture other daemons can read. Written atomically on intent change.
	intentSignalFile = "/run/luminos/intent.json"
	// ramSocketPath is luminos-ram's control socket (hardcoded there too — config has no
	// RAM field). The Conductor pushes the Intent here so ram reacts in lock-step.
	ramSocketPath = "/run/luminos/ram.sock"
	// telemetryMaxBytes caps the per-tick telemetry log; it rotates to .1 past this size
	// so the always-on corpus can't grow unbounded on disk.
	telemetryMaxBytes = 64 << 20 // 64 MiB
)

// conductorOwnsFan reports whether the Conductor is the single writer of the fan
// hwmon. The legacy curve writers check this and bail so they never fight the PID.
func conductorOwnsFan() bool {
	return conductorEnabled && conductor != nil && conductor.fan != nil && conductor.fan.hwmon != ""
}

// Intent is the per-component power posture the Conductor wants for the CURRENT
// workload. Each lever reads only the fields it owns — that is what decouples the
// components from a single global profile.
type Intent struct {
	Name      string  // workload class: idle/light/media/compute/gaming/training
	FanTarget float64 // fair chassis setpoint °C the CPU/chassis fan PID holds
	GPUTarget float64 // fair GPU setpoint °C the GPU fan PID holds
	PinGPUP0  bool    // pin dGPU to P0 + lock clocks so PCIe can't downtrain mid-job
}

// IntentBroadcast is the cross-daemon wire form of the active Intent (Phase 4). The
// Conductor writes it to intentSignalFile and pushes it to ram+ai on every intent
// change so the whole daemon stack reacts under ONE rule instead of each guessing.
// Swappiness is the ram hint: heavy workloads want less paging of the working set
// (-1 = leave the kernel default). [CHANGE: claude-code | 2026-07-01]
type IntentBroadcast struct {
	Name       string  `json:"name"`
	FanTarget  float64 `json:"fan_target_c"`
	GPUTarget  float64 `json:"gpu_target_c"`
	PinGPUP0   bool    `json:"pin_gpu_p0"`
	Swappiness int     `json:"swappiness"`
	OnAC       bool    `json:"on_ac"`
	Source     string  `json:"source"`
	Timestamp  string  `json:"timestamp"`
}

// telemetryRow is one per-tick training sample: the numeric sensor vector plus the
// action the Conductor took (fair targets, resulting fan duties, pin decision). This
// is the corpus the future NPU policy model (Phase 5) trains on — same .jsonl idea as
// nexus_*.jsonl, but numbers in → action out. [CHANGE: claude-code | 2026-07-01]
type telemetryRow struct {
	T         string  `json:"t"`
	Intent    string  `json:"intent"`
	OnAC      bool    `json:"on_ac"`
	CPUTempC  float64 `json:"cpu_temp_c"`
	GPUTempC  float64 `json:"gpu_temp_c"`
	CPULoad   float64 `json:"cpu_load"`
	DGPULoad  float64 `json:"dgpu_load"`
	IGPULoad  float64 `json:"igpu_load"`
	GPUPowerW float64 `json:"gpu_power_w"`
	FanTarget float64 `json:"fan_target_c"`
	GPUTarget float64 `json:"gpu_target_c"`
	CPUDuty   int     `json:"cpu_duty"`
	GPUDuty   int     `json:"gpu_duty"`
	PinP0     bool    `json:"pin_p0"`
}

// Signals is the sensed state the Conductor classifies on. Filled each tick from
// the very same reads monitorLoop already performs — no extra sysfs traffic.
type Signals struct {
	OnAC      bool
	CPUTempC  float64
	GPUTempC  float64
	CPULoad   float64
	DGPULoad  float64
	IGPULoad  float64
	GPUPowerW float64
}

// Lever is one independently-actuated hardware control. Apply moves it toward the
// Intent (called only on Intent change); Revert hands it back to firmware/default
// management. This interface is the "per-component control under one policy" core.
type Lever interface {
	Name() string
	Apply(in Intent)
	Revert()
}

// --- fan lever (Phase 2: closed-loop PID owns the fan) ---

// fanLever drives the asus_custom_fan_curve hwmon with two PIDs: one for the
// CPU/chassis (also feeds the mid fan) and one for the GPU fan, so a CPU-heavy /
// GPU-light job doesn't needlessly spin the GPU fan and vice-versa.
type fanLever struct {
	cpu   *FanController
	gpu   *FanController
	hwmon string // "" → actuator not found; tick() no-ops and fan stays on firmware

	// last PID outputs, surfaced for the Phase 4 telemetry row (0 when hwmon unbound).
	// [CHANGE: claude-code | 2026-07-01]
	lastCPUDuty int
	lastGPUDuty int
}

func newFanLever() *fanLever {
	hw, err := fanCurveHwmonPath()
	if err != nil {
		lg.Warn("conductor: fan lever disabled — %v (fan stays on asusctl curve)", err)
		return &fanLever{} // empty hwmon → conductorOwnsFan() stays false
	}
	lg.Info("conductor: fan lever bound to %s", hw)
	return &fanLever{cpu: NewFanController(), gpu: NewFanController(), hwmon: hw}
}

func (f *fanLever) Name() string { return "fan" }

// tick runs ONE closed-loop step. It is separate from Apply because the PID needs
// the live temps and dt every loop iteration, not only when the Intent changes.
func (f *fanLever) tick(cpuTempC, gpuTempC, dt float64, in Intent) {
	if f.hwmon == "" {
		return
	}
	cpuDuty := f.cpu.Update(cpuTempC, in.FanTarget, dt)
	gpuDuty := f.gpu.Update(gpuTempC, in.GPUTarget, dt)
	f.lastCPUDuty, f.lastGPUDuty = cpuDuty, gpuDuty
	if err := setAllFansDuty(f.hwmon, cpuDuty, gpuDuty); err != nil {
		lg.Warn("conductor: fan write failed: %v", err)
	}
}

// Apply resets the PID integrators on an Intent change so a stale integral from the
// old fair target doesn't carry over and overshoot the new one.
func (f *fanLever) Apply(in Intent) {
	if f.hwmon == "" {
		return
	}
	f.cpu.Reset()
	f.gpu.Reset()
}

// Revert hands the fan back to the asusctl curve. We don't write here — once the
// Conductor is disabled, monitorLoop's applyAggressiveFanCurve resumes ownership.
func (f *fanLever) Revert() {}

// --- pcie / gpu-pin lever (Phase 1: workload-aware P0 pin) ---

// pcieLever pins the dGPU to P0 for heavy-GPU workloads so DPM=0x02 can't park the
// card and downtrain the PCIe link to Gen1 mid-job. This is the workload-aware fix
// for the training stall: the link was capped on the 180W brick (never battery)
// because the OLD daemon never recognised the training job as GPU-busy, so it never
// pinned P0. We reuse the proven offload P0 mechanism (applyOffloadPin).
type pcieLever struct {
	pinned bool // true only when THIS lever applied the pin (so we revert our own)
}

func (p *pcieLever) Name() string { return "pcie" }

func (p *pcieLever) Apply(in Intent) {
	switch {
	case in.PinGPUP0 && !p.pinned:
		if offloadActive.Load() {
			// A real weight-offload session already holds the P0 pin — don't
			// double-manage it (it will release on offload_stop, not on our Intent).
			lg.Info("conductor: PCIe pin requested but an offload session owns it — deferring")
			return
		}
		applyOffloadPin(true)
		p.pinned = true
		verifyPCIeLinkSpeed("after P0 pin")
	case !in.PinGPUP0 && p.pinned:
		applyOffloadPin(false)
		p.pinned = false
	}
}

func (p *pcieLever) Revert() {
	if p.pinned {
		applyOffloadPin(false)
		p.pinned = false
	}
}

// verifyPCIeLinkSpeed reads back the dGPU's negotiated link state so we can confirm
// the pin actually widened the link (and log it for the telemetry the future NPU
// model will train on). dGPU is 0000:01:00.0 (card1).
func verifyPCIeLinkSpeed(when string) {
	const base = "/sys/bus/pci/devices/0000:01:00.0"
	speed, sErr := os.ReadFile(base + "/current_link_speed")
	width, wErr := os.ReadFile(base + "/current_link_width")
	if sErr != nil || wErr != nil {
		lg.Warn("conductor: PCIe link read-back failed (%v / %v)", sErr, wErr)
		return
	}
	lg.Info("conductor: PCIe link %s — speed=%s width=x%s", when,
		strings.TrimSpace(string(speed)), strings.TrimSpace(string(width)))
}

// --- the Conductor ---

// Conductor is the single policy engine: sense → classify → Intent → drive each
// lever independently. It owns the fan PID and the PCIe/GPU pin.
type Conductor struct {
	fan      *fanLever
	pcie     *pcieLever
	levers   []Lever
	cur      Intent
	lastTick time.Time
}

func NewConductor() *Conductor {
	f := newFanLever()
	p := &pcieLever{}
	return &Conductor{fan: f, pcie: p, levers: []Lever{f, p}}
}

// Tick is called once per monitorLoop iteration when the Conductor is enabled.
// It classifies the live signals, re-issues the Intent to every lever ON CHANGE,
// and runs the fan PID every tick (the PID needs continuous feedback).
func (c *Conductor) Tick(sig Signals) {
	now := time.Now()
	dt := 2.0 // default to the on-AC poll period for the very first tick
	if !c.lastTick.IsZero() {
		dt = now.Sub(c.lastTick).Seconds()
	}
	c.lastTick = now

	in := c.classify(sig)
	if in.Name != c.cur.Name {
		lg.Info("conductor: intent %q → %q (fanTarget=%.0f°C gpuTarget=%.0f°C pinP0=%v cpu=%.0f%% dgpu=%.0f%% igpu=%.0f%%)",
			c.cur.Name, in.Name, in.FanTarget, in.GPUTarget, in.PinGPUP0, sig.CPULoad, sig.DGPULoad, sig.IGPULoad)
		for _, l := range c.levers {
			l.Apply(in)
		}
		c.cur = in
		// Phase 4: only broadcast on change (levers Apply on change too) — ram/ai react
		// in lock-step. Sockets are pushed off the loop so a slow peer can't stall the PID.
		c.broadcast(in, sig)
	}
	c.fan.tick(sig.CPUTempC, sig.GPUTempC, dt, in)
	c.logTelemetry(sig, in) // every tick: the sensor→action corpus for the Phase 5 model
}

// broadcast publishes the active Intent to the rest of the stack (Phase 4). It writes
// intentSignalFile atomically (rename-over so a reader never sees a half-written file)
// and pushes an "intent" message to ram+ai. The file is the durable, pollable copy;
// the socket push is the low-latency nudge. Both are best-effort. [CHANGE: claude-code | 2026-07-01]
func (c *Conductor) broadcast(in Intent, sig Signals) {
	b := IntentBroadcast{
		Name:       in.Name,
		FanTarget:  in.FanTarget,
		GPUTarget:  in.GPUTarget,
		PinGPUP0:   in.PinGPUP0,
		Swappiness: intentSwappinessHint(in.Name),
		OnAC:       sig.OnAC,
		Source:     "luminos-power",
		Timestamp:  time.Now().Format(time.RFC3339),
	}
	payload, err := json.Marshal(b)
	if err != nil {
		lg.Warn("conductor: marshal intent broadcast: %v", err)
		return
	}
	// Atomic write: temp file in the same dir + rename.
	tmp := intentSignalFile + ".tmp"
	if err := os.WriteFile(tmp, append(payload, '\n'), 0644); err != nil {
		lg.Warn("conductor: write %s: %v", tmp, err)
	} else if err := os.Rename(tmp, intentSignalFile); err != nil {
		lg.Warn("conductor: rename intent signal: %v", err)
	}
	// Socket nudge, off-loop so a 3s dial timeout can't stall the fan PID cadence.
	go pushIntent(b)
}

// intentSwappinessHint maps a workload class to the ram swappiness hint. Heavy work
// keeps its working set resident (less paging); everything else leaves the kernel
// default (-1). ram enforces offload>intent precedence. [CHANGE: claude-code | 2026-07-01]
func intentSwappinessHint(class string) int {
	switch class {
	case "gaming", "training", "compute", "heavy":
		return 10
	default:
		return -1
	}
}

// pushIntent dials ram and ai and delivers the Intent. Failures are logged, not fatal —
// the intentSignalFile is the durable fallback any daemon can poll. [CHANGE: claude-code | 2026-07-01]
func pushIntent(b IntentBroadcast) {
	msg, err := socket.NewMessage("intent", "luminos-power", b)
	if err != nil {
		lg.Warn("conductor: build intent msg: %v", err)
		return
	}
	for _, sock := range []string{ramSocketPath, cfg.Sockets.AI} {
		if _, err := socket.Send(sock, msg); err != nil {
			lg.Debug("conductor: intent push to %s failed: %v", sock, err)
		}
	}
}

// logTelemetry appends one training row per tick. Best-effort: telemetry must never
// take down the control loop. Rotates past telemetryMaxBytes. [CHANGE: claude-code | 2026-07-01]
func (c *Conductor) logTelemetry(sig Signals, in Intent) {
	path := cfg.Log.Dir + "/conductor-telemetry.jsonl"
	if fi, err := os.Stat(path); err == nil && fi.Size() > telemetryMaxBytes {
		_ = os.Rename(path, path+".1") // keep one previous generation
	}
	row := telemetryRow{
		T:         time.Now().Format(time.RFC3339),
		Intent:    in.Name,
		OnAC:      sig.OnAC,
		CPUTempC:  sig.CPUTempC,
		GPUTempC:  sig.GPUTempC,
		CPULoad:   sig.CPULoad,
		DGPULoad:  sig.DGPULoad,
		IGPULoad:  sig.IGPULoad,
		GPUPowerW: sig.GPUPowerW,
		FanTarget: in.FanTarget,
		GPUTarget: in.GPUTarget,
		CPUDuty:   c.fan.lastCPUDuty,
		GPUDuty:   c.fan.lastGPUDuty,
		PinP0:     in.PinGPUP0,
	}
	line, err := json.Marshal(row)
	if err != nil {
		return
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	fmt.Fprintf(f, "%s\n", line)
}

// Revert returns every lever to firmware/default management. Called on shutdown so
// we never leave the GPU pinned or the fan on a stale duty after the daemon exits.
// It also clears the broadcast so ram restores its swappiness baseline (Phase 4).
func (c *Conductor) Revert() {
	for _, l := range c.levers {
		l.Revert()
	}
	// Tell the stack we're idle again, then drop the signal file so nothing reads a
	// stale posture after we exit. [CHANGE: claude-code | 2026-07-01]
	pushIntent(IntentBroadcast{Name: "idle", Swappiness: -1, Source: "luminos-power", Timestamp: time.Now().Format(time.RFC3339)})
	if err := os.Remove(intentSignalFile); err != nil && !os.IsNotExist(err) {
		lg.Warn("conductor: remove intent signal on revert: %v", err)
	}
}

// classify is the heuristic workload classifier (Phase 3 seed; Phase 4 expands it
// and broadcasts the Intent to the other daemons). It maps the live signals to a
// workload class, then derives the fair fan targets and the PCIe-pin decision.
//
// The fair-target judgement is "is this temp normal FOR WHAT YOU'RE DOING?": light
// work can hold 47°C, heavy work cannot — so we hold a fair higher ceiling under
// load instead of wasting fan chasing a temp the workload makes physically
// unreachable. fairTargetForWorkload (fan_control.go) owns the chassis numbers.
func (c *Conductor) classify(s Signals) Intent {
	var class string
	pin := false
	switch {
	case s.DGPULoad >= 60 || s.GPUPowerW >= 40:
		// Heavy dGPU: gaming or a training/compute job. Pin P0 so the link stays wide.
		if s.CPULoad >= 50 {
			class = "training" // GPU + CPU both hot → likely a training/compute job
		} else {
			class = "gaming"
		}
		pin = true
	case s.IGPULoad >= 40:
		class = "media" // iGPU decode dominating → 4K video / playback
	case s.CPULoad >= 50:
		class = "compute" // CPU-bound (compile, archive) with the GPU idle
	case s.CPULoad >= 15 || s.DGPULoad >= 10:
		class = "light"
	default:
		class = "idle"
	}
	return Intent{
		Name:      class,
		FanTarget: fairTargetForWorkload(class),
		GPUTarget: gpuFairTarget(class),
		// Only pin on AC: on battery we WANT the dGPU parked (power saving), and the
		// training stall this fixes only ever happened on the 180W brick anyway.
		PinGPUP0: pin && s.OnAC,
	}
}

// gpuFairTarget is the GPU-fan counterpart to fairTargetForWorkload: a fair GPU die
// ceiling per workload class. Under real GPU load 55°C is unreachable, so we hold a
// fair 65°C efficiently rather than maxing the GPU fan against physics.
func gpuFairTarget(class string) float64 {
	switch class {
	case "gaming", "training", "compute", "heavy":
		return 65.0
	default:
		return 55.0
	}
}
