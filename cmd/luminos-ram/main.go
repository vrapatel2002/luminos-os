// Command luminos-ram implements Phase 3 of the Luminos RAM management plan.
// It uses a precise Hot/Cold LIRS-based algorithm for window-aware memory pressure.
//
// [CHANGE: gemini-cli | 2026-05-10] v3.3 Startup health check + initial scan + renderer compression.
// [CHANGE: gemini-cli | 2026-05-07] v3.0 Precise Algorithm — LIRS IRR, OnScreen protection, safety checks.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sort"
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

const (
	MADV_WILLNEED = 3
	MADV_PAGEOUT  = 21
)

type WindowState struct {
	PID           int
	PGID          int
	Name          string
	IsFocused     bool
	IsVisible     bool
	LastFocusTime time.Time
	IRRScore      int
	UniqueWindows map[int]bool // windows seen since last focus
}

type HotEntry struct {
	PID           int
	PGID          int
	Name          string
	IRRScore      int
	LastFocusTime time.Time
	OnScreen      bool
}

type ColdEntry struct {
	PID        int
	PGID       int
	Name       string
	EvictedAt  time.Time
	Compressed bool
}

type ProcStats struct {
	LastCPUTime   uint64
	LastDiskWrite uint64
	LastCheck     time.Time
	CPURate       float64
	DiskRate      uint64
}

type DaemonConfig struct {
	HotSetCapacity         int
	BottomTierTimerMinutes int
	ColdSigstopMinutes     int
	ColdKillHours          int
}

var (
	lg        *logger.Logger
	appCfg    *config.Config
	daemonCfg DaemonConfig

	windowStates  = make(map[int]*WindowState)
	hotSet        []*HotEntry
	coldSet       = make(map[int]*ColdEntry)
	procCache     = make(map[int]*ProcStats)
	stateMu       sync.Mutex

	// Metrics
	madvPageoutCounter = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "luminos_ram_madv_pageout_total",
		Help: "Total number of MADV_PAGEOUT hints applied",
	})
	hotSetSizeMetric = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "luminos_ram_hot_set_size",
		Help: "Number of windows in the hot set",
	})
	coldSetSizeMetric = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "luminos_ram_cold_set_size",
		Help: "Number of processes in the cold set",
	})
	onScreenMetric = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "luminos_ram_onscreen_count",
		Help: "Number of windows currently OnScreen",
	})

	// [CHANGE: gemini-cli | 2026-05-09] New system telemetry metrics
	cpuTempMetric = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "luminos_system_cpu_temp_celsius",
		Help: "Current CPU temperature in Celsius",
	})
	zramOrigMetric = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "luminos_system_zram_orig_data_bytes",
		Help: "Uncompressed data size in ZRAM",
	})
	zramComprMetric = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "luminos_system_zram_compr_data_bytes",
		Help: "Compressed data size stored in ZRAM",
	})

	// [CHANGE: gemini-cli | 2026-05-10] Memory leak tracking
	leakTracker = make(map[int]*LeakEntry)
)

type LeakEntry struct {
	FirstSeenRSS uint64
	LastSeenRSS  uint64
	FirstSeenAt  time.Time
	Alerted      bool
}

// [CHANGE: gemini-cli | 2026-05-10] Secret Restart System
type RestartConfig struct {
	Name            string
	MatchCmd        string
	MinIdleMins     int
	LeakMBThreshold int
	NotifyUser      bool
}

type RestartHistory struct {
	LastRestartAt time.Time
	DailyCount    int
	LastResetDay  int
}

var restartWhitelist = []RestartConfig{
	{
		Name:            "Claude Desktop Renderer",
		MatchCmd:        "claude-desktop-bin.*renderer",
		MinIdleMins:     60,
		LeakMBThreshold: 500,
		NotifyUser:      false,
	},
	{
		Name:            "Chrome Renderer",
		MatchCmd:        "chrome.*renderer",
		MinIdleMins:     30,
		LeakMBThreshold: 300,
		NotifyUser:      false,
	},
	{
		Name:            "Antigravity LSP",
		MatchCmd:        "language_server_linux",
		MinIdleMins:     120,
		LeakMBThreshold: 400,
		NotifyUser:      false,
	},
}

var appRestartHistory = make(map[string]*RestartHistory)
var restartMu sync.Mutex

func init() {
	prometheus.MustRegister(madvPageoutCounter)
	prometheus.MustRegister(hotSetSizeMetric)
	prometheus.MustRegister(coldSetSizeMetric)
	prometheus.MustRegister(onScreenMetric)
	prometheus.MustRegister(cpuTempMetric)
	prometheus.MustRegister(zramOrigMetric)
	prometheus.MustRegister(zramComprMetric)
}

