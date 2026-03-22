"""
src/gui/theme/spacing.py
All spacing, sizing, radius, and animation timing constants for Luminos.

All pixel values are integers. All timing values are milliseconds.
Import these directly — never hardcode magic numbers in widget code.
"""

RADIUS: dict[str, int] = {
    "small":  6,
    "medium": 10,
    "large":  14,
    "xlarge": 20,
    "pill":   999,
}

SPACING: dict[str, int] = {
    "xs":  4,
    "sm":  8,
    "md":  12,
    "lg":  16,
    "xl":  24,
    "xxl": 32,
}

SIZING: dict[str, int] = {
    "bar_height":       36,
    "dock_height":      64,
    "dock_icon":        48,
    "dock_icon_hover":  54,
    "launcher_width":   560,
    "launcher_height":  480,
    "quick_settings_w": 360,
    "notification_w":   380,
    "settings_w":       800,
    "settings_h":       560,
    "icon_sm":          16,
    "icon_md":          24,
    "icon_lg":          32,
    "icon_xl":          48,
}

ANIMATION: dict[str, int] = {
    "fast":   150,   # ms — hover, focus ring
    "normal": 200,   # ms — panel slide, fade
    "slow":   350,   # ms — mode transitions
}
