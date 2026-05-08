// Command luminos-power monitors AC adapter state and CPU temperature on the ASUS ROG G14,
// automatically applying power profiles via asusctl and reporting to luminos-ai.
// Fully automatic — no user interaction, no manual switching. See LUMINOS_PROJECT_SCOPE.md §Feature 2.
//
// Power profiles:
//   Unplugged → asusctl profile Quiet   (preserves battery)
//   Plugged in → asusctl profile Performance
//
// Fan curve (from LUMINOS_PROJECT_SCOPE.md §Feature 4):
//   < 50°C  → quiet    fan curve
//   50–65°C → balanced fan curve
//   65–85°C → performance fan curve
//   > 85°C  → max fan curve + force Quiet profile to protect hardware
//
// [CHANGE: gemini-cli | 2026-05-07] Lowered thresholds: Q->B at 50°C, B->P at 65°C.
// supergfxctl mode is NEVER changed — always stays Hybrid per project rules.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — luminos-power daemon.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
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
	FanMode   string    `json:"fan_mode"`
	Profile   string    `json:"profile"`
	UpdatedAt time.Time `json:"updated_at"`
}

var (
	lg        *logger.Logger
	cfg       *config.Config
	prevState PowerState
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

	lg.Info("luminos-power started — listening on %s", cfg.Sockets.Power)

	// monitorLoop runs the AC/thermal polling in the background.
	go monitorLoop(ctx)

	socket.Serve(ctx, l, handleMessage)

	os.Remove(cfg.Sockets.Power)
	lg.Info("luminos-power stopped")
}

// handleMessage answers status queries about current power/thermal state.
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

// monitorLoop polls AC adapter and CPU temperature every PollIntervalSecs seconds.
// It applies asusctl commands only when something changes, to avoid unnecessary execs.
func monitorLoop(ctx context.Context) {
	interval := time.Duration(cfg.Power.PollIntervalSecs) * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	// Apply initial power state immediately so the system is configured from the moment
	// the daemon starts (e.g., on boot while already on AC or already on battery).
	applyPowerState(readACState(), readCPUTemp())

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			applyPowerState(readACState(), readCPUTemp())
		}
	}
}

// readACState returns true if any "Mains" type power supply reports online=1.
// Reads /sys/class/power_supply/*/type and /sys/class/power_supply/*/online.
// Defaults to true (plugged in) on read error to avoid wrongly throttling a plugged machine.
func readACState() bool {
	entries, err := filepath.Glob("/sys/class/power_supply/*/type")
	if err != nil || len(entries) == 0 {
		return true // Assume plugged in on error.
	}
	for _, typePath := range entries {
		data, err := os.ReadFile(typePath)
		if err != nil {
			continue
		}
		if strings.TrimSpace(string(data)) != "Mains" {
			continue
		}
		onlinePath := filepath.Join(filepath.Dir(typePath), "online")
		onData, err := os.ReadFile(onlinePath)
		if err != nil {
			continue
		}
		if strings.TrimSpace(string(onData)) == "1" {
			return true
		}
	}
	return false
}

// readCPUTemp returns the highest temperature in °C found across all hwmon sensors.
// hwmon reports temperatures in millidegrees, so we divide by 1000.
// Returns 0 on error, which keeps the fan in quiet mode (safe default).
func readCPUTemp() float64 {
	entries, err := filepath.Glob("/sys/class/hwmon/hwmon*/temp*_input")
	if err != nil {
		return 0
	}
	var max float64
	for _, path := range entries {
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		milli, err := strconv.ParseFloat(strings.TrimSpace(string(data)), 64)
		if err != nil {
			continue
		}
		if c := milli / 1000.0; c > max {
			max = c
		}
	}
	return max
}

// applyPowerState compares current readings to prevState and calls asusctl only when
// something changed. This avoids hammering asusctl 30 times a minute when nothing changes.
func applyPowerState(onAC bool, tempC float64) {
	// [CHANGE: gemini-cli | 2026-05-07] Lowered thresholds to keep CPU near 50°C.
	// We select the profile based on AC state and temperature.
	profile := "Quiet"
	if onAC {
		switch {
		case tempC >= 65.0:
			profile = "Performance"
		case tempC >= 50.0:
			profile = "Balanced"
		default:
			profile = "Quiet"
		}
	}

	// Emergency throttle: if temp exceeds 85°C, force Quiet profile regardless of AC state
	// to protect hardware before the kernel's thermal throttle kicks in.
	if tempC > 85.0 {
		lg.Warn("CPU temp %.1f°C > 85°C — forcing Quiet profile to protect hardware", tempC)
		profile = "Quiet"
	}

	acChanged := onAC != prevState.OnAC
	profileChanged := profile != prevState.Profile

	if !acChanged && !profileChanged {
		return // Nothing changed — skip asusctl execs entirely.
	}

	lg.Info("state change: ac=%v temp=%.1f°C profile=%s", onAC, tempC, profile)

	// [CHANGE: gemini-cli | 2026-04-20] Updated to asusctl 6.3.6 'profile set <name>' syntax.
	// Independent fan-curve mode calls are removed as they are part of the profile.
	if profileChanged || acChanged {
		if err := runCmd("asusctl", "profile", "set", profile); err != nil {
			lg.Error("asusctl profile set %s: %v", profile, err)
		}
	}

	prevState = PowerState{
		OnAC:      onAC,
		CPUTempC:  tempC,
		FanMode:   profile, // Storing profile as 'fanMode' for legacy compatibility in JSON
		Profile:   profile,
		UpdatedAt: time.Now(),
	}

	// Notify luminos-ai so the central status endpoint stays accurate.
	reportToAI()
}
// [CHANGE: gemini-cli | 2026-04-20] fanModeForTemp removed; logic integrated into applyPowerState.
// runCmd executes a command and returns a descriptive error on non-zero exit.
func runCmd(name string, args ...string) error {
	out, err := exec.Command(name, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s %v: %w\noutput: %s", name, args, err, strings.TrimSpace(string(out)))
	}
	return nil
}

// reportToAI sends the current power state to luminos-ai for status aggregation.
// Failure is logged at DEBUG level only — luminos-ai may not be up yet at boot.
func reportToAI() {
	msg, err := socket.NewMessage("report_power", "luminos-power", prevState)
	if err != nil {
		lg.Error("build report_power: %v", err)
		return
	}
	if _, err := socket.Send(cfg.Sockets.AI, msg); err != nil {
		lg.Debug("report to luminos-ai (may not be running yet): %v", err)
	}
}

func replyOK(req socket.Message, payload interface{}) socket.Message {
	b, _ := json.Marshal(payload)
	return socket.Message{
		Type:      req.Type + "_response",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-power",
	}
}

func replyError(req socket.Message, errMsg string) socket.Message {
	b, _ := json.Marshal(map[string]string{"error": errMsg})
	return socket.Message{
		Type:      "error",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-power",
	}
}