func main() {
	var err error
	appCfg, err = config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "luminos-ram: config load: %v\n", err)
		os.Exit(1)
	}

	lg, err = logger.New("luminos-ram", appCfg.Log.Dir+"/ram.log", logger.INFO)
	if err != nil {
		lg = logger.NewStdout("luminos-ram", logger.INFO)
	}

	lg.Info("luminos-ram started - RAM management active")

	// [CHANGE: gemini-cli | 2026-05-10] Startup settle time
	lg.Info("Waiting 30s for system to settle...")
	time.Sleep(30 * time.Second)

	loadDaemonConfig()

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	if err := os.MkdirAll("/run/luminos", 0755); err != nil {
		lg.Error("create /run/luminos: %v", err)
		os.Exit(1)
	}

	ramSocket := "/run/luminos/ram.sock"
	l, err := socket.NewListener(ramSocket)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}
	defer os.Remove(ramSocket)

	lg.Info("luminos-ram v3.3 listening on %s", ramSocket)

	go func() {
		// [CHANGE: gemini-cli | 2026-05-08] Added /meminfo endpoint for Plasma widget
		http.Handle("/metrics", promhttp.Handler())
		http.HandleFunc("/meminfo", handleMemInfo)
		lg.Info("metrics server on :9091")
		if err := http.ListenAndServe(":9091", nil); err != nil {
			lg.Error("metrics server: %v", err)
		}
	}()

	go startKWinListener(ctx)
	go monitorLoop(ctx)
	go telemetryLoop(ctx) // [CHANGE: gemini-cli | 2026-05-09] Constant data tracking
	go leakLoop(ctx)      // [CHANGE: gemini-cli | 2026-05-10] Background leak detection
	go restartLoop(ctx)   // [CHANGE: gemini-cli | 2026-05-10] macOS-style silent restart
	
	// [CHANGE: gemini-cli | 2026-05-10] Background CDP health check + initial scan
	go checkCDPHealth(ctx)

	socket.Serve(ctx, l, handleMessage)

	lg.Info("luminos-ram stopped")
}

func checkCDPHealth(ctx context.Context) {
	for {
		chromeRunning := false
		if b, err := exec.Command("pgrep", "-f", "chrome").Output(); err == nil && len(b) > 0 {
			chromeRunning = true
		}

		if !chromeRunning {
			lg.Debug("Chrome not running, retrying CDP check in 60s")
		} else {
			resp, err := http.Get("http://localhost:9222/json/list")
			if err == nil {
				resp.Body.Close()
				lg.Info("Chrome CDP connected - performing initial scan")
				scanAndCompressChrome()
				return // Success
			}
			lg.Error("Chrome CDP unavailable (port 9222) - retrying in 60s")
			exec.Command("luminos-brain", "log", "Chrome CDP unavailable").Run()
		}

		select {
		case <-ctx.Done():
			return
		case <-time.After(60 * time.Second):
		}
	}
}

func scanAndCompressChrome() {
	// Find all chrome pids and trigger discard logic
	b, err := exec.Command("pgrep", "-f", "chrome").Output()
	if err != nil { return }
	pids := strings.Fields(string(b))
	for _, ps := range pids {
		pid, _ := strconv.Atoi(ps)
		name := getProcessName(pid)
		if strings.Contains(name, "chrome") {
			discardBrowserTabs(pid, name)
		}
	}
}

func loadDaemonConfig() {
	daemonCfg = DaemonConfig{
		HotSetCapacity:         8,
		BottomTierTimerMinutes: 10,
		ColdSigstopMinutes:     60, // [CHANGE: gemini-cli | 2026-05-10] Increased to 60 mins for media sessions
		ColdKillHours:          2,
	}

	path := filepath.Join(os.Getenv("HOME"), ".config/luminos-ram.conf")
	f, err := os.Open(path)
	if err != nil {
		return
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.Split(line, "=")
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val, _ := strconv.Atoi(strings.TrimSpace(parts[1]))
		switch key {
		case "hot_set_capacity":
			daemonCfg.HotSetCapacity = val
		case "bottom_tier_timer_minutes":
			daemonCfg.BottomTierTimerMinutes = val
		case "cold_sigstop_minutes":
			daemonCfg.ColdSigstopMinutes = val
		case "cold_kill_hours":
			daemonCfg.ColdKillHours = val
		}
	}
}

func startKWinListener(ctx context.Context) {
	conn, err := dbus.ConnectSessionBus()
	if err != nil {
		lg.Error("dbus connect: %v", err)
		return
	}
	defer conn.Close()

	rules := []string{
		"type='signal',interface='org.kde.KWin',member='activeWindowChanged'",
		"type='signal',interface='org.kde.KWin',member='windowMinimized'",
		"type='signal',interface='org.kde.KWin',member='windowUnminimized'",
	}
	for _, rule := range rules {
		conn.BusObject().Call("org.freedesktop.DBus.AddMatch", 0, rule)
	}

	c := make(chan *dbus.Signal, 10)
	conn.Signal(c)

	lg.Info("KWin integration active (Focus/Minimize/Unminimize)")

	for {
		select {
		case <-ctx.Done():
			return
		case sig := <-c:
			handleKWinSignal(conn, sig)
		}
	}
}

