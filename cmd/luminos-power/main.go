// Command luminos-power monitors AC adapter state and CPU temperature on the ASUS ROG G14,
// applying EPP-based CPU power hints and asusctl profiles automatically.
//
// [CHANGE: gemini-cli | 2026-05-10] v2.1 Quiet Daily Driver (load-tracking)
// [CHANGE: claude-code | 2026-05-14] v3.0 EPP-based control — replaces load-tracking algorithm
//   - governor=powersave always; EPP hint set by AC state
//   - Poll rate: 2s on AC, 10s on battery (ROOT-05 fix)
//   - WiFi power save, KSM, display Hz managed on AC transitions (ROOT-04, ROOT-06)
//   - GPU gaming detection retained (asusctl profile Performance on AC only)
//   - Emergency thermal: EPP=power immediately (no delay)
// [CHANGE: claude-code | 2026-05-15] v3.1 Thermal governor — 45°C target
//   - 4 thermal zones with 5°C hysteresis, scaling_max_freq caps per zone
//   - Gaming mode bypasses thermal capping on AC (user explicitly wants performance)
//   - Hardware max freq read at startup (no hardcoded value)
// [CHANGE: claude-code | 2026-05-26] v4.0 Adaptive Dual Governor
//   - Continuous CPU cap: baseCap + (smoothedLoad/100) × (maxCap - baseCap)
//   - EMA smoothing (α=0.3) on CPU load — no snap changes
//   - Thermal zone tracking decoupled from cap writes (zone only sets emergency/ZoneHot caps)
//   - Exec watcher: /proc scan for new app launches → pre-alloc cap headroom
//   - PSI watcher: poll /proc/pressure/cpu — event-driven wake when idle, tight loop when near cap
//   - iGPU dominance penalty: when iGPU busier than CPU, up to 0.3 GHz CPU reduction (shared TDP)
//   - App history table: known apps pre-allocate cap headroom on launch for smooth startup
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
	"golang.org/x/sys/unix"
)

// PowerState is the payload reported to luminos-ai on every state change.
type PowerState struct {
	OnAC      bool      `json:"on_ac"`
	CPUTempC  float64   `json:"cpu_temp_c"`
	GPULoad   float64   `json:"gpu_load"`
	EPP       string    `json:"epp"`
	Profile   string    `json:"profile"`
	UpdatedAt time.Time `json:"updated_at"`
}

const (
	wifiIface = "wlp3s0"
	// kscreen output ID for the built-in eDP panel
	displayOutputID = "1"
	// dGPU (NVIDIA) gaming thresholds — beast mode trigger
	gpuHighThreshPct   = 80.0
	gpuHighThreshTicks = 15 // 30s at 2s poll
	gpuLowThreshPct    = 20.0
	gpuLowThreshTicks  = 30 // 60s at 2s poll
	// CPU beast-mode thresholds — catches CPU-heavy work (ML training, compilation)
	cpuHighThreshPct   = 75.0
	cpuHighThreshTicks = 10 // 20s at 2s poll
	cpuLowThreshPct    = 25.0
	cpuLowThreshTicks  = 30 // 60s at 2s poll
	// [CHANGE: claude-code | 2026-05-24] Load-based Quiet idle detection.
	// Balanced→Quiet when CPU+iGPU+dGPU all idle for 60s on AC.
	// Quiet→Balanced immediately when any load rises.
	quietIdleCPUPct   = 25.0 // CPU% threshold for idle
	quietIdleIGPUPct  = 15.0 // iGPU% threshold for idle (card2=AMD 780M)
	quietIdleDGPUPct  = 5.0  // dGPU% threshold for idle (card1=NVIDIA)
	quietIdleTicks    = 30   // 60s sustained idle (30 × 2s) → drop to Quiet
	// Emergency thermal threshold
	// [CHANGE: claude-code | 2026-05-24] BUG-055: raised from 85°C→92°C (ZoneHot entry raised to 87°C)
	thermalEmergencyC = 92.0

	// [CHANGE: claude-code | 2026-05-26] v4.0 Adaptive Governor constants.
	//
	// The governor sets a continuous CPU frequency cap based on smoothed load:
	//   cap = baseCap + (smoothedLoad/100) × (maxCap - baseCap)
	//
	// At 0% load → baseCap (floor, power saving).
	// At 100% load → maxCap (ceiling, full performance).
	// Thermal zones still apply ZoneHot (87°C→3.0GHz) and Emergency (92°C→2.0GHz) as overrides.
	//
	// iGPU dominance: when iGPU is busier than CPU by >20%, apply a small CPU penalty
	// (up to 0.3 GHz) to redistribute shared APU TDP toward the iGPU.
	//
	// Pre-allocation: when a known app launches, temporarily raise effective load estimate
	// by the app's PreAllocPct for 30s, giving startup headroom without waiting for load to ramp.
	adaptiveBaseCap    = 1800000  // kHz — floor cap when fully idle (1.8 GHz)
	adaptiveMaxCapAC   = 0        // 0 = hardware max on AC (5.137 GHz)
	adaptiveMaxCapBat  = 3500000  // kHz — max cap on battery (3.5 GHz, power saving)
	adaptiveEMAAlpha   = 0.30     // EMA weight for new sample (0.7 old + 0.3 new)
	adaptiveCapChangeThreshKHz = 150000 // only write sysfs if cap shifts by >150 MHz
	preAllocDuration   = 30 * time.Second
	// iGPU dominance: penalty per 1% of dominance delta, capped at 300 MHz total
	dominancePenaltyPerPct = 12000 // kHz per 1% dominance (0.012 GHz/%)
	dominanceMaxPenaltyKHz = 300000

	// Thermal governor zones (ZoneCool→ZoneHot) with 5°C hysteresis for exit.
	// Target: 45°C idle via EPP hints alone. Freq caps only for genuinely hot temps.
	// On AC: ZoneWarm has no cap (fans at 100% from 70°C handle it). Only ZoneHot+ caps.
	// On battery: caps start at 62°C — saves power and battery.
	thermalHysteresisC        = 5.0
	thermalDowngradeHoldTicks = 5 // must stay below exit threshold for 5 ticks (10s on AC) before downgrading zone

	// AC thresholds — permissive, caps only when actually overheating
	// [CHANGE: claude-code | 2026-05-24] BUG-055: raised Zone3 from 80°C→87°C.
	// 8845HS TJmax=105°C. YouTube/normal load sits at 80-85°C with fans at 100%.
	// Old 80°C threshold triggered 3.0GHz cap during normal use, causing oscillation+stutter.
	thermalACZone1C = 60.0 // cool→mild on AC: EPP nudge only, no cap
	thermalACZone2C = 72.0 // mild→warm on AC: no cap (fans 100% at 70°C handle cooling — BUG-055)
	thermalACZone3C = 87.0 // warm→hot on AC:  3.0 GHz cap (was 80°C — raised, BUG-055)

	// Battery thresholds — more aggressive to save power and extend range
	thermalBatZone1C = 50.0 // cool→mild on bat: EPP=power (already set), no cap
	thermalBatZone2C = 62.0 // mild→warm on bat: 3.5 GHz cap
	thermalBatZone3C = 72.0 // warm→hot on bat:  2.5 GHz cap
)

