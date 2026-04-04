"""
src/gui/theme/__init__.py
Luminos GUI Theme — public exports.

Import the design system constants from here:
    from gui.theme import ACCENT, BG_BASE, FONT_FAMILY, glass_bg

luminos_theme.py is the single source of truth for all visual values.
"""

# Primary export: the complete design system
from .luminos_theme import *  # noqa: F401,F403
from .luminos_theme import glass_bg  # explicit for clarity

# Mode manager singleton
from .mode_manager import ModeManager as _ModeManager
mode = _ModeManager()

# Legacy exports kept for backwards compat during transition
from .icons import find_icon, get_system_icons
from .gtk_css import generate_css
from .colors import get_colors, DARK, LIGHT
