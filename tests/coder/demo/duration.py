import re

def parse_duration(s: str) -> int:
    """Parse a duration string like '1h30m', '45s', '2h' into total seconds (int).

    Supported units: h (hours), m (minutes), s (seconds), each at most once,
    always in order h → m → s. Raises ValueError for empty or malformed input.
    """
    if not isinstance(s, str):
        raise TypeError(f"Duration must be a string, got {type(s).__name__}")
    if not s.strip():
        raise ValueError(f"Empty duration: {s!r}")

    text = s.strip()
    pattern = r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$'
    m = re.match(pattern, text)
    if not m:
        raise ValueError(f"Invalid duration: {text!r}")

    hours, minutes, secs = m.groups()

    total = 0
    if hours is not None:
        total += int(hours) * 3600
    if minutes is not None:
        total += int(minutes) * 60
    if secs is not None:
        total += int(secs)

    return total
