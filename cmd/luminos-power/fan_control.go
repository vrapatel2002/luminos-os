// Closed-loop PID fan controller for the Conductor (DECISION 24, Phase 2).
//
// Replaces the open-loop "hand a static curve to the EC and walk away" approach
// (applyAggressiveFanCurve) with a real feedback controller that holds a
// workload-dependent target temperature using the *least* fan it can.
//
// Actuator (decided by the Phase 0 hardware probe, 2026-06-30):
//   The ASUS EC exposes a writable 8-point fan curve per fan via the
//   `asus_custom_fan_curve` hwmon (root-writable, temp in °C, pwm in 0-255).
//   To get direct PWM authority we write a curve that is FLAT at our target duty
//   across the normal band, but always ramps to 100% in the danger band (≥70°C).
//   That bakes a hardware-level failsafe into the EC: even if this daemon dies
//   with a low duty set, the EC still spins the fan up as the chassis heats.
//
// This file is self-contained and NOT yet wired into monitorLoop — wiring is the
// reviewed Phase 2→3 step. Nothing here runs until Start()/Update() are called.
// It reuses the existing package helpers `lg` (logger) and `writeSysfs`.
// [CHANGE: claude-code | 2026-06-30] v0 — Conductor PID fan module.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// --- actuator: asus_custom_fan_curve discovery + duty writes ---

// fanCurveTempAnchors are the 8 temperature breakpoints (°C) the EC curve uses.
// We keep the stock anchors so the driver sees a valid monotonic-temp curve;
// only the per-point PWM values change to encode our target duty + failsafe ramp.
var fanCurveTempAnchors = [8]int{30, 40, 45, 50, 60, 70, 80, 90}

// fanFailsafeFloorPWM is the minimum PWM the written curve guarantees at each
// anchor REGARDLESS of our target duty — this is the EC-level safety net that
// survives a daemon crash. Below 70°C the floor is 0 (we have full authority);
// at/above 70°C it ramps hard so the hardware self-protects.
var fanFailsafeFloorPWM = [8]int{0, 0, 0, 0, 0, 120, 210, 255}

// fanCurveHwmonPath finds the asus_custom_fan_curve hwmon directory by NAME.
// hwmon indices are not stable across boots, so we never hardcode hwmon8.
func fanCurveHwmonPath() (string, error) {
	entries, err := filepath.Glob("/sys/class/hwmon/hwmon*")
	if err != nil {
		return "", err
	}
	for _, d := range entries {
		b, err := os.ReadFile(filepath.Join(d, "name"))
		if err != nil {
			continue
		}
		if strings.TrimSpace(string(b)) == "asus_custom_fan_curve" {
			return d, nil
		}
	}
	return "", fmt.Errorf("asus_custom_fan_curve hwmon not found")
}

// fanChannels maps a friendly fan name to its pwm channel index on the EC.
// Probe (2026-06-30): fan1=cpu_fan, fan2=gpu_fan, fan3=mid_fan.
var fanChannels = map[string]int{"cpu": 1, "gpu": 2, "mid": 3}

// clampPWM bounds a value to the valid 0-255 EC duty range.
func clampPWM(v int) int {
	if v < 0 {
		return 0
	}
	if v > 255 {
		return 255
	}
	return v
}

