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
// (idempotent) and the PWM points. Requires root (the daemon runs as root).
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

	integral float64 // accumulated error (anti-windup clamped)
	prevErr  float64
	prevDuty int  // last duty written, for slew limiting
	seeded   bool // false until the first Update seeds prevErr

	// tuning knobs
	IntegralClamp float64 // max |integral| — anti-windup
	MinDuty       int     // floor (0 = allow silent at idle)
	MaxDuty       int     // ceiling (255 = full)
	MaxStepUp     int     // max PWM increase per tick (slew up — fast)
	MaxStepDown   int     // max PWM decrease per tick (slew down — gentle, avoids surging)
}

// NewFanController returns a controller with conservative default tuning.
// Kp=14 → each 1°C over target adds ~14 PWM (~5.5%); a 10°C overshoot ≈ full ramp.
// Slew-up is faster than slew-down so it reacts quickly to heat but eases off
// quietly. These are starting values to be refined against real telemetry.
func NewFanController() *FanController {
	return &FanController{
		Kp: 14.0, Ki: 0.6, Kd: 8.0,
		IntegralClamp: 120.0,
		MinDuty:       0,
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
	err := tempC - setpointC

	if !c.seeded {
		// Seed derivative history so the first tick doesn't kick on a phantom slope.
		c.prevErr = err
		c.seeded = true
	}

	c.integral += err * dt
	c.integral = clampF(c.integral, -c.IntegralClamp, c.IntegralClamp)

	deriv := (err - c.prevErr) / dt
	c.prevErr = err

	raw := c.Kp*err + c.Ki*c.integral + c.Kd*deriv
	duty := clampPWM(int(raw))
	if duty < c.MinDuty {
		duty = c.MinDuty
	}
	if duty > c.MaxDuty {
		duty = c.MaxDuty
	}

	// Slew limiting against the last duty — asymmetric (fast up, gentle down).
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
	// prevDuty intentionally retained so the next Update slews from the real fan state.
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
