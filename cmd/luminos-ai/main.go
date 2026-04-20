// Command luminos-ai is the central Luminos OS IPC daemon.
// It listens on /run/luminos/ai.sock, routes messages between sub-daemons,
// and exposes health/status endpoints for the whole daemon stack.
// All other daemons report their state here so a single "status" call gives
// a complete picture of what the system is doing.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — luminos-ai daemon.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
)

// aggregatedState caches the latest status pushed by each sub-daemon.
// luminos-ai answers "status" queries from this cache, avoiding round-trips.
type aggregatedState struct {
	mu       sync.RWMutex
	power    json.RawMessage
	sentinel json.RawMessage
	router   json.RawMessage
}

var (
	lg    *logger.Logger
	state aggregatedState
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "luminos-ai: config load: %v\n", err)
		os.Exit(1)
	}

	lg, err = logger.New("luminos-ai", cfg.Log.Dir+"/ai.log", logger.INFO)
	if err != nil {
		// Fall back to stdout if /var/log/luminos has not been created yet.
		lg = logger.NewStdout("luminos-ai", logger.INFO)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	// Ensure /run/luminos exists — systemd RuntimeDirectory should create it,
	// but we create it here so the daemon can also be started manually.
	if err := os.MkdirAll("/run/luminos", 0755); err != nil {
		lg.Error("create /run/luminos: %v", err)
		os.Exit(1)
	}

	l, err := socket.NewListener(cfg.Sockets.AI)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}

	lg.Info("luminos-ai started — listening on %s", cfg.Sockets.AI)
	lg.Info("mode: rules_only (Phase 1 — Python inference services not yet online)")

	// socket.Serve blocks until ctx is cancelled (which closes l via its goroutine).
	socket.Serve(ctx, l, handleMessage)

	// Clean up socket file on exit so the next start doesn't see a stale socket.
	os.Remove(cfg.Sockets.AI)
	lg.Info("luminos-ai stopped")
}

// handleMessage dispatches incoming IPC messages by type.
// Health/status are handled locally; report_* messages update the aggregated state.
func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "ping":
		return replyOK(msg, map[string]string{"pong": "ok", "daemon": "luminos-ai"})

	case "health":
		return replyOK(msg, map[string]interface{}{
			"status":  "ok",
			"daemon":  "luminos-ai",
			"version": "0.1.0-phase1",
			"time":    time.Now().Format(time.RFC3339),
			"mode":    "rules_only",
		})

	case "status":
		// Return a snapshot of all sub-daemon states collected via report_* messages.
		state.mu.RLock()
		defer state.mu.RUnlock()
		return replyOK(msg, map[string]interface{}{
			"daemon":   "luminos-ai",
			"mode":     "rules_only",
			"power":    state.power,
			"sentinel": state.sentinel,
			"router":   state.router,
		})

	case "report_power":
		// luminos-power pushes AC/thermal state on every change.
		state.mu.Lock()
		state.power = msg.Payload
		state.mu.Unlock()
		lg.Info("power state updated from %s: %s", msg.Source, string(msg.Payload))
		return replyOK(msg, map[string]string{"status": "received"})

	case "report_sentinel":
		// luminos-sentinel pushes threat events when a rule triggers.
		state.mu.Lock()
		state.sentinel = msg.Payload
		state.mu.Unlock()
		lg.Warn("sentinel event from %s: %s", msg.Source, string(msg.Payload))
		return replyOK(msg, map[string]string{"status": "received"})

	case "report_router":
		// luminos-router pushes .exe classification results.
		state.mu.Lock()
		state.router = msg.Payload
		state.mu.Unlock()
		return replyOK(msg, map[string]string{"status": "received"})

	default:
		lg.Warn("unknown message type %q from %s", msg.Type, msg.Source)
		return replyError(msg, fmt.Sprintf("unknown type: %s", msg.Type))
	}
}

func replyOK(req socket.Message, payload interface{}) socket.Message {
	b, _ := json.Marshal(payload)
	return socket.Message{
		Type:      req.Type + "_response",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-ai",
	}
}

func replyError(req socket.Message, errMsg string) socket.Message {
	b, _ := json.Marshal(map[string]string{"error": errMsg})
	return socket.Message{
		Type:      "error",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-ai",
	}
}
