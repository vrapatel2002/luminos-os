// Command luminos-power monitors AC adapter state and CPU temperature on the ASUS ROG G14,
// automatically applying power profiles via asusctl and reporting to luminos-ai.
// Fully automatic — no user interaction, no manual switching.
//
// [CHANGE: gemini-cli | 2026-05-10] v2.1 Quiet Daily Driver
// Load-based switching: Quiet (Idle/Battery), Balanced (Heavy Work), Performance (Gaming).
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
	CPULoad   float64   `json:"cpu_load"`
	GPULoad   float64   `json:"gpu_load"`
	Profile   string    `json:"profile"`
	UpdatedAt time.Time `json:"updated_at"`
}

var (
	lg             *logger.Logger
	cfg            *config.Config
	prevState      PowerState
	lastChangeTime time.Time
	
	// History for triggers
	gpuHighTicks int // 30s threshold (15 ticks at 2s)
	gpuLowTicks  int // 60s threshold (30 ticks at 2s)
	cpuHighTicks int // 3m threshold (90 ticks at 2s) [CHANGE: v2.1]
	cpuLowTicks  int // 3m threshold (90 ticks at 2s) [CHANGE: v2.1]
	cpuCount     int
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

	lg.Info("luminos-power v2.1 started — listening on %s", cfg.Sockets.Power)

	// Apply aggressive fan curves to all modes
	applyAggressiveFanCurve("balanced")
	applyAggressiveFanCurve("quiet")

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
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			onAC := readACState()
			temp := readCPUTemp()
			cpuLoad := readCPULoad()
			gpuLoad := readGPULoad()
			applyPowerState(onAC, temp, cpuLoad, gpuLoad)
		}
	}
}

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
		if c := m / 1000.0; c > max { max = c }
	}
	return max
}

func readCPULoad() float64 {
	d, err := os.ReadFile("/proc/loadavg")
	if err != nil { return 0 }
	fields := strings.Fields(string(d))
	if len(fields) < 3 { return 0 }
	load, _ := strconv.ParseFloat(fields[2], 64)
	return load / float64(cpuCount)
}

func readGPULoad() float64 {
	matches, _ := filepath.Glob("/sys/class/drm/card*/device/gpu_busy_percent")
	var max float64
	for _, m := range matches {
		d, _ := os.ReadFile(m)
		val, _ := strconv.ParseFloat(strings.TrimSpace(string(d)), 64)
		if val > max { max = val }
	}
	return max
}

func applyPowerState(onAC bool, tempC, cpuLoad, gpuLoad float64) {
	// [CHANGE: gemini-cli | 2026-05-10] Smart Mode Switching Logic v2.1
	profile := prevState.Profile
	if profile == "" { profile = "Quiet" } // Default to Quiet

	// Battery: Always Quiet
	if !onAC {
		profile = "Quiet"
	} else {
		// 1. GPU Gaming Trigger -> Performance
		if gpuLoad > 80.0 {
			gpuHighTicks++
		} else {
			gpuHighTicks = 0
		}
		if gpuHighTicks >= 15 { // 30 seconds
			profile = "Performance"
		}

		// 2. GPU Idle Trigger -> Back from Performance
		if profile == "Performance" && gpuLoad < 20.0 {
			gpuLowTicks++
		} else {
			gpuLowTicks = 0
		}
		if gpuLowTicks >= 30 { // 60 seconds
			profile = "Balanced"
		}

		// 3. CPU Heavy Work -> Balanced (if in Quiet)
		// [CHANGE: v2.1] CPU > 40% for 3 minutes
		if profile == "Quiet" && cpuLoad > 0.4 {
			cpuHighTicks++
		} else {
			cpuHighTicks = 0
		}
		if cpuHighTicks >= 90 { // 180 seconds / 2s per tick = 90
			profile = "Balanced"
		}

		// 4. CPU Idle -> Quiet (if in Balanced)
		// [CHANGE: v2.1] CPU < 30% for 3 minutes
		if profile == "Balanced" && cpuLoad < 0.3 {
			cpuLowTicks++
		} else {
			cpuLowTicks = 0
		}
		if cpuLowTicks >= 90 { // 180 seconds
			profile = "Quiet"
		}

		// 5. Emergency Throttle (> 85C)
		if tempC > 85.0 {
			lg.Warn("CPU temp %.1f°C > 85°C — Emergency Quiet", tempC)
			profile = "Quiet"
		} else if profile == "Quiet" && prevState.Profile == "Quiet" && tempC < 75.0 && cpuLoad > 0.4 {
			// Recovery from emergency if load is still high
			profile = "Balanced"
		}
	}

	if profile == prevState.Profile && onAC == prevState.OnAC {
		return
	}

	// 30s Hold Time
	if onAC == prevState.OnAC && time.Since(lastChangeTime) < 30*time.Second {
		return
	}

	lg.Info("state change: profile=%s load=%.2f gpu=%.0f%% temp=%.1f°C", profile, cpuLoad, gpuLoad, tempC)

	if err := runCmd("asusctl", "profile", "set", profile); err != nil {
		lg.Error("asusctl profile set %s: %v", profile, err)
	}
	lastChangeTime = time.Now()

	prevState = PowerState{
		OnAC:      onAC,
		CPUTempC:  tempC,
		CPULoad:   cpuLoad,
		GPULoad:   gpuLoad,
		Profile:   profile,
		UpdatedAt: time.Now(),
	}
	reportToAI()
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
