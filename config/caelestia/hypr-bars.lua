-- hypr-bars.lua — [CHANGE: claude-code | 2026-08-05]
--
-- Titlebars with minimize / maximize / close buttons, via the hyprbars plugin.
--
-- WHY THIS IS A SEPARATE MODULE
-- The exact same file is loaded by a throwaway nested Hyprland during testing, so the
-- code that gets proven is the code that ships. Copying the block into a test config
-- instead would let the two drift apart.
--
-- THE TWO NON-OBVIOUS THINGS, both found by testing rather than from docs:
--
-- 1. `hyprbars-button` is a plugin KEYWORD, not a config VALUE. Putting it inside
--    hl.config{ plugin = { hyprbars = ... } } fails with
--        unknown config key 'plugin.hyprbars.hyprbars-button'
--    and `hyprctl keyword` refuses outright ("keyword can't work with non-legacy
--    parsers. Use eval."). The real entry point is hl.plugin.hyprbars.add_button{},
--    whose schema the plugin will tell you if you call it wrong:
--        { bg_color, fg_color, size, icon, action }
--
-- 2. hl.plugin.hyprbars DOES NOT EXIST while the config is being parsed. hl.plugin
--    holds only `load` at that point; the hyprbars table appears afterwards, once the
--    plugin has registered. So the buttons cannot be added inline — they are added
--    from a repeating timer that disables itself on success. Without the retry this
--    is a race that fails silently and leaves bars with no buttons.
--
-- Button actions shell out to `luminos-win`, because under the Lua parser
-- `hyprctl dispatch killactive` is a syntax error — see that script's header.

local M = {}

local PLUGIN_SO = "/usr/lib/libhyprbars.so"

-- Theme the bar from Caelestia's live scheme so it tracks luminos-look presets
-- instead of freezing one hardcoded palette. Falls back to sane values if the
-- scheme file is missing or a key is absent.
local scheme = {}
do
    local ok, res = pcall(require, "scheme.current")
    if not ok then
        local home = os.getenv("HOME")
        local f = loadfile(home .. "/.config/hypr/scheme/current.lua")
        if f then
            local ok2, res2 = pcall(f)
            if ok2 and type(res2) == "table" then scheme = res2 end
        end
    elseif type(res) == "table" then
        scheme = res
    end
end

local function col(key, fallback)
    local v = scheme[key]
    if type(v) == "string" and v ~= "" then return "0xff" .. v end
    return fallback
end

function M.setup()
    hl.plugin.load(PLUGIN_SO)

    hl.config({
        plugin = {
            hyprbars = {
                bar_height                 = 26,
                bar_padding                = 10,
                bar_button_padding         = 8,
                bar_color                  = col("surfaceContainer", "0xff201f23"),
                ["col.text"]               = col("onSurface", "0xffe5e1e7"),
                bar_text_size              = 11,
                bar_text_font              = "Sans",
                bar_text_align             = "center",
                bar_title_enabled          = true,
                bar_buttons_alignment      = "right",
                -- Keep the bar inside the window's own geometry so a maximized window
                -- does not get pushed under the Caelestia panel.
                bar_part_of_window         = true,
                bar_precedence_over_border = true,
                -- Double-clicking the bar maximizes, the way Plasma does.
                on_double_click            = "luminos-win max",
            },
        },
    })

    -- Buttons are laid out from the RIGHT, so the first one added ends up rightmost.
    -- Adding close -> max -> min therefore reads min, max, close left to right, which
    -- is the Plasma/Windows order Shawn is used to.
    --
    -- These three colours are DELIBERATELY hardcoded, unlike everything above.
    -- Caelestia's scheme does define red/green/yellow, so col("red") looks like the
    -- obvious choice and fails silently: the keys exist, parse fine, and produce
    -- nonsense, because they are harmonised into the wallpaper's palette rather than
    -- being traffic lights. In the current scheme red = c1a5fd (purple) and
    -- green = c8e3ff (pale blue). A close button must read as "close" in any theme,
    -- so these stay fixed while the bar itself keeps tracking luminos-look.
    local buttons = {
        { colour = "0xffff5f57", action = "luminos-win close" },
        { colour = "0xfffebc2e", action = "luminos-win max" },
        { colour = "0xff28c840", action = "luminos-win min" },
    }

    local function add_buttons()
        local hb = hl.plugin.hyprbars
        if type(hb) ~= "table" or type(hb.add_button) ~= "function" then
            return false -- plugin not registered yet
        end
        for _, b in ipairs(buttons) do
            local ok, err = pcall(hb.add_button, {
                bg_color = b.colour,
                fg_color = col("surfaceContainer", "0xff201f23"),
                size     = 13,
                icon     = "",
                action   = b.action,
            })
            if not ok then
                print("hypr-bars: add_button failed for " .. b.action .. ": " .. tostring(err))
            end
        end
        return true
    end

    if add_buttons() then return end

    -- Retry for ~5s. Repeating rather than one long sleep so the buttons appear as
    -- soon as the plugin is ready, and bounded so a failed load cannot spin forever.
    local tries = 0
    local timer
    timer = hl.timer(function()
        tries = tries + 1
        local done = add_buttons()
        if done or tries >= 20 then
            if timer and timer.set_enabled then timer:set_enabled(false) end
            if not done then
                print("hypr-bars: gave up adding buttons after " .. tries .. " tries")
            end
        end
    end, { timeout = 250, type = "repeat" })
end

return M
