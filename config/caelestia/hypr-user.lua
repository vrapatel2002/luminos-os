-- hypr-user.lua — Luminos hardware overrides on top of stock Caelestia
-- [CHANGE: claude-code | 2026-08-04]
--
-- ~/.config/hypr/ is now a byte-for-byte copy of caelestia-dots/caelestia's `hypr/` tree, so
-- that `caelestia update` can keep it current without ever hitting a merge conflict. Everything
-- specific to THIS laptop lives here instead.
--
-- hyprland.lua requires this file LAST, after every Caelestia module, so anything set here wins.
--
-- Rule of thumb: value tweaks (apps, gaps, colours, keybind strings) go in hypr-vars.lua.
-- Behaviour — env vars, autostarts, monitor rules — goes here.

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- GPU — THE MOST IMPORTANT LINES IN THIS FILE. DO NOT REMOVE.
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- This laptop enumerates the NVIDIA dGPU FIRST:
--     card1 / renderD128 = 0x10de NVIDIA RTX 4050   (PCI 0000:01:00.0)
--     card2 / renderD129 = 0x1002 AMD iGPU          (PCI 0000:65:00.0)
--
-- Left to choose, Hyprland can land on the NVIDIA card. That is bad twice over:
--   1. It holds the dGPU awake forever, destroying the 0 W runtime-PM gating that the
--      BUG-047 / BUG-050 / BUG-078 work exists to achieve.
--   2. It would probably fail to start at all — /etc/environment forces Mesa-only EGL
--      (__EGL_VENDOR_LIBRARY_FILENAMES=.../50_mesa.json), so there is no NVIDIA EGL vendor.
--
-- ⚠️ DO NOT "IMPROVE" THIS BACK TO A /dev/dri/by-path/... PATH. (BUG-094)
-- aquamarine parses AQ_DRM_DEVICES as a COLON-SEPARATED LIST. The obvious stable name,
-- /dev/dri/by-path/pci-0000:65:00.0-card, is full of colons, so aquamarine split it into three
-- garbage paths, found no GPU, and aborted the session before it drew a frame:
--
--     drm: Failed to canonicalize path /dev/dri/by-path/pci-0000
--     drm: Failed to canonicalize path 65
--     drm: Explicit device 00.0-card not found
--     drm: Found no gpus to use, cannot continue
--
-- /dev/dri/cardN has no colons, but the number is enumeration order and is NOT stable.
-- /dev/dri/luminos-igpu is a colon-free alias from /etc/udev/rules.d/99-luminos-gpu-alias.rules,
-- matched on the PCI address. Stable across boots AND survives the colon split.
--
-- Also set in ~/.config/uwsm/env-hyprland, which is the one that actually wins on a uwsm login
-- (uwsm builds the environment before the compositor is exec'd). This is the belt to that
-- braces: it covers a bare `Hyprland` launch with no uwsm in the path.
hl.env("AQ_DRM_DEVICES", "/dev/dri/luminos-igpu")

-- NOTE: there are deliberately NO NVIDIA environment variables here — no LIBVA_DRIVER_NAME,
-- no GBM_BACKEND, no __GLX_VENDOR_LIBRARY_NAME, no NVD_BACKEND. Every Hyprland guide on the
-- internet tells you to add them. Adding them here is exactly what would undo the power gating.
-- The dGPU stays asleep and is woken on demand by dgpu-exec, the same as under Plasma.

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- POWER — asusd owns platform_profile, alone.
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- caelestia-shell hard-depends on power-profiles-daemon, so it is installed — but it is MASKED
-- (DECISION 40). Two daemons writing /sys/firmware/acpi/platform_profile fight each other and
-- the loser silently wins at random, which is how the fan curve and the 0 W dGPU gating get
-- destroyed. asusd is the single owner and stays that way.
--
-- Consequence: Caelestia's power-profile buttons render but do nothing. That is expected, not a
-- bug. Wiring them to asusd is Phase 5 work. Do NOT "fix" them by unmasking ppd.
--
-- Nothing to set here — this block exists so the next person does not undo the masking while
-- chasing the dead buttons.

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Display
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Stock Caelestia sets scale = 1. On this 2880x1800 14" panel that is ~242 DPI of unscaled UI —
-- text roughly the height of a grain of rice. Hyprland picked 2.00 on its own during the first
-- real login and that is what the desktop was signed off on looking like, so it is pinned here
-- rather than left to autodetection.
--
-- 2.00 gives 1440x900 logical. Plasma uses 1.6 (1800x1125) — try scale = 1.6 if things feel too
-- big, but note Hyprland is fussier than Plasma about fractional scales that do not divide the
-- panel cleanly.
hl.monitor({
    output   = "eDP-2",
    mode     = "2880x1800@120",
    position = "auto",
    scale    = 2,
})

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Theming — keep the Yaru/KDE look that already exists
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Caelestia's env.lua sets QT_QPA_PLATFORMTHEME=qtengine. qtengine is NOT installed here, and
-- installing it would take over Qt styling from KDE and undo the Ubuntu/Yaru look built in
-- BUG-088 / BUG-090. plasma-integration IS installed, so "kde" keeps Dolphin, Kate and every
-- other Qt app looking exactly as they do under Plasma.
hl.env("QT_QPA_PLATFORMTHEME", "kde")

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Autostart
-- ═════════════════════════════════════════════════════════════════════════════════════════
hl.on("hyprland.start", function()
    -- Polkit agent. Caelestia's execs.lua launches /usr/lib/polkit-gnome/... which does not
    -- exist here — polkit-gnome is not installed and pulling it in would mean two agents
    -- racing for the same D-Bus name. Without a working agent, anything that asks for
    -- authentication fails SILENTLY with no prompt at all, which is a miserable thing to debug.
    -- KDE's agent is already installed and does the same job.
    hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")

    -- Session black box. uwsm should already start this via graphical-session.target; this is
    -- belt-and-braces for a bare `Hyprland` launch, where the systemd unit never fires and the
    -- one session most in need of a record would be the one with no record.
    -- Idempotent — a duplicate run just writes a second file.
    hl.exec_cmd("/home/shawn/luminos-os/scripts/luminos-session-recorder")

    -- Load the hyprpm plugins. Hyprland does NOT do this itself: `hyprpm enable` only records
    -- the choice in /var/cache/hyprpm/shawn/state.toml, and without this line the plugins are
    -- simply absent after every logout, with nothing on screen to say so.
    -- [CHANGE: claude-code | 2026-08-05]
    --
    -- `-n` means NOTIFY, not "no". It is deliberate. A plugin built against the wrong Hyprland
    -- version fails to load SILENTLY, so the login toast is the only positive confirmation
    -- that the borders and focus flash are actually live. If it ever stops appearing, run
    -- `hyprpm update && hyprpm reload`. Warnings and errors notify regardless of this flag.
    hl.exec_cmd("hyprpm reload -n")
end)

-- NOT autostarted any more: `kitty`. It existed only as proof-of-life while we could not tell a
-- running compositor from a crashed one (BUG-092). The first real login succeeded on 2026-08-04
-- with Caelestia's bar and Claude Desktop both rendering, so the ambiguity is gone and an
-- unwanted terminal on every login is just noise. SUPER+T opens one.

-- Three of Caelestia's stock autostarts have no binary on this machine and will fail harmlessly.
-- Two are absent by choice, one by accident of never having been installed:
--
--   trash-empty 30  — DELIBERATELY DISABLED by uninstalling trash-cli. Upstream runs this at
--     every login and it PERMANENTLY deletes anything in the trash older than 30 days. On this
--     machine that was 31 of 43 items and 8.9 GB, including LUMINOS_MASTER_FILE.md,
--     AGENT_HANDOFF.md, DECISION_HYPRLAND_TO_KDE.md, conversations.json and projects.json.
--     Do NOT reinstall trash-cli without emptying or rescuing the trash first.
--
--   gammastep + /usr/lib/geoclue-2.0/demos/agent  — night light. geoclue drags in avahi and
--     ModemManager, which is a bigger system change than a colour shift is worth. Install
--     `gammastep geoclue` if night light is ever wanted.
--
-- Everything else execs.lua starts (gnome-keyring, cliphist, mpris-proxy, hyprctl setcursor,
-- caelestia shell -d) is installed and working.

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- HIVE chat popup — SUPER+SPACE
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- [CHANGE: claude-code | 2026-08-04] Phase 5: wired up, as this block promised.
-- Confirmed free in stock Caelestia: its launcher is a bare SUPER tap (kbLauncher =
-- "SUPER + SUPER_L") and SUPER+SPACE is not used by anything. Verified against the live
-- compositor with `hyprctl binds` — the only Space binds were modmask 72 (SUPER+ALT,
-- toggle floating) and modmask 68 (SUPER+CTRL). Plain SUPER is modmask 64: free.
--
-- The launcher toggles: press once to open, again to close. It also brings
-- luminos-hive.service up if 127.0.0.1:8078 is not listening, so the chat window never
-- opens against a dead backend.
hl.bind("SUPER + SPACE", hl.dsp.exec_cmd("luminos-hive-popup"))

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Look tuner — luminos-look / luminos-look-dashboard
-- ═════════════════════════════════════════════════════════════════════════════════════════
local vars = require("variables")

-- animations.lua sets `animations.enabled = true` as a literal, not from a variable, so a
-- saved `performance` preset could never switch animations off through hypr-vars.lua alone.
-- This file is required LAST, after every Caelestia module, so re-issuing the config here is
-- what actually lets the saved value win. Guarded because the key only exists after a save.
if vars.luminosAnimations ~= nil then
    hl.config({ animations = { enabled = vars.luminosAnimations } })
end

-- Float the dashboard. Matched on TITLE, not class: its class is `org.quickshell`, which is
-- also Caelestia's own bar and launcher — a class match would rip those out of the layer
-- shell too.
hl.window_rule({ match = { title = "^Luminos Look$" }, float = true })

-- Binds. All five were confirmed free against `hyprctl binds` on the RUNNING compositor
-- (SUPER+SHIFT is otherwise used only by C, Comma, Equal, L, M, Minus, S and the arrows),
-- rather than against the config file, which would have missed anything bound at runtime.
hl.bind("SUPER + SHIFT + T", hl.dsp.exec_cmd("luminos-look-dashboard"))     -- open/close tuner
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("luminos-look next"))          -- next look
hl.bind("SUPER + SHIFT + P", hl.dsp.exec_cmd("luminos-look prev"))          -- previous look
hl.bind("SUPER + SHIFT + Return", hl.dsp.exec_cmd("luminos-look save"))     -- keep this one
hl.bind("SUPER + SHIFT + Backspace", hl.dsp.exec_cmd("luminos-look reset")) -- undo previews

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Make CTRL+SUPER+SHIFT+R survivable
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- [CHANGE: claude-code | 2026-08-04]
-- Stock Caelestia binds CTRL+SUPER+SHIFT+R to `qs -c caelestia kill` with NO restart
-- (hyprland/keybinds.lua:68). Pressing it removes the bar, the launcher, the notification
-- daemon and the lock screen in one keystroke, and nothing brings them back — the desktop is
-- simply gone until you find a terminal. That is a debugging bind for someone developing
-- Quickshell, not something that should sit one slip away from CTRL+SUPER+ALT+R (the bind
-- immediately next to it, which DOES restart).
--
-- On 2026-08-04 the shell died at ~18:07 during look-tuner testing. Its log ends with only
-- routine warnings and no fatal error, which means it was signalled, not crashed — the exact
-- signature of this bind firing. Shawn was left with no panel and no notifications.
--
-- The hl Lua API (/usr/share/hypr/stubs/hl.meta.lua) has NO unbind, so binding the same combo
-- here does NOT replace keybinds.lua:68 — it stacks. `hyprctl binds` confirms two entries for
-- modmask=69 key=R, and Hyprland fires both. So this must not be a second "kill and restart":
-- that would race the stock kill against this one's restart.
--
-- Instead this is a GUARD. The stock bind kills at t≈0; this waits well clear of that, then
-- starts the shell only if nothing is running. If the stock kill worked, the shell comes back.
-- If it somehow did not, the live shell is left alone instead of being pointlessly bounced.
-- The logic lives in /usr/local/bin/luminos-shell-guard rather than inline here, because two
-- separate traps make the one-liner version silently wrong (both documented in that script):
-- `pgrep -f` self-matches, and `caelestia shell -d` does not reliably start the shell from a
-- detached context. The script was proven end to end on 2026-08-04: shell killed (0 layers),
-- guard run, shell back with 6 layers.
hl.bind("CTRL + SUPER + SHIFT + R", hl.dsp.exec_cmd("luminos-shell-guard"), { release = true })

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Float everything — [CHANGE: claude-code | 2026-08-04]
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Shawn wants a Plasma/Windows-style desktop: windows that open free, stack on top of each
-- other and get dragged where he wants them. Stock Caelestia is `general:layout = dwindle`,
-- so two windows split the screen left/right and cannot overlap — that is the "locked to a
-- position" problem, not a bug.
--
-- Why a catch-all window rule and NOT `general:layout = floating`:
-- the dwindle layout is still wanted for the times he DOES want a split, and
-- kbToggleWindowFloating (SUPER+ALT+Space) toggles a window between float and the ACTIVE
-- layout. Switching the layout itself to `floating` would make that toggle a no-op and
-- permanently remove tiling. A rule floats windows at map time while leaving the layout
-- intact, so SUPER+ALT+Space still snaps a window back into a tile on demand.
--
-- Ordering matters and works in our favour: this file is required LAST, so this rule is
-- evaluated after every Caelestia rule. It sets ONLY `float`, so the sized floaters in
-- rules.lua (float_50_60 / float_60_70 / float_70_80) keep their own size and centring —
-- setting a size here would have flattened all of them to one dimension.
--
-- `class = ".*"` rather than an omitted match: an absent match is untested against this
-- Lua parser, and `.*` also matches the empty class that some XWayland windows report.
--
-- Caelestia's bar, launcher and OSDs are layer-shell surfaces, NOT windows, so no window
-- rule can reach them — confirmed by `hyprctl layers` still showing 6 layers after reload.
hl.window_rule({ match = { class = ".*" }, float = true })

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Give Thunar a sane opening size — [CHANGE: claude-code | 2026-08-05]
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Thunar opened at 640x480 on a 1440x900 logical desktop — a postage stamp next to Claude
-- (1348x858) and Chrome (668x858). Measured with `hyprctl clients -j`, not eyeballed.
--
-- The cause is NOT the catch-all above. It is that Thunar has never saved a window size:
--     $ xfconf-query -c thunar -l
--     /last-icon-view-zoom-level  /last-separator-position  /last-view  /last-window-maximized
-- There is no /last-window-width or /last-window-height, so Thunar falls back to its
-- compiled-in 640x480. It only writes those two keys when it is closed un-maximized, so it
-- can sit in that state indefinitely. Stock rules.lua hands sized-floater tags to
-- pavucontrol, nwg-look, GNOME Settings and the file *dialogs* — but never to Thunar
-- itself, so nothing was sizing it.
--
-- Deliberately sets ONLY size + center, not float:
--   * the catch-all above already floats it, and
--   * leaving `float` alone means the hypr-locked.conf block below can still claw Thunar
--     into the tiling layout if it is ever locked. Setting float = true here would quietly
--     defeat SUPER+SHIFT+SPACE for this one app.
-- 0.6 x 0.7 matches the stock float_60_70 tag (rules.lua:182) = 864x630 logical.
--
-- Window-rule tables are NOT validated by this parser — an unknown key returns ok and does
-- nothing — so this was confirmed by reading the size back off the live window after a
-- reload, not by trusting the config to have applied.
hl.window_rule({
    match  = { class = "^thunar$" },
    size   = "(monitor_w*0.6) (monitor_h*0.7)",
    center = true,
})

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Locked apps — float by default, tile by exception — [CHANGE: claude-code | 2026-08-05]
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- The catch-all above floats EVERYTHING. Shawn wants some apps pinned into the tiling
-- layout instead, so this reads a list of window classes and claws just those back.
--
-- Ordering is what makes this work, and it was measured rather than assumed. In a throwaway
-- nested Hyprland (2026-08-05) three kitty windows were opened under exactly this rule
-- shape and `floating` was read back off each one:
--     catch-all float=true only ....... floating: 1
--     later rule float=false .......... floating: 0
--     later rule tile=true ............ floating: 0
-- So a later rule DOES override the catch-all, and `float = false` is a real key rather than
-- one of the many that this parser accepts and silently ignores. Worth checking, because
-- window-rule tables are NOT validated: an unknown key returns ok and does nothing.
--
-- Why a plain text file and not a .lua list: luminos-win rewrites it on every lock/unlock.
-- If that file were Lua, one bad write would be a config SYNTAX ERROR, which puts Hyprland
-- in emergency mode with no binds registered — a black screen with no keyboard way out.
-- A text file that goes wrong costs at most one missing rule. For the same reason the class
-- is allow-listed to [%w%._%-] here as well as in the script: these strings are interpolated
-- into a Lua pattern, so a stray quote is a syntax error, not a cosmetic bug.
local locked_path = os.getenv("HOME") .. "/.config/caelestia/hypr-locked.conf"
local ok_locked, err_locked = pcall(function()
    local fh = io.open(locked_path, "r")
    if not fh then return end -- no file yet is the normal case, not an error
    for line in fh:lines() do
        local cls = line:match("^%s*(.-)%s*$")
        if cls ~= "" and cls:sub(1, 1) ~= "#" then
            if cls:match("^[%w%._%-]+$") then
                hl.window_rule({ match = { class = "^" .. cls:gsub("%.", "%%.") .. "$" }, float = false })
            else
                print("hypr-user: skipping unsafe class in hypr-locked.conf: " .. cls)
            end
        end
    end
    fh:close()
end)
if not ok_locked then
    print("hypr-user: could not read " .. locked_path .. ": " .. tostring(err_locked))
