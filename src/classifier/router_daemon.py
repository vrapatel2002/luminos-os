"""
src/classifier/router_daemon.py
Compatibility router daemon — Unix socket server.

Listens on /run/user/<uid>/luminos-router.sock for classification requests.
Protocol: newline-delimited JSON (one request per line, one response per line).

Request:
    {"type": "classify", "path": "/path/to/app.exe"}

Response:
    {"zone": 2, "layer": "proton", "confidence": 0.90, "reason": "...", "cached": bool}

Also supports:
    {"type": "status"}        → {"online": true, "cache_size": int}
    {"type": "clear_cache"}   → {"cleared": int}

Usage:
    python3 -m classifier.router_daemon
"""

import json
import logging
import os
import signal
import socket
import sys
import threading

logger = logging.getLogger("luminos-ai.router-daemon")

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from classifier import classify_binary
from classifier.cache import get_cached, store, clear_cache, _CACHE_DIR


def _get_socket_path() -> str:
    uid = os.getuid()
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    return os.path.join(runtime_dir, "luminos-router.sock")


def _handle_request(data: dict) -> dict:
    """Process a single JSON request and return a response dict."""
    req_type = data.get("type", "")

    if req_type == "classify":
        path = data.get("path", "")
        if not path or not os.path.isfile(path):
            return {"error": f"File not found: {path}"}

        # Check cache first
        cached = get_cached(path)
        if cached:
            return cached

        # Full classification pipeline
        result = classify_binary(path)
        store(path, result)
        result["cached"] = False
        return result

    elif req_type == "status":
        cache_count = 0
        if os.path.isdir(_CACHE_DIR):
            try:
                cache_count = len([f for f in os.listdir(_CACHE_DIR) if f.endswith(".json")])
            except OSError:
                pass
        return {"online": True, "cache_size": cache_count}

    elif req_type == "clear_cache":
        cleared = clear_cache()
        return {"cleared": cleared}

    else:
        return {"error": f"Unknown request type: {req_type}"}


def _handle_client(conn: socket.socket, addr) -> None:
    """Handle a single client connection (one request-response per line)."""
    try:
        conn.settimeout(30)
        buf = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line.decode("utf-8"))
                    response = _handle_request(request)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    response = {"error": f"Invalid JSON: {e}"}
                conn.sendall(json.dumps(response).encode("utf-8") + b"\n")
    except (socket.timeout, ConnectionResetError, BrokenPipeError):
        pass
    except Exception as e:
        logger.debug(f"Client handler error: {e}")
    finally:
        conn.close()


def run_daemon() -> None:
    """Start the router daemon, listening on a Unix socket."""
    sock_path = _get_socket_path()

    # Clean up stale socket
    if os.path.exists(sock_path):
        try:
            os.unlink(sock_path)
        except OSError:
            pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    os.chmod(sock_path, 0o600)
    server.listen(8)
    server.settimeout(1.0)

    logger.info(f"Router daemon listening on {sock_path}")

    _shutdown = threading.Event()

    def _signal_handler(signum, frame):
        _shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        while not _shutdown.is_set():
            try:
                conn, addr = server.accept()
                t = threading.Thread(target=_handle_client, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
    finally:
        server.close()
        try:
            os.unlink(sock_path)
        except OSError:
            pass
        logger.info("Router daemon stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    run_daemon()
