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

import html
import http.server
import html.parser
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
import urllib.parse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from hive_context import get_system_context, get_brain_context, log_incident

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
GREETING_CACHE_PATH = os.path.expanduser("~/.cache/luminos/hive-greeting.txt")

ALLOWED_MODELS = {"nexus", "bolt", "nova", "web"}

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

# [CHANGE: gemini-cli | 2026-05-03] Intent detection keywords for fallback routing
CODE_KEYWORDS = [
    re.compile(r"\bwrite\s+(me\s+)?(a|an|some)?\s*(code|script|function|class|program)", re.IGNORECASE),
    re.compile(r"\b(debug|fix|review)\s+(this|my|the)?\s*(code|script|function)", re.IGNORECASE),
    re.compile(r"\b(python|bash|javascript|typescript|rust|go|c\+\+|sql)\b", re.IGNORECASE),
    re.compile(r"\b(api|endpoint|http|curl|json|yaml)\b", re.IGNORECASE),
    re.compile(r"\b(asyncio|await|promise|callback)\b", re.IGNORECASE),
    re.compile(r"```"),
]

REASONING_KEYWORDS = [
    re.compile(r"\bexplain\s+why\b", re.IGNORECASE),
    re.compile(r"\bstep[- ]by[- ]step\b", re.IGNORECASE),
    re.compile(r"\b(plan|strategy|architecture|design)\s+(a|an|the|for)", re.IGNORECASE),
    re.compile(r"\b(compare|evaluate|weigh|trade[- ]off)\b", re.IGNORECASE),
    re.compile(r"\b(analyze|reason|deduce)\b", re.IGNORECASE),
    re.compile(r"\b(math|calculate|equation|proof)\b", re.IGNORECASE),
]

WEB_KEYWORDS = [
    # Explicit search/browse requests
    re.compile(r"\b(search|look up|google|find|browse)\b.*\b(web|online|internet|site|article|news|price|weather|stock)\b", re.IGNORECASE),
    re.compile(r"\bsearch (for|about|the web for)\b", re.IGNORECASE),
    re.compile(r"\b(find me|look up|fetch|get me) (info|information|data|details|the price|the score)\b", re.IGNORECASE),
    # Live/current data
    re.compile(r"\b(what('s| is) (happening|going on|the latest|the current|the price|the weather))\b", re.IGNORECASE),
    re.compile(r"\b(latest|current|recent|today'?s?|live)\b.*(news|price|update|score|weather|rate)\b", re.IGNORECASE),
    re.compile(r"\bwhat (is|are) .{0,40} (today|right now|currently|at the moment)\b", re.IGNORECASE),
    re.compile(r"\b(how much (does|is)|what does .{0,30} cost)\b", re.IGNORECASE),
    # Sports: matches, fixtures, schedules, standings
    re.compile(r"\b(ipl|cricket|football|soccer|nfl|nba|nhl|premier league|la liga|bundesliga|champions league|formula.?1|f1|tennis|ufc|mma|rugby|hockey|baseball)\b", re.IGNORECASE),
    re.compile(r"\b(remaining|upcoming|next|scheduled|fixture|fixtures|standings|table|results|scoreboard)\b.*(match|game|match|season|series|tournament|round)\b", re.IGNORECASE),
    re.compile(r"\b(match|game|tournament|season|series|playoff|qualifier|final|semi.?final)\b.*(schedule|fixture|remaining|upcoming|result|score)\b", re.IGNORECASE),
    re.compile(r"\b(who (won|is winning|leads|is leading|is ahead))\b", re.IGNORECASE),
    re.compile(r"\b(score|result|winner|standings)\b.*(today|yesterday|this week|last night|live)\b", re.IGNORECASE),
    # News / events / announcements
    re.compile(r"\b(news|headline|announcement|release|launch|update)\b.*(about|on|for|from|regarding)\b", re.IGNORECASE),
    re.compile(r"\b(tell me|what are|show me).{0,30}(news|update|match|game|score|result|price|weather)\b", re.IGNORECASE),
    # Tech releases / software versions
    re.compile(r"\b(latest|new|newest|current) (version|release|update) of\b", re.IGNORECASE),
]