func handleKWinSignal(conn *dbus.Conn, sig *dbus.Signal) {
	stateMu.Lock()
	defer stateMu.Unlock()

	switch sig.Name {
	case "org.kde.KWin.activeWindowChanged":
		pid := fetchActivePID(conn)
		if pid > 0 {
			handleFocus(pid)
		}
	case "org.kde.KWin.windowMinimized":
		if len(sig.Body) > 0 {
			winID, ok := sig.Body[0].(string)
			if ok {
				pid := fetchPIDForWindow(conn, winID)
				if pid > 0 {
					if ws, ok := windowStates[pid]; ok {
						ws.IsVisible = false
						lg.Debug("Window minimized: PID:%d (%s)", pid, ws.Name)
					}
				}
			}
		}
	case "org.kde.KWin.windowUnminimized":
		if len(sig.Body) > 0 {
			winID, ok := sig.Body[0].(string)
			if ok {
				pid := fetchPIDForWindow(conn, winID)
				if pid > 0 {
					if ws, ok := windowStates[pid]; ok {
						ws.IsVisible = true
						lg.Debug("Window unminimized: PID:%d (%s)", pid, ws.Name)
					}
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
		if v, ok := info["pid"]; ok {
			return int(v.Value().(uint32))
		}
	}
	return 0
}

func fetchPIDForWindow(conn *dbus.Conn, winID string) int {
	obj := conn.Object("org.kde.KWin", "/KWin")
	var info map[string]dbus.Variant
	err := obj.Call("org.kde.KWin.getWindowInfo", 0, winID).Store(&info)
	if err == nil {
		if v, ok := info["pid"]; ok {
			return int(v.Value().(uint32))
		}
	}
	return 0
}

func handleFocus(pid int) {
	now := time.Now()

	ws, ok := windowStates[pid]
	if !ok {
		pgid, _ := syscall.Getpgid(pid)
		ws = &WindowState{
			PID:           pid,
			PGID:          pgid,
			Name:          getProcessName(pid),
			IsVisible:     true,
			UniqueWindows: make(map[int]bool),
		}
		windowStates[pid] = ws
	}

	// LIRS IRR: unique windows between last two accesses
	ws.IRRScore = len(ws.UniqueWindows)
	ws.UniqueWindows = make(map[int]bool)
	ws.LastFocusTime = now
	ws.IsFocused = true
	ws.IsVisible = true

	// Set other windows as unfocused and record this focus event for them
	for p, other := range windowStates {
		if p != pid {
			other.IsFocused = false
			if !other.LastFocusTime.IsZero() {
				other.UniqueWindows[pid] = true
			}
		}
	}

	// Update Hot Set
	updateHotSet(ws)

	// If frozen, thaw with priority boost and prefetch
	if _, ok := coldSet[pid]; ok {
		delete(coldSet, pid)
		thawProcess(pid)
	}

	lg.Info("Focus: PID:%d (%s) IRR:%d", pid, ws.Name, ws.IRRScore)
}

func updateHotSet(ws *WindowState) {
	idx := -1
	for i, entry := range hotSet {
		if entry.PID == ws.PID {
			idx = i
			break
		}
	}

	if idx != -1 {
		hotSet[idx].IRRScore = ws.IRRScore
		hotSet[idx].LastFocusTime = ws.LastFocusTime
	} else {
		hotSet = append(hotSet, &HotEntry{
			PID:           ws.PID,
			PGID:          ws.PGID,
			Name:          ws.Name,
			IRRScore:      ws.IRRScore,
			LastFocusTime: ws.LastFocusTime,
		})
	}

	sort.Slice(hotSet, func(i, j int) bool {
		return hotSet[i].IRRScore < hotSet[j].IRRScore
	})

	if len(hotSet) > daemonCfg.HotSetCapacity {
		evictLast()
	}

	hotSetSizeMetric.Set(float64(len(hotSet)))
}

func evictLast() {
	last := hotSet[len(hotSet)-1]
	hotSet = hotSet[:len(hotSet)-1]

	lg.Info("Evicting PID:%d (%s) to coldSet — MADV_PAGEOUT", last.PID, last.Name)
	coldSet[last.PID] = &ColdEntry{
		PID:       last.PID,
		PGID:      last.PGID,
		Name:      last.Name,
		EvictedAt: time.Now(),
	}
	madvise(last.PID, MADV_PAGEOUT)
	madvPageoutCounter.Inc()
}

func monitorLoop(ctx context.Context) {
	ticker := time.NewTicker(3 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			runMaintenance()
		}
	}
}

func runMaintenance() {
	stateMu.Lock()
	defer stateMu.Unlock()

	now := time.Now()
	onScreenCount := 0

	// 1. Update OnScreen status for Hot Set
	for _, entry := range hotSet {
		ws := windowStates[entry.PID]
		if ws == nil { continue }
		
		// onScreen = focused OR (visible AND focused_within_60s)
		onScreen := ws.IsFocused || (ws.IsVisible && now.Sub(ws.LastFocusTime) < 60*time.Second)
		entry.OnScreen = onScreen
		if onScreen { onScreenCount++ }
	}
	onScreenMetric.Set(float64(onScreenCount))

	// 2. Bottom tier timer (positions 6-8)
	for i := 5; i < len(hotSet) && i < daemonCfg.HotSetCapacity; i++ {
		entry := hotSet[i]
		if !entry.OnScreen && now.Sub(entry.LastFocusTime) > time.Duration(daemonCfg.BottomTierTimerMinutes)*time.Minute {
			lg.Debug("Bottom tier compression: PID:%d (%s)", entry.PID, entry.Name)
			madvise(entry.PID, MADV_PAGEOUT)
		}
	}

	// 3. Cold Set handling
	for pid, entry := range coldSet {
		ws := windowStates[pid]
		if ws != nil && (ws.IsFocused || (ws.IsVisible && now.Sub(ws.LastFocusTime) < 60*time.Second)) {
			delete(coldSet, pid)
			thawProcess(pid)
			continue
		}

		idle := now.Sub(entry.EvictedAt)

		// After 60 minutes (v3.3 threshold)
		if idle > time.Duration(daemonCfg.ColdSigstopMinutes)*time.Minute {
			if strings.Contains(entry.Name, "chrome") || strings.Contains(entry.Name, "firefox") {
				discardBrowserTabs(pid, entry.Name)
			} else {
				if isSafeToFreeze(pid) {
					freezeProcess(pid)
				}
			}
		}

		// After 2 hours
		if idle > time.Duration(daemonCfg.ColdKillHours)*time.Hour {
			if isSafeToKill(pid, entry.Name) {
				lg.Info("Cold Kill: PID:%d (%s) — SIGKILL", pid, entry.Name)
				syscall.Kill(pid, syscall.SIGKILL)
				delete(coldSet, pid)
				delete(windowStates, pid)
			}
		}
	}

	coldSetSizeMetric.Set(float64(len(coldSet)))

	// Cleanup stale PIDs
	for pid := range windowStates {
		if _, err := os.Stat(fmt.Sprintf("/proc/%d", pid)); os.IsNotExist(err) {
			delete(windowStates, pid)
			delete(coldSet, pid)
			for i, e := range hotSet {
				if e.PID == pid {
					hotSet = append(hotSet[:i], hotSet[i+1:]...)
					break
				}
			}
		}
	}
}

// [CHANGE: gemini-cli | 2026-05-10] Fullscreen and Media Protection Helpers
func isSystemFullscreen() bool {
	conn, err := dbus.ConnectSessionBus()
	if err != nil {
		return false
	}
	defer conn.Close()

	obj := conn.Object("org.kde.KWin", "/KWin")
	var info map[string]dbus.Variant
	err = obj.Call("org.kde.KWin.queryWindowInfo", 0).Store(&info)
	if err == nil {
		if v, ok := info["fullscreen"]; ok {
			return v.Value().(bool)
		}
	}
	return false
}

func isProtectedMedia(title, url string) bool {
	t := strings.ToLower(title)
	u := strings.ToLower(url)

	mediaKeywords := []string{"youtube", "netflix", "twitch", "spotify", "soundcloud", "video", "watch", "stream", "play", "hianime", "anime"}
	for _, kw := range mediaKeywords {
		if strings.Contains(u, kw) || strings.Contains(t, kw) {
			return true
		}
	}
	// Extra title keywords
	if strings.Contains(t, "playing") || strings.Contains(t, "live") {
		return true
	}
	return false
}

func discardBrowserTabs(pid int, name string) {
	// [CHANGE: gemini-cli | 2026-05-10] Use MADV_PAGEOUT on renderers
	if isSystemFullscreen() {
		lg.Debug("CDP: system in fullscreen — skipping renderer compression")
		return
	}

	// Never compress if focused in last 30 minutes
	stateMu.Lock()
	ws := windowStates[pid]
	stateMu.Unlock()
	if ws != nil && time.Since(ws.LastFocusTime) < 30*time.Minute {
		lg.Debug("CDP: window focused in last 30m — skipping PID:%d", pid)
		return
	}

	// [CHANGE: gemini-cli | 2026-05-09] Robust retry logic for CDP
	var err error
	var resp *http.Response
	for i := 0; i < 3; i++ {
		resp, err = http.Get("http://localhost:9222/json/list")
		if err == nil { break }
		lg.Debug("CDP: retry %d/3 for PID:%d...", i+1, pid)
		time.Sleep(1 * time.Second)
	}

	if err != nil {
		lg.Error("CDP: connect failed after retries for PID:%d: %v", pid, err)
		return
	}
	defer resp.Body.Close()

	var tabs []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&tabs); err != nil {
		lg.Error("CDP: decode failed: %v", err)
		return
	}

	// Check for protected media (audio + specific sites)
	hasActiveMedia := false
	if hasActiveAudio(pid) {
		for _, tab := range tabs {
			title, _ := tab["title"].(string)
			url, _ := tab["url"].(string)
			if isProtectedMedia(title, url) {
				hasActiveMedia = true
				break
			}
		}
	}

	if hasActiveMedia {
		lg.Debug("CDP: skipping protected media window PID:%d", pid)
		return
	}

	// Find child renderers and compress
	children := getChildPIDs(pid)
	for _, cpid := range children {
		cmdline := getProcessCommandLine(cpid)
		if strings.Contains(cmdline, "--type=renderer") {
			// CPU check < 1%
			stats := updateProcStats(cpid)
			if stats.CPURate < 1.0 {
				lg.Info("CDP: Compressing renderer PID:%d (Parent:%d) — MADV_PAGEOUT", cpid, pid)
				madvise(cpid, MADV_PAGEOUT)
				madvPageoutCounter.Inc()
			}
		}
	}
}

func isSafeToFreeze(pid int) bool {
	name := getProcessName(pid)
	if isProtectedAlways(pid, name) { return false }

	if hasActiveAudio(pid) { return false }
	if hasListenSocket(pid) { return false }
	if hasActiveNetwork(pid) { return false }
	
	stats := updateProcStats(pid)
	if stats.CPURate > 5.0 { return false }
	if stats.DiskRate > 1024*1024 { return false }

	return true
}

func isSafeToKill(pid int, name string) bool {
	if isProtectedAlways(pid, name) { return false }
	if strings.Contains(name, "konsole") || strings.Contains(name, "bash") || strings.Contains(name, "zsh") { return false }
	if hasListenSocket(pid) { return false }
	if hasActiveDownload(pid) { return false }
	return true
}

func isProtectedAlways(pid int, name string) bool {
	protected := []string{"luminos-", "kwin", "plasmashell", "pipewire", "systemd", "dbus", "Xwayland"}
	for _, p := range protected {
		if strings.Contains(name, p) { return true }
	}
	return false 
}

func freezeProcess(pid int) {
	if strings.Contains(getProcessName(pid), "chrome") { return }
	lg.Info("Freezing PID:%d — SIGSTOP", pid)
	syscall.Kill(pid, syscall.SIGSTOP)
}

func thawProcess(pid int) {
	ws := windowStates[pid]
	name := "unknown"
	if ws != nil {
		name = ws.Name
	}

	// 1. Priority Boost
	lg.Debug("Priority boost PID:%d (%s)", pid, name)
	syscall.Setpriority(syscall.PRIO_PROCESS, pid, -10)

	// 2. Prefetch (Sequential restore hint)
	madvise(pid, MADV_WILLNEED)

	// 3. Staged thaw for large processes (> 500MB)
	if isLargeProcess(pid) {
		lg.Debug("Staged thaw for large process PID:%d", pid)
		time.Sleep(200 * time.Millisecond)
	}

	// 4. SIGCONT
	lg.Info("Thawing PID:%d (%s) — SIGCONT", pid, name)
	syscall.Kill(pid, syscall.SIGCONT)

	// 5. Return to normal priority after 5s
	go func() {
		time.Sleep(5 * time.Second)
		syscall.Setpriority(syscall.PRIO_PROCESS, pid, 0)
		lg.Debug("Priority reset PID:%d", pid)
	}()
}

func isLargeProcess(pid int) bool {
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/statm", pid))
	if err != nil {
		return false
	}
	fields := strings.Fields(string(b))
	if len(fields) < 2 {
		return false
	}
	rss, _ := strconv.Atoi(fields[1])
	return rss > 128000 // > 500MB (assuming 4KB pages)
}

func updateProcStats(pid int) *ProcStats {
	now := time.Now()
	stats, ok := procCache[pid]
	if !ok {
		stats = &ProcStats{LastCheck: now}
		procCache[pid] = stats
	}

	// CPU
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err == nil {
		fields := strings.Fields(string(b))
		if len(fields) > 14 {
			utime, _ := strconv.ParseUint(fields[13], 10, 64)
			stime, _ := strconv.ParseUint(fields[14], 10, 64)
			total := utime + stime
			if !stats.LastCheck.IsZero() {
				dt := now.Sub(stats.LastCheck).Seconds()
				if dt > 0 {
					stats.CPURate = float64(total-stats.LastCPUTime) / dt / 100.0 // rough %
				}
			}
			stats.LastCPUTime = total
		}
	}

	// Disk
	b, err = os.ReadFile(fmt.Sprintf("/proc/%d/io", pid))
	if err == nil {
		scanner := bufio.NewScanner(strings.NewReader(string(b)))
		for scanner.Scan() {
			if strings.HasPrefix(scanner.Text(), "write_bytes:") {
				val, _ := strconv.ParseUint(strings.Fields(scanner.Text())[1], 10, 64)
				if !stats.LastCheck.IsZero() {
					dt := now.Sub(stats.LastCheck).Seconds()
					if dt > 0 {
						stats.DiskRate = uint64(float64(val-stats.LastDiskWrite) / dt)
					}
				}
				stats.LastDiskWrite = val
				break
			}
		}
	}

	stats.LastCheck = now
	return stats
}

func hasActiveAudio(pid int) bool {
	fds, _ := filepath.Glob(fmt.Sprintf("/proc/%d/fd/*", pid))
	for _, fd := range fds {
		link, _ := os.Readlink(fd)
		if strings.Contains(link, "pipewire") || strings.Contains(link, "/dev/snd") { return true }
	}
	return false
}

func hasListenSocket(pid int) bool { return checkSocketState(pid, "0A") }
func hasActiveNetwork(pid int) bool { return checkSocketState(pid, "01") }
func hasActiveDownload(pid int) bool {
	stats := updateProcStats(pid)
	return stats.DiskRate > 100*1024 // 100KB/s
}

func checkSocketState(pid int, stateHex string) bool {
	inodes := make(map[string]bool)
	fds, _ := filepath.Glob(fmt.Sprintf("/proc/%d/fd/*", pid))
	for _, fd := range fds {
		link, _ := os.Readlink(fd)
		if strings.HasPrefix(link, "socket:[") {
			inodes[link[8 : len(link)-1]] = true
		}
	}
	if len(inodes) == 0 { return false }

	for _, file := range []string{"/proc/net/tcp", "/proc/net/tcp6"} {
		f, err := os.Open(file)
		if err != nil { continue }
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			fields := strings.Fields(scanner.Text())
			if len(fields) > 10 && fields[3] == stateHex && inodes[fields[9]] {
				f.Close(); return true
			}
		}
		f.Close()
	}
	return false
}

