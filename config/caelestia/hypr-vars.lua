-- hypr-vars.lua — Luminos overrides for Caelestia's variables.lua
-- [CHANGE: claude-code | 2026-08-04]
--
-- This file is merged OVER ~/.config/hypr/variables.lua by hyprland.lua before any of the
-- Caelestia modules load. Put value tweaks here (apps, gaps, colours, keybind strings) so that
-- ~/.config/hypr/ stays byte-identical to upstream and `caelestia update` never conflicts.
--
-- For behaviour that is NOT a variable — env vars, autostarts, monitor rules — use
-- hypr-user.lua instead. That one is required LAST, after every Caelestia module.

return {
    -- ── Apps ────────────────────────────────────────────────────────────────────────────
    -- Caelestia's defaults are foot / firefox / codium / thunar. None of those are installed
    -- here, and installing them would mean four redundant apps. These are the Luminos
    -- equivalents that already exist on this machine.
    terminal      = "kitty",                -- SUPER+T   (Caelestia default: foot)
    fileExplorer  = "dolphin",              -- SUPER+E   (Caelestia default: thunar)
    browser       = "google-chrome-stable", -- SUPER+W   matches xdg-settings default-web-browser
    audioSettings = "pavucontrol",          -- CTRL+ALT+V  unchanged, already installed

    -- SUPER+C. There is no GUI editor installed, so this opens vim in a terminal rather than
    -- silently doing nothing. Change to "code" or "codium" if a GUI editor is ever installed.
    editor        = "kitty -e vim",

    -- ── Cursor ──────────────────────────────────────────────────────────────────────────
    -- Caelestia defaults to sweet-cursors, which is not installed — that would leave Hyprland
    -- with no cursor theme at all and fall back to the ugly X11 default. Yaru is what Plasma
    -- already uses (kcminputrc cursorTheme=Yaru), so the pointer looks identical in both
    -- sessions. Verified present at /usr/share/icons/Yaru/cursors.
    cursorTheme   = "Yaru",
    cursorSize    = 24,

    -- ── Suspend ─────────────────────────────────────────────────────────────────────────
    -- Caelestia's sleep gesture defaults to `systemctl suspend-then-hibernate`. This laptop
    -- has no hibernate image configured (swap is zram, which cannot hold one), so that command
    -- would fail or fall through unpredictably. Plain suspend is what the G14 is tuned for and
    -- is proven working — see the 2026-08-02 suspend work.
    sleepGestureCmd = "systemctl suspend",
}
