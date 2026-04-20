"""
src/gui/theme/colors.py
Complete Luminos color system — dark and light modes.

Apple System Colors adapted for Luminos dark-first design.
All color values are CSS-compatible strings.
rgba() values include alpha for frosted glass compositing.
"""

DARK: dict[str, str] = {
    # --- Base layers ---
    "bg_primary":        "#1c1c1e",
    "bg_secondary":      "#2c2c2e",
    "bg_tertiary":       "#3a3a3c",

    # --- Frosted glass surfaces (with alpha) ---
    "surface":           "rgba(28,28,30,0.75)",
    "surface_raised":    "rgba(44,44,46,0.80)",
    "surface_overlay":   "rgba(58,58,60,0.85)",

    # --- Borders ---
    "border":            "rgba(255,255,255,0.08)",
    "border_strong":     "rgba(255,255,255,0.15)",

    # --- Text ---
    "text_primary":      "#ffffff",
    "text_secondary":    "rgba(255,255,255,0.55)",
    "text_tertiary":     "rgba(255,255,255,0.30)",
    "text_disabled":     "rgba(255,255,255,0.20)",

    # --- Accents ---
    "accent_blue":       "#0a84ff",
    "accent_blue_hover": "#409cff",

    # --- Luminos specific ---
    "luminos_ai":        "#5e9eff",
    "zone2_wine":        "#5e9eff",
    "zone3_alert":       "#ff9f0a",
    "sentinel_safe":     "#32d74b",
    "sentinel_warn":     "#ff9f0a",
    "sentinel_danger":   "#ff453a",

    # --- System status ---
    "success":           "#32d74b",
    "warning":           "#ff9f0a",
    "error":             "#ff453a",
    "info":              "#64d2ff",

    # --- Dock + bar ---
    "bar_bg":            "rgba(20,20,22,0.85)",
    "dock_bg":           "rgba(28,28,30,0.80)",
    "dock_item_hover":   "rgba(255,255,255,0.10)",
}

LIGHT: dict[str, str] = {
    # --- Base layers ---
    "bg_primary":        "#f5f5f7",
    "bg_secondary":      "#ffffff",
    "bg_tertiary":       "#e5e5ea",

    # --- Frosted glass surfaces ---
    "surface":           "rgba(255,255,255,0.75)",
    "surface_raised":    "rgba(242,242,247,0.80)",
    "surface_overlay":   "rgba(255,255,255,0.90)",

    # --- Borders ---
    "border":            "rgba(0,0,0,0.08)",
    "border_strong":     "rgba(0,0,0,0.15)",

    # --- Text ---
    "text_primary":      "#1d1d1f",
    "text_secondary":    "rgba(0,0,0,0.45)",
    "text_tertiary":     "rgba(0,0,0,0.25)",
    "text_disabled":     "rgba(0,0,0,0.18)",

    # --- Accents ---
    "accent_blue":       "#007aff",
    "accent_blue_hover": "#0071e3",

    # --- Luminos specific ---
    "luminos_ai":        "#007aff",
    "zone2_wine":        "#007aff",
    "zone3_alert":       "#ff9500",
    "sentinel_safe":     "#34c759",
    "sentinel_warn":     "#ff9500",
    "sentinel_danger":   "#ff3b30",

    # --- System status ---
    "success":           "#34c759",
    "warning":           "#ff9500",
    "error":             "#ff3b30",
    "info":              "#32ade6",

    # --- Dock + bar ---
    "bar_bg":            "rgba(255,255,255,0.85)",
    "dock_bg":           "rgba(255,255,255,0.80)",
    "dock_item_hover":   "rgba(0,0,0,0.06)",
}


def get_colors(dark: bool = True) -> dict:
    """Return the color palette for the requested mode."""
    return DARK if dark else LIGHT