// appProfile describes a known application's expected CPU load and launch headroom.
// PreAllocPct is added to the smoothed load estimate for preAllocDuration after launch,
// giving the app enough cap headroom to start up without being throttled.
// It does NOT limit the app — it raises the frequency ceiling so startup feels smooth.
type appProfile struct {
	PreAllocPct float64 // extra % load to add to cap estimate at launch (e.g. 15 = +15%)
}

// knownApps maps process comm names (from /proc/N/comm) to their launch profiles.
// Update this table as new apps are added; unknown apps get no pre-alloc bonus.
// [CHANGE: claude-code | 2026-05-26] v4.0 app history table
var knownApps = map[string]appProfile{
	"chrome":          {PreAllocPct: 20}, // Chrome GPU process + initial tab load
	"terminal64.exe":  {PreAllocPct: 15}, // MetaTrader 5 (Wine) — heavy on launch
	"python.exe":      {PreAllocPct: 10}, // Forex bot bridge (Wine Python)
	"python3":         {PreAllocPct: 10}, // hive-daemon, forex bot
	"claude":          {PreAllocPct: 18}, // Claude Desktop (Electron)
	"konsole":         {PreAllocPct: 8},
	"kwin_wayland":    {PreAllocPct: 5},
	"plasmashell":     {PreAllocPct: 8},
	"code":            {PreAllocPct: 20}, // VS Code (Electron)
	"wine64":          {PreAllocPct: 12},
}

// ThermalZone represents current CPU temperature zone.
type ThermalZone int

const (
	ZoneCool ThermalZone = iota // <60°C  — no throttle (AC)
	ZoneMild                    // 60-72°C — no cap (AC)
	ZoneWarm                    // 72-87°C — no cap (fans at 100% handle it — BUG-055)
	ZoneHot                     // >87°C  — 3.0 GHz cap (AC, below emergency 92°C)
)

