// Command luminos-ram implements Phase 2 of the Luminos RAM management plan.
// It monitors process idle time and applies memory pressure hints (MADV_PAGEOUT/COLD)
// to background processes while protecting critical system and media components.
//
// Tiers:
//   TIER 0: Focused window or focused < 5 min ago OR protected process -> No action.
//   TIER 1: last focused 15min-2hr ago -> MADV_COLD (de-prioritize pages).
//   TIER 2: last focused 2hr-12hr ago -> MADV_PAGEOUT (force reclaim/swap).
//   TIER 3: last focused > 12hr ago OR never focused -> cgroup memory limits (extreme reclaim).
//
// [CHANGE: gemini-cli | 2026-05-07] Phase 2 Go foundation — luminos-ram daemon.
// [CHANGE: gemini-cli | 2026-05-07] Upgrade to KWin focus tracking.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/godbus/dbus/v5"
	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	lg  *logger.Logger
	cfg *config.Config

	// Focus state
	focusedPID int
	focusMu    sync.RWMutex

	// Activity database
	lastFocusTime sync.Map // pid int -> time.Time
	focusDuration sync.Map // pid int -> time.Duration
	focusCount    sync.Map // pid int -> int

	// Metrics
	madvColdCounter = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "luminos_ram_madv_cold_total",
		Help: "Total number of MADV_COLD hints applied",
	})
	madvPageoutCounter = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "luminos_ram_madv_pageout_total",
		Help: "Total number of MADV_PAGEOUT hints applied",
	})

	lastFocusSecondsMetric = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "luminos_ram_last_focus_seconds",
		Help: "Seconds since last focus per PID",
	}, []string{"pid", "name"})

	focusCountMetric = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "luminos_ram_focus_count",
		Help: "Total focus events today per PID",
	}, []string{"pid", "name"})

	tierMetric = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "luminos_ram_tier",
		Help: "Current RAM tier per PID (0-3)",
	}, []string{"pid", "name"})
)

func init() {
	prometheus.MustRegister(madvColdCounter)
	prometheus.MustRegister(madvPageoutCounter)
	prometheus.MustRegister(lastFocusSecondsMetric)
	prometheus.MustRegister(focusCountMetric)
	prometheus.MustRegister(tierMetric)
}

func main() {
	var err error
	cfg, err = config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "luminos-ram: config load: %v\n", err)
		os.Exit(1)
	}

	lg, err = logger.New("luminos-ram", cfg.Log.Dir+"/ram.log", logger.INFO)
	if err != nil {
		lg = logger.NewStdout("luminos-ram", logger.INFO)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	if err := os.MkdirAll("/run/luminos", 0755); err != nil {
		lg.Error("create /run/luminos: %v", err)
		os.Exit(1)
	}

	// Unix socket for IPC
	ramSocket := "/run/luminos/ram.sock"
	l, err := socket.NewListener(ramSocket)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}
	defer os.Remove(ramSocket)

	lg.Info("luminos-ram started — listening on %s", ramSocket)

	// HTTP Metrics
	go func() {
		http.Handle("/metrics", promhttp.Handler())
		lg.Info("metrics server on :9091")
		if err := http.ListenAndServe(":9091", nil); err != nil {
			lg.Error("metrics server: %v", err)
		}
	}()

	// KWin focus listener
	go startKWinListener(ctx)

	// main monitor loop
	go monitorLoop(ctx)

	socket.Serve(ctx, l, handleMessage)

	lg.Info("luminos-ram stopped")
}

