"""
src/gui/settings/__init__.py
Luminos Settings — public API.

Usage:
    from gui.settings import launch_settings
    launch_settings()
"""

import subprocess
import logging

logger = logging.getLogger("luminos-ai.gui.settings")


def launch_settings() -> None:
    """Launch the Luminos Settings app as a subprocess."""
    try:
        subprocess.Popen(["luminos-settings"])
    except FileNotFoundError:
        # Dev fallback — run via Python module
        import sys
        import os
        src = os.path.join(os.path.dirname(__file__), "..", "..")
        subprocess.Popen(
            [sys.executable, "-m", "gui.settings.settings_app"],
            cwd=src,
        )
    except Exception as e:
        logger.warning(f"Failed to launch settings: {e}")