var (
	lg        *logger.Logger
	cfg       *config.Config
	prevState PowerState
	cpuCount  int

	gpuHighTicks int
	gpuLowTicks  int
	cpuHighTicks int
	cpuLowTicks  int
	quietTicks   int // ticks of all-idle load → Quiet profile

	currentThermalZone  ThermalZone = ZoneCool
	thermalDownholdTick int        // consecutive ticks below exit threshold before downgrading
	cpuHardwareMaxFreq  int        // read from sysfs at startup, kHz

	// [CHANGE: claude-code | 2026-05-26] v4.0 adaptive governor state
	smoothedCPULoad    float64       // EMA-smoothed CPU% (α=0.3)
	prevAppliedCapKHz  int           // last cap written to sysfs — avoid redundant writes
	preAllocBonus      float64       // extra % added to load estimate (decays after preAllocDuration)
	preAllocExpiry     time.Time     // when preAllocBonus expires

	// /proc/stat snapshot for delta-based CPU load calculation
	lastCPUStatIdle  uint64
	lastCPUStatTotal uint64
)

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

	cpuCount = runtime.NumCPU()
	cpuHardwareMaxFreq = readCPUHardwareMax()
	prevAppliedCapKHz = cpuHardwareMaxFreq // start uncapped
	lg.Info("CPU hardware max freq: %d kHz (%.2f GHz)", cpuHardwareMaxFreq, float64(cpuHardwareMaxFreq)/1e6)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	if err := os.MkdirAll("/run/luminos", 0755); err != nil {
		lg.Error("create /run/luminos: %v", err)
		os.Exit(1)
	}

	l, err := socket.NewListener(cfg.Sockets.Power)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}

	lg.Info("luminos-power v4.0 started — Adaptive Dual Governor + PSI watcher, listening on %s", cfg.Sockets.Power)

	// Apply fan curves to all profiles once at startup
	applyAggressiveFanCurve("balanced")
	applyAggressiveFanCurve("quiet")

	// Set initial power state based on current AC state
	onAC := readACState()
	applyACTransition(onAC)

	go monitorLoop(ctx)
	socket.Serve(ctx, l, handleMessage)

	os.Remove(cfg.Sockets.Power)
	lg.Info("luminos-power stopped")
}

func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "ping":
		return replyOK(msg, map[string]string{"pong": "ok", "daemon": "luminos-power"})
	case "status":
		b, _ := json.Marshal(prevState)
		return socket.Message{
			Type:      "status_response",
			Payload:   json.RawMessage(b),
			Timestamp: time.Now(),
			Source:    "luminos-power",
		}
	default:
		return replyError(msg, fmt.Sprintf("unknown type: %s", msg.Type))
	}
}

