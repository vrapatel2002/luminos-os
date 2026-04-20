"""
src/gui/greeter/greetd_client.py
Minimal greetd IPC client.

greetd communicates over a Unix socket at $GREETD_SOCK.
Protocol: JSON messages framed with a 4-byte big-endian length header.

Message types (greeter → greetd):
  create_session:  {"type": "create_session", "username": str}
  post_auth_message_response: {"type": "post_auth_message_response", "response": str | None}
  start_session:   {"type": "start_session", "cmd": [str, ...]}
  cancel_session:  {"type": "cancel_session"}

Response types (greetd → greeter):
  success:         {"type": "success"}
  error:           {"type": "error", "error_type": str, "description": str}
  auth_message:    {"type": "auth_message", "auth_message_type": str, "auth_message": str}
"""

import json
import logging
import os
import socket
import struct

logger = logging.getLogger(__name__)


class GreetdClient:
    """Synchronous greetd IPC client."""

    def __init__(self):
        self._sock_path = os.environ.get("GREETD_SOCK", "")
        self._sock: socket.socket | None = None

    @property
    def available(self) -> bool:
        """True if GREETD_SOCK is set and the socket exists."""
        return bool(self._sock_path) and os.path.exists(self._sock_path)

    def _connect(self):
        if self._sock is not None:
            return
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(self._sock_path)
        self._sock.settimeout(10)

    def _send(self, msg: dict) -> dict:
        """Send a JSON message and return the response."""
        self._connect()
        payload = json.dumps(msg).encode()
        header = struct.pack(">I", len(payload))
        self._sock.sendall(header + payload)
        return self._recv()

    def _recv(self) -> dict:
        """Read a length-prefixed JSON response."""
        raw_len = self._recvall(4)
        length = struct.unpack(">I", raw_len)[0]
        raw_data = self._recvall(length)
        return json.loads(raw_data.decode())

    def _recvall(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("greetd socket closed")
            data += chunk
        return data

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    # -------------------------------------------------------------------
    # High-level API
    # -------------------------------------------------------------------

    def create_session(self, username: str) -> dict:
        """Start a new login session for the given user."""
        return self._send({"type": "create_session", "username": username})

    def post_auth_response(self, response: str | None) -> dict:
        """Respond to an auth_message (password prompt)."""
        return self._send({
            "type": "post_auth_message_response",
            "response": response,
        })

    def start_session(self, cmd: list[str]) -> dict:
        """Launch the user's session with the given command."""
        return self._send({"type": "start_session", "cmd": cmd})

    def cancel_session(self) -> dict:
        """Cancel the current login session."""
        return self._send({"type": "cancel_session"})