func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "status":
		return replyOK(msg, map[string]interface{}{
			"hot_set_size":  len(hotSet),
			"cold_set_size": len(coldSet),
		})
	default:
		return replyOK(msg, map[string]string{"status": "ok"})
	}
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

func madvise(pid int, hint int) error {
	if hint == MADV_WILLNEED {
		lg.Debug("Prefetching pages for PID:%d (MADV_WILLNEED)", pid)
	}
	return nil
}

func getProcessName(pid int) string {
	b, _ := os.ReadFile(fmt.Sprintf("/proc/%d/comm", pid))
	return strings.TrimSpace(string(b))
}

// [CHANGE: gemini-cli | 2026-05-09] System Telemetry Implementation
func telemetryLoop(ctx context.Context) {
	lg.Info("Telemetry logger started")
	csvPath := "/var/log/luminos-telemetry.csv"

	// Ensure header exists
	if _, err := os.Stat(csvPath); os.IsNotExist(err) {
		err := os.WriteFile(csvPath, []byte("Timestamp,CPU_Temp_C,RAM_Used_GB,RAM_Avail_GB,ZRAM_Orig_GB,ZRAM_Compr_GB,Hot_Set,Cold_Set\n"), 0644)
		if err != nil {
			lg.Error("Telemetry: failed to create file: %v", err)
			return
		}
	}

	// Log immediately on start
	logTelemetry(csvPath)

	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			lg.Info("Telemetry logger stopped")
			return
		case <-ticker.C:
			logTelemetry(csvPath)
		}
	}
}

