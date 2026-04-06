"""
src/sentinel/network_monitor.py
Phase 5.11 Task 3 — Outbound network connection monitor.

Scans /proc/net/tcp and /proc/net/tcp6 every 60 seconds.
Logs any Luminos OS process making outbound connections
(there should be none — Luminos itself is zero telemetry).

State: ESTABLISHED connections with remote port != 0 are outbound.

Pure helpers (testable without a running system):
  parse_proc_net_tcp(raw_text)     → list[dict]
  get_process_name_for_inode(inode, pid_map) → str
  is_outbound(tcp_entry)           → bool

Usage:
  monitor = NetworkMonitor()
  monitor.start()   # background thread
  connections = monitor.get_recent_connections()
  monitor.stop()
"""

import logging
import os
import socket
import struct
import threading
import time

logger = logging.getLogger("luminos.sentinel.network_monitor")

# State: ESTABLISHED
_TCP_ESTABLISHED = "01"

# Network monitor log
_NETMON_LOG = os.path.expanduser("~/.local/share/luminos/network_monitor.log")

# Luminos process names to watch (outbound from these = zero telemetry violation)
_LUMINOS_PROCS = frozenset({
    "luminos-ai", "luminos-bar", "luminos-dock", "luminos-session",
    "luminos-sentinel", "luminos-firstrun", "luminos-settings",
    "luminos-launcher", "python3",
})


# ===========================================================================
# Pure helpers
# ===========================================================================

def parse_proc_net_tcp(raw_text: str) -> list:
    """
    Parse the contents of /proc/net/tcp or /proc/net/tcp6.

    Args:
        raw_text: Contents of the file as a string.

    Returns:
        List of dicts with keys:
          local_addr, local_port, remote_addr, remote_port,
          state, inode
    """
    entries = []
    lines   = raw_text.strip().splitlines()
    if not lines:
        return entries

    # Skip header
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            local_hex  = parts[1]
            remote_hex = parts[2]
            state      = parts[3]
            inode      = int(parts[9])

            local_addr,  local_port  = _decode_addr(local_hex)
            remote_addr, remote_port = _decode_addr(remote_hex)

            entries.append({
                "local_addr":   local_addr,
                "local_port":   local_port,
                "remote_addr":  remote_addr,
                "remote_port":  remote_port,
                "state":        state,
                "inode":        inode,
            })
        except (ValueError, IndexError):
            continue
    return entries


def is_outbound(tcp_entry: dict) -> bool:
    """
    Return True if a TCP entry represents an outbound ESTABLISHED connection.
    Outbound = remote_port is non-zero and state is ESTABLISHED.

    Args:
        tcp_entry: Dict as returned by parse_proc_net_tcp.

    Returns:
        True if this is an outbound connection.
    """
    return (
        tcp_entry.get("state") == _TCP_ESTABLISHED
        and tcp_entry.get("remote_port", 0) != 0
        and not _is_loopback(tcp_entry.get("remote_addr", ""))
    )


def get_inode_to_pid_map() -> dict:
    """
    Build a mapping from socket inode → PID by scanning /proc/*/fd.

    Returns:
        Dict: {inode_int: pid_int}
    """
    inode_map = {}
    try:
        for pid_str in os.listdir("/proc"):
            if not pid_str.isdigit():
                continue
            fd_dir = f"/proc/{pid_str}/fd"
            try:
                for fd in os.listdir(fd_dir):
                    try:
                        target = os.readlink(f"{fd_dir}/{fd}")
                        if target.startswith("socket:["):
                            inode = int(target[8:-1])
                            inode_map[inode] = int(pid_str)
                    except (OSError, ValueError):
                        pass
            except (OSError, PermissionError):
                pass
    except OSError:
        pass
    return inode_map


def get_process_name(pid: int) -> str:
    """Return process name for pid, or 'unknown'."""
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


# ===========================================================================
# NetworkMonitor class
# ===========================================================================

