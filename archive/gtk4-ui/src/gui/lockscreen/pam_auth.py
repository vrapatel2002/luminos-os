"""
src/gui/lockscreen/pam_auth.py
PAM authentication wrapper for the Luminos lock screen.

Pure Python — no GTK, no display required.
`python-pam` is imported lazily so tests can mock it without installing it.

Backoff schedule (failed attempts → lockout duration):
  ≥ 3  → 30 s
  ≥ 5  → 120 s  (2 min)
  ≥ 7  → 300 s  (5 min)
"""

import logging
import os
import pwd
import time

logger = logging.getLogger(__name__)

# Backoff thresholds: (min_attempts, lockout_seconds)
_BACKOFF = [
    (7, 300),
    (5, 120),
    (3,  30),
]


class PAMAuth:
    """
    Wraps python-pam to provide authenticated lockout with exponential backoff.

    Attributes:
        service:      PAM service name (default "login").
        attempts:     Number of consecutive failed attempts.
        locked_until: Unix timestamp after which authentication is allowed again.
    """

    def __init__(self, service: str = "login"):
        self.service:      str         = service
        self.attempts:     int         = 0
        self.locked_until: float | None = None

    # -----------------------------------------------------------------------
    # User helpers
    # -----------------------------------------------------------------------

    def get_current_user(self) -> str:
        """Return the login name of the process owner."""
        try:
            return pwd.getpwuid(os.getuid()).pw_name
        except (KeyError, OSError):
            return os.environ.get("USER", "user")

    # -----------------------------------------------------------------------
    # Lockout check
    # -----------------------------------------------------------------------

    def is_locked_out(self) -> dict:
        """
        Return lockout status.

        Returns:
            {"locked": bool, "wait_seconds": int}
        """
        if self.locked_until is None:
            return {"locked": False, "wait_seconds": 0}
        remaining = self.locked_until - time.time()
        if remaining <= 0:
            self.locked_until = None
            return {"locked": False, "wait_seconds": 0}
        return {"locked": True, "wait_seconds": int(remaining) + 1}

    # -----------------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------------

    def authenticate(self, password: str) -> dict:
        """
        Try to authenticate the current user with the given password via PAM.

        Returns one of:
            {"success": True}
            {"success": False, "reason": "locked_out", "wait_seconds": int}
            {"success": False, "reason": "wrong_password",
             "attempts": int, "lockout_applied": bool}
        """
        lockout = self.is_locked_out()
        if lockout["locked"]:
            return {
                "success": False,
                "reason": "locked_out",
                "wait_seconds": lockout["wait_seconds"],
            }

        # Try PAM authentication
        success = self._pam_authenticate(password)

        if success:
            logger.info(f"PAMAuth: authentication succeeded for {self.get_current_user()}")
            self.attempts = 0
            self.locked_until = None
            return {"success": True}

        # Failed — increment counter and apply backoff if threshold reached
        self.attempts += 1
        lockout_applied = self._apply_backoff()
        logger.warning(
            f"PAMAuth: failed attempt {self.attempts} for {self.get_current_user()}"
            + (f" — lockout applied ({self.is_locked_out()['wait_seconds']}s)" if lockout_applied else "")
        )
        result: dict = {
            "success": False,
            "reason": "wrong_password",
            "attempts": self.attempts,
            "lockout_applied": lockout_applied,
        }
        if lockout_applied:
            result["wait_seconds"] = self.is_locked_out()["wait_seconds"]
        return result

    # -----------------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all failed attempts and any active lockout."""
        self.attempts = 0
        self.locked_until = None

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _pam_authenticate(self, password: str) -> bool:
        """
        Perform the actual PAM authentication call.
        Returns True on success, False on failure or if pam is unavailable.
        """
        try:
            import pam as pam_module  # python-pam
            p = pam_module.pam()
            return p.authenticate(
                self.get_current_user(),
                password,
                service=self.service,
            )
        except ImportError:
            logger.warning("PAMAuth: python-pam not installed — authentication denied")
            return False
        except Exception as e:
            logger.error(f"PAMAuth: PAM error — {e}")
            return False

    def _apply_backoff(self) -> bool:
        """
        Check if current attempt count triggers a lockout.
        Sets self.locked_until if so.
        Returns True if a lockout was applied.
        """
        for min_attempts, lockout_s in _BACKOFF:
            if self.attempts >= min_attempts:
                self.locked_until = time.time() + lockout_s
                logger.warning(
                    f"PAMAuth: {self.attempts} failed attempts — "
                    f"lockout for {lockout_s}s"
                )
                return True
        return False


# ---------------------------------------------------------------------------
# Pure helpers — testable without PAM installed
# ---------------------------------------------------------------------------

def _backoff_for_attempts(attempts: int) -> int:
    """
    Return the lockout duration in seconds for a given attempt count.
    Returns 0 if no lockout threshold is met.
    (Module-level pure function for unit testing.)
    """
    for min_attempts, lockout_s in _BACKOFF:
        if attempts >= min_attempts:
            return lockout_s
    return 0