// writeFanDuty programs one fan channel to hold `duty` (0-255) across the normal
// band, with the baked-in failsafe ramp above 70°C. It writes the temp anchors
// (idempotent) and the PWM points, then FLUSHES the channel. Requires root (the
// daemon runs as root).
//
// [CHANGE: claude-code | 2026-07-04] BUG-079 follow-up — the ACTUATOR FLUSH.
// Load test 2 proved fixes 1-4 (feed-forward, pre-spin floor, slam) were inert:
// the PID commanded correct duties into the sysfs points but the fan physically
// stayed at 2100-3000 rpm while the CPU sat at 95°C. Root cause: the
// asus_custom_fan_curve driver only updates its *cached* table when you write
// pwmN_auto_pointX_pwm — it does NOT push that table to the EC until pwmN_enable
// is (re-)latched. asusd flushes on `--enable-fan-curves true`; the Conductor
// never did, so its point-writes never reached the hardware. Writing
// pwmN_enable=1 after the points re-latches the cached table to the EC every tick,
// finally giving the PID real-time authority over the fan. Verified on hardware:
// point-writes with no flush → no rpm change; a single pwmN_enable=1 → fan tracks.
func writeFanDuty(hwmon string, channel, duty int) error {
	duty = clampPWM(duty)
	for i := 0; i < 8; i++ {
		pwm := duty
		if f := fanFailsafeFloorPWM[i]; f > pwm {
			pwm = f // never let our target sink below the hardware failsafe floor
		}
		tPath := fmt.Sprintf("%s/pwm%d_auto_point%d_temp", hwmon, channel, i+1)
		pPath := fmt.Sprintf("%s/pwm%d_auto_point%d_pwm", hwmon, channel, i+1)
		if err := writeSysfs(tPath, strconv.Itoa(fanCurveTempAnchors[i])); err != nil {
			return fmt.Errorf("write %s: %w", tPath, err)
		}
		if err := writeSysfs(pPath, strconv.Itoa(pwm)); err != nil {
			return fmt.Errorf("write %s: %w", pPath, err)
		}
	}
	// FLUSH: re-latch the cached point table to the EC. Without this the writes
	// above never reach the hardware. Idempotent (enable=1 = custom-curve mode).
	ePath := fmt.Sprintf("%s/pwm%d_enable", hwmon, channel)
	if err := writeSysfs(ePath, "1"); err != nil {
		return fmt.Errorf("flush %s: %w", ePath, err)
	}
	return nil
}

// setAllFansDuty programs the cpu and mid fans to `cpuDuty` and the gpu fan to
// `gpuDuty`. The gpu fan is driven separately so a GPU-light/CPU-heavy workload
// (e.g. compile) doesn't needlessly spin the GPU fan, and vice versa.
func setAllFansDuty(hwmon string, cpuDuty, gpuDuty int) error {
	if err := writeFanDuty(hwmon, fanChannels["cpu"], cpuDuty); err != nil {
		return err
	}
	if err := writeFanDuty(hwmon, fanChannels["mid"], cpuDuty); err != nil {
		return err
	}
	if err := writeFanDuty(hwmon, fanChannels["gpu"], gpuDuty); err != nil {
		return err
	}
	return nil
}

// --- the PID controller ---

// FanController is a positional PID that converts a temperature error into a fan
// duty (0-255). One instance per thermal domain (we run one for CPU/chassis and
// reuse its output for the GPU fan scaled by GPU load in the wiring step).
type FanController struct {
	Kp, Ki, Kd float64 // gains: Kp is PWM-per-°C of error

	integral float64 // accumulated error (anti-windup via back-calculation)
	prevErr  float64
	prevDuty int  // last duty written, for slew limiting
	seeded   bool // false until the first Update seeds prevErr

	// [CHANGE: claude-code | 2026-07-04] input smoothing + deadband, added after the
	// first live test (dGPU idle) showed the raw-temp PID hunting: fan surged
	// 2600↔3500 rpm on a FLAT 49.8°C because the 47°C target left a standing +2.8°C
	// error the integral kept winding up. See docs/BUGS.md BUG-079.
	smoothedTemp float64 // EMA-filtered control temp (raw Tctl is too spiky to PID on)
	tempSeeded   bool    // false until smoothedTemp is primed

	// [CHANGE: claude-code | 2026-07-04] BUG-079 follow-up: feed-forward on temp slope.
	// The load test showed the fan losing the race to a sudden spike because it only
	// started ramping once the PID error had built up. A feed-forward term on the RATE
	// of temperature rise starts the (EC-inertia-limited) fan ramp the instant the temp
	// climbs, not after it's already hot. See docs/BUGS.md BUG-079.
	prevSmoothedTemp float64 // previous smoothed temp, for the dT/dt feed-forward
	slopeSeeded      bool    // false until prevSmoothedTemp is primed

	// tuning knobs
	TempAlpha     float64 // EMA weight on the newest temp sample (0..1); lower = smoother
	Deadband      float64 // °C band around the target where error is treated as 0
	Kbc           float64 // back-calculation anti-windup gain (≈ 1/tracking-time)
	IntegralLeak  float64 // per-tick integral decay while comfortably inside the deadband
	IntegralClamp float64 // backstop clamp on |integral|
	Kff           float64 // feed-forward: PWM added per (°C/s) of RISING smoothed temp (0 = off)
	SlamTempC     float64 // hard-slam trigger: at/above this RAW temp, command MaxDuty now (0 = off)
	MinDuty       int     // pre-spin floor (0 = silent at idle; Conductor raises it under load)
	MaxDuty       int     // ceiling (255 = full)
	MaxStepUp     int     // max PWM increase per tick (slew up — fast)
	MaxStepDown   int     // max PWM decrease per tick (slew down — gentle, avoids surging)
}

