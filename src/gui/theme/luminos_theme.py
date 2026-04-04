"""
src/gui/theme/luminos_theme.py
Single source of truth for every visual value in Luminos OS.

Every other UI file must import from here.
Zero hardcoded color values anywhere else in the codebase.

Reference: LUMINOS_DESIGN_SYSTEM.md
"""

# =========================================================================
# Colors — Base
# =========================================================================
BG_BASE = "#0A0A0F"
BG_SURFACE = "#13131A"
BG_ELEVATED = "#1C1C26"
BG_OVERLAY = "rgba(255, 255, 255, 0.06)"

# =========================================================================
# Colors — Accent
# =========================================================================
ACCENT = "#0080FF"
ACCENT_HOVER = "#0066CC"
ACCENT_PRESSED = "#0052A3"
ACCENT_GLOW = "rgba(0, 128, 255, 0.4)"
ACCENT_SUBTLE = "rgba(0, 128, 255, 0.12)"

# =========================================================================
# Colors — Text
# =========================================================================
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#8888AA"
TEXT_DISABLED = "#444466"

# =========================================================================
# Colors — Border
# =========================================================================
BORDER = "rgba(255, 255, 255, 0.08)"
BORDER_FOCUS = "rgba(0, 128, 255, 0.6)"
BORDER_SUBTLE = "rgba(255, 255, 255, 0.04)"

# =========================================================================
# Colors — Status
# =========================================================================
COLOR_SUCCESS = "#00C896"
COLOR_WARNING = "#FFB020"
COLOR_ERROR = "#FF4455"

# =========================================================================
# Typography
# =========================================================================
FONT_FAMILY = "Inter"
FONT_DISPLAY = 80
FONT_H1 = 32
FONT_H2 = 24
FONT_H3 = 18
FONT_BODY_LARGE = 16
FONT_BODY = 14
FONT_BODY_SMALL = 13
FONT_CAPTION = 12
FONT_LABEL = 11

# =========================================================================
# Spacing (8px base grid)
# =========================================================================
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_6 = 24
SPACE_8 = 32
SPACE_12 = 48

# =========================================================================
# Radius
# =========================================================================
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_DEFAULT = 12
RADIUS_LG = 16
RADIUS_FULL = 9999
RADIUS_MAXIMIZED = 0

# =========================================================================
# Animation timing (milliseconds)
# =========================================================================
ANIM_INSTANT = 0
ANIM_FAST = 100
ANIM_DEFAULT = 200
ANIM_SLOW = 350

# =========================================================================
# Blur
# =========================================================================
BLUR_STRENGTH = "blur(20px)"
BLUR_HEAVY = "blur(40px)"

# =========================================================================
# Component specific
# =========================================================================
DOCK_HEIGHT = 64
DOCK_ICON_SIZE = 48
DOCK_BOTTOM_MARGIN = 20
BAR_HEIGHT = 36
SIDEBAR_WIDTH = 220
SETTINGS_PADDING = 24
INPUT_HEIGHT = 40
BUTTON_HEIGHT = 36


# =========================================================================
# Helpers
# =========================================================================
def glass_bg(opacity=0.8):
    """Frosted glass background color at given opacity."""
    return f"rgba(28, 28, 38, {opacity})"
