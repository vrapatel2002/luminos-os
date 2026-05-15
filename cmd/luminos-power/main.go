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
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
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
	// GPU gaming thresholds (unchanged from v2.1)
	gpuHighThreshPct   = 80.0
	gpuHighThreshTicks = 15 // 30s at 2s poll
	gpuLowThreshPct    = 20.0
	gpuLowThreshTicks  = 30 // 60s at 2s poll
	// Emergency thermal threshold
	thermalEmergencyC = 85.0
)

var (
	lg        *logger.Logger
	cfg       *config.Config
	prevState PowerState
	cpuCount  int

	gpuHighTicks int
	gpuLowTicks  int
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

	lg.Info("luminos-power v3.0 started — EPP-based control, listening on %s", cfg.Sockets.Power)

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

func monitorLoop(ctx context.Context) {
	// Start at 2s; adjusted below based on AC state
	interval := 2 * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			onAC := readACState()
			temp := readCPUTemp()
			gpuLoad := readGPULoad()

			// Detect AC transition → immediate response
			if onAC != prevState.OnAC {
				applyACTransition(onAC)
				// Adjust poll rate
				newInterval := batteryInterval(onAC)
				if newInterval != interval {
					interval = newInterval
					ticker.Reset(interval)
					lg.Info("poll interval → %v (on_ac=%v)", interval, onAC)
				}
			}

			// Emergency thermal: override EPP instantly, no delay
			if temp > thermalEmergencyC {
				lg.Warn("CPU temp %.1f°C > %.0f°C — Emergency: EPP=power + Quiet profile", temp, thermalEmergencyC)
				runCmd("asusctl", "profile", "set", "Quiet")
				setAllEPP("power") // after asusctl
				updateState(onAC, temp, gpuLoad, "power", "Quiet")
				gpuHighTicks = 0
				gpuLowTicks = 0
				continue
			}

			// GPU gaming detection (AC only — no Performance on battery)
			if onAC {
				profile := applyGamingDetection(gpuLoad, prevState.Profile)
				if profile != prevState.Profile {
					epp := eppForProfile(profile)
					runCmd("asusctl", "profile", "set", profile)
					// Write EPP after asusctl — asusctl overwrites EPP when setting profile
					setAllEPP(epp)
					updateState(onAC, temp, gpuLoad, epp, profile)
					continue
				}
			}

			updateState(onAC, temp, gpuLoad, prevState.EPP, prevState.Profile)
		}
	}
}

// applyACTransition handles the full set of changes when AC state changes.
// Called at startup and on every AC plug/unplug event.
func applyACTransition(onAC bool) {
	if onAC {
		lg.Info("AC plugged — applying AC power settings")
		setAllGovernor("powersave")
		setWiFiPowerSave(false)
		setKSM(true)
		setDisplayHz(120)
		runCmd("asusctl", "profile", "set", "Balanced")
		// Write EPP after asusctl — asusctl overwrites EPP when setting profile
		setAllEPP("balance_performance")
		prevState.EPP = "balance_performance"
		prevState.Profile = "Balanced"
	} else {
		lg.Info("AC unplugged — applying battery power settings")
		setAllGovernor("powersave")
		setWiFiPowerSave(true)
		setKSM(false)
		setDisplayHz(60)
		runCmd("asusctl", "profile", "set", "Quiet")
		// Write EPP after asusctl — asusctl overwrites EPP when setting profile
		setAllEPP("power")
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

func batteryInterval(onAC bool) time.Duration {
	if onAC {
		return 2 * time.Second
	}
	return 10 * time.Second
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
	lg.Info("Applying aggressive fan curve to %s profile", mode)
	curve := "30c:0,40c:20,50c:45,60c:65,70c:85,80c:100,90c:100,100c:100"
	runCmd("asusctl", "fan-curve", "--mod-profile", mode, "--fan", "cpu", "--data", curve)
	runCmd("asusctl", "fan-curve", "--mod-profile", mode, "--fan", "gpu", "--data", curve)
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