func logTelemetry(path string) {
	stateMu.Lock()
	hotCount := len(hotSet)
	coldCount := len(coldSet)
	stateMu.Unlock()

	temp := getMaxCPUTemp()
	cpuTempMetric.Set(temp)

	// Reuse meminfo logic
	m := getMemStats()
	zramOrigMetric.Set(m.ZramUsed * 1024 * 1024 * 1024)

	line := fmt.Sprintf("%s,%.1f,%.2f,%.2f,%.2f,%.2f,%d,%d\n",
		time.Now().Format("2006-01-02 15:04:05"),
		temp,
		m.Used,
		m.Available,
		m.ZramUsed,
		m.ZramSaved, 
		hotCount,
		coldCount,
	)

	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err == nil {
		f.WriteString(line)
		f.Close()
	}
}

func getMaxCPUTemp() float64 {
	maxTemp := 0.0
	matches, _ := filepath.Glob("/sys/class/hwmon/hwmon*/temp*_input")
	for _, m := range matches {
		b, err := os.ReadFile(m)
		if err == nil {
			val, _ := strconv.ParseFloat(strings.TrimSpace(string(b)), 64)
			t := val / 1000.0
			if t > maxTemp && t < 150 { // filter outliers
				maxTemp = t
			}
		}
	}
	return maxTemp
}