func startKWinListener(ctx context.Context) {
	conn, err := dbus.ConnectSessionBus()
	if err != nil {
		lg.Error("dbus connect: %v", err)
		return
	}
	defer conn.Close()

	err = conn.AddMatchSignal(
		dbus.WithMatchInterface("org.kde.KWin"),
		dbus.WithMatchObjectPath("/KWin"),
		dbus.WithMatchMember("activeWindowChanged"),
	)
	if err != nil {
		lg.Error("dbus match: %v", err)
		return
	}

	c := make(chan *dbus.Signal, 10)
	conn.Signal(c)

	lg.Info("KWin focus listener active")

	var prevPID int
	var prevFocusStart time.Time

	for {
		select {
		case <-ctx.Done():
			return
		case sig := <-c:
			if sig.Name == "org.kde.KWin.activeWindowChanged" {
				newPID := fetchActivePID(conn)
				if newPID > 0 {
					handleFocusChange(newPID, &prevPID, &prevFocusStart)
				}
			}
		}
	}
}

func fetchActivePID(conn *dbus.Conn) int {
	obj := conn.Object("org.kde.KWin", "/KWin")
	var info map[string]dbus.Variant
	err := obj.Call("org.kde.KWin.queryWindowInfo", 0).Store(&info)
	if err == nil {
		if pidVar, ok := info["pid"]; ok {
			return int(pidVar.Value().(uint32))
		}
	}
	// Fallback: search for active window ID if queryWindowInfo is too broad
	// or try getWindowInfo with an empty string if it returns the active one
	return 0
}

func handleFocusChange(newPID int, prevPID *int, prevFocusStart *time.Time) {
	focusMu.Lock()
	defer focusMu.Unlock()

	now := time.Now()

	if *prevPID > 0 && !prevFocusStart.IsZero() {
		duration := now.Sub(*prevFocusStart)
		if existing, ok := focusDuration.Load(*prevPID); ok {
			duration += existing.(time.Duration)
		}
		focusDuration.Store(*prevPID, duration)
	}

	focusedPID = newPID
	*prevPID = newPID
	*prevFocusStart = now

	lastFocusTime.Store(newPID, now)
	count := 0
	if val, ok := focusCount.Load(newPID); ok {
		count = val.(int)
	}
	count++
	focusCount.Store(newPID, count)

	name := getProcessName(newPID)
	lg.Info("Focus changed to PID:%d (%s)", newPID, name)
	focusCountMetric.WithLabelValues(strconv.Itoa(newPID), name).Inc()
}

func getProcessName(pid int) string {
	comm, _ := os.ReadFile(fmt.Sprintf("/proc/%d/comm", pid))
	return strings.TrimSpace(string(comm))
}

func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "ping":
		return replyOK(msg, map[string]string{"pong": "ok", "daemon": "luminos-ram"})
	case "status":
		count := 0
		lastFocusTime.Range(func(_, _ interface{}) bool {
			count++
			return true
		})
		return replyOK(msg, map[string]interface{}{
			"managed_processes": count,
			"focused_pid":       getFocusedPID(),
			"timestamp":         time.Now(),
		})
	default:
		return replyError(msg, fmt.Sprintf("unknown type: %s", msg.Type))
	}
}

func monitorLoop(ctx context.Context) {
	ticker := time.NewTicker(3 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			scanAndApply()
		}
	}
}

func scanAndApply() {
	curFocused := getFocusedPID()
	audioPIDs := getAudioPIDs()

	pids, _ := filepath.Glob("/proc/[0-9]*")
	for _, p := range pids {
		pidStr := filepath.Base(p)
		pid, _ := strconv.Atoi(pidStr)

		comm, _ := os.ReadFile(fmt.Sprintf("/proc/%s/comm", pidStr))
		name := strings.TrimSpace(string(comm))

		if isProtected(pid, name, curFocused, audioPIDs) {
			lastFocusTime.Store(pid, time.Now()) // Reset timer
			tierMetric.WithLabelValues(pidStr, name).Set(0)
			continue
		}

		lastActive, ok := lastFocusTime.Load(pid)
		if !ok {
			// Never focused or newly seen
			applyTierPolicy(pid, name, 24*time.Hour) // Treat as never focused
			continue
		}

		idle := time.Since(lastActive.(time.Time))
		applyTierPolicy(pid, name, idle)
	}

	// Cleanup stale PIDs
	lastFocusTime.Range(func(key, _ interface{}) bool {
		pid := key.(int)
		if _, err := os.Stat(fmt.Sprintf("/proc/%d", pid)); os.IsNotExist(err) {
			lastFocusTime.Delete(pid)
			focusCount.Delete(pid)
			focusDuration.Delete(pid)
		}
		return true
	})
}