// NewFanController returns a controller tuned against the 2026-07-04 live test.
// Kp=8 → each 1°C of (deadbanded) error adds ~8 PWM (~3%). A ±2°C deadband keeps
// the fan from chasing the last couple degrees, EMA smoothing (TempAlpha) stops it
// reacting to per-core spikes, and back-calculation anti-windup (Kbc) plus an
// in-band integral leak keep it from winding up on a standing error. [CHANGE 2026-07-04]
func NewFanController() *FanController {
	return &FanController{
		Kp: 8.0, Ki: 0.5, Kd: 8.0,
		TempAlpha:     0.30, // smooth the spiky per-core Tctl (0.30 ≈ a few-tick half-life)
		Deadband:      2.0,  // ±2°C around target = no correction → kills the surge
		Kbc:           0.5,  // bleed the integral while the output is saturated (Tt≈2s)
		IntegralLeak:  0.90, // relax the integral each in-band tick so the fan settles down
		IntegralClamp: 120.0,
		Kff:           30.0, // a 1°C/s rise adds ~30 PWM now — start the ramp before it's hot
		SlamTempC:     85.0, // ≥85°C → abandon the PID and slam to max (throttle is ~95°C)
		MinDuty:       0,    // Conductor overrides per-workload (pre-spin floor)
		MaxDuty:       255,
		MaxStepUp:     60, // can jump ~23% per tick toward cooling
		MaxStepDown:   18, // backs off ~7% per tick — no audible surging
	}
}