// monitorLoop is the main control loop for luminos-power v4.0.
//
// Sleep strategy (replaces fixed 2s ticker):
//   - Idle (all loads <20%): block on PSI poll up to 10s — wakes only on CPU pressure event
//   - Active (20-60%): 2s sleep
//   - Near cap (>60%): 500ms tight loop — fast trigger detection
//
// Cap strategy:
//   adaptive cap = baseCap + (effectiveLoad/100) × (maxCap - baseCap), EMA smoothed
//   effectiveLoad = smoothedCPULoad + preAllocBonus (decays 30s after app launch)
//   thermal override: ZoneHot (87°C) → 3.0 GHz cap replaces adaptive cap if lower
//   emergency: 92°C → 2.0 GHz, Quiet profile — overrides everything
//
// [CHANGE: claude-code | 2026-05-26] v4.0
func monitorLoop(ctx context.Context) {
	// PSI watcher — event-driven wake on CPU pressure.
	// Falls back to time.After if /proc/pressure/cpu is unavailable.
	psiFile, psiErr := openPSIWatcher()
	if psiErr != nil {
		lg.Warn("PSI watcher unavailable (%v) — using time-based sleep", psiErr)
	} else {
		lg.Info("PSI watcher active — event-driven idle sleep")
		defer psiFile.Close()
	}

	// Exec watcher — /proc scanner detects new app launches.
	ew := newExecWatcher()
	go ew.run(ctx)

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		// === SENSE ===
		onAC := readACState()
		temp := readCPUTemp()
		dgpuLoad := readDGPULoad() // NVIDIA dGPU
		igpuLoad := readIGPULoad() // AMD 780M
		cpuLoad := readCPULoadPct()

		// EMA smoothing on CPU load — prevents snap decisions on spikes.
		// First tick (smoothedCPULoad==0): seed from raw to avoid starting at 0%.
		if smoothedCPULoad == 0 && cpuLoad > 0 {
			smoothedCPULoad = cpuLoad
		} else {
			smoothedCPULoad = (1-adaptiveEMAAlpha)*smoothedCPULoad + adaptiveEMAAlpha*cpuLoad
		}

		// Drain exec events → update pre-alloc bonus.
		// Takes the max bonus of all apps launched since last tick.
	drainExec:
		for {
			select {
			case appName := <-ew.events:
				if p, ok := knownApps[appName]; ok {
					if p.PreAllocPct > preAllocBonus {
						preAllocBonus = p.PreAllocPct
					}
					preAllocExpiry = time.Now().Add(preAllocDuration)
					lg.Info("exec: %s → pre-alloc +%.0f%% for %v", appName, p.PreAllocPct, preAllocDuration)
				}
			default:
				break drainExec
			}
		}
		if time.Now().After(preAllocExpiry) {
			preAllocBonus = 0
		}

		// === AC TRANSITION ===
		if onAC != prevState.OnAC {
			applyACTransition(onAC)
			cpuHighTicks = 0
			cpuLowTicks = 0
			quietTicks = 0
			smoothedCPULoad = cpuLoad // reset EMA on AC change — old average no longer valid
			prevAppliedCapKHz = cpuHardwareMaxFreq
		}

		// === BEAST MODE ===
		// Uses dGPU only (iGPU load = compositing, not gaming).
		// Beast mode disables the adaptive governor and runs uncapped.
		if onAC && prevState.Profile != "Performance" {
			gpuProfile := applyGamingDetection(dgpuLoad, prevState.Profile)
			cpuProfile := applyCPUBeastDetection(cpuLoad, prevState.Profile)
			if gpuProfile == "Performance" || cpuProfile == "Performance" {
				src := "gpu"
				if cpuProfile == "Performance" {
					src = "cpu"
				}
				lg.Info("beast mode → Performance (trigger: %s, cpu=%.0f%%, dgpu=%.0f%%)", src, cpuLoad, dgpuLoad)
				runCmd("asusctl", "profile", "set", "Performance")
				setEPPAfterAsusctl("performance")
				setAllMaxFreq(0) // full boost — adaptive governor suspended
				prevAppliedCapKHz = cpuHardwareMaxFreq
				currentThermalZone = ZoneCool
				thermalDownholdTick = 0
				quietTicks = 0
				updateState(onAC, temp, dgpuLoad, "performance", "Performance")
				sleepAdaptive(ctx, psiFile, smoothedCPULoad, igpuLoad)
				continue
			}
		} else if onAC && prevState.Profile == "Performance" {
			gpuProfile := applyGamingDetection(dgpuLoad, "Performance")
			cpuProfile := applyCPUBeastDetection(cpuLoad, "Performance")
			if gpuProfile == "Balanced" && cpuProfile == "Balanced" {
				lg.Info("beast mode exit → Balanced (cpu=%.0f%%, dgpu=%.0f%%)", cpuLoad, dgpuLoad)
				runCmd("asusctl", "profile", "set", "Balanced")
				currentThermalZone = ZoneCool
				thermalDownholdTick = 0
				quietTicks = 0
				setEPPAfterAsusctl("power")
				updateState(onAC, temp, dgpuLoad, "power", "Balanced")
				sleepAdaptive(ctx, psiFile, smoothedCPULoad, igpuLoad)
				continue
			}
		}

		// === QUIET IDLE DETECTION (AC, non-Performance) ===
		// Balanced→Quiet: all loads idle for 60s. Quiet→Balanced: immediate on load.
		if onAC && prevState.Profile == "Balanced" {
			if cpuLoad < quietIdleCPUPct && igpuLoad < quietIdleIGPUPct && dgpuLoad < quietIdleDGPUPct {
				quietTicks++
				if quietTicks >= quietIdleTicks {
					quietTicks = 0
					lg.Info("idle → Quiet (cpu=%.0f%%, igpu=%.0f%%, dgpu=%.0f%%)", cpuLoad, igpuLoad, dgpuLoad)
					runCmd("asusctl", "profile", "set", "Quiet")
					updateState(onAC, temp, dgpuLoad, prevState.EPP, "Quiet")
					sleepAdaptive(ctx, psiFile, smoothedCPULoad, igpuLoad)
					continue
				}
			} else {
				quietTicks = 0
			}
		} else if onAC && prevState.Profile == "Quiet" {
			if cpuLoad >= quietIdleCPUPct || igpuLoad >= quietIdleIGPUPct || dgpuLoad >= quietIdleDGPUPct {
				quietTicks = 0
				lg.Info("load → Balanced (cpu=%.0f%%, igpu=%.0f%%, dgpu=%.0f%%)", cpuLoad, igpuLoad, dgpuLoad)
				runCmd("asusctl", "profile", "set", "Balanced")
				updateState(onAC, temp, dgpuLoad, prevState.EPP, "Balanced")
				sleepAdaptive(ctx, psiFile, smoothedCPULoad, igpuLoad)
				continue
			}
		}

		// === EMERGENCY THERMAL ===
		// Overrides adaptive governor entirely.
		emergencyThreshC := thermalEmergencyC
		if prevState.Profile == "Performance" {
			emergencyThreshC = 95.0 // TJmax 105°C, 95°C is safe under gaming load
		}
		if temp > emergencyThreshC {
			if prevState.Profile == "Performance" {
				lg.Warn("%.1f°C > %.0f°C in beast mode — throttle 3.5GHz", temp, emergencyThreshC)
				setAllMaxFreq(3500000)
				prevAppliedCapKHz = 3500000
			} else {
				lg.Warn("%.1f°C > %.0f°C — Emergency: Quiet + 2GHz cap", temp, thermalEmergencyC)
				runCmd("asusctl", "profile", "set", "Quiet")
				setAllEPP("power")
				setAllMaxFreq(2000000)
				prevAppliedCapKHz = 2000000
				updateState(onAC, temp, dgpuLoad, "power", "Quiet")
			}
			sleepAdaptive(ctx, psiFile, smoothedCPULoad, igpuLoad)
			continue
		}

		// === ADAPTIVE GOVERNOR (non-Performance, non-Emergency) ===
		// Advance thermal zone for ZoneHot detection (only zone with a cap on AC).
		// Then compute the final cap as min(adaptiveCap, thermalCap).
		if prevState.Profile != "Performance" {
			advanceThermalZone(temp, onAC)

			// Effective load = smoothed + pre-alloc headroom (capped at 100%)
			effectiveLoad := math.Min(smoothedCPULoad+preAllocBonus, 100)
			adaptiveCap := computeAdaptiveCap(effectiveLoad, igpuLoad, onAC)

			// Thermal override: ZoneHot applies a hard cap that adaptive governor must respect.
			// ZoneCool/ZoneMild/ZoneWarm have no cap — fans handle it (BUG-055).
			thermalCap := thermalCapForCurrentZone(onAC)
			finalCap := adaptiveCap
			if thermalCap > 0 && thermalCap < adaptiveCap {
				finalCap = thermalCap
			}

			// Smooth cap transitions: 70% old + 30% target — prevents rapid sysfs churn.
			smoothedCap := int(0.7*float64(prevAppliedCapKHz) + 0.3*float64(finalCap))

			// Only write sysfs if the change is meaningful (>150 MHz).
			if abs(smoothedCap-prevAppliedCapKHz) > adaptiveCapChangeThreshKHz {
				setAllMaxFreq(smoothedCap)
				prevAppliedCapKHz = smoothedCap
				lg.Info("adaptive cap → %.2f GHz (cpu=%.0f%% smooth=%.0f%% prealloc=%.0f%% igpu=%.0f%%)",
					float64(smoothedCap)/1e6, cpuLoad, smoothedCPULoad, preAllocBonus, igpuLoad)
			}
		}

		updateState(onAC, temp, dgpuLoad, prevState.EPP, prevState.Profile)
		sleepAdaptive(ctx, psiFile, smoothedCPULoad, igpuLoad)
	}
}

