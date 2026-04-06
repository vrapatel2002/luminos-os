"""
src/classifier/sandbox_check.py
Phase 5.11 Task 4 — Verify Wine/Proton apps are properly sandboxed.

Checks:
  1. WINEPREFIX is under /tmp/luminos/prefixes/ (not ~/real home)
  2. HOME inside the Wine environment points to the sandbox dir (not real ~)

If a sandbox escape is detected:
  - Kill the process immediately (SIGKILL).
  - Send a critical notification.

Pure helper (testable):
  check_wine_sandbox(pid, env) → SandboxResult
"""

import logging
import os
import signal
import subprocess
import time

logger = logging.getLogger("luminos.classifier.sandbox_check")

# All Wine prefixes must be under this path
_SAFE_PREFIX_ROOT  = "/tmp/luminos/prefixes"
_REAL_HOME         = os.path.expanduser("~")


# ===========================================================================
# Data type
# ===========================================================================

class SandboxResult:
    """Result of a sandbox verification check."""

    def __init__(self, safe: bool, reason: str = "", pid: int = 0):
        self.safe   = safe
        self.reason = reason
        self.pid    = pid

    def __bool__(self) -> bool:
        return self.safe

    def __repr__(self) -> str:
        status = "SAFE" if self.safe else "ESCAPE"
        return f"SandboxResult({status}: {self.reason})"


# ===========================================================================
# Public API
# ===========================================================================

def check_wine_sandbox(pid: int, env: dict | None = None) -> SandboxResult:
    """
    Verify that a Wine process with the given PID is properly sandboxed.

    Reads environment from /proc/<pid>/environ if env not provided.

    Args:
        pid: PID of the Wine/Proton process to check.
        env: Optional environment dict (for testing).

    Returns:
        SandboxResult(safe=True) if sandboxed.
        SandboxResult(safe=False, reason=...) if escape detected.
    """
    if env is None:
        env = _read_proc_environ(pid)
        if env is None:
            return SandboxResult(safe=True, reason="cannot read environ")

    # Check 1: WINEPREFIX must be under _SAFE_PREFIX_ROOT
    wineprefix = env.get("WINEPREFIX", "")
    if wineprefix:
        real_prefix = os.path.realpath(wineprefix)
        safe_root   = os.path.realpath(_SAFE_PREFIX_ROOT)
        if not real_prefix.startswith(safe_root + os.sep) and \
           real_prefix != safe_root:
            return SandboxResult(
                safe=False,
                reason=f"WINEPREFIX={wineprefix} is outside safe root {_SAFE_PREFIX_ROOT}",
                pid=pid,
            )

    # Check 2: HOME must NOT point to the real home directory
    home = env.get("HOME", "")
    if home:
        real_home    = os.path.realpath(home)
        real_user_home = os.path.realpath(_REAL_HOME)
        if real_home == real_user_home:
            return SandboxResult(
                safe=False,
                reason=f"HOME={home} points to real home directory — sandbox escape",
                pid=pid,
            )

    # Check 3: HOME should be inside the WINEPREFIX or /tmp/luminos
    if home and wineprefix:
        real_home   = os.path.realpath(home)
        real_prefix = os.path.realpath(wineprefix)
        safe_root   = os.path.realpath(_SAFE_PREFIX_ROOT)
        if not (real_home.startswith(real_prefix) or
                real_home.startswith(safe_root)):
            return SandboxResult(
                safe=False,
                reason=f"HOME={home} is outside WINEPREFIX={wineprefix}",
                pid=pid,
            )

    return SandboxResult(safe=True, reason="sandbox verified", pid=pid)


def enforce_sandbox(pid: int, env: dict | None = None) -> SandboxResult:
    """
    Check sandbox and act on violations:
      - Kill the process (SIGKILL).
      - Send critical notification.
      - Log the event.

    Args:
        pid: PID of the Wine/Proton process.
        env: Optional environment dict (for testing).

    Returns:
        SandboxResult from check_wine_sandbox.
    """
    result = check_wine_sandbox(pid, env)
    if result.safe:
        return result

    logger.critical(
        f"SANDBOX ESCAPE DETECTED: PID {pid} — {result.reason}"
    )

    # Kill process immediately
    _kill_process(pid, result.reason)

    # Notify user
    _notify_escape(pid, result.reason)

    # Log to sentinel
    _log_escape(pid, result.reason)

    return result


def verify_on_launch(exe_path: str, proc: object) -> SandboxResult:
    """
    Called immediately after spawning a Wine process.
    Waits briefly for the process to initialize, then checks its environment.

    Args:
        exe_path: Path to the .exe being launched.
        proc:     subprocess.Popen object.

    Returns:
        SandboxResult.
    """
    # Give the process 1 second to initialize
    time.sleep(1)

    pid = getattr(proc, "pid", 0)
    if not pid:
        return SandboxResult(safe=True, reason="no PID")

    if not os.path.isdir(f"/proc/{pid}"):
        return SandboxResult(safe=True, reason="process already exited")

    return enforce_sandbox(pid)


# ===========================================================================
# Internal
# ===========================================================================

def _read_proc_environ(pid: int) -> dict | None:
    """
    Read /proc/<pid>/environ and return as a dict.
    Returns None if the file cannot be read.
    """
    environ_path = f"/proc/{pid}/environ"
    try:
        with open(environ_path, "rb") as f:
            raw = f.read()
        env = {}
        for entry in raw.split(b"\x00"):
            if b"=" in entry:
                key, _, val = entry.partition(b"=")
                env[key.decode("utf-8", errors="replace")] = \
                    val.decode("utf-8", errors="replace")
        return env
    except (OSError, PermissionError) as e:
        logger.debug(f"Cannot read /proc/{pid}/environ: {e}")
        return None


def _kill_process(pid: int, reason: str) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
        logger.warning(f"Killed PID {pid}: {reason}")
    except (ProcessLookupError, PermissionError) as e:
        logger.debug(f"Could not kill PID {pid}: {e}")


def _notify_escape(pid: int, reason: str) -> None:
    msg = f"PID {pid}: {reason[:100]}"
    try:
        from notifications.system_notifier import send_notification
        send_notification(
            title="Security: Sandbox Escape Blocked",
            body=msg,
            urgency="critical",
            app_name="Sentinel",
            auto_dismiss=False,
        )
        return
    except Exception:
        pass
    try:
        subprocess.Popen(
            [
                "notify-send",
                "--urgency=critical",
                "--expire-time=0",
                "--app-name=Sentinel",
                "Security: Sandbox Escape Blocked",
                msg,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _log_escape(pid: int, reason: str) -> None:
    from sentinel.sentinel_daemon import log_sentinel_event
    log_sentinel_event({
        "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "process_name":   "wine",
        "pid":            pid,
        "syscalls":       ["sandbox_check"],
        "classification": "block",
        "details":        reason,
    })