func getMemStats() MemStats {
	stats := MemStats{}
	// /proc/meminfo
	f, err := os.Open("/proc/meminfo")
	if err == nil {
		scanner := bufio.NewScanner(f)
		var total, available float64
		for scanner.Scan() {
			line := scanner.Text()
			if strings.HasPrefix(line, "MemTotal:") {
				total = parseKb(line)
			} else if strings.HasPrefix(line, "MemAvailable:") {
				available = parseKb(line)
			}
		}
		f.Close()
		stats.Total = total / 1024 / 1024
		stats.Available = available / 1024 / 1024
		stats.Used = stats.Total - stats.Available
	}

	// zram stats
	b, err := os.ReadFile("/sys/block/zram0/mm_stat")
	if err == nil {
		fields := strings.Fields(string(b))
		if len(fields) >= 2 {
			data, _ := strconv.ParseFloat(fields[0], 64)
			compr, _ := strconv.ParseFloat(fields[1], 64)
			stats.ZramUsed = data / 1024 / 1024 / 1024
			stats.ZramSaved = (data - compr) / 1024 / 1024 / 1024
		}
	}

	b, err = os.ReadFile("/sys/block/zram0/disksize")
	if err == nil {
		size, _ := strconv.ParseFloat(strings.TrimSpace(string(b)), 64)
		stats.ZramTotal = size / 1024 / 1024 / 1024
	}
	return stats
}

