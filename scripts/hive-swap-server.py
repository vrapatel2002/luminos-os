#!/usr/bin/env python3
# [CHANGE: antigravity | 2026-04-28]
# ============================================
# HIVE Model Swap Server
# PURPOSE: HTTP server on port 8079 for model swapping and clipboard
# ENDPOINTS:
#   GET  /swap/<model>  — kill/restart llama-server with new model
#   GET  /status        — current model name and running state
#   POST /copy          — pipe text to wl-copy for Wayland clipboard
# BINDS: 127.0.0.1:8079 (localhost only)
# DEPS: Python stdlib only — NO pip packages
# ============================================

import http.server
import json
import os
import signal
import subprocess
import sys

# ── Constants ──
ALLOWED_MODELS = {"nexus", "bolt", "nova"}
SWAP_SCRIPT = "/home/shawn/luminos-os/scripts/hive-start-model.sh"
ACTIVE_MODEL_FILE = "/tmp/hive-active-model"
LAST_REQUEST_FILE = "/tmp/hive-last-request"
WL_COPY_BIN = "/usr/bin/wl-copy"
BIND_HOST = "127.0.0.1"
BIND_PORT = 8079


class HiveSwapHandler(http.server.BaseHTTPRequestHandler):
    """Request handler for HIVE model swap and clipboard operations."""

    def log_message(self, format, *args):
        """Override to prefix log lines with [SWAP]."""
        print(f"[SWAP] {args[0]} {args[1]} {args[2]}")

    def _send_json(self, status_code, data):
        """Send a JSON response with CORS headers."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests: /swap/<model> and /status."""
        path = self.path.rstrip("/")

        # ── /swap/<model> ──
        if path.startswith("/swap/"):
            model = path[len("/swap/"):]
            if model not in ALLOWED_MODELS:
                self._send_json(400, {
                    "status": "error",
                    "message": f"Invalid model: {model}. Allowed: {', '.join(sorted(ALLOWED_MODELS))}"
                })
                return

            print(f"[SWAP] Swapping to model: {model}")

            # Touch activity marker so idle watchdog stays happy
            try:
                with open(LAST_REQUEST_FILE, "a"):
                    os.utime(LAST_REQUEST_FILE, None)
            except OSError:
                pass

            # Run the swap script synchronously — QML waits for response
            try:
                result = subprocess.run(
                    [SWAP_SCRIPT, model],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    # Update active model file
                    try:
                        with open(ACTIVE_MODEL_FILE, "w") as f:
                            f.write(model)
                    except OSError as e:
                        print(f"[SWAP] Warning: could not write active model file: {e}")

                    print(f"[SWAP] Model {model} is ready")
                    self._send_json(200, {"status": "ready", "model": model})
                else:
                    print(f"[SWAP] Model {model} failed (exit {result.returncode})")
                    print(f"[SWAP] stderr: {result.stderr[:500]}")
                    self._send_json(500, {"status": "failed", "model": model})

            except subprocess.TimeoutExpired:
                print(f"[SWAP] Model {model} timed out after 60s")
                self._send_json(500, {"status": "failed", "model": model})
            except FileNotFoundError:
                print(f"[SWAP] Script not found: {SWAP_SCRIPT}")
                self._send_json(500, {"status": "failed", "model": model})
            return

        # ── /status ──
        if path == "/status":
            model_name = "none"
            try:
                with open(ACTIVE_MODEL_FILE, "r") as f:
                    content = f.read().strip()
                    if content:
                        model_name = content
            except (FileNotFoundError, OSError):
                pass

            # Check if llama-server process is actually running
            running = False
            try:
                result = subprocess.run(
                    ["/usr/bin/pgrep", "-x", "llama-server"],
                    capture_output=True
                )
                running = result.returncode == 0
            except (FileNotFoundError, OSError):
                pass

            self._send_json(200, {"model": model_name, "running": running})
            return

        # ── Unknown path ──
        self._send_json(404, {"status": "error", "message": "Not found"})

    def do_POST(self):
        """Handle POST requests: /copy."""
        path = self.path.rstrip("/")

        if path == "/copy":
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, {"status": "error", "message": "Empty request body"})
                return

            try:
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self._send_json(400, {"status": "error", "message": f"Invalid JSON: {e}"})
                return

            text = data.get("text", "")
            if not text:
                self._send_json(400, {"status": "error", "message": "Missing 'text' field"})
                return

            # Pipe text to wl-copy via stdin (NO shell=True)
            try:
                process = subprocess.Popen(
                    [WL_COPY_BIN],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
                self._send_json(200, {"status": "ok"})
            except Exception as e:
                self._send_json(500, {
                    "status": "error",
                    "message": f"Failed to start wl-copy: {e}"
                })
            return

        self._send_json(404, {"status": "error", "message": "Not found"})


def main():
    server = http.server.HTTPServer((BIND_HOST, BIND_PORT), HiveSwapHandler)
    print(f"[SWAP] HIVE Swap Server listening on {BIND_HOST}:{BIND_PORT}")

    # Graceful shutdown on SIGTERM
    def handle_sigterm(signum, frame):
        print("[SWAP] Received SIGTERM, shutting down...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[SWAP] Received Ctrl+C, shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