// applyACTransition handles the full set of changes when AC state changes.
// Called at startup and on every AC plug/unplug event.
func applyACTransition(onAC bool) {
	// Reset thermal zone, hold counter, freq cap, and idle counter on any AC transition
	currentThermalZone = ZoneCool
	thermalDownholdTick = 0
	quietTicks = 0
	setAllMaxFreq(0)

	if onAC {
		lg.Info("AC plugged — applying AC power settings")
		setAllGovernor("powersave")
		setWiFiPowerSave(false)
		setKSM(true)
		setDisplayHz(120)
		runCmd("asusctl", "profile", "set", "Balanced")
		// asusd applies EPP asynchronously via D-Bus — wait for it to finish
		// before overwriting. EPP=power targets 45°C idle on AC and battery alike.
		setEPPAfterAsusctl("power")
		prevState.EPP = "power"
		prevState.Profile = "Balanced"
	} else {
		lg.Info("AC unplugged — applying battery power settings")
		setAllGovernor("powersave")
		setWiFiPowerSave(true)
		setKSM(false)
		setDisplayHz(60)
		runCmd("asusctl", "profile", "set", "Quiet")
		setEPPAfterAsusctl("power")
		prevState.EPP = "power"
		prevState.Profile = "Quiet"
	}
	prevState.OnAC = onAC
	prevState.UpdatedAt = time.Now()
	reportToAI()
}

// applyGamingDetection tracks GPU load and returns the desired profile.
// GPU > 80% for 30s → Performance; GPU < 20% for 60s after Performance → Balanced.
func applyGamingDetection(gpuLoad float64, currentProfile string) string {
	if gpuLoad > gpuHighThreshPct {
		gpuHighTicks++
		gpuLowTicks = 0
	} else if currentProfile == "Performance" && gpuLoad < gpuLowThreshPct {
		gpuLowTicks++
		gpuHighTicks = 0
	} else {
		gpuHighTicks = 0
		gpuLowTicks = 0
	}

	if gpuHighTicks >= gpuHighThreshTicks {
		gpuHighTicks = gpuHighThreshTicks // cap
		return "Performance"
	}
	if gpuLowTicks >= gpuLowThreshTicks {
		gpuLowTicks = 0
		return "Balanced"
	}
	return currentProfile
}

// applyCPUBeastDetection mirrors applyGamingDetection for CPU-heavy workloads.
// Catches ML training, XGBoost, compilation — anything GPU detection misses.
func applyCPUBeastDetection(cpuLoad float64, currentProfile string) string {
	if cpuLoad > cpuHighThreshPct {
		cpuHighTicks++
		cpuLowTicks = 0
	} else if currentProfile == "Performance" && cpuLoad < cpuLowThreshPct {
		cpuLowTicks++
		cpuHighTicks = 0
	} else {
		cpuHighTicks = 0
		cpuLowTicks = 0
	}

	if cpuHighTicks >= cpuHighThreshTicks {
		cpuHighTicks = cpuHighThreshTicks // cap
		return "Performance"
	}
	if cpuLowTicks >= cpuLowThreshTicks {
		cpuLowTicks = 0
		return "Balanced"
	}
	return currentProfile
}

func eppForProfile(profile string) string {
	switch profile {
	case "Performance":
		return "performance"
	case "Balanced":
		return "balance_performance"
	default:
		return "balance_performance"
	}
}


// --- thermal zone tracking ---