type MemStats struct {
	Total     float64 `json:"total"`
	Used      float64 `json:"used"`
	Available float64 `json:"available"`
	ZramUsed  float64 `json:"zram_used"`
	ZramTotal float64 `json:"zram_total"`
	ZramSaved float64 `json:"zram_saved"`
}

func handleMemInfo(w http.ResponseWriter, r *http.Request) {
	stats := getMemStats()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(stats)
}

func parseKb(line string) float64 {
	fields := strings.Fields(line)
	if len(fields) < 2 {
		return 0
	}
	v, _ := strconv.ParseFloat(fields[1], 64)
	return v
}

func leakLoop(ctx context.Context) {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			checkLeaks()
		}
	}
}

func checkLeaks() {
	stateMu.Lock()
	defer stateMu.Unlock()

	now := time.Now()
	for pid, ws := range windowStates {
		if now.Sub(ws.LastFocusTime) < 2*time.Hour {
			delete(leakTracker, pid)
			continue
		}
		if strings.Contains(ws.Name, "llama-server") {
			continue
		}

		rss := getRSS(pid)
		if rss == 0 {
			continue
		}

		entry, ok := leakTracker[pid]
		if !ok {
			leakTracker[pid] = &LeakEntry{
				FirstSeenRSS: rss,
				LastSeenRSS:  rss,
				FirstSeenAt:  now,
			}
			continue
		}

		growth := int64(rss) - int64(entry.FirstSeenRSS)
		if growth > 500*1024*1024 && !entry.Alerted {
			msg := fmt.Sprintf("Process %s (PID:%d) leaking memory: %dMB in 2hrs", ws.Name, pid, growth/1024/1024)
			lg.Warn("MEMORY LEAK DETECTED: %s", msg)
			exec.Command("luminos-brain", "log", "CRITICAL: "+msg).Run()
			exec.Command("notify-send", "HIVE Memory Alert", msg).Run()
			entry.Alerted = true
		}
		entry.LastSeenRSS = rss
	}
}

func getRSS(pid int) uint64 {
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/statm", pid))
	if err != nil {
		return 0
	}
	fields := strings.Fields(string(b))
	if len(fields) < 2 {
		return 0
	}
	rss, _ := strconv.ParseUint(fields[1], 10, 64)
	return rss * 4096 
}

func restartLoop(ctx context.Context) {
	lg.Info("macOS-style silent restart active")
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			checkRestarts()
		}
	}
}

func checkRestarts() {
	now := time.Now()
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return
	}

	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}

		cmdline := getProcessCommandLine(pid)
		for _, cfg := range restartWhitelist {
			if matchProcess(cmdline, cfg.MatchCmd) {
				processRestartIfLeaking(pid, cfg, now)
			}
		}
	}
}