class NetworkMonitor:
    """
    Background thread that scans /proc/net/tcp every 60 seconds.
    Logs outbound connections from Luminos processes.
    """

    def __init__(self, scan_interval: int = 60):
        self._interval   = scan_interval
        self._running    = False
        self._thread     = None
        self._lock       = threading.Lock()
        self._recent: list[dict] = []   # Last N connections found

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(
            target=self._run,
            name="luminos-netmon",
            daemon=True,
        )
        self._thread.start()
        logger.info("Network monitor started.")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Network monitor stopped.")

    def get_recent_connections(self) -> list:
        """Return a snapshot of recently observed connections."""
        with self._lock:
            return list(self._recent)

    def scan_now(self) -> list:
        """Run one scan immediately and return results."""
        return self._scan()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while self._running:
            try:
                self._scan()
            except Exception as e:
                logger.error(f"Network scan error: {e}")
            # Sleep in small increments so stop() is responsive
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)

    def _scan(self) -> list:
        inode_map   = get_inode_to_pid_map()
        connections = []

        for filename in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(filename, "r") as f:
                    raw = f.read()
                entries = parse_proc_net_tcp(raw)
                for entry in entries:
                    if not is_outbound(entry):
                        continue
                    pid  = inode_map.get(entry["inode"], 0)
                    name = get_process_name(pid) if pid else "unknown"
                    conn = {
                        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "process":     name,
                        "pid":         pid,
                        "remote_addr": entry["remote_addr"],
                        "remote_port": entry["remote_port"],
                    }
                    connections.append(conn)

                    # Log if it's a Luminos process (zero-telemetry check)
                    if name in _LUMINOS_PROCS:
                        self._log_luminos_connection(conn)
            except (OSError, PermissionError):
                pass

        with self._lock:
            self._recent = connections[-100:]   # keep last 100

        return connections

    def _log_luminos_connection(self, conn: dict) -> None:
        """
        Log an outbound connection from a Luminos process.
        Should never happen — Luminos is zero telemetry.
        """
        line = (
            f"{conn['timestamp']} | LUMINOS_OUTBOUND | "
            f"{conn['process']} (pid={conn['pid']}) → "
            f"{conn['remote_addr']}:{conn['remote_port']}"
        )
        logger.warning(f"Zero-telemetry violation: {line}")
        try:
            os.makedirs(os.path.dirname(_NETMON_LOG), exist_ok=True)
            with open(_NETMON_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


# ===========================================================================
# Helpers
# ===========================================================================

def _decode_addr(hex_str: str) -> tuple:
    """
    Decode a hex address:port string from /proc/net/tcp.

    Handles both IPv4 (8 hex chars) and IPv6 (32 hex chars).

    Returns:
        (ip_str, port_int)
    """
    addr_hex, port_hex = hex_str.split(":")
    port = int(port_hex, 16)

    if len(addr_hex) == 8:
        # IPv4 — little-endian
        raw  = int(addr_hex, 16)
        addr = socket.inet_ntop(
            socket.AF_INET,
            struct.pack("<I", raw)
        )
    else:
        # IPv6 — four little-endian 32-bit words
        raw = bytes.fromhex(addr_hex)
        # Each 4-byte word is little-endian
        words = [raw[i:i+4] for i in range(0, 16, 4)]
        ipv6_bytes = b"".join(
            struct.pack(">I", struct.unpack("<I", w)[0]) for w in words
        )
        addr = socket.inet_ntop(socket.AF_INET6, ipv6_bytes)

    return addr, port


def _is_loopback(addr: str) -> bool:
    """Return True if addr is a loopback address."""
    return (
        addr.startswith("127.")
        or addr == "::1"
        or addr.startswith("::ffff:127.")
    )


# Module-level singleton
_monitor: NetworkMonitor | None = None


def get_monitor() -> NetworkMonitor:
    """Return (and create if needed) the global NetworkMonitor."""
    global _monitor
    if _monitor is None:
        _monitor = NetworkMonitor()
    return _monitor