// advanceThermalZone updates currentThermalZone based on temperature.
// Does NOT write sysfs — the adaptive governor reads thermalCapForCurrentZone()
// and applies the final merged cap. This separation prevents double-writes.
//
// [CHANGE: claude-code | 2026-05-26] v4.0: decoupled zone tracking from cap writes.
// Previously applyThermalGovernor() both tracked zone AND wrote sysfs — the adaptive
// governor now owns all sysfs writes and calls thermalCapForCurrentZone() to get
// the thermal constraint.
func advanceThermalZone(temp float64, onAC bool) {
	z1, z2, z3 := thermalACZone1C, thermalACZone2C, thermalACZone3C
	if !onAC {
		z1, z2, z3 = thermalBatZone1C, thermalBatZone2C, thermalBatZone3C
	}

	prev := currentThermalZone
	newZone := prev

	switch prev {
	case ZoneCool:
		if temp >= z1 {
			thermalDownholdTick = 0
			newZone = ZoneMild
		}
	case ZoneMild:
		if temp >= z2 {
			thermalDownholdTick = 0
			newZone = ZoneWarm
		} else if temp < z1-thermalHysteresisC {
			thermalDownholdTick++
			if thermalDownholdTick >= thermalDowngradeHoldTicks {
				thermalDownholdTick = 0
				newZone = ZoneCool
			}
		} else {
			thermalDownholdTick = 0
		}
	case ZoneWarm:
		if temp >= z3 {
			thermalDownholdTick = 0
			newZone = ZoneHot
		} else if temp < z2-thermalHysteresisC {
			thermalDownholdTick++
			if thermalDownholdTick >= thermalDowngradeHoldTicks {
				thermalDownholdTick = 0
				newZone = ZoneMild
			}
		} else {
			thermalDownholdTick = 0
		}
	case ZoneHot:
		if temp < z3-thermalHysteresisC {
			thermalDownholdTick++
			if thermalDownholdTick >= thermalDowngradeHoldTicks {
				thermalDownholdTick = 0
				newZone = ZoneWarm
			}
		} else {
			thermalDownholdTick = 0
		}
	}

	if newZone != prev {
		currentThermalZone = newZone
		lg.Info("thermal zone %d→%d (%.1f°C, on_ac=%v)", prev, newZone, temp, onAC)
	}
}

// thermalCapForCurrentZone returns the thermal cap in kHz for the current zone.
// Returns 0 (= no cap) for ZoneCool/ZoneMild/ZoneWarm on AC (fans handle it).
// Returns non-zero for ZoneHot and battery warm zones.
func thermalCapForCurrentZone(onAC bool) int {
	switch currentThermalZone {
	case ZoneHot:
		if onAC {
			return 3000000 // 3.0 GHz — only cap on AC, fans can't keep up at this point
		}
		return 2500000 // 2.5 GHz on battery
	case ZoneWarm:
		if onAC {
			return 0 // no cap — fan curve v5 handles it (BUG-055)
		}
		return 3500000 // 3.5 GHz on battery (power saving)
	default:
		return 0 // ZoneCool, ZoneMild: no cap needed
	}
}

// --- adaptive governor ---

// computeAdaptiveCap returns the target CPU cap in kHz based on smoothed load.
//
// Formula:
//   cap = baseCap + (effectiveLoad/100) × (maxCap - baseCap)
//
// iGPU dominance penalty: when iGPU is running harder than CPU (e.g. video decode
// while CPU is light), reduce CPU cap slightly to give shared TDP headroom to iGPU.
// Penalty = dominance% × 12kHz, capped at 300 MHz.
//
// [CHANGE: claude-code | 2026-05-26] v4.0
func computeAdaptiveCap(effectiveLoad, igpuLoad float64, onAC bool) int {
	maxCap := cpuHardwareMaxFreq
	if !onAC && adaptiveMaxCapBat > 0 {
		maxCap = adaptiveMaxCapBat
	}

	// Linear interpolation: idle→baseCap, full load→maxCap
	cap := adaptiveBaseCap + int((effectiveLoad/100.0)*float64(maxCap-adaptiveBaseCap))

	// iGPU dominance: when iGPU is doing more work than CPU, it needs more of the
	// shared APU TDP. Nudge CPU cap down proportionally.
	dominance := igpuLoad - effectiveLoad
	if dominance > 20 {
		penalty := int(dominance * dominancePenaltyPerPct)
		if penalty > dominanceMaxPenaltyKHz {
			penalty = dominanceMaxPenaltyKHz
		}
		cap -= penalty
	}

	// Clamp to [baseCap, maxCap]
	if cap < adaptiveBaseCap {
		cap = adaptiveBaseCap
	}
	if cap > maxCap {
		cap = maxCap
	}
	return cap
}

