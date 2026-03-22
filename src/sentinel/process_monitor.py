"""
process_monitor.py
Extracts live behavioral signals from a running process by PID.
Uses /proc filesystem directly — no psutil dependency.
"""

import os
import time


# Cmdline tokens that warrant suspicion
SUSPICIOUS_CMDLINE_TOKENS = [
    "curl",
    "wget",
    "nc ",
    "ncat",
    "chmod 777",
    "/tmp/",
    "base64",
    "--no-verify",
]


def _read_proc_file(path: str, default: str = "") -> str:
    """Read a /proc file, return default on any error."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except (OSError, PermissionError):
        return default


def _get_process_name(pid: int) -> str:
    raw = _read_proc_file(f"/proc/{pid}/comm").strip()
    return raw if raw else "unknown"


def _get_exe_path(pid: int) -> str:
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except (OSError, PermissionError):
        return "unknown"


def _get_cmdline(pid: int) -> str:
    raw = _read_proc_file(f"/proc/{pid}/cmdline")
    # cmdline is NUL-delimited
    return raw.replace('\x00', ' ').strip()


def _get_memory_mb(pid: int) -> float:
    """
    Read VmRSS from /proc/<pid>/status — resident set size in kB.
    Returns 0.0 on failure.
    """
    status = _read_proc_file(f"/proc/{pid}/status")
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1]) / 1024.0
                except ValueError:
                    return 0.0
    return 0.0


def _get_cpu_percent(pid: int, interval: float = 0.1) -> float:
    """
    Sample CPU usage over `interval` seconds using /proc/<pid>/stat.
    Returns percentage (0.0–100.0+), or 0.0 on failure.
    """
    def _read_cpu_ticks(pid: int):
        stat = _read_proc_file(f"/proc/{pid}/stat")
        if not stat:
            return None
        parts = stat.split()
        if len(parts) < 15:
            return None
        try:
            utime = int(parts[13])
            stime = int(parts[14])
            return utime + stime
        except (ValueError, IndexError):
            return None

    def _total_cpu_ticks():
        cpu = _read_proc_file("/proc/stat")
        if not cpu:
            return None
        for line in cpu.splitlines():
            if line.startswith("cpu "):
                parts = line.split()
                try:
                    return sum(int(x) for x in parts[1:])
                except ValueError:
                    return None
        return None

    t1_proc = _read_cpu_ticks(pid)
    t1_sys = _total_cpu_ticks()
    if t1_proc is None or t1_sys is None:
        return 0.0

    time.sleep(interval)

    t2_proc = _read_cpu_ticks(pid)
    t2_sys = _total_cpu_ticks()
    if t2_proc is None or t2_sys is None:
        return 0.0

    proc_delta = t2_proc - t1_proc
    sys_delta = t2_sys - t1_sys

    if sys_delta == 0:
        return 0.0

    # Scale by number of logical CPUs so result is per-process %
    try:
        num_cpus = os.cpu_count() or 1
    except Exception:
        num_cpus = 1

    return round((proc_delta / sys_delta) * 100.0 * num_cpus, 2)


def _get_open_files_count(pid: int) -> int:
    fd_dir = f"/proc/{pid}/fd"
    try:
        return len(os.listdir(fd_dir))
    except (OSError, PermissionError):
        return 0


def _get_network_connections(pid: int) -> int:
    """
    Count network socket fds by inspecting /proc/<pid>/net/tcp,
    /proc/<pid>/net/tcp6, /proc/<pid>/net/udp, /proc/<pid>/net/udp6.
    Falls back to counting socket symlinks in /proc/<pid>/fd.
    """
    count = 0
    for net_file in ("tcp", "tcp6", "udp", "udp6"):
        path = f"/proc/{pid}/net/{net_file}"
        raw = _read_proc_file(path)
        if raw:
            # First line is header; each subsequent line is one socket entry
            lines = [l for l in raw.strip().splitlines() if l.strip()]
            if lines:
                count += max(0, len(lines) - 1)

    # If /proc/<pid>/net isn't accessible (different net ns), fall back to fd scan
    if count == 0:
        fd_dir = f"/proc/{pid}/fd"
        try:
            for fd in os.listdir(fd_dir):
                try:
                    target = os.readlink(f"{fd_dir}/{fd}")
                    if target.startswith("socket:"):
                        count += 1
                except OSError:
                    pass
        except (OSError, PermissionError):
            pass

    return count


def _get_child_process_count(pid: int) -> int:
    """Count direct children by scanning /proc for processes whose ppid matches."""
    count = 0
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            status = _read_proc_file(f"/proc/{entry}/status")
            for line in status.splitlines():
                if line.startswith("PPid:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == str(pid):
                        count += 1
                    break
    except (OSError, PermissionError):
        pass
    return count


def _is_elevated(pid: int) -> bool:
    """Return True if process is running as UID 0 (root)."""
    status = _read_proc_file(f"/proc/{pid}/status")
    for line in status.splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            # Uid: real  effective  saved  fs
            if len(parts) >= 3:
                try:
                    return int(parts[1]) == 0 or int(parts[2]) == 0
                except ValueError:
                    return False
    return False


def _cmdline_has_suspicious(cmdline: str) -> bool:
    return any(token in cmdline for token in SUSPICIOUS_CMDLINE_TOKENS)


def _pid_exists(pid: int) -> bool:
    return os.path.isdir(f"/proc/{pid}")


def get_process_signals(pid: int) -> dict:
    """
    Collect live behavioral signals for a running process.

    Returns a dict with all signal fields. On PermissionError or
    missing process, returns partial data with safe defaults rather
    than raising.
    """
    if not _pid_exists(pid):
        return {
            "pid": pid,
            "process_name": "unknown",
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "open_files_count": 0,
            "network_connections": 0,
            "child_process_count": 0,
            "is_elevated": False,
            "cmdline_has_suspicious": False,
            "exe_path": "unknown",
            "error": "process_not_found",
        }

    process_name  = _get_process_name(pid)
    exe_path      = _get_exe_path(pid)
    cmdline       = _get_cmdline(pid)
    cpu_percent   = _get_cpu_percent(pid)
    memory_mb     = _get_memory_mb(pid)
    open_files    = _get_open_files_count(pid)
    net_conns     = _get_network_connections(pid)
    children      = _get_child_process_count(pid)
    elevated      = _is_elevated(pid)
    susp_cmd      = _cmdline_has_suspicious(cmdline)

    return {
        "pid":                    pid,
        "process_name":           process_name,
        "cpu_percent":            cpu_percent,
        "memory_mb":              memory_mb,
        "open_files_count":       open_files,
        "network_connections":    net_conns,
        "child_process_count":    children,
        "is_elevated":            elevated,
        "cmdline_has_suspicious": susp_cmd,
        "exe_path":               exe_path,
    }