// Update runs one control step. `tempC` is the current control temperature
// (k10temp Tctl), `setpointC` is the fair target for the CURRENT workload (the
// Conductor supplies this per-Intent; lower target → more fan). `dt` is seconds
// since the last call. Returns the duty (0-255) to program.
//
// Sign convention: error = temp − setpoint. Hotter than target → positive error
// → more fan. Cooler than target → negative error → duty falls toward MinDuty.
func (c *FanController) Update(tempC, setpointC, dt float64) int {
	if dt <= 0 {
		dt = 1
	}

	// 1. EMA-smooth the control temperature. Raw Tctl is spiky per-core; the first
	//    live test showed the PID chasing those spikes into a hunting limit-cycle.
	if !c.tempSeeded {
		c.smoothedTemp = tempC
		c.tempSeeded = true
	} else {
		c.smoothedTemp = (1-c.TempAlpha)*c.smoothedTemp + c.TempAlpha*tempC
	}
	if !c.slopeSeeded {
		c.prevSmoothedTemp = c.smoothedTemp
		c.slopeSeeded = true
	}

	// 1a. HARD SLAM (safety net). Triggered on the RAW temp so the emergency fires
	//     immediately — smoothing would delay it. Above SlamTempC we abandon the PID and
	//     command MaxDuty, bypassing the slew-down limit so the fan starts its (EC-inertia
	//     limited) ramp to max at once. This replaces the 52°C thermal-burst curve that
	//     conductorOwnsFan() suppresses. We update history so the exit is smooth and skip
	//     the integral so it can't wind up while pinned. [CHANGE: claude-code | 2026-07-04]
	if c.SlamTempC > 0 && tempC >= c.SlamTempC {
		c.prevErr = c.smoothedTemp - setpointC
		c.prevSmoothedTemp = c.smoothedTemp
		c.prevDuty = c.MaxDuty
		return c.MaxDuty
	}

	// Feed-forward on the rate of temperature rise (BUG-079): only positive slope adds
	// fan (a cooling trend must never subtract), so a fast climb starts the ramp early.
	tempSlope := (c.smoothedTemp - c.prevSmoothedTemp) / dt
	c.prevSmoothedTemp = c.smoothedTemp
	ff := 0.0
	if tempSlope > 0 {
		ff = c.Kff * tempSlope
	}

	// 2. Error with a deadband. Within ±Deadband of the target we command no
	//    correction, so the fan settles at a steady low duty instead of surging to
	//    shed the last couple degrees the workload makes hard to reach.
	rawErr := c.smoothedTemp - setpointC
	var err float64
	inBand := false
	switch {
	case rawErr > c.Deadband:
		err = rawErr - c.Deadband
	case rawErr < -c.Deadband:
		err = rawErr + c.Deadband
	default:
		inBand = true // err stays 0 inside the band
	}

	if !c.seeded {
		// Seed derivative history so the first tick doesn't kick on a phantom slope.
		c.prevErr = err
		c.seeded = true
	}
	deriv := (err - c.prevErr) / dt
	c.prevErr = err

	// 3. Tentative PID output using the integral carried from the last tick, plus the
	//    feed-forward boost so a rising temp is met before the error alone would react.
	u := c.Kp*err + c.Ki*c.integral + c.Kd*deriv + ff
	uSat := clampF(u, float64(c.MinDuty), float64(c.MaxDuty))

	// 4. Integral update. In-band: leak toward 0 so a past hot spell doesn't keep the
	//    fan up once we're comfortable again. Out-of-band: integrate with a
	//    back-calculation anti-windup term that bleeds the integral whenever the
	//    output saturates (replaces the old hard clamp that unwound far too slowly).
	if inBand {
		c.integral *= c.IntegralLeak
	} else {
		c.integral += (err + c.Kbc*(uSat-u)) * dt
		c.integral = clampF(c.integral, -c.IntegralClamp, c.IntegralClamp) // backstop
	}

	duty := int(uSat + 0.5)
	if duty < c.MinDuty {
		duty = c.MinDuty
	}
	if duty > c.MaxDuty {
		duty = c.MaxDuty
	}

	// 5. Slew limiting against the last duty — asymmetric (fast up, gentle down).
	if duty > c.prevDuty+c.MaxStepUp {
		duty = c.prevDuty + c.MaxStepUp
	} else if duty < c.prevDuty-c.MaxStepDown {
		duty = c.prevDuty - c.MaxStepDown
	}
	duty = clampPWM(duty)
	c.prevDuty = duty
	return duty
}

// Reset clears controller state (used when handing control back/forth, e.g. on
// entering/leaving an override mode) so stale integral/derivative don't carry over.
func (c *FanController) Reset() {
	c.integral = 0
	c.prevErr = 0
	c.seeded = false
	c.tempSeeded = false  // re-prime the temp EMA from the next real reading
	c.slopeSeeded = false // re-prime the feed-forward slope too, so the first post-reset
	// tick doesn't see a phantom jump. prevDuty intentionally retained so the next
	// Update slews from the real fan state.
}

// fairTargetForWorkload returns the fair target temperature (°C) for a workload
// class. This is the "is this temp normal FOR WHAT YOU'RE DOING?" judgement:
// light work can reach 47°C, heavy work cannot, so we don't waste fan chasing it.
// The Conductor's Intent (Phase 3/4) will own this; kept here so the fan module
// is testable standalone. Returns the setpoint the PID should hold.
func fairTargetForWorkload(class string) float64 {
	switch class {
	case "idle", "browsing", "light":
		return 47.0 // reachable → hold it gently
	case "media": // 4K video / decode
		return 55.0
	case "gaming", "training", "compute", "heavy":
		return 60.0 // 47 impossible → hold a fair ceiling efficiently
	default:
		return 52.0 // unknown workload → a safe middle target
	}
}

func clampF(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