// sleepAdaptive sleeps for an interval based on current load:
//   - Idle (<20% all): PSI event-driven sleep up to 10s — wakes on CPU pressure
//   - Active (20-60%): 2s
//   - Near cap (>60%): 500ms — tight loop for trigger detection
//
// [CHANGE: claude-code | 2026-05-26] v4.0
func sleepAdaptive(ctx context.Context, psiFile *os.File, cpuLoad, igpuLoad float64) {
	maxLoad := math.Max(cpuLoad, igpuLoad)
	var d time.Duration
	switch {
	case maxLoad < 20:
		d = 10 * time.Second
	case maxLoad < 60:
		d = 2 * time.Second
	default:
		d = 500 * time.Millisecond
	}

	// In the idle zone, block on PSI rather than sleeping — wakes only when
	// CPU stall pressure exceeds the threshold (70ms stall in 1s window).
	if psiFile != nil && maxLoad < 20 {
		waitPSI(psiFile, d)
		return
	}

	select {
	case <-ctx.Done():
	case <-time.After(d):
	}
}

// --- PSI (Pressure Stall Information) watcher ---
// Linux 4.20+. /proc/pressure/cpu supports poll(POLLPRI) with a threshold trigger.
// The kernel wakes the fd only when the stall rate crosses the threshold — zero CPU wasted.
//
// [CHANGE: claude-code | 2026-05-26] v4.0

// openPSIWatcher opens /proc/pressure/cpu and arms a stall threshold.
// The file stays open; call waitPSI() to block until the threshold fires.
func openPSIWatcher() (*os.File, error) {
	f, err := os.OpenFile("/proc/pressure/cpu", os.O_RDWR, 0)
	if err != nil {
		return nil, err
	}
	// "some 70000 1000000" = wake when any CPU stall exceeds 70ms in a 1s window.
	// This fires under moderate load — light enough to catch real work, ignores pure idle.
	if _, err := fmt.Fprintf(f, "some 70000 1000000"); err != nil {
		f.Close()
		return nil, fmt.Errorf("write PSI threshold: %w", err)
	}
	return f, nil
}

// waitPSI blocks until the PSI threshold fires or timeout elapses.
// Returns true if the PSI event fired, false on timeout.
func waitPSI(f *os.File, timeout time.Duration) bool {
	pfd := []unix.PollFd{{
		Fd:     int32(f.Fd()),
		Events: unix.POLLPRI | unix.POLLERR,
	}}
	ms := int(timeout.Milliseconds())
	n, _ := unix.Poll(pfd, ms)
	return n > 0
}

// --- exec watcher ---
// Scans /proc every 1s for new PIDs. On detecting an unknown PID whose comm matches
// a knownApp, fires the app name on the events channel.
// This is simpler than fanotify/netlink and sufficient for our pre-allocation use case.
//
// [CHANGE: claude-code | 2026-05-26] v4.0

type execWatcher struct {
	knownPIDs map[int]struct{}
	mu        sync.Mutex
	events    chan string // comm names of newly launched known apps
}

func newExecWatcher() *execWatcher {
	return &execWatcher{
		knownPIDs: make(map[int]struct{}),
		events:    make(chan string, 16),
	}
}

// run scans /proc every 1s for new process launches.
// Sends the comm name to events when a known app appears.
func (w *execWatcher) run(ctx context.Context) {
	// Seed known PIDs without firing events (they were already running at daemon start).
	w.seed()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			w.scan()
		}
	}
}

func (w *execWatcher) seed() {
	entries, _ := os.ReadDir("/proc")
	w.mu.Lock()
	defer w.mu.Unlock()
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		w.knownPIDs[pid] = struct{}{}
	}
}

func (w *execWatcher) scan() {
	entries, _ := os.ReadDir("/proc")
	w.mu.Lock()
	defer w.mu.Unlock()

	seen := make(map[int]struct{}, len(entries))
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		seen[pid] = struct{}{}
		if _, known := w.knownPIDs[pid]; !known {
			w.knownPIDs[pid] = struct{}{}
			comm, err := os.ReadFile(fmt.Sprintf("/proc/%d/comm", pid))
			if err != nil {
				continue
			}
			name := strings.TrimSpace(string(comm))
			if _, ok := knownApps[name]; ok {
				select {
				case w.events <- name:
				default: // drop if channel full — non-blocking
				}
			}
		}
	}
	// Prune dead PIDs to keep the map bounded.
	for pid := range w.knownPIDs {
		if _, alive := seen[pid]; !alive {
			delete(w.knownPIDs, pid)
		}
	}
}

