"""
src/sentinel/sentinel_daemon.py
Phase 5.11 Task 1 — Sentinel notification daemon.

When Sentinel flags suspicious activity:
  - Sends a critical notification (never auto-dismiss).
  - Logs to /var/log/luminos/sentinel.log with full context.
  - "View Details" action opens the log.

Log format per line:
  ISO_TIMESTAMP | process_name | PID | syscalls | classification

Pure helper (testable without NPU/notification system):
  format_sentinel_log_line(entry) → str
  parse_sentinel_log_line(line)   → dict | None
"""

import logging
import os
import subprocess
import time

logger = logging.getLogger("luminos.sentinel.daemon")

SENTINEL_LOG_PATH = "/var/log/luminos/sentinel.log"

# Classifications from npu_classifier.py
CLASSIFICATION_NORMAL     = "normal"
CLASSIFICATION_SUSPICIOUS = "suspicious"
CLASSIFICATION_BLOCK      = "block"


# ===========================================================================
# Pure helpers
# ===========================================================================

def format_sentinel_log_line(entry: dict) -> str:
    """
    Format a sentinel event dict as a single log line.

    Args:
        entry: Dict with keys: timestamp, process_name, pid,
               syscalls, classification, details (optional).

    Returns:
        Single-line string ending without newline.

    Example output:
        2026-04-06T14:30:00 | bash | 12345 | execve,connect | suspicious
    """
    ts      = entry.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
    name    = entry.get("process_name", "unknown")
    pid     = entry.get("pid", 0)
    syscalls = entry.get("syscalls", [])
    cls     = entry.get("classification", "unknown")
    details = entry.get("details", "")

    syscall_str = ",".join(syscalls) if isinstance(syscalls, list) else str(syscalls)
    parts = [ts, name, str(pid), syscall_str, cls]
    if details:
        parts.append(details)
    return " | ".join(parts)


def parse_sentinel_log_line(line: str) -> dict | None:
    """
    Parse one log line back into a dict.

    Args:
        line: String in format produced by format_sentinel_log_line.

    Returns:
        Dict with keys: timestamp, process_name, pid, syscalls,
        classification, details.
        None if line cannot be parsed.
    """
    if not line.strip():
        return None
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 5:
        return None
    try:
        return {
            "timestamp":       parts[0],
            "process_name":    parts[1],
            "pid":             int(parts[2]) if parts[2].isdigit() else 0,
            "syscalls":        [s for s in parts[3].split(",") if s],
            "classification":  parts[4],
            "details":         parts[5] if len(parts) > 5 else "",
        }
    except Exception:
        return None


# ===========================================================================
# Logging
# ===========================================================================