end

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Window action binds — [CHANGE: claude-code | 2026-08-05]
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- These replace the hyprbars titlebar buttons, which were removed on Shawn's say-so
-- ("i do not like the 3 buttons"). Only MINIMIZE actually needed a new bind — stock
-- Caelestia already has close (SUPER+Q), maximize (SUPER+ALT+F) and float/tile
-- (SUPER+ALT+Space) — so the rest of the desktop is unchanged.
--
-- All three combos were confirmed free against `hyprctl binds` on the RUNNING compositor
-- rather than against the config file, which would have missed anything bound at runtime.
-- SUPER+ALT+M, used for restore until today, is retired in favour of SUPER+SHIFT+H so that
-- hide and un-hide sit next to each other. SUPER+SHIFT+M was never available: it is volume
-- mute at variables.lua:133.
-- SUPER+ALT+Space (stock) floats/tiles ONE window until it closes. SUPER+SHIFT+Space makes
-- that choice stick for the whole app by writing its class to hypr-locked.conf, so the
-- pairing is deliberate: same key, one modifier apart, temporary vs permanent.
hl.bind("SUPER + H", hl.dsp.exec_cmd("luminos-win min"))                    -- hide (minimize)
hl.bind("SUPER + SHIFT + H", hl.dsp.exec_cmd("luminos-win restore"))        -- bring them all back
hl.bind("SUPER + SHIFT + SPACE", hl.dsp.exec_cmd("luminos-win togglelock")) -- lock app tiled/floating

