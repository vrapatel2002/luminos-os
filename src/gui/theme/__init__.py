"""
src/gui/theme/__init__.py
Luminos GUI Theme — public exports.

Import from here in all widget code:
    from gui.theme import mode, DARK, generate_css, SIZING

The module-level `mode` singleton manages dark/light state
for the entire GUI lifetime.
"""

from .mode_manager import ModeManager
from .colors       import DARK, LIGHT, get_colors
from .spacing      import RADIUS, SPACING, SIZING, ANIMATION
from .gtk_css      import generate_css
from .icons        import find_icon, get_system_icons

# Module-level singleton — one mode manager for the GUI lifetime
mode = ModeManager()