// abs returns the absolute value of an int.
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// setEPPAfterAsusctl waits for asusd's async D-Bus write to complete before
// overwriting EPP. asusctl returns immediately but asusd applies the profile
// EPP ~100-300ms later via the kernel driver, clobbering a direct sysfs write.
func setEPPAfterAsusctl(epp string) {
	time.Sleep(350 * time.Millisecond)
	setAllEPP(epp)
}

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
	if err := runCmd("/usr/bin/iw", "dev", wifiIface, "set", "power_save", val); err != nil {
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
	cmd := exec.Command("runuser", "-u", uid, "--",
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

func readCPUTemp() float64 {
	entries, _ := filepath.Glob("/sys/class/hwmon/hwmon*/temp*_input")
	var max float64
	for _, p := range entries {
		d, _ := os.ReadFile(p)
		m, _ := strconv.ParseFloat(strings.TrimSpace(string(d)), 64)
		if c := m / 1000.0; c > max {
			max = c
		}
	}
	return max
}

func readGPULoad() float64 {
	// Returns max GPU load across all cards (used for beast-mode dGPU detection).
	matches, _ := filepath.Glob("/sys/class/drm/card*/device/gpu_busy_percent")
	var max float64
	for _, m := range matches {
		d, _ := os.ReadFile(m)
		val, _ := strconv.ParseFloat(strings.TrimSpace(string(d)), 64)
		if val > max {
			max = val
		}
	}
	return max
}

// readDGPULoad returns NVIDIA dGPU (card1) busy percent. 0 if unavailable/powered down.
func readDGPULoad() float64 {
	d, _ := os.ReadFile("/sys/class/drm/card1/device/gpu_busy_percent")
	val, _ := strconv.ParseFloat(strings.TrimSpace(string(d)), 64)
	return val
}

// readIGPULoad returns AMD iGPU (card2) busy percent. 0 if unavailable.
func readIGPULoad() float64 {
	d, _ := os.ReadFile("/sys/class/drm/card2/device/gpu_busy_percent")
	val, _ := strconv.ParseFloat(strings.TrimSpace(string(d)), 64)
	return val
}

// readCPULoadPct returns system-wide CPU utilisation as a percentage (0-100)
// computed from the delta of /proc/stat between consecutive calls.
// First call always returns 0 (no previous snapshot to diff against).
func readCPULoadPct() float64 {
	data, err := os.ReadFile("/proc/stat")
	if err != nil {
		return 0
	}
	// First line: "cpu  user nice system idle iowait irq softirq steal guest guest_nice"
	line := strings.SplitN(string(data), "\n", 2)[0]
	fields := strings.Fields(line)
	if len(fields) < 5 || fields[0] != "cpu" {
		return 0
	}
	var vals [10]uint64
	for i, f := range fields[1:] {
		if i >= 10 {
			break
		}
		vals[i], _ = strconv.ParseUint(f, 10, 64)
	}
	idle := vals[3] + vals[4] // idle + iowait
	var total uint64
	for _, v := range vals {
		total += v
	}

	if lastCPUStatTotal == 0 {
		// First call — seed the snapshot, return 0
		lastCPUStatIdle = idle
		lastCPUStatTotal = total
		return 0
	}

	deltaTotal := total - lastCPUStatTotal
	deltaIdle := idle - lastCPUStatIdle
	lastCPUStatIdle = idle
	lastCPUStatTotal = total

	if deltaTotal == 0 {
		return 0
	}
	used := deltaTotal - deltaIdle
	return float64(used) / float64(deltaTotal) * 100.0
}

// --- helpers ---

func updateState(onAC bool, temp, gpuLoad float64, epp, profile string) {
	prevState = PowerState{
		OnAC:      onAC,
		CPUTempC:  temp,
		GPULoad:   gpuLoad,
		EPP:       epp,
		Profile:   profile,
		UpdatedAt: time.Now(),
	}
}

func applyAggressiveFanCurve(mode string) {
	// [CHANGE: claude-code | 2026-05-24] Fan curve v5 — steep recovery above 47°C
	//
	// Problem with v4: 50°C breakpoint was only 25%. At 52°C the firmware interpolated
	// to ~29% — not enough fan to pull the CPU back down to 47°C. The curve was quiet
	// below 47°C but had no recovery bite above it.
	//
	// Fix: raise 50°C from 25% → 55%. Creates a steep 45→50°C slope so any overshoot
	// above 47°C gets aggressively corrected:
	//   40°C → 5%   (silent at idle — same as v4)
	//   47°C → 22 + (2/5)·(55−22) = 35%  (good hold — up from 21%)
	//   48°C → 22 + (3/5)·(55−22) = 42%  (noticeably ramping)
	//   50°C → 55%  (aggressive recovery threshold)
	//   52°C → 55 + (2/10)·(88−55) = 62%  (strong pullback from overshoot)
	//
	// Mid fan is 67% of CPU/GPU curve throughout.
	lg.Info("Applying fan curve to %s profile (v5: steep 47°C recovery)", mode)
	cpuGpuCurve := "30c:0%,40c:5%,45c:22%,50c:55%,60c:88%,70c:100%,80c:100%,90c:100%"
	midCurve    := "30c:0%,40c:0%,45c:15%,50c:37%,60c:59%,70c:70%,80c:88%,90c:100%"
	runCmd("asusctl", "fan-curve", "--mod-profile", mode, "--fan", "cpu", "--data", cpuGpuCurve)
	runCmd("asusctl", "fan-curve", "--mod-profile", mode, "--fan", "gpu", "--data", cpuGpuCurve)
	runCmd("asusctl", "fan-curve", "--mod-profile", mode, "--fan", "mid", "--data", midCurve)
	runCmd("asusctl", "fan-curve", "--mod-profile", mode, "--enable-fan-curves", "true")
}

func runCmd(name string, args ...string) error {
	out, err := exec.Command(name, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s %v: %w\noutput: %s", name, args, err, strings.TrimSpace(string(out)))
	}
	return nil
}

func reportToAI() {
	msg, _ := socket.NewMessage("report_power", "luminos-power", prevState)
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
