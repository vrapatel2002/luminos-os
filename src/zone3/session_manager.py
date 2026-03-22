"""
session_manager.py
Manages Firecracker VM session lifecycle — create, track, destroy, clean up.

Each Zone 3 session gets an isolated working directory under SESSION_DIR.
Sessions must be explicitly destroyed after use — nothing persists.
"""

import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("luminos-ai.zone3.sessions")

SESSION_DIR = "/tmp/luminos-vms/"


def _session_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, session_id)


def _dir_size_mb(path: str) -> float:
    """Recursively sum file sizes under path, return MB."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass
    except OSError:
        pass
    return total / (1024 * 1024)


def create_session() -> str:
    """
    Allocate a new session: generate an ID, create its working directory.

    Returns:
        session_id: 8-char hex string.

    Raises:
        OSError: if the session directory cannot be created.
    """
    session_id = uuid.uuid4().hex[:8]
    session_path = _session_path(session_id)
    os.makedirs(session_path, exist_ok=True)
    logger.info(f"Session {session_id} created at {session_path}")
    return session_id


def destroy_session(session_id: str) -> bool:
    """
    Permanently remove a session's working directory.

    Args:
        session_id: The session to destroy.

    Returns:
        True  — directory was found and removed.
        False — session not found (already gone or never existed).
    """
    session_path = _session_path(session_id)
    if not os.path.isdir(session_path):
        logger.warning(f"Session {session_id} not found — nothing to destroy")
        return False

    try:
        shutil.rmtree(session_path)
        logger.info(f"Session {session_id} destroyed — quarantine cleared")
        return True
    except OSError as e:
        logger.error(f"Failed to destroy session {session_id}: {e}")
        return False


def list_sessions() -> list:
    """
    Return metadata for every active session directory.

    Returns:
        List of dicts: [{"session_id": str, "created": str, "size_mb": float}]
        Empty list if SESSION_DIR does not exist.
    """
    if not os.path.isdir(SESSION_DIR):
        return []

    sessions = []
    try:
        entries = sorted(os.listdir(SESSION_DIR))
    except OSError:
        return []

    for name in entries:
        full_path = os.path.join(SESSION_DIR, name)
        if not os.path.isdir(full_path):
            continue

        try:
            ctime = os.path.getctime(full_path)
            created_str = datetime.fromtimestamp(ctime, tz=timezone.utc).isoformat()
        except OSError:
            created_str = "unknown"

        sessions.append({
            "session_id": name,
            "created":    created_str,
            "size_mb":    _dir_size_mb(full_path),
        })

    return sessions


def cleanup_old_sessions(max_age_hours: int = 24) -> int:
    """
    Remove sessions whose directories are older than max_age_hours.

    Args:
        max_age_hours: Maximum allowed session age in hours (default 24).

    Returns:
        Number of sessions removed.
    """
    if not os.path.isdir(SESSION_DIR):
        return 0

    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    try:
        entries = os.listdir(SESSION_DIR)
    except OSError:
        return 0

    for name in entries:
        full_path = os.path.join(SESSION_DIR, name)
        if not os.path.isdir(full_path):
            continue
        try:
            if os.path.getctime(full_path) < cutoff:
                shutil.rmtree(full_path)
                logger.info(f"Session {name} cleaned up (age > {max_age_hours}h)")
                removed += 1
        except OSError as e:
            logger.warning(f"Could not clean session {name}: {e}")

    return removed
