#!/usr/bin/env python3
# [CHANGE: antigravity | 2026-05-02]
# ============================================
# HIVE Daemon — Consolidated Orchestration Server
# PURPOSE: Single daemon owning model state, swapping, routing, and inference.
#          Replaces the split logic across QML + swap server.
#          Runs PARALLEL to hive-swap-server.py (port 8079) until QML migration.
# ENDPOINTS:
#   POST /chat   — main chat entry (routing + inference)
#   GET  /state  — current model + ready status
#   GET  /health — daemon liveness check
#   POST /copy   — clipboard via wl-copy
# BINDS: 127.0.0.1:8078 (localhost only)
# DEPS: Python stdlib only — NO pip packages
# ============================================

import http.server
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import fcntl
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Constants ──────────────────────────────────────────────────────────────────

BIND_HOST = "127.0.0.1"
BIND_PORT = 8078
LLAMA_SERVER_URL = "http://localhost:8080/v1/chat/completions"
SWAP_SCRIPT = "/home/shawn/luminos-os/scripts/hive-start-model.sh"
PROMPTS_DIR = "/home/shawn/luminos-os/config/prompts"
ACTIVE_MODEL_FILE = "/tmp/hive-active-model"
LAST_REQUEST_FILE = "/tmp/hive-last-request"
LOCKFILE = "/tmp/hive-daemon.lock"
WL_COPY_BIN = "/usr/bin/wl-copy"

ALLOWED_MODELS = {"nexus", "bolt", "nova"}

# Chip name → model alias
# Matches QML HiveChat.qml chip definitions
CHIP_TO_MODEL = {
    "Code":       "bolt",
    "Learn":      "nova",
    "Strategize": "nova",
    "Write":      "nexus",
    "System":     "nexus",
}

# Route tag regex: [ROUTE:BOLT], [ROUTE:NOVA], [ROUTE:NEXUS]
ROUTE_TAG_RE = re.compile(r"\[ROUTE:(\w+)\]", re.IGNORECASE)

# ── Logging ────────────────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s [HIVE] %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("hive-daemon")
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
logger.addHandler(console_handler)

# File handler
try:
    file_handler = logging.FileHandler("/tmp/hive-daemon.log", mode="a")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
    logger.addHandler(file_handler)
except OSError as e:
    print(f"Warning: could not open log file: {e}", file=sys.stderr)

# ── System Prompt Cache ───────────────────────────────────────────────────────

_system_prompts: dict[str, str | None] = {}


def _load_system_prompts():
    """Load all system prompts from disk at startup. Cache in memory."""
    for model in ALLOWED_MODELS:
        prompt_path = os.path.join(PROMPTS_DIR, f"{model}.txt")
        try:
            with open(prompt_path, "r") as f:
                _system_prompts[model] = f.read().strip()
                logger.info("Loaded system prompt for %s (%d chars)", model, len(_system_prompts[model]))
        except FileNotFoundError:
            _system_prompts[model] = None
            logger.warning("System prompt not found for %s at %s — will run without", model, prompt_path)
        except OSError as e:
            _system_prompts[model] = None
            logger.warning("Could not read system prompt for %s: %s", model, e)


# ── Model State ───────────────────────────────────────────────────────────────

