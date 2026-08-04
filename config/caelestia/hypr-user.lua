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
-- Reserved: SUPER+SPACE
-- ═════════════════════════════════════════════════════════════════════════════════════════
-- DELIBERATELY NOT BOUND. That is the Luminos HIVE popup shortcut and gets wired up in Phase 5.
-- Confirmed free in stock Caelestia: its launcher is a bare SUPER tap (kbLauncher =
-- "SUPER + SUPER_L") and SUPER+SPACE is not used by anything. The nearest neighbour is
-- SUPER+ALT+Space (toggle floating), which does not clash.

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
