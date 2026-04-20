// Command luminos-sentinel monitors /proc for new processes and enforces
// rule-based security policies, primarily around Wine/Proton isolation.
// Phase 1: rule-based only (threat_rules.go). Phase 3 will add NPU ML classification.
// See LUMINOS_PROJECT_SCOPE.md §Feature 5 — Sentinel Security.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — luminos-sentinel daemon.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
)

var (
	lg  *logger.Logger
	cfg *config.Config
)

func main() {
	var err error
	cfg, err = config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "luminos-sentinel: config load: %v\n", err)
		os.Exit(1)
	}

	lg, err = logger.New("luminos-sentinel", cfg.Log.Dir+"/sentinel.log", logger.INFO)
	if err != nil {
		lg = logger.NewStdout("luminos-sentinel", logger.INFO)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	if err := os.MkdirAll("/run/luminos", 0755); err != nil {
		lg.Error("create /run/luminos: %v", err)
		os.Exit(1)
	}

	l, err := socket.NewListener(cfg.Sockets.Sentinel)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}

	lg.Info("luminos-sentinel started — listening on %s", cfg.Sockets.Sentinel)
	lg.Info("mode: rules_only (Phase 1 — NPU ML classification is Phase 3)")

	// scanLoop polls /proc for new processes in the background.
	go scanLoop(ctx)

	socket.Serve(ctx, l, handleMessage)

	os.Remove(cfg.Sockets.Sentinel)
	lg.Info("luminos-sentinel stopped")
}

// handleMessage answers status and control queries.
func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "ping":
		return replyOK(msg, map[string]string{"pong": "ok", "daemon": "luminos-sentinel"})
	case "status":
		return replyOK(msg, map[string]interface{}{
			"daemon": "luminos-sentinel",
			"mode":   "rules_only",
		})
	default:
		return replyError(msg, fmt.Sprintf("unknown type: %s", msg.Type))
	}
}

// scanLoop polls /proc every PollIntervalMs milliseconds.
// It tracks known PIDs and only inspects newly-appeared ones to minimise CPU usage.
func scanLoop(ctx context.Context) {
	interval := time.Duration(cfg.Sentinel.PollIntervalMs) * time.Millisecond
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	// knownPIDs is the set of PIDs seen on the previous scan.
	// Newly-appeared PIDs are those in currentPIDs but not in knownPIDs.
	knownPIDs := make(map[int]bool)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			current := listPIDs()
			for pid := range current {
				if !knownPIDs[pid] {
					checkProcess(pid)
				}
			}
			knownPIDs = current
		}
	}
}

// listPIDs returns the set of numeric directory names in /proc — each is a running process PID.
func listPIDs() map[int]bool {
	entries, err := os.ReadDir("/proc")
	if err != nil {
		lg.Error("readdir /proc: %v", err)
		return nil
	}
	pids := make(map[int]bool, len(entries))
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		var pid int
		if _, err := fmt.Sscanf(e.Name(), "%d", &pid); err == nil {
			pids[pid] = true
		}
	}
	return pids
}

// checkProcess inspects a newly-appeared process against all threat rules.
// It is safe to call when the process has already exited — ReadProcess will return an error.
func checkProcess(pid int) {
	proc, err := ReadProcess(pid)
	if err != nil {
		// Short-lived processes (e.g. shell builtins) exit before we can read them.
		// This is normal and not an error.
		return
	}

	violations := CheckThreatRules(proc)
	for _, v := range violations {
		lg.Warn("THREAT [%s] pid=%d exe=%s — %s", v.RuleName, pid, proc.ExePath, v.Description)
		reportThreat(proc, v)
	}
}

// reportThreat sends a threat event to luminos-ai for central logging and monitoring.
func reportThreat(proc *Process, v Violation) {
	payload := map[string]interface{}{
		"rule":        v.RuleName,
		"description": v.Description,
		"pid":         proc.PID,
		"exe":         proc.ExePath,
		"time":        time.Now().Format(time.RFC3339),
	}
	msg, err := socket.NewMessage("report_sentinel", "luminos-sentinel", payload)
	if err != nil {
		lg.Error("build report_sentinel: %v", err)
		return
	}
	if _, err := socket.Send(cfg.Sockets.AI, msg); err != nil {
		lg.Debug("report to luminos-ai: %v", err)
	}
}

func replyOK(req socket.Message, payload interface{}) socket.Message {
	b, _ := json.Marshal(payload)
	return socket.Message{
		Type:      req.Type + "_response",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-sentinel",
	}
}

func replyError(req socket.Message, errMsg string) socket.Message {
	b, _ := json.Marshal(map[string]string{"error": errMsg})
	return socket.Message{
		Type:      "error",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-sentinel",
	}
}