class ModelState:
    """Thread-safe tracker for the currently loaded model."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_model: str | None = None
        self._ready = False

        # Try to bootstrap from existing active-model file
        # (in case llama-server is already running from popup)
        try:
            with open(ACTIVE_MODEL_FILE, "r") as f:
                name = f.read().strip()
                if name in ALLOWED_MODELS:
                    self._current_model = name
                    # Don't set _ready — we haven't verified llama-server is alive.
                    # We'll trust that state once a /chat request arrives.
                    # Actually, since the file was written by a previous swap, trust it.
                    self._ready = True
                    logger.info("Bootstrapped model state from file: %s", name)
        except (FileNotFoundError, OSError):
            pass

    @property
    def current_model(self) -> str | None:
        with self._lock:
            return self._current_model

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._ready

    def set_model(self, model: str | None, ready: bool = True):
        with self._lock:
            old = self._current_model
            self._current_model = model
            self._ready = ready
            if old != model:
                logger.info("STATE TRANSITION: %s → %s (ready=%s)", old, model, ready)
            # Write to file for external tools (idle watchdog, popup)
            if model:
                try:
                    with open(ACTIVE_MODEL_FILE, "w") as f:
                        f.write(model)
                except OSError:
                    pass

    def set_not_ready(self):
        with self._lock:
            self._ready = False


_state = ModelState()


# ── Model Swap ────────────────────────────────────────────────────────────────

def _swap_model(target: str) -> tuple[bool, str]:
    """
    Swap to target model using hive-start-model.sh.
    Returns (success, error_message).
    """
    if target not in ALLOWED_MODELS:
        return False, f"Invalid model: {target}"

    # If already loaded, skip swap entirely
    if _state.current_model == target and _state.ready:
        logger.info("Model %s already loaded — skipping swap", target)
        return True, ""

    logger.info("SWAP START: → %s", target)
    _state.set_not_ready()

    # Touch activity marker
    try:
        with open(LAST_REQUEST_FILE, "a"):
            os.utime(LAST_REQUEST_FILE, None)
    except OSError:
        pass

    try:
        result = subprocess.run(
            [SWAP_SCRIPT, target],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            _state.set_model(target, ready=True)
            logger.info("SWAP COMPLETE: %s is ready", target)
            return True, ""
        else:
            err = result.stderr[:500].strip() if result.stderr else "unknown error"
            logger.error("SWAP FAILED: %s (exit %d): %s", target, result.returncode, err)
            _state.set_model(None, ready=False)
            return False, f"Swap to {target} failed (exit {result.returncode}): {err}"

    except subprocess.TimeoutExpired:
        logger.error("SWAP TIMEOUT: %s after 120s", target)
        _state.set_model(None, ready=False)
        return False, f"Swap to {target} timed out after 120s"
    except FileNotFoundError:
        logger.error("SWAP SCRIPT NOT FOUND: %s", SWAP_SCRIPT)
        _state.set_model(None, ready=False)
        return False, f"Swap script not found: {SWAP_SCRIPT}"


# ── Inference ─────────────────────────────────────────────────────────────────

def _call_llama(messages: list[dict], model_name: str) -> tuple[str | None, str | None]:
    """
    Send a chat completion request to llama-server.
    Returns (response_text, error_message).
    Retries once on 503. Retries once on connection refused after re-swap.
    """
    payload = json.dumps({
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": False,
    }).encode("utf-8")

    def _do_request() -> tuple[str | None, str | None, bool]:
        """Returns (text, error, should_reswap)."""
        req = Request(
            LLAMA_SERVER_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
                    return text, None, False
                return None, "Empty response from llama-server", False
        except HTTPError as e:
            if e.code == 503:
                return None, f"llama-server returned 503", False
            return None, f"llama-server HTTP {e.code}: {e.reason}", False
        except URLError as e:
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            if "Connection refused" in reason or "No connection" in reason:
                return None, f"Connection refused to llama-server", True
            return None, f"llama-server connection error: {reason}", False
        except Exception as e:
            return None, f"Inference error: {e}", False

    # First attempt
    text, err, needs_reswap = _do_request()
    if text is not None:
        return text, None

    # Handle 503: retry once after 2s delay
    if err and "503" in err:
        logger.warning("llama-server 503, retrying in 2s...")
        time.sleep(2)
        text, err2, _ = _do_request()
        if text is not None:
            return text, None
        return None, err2 or err

    # Handle connection refused: attempt re-swap, then retry
    if needs_reswap:
        logger.warning("Connection refused — attempting re-swap of %s", model_name)
        ok, swap_err = _swap_model(model_name)
        if not ok:
            return None, f"Re-swap failed: {swap_err}"
        text, err2, _ = _do_request()
        if text is not None:
            return text, None
        return None, err2 or err

    return None, err


def _build_messages(model: str, user_message: str, history: list[dict] | None) -> list[dict]:
    """Build the messages array with system prompt + history + user message."""
    messages = []
    prompt = _system_prompts.get(model)
    if prompt:
        messages.append({"role": "system", "content": prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def _strip_route_tags(text: str) -> str:
    """Remove [ROUTE:X] tags from response text."""
    return ROUTE_TAG_RE.sub("", text).strip()


# ── Request Handler ───────────────────────────────────────────────────────────

class HiveDaemonHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the consolidated HIVE daemon."""

    # Silence default access logging — we do our own
    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code: int, data: dict):
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

    def _read_json_body(self) -> dict | None:
        """Read and parse JSON request body. Returns None on failure (sends error)."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json(400, {"error": "Empty request body"})
            return None
        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._send_json(400, {"error": f"Invalid JSON: {e}"})
            return None

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.rstrip("/")

        # ── GET /health ──
        if path == "/health":
            logger.debug("GET /health")
            self._send_json(200, {
                "status": "ok",
                "daemon": "hive-daemon",
                "port": BIND_PORT,
                "uptime_s": int(time.time() - _startup_time),
            })
            return

        # ── GET /state ──
        if path == "/state":
            logger.debug("GET /state")
            self._send_json(200, {
                "model": _state.current_model,
                "ready": _state.ready,
            })
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.rstrip("/")

        # ── POST /copy ──
        if path == "/copy":
            logger.debug("POST /copy")
            data = self._read_json_body()
            if data is None:
                return
            text = data.get("text", "")
            if not text:
                self._send_json(400, {"error": "Missing 'text' field"})
                return
            try:
                process = subprocess.Popen(
                    [WL_COPY_BIN],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
                self._send_json(200, {"status": "ok"})
            except Exception as e:
                self._send_json(500, {"error": f"Failed to start wl-copy: {e}"})
            return

        # ── POST /chat ──
        if path == "/chat":
            self._handle_chat()
            return

        self._send_json(404, {"error": "Not found"})

    # ── Chat Logic ────────────────────────────────────────────────────────

    def _handle_chat(self):
        t_start = time.monotonic()

        data = self._read_json_body()
        if data is None:
            return

        user_message = data.get("message", "").strip()
        if not user_message:
            self._send_json(400, {"error": "Missing 'message' field"})
            return

        chip = data.get("chip")  # None or one of the chip names
        history = data.get("history")  # None or list of {role, content}

        logger.info("POST /chat — chip=%s message=%s",
                     chip, user_message[:80] + ("..." if len(user_message) > 80 else ""))

        # Touch activity marker
        try:
            with open(LAST_REQUEST_FILE, "a"):
                os.utime(LAST_REQUEST_FILE, None)
        except OSError:
            pass

        # ── Path A: Chip is set → direct to mapped model ──
        if chip and chip in CHIP_TO_MODEL:
            target_model = CHIP_TO_MODEL[chip]
            ok, swap_err = _swap_model(target_model)
            if not ok:
                self._send_json(500, self._error_response(swap_err))
                return

            messages = _build_messages(target_model, user_message, history)
            response_text, infer_err = _call_llama(messages, target_model)
            t_end = time.monotonic()

            if infer_err:
                self._send_json(502, self._error_response(infer_err))
                return

            # Strip any accidental route tags from specialist output
            clean_text = _strip_route_tags(response_text)

            # Map model to agent display name
            agent_name = {"nexus": "Nexus", "bolt": "Bolt", "nova": "Nova"}.get(target_model, target_model)

            self._send_json(200, {
                "agent": agent_name,
                "content": clean_text,
                "thinking_time_ms": int((t_end - t_start) * 1000),
                "routed": False,
                "route_target": None,
                "error": None,
            })
            return

        # ── Path B: No chip → route through Nexus ──
        ok, swap_err = _swap_model("nexus")
        if not ok:
            self._send_json(500, self._error_response(swap_err))
            return

        nexus_messages = _build_messages("nexus", user_message, history)
        nexus_response, infer_err = _call_llama(nexus_messages, "nexus")
        t_nexus = time.monotonic()

        if infer_err:
            self._send_json(502, self._error_response(infer_err))
            return

        # Check for route tags
        route_match = ROUTE_TAG_RE.search(nexus_response)

        if not route_match:
            # Nexus handles it directly — no routing
            clean_text = _strip_route_tags(nexus_response)
            t_end = time.monotonic()
            self._send_json(200, {
                "agent": "Nexus",
                "content": clean_text,
                "thinking_time_ms": int((t_end - t_start) * 1000),
                "routed": False,
                "route_target": None,
                "error": None,
            })
            return

        # ── Route to specialist ──
        route_target = route_match.group(1).lower()  # "bolt" or "nova"
        if route_target not in ALLOWED_MODELS:
            # Unknown route target — return Nexus response stripped
            logger.warning("Unknown route target from Nexus: %s", route_target)
            clean_text = _strip_route_tags(nexus_response)
            t_end = time.monotonic()
            self._send_json(200, {
                "agent": "Nexus",
                "content": clean_text,
                "thinking_time_ms": int((t_end - t_start) * 1000),
                "routed": False,
                "route_target": None,
                "error": None,
            })
            return

        logger.info("ROUTING: Nexus → %s", route_target)

        ok, swap_err = _swap_model(route_target)
        if not ok:
            # Swap failed — return Nexus response with error note
            clean_text = _strip_route_tags(nexus_response)
            self._send_json(500, {
                "agent": "Nexus",
                "content": clean_text,
                "thinking_time_ms": int((time.monotonic() - t_start) * 1000),
                "routed": True,
                "route_target": route_target,
                "error": f"Routing to {route_target} failed: {swap_err}",
            })
            return

        # Send ONLY the original user message to specialist (no Nexus artifacts)
        specialist_messages = _build_messages(route_target, user_message, history)
        specialist_response, infer_err = _call_llama(specialist_messages, route_target)
        t_end = time.monotonic()

        if infer_err:
            self._send_json(502, self._error_response(infer_err))
            return

        clean_text = _strip_route_tags(specialist_response)
        agent_name = {"nexus": "Nexus", "bolt": "Bolt", "nova": "Nova"}.get(route_target, route_target)

        self._send_json(200, {
            "agent": agent_name,
            "content": clean_text,
            "thinking_time_ms": int((t_end - t_start) * 1000),
            "nexus_time_ms": int((t_nexus - t_start) * 1000),
            "specialist_time_ms": int((t_end - t_nexus) * 1000),
            "routed": True,
            "route_target": route_target,
            "error": None,
        })

    def _error_response(self, error_msg: str) -> dict:
        return {
            "agent": None,
            "content": None,
            "thinking_time_ms": 0,
            "routed": False,
            "route_target": None,
            "error": error_msg,
        }


# ── Single Instance Lock ─────────────────────────────────────────────────────

_lock_fd = None


def _acquire_lock():
    """Acquire an exclusive lock file. Exit if another instance is running."""
    global _lock_fd
    try:
        _lock_fd = open(LOCKFILE, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
    except (IOError, OSError):
        print(f"ERROR: Another hive-daemon instance is already running (lockfile: {LOCKFILE})",
              file=sys.stderr)
        sys.exit(1)


def _release_lock():
    """Release the lock file."""
    global _lock_fd
    if _lock_fd:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except OSError:
            pass
        try:
            os.unlink(LOCKFILE)
        except OSError:
            pass


# ── Main ──────────────────────────────────────────────────────────────────────

_startup_time = time.time()


def main():
    global _startup_time
    _startup_time = time.time()

    _acquire_lock()
    _load_system_prompts()

    server = http.server.ThreadingHTTPServer((BIND_HOST, BIND_PORT), HiveDaemonHandler)
    # Allow socket reuse to avoid "Address already in use" after restart
    server.allow_reuse_address = True

    logger.info("═══════════════════════════════════════════════════════════")
    logger.info("HIVE Daemon v1.0 — listening on %s:%d", BIND_HOST, BIND_PORT)
    logger.info("Current model state: %s (ready=%s)", _state.current_model, _state.ready)
    logger.info("System prompts loaded: %s",
                ", ".join(m for m, p in _system_prompts.items() if p))
    logger.info("═══════════════════════════════════════════════════════════")

    def _shutdown(signum, frame):
        signame = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        logger.info("Received %s — shutting down", signame)
        _release_lock()
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
        _release_lock()
        server.shutdown()


if __name__ == "__main__":
    main()
