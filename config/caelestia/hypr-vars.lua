-- hypr-vars.lua — Luminos overrides for Caelestia's variables.lua
-- [CHANGE: claude-code | 2026-08-04]
--
-- This file is merged OVER ~/.config/hypr/variables.lua by hyprland.lua before any of the
-- Caelestia modules load. Put value tweaks here (apps, gaps, colours, keybind strings) so that
-- ~/.config/hypr/ stays byte-identical to upstream and `caelestia update` never conflicts.
--
-- For behaviour that is NOT a variable — env vars, autostarts, monitor rules — use
-- hypr-user.lua instead. That one is required LAST, after every Caelestia module.

local vars = {
    -- ── Apps ────────────────────────────────────────────────────────────────────────────
    -- Caelestia's defaults are foot / firefox / codium / thunar. Most are not installed here,
    -- and installing them would mean redundant apps. These are the Luminos equivalents.
    terminal      = "kitty",                -- SUPER+T   (Caelestia default: foot)
    -- thunar installed 2026-08-04 at Shawn's request, replacing dolphin. This restores
    -- Caelestia's own default. Dolphin is still installed and still works if launched by name;
    -- it is only no longer what SUPER+E opens. Thunar is GTK3 (not GTK4/libadwaita) and pulls
    -- no KDE/Plasma runtime into the Hyprland session, so it starts faster here.
    fileExplorer  = "thunar",               -- SUPER+E   (Caelestia default: thunar)
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

    -- ── Touchpad ────────────────────────────────────────────────────────────────────────
    -- [CHANGE: claude-code | 2026-08-05]
    -- Caelestia ships touchpadScrollFactor = 0.3, i.e. three-tenths of the scroll distance
    -- libinput actually reports. In a tall page that only reads as "slow", but the SUPER
    -- launcher's app list is a short viewport — it shows Config.launcher.maxShown rows and
    -- nothing more — so a whole two-finger swipe moved it well under one row and the list
    -- looked frozen. The list was never broken; the input was being scaled down before it
    -- got there. 1.0 is Hyprland's own default (untouched libinput delta).
    --
    -- Applied at ~/.config/hypr/hyprland/input.lua:14 as input:touchpad:scroll_factor.
    -- Mouse-wheel scrolling uses the separate input:scroll_factor, which was already 1.0 —
    -- that is why the two devices behaved differently. Lower this toward 0.3 if it now
    -- overshoots; it takes effect on `hyprctl reload`, no logout needed.
    touchpadScrollFactor = 1.0,

    -- ── Suspend ─────────────────────────────────────────────────────────────────────────
    -- Caelestia's sleep gesture defaults to `systemctl suspend-then-hibernate`. This laptop
    -- has no hibernate image configured (swap is zram, which cannot hold one), so that command
    -- would fail or fall through unpredictably. Plain suspend is what the G14 is tuned for and
    -- is proven working — see the 2026-08-02 suspend work.
    sleepGestureCmd = "systemctl suspend",
}

-- ── Look preset ─────────────────────────────────────────────────────────────────────
-- `luminos-look save` writes ~/.config/caelestia/hypr-look.lua and overwrites it WHOLE.
-- Keeping it in its own file is the point: everything above this line is hand-written
-- and reasoned about, so a theme tool must never be able to rewrite it. The merge runs
-- last, so a saved look wins over any look value set above.
--
-- pcall, not require: the file legitimately does not exist until the first save, and a
-- missing look must not take the whole Hyprland config down with it.
local ok, look = pcall(require, "hypr-look")
if ok and type(look) == "table" then
    for k, v in pairs(look) do
        vars[k] = v
    end
end

return vars