def log_sentinel_event(entry: dict) -> None:
    """
    Append a sentinel event to SENTINEL_LOG_PATH.

    Args:
        entry: Dict as accepted by format_sentinel_log_line.
    """
    try:
        os.makedirs(os.path.dirname(SENTINEL_LOG_PATH), exist_ok=True)
        line = format_sentinel_log_line(entry)
        with open(SENTINEL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        logger.warning(f"Failed to write sentinel log: {e}")


# ===========================================================================
# Notifications
# ===========================================================================

def notify_sentinel_alert(entry: dict) -> None:
    """
    Send a critical desktop notification for a suspicious event.
    Never auto-dismisses (urgency=critical).
    "View Details" action opens sentinel log viewer.

    Args:
        entry: Sentinel event dict.
    """
    process_name    = entry.get("process_name", "Unknown Process")
    classification  = entry.get("classification", "suspicious")
    details         = entry.get("details", "Unusual system activity detected")

    title = "Security Alert"
    body  = f"{process_name}: {details}" if details else \
            f"{process_name} flagged as {classification}"

    # Try Luminos notification system first
    try:
        from notifications.system_notifier import send_notification
        send_notification(
            title=title,
            body=body,
            urgency="critical",
            app_name="Sentinel",
            auto_dismiss=False,
        )
        return
    except Exception:
        pass

    # Fallback: notify-send
    try:
        subprocess.Popen(
            [
                "notify-send",
                "--urgency=critical",
                "--app-name=Sentinel",
                "--expire-time=0",
                f"--action=details=View Details",
                title,
                body,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug(f"notify-send error: {e}")


# ===========================================================================
# Sentinel daemon loop
# ===========================================================================

class SentinelDaemon:
    """
    Daemon that runs the Sentinel monitor and handles alert dispatch.

    Usage:
        daemon = SentinelDaemon()
        daemon.start()   # non-blocking — starts background thread
        daemon.stop()
    """

    def __init__(self):
        self._running    = False
        self._thread     = None

    def start(self) -> None:
        import threading
        self._running = True
        self._thread  = threading.Thread(
            target=self._run,
            name="sentinel-daemon",
            daemon=True,
        )
        self._thread.start()
        logger.info("Sentinel daemon started.")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Sentinel daemon stopped.")

    def _run(self) -> None:
        """Main daemon loop — calls process_events in a tight loop."""
        from sentinel.process_monitor import get_process_signals
        from sentinel.npu_classifier  import classify_signals
        from sentinel.threat_rules    import apply_threat_rules

        while self._running:
            try:
                self._scan_processes(get_process_signals, classify_signals,
                                     apply_threat_rules)
            except Exception as e:
                logger.error(f"Sentinel scan error: {e}")
            time.sleep(2)

    def _scan_processes(self, get_signals_fn, classify_fn,
                        rules_fn) -> None:
        """Scan running processes and handle any alerts."""
        try:
            pids = [
                int(p) for p in os.listdir("/proc")
                if p.isdigit()
            ]
        except OSError:
            return

        for pid in pids:
            if not self._running:
                break
            try:
                signals        = get_signals_fn(pid)
                rule_result    = rules_fn(signals)
                classification = rule_result.get("classification", "normal")

                if classification in (CLASSIFICATION_SUSPICIOUS,
                                      CLASSIFICATION_BLOCK):
                    entry = {
                        "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "process_name":   signals.get("process_name", "unknown"),
                        "pid":            pid,
                        "syscalls":       rule_result.get("triggered_rules", []),
                        "classification": classification,
                        "details":        rule_result.get("reason", ""),
                    }
                    log_sentinel_event(entry)
                    notify_sentinel_alert(entry)

                    if classification == CLASSIFICATION_BLOCK:
                        self._kill_process(pid, entry)

            except Exception:
                continue

    def _kill_process(self, pid: int, entry: dict) -> None:
        """Kill a blocked process."""
        try:
            import signal as sig
            os.kill(pid, sig.SIGKILL)
            logger.warning(
                f"Blocked and killed PID {pid} "
                f"({entry.get('process_name', '?')})"
            )
        except (ProcessLookupError, PermissionError) as e:
            logger.debug(f"Could not kill PID {pid}: {e}")

    def handle_threat(self, threat: dict) -> None:
        """
        External entry point — call this to dispatch a Sentinel threat.
        Can be used by npu_interface.py to inject NPU-detected threats.

        Args:
            threat: Dict with classification, process_name, pid, details.
        """
        classification = threat.get("classification", "normal")
        if classification == CLASSIFICATION_NORMAL:
            return

        entry = {
            "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%S"),
            "process_name":   threat.get("process_name", "unknown"),
            "pid":            threat.get("pid", 0),
            "syscalls":       threat.get("syscalls", []),
            "classification": classification,
            "details":        threat.get("details", ""),
        }
        log_sentinel_event(entry)
        notify_sentinel_alert(entry)


# Module-level singleton (started by luminos-session or luminos-ai service)
_daemon: SentinelDaemon | None = None


def get_daemon() -> SentinelDaemon:
    """Return (and create if needed) the global SentinelDaemon instance."""
    global _daemon
    if _daemon is None:
        _daemon = SentinelDaemon()
    return _daemon