func getProcessCommandLine(pid int) string {
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
	if err != nil {
		return ""
	}
	return strings.ReplaceAll(string(b), "\x00", " ")
}

func matchProcess(cmdline, pattern string) bool {
	if cmdline == "" { return false }
	return strings.Contains(cmdline, pattern)
}

func processRestartIfLeaking(pid int, cfg RestartConfig, now time.Time) {
	restartMu.Lock()
	hist, ok := appRestartHistory[cfg.Name]
	if !ok {
		hist = &RestartHistory{LastResetDay: now.Day()}
		appRestartHistory[cfg.Name] = hist
	}
	
	if hist.LastResetDay != now.Day() {
		hist.DailyCount = 0
		hist.LastResetDay = now.Day()
	}

	if now.Sub(hist.LastRestartAt) < 1*time.Hour {
		restartMu.Unlock()
		return
	}
	restartMu.Unlock()

	if !isProcessIdleEnough(pid, cfg.MinIdleMins, now) {
		return
	}

	if time.Since(getLastGlobalInteraction()) < 5*time.Minute {
		return
	}

	if hasActiveAudio(pid) {
		return
	}

	rss := getRSS(pid)
	if rss == 0 { return }

	stateMu.Lock()
	entry, ok := leakTracker[pid]
	if !ok {
		leakTracker[pid] = &LeakEntry{
			FirstSeenRSS: rss,
			LastSeenRSS:  rss,
			FirstSeenAt:  now,
		}
		stateMu.Unlock()
		return
	}
	stateMu.Unlock()

	growth := int64(rss) - int64(entry.FirstSeenRSS)
	if growth > int64(cfg.LeakMBThreshold)*1024*1024 {
		performSilentRestart(pid, cfg, growth/1024/1024)
	}
}

func isProcessIdleEnough(pid int, minIdle int, now time.Time) bool {
	stateMu.Lock()
	ws, ok := windowStates[pid]
	if !ok {
		ppid := getParentPID(pid)
		ws, ok = windowStates[ppid]
	}
	stateMu.Unlock()

	if ok {
		if ws.IsFocused || now.Sub(ws.LastFocusTime) < time.Duration(minIdle)*time.Minute {
			return false
		}
	} else {
		if strings.Contains(getProcessName(pid), "chrome") {
			anyChromeActive := false
			stateMu.Lock()
			for _, w := range windowStates {
				if strings.Contains(w.Name, "chrome") && (w.IsFocused || now.Sub(w.LastFocusTime) < time.Duration(minIdle)*time.Minute) {
					anyChromeActive = true
					break
				}
			}
			stateMu.Unlock()
			if anyChromeActive { return false }
		}
	}
	return true
}

func getParentPID(pid int) int {
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err != nil { return 0 }
	fields := strings.Fields(string(b))
	if len(fields) < 4 { return 0 }
	ppid, _ := strconv.Atoi(fields[3])
	return ppid
}

func getLastGlobalInteraction() time.Time {
	last := time.Time{}
	stateMu.Lock()
	for _, ws := range windowStates {
		if ws.LastFocusTime.After(last) {
			last = ws.LastFocusTime
		}
	}
	stateMu.Unlock()
	return last
}

func performSilentRestart(pid int, cfg RestartConfig, savedMB int64) {
	lg.Info("Silent Restart: %s (PID:%d) — saved %dMB", cfg.Name, pid, savedMB)
	exec.Command("luminos-brain", "log", fmt.Sprintf("silently restarted %s (PID:%d) - saved %dMB", cfg.Name, pid, savedMB)).Run()
	syscall.Kill(pid, syscall.SIGTERM)
	time.Sleep(1 * time.Second)
	if _, err := os.Stat(fmt.Sprintf("/proc/%d", pid)); err == nil {
		syscall.Kill(pid, syscall.SIGKILL)
	}
	restartMu.Lock()
	hist := appRestartHistory[cfg.Name]
	hist.LastRestartAt = time.Now()
	hist.DailyCount++
	if hist.DailyCount >= 3 {
		alertMsg := fmt.Sprintf("%s leaking repeatedly. Consider full restart.", cfg.Name)
		exec.Command("notify-send", "HIVE", alertMsg).Run()
		lg.Warn("REPEATED LEAK: %s", alertMsg)
	}
	restartMu.Unlock()
}

func getChildPIDs(ppid int) []int {
	var children []int
	matches, _ := filepath.Glob("/proc/*/stat")
	for _, m := range matches {
		b, err := os.ReadFile(m)
		if err != nil { continue }
		fields := strings.Fields(string(b))
		if len(fields) < 4 { continue }
		p, _ := strconv.Atoi(fields[3])
		if p == ppid {
			childPID, _ := strconv.Atoi(filepath.Base(filepath.Dir(m)))
			children = append(children, childPID)
		}
	}
	return children
}
