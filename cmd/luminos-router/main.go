// Command luminos-router is the rule-based Windows .exe compatibility classifier.
// It reads PE headers and applies zone_rules.go to assign each .exe to a zone:
//   Zone 1 — native Linux binary (run directly)
//   Zone 2 — standard Windows app (Wine/Proton)
//   Zone 3 — needs Windows APIs Wine lacks (Firecracker microVM)
//   Zone 4 — kernel-level anticheat present (full KVM with GPU passthrough)
//
// Phase 1: rule-based only, answers in <50ms, caches results.
// Phase 2 will add a Python ONNX classifier for the ~20% of edge cases rules can't resolve.
// See LUMINOS_PROJECT_SCOPE.md §Feature 1 and DAEMON_ARCHITECTURE.md §Phase 2.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — luminos-router daemon.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/luminos-os/luminos/internal/config"
	"github.com/luminos-os/luminos/internal/logger"
	"github.com/luminos-os/luminos/internal/socket"
)

// ClassifyRequest is the payload sent by clients asking for a zone decision.
type ClassifyRequest struct {
	Path string `json:"path"`
}

// ClassifyResponse is returned for each classification result.
type ClassifyResponse struct {
	Path       string `json:"path"`
	Zone       int    `json:"zone"`
	ZoneName   string `json:"zone_name"`
	Reason     string `json:"reason"`
	FromCache  bool   `json:"from_cache"`
	DurationMs int64  `json:"duration_ms"`
}

var (
	lg  *logger.Logger
	cfg *config.Config
)

func main() {
	var err error
	cfg, err = config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "luminos-router: config load: %v\n", err)
		os.Exit(1)
	}

	lg, err = logger.New("luminos-router", cfg.Log.Dir+"/router.log", logger.INFO)
	if err != nil {
		lg = logger.NewStdout("luminos-router", logger.INFO)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	// Router socket lives in XDG_RUNTIME_DIR (per-user) not /run/luminos (root-owned).
	// See DAEMON_ARCHITECTURE.md §Socket Paths.
	socketPath := routerSocketPath()
	if err := os.MkdirAll(filepath.Dir(socketPath), 0755); err != nil {
		lg.Error("create socket dir: %v", err)
		os.Exit(1)
	}

	if err := os.MkdirAll(cfg.Router.CacheDir, 0755); err != nil {
		// Cache directory failure is non-fatal — classification still works, just slower.
		lg.Warn("create cache dir %s: %v (caching disabled)", cfg.Router.CacheDir, err)
	}

	l, err := socket.NewListener(socketPath)
	if err != nil {
		lg.Error("listen: %v", err)
		os.Exit(1)
	}

	lg.Info("luminos-router started — listening on %s", socketPath)
	lg.Info("mode: rules_only (Phase 1 — ML edge-case classifier is Phase 2)")

	socket.Serve(ctx, l, handleMessage)

	os.Remove(socketPath)
	lg.Info("luminos-router stopped")
}

// handleMessage dispatches router requests to the appropriate handler.
func handleMessage(msg socket.Message) socket.Message {
	switch msg.Type {
	case "ping":
		return replyOK(msg, map[string]string{"pong": "ok", "daemon": "luminos-router"})
	case "status":
		return replyOK(msg, map[string]interface{}{
			"daemon": "luminos-router",
			"mode":   "rules_only",
		})
	case "classify":
		return handleClassify(msg)
	default:
		return replyError(msg, fmt.Sprintf("unknown type: %s", msg.Type))
	}
}

// handleClassify processes a classify request and returns a zone decision.
// It checks the cache first so repeated calls for the same .exe are instant.
// The spec requires a result in under 3 seconds; rule-based path is typically <50ms.
func handleClassify(msg socket.Message) socket.Message {
	start := time.Now()

	var req ClassifyRequest
	if err := json.Unmarshal(msg.Payload, &req); err != nil {
		return replyError(msg, fmt.Sprintf("bad payload: %v", err))
	}
	if req.Path == "" {
		return replyError(msg, "path is required")
	}

	// Cache hit: return immediately without re-analysing the PE file.
	if cached, ok := loadCache(cfg.Router.CacheDir, req.Path); ok {
		cached.FromCache = true
		cached.DurationMs = time.Since(start).Milliseconds()
		lg.Debug("cache hit for %s → zone%d (%s)", req.Path, cached.Zone, cached.ZoneName)
		return replyOK(msg, cached)
	}

	zone, zoneName, reason, err := ClassifyEXE(req.Path)
	if err != nil {
		return replyError(msg, fmt.Sprintf("classify %s: %v", req.Path, err))
	}

	resp := ClassifyResponse{
		Path:       req.Path,
		Zone:       zone,
		ZoneName:   zoneName,
		Reason:     reason,
		FromCache:  false,
		DurationMs: time.Since(start).Milliseconds(),
	}

	// Persist result so the second call for any given .exe is instant.
	saveCache(cfg.Router.CacheDir, req.Path, resp)

	lg.Info("classify %s → zone%d/%s in %dms: %s",
		req.Path, zone, zoneName, resp.DurationMs, reason)

	// Notify luminos-ai for monitoring dashboards and status queries.
	reportToAI(resp)

	return replyOK(msg, resp)
}

// routerSocketPath returns the runtime socket path for the router.
// Prefers XDG_RUNTIME_DIR so the user session can access it; falls back to /tmp.
func routerSocketPath() string {
	if xdg := os.Getenv("XDG_RUNTIME_DIR"); xdg != "" {
		return xdg + "/luminos-router.sock"
	}
	return "/tmp/luminos-router.sock"
}

// reportToAI notifies luminos-ai of the classification for central monitoring.
// Failure is not propagated — the classification result is still returned to the caller.
func reportToAI(resp ClassifyResponse) {
	msg, err := socket.NewMessage("report_router", "luminos-router", resp)
	if err != nil {
		lg.Error("build report_router: %v", err)
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
		Source:    "luminos-router",
	}
}

func replyError(req socket.Message, errMsg string) socket.Message {
	b, _ := json.Marshal(map[string]string{"error": errMsg})
	return socket.Message{
		Type:      "error",
		Payload:   json.RawMessage(b),
		Timestamp: time.Now(),
		Source:    "luminos-router",
	}
}