-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Hyprland plugins (hyprpm) — [CHANGE: claude-code | 2026-08-05]
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- Three plugins are enabled: borders-plus-plus, hyprfocus and hyprexpo. Enable/disable is NOT
-- done here — it lives in hyprpm's own state at /var/cache/hyprpm/shawn/state.toml, set with
-- `hyprpm enable <name>` / `hyprpm disable <name>`. This block only CONFIGURES them.
--
-- ⚠️ THE ONE THING THAT WILL BREAK THIS: a Hyprland version bump.
-- hyprpm plugins are C++ .so files compiled against the EXACT Hyprland commit in use. After
-- any `pacman -Syu` that moves Hyprland off 0.56.1, every plugin silently STOPS LOADING —
-- the compositor still starts, nothing errors on screen, the borders and focus flash just
-- quietly vanish. The fix is always the same:
--
--     hyprpm update && hyprpm reload
--
-- That is exactly the state this machine was found in on 2026-08-05: hyprpm's headers were
-- pinned to an April build (0.54.3, hash 521ece46…) while Hyprland had moved to 0.56.1, so
-- 2 of the plugins would not build and NONE were loaded.
--
-- Also note the plugin roster shrank upstream: hyprexpo, hyprtrails, hyprwinwrap,
-- hyprscrolling and xtra-dispatchers were DELETED from hyprwm/hyprland-plugins in May 2026
-- ("it's been removed. It was unmaintained" — vaxry, issue #672). Only borders-plus-plus,
-- csgo-vulkan-fix, hyprbars and hyprfocus still ship. Do not go looking for the others in
-- that repo; they are not coming back.
--
-- hyprexpo therefore comes from a DIFFERENT repo: github.com/sandwichfarm/hyprexpo, the
-- maintained fork that picked the plugin up after the retirement. It is a second hyprpm
-- source, so `hyprpm update` covers it too — but if it ever goes unmaintained as well, the
-- symptom will be hyprexpo alone failing to build after a Hyprland bump while the two
-- official ones rebuild fine. If that happens, `hyprpm remove` it rather than pinning
-- Hyprland back.
--
-- NOT enabled, deliberately:
--   * hyprbars       — it builds fine and is one command away, but the titlebars and their
--                      3 buttons were removed on 2026-08-05 at Shawn's request. Re-enabling
--                      it would undo that. SUPER+H / SUPER+Q / SUPER+ALT+F replace it.
--   * csgo-vulkan-fix — fixes mouse offsets in CS:GO under Vulkan. Not installed here.
hl.config({
    plugin = {
        -- One extra border drawn OUTSIDE the normal 1px one, as a soft dark outline.
        -- Deliberately a neutral translucent black rather than an accent colour: Caelestia
        -- regenerates its Material palette from the wallpaper at runtime, so any accent
        -- hardcoded here would go stale and clash the moment the wallpaper changes. A dark
        -- outline just reads as definition against every palette.
        -- natural_rounding makes it follow the 15px window rounding instead of squaring off.
        borders_plus_plus = {
            add_borders      = 1,
            natural_rounding = true,
            border_size_1    = 2,
            col = {
                border_1 = "rgba(ffffff26)",
            },
        },

        -- Flash the window briefly when focus moves to it. Keyboard only: the mouse already
        -- tells you where focus went because your hand is on it, and flashing on every
        -- pointer cross is distracting with focus-follows-mouse.
        hyprfocus = {
            enable                   = true,
            animate_floating         = true,
            keyboard_focus_animation = "flash",
            mouse_focus_animation    = "none",
            fade_opacity             = 0.8,
        },

        -- Expose-style grid of every workspace at once, bound to SUPER+G below.
        -- 3 columns because this is a single 14" 2880x1800 panel — 4 would make each tile
        -- too small to recognise a window from, and 2 wastes half the screen.
        hyprexpo = {
            columns          = 3,
            gaps_in          = 6,
            gaps_out         = 0,
            -- Matches the dark shell background rather than pure black, so the overview
            -- reads as part of the desktop instead of a modal that blanks it.
            bg_col           = "rgb(111111)",
            -- Keeps the workspace you are already on in the centre of the grid, so the
            -- tile under your eyes does not jump when the overview opens.
            workspace_method = "center current",
            gesture_distance = 200,
            cancel_key       = "escape",
            show_cursor      = 1,
            -- OFF on purpose. With drag-drop on, a click whose pointer drifts even a few
            -- pixels is read as "move this window to that workspace" instead of "switch
            -- to that workspace". On a touchpad that drift is constant.
            drag_drop_enable = 0,
            -- Arrow/hjkl selection inside the overview. See the submap further down.
            keynav_enable    = 1,
            -- Digits pick the Nth VISIBLE tile, not the global workspace ID, which is what
            -- you actually mean when you are looking at a grid.
            number_key_mode  = "index",
            show_workspace_names = 1,
        },
    },
})

-- SUPER+G opens the overview. SUPER+G, SUPER+grave and SUPER+Tab were all confirmed free
-- by querying the RUNNING compositor (`hyprctl binds`) rather than reading the config —
-- Caelestia binds a lot of keys from Lua, so grepping the files under-reports. G was picked
-- over the other two simply as the easiest one-handed reach next to the existing SUPER row.
-- "toggle" rather than "select": pressing it again closes the overview.
--
-- Testing this from a terminal is misleading. `hyprctl dispatch 'hl.plugin.hyprexpo.expo("toggle")'`
-- OPENS the overview and then prints "error: expected a dispatcher" — the plugin call fires as
-- a side effect and returns nil, which hyprctl's own wrapper then rejects. The error is about
-- hyprctl, not the plugin. Check `hyprctl submap` (it reads "hyprexpo") to see the truth.
hl.bind("SUPER + G", function()
    hl.plugin.hyprexpo.expo("toggle")
end)

-- While the overview is open, hyprexpo activates a submap named "hyprexpo" and ONLY these
-- keys are live — the rest of the desktop's binds are suspended until it closes. That is
-- why escape has to be re-bound here explicitly: without it the overview is only closable
-- by clicking, and a keyboard-only exit would be impossible.
hl.define_submap("hyprexpo", function()
    hl.bind("left",   function() hl.plugin.hyprexpo.kb_focus("left") end)
    hl.bind("right",  function() hl.plugin.hyprexpo.kb_focus("right") end)
    hl.bind("up",     function() hl.plugin.hyprexpo.kb_focus("up") end)
    hl.bind("down",   function() hl.plugin.hyprexpo.kb_focus("down") end)
    hl.bind("h",      function() hl.plugin.hyprexpo.kb_focus("left") end)
    hl.bind("l",      function() hl.plugin.hyprexpo.kb_focus("right") end)
    hl.bind("k",      function() hl.plugin.hyprexpo.kb_focus("up") end)
    hl.bind("j",      function() hl.plugin.hyprexpo.kb_focus("down") end)
    hl.bind("return", function() hl.plugin.hyprexpo.kb_confirm() end)
    hl.bind("escape", function() hl.plugin.hyprexpo.expo("cancel") end)
end)
