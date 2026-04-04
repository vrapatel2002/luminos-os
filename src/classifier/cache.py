"""
src/classifier/cache.py
Router result cache — stores classification decisions by file hash.

Cache location: ~/.cache/luminos/router/
Each entry is a JSON file named by the SHA-256 hash of the executable.
Results are cached permanently — analysis runs once per unique binary.
"""

import hashlib
import json
import logging
import os

logger = logging.getLogger("luminos-ai.classifier.cache")

_CACHE_DIR = os.path.expanduser("~/.cache/luminos/router/")


def _hash_file(path: str) -> str:
    """Compute SHA-256 of a file's contents (first 16 MB for speed)."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
                if f.tell() >= 16 * 1024 * 1024:
                    break
    except OSError:
        return ""
    # Include file size in hash so truncated reads still produce unique keys
    h.update(str(os.path.getsize(path)).encode())
    return h.hexdigest()


def get_cached(exe_path: str) -> dict | None:
    """
    Look up a cached classification result for the given executable.

    Args:
        exe_path: Path to the Windows executable.

    Returns:
        Cached decision dict, or None if not cached.
    """
    file_hash = _hash_file(exe_path)
    if not file_hash:
        return None

    cache_file = os.path.join(_CACHE_DIR, f"{file_hash}.json")
    if not os.path.isfile(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "layer" in data:
            logger.debug(f"Cache hit for {os.path.basename(exe_path)}: {data['layer']}")
            data["cached"] = True
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Cache read error: {e}")

    return None


def store(exe_path: str, result: dict) -> bool:
    """
    Cache a classification result for the given executable.

    Args:
        exe_path: Path to the Windows executable.
        result:   Decision dict from the router.

    Returns:
        True on success, False on error.
    """
    file_hash = _hash_file(exe_path)
    if not file_hash:
        return False

    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(_CACHE_DIR, f"{file_hash}.json")

        # Store only the decision fields, not internal state
        entry = {
            "zone":       result.get("zone"),
            "layer":      result.get("layer"),
            "confidence": result.get("confidence"),
            "reason":     result.get("reason"),
            "exe_name":   os.path.basename(exe_path),
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)

        logger.debug(f"Cached result for {os.path.basename(exe_path)}: {entry['layer']}")
        return True
    except OSError as e:
        logger.debug(f"Cache write error: {e}")
        return False


def clear_cache() -> int:
    """
    Remove all cached classification results.

    Returns:
        Number of cache entries removed.
    """
    if not os.path.isdir(_CACHE_DIR):
        return 0
    removed = 0
    try:
        for name in os.listdir(_CACHE_DIR):
            if name.endswith(".json"):
                os.remove(os.path.join(_CACHE_DIR, name))
                removed += 1
    except OSError:
        pass
    return removed
