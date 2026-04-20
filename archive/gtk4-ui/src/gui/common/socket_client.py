"""
src/gui/common/socket_client.py
Unix socket client for communicating with the Luminos AI daemon.

Rules:
- Each send() call opens a fresh connection and closes it after the reply.
- Never raises — all exceptions return an error dict.
- Timeout default 3s to avoid blocking the GUI event loop.
- Socket path matches daemon: /tmp/luminos-ai.sock
"""

import json
import logging
import socket

logger = logging.getLogger("luminos-ai.gui.socket_client")

# Socket path — matches src/daemon/main.py SOCKET_PATH
DEFAULT_SOCKET_PATH = "/tmp/luminos-ai.sock"
_RECV_BUFFER        = 65536   # 64 KB — enough for any daemon response


class DaemonClient:
    """
    Thin synchronous client for the luminos-ai Unix socket.

    Usage:
        client = DaemonClient()
        result = client.send({"type": "ping"})
        # → {"status": "ok", "service": "luminos-ai"}
        # or {"error": "...", "available": False} on failure
    """

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path

    def send(self, request: dict, timeout: float = 3.0) -> dict:
        """
        Send a JSON request to the daemon and return the parsed response.

        Args:
            request: Dict to send as JSON.
            timeout: Socket timeout in seconds.

        Returns:
            Parsed response dict, or {"error": str, "available": False}.
        """
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect(self.socket_path)
                s.sendall(json.dumps(request).encode("utf-8"))

                chunks = []
                while True:
                    chunk = s.recv(_RECV_BUFFER)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    # Stop if we have a complete JSON object
                    try:
                        data = b"".join(chunks)
                        result = json.loads(data.decode("utf-8"))
                        return result
                    except json.JSONDecodeError:
                        continue   # need more data

                data = b"".join(chunks)
                return json.loads(data.decode("utf-8"))

        except (FileNotFoundError, ConnectionRefusedError, PermissionError) as e:
            # Daemon not running, socket missing, or not accessible — silent.
            logger.debug("Daemon unavailable at %s: %s", self.socket_path, e)
            return {"error": "daemon not running", "available": False}
        except socket.timeout:
            logger.debug("Daemon request timed out: %s", self.socket_path)
            return {"error": "timeout", "available": False}
        except json.JSONDecodeError as e:
            logger.debug("Invalid JSON from daemon: %s", e)
            return {"error": f"invalid response: {e}", "available": False}
        except Exception as e:
            logger.debug("Daemon client error: %s", e)
            return {"error": str(e), "available": False}

    def ping(self) -> bool:
        """Return True if daemon is reachable and responds to ping."""
        result = self.send({"type": "ping"})
        return result.get("status") == "ok"
