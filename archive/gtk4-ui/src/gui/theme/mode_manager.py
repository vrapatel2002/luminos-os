"""
src/gui/theme/mode_manager.py
Dark/light mode management with time-based auto scheduling.

Rules:
- Default is auto mode: light 6am–7pm, dark 7pm–6am.
- set_manual() overrides auto until set_auto() clears it.
- get_mode() always returns the current effective bool (True=dark).
- No I/O — _calculate_auto_mode() reads datetime only.
"""

import datetime
import logging

logger = logging.getLogger("luminos-ai.gui.theme.mode")

# Hours for automatic light mode window (inclusive start, exclusive end)
_LIGHT_START = 6    # 6:00 AM
_LIGHT_END   = 19   # 7:00 PM


class ModeManager:
    """
    Manages dark/light mode selection.

    Manual override takes priority over auto scheduling.
    Call set_auto() to return to time-based switching.
    """

    def __init__(self):
        self.manual_override: bool | None = None   # None = auto
        self.dark_mode: bool = True
        self._calculate_auto_mode()

    def _calculate_auto_mode(self):
        """Update dark_mode based on current hour. Light: 6am–7pm."""
        hour = datetime.datetime.now().hour
        self.dark_mode = not (_LIGHT_START <= hour < _LIGHT_END)
        logger.debug(f"Auto mode: hour={hour} → {'dark' if self.dark_mode else 'light'}")

    def get_mode(self) -> bool:
        """
        Return current effective mode.

        Returns:
            True = dark mode, False = light mode.
        """
        if self.manual_override is not None:
            return self.manual_override
        self._calculate_auto_mode()
        return self.dark_mode

    def set_manual(self, dark: bool):
        """
        Force a specific mode, overriding auto scheduling.

        Args:
            dark: True for dark mode, False for light.
        """
        self.manual_override = dark
        self.dark_mode = dark
        logger.info(f"Mode manually set to {'dark' if dark else 'light'}")

    def set_auto(self):
        """Clear manual override and return to time-based auto mode."""
        self.manual_override = None
        self._calculate_auto_mode()
        logger.info(f"Mode returned to auto ({'dark' if self.dark_mode else 'light'})")

    def is_auto(self) -> bool:
        """Return True if currently in automatic mode."""
        return self.manual_override is None

    def get_css(self) -> str:
        """Return the full GTK4 CSS string for the current mode."""
        from .gtk_css import generate_css
        return generate_css(self.get_mode())

    def get_colors(self) -> dict:
        """Return the color palette dict for the current mode."""
        from .colors import get_colors
        return get_colors(self.get_mode())