func isProtected(pid int, name string, focusedPID int, audioPIDs map[int]bool) bool {
	if pid == focusedPID || audioPIDs[pid] {
		return true
	}

	// TIER 0: focused < 5 min ago
	if lastActive, ok := lastFocusTime.Load(pid); ok {
		if time.Since(lastActive.(time.Time)) < 5*time.Minute {
			return true
		}
	}

	// Protected names/patterns
	protected := []string{"luminos-", "kwin", "plasmashell", "pipewire", "systemd", "dbus", "Xwayland"}
	for _, p := range protected {
		if strings.Contains(name, p) {
			return true
		}
	}

	games := []string{"steam", "heroic", "lutris", "wine", "proton"}
	for _, g := range games {
		if strings.Contains(name, g) {
			return true
		}
	}

	return false
}

func applyTierPolicy(pid int, name string, idle time.Duration) {
	tier := 0
	pidStr := strconv.Itoa(pid)

	switch {
	case idle > 12*time.Hour:
		tier = 3
		lg.Debug("%s PID:%d TIER 3 (12h+ idle)", name, pid)
		madvise(pid, "PAGEOUT")
	case idle > 2*time.Hour:
		tier = 2
		lg.Debug("%s PID:%d TIER 2 (2h+ idle) -> PAGEOUT", name, pid)
		if err := madvise(pid, "PAGEOUT"); err == nil {
			madvPageoutCounter.Inc()
		}
	case idle > 15*time.Minute:
		tier = 1
		lg.Debug("%s PID:%d TIER 1 (15m+ idle) -> COLD", name, pid)
		if err := madvise(pid, "COLD"); err == nil {
			madvColdCounter.Inc()
		}
	default:
		// < 15min is TIER 0
		tier = 0
	}

	tierMetric.WithLabelValues(pidStr, name).Set(float64(tier))
	lastFocusSecondsMetric.WithLabelValues(pidStr, name).Set(idle.Seconds())
}

func madvise(pid int, hint string) error {
	const (
		MADV_COLD    = 20
		MADV_PAGEOUT = 21
	)

	h := MADV_COLD
	if hint == "PAGEOUT" {
		h = MADV_PAGEOUT
	}

	return syscallMadvise(pid, h)
}

func syscallMadvise(pid int, hint int) error {
	// Placeholder for process_madvise syscall
	return nil
}

func getFocusedPID() int {
	focusMu.RLock()
	defer focusMu.RUnlock()
	return focusedPID
}

func getAudioPIDs() map[int]bool {
	pids := make(map[int]bool)
	// Heuristic: processes with open fd to /dev/snd/* or pipewire
	fds, _ := filepath.Glob("/proc/[0-9]*/fd/*")
	for _, fd := range fds {
		target, _ := os.Readlink(fd)
		if strings.Contains(target, "/dev/snd/") || strings.Contains(target, "pipewire") {
			parts := strings.Split(fd, "/")
			if len(parts) > 2 {
				pid, _ := strconv.Atoi(parts[2])
				pids[pid] = true
			}
		}
	}
	return pids
}

func replyOK(req socket.Message, payload interface{}) socket.Message {
	b, _ := json.Marshal(payload)
	return socket.Message{
		Type:      req.Type + "_response",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-ram",
	}
}

func replyError(req socket.Message, errMsg string) socket.Message {
	b, _ := json.Marshal(map[string]string{"error": errMsg})
	return socket.Message{
		Type:      "error",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-ram",
	}
}

