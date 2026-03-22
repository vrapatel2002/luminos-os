"""
threat_rules.py
Rule-based threat classifier for live process signals.

Status levels:  safe | suspicious | dangerous
Actions:        allow | warn | block
"""


def assess(signals: dict) -> dict:
    """
    Apply priority-ordered threat rules to process signals.

    Args:
        signals: dict from process_monitor.get_process_signals()

    Returns:
        {
            "status":     "safe" | "suspicious" | "dangerous",
            "confidence": float (0.0 – 1.0),
            "flags":      list[str],
            "action":     "allow" | "warn" | "block",
        }
    """
    elevated      = signals.get("is_elevated", False)
    susp_cmd      = signals.get("cmdline_has_suspicious", False)
    cpu_pct       = signals.get("cpu_percent", 0.0)
    net_conns     = signals.get("network_connections", 0)
    memory_mb     = signals.get("memory_mb", 0.0)

    # Rule 1 — elevated process with suspicious cmdline tokens
    if elevated and susp_cmd:
        return {
            "status":     "dangerous",
            "confidence": 0.95,
            "flags":      ["elevated+suspicious_cmd"],
            "action":     "block",
        }

    # Rule 2 — CPU spike combined with abnormally high network activity
    if cpu_pct > 90 and net_conns > 50:
        return {
            "status":     "dangerous",
            "confidence": 0.90,
            "flags":      ["cpu_spike+high_network"],
            "action":     "block",
        }

    # Rule 3 — suspicious cmdline tokens (not elevated)
    if susp_cmd:
        return {
            "status":     "suspicious",
            "confidence": 0.75,
            "flags":      ["suspicious_cmdline"],
            "action":     "warn",
        }

    # Rule 4 — elevated process with notable network activity
    if elevated and net_conns > 20:
        return {
            "status":     "suspicious",
            "confidence": 0.70,
            "flags":      ["elevated+network"],
            "action":     "warn",
        }

    # Rule 5 — high memory + elevated network (potential data exfil pattern)
    if memory_mb > 2000 and net_conns > 30:
        return {
            "status":     "suspicious",
            "confidence": 0.65,
            "flags":      ["high_mem+network"],
            "action":     "warn",
        }

    # Fallback — no threat indicators found
    return {
        "status":     "safe",
        "confidence": 0.95,
        "flags":      [],
        "action":     "allow",
    }