def detect_intent(message: str) -> str | None:
    """Detect if message likely needs Bolt (code), Nova (reasoning), or web search."""
    for pattern in WEB_KEYWORDS:
        if pattern.search(message):
            return "web"
    for pattern in CODE_KEYWORDS:
        if pattern.search(message):
            return "bolt"
    for pattern in REASONING_KEYWORDS:
        if pattern.search(message):
            return "nova"
    return None


# ── Web Search ────────────────────────────────────────────────────────────────

class _HTMLTextExtractor(html.parser.HTMLParser):
    """Strip HTML tags and collect visible text, skipping nav/footer/menu noise."""
    _SKIP_TAGS = {"script", "style", "noscript", "head", "meta", "link",
                  "nav", "footer", "header", "aside", "form", "button", "svg", "iframe"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        # Also skip elements with nav/menu/ad-related class or id
        attr_dict = dict(attrs)
        for val in (attr_dict.get("class", ""), attr_dict.get("id", "")):
            if any(noise in val.lower() for noise in
                   ("nav", "menu", "header", "footer", "sidebar", "ad-", "cookie", "banner", "popup")):
                self._skip_depth += 1
                return

    def handle_endtag(self, tag):
        if self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _web_search(query: str, num_results: int = 5) -> list[dict]:
    """
    Search DuckDuckGo HTML endpoint. Returns list of {title, snippet, url}.
    No API key. Uses stdlib urllib only.
    """
    encoded = urllib.parse.urlencode({"q": query})
    url = f"https://html.duckduckgo.com/html/?{encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=8) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Web search HTTP error: %s", e)
        return []

    results = []
    # DDG HTML: <a class="result__a" ...>TITLE</a> ... <a class="result__snippet">SNIPPET</a>
    # Extract result blocks with a simple regex (no bs4 needed)
    block_re = re.compile(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    for m in block_re.finditer(raw_html):
        raw_url, raw_title, raw_snippet = m.group(1), m.group(2), m.group(3)
        # DDG wraps real URLs in a redirect; extract uddg param if present
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
        real_url = qs.get("uddg", [raw_url])[0]
        # Skip ad redirects (y.js) and bare duckduckgo.com links
        if "duckduckgo.com/y.js" in real_url or real_url.startswith("//duckduckgo.com"):
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        snippet = html.unescape(re.sub(r"<[^>]+>", "", raw_snippet)).strip()
        if title and snippet:
            results.append({"title": title, "snippet": snippet, "url": real_url})
        if len(results) >= num_results:
            break

    logger.info("Web search '%s' → %d results", query[:60], len(results))
    return results


def _fetch_page_text(url: str, max_chars: int = 5000) -> str:
    """Fetch a URL and return stripped plain text, truncated to max_chars."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=8) as resp:
            raw = resp.read(131072).decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Page fetch error %s: %s", url, e)
        return ""

    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(raw)
    except Exception:
        pass
    text = extractor.get_text()
    # Filter out very short or pure-whitespace extractions (JS-rendered pages)
    if len(text) < 200:
        return ""
    return text[:max_chars] if len(text) > max_chars else text


def _fetch_best_page_text(results: list[dict], max_chars: int = 5000) -> str:
    """Try top 3 results until one yields useful page content (>500 chars)."""
    for r in results[:3]:
        text = _fetch_page_text(r["url"], max_chars)
        if len(text) > 500:
            logger.info("Page fetch OK: %s (%d chars)", r["url"][:60], len(text))
            return text
        logger.info("Page fetch thin/blocked: %s", r["url"][:60])
    return ""


def _format_web_context(query: str, results: list[dict], page_text: str = "") -> str:
    """Format search results + optional page text for injection into Nexus context."""
    lines = [
        f"[WEB SEARCH RESULTS for: {query}]",
        "INSTRUCTION: Extract and present the actual data below in a clear formatted list.",
        "DO NOT just provide links. DO NOT say 'I recommend visiting'. Present the real content.",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['snippet']}")
        lines.append(f"   URL: {r['url']}")
        lines.append("")
    if page_text:
        lines.append("[PAGE CONTENT — use this to extract the actual data]")
        lines.append(page_text)
        lines.append("")
    lines.append("[END — present the data as a structured list, cite source at the bottom]")
    return "\n".join(lines)

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
        self._current_stage = "idle"
        self._stage_started_at = 0.0

        # Try to bootstrap from existing active-model file, but ONLY if
        # llama-server is actually reachable right now (file can be stale on restart).
        try:
            with open(ACTIVE_MODEL_FILE, "r") as f:
                name = f.read().strip()
                if name in ALLOWED_MODELS:
                    self._current_model = name
                    # Verify llama-server is actually alive before trusting
                    try:
                        from urllib.request import urlopen as _urlopen
                        with _urlopen("http://localhost:8080/health", timeout=2) as resp:
                            if b"ok" in resp.read():
                                self._ready = True
                                logger.info("Bootstrapped model state: %s (llama-server verified alive)", name)
                            else:
                                logger.info("Bootstrapped model name: %s (llama-server unhealthy — marking not ready)", name)
                    except Exception:
                        logger.info("Bootstrapped model name: %s (llama-server not running — marking not ready)", name)
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

    @property
    def progress(self) -> tuple[str, float]:
        with self._lock:
            return self._current_stage, self._stage_started_at

    def set_stage(self, stage: str):
        with self._lock:
            self._current_stage = stage
            self._stage_started_at = time.time()

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
        _state.set_model(None, ready=False)  # Force reset — prevents _swap_model skipping on stale state
        ok, swap_err = _swap_model(model_name)
        if not ok:
            return None, f"Re-swap failed: {swap_err}"
        text, err2, _ = _do_request()
        if text is not None:
            return text, None
        return None, err2 or err

    return None, err


def _build_messages(model: str, user_message: str, history: list[dict] | None, sys_ctx=None, brain_ctx="") -> list[dict]:
    """Build the messages array with system prompt + history + user message."""
    messages = []
    
    # System Context String
    if sys_ctx:
        sys_info = f"""
CURRENT SYSTEM STATE:
RAM: {sys_ctx['ram_used']}GB used of {sys_ctx['ram_total']}GB ({sys_ctx['ram_available']}GB available)
CPU Temperature: {sys_ctx['cpu_temp']}°C
Power Profile: {sys_ctx['profile']}
Services: {sys_ctx['services_status']}
"""
    else:
        sys_info = ""

    knowledge = f"\nRELEVANT KNOWLEDGE:\n{brain_ctx}\n" if brain_ctx else ""

    system_prompt = f"""You are HIVE, the local AI assistant for Luminos OS.
You are a security guard — observe, report, guide.
Never fix things yourself. Guide the user.
{sys_info}{knowledge}
RULES:
- If asked about Python/venv: always check brain context before answering
- If something seems risky: say NO and explain why
- Keep answers short and direct
- Cite which rule or incident you're referencing"""

    messages.append({"role": "system", "content": system_prompt})
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

        # ── GET /progress ──
        if path == "/progress":
            stage, started_at = _state.progress
            elapsed = int((time.time() - started_at) * 1000) if started_at > 0 else 0
            self._send_json(200, {
                "stage": stage,
                "elapsed_ms": elapsed,
                "loaded_model": _state.current_model
            })
            return

        # ── GET /greeting ──
        if path == "/greeting":
            logger.debug("GET /greeting")
            if os.path.exists(GREETING_CACHE_PATH):
                try:
                    with open(GREETING_CACHE_PATH, "r") as f:
                        text = f.read().strip()
                        if text:
                            self._send_json(200, {"greeting": text, "cached": True})
                            return
                except OSError:
                    pass
            self._send_json(200, {"greeting": None, "cached": False})
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.rstrip("/")

        # ── POST /preload ──
        # Kicks off nexus loading in a background thread — returns immediately.
        # Called by the popup on open so the model is warming while user types.
        if path == "/preload":
            if _state.ready and _state.current_model == "nexus":
                self._send_json(200, {"status": "ready", "model": "nexus"})
            elif _state.progress[0] not in ("idle",):
                # Already loading — don't spawn a second swap
                self._send_json(200, {"status": "loading", "stage": _state.progress[0]})
            else:
                logger.info("POST /preload — starting nexus preload in background")
                threading.Thread(target=_swap_model, args=("nexus",), daemon=True).start()
                self._send_json(200, {"status": "loading"})
            return

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

        # ── POST /greeting/refresh ──
        if path == "/greeting/refresh":
            self._handle_greeting_refresh()
            return

        self._send_json(404, {"error": "Not found"})

    # ── Chat Logic ────────────────────────────────────────────────────────

    def _handle_greeting_refresh(self):
        """Generate a fresh greeting using Nexus and cache it."""
        logger.info("POST /greeting/refresh — refreshing cached greeting")
        
        # Ensure Nexus is loaded (re-use _swap_model logic)
        ok, swap_err = _swap_model("nexus")
        if not ok:
            logger.error("Failed to swap to Nexus for greeting refresh: %s", swap_err)
            self._send_json(500, {"status": "error", "error": swap_err})
            return

        system_prompt = (
            "You are Nexus. Generate ONE punchy greeting for Vratik opening a fresh chat. RULES: "
            "- MAXIMUM 4 words. "
            "- No full sentences. "
            "- No 'Hey Sam' or 'Hey Vratik' — too generic. "
            "- Vary tone: curious, hyped, chill, playful. "
            "- Output ONLY the greeting, no quotes, no explanation. "
            "Good examples: 'Inspired, Vratik?' / 'What's cooking?' / 'Back at it?' / 'Let's build.' / 'Yo, ready?'. "
            "Bad examples: 'Hey, what's up? Ready to dive in' / 'Hello! How can I help you today?'"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate one greeting now."}
        ]

        try:
            # We don't track stage for background refresh to avoid UI interference
            # but we use _call_llama directly
            response_text, infer_err = _call_llama(messages, "nexus")
            
            if infer_err:
                logger.error("Inference failed for greeting refresh: %s", infer_err)
                self._send_json(502, {"status": "error", "error": infer_err})
                return

            # Clean result
            greeting = response_text.strip().strip('"').strip("'")
            
            # Cache it
            os.makedirs(os.path.dirname(GREETING_CACHE_PATH), exist_ok=True)
            with open(GREETING_CACHE_PATH, "w") as f:
                f.write(greeting)
            
            logger.info("Successfully refreshed greeting cache: %s", greeting)
            self._send_json(200, {"status": "ok", "greeting": greeting})

        except Exception as e:
            logger.error("Unexpected error in greeting refresh: %s", e)
            self._send_json(500, {"status": "error", "error": str(e)})

    def _handle_chat(self):
        t_start = time.monotonic()

        data = self._read_json_body()
        if data is None:
            return

        user_message = data.get("message", "").strip()
        if not user_message:
            self._send_json(400, {"error": "Missing 'message' field"})
            return

        try:
            _state.set_stage("routing_check")

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

            # ── Early web intercept — no model needed ──────────────────────────
            # Check web intent BEFORE any _swap_model calls so web search works
            # even when llama-server is not running.
            # Chips bypass this (user explicitly chose a model).
            if not chip and detect_intent(user_message) == "web":
                logger.info("EARLY WEB INTERCEPT: fetching search results")
                _state.set_stage("web_search")
                search_results = _web_search(user_message)
                page_text = _fetch_best_page_text(search_results) if search_results else ""
                t_search = time.monotonic()

                if _state.ready:
                    # Llama is loaded — synthesize via Nexus
                    web_ctx = _format_web_context(user_message, search_results, page_text)
                    sys_ctx = get_system_context()
                    _state.set_stage("generating_nexus_web")
                    web_messages = _build_messages("nexus", user_message, history, sys_ctx, web_ctx)
                    response_text, infer_err = _call_llama(web_messages, "nexus")
                    t_end = time.monotonic()
                    if not infer_err:
                        clean_text = _strip_route_tags(response_text)
                        self._send_json(200, {
                            "agent": "Nexus",
                            "content": clean_text,
                            "thinking_time_ms": int((t_end - t_start) * 1000),
                            "routed": True,
                            "fallback_routed": True,
                            "route_target": "web",
                            "error": None,
                        })
                        return

                # No model loaded (or synthesis failed) — return raw results directly
                if search_results:
                    lines = [f"**Web results for:** {user_message}\n"]
                    for i, r in enumerate(search_results, 1):
                        lines.append(f"**{i}. {r['title']}**")
                        lines.append(r["snippet"])
                        lines.append(f"🔗 {r['url']}\n")
                    content = "\n".join(lines)
                else:
                    content = "No results found. Try a different query."
                t_end = time.monotonic()
                self._send_json(200, {
                    "agent": "Nexus",
                    "content": content,
                    "thinking_time_ms": int((t_end - t_start) * 1000),
                    "routed": True,
                    "fallback_routed": True,
                    "route_target": "web",
                    "error": None,
                })
                return
            # ── End early web intercept ────────────────────────────────────────

            # [CHANGE: gemini-cli | 2026-05-09] Context injection
            sys_ctx = get_system_context()
            brain_ctx = get_brain_context(user_message)

            # ── Path A: Chip is set → direct to mapped model ──
            if chip and chip in CHIP_TO_MODEL:
                target_model = CHIP_TO_MODEL[chip]
                _state.set_stage(f"swapping_to_{target_model}")
                ok, swap_err = _swap_model(target_model)
                if not ok:
                    self._send_json(500, self._error_response(swap_err))
                    return

                _state.set_stage(f"generating_{target_model}")
                messages = _build_messages(target_model, user_message, history, sys_ctx, brain_ctx)
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
            _state.set_stage("swapping_to_nexus")
            ok, swap_err = _swap_model("nexus")
            if not ok:
                self._send_json(500, self._error_response(swap_err))
                return

            _state.set_stage("generating_nexus")
            nexus_messages = _build_messages("nexus", user_message, history, sys_ctx, brain_ctx)
            nexus_response, infer_err = _call_llama(nexus_messages, "nexus")
            t_nexus = time.monotonic()

            if infer_err:
                self._send_json(502, self._error_response(infer_err))
                return

            # Check for route tags
            route_match = ROUTE_TAG_RE.search(nexus_response)
            route_target = None
            fallback_routed = False

            if route_match:
                route_target = route_match.group(1).lower()
            else:
                # [CHANGE: gemini-cli | 2026-05-03] Fallback intent detection
                route_target = detect_intent(user_message)
                if route_target:
                    fallback_routed = True
                    logger.info("FALLBACK ROUTING: Detected intent '%s' for message", route_target)

            if not route_target or route_target == "nexus":
                # Nexus handles it directly — no routing
                clean_text = _strip_route_tags(nexus_response)
                t_end = time.monotonic()

                # [CHANGE: gemini-cli | 2026-05-09] Log incident if needed
                log_incident(user_message)

                self._send_json(200, {
                    "agent": "Nexus",
                    "content": clean_text,
                    "thinking_time_ms": int((t_end - t_start) * 1000),
                    "routed": False,
                    "fallback_routed": False,
                    "route_target": None,
                    "error": None,
                })
                return

            # ── Web search route — fetch data then re-run Nexus with context ──
            if route_target == "web":
                logger.info("WEB ROUTE: fetching results for query: %s", user_message[:80])
                _state.set_stage("web_search")
                search_results = _web_search(user_message)
                page_text = ""
                if search_results:
                    page_text = _fetch_best_page_text(search_results)
                web_ctx = _format_web_context(user_message, search_results, page_text)
                # Re-run Nexus with web context injected so it can synthesize an answer
                _state.set_stage("swapping_to_nexus")
                ok, swap_err = _swap_model("nexus")
                if not ok:
                    self._send_json(500, self._error_response(swap_err))
                    return
                _state.set_stage("generating_nexus_web")
                web_messages = _build_messages("nexus", user_message, history, sys_ctx, web_ctx)
                response_text, infer_err = _call_llama(web_messages, "nexus")
                t_end = time.monotonic()
                if infer_err:
                    self._send_json(502, self._error_response(infer_err))
                    return
                clean_text = _strip_route_tags(response_text)
                self._send_json(200, {
                    "agent": "Nexus",
                    "content": clean_text,
                    "thinking_time_ms": int((t_end - t_start) * 1000),
                    "routed": True,
                    "fallback_routed": fallback_routed,
                    "route_target": "web",
                    "error": None,
                })
                return

            # ── Route to specialist ──
            if route_target not in ALLOWED_MODELS:
                # Unknown route target — return Nexus response stripped
                logger.warning("Unknown route target: %s", route_target)
                clean_text = _strip_route_tags(nexus_response)
                t_end = time.monotonic()

                # [CHANGE: gemini-cli | 2026-05-09] Log incident if needed
                log_incident(user_message)

                self._send_json(200, {
                    "agent": "Nexus",
                    "content": clean_text,
                    "thinking_time_ms": int((t_end - t_start) * 1000),
                    "routed": False,
                    "fallback_routed": False,
                    "route_target": None,
                    "error": None,
                })
                return

            _state.set_stage(f"routing_to_{route_target}")
            logger.info("ROUTING: Nexus → %s (fallback=%s)", route_target, fallback_routed)

            _state.set_stage(f"swapping_to_{route_target}")
            ok, swap_err = _swap_model(route_target)
            if not ok:
                # Swap failed — return Nexus response with error note
                clean_text = _strip_route_tags(nexus_response)
                self._send_json(500, {
                    "agent": "Nexus",
                    "content": clean_text,
                    "thinking_time_ms": int((time.monotonic() - t_start) * 1000),
                    "routed": not fallback_routed,
                    "fallback_routed": fallback_routed,
                    "route_target": route_target,
                    "error": f"Routing to {route_target} failed: {swap_err}",
                })
                return

            # Send ONLY the original user message to specialist (no Nexus artifacts)
            # [CHANGE: gemini-cli | 2026-05-09] Specialist also gets context
            _state.set_stage(f"generating_{route_target}")
            specialist_messages = _build_messages(route_target, user_message, history, sys_ctx, brain_ctx)
            specialist_response, infer_err = _call_llama(specialist_messages, route_target)
            t_end = time.monotonic()

            if infer_err:
                self._send_json(502, self._error_response(infer_err))
                return

            clean_text = _strip_route_tags(specialist_response)
            agent_name = {"nexus": "Nexus", "bolt": "Bolt", "nova": "Nova"}.get(route_target, route_target)

            # [CHANGE: gemini-cli | 2026-05-09] Log incident if needed
            log_incident(user_message)

            self._send_json(200, {
                "agent": agent_name,
                "content": clean_text,
                "thinking_time_ms": int((t_end - t_start) * 1000),
                "nexus_time_ms": int((t_nexus - t_start) * 1000),
                "specialist_time_ms": int((t_end - t_nexus) * 1000),
                "routed": not fallback_routed,
                "fallback_routed": fallback_routed,
                "route_target": route_target,
                "error": None,
            })

        finally:
            _state.set_stage("idle")

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


def _health_monitor():
    """
    Background thread: ping llama-server every 30s.
    If it's unreachable when we think it's ready, mark state not-ready.
    Catches idle-watchdog kills, OOM kills, crashes — any case where
    llama-server dies without telling the daemon.
    """
    while True:
        time.sleep(30)
        if _state.ready:
            try:
                with urlopen("http://localhost:8080/health", timeout=3) as resp:
                    body = resp.read()
                    if b"ok" not in body:
                        raise Exception("unhealthy")
            except Exception:
                logger.info("HEALTH MONITOR: llama-server unreachable — marking not ready")
                _state.set_model(None, ready=False)


def main():
    global _startup_time
    _startup_time = time.time()

    _acquire_lock()
    _load_system_prompts()

    # Background health monitor — keeps _state in sync when llama-server dies
    threading.Thread(target=_health_monitor, daemon=True).start()

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
