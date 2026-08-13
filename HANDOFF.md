# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-08-13 — Response 7 (step 1 BUILT and proven on screen)
# [CHANGE: claude-code | 2026-08-13]

> One file, overwritten in place every response (AGENTS.md §0.2). A snapshot, not a log.
> Do not append to it — it reached 82 KB that way once already.

## Goal (durable)

Caelestia shell running on KWin as a usable everyday session (DECISION 63), alongside the
untouched Hyprland session, which stays the fallback.

## Aim right now

Shawn's words on 2026-08-13: *"i want the exact shell but not as shell so can we edit kwin default
and write the calestia code over there?"*

So: keep **Caelestia's real code**, stop it being a screen-covering shell. Diagnosis is done
(below). A new one step is proposed and awaiting a go. No code changed yet.

## 🚫 DEAD END — do not propose again

**The colour/token theming route is rejected.** `scripts/luminos-kde-caelestia-theme` +
`scripts/luminos-kde-caelestia-panel` + `config/kde/caelestia-design-spec.json` (DECISION 63
"Option 3") pour Caelestia's palette, fonts and geometry into Plasma's own panel. Shawn tried it
on 2026-08-09 (backups show it applied 19:01:27 and was rolled back 19:01:59, 32 s later) and his
verdict on 2026-08-13 was: *"this was shit i mean it never look like anything from shell."*
A matching palette is not the shell. Do not resurrect this.

**Porting the QML into Plasma applets is also out** — measured, not guessed: of 269 QML files,
**226 import `Caelestia.*`** and **134 import `Quickshell.*`**. Plasma has neither module. That is
a rewrite of nearly the whole shell, plus `Caelestia.Blobs`/`Caelestia.Config` are compiled C++
plugins. Fails the scope rule on its face.

## 🔒 Scope rule Shawn restated on 2026-08-13 — this now governs the whole session

> *"keep the default kwin got it do not try to copy hyperland style. keep it simple we just want it
> to look like Caelestia. nothing more one step at a time got it?"*

Caelestia is a **look**. KWin's window behaviour stays **stock**. When a Caelestia feature only
works because Hyprland does something special, the default answer is **drop the feature**, not
rebuild the mechanism. **Prefer removing a patch over adding one.** Ship one step at a time — no
numbered plans. This is the second time he has said it (DECISION 63 already says "never port the
tiling"), so treat it as hard scope, not a preference.

## Answers Shawn gave

1. Session = **Caelestia-on-KWin**. (Note the box is booted into **Hyprland** right now — `Hyprland`
   PID 1497 + `qs -c caelestia` PID 1683, up since 2026-08-11 16:33 — so nothing can be reproduced
   without him logging into the other session.)
2. Whether the bottom edge / top-right corner triggers it: **he does not know.** So the exact stuck
   boolean is still unidentified — see step 1, which is deliberately chosen to not need that answer.
3. Tiling: **remove it, keep KWin default.** Not yet done (holding to one step at a time).

## What was established this response (evidence, not theory)

### The shell is ONE whole-screen surface — this answers question 3

`hyprctl layers` on the live session, verbatim:

```
Layer level 0 (background):
  0 0 1440 900   caelestia-background
Layer level 2 (top):
  0   450  1 1   caelestia-border-exclusion
  750 0    1 1   caelestia-border-exclusion
  1439 455 1 1   caelestia-border-exclusion
  745 899  1 1   caelestia-border-exclusion
  0 0 1440 900   caelestia-drawers          <-- the entire screen
```

- `caelestia-drawers` is **the full 1440×900 logical screen**, on the **top** layer, i.e. above
  every normal window, permanently. Source: `modules/drawers/ContentWindow.qml:99-102`
  (`anchors.top/bottom/left/right: true`) and `:75` (`exclusionMode: ExclusionMode.Ignore` — it
  reserves *no* space). The bar, the rounded border, the launcher and the dashboard are all drawn
  inside that one surface.
- The only things that reserve space are the **four 1×1 px `border-exclusion` windows**, one per
  edge — `modules/drawers/Exclusions.qml:15-30`. Left = `bar.exclusiveZone`, the other three =
  `Config.border.thickness`.
- So there is **no separate "window area" surface**. Windows always live underneath the shell.
  "Windows hiding under the shell" is the architecture, not a bug — it only *looks* wrong when the
  four exclusion markers do not reserve the right amount, which is the thing to measure next.

### Clicks: the input region, not the compositor — this answers question 1

What decides whether a click hits your window or the shell is the surface's input region, `mask:`
at **`ContentWindow.qml:97`**:

```qml
mask: hasFullscreen ? emptyRegion : (luminosGrab ? null : regions)
```

- Normally `mask: regions` (`Regions.qml`, `intersection: Intersection.Xor`) punches the interior
  **out**, so clicks fall through to windows.
- **`mask: null` means the whole surface takes input** — the patch's own comment at
  `ContentWindow.qml:79-84` says exactly that. It was added deliberately because KWin has no
  `hyprland_focus_grab_v1` (confirmed in `shell.log`: *"The active compositor does not support the
  hyprland_focus_grab_v1 protocol"*), so an outside click has to physically reach the shell.
- `luminosGrab` (`ContentWindow.qml:85-95`) is true for: launcher, session menu, sidebar,
  non-hover dashboard, nested tray menu, **or any detached popout**.
- `~/.config/caelestia/shell.json` has **`launcher.showOnHover: true`**. So brushing the bottom
  edge opens the launcher → `luminosGrab` → the whole screen swallows input.

**The trap (hypothesis, not yet reproduced):** once the mask is null, the `Interactions` MouseArea
covers the whole screen, so `containsMouse` can never go false, so `onContainsMouseChanged`
(`Interactions.qml:125`) — the handler that closes hover-opened panels — can never fire. The state
that makes the mask null is the state that stops the code from clearing it. The only remaining exit
is `onPressed` → `luminosClickOutside()` (`Interactions.qml:120-124`), and **that click is
consumed** — one dead click, then the next works. If `luminosOnOpenPanel()` (`:84-106`) wrongly
reports the press as *inside* an open panel, the panel never closes and **every** click is dead
until something else resets it. That is the "stuck" state.

Ruled out: **BUG-114 (tap-to-click) is genuinely fixed** — `~/.config/kcminputrc` has
`TapToClick=true` under `[Libinput][2362][12305][ASUP1208:00 093A:3011 Touchpad]`, written by
`luminos-caelestia-kwin-session:159`. Still worth confirming bare `kwin_wayland` applies kcminputrc
with no kded6 running.

### "Hyprland layout" is actually KWin's own custom tiling — this answers question 2

`~/.config/kwinrc` contains **four** `[Tiling][<output-uuid>][<desktop-uuid>]` groups, every one of
them:

```
padding=4
tiles={"layoutDirection":"horizontal","tiles":[{"width":0.25},{"width":0.5},{"width":0.25}]}
```

A saved **25% / 50% / 25% three-column** custom tile layout (KWin 6's Meta+T feature), for two
different output UUIDs and three desktop UUIDs. Bare `kwin_wayland` reads the same `~/.config/kwinrc`
as Plasma, so it applies in the Caelestia-on-KWin session too. This is very likely what AGENTS.md
§14 item **0d(a)** describes as apps that "open fullscreen, appear to crash, then reopen in a split
shape" — it looks like Hyprland dwindle, but nothing Hyprland is involved.
`~/.config/kwinrulesrc` holds only one unrelated rule (Wine/WinRAR).

## STEP 1 — DONE 2026-08-13, verified on screen

**`config/quickshell/caelestia-bar/shell.qml` (new, tracked in the repo) runs Caelestia's REAL bar
in its own thin left-edge `PanelWindow`, with no full-screen sheet anywhere.**

Wiring:
- `~/.config/quickshell/caelestia-bar/` — `assets components modules services utils` are symlinks
  into `~/.config/quickshell/caelestia-kwin/` (so it inherits the KWin patches to
  `services/{Brightness,ShellState}.qml`), and `shell.qml` is a symlink to the repo file.
- Nothing in `luminos-caelestia-kwin-overlay` or `caelestia-kwin/` was touched. Existing session
  is untouched and remains the fallback.
- Run it with `qs -c caelestia-bar`.

Why it works at all: `modules/bar/BarWrapper.qml` is a plain QML `Item`, not a window, with four
required properties (`screen`, `screenState`, `popouts`, `fullscreen`) and an already-computed
`readonly property int exclusiveZone`. It is *designed* to be dropped into a container. Upstream's
container is the full-screen `Drawers` sheet; ours is a `PanelWindow` whose `implicitWidth` and
`exclusiveZone` bind straight to the wrapper's. No bar code was copied or rewritten.

**Proof (not a claim):** launched live on the running Hyprland session 2026-08-13 01:09.
`hyprctl layers` showed `xywh: 60 10 60 880, namespace: caelestia-bar, pid 71557` — its own 60 px
surface, correctly excluded, nothing covering the screen. `grim` capture at
`/tmp/caelestia-bar-shot.png` (crop `/tmp/caelestia-bar-compare.png`) shows the new bar next to the
real one: logo, workspace pill, status icons, clock, tray pill, power button — identical geometry,
colour, font and rounding. Test instance killed afterwards; `qs -c caelestia` PID 1683 untouched.

**Differences actually observed, do not overstate the win:**
- The active-window entry read **"Desktop"** on the new bar while the original read
  "Claude (legacy)". That widget is `Hypr.activeToplevel`, i.e. Hyprland IPC. On KWin expect it
  permanently "Desktop". Same for the workspace pips — they rendered, but they are
  `Quickshell.Hyprland` backed and were mirroring the *original* instance's IPC, so **they are not
  proven to work on KWin**. Measure there before claiming anything.
- No rounded screen border / 10 px gap — that is painted by the sheet's blob. Expected, stated
  up front, would need its own thin window later.
- Bar popouts (hover a status icon) do nothing. `checkPopout()` is only ever called from
  `Interactions.qml`, which belongs to the sheet. A `BarPopouts.Wrapper` is instantiated only
  because `BarWrapper` requires one; it is `visible: false`.
- `PowerProfiles` DBus warning on launch is the masked `power-profiles-daemon` (DECISION 39/41),
  not new.

## STEP 2 — ARMED 2026-08-13, waiting on Shawn to log in

`scripts/luminos-caelestia-kwin` now has ONE switch near the top:

```bash
export SHELL_DIR="$HOME/.config/quickshell/caelestia-bar"   # was caelestia-kwin
```

The inner script picks it up via the environment (`SHELL_DIR="${SHELL_DIR:-...caelestia-kwin}"`),
so there is no second path to forget. Installed to `/usr/local/bin/luminos-caelestia-kwin` with
`sudo install -m755` and read back to confirm (line 40 / line 86). `bash -n` clean.

**Revert = change that one word back to `caelestia-kwin` and re-install.**

Shawn has to log out and pick **Caelestia-on-KWin** at the greeter. Only he can do that part.

What that session will have: **the bar and the launcher**. Still missing: dashboard, sidebar,
session menu, OSD, notifications, utilities, bar popouts — those live in the sheet, which is gone.
Their five `~/.local/share/applications/luminos-cael-*.desktop` shortcuts (Meta+K, Meta+N,
Meta+Escape, Meta+U, Ctrl+Alt+C) still `ipc call` into `caelestia-kwin`, which will not be
running, so they fail. **That is deliberate** — see STEP 2b. Escape hatches: **Meta+Return →
kitty** (`luminos-cael-terminal.desktop`) and **Ctrl+Alt+T → konsole**.

The four things to actually judge there:
1. Do clicks work everywhere on screen? (the whole point)
2. Do the workspace pips render/work, or are they dead? (`Quickshell.Hyprland`)
3. Does the active-window entry say "Desktop"? (expected yes)
4. Does Meta+P open the launcher, and **can you type into the search field**? Only Shawn can
   answer 4 — see the keyboard-focus note in STEP 2b.

## STEP 2b — the launcher, added 2026-08-13 (asked for: "make the launcher also work there")

Same trick as the bar: upstream's `modules/launcher/Wrapper.qml` unmodified, in its own
bottom-anchored `PanelWindow` inside a per-screen `Scope`. Nothing about the launcher was rewritten.

Two things made it fit:
- **`Launcher.Wrapper.panels` is `var`, not a typed `Panels`.** Grep proved only four sub-properties
  are ever read: `panels.bar.implicitWidth` and `panels.popouts.{hasCurrent,currentName,currentCenter}`
  at `launcher/WallpaperList.qml:26-31`, and `panels.utilities.implicitWidth` /
  `panels.dashboard.nonAnimHeight` — both behind `if (screenState.…)` guards for panels we do not
  have. So a 4-property `QtObject` shim replaces the whole `Panels` item.
- `Shortcuts {}` is instantiated for the `drawers` IPC target, which is what Meta+P calls. Its
  `CustomShortcuts` are Hyprland-only and will log "unsupported" on KWin — expected noise.

**Proof:** run live on Hyprland 2026-08-13, `qs -c caelestia-bar`, PID 78431.
`qs -p …/caelestia-bar ipc call drawers toggle launcher` → rc=0, then `drawers isOpen launcher` → 1.
`hyprctl layers`: `caelestia-launcher xywh: 459 346 632 534` — bottom edge at 880 on a 900 px
screen, i.e. bottom-anchored, not floating in the middle. `grim` capture shows the app list, icons,
descriptions and the `Type ">" for commands` field rendering exactly like upstream.

**Meta+P now points at the running config.** `luminos-cael-launcher.desktop` `Exec=` was repointed
from `caelestia-kwin` to `caelestia-bar`, and `luminos-caelestia-kwin-session` was changed to match
so a re-install does not clobber it (`SHELL_DIR` = the running config, new `SHELL_DIR_FULL` = the
old one). **The other five shortcuts were deliberately NOT repointed**: `drawers toggle dashboard`
against the bar config would *succeed*, set `screenState.dashboard = true` with nothing rendering
it, and then the launcher's `maxHeight` reads `panels.dashboard.nonAnimHeight` off the zero-size
stand-in → `NaN` → the one panel that works breaks. A shortcut that fails is better than one that
quietly breaks something else.

**UNVERIFIED, and only Shawn can settle it — `WlrKeyboardFocus.Exclusive`.** KWin has no
`hyprland_focus_grab_v1`, so without an exclusive grab the search field never receives the keyboard
and the launcher is a picture you cannot type into. The window takes `Exclusive` only while
`screenState.launcher` is true, and hiding it hands the keyboard straight back. Exits if it ever
sticks: **Escape** (`launcher/Content.qml:86`), **Meta+P** again, or **Ctrl+Alt+Backspace**.

**Known cosmetic difference, stated up front:** the launcher's rounded backdrop is a plain
`StyledRect` with `Tokens.rounding.extraLarge`. Upstream's is a blob in the sheet that stretches
toward the bar as it opens. Ours does not do the goo and will not pretend to.

**Two gotchas found the hard way:**

1. `Tokens` is an *attached property* from the compiled `Caelestia.Config` plugin, not a global.
   Using `Tokens.rounding.*` without `import Caelestia.Config` fails at **runtime** with
   `ReferenceError: Tokens is not defined`, not at load.

2. **Never bind a `PanelWindow.visible` to an animated property of its own contents.** The first
   version was `visible: launcher.visible`, and `Wrapper.qml:34` is `visible: offsetScale < 1`
   where `offsetScale` is driven by a `Behavior` animation. Under `QSG_RENDER_LOOP=threaded` a
   hidden window gets no frames, the animation never advances, `visible` never leaves `false` —
   so **the launcher opened exactly once and the key was dead forever after**. It failed silently
   from every angle: no warning in the log, and `ipc call drawers isOpen launcher` kept answering
   `1`. Only `hyprctl layers` showed there was no surface. Fix is
   `visible: scope.screenState.launcher || launcher.visible` — the plain bool opens it instantly,
   the animated one keeps it up through the close animation. **Verified with three open/close
   cycles**, `xywh: 459 346 632 534` each time, 0 surfaces after each close.

## After that, in order (do NOT start these yet)

1. ~~Give the launcher its own small window the same way~~ — DONE, see STEP 2b. Next the
   dashboard, then the sidebar — one per step. When a panel lands, repoint its
   `luminos-cael-*.desktop` at `SHELL_DIR` in `luminos-caelestia-kwin-session` (add its id to the
   `[ "$id" = "launcher" ]` test) and drop its `absent` entry from the `panelsShim`.
3. Delete the four `[Tiling]` groups from `~/.config/kwinrc` (Shawn approved: "keep the default
   kwin"). Back the file up first. Note it is **not proven** these cause the reshaping — KWin custom
   tiles apply on quick-tile/drag, not to newly-opened windows — so removing them is "restore stock
   default", not "fix confirmed bug". Do not oversell it.
4. Measure whether KWin honours `exclusiveZone` at all in a bare `kwin_wayland` session: does the
   work area actually shrink, or do maximized windows still cover 0,0–1440×900?

## Superseded (kept so it is not re-proposed as new)

The previous one step — deleting the click-outside patch (`luminosGrab` + `mask: ... null ...` in
`ContentWindow.qml`, and the whole `Interactions.qml` patch) from the overlay — is still a correct
fix **for the existing session**, and remains the fallback if the separate-windows route is refused.
Keep the other `ContentWindow.qml` patch either way (`if (!monitor) return 0` in `dragMaskPadding`)
— that one *fixes* clicking by disarming the invisible edge drag bands. Cost of that route: clicking
empty desktop no longer closes an open panel; Escape still works
(`modules/launcher/Content.qml:86`, `modules/session/Content.qml:104`).

## Gotchas / do NOT redo

- **Never port Hyprland's tiling into this session** — Shawn has said so directly.
- Every bug in this shell so far has the same shape: **a Hyprland API returns null, and null
  silently evaluates false**. No error, no log line, the feature takes the wrong branch. Suspect the
  compositor bridge before suspecting the QML.
- Worse variant: a *write* to a stub component (`HyprlandFocusGrab.active`) is dropped, so it reads
  back **false forever** and every binding on it freezes. Never depend on it.
- `shell.log` shows `hyprland_global_shortcuts_v1` unsupported ~22×. That is expected and already
  worked around with `X-KDE-Shortcuts=` .desktop files — not a new finding, do not re-chase it.
- The `eglInitialize failed` lines in the session log are **probe noise**, settled by BUG-115.
- Do not judge session state from the agent shell's own env — it is frozen at the session that
  spawned it. Use `pgrep -a`, `loginctl`, `/proc/<pid>/environ`.

## Standing repo rules (carry forward)

- **NEVER `git add -A`.** An API key got published that way (BUG-086, WONTFIX per Shawn — do not
  re-raise rotation). The tree holds unrelated in-flight work: `_to_delete/`, `reference_code/`,
  `config/kde/caelestia-design-spec.json`, `scripts/luminos-kde-caelestia-{panel,theme}`,
  `scripts/brightnessctl`, `switch-to-old-claude.sh`, `fix-claude-legacy.sh`, dirty
  `research/turboquant` submodules, modified `scripts/luminos-session-recorder`. **Stage by name.**
- **Luminos scripts print success on failed paths.** Verify writes by reading them back.
- **`luminos-brain safe` NOs are usually false** — it greps its own header banner.
- **BUG-080: the forex bot is live trading.** Check before anything that reboots or kills processes.

## Still open from the previous round (unchanged)

- **Tab sleeper v3.0 needs one click from Shawn**: `chrome://extensions` → Luminos Tab Sleeper →
  **Reload**. Chrome does not auto-reload unpacked extensions, so the live worker is still v2.0 and
  the 2-tab cap is not in force. Verify with `luminos-tabs` (says `NEVER REPORTED` until v3.0 runs).
  While there, turn Memory Saver off at `chrome://settings/performance`.
- Nothing from the DECISION 66 round is committed. Also unpushed: `5321eada`, `fc84917f`,
  and now `72a773b1`/`cbeb42cb`. **Ask before pushing.**
- **BUG-117** still open: `luminos-maximize`'s `metadata.json` lacks `KPackageStructure`, so KWin
  rejects it every startup while `kwinrc` says it is enabled. Ruled out as the cause of 0d(a).

## Files read (nothing modified except this file)

`AGENTS.md`, `HANDOFF.md`, `~/.config/quickshell/caelestia-kwin/modules/drawers/{ContentWindow,Interactions}.qml`,
`/etc/xdg/quickshell/caelestia/shell.qml`,
`/etc/xdg/quickshell/caelestia/modules/drawers/{Exclusions,Regions}.qml`,
`/etc/xdg/quickshell/caelestia/modules/bar/BarWrapper.qml`,
`scripts/luminos-caelestia-kwin-overlay`, `scripts/luminos-kde-caelestia-{theme,panel}`,
`config/kde/caelestia-design-spec.json`,
`~/.config/caelestia/shell.json`, `~/.config/kwinrc`, `~/.config/kwinrulesrc`, `~/.config/kcminputrc`,
`~/.local/state/luminos/caelestia-kwin/shell.log`, `~/.local/share/luminos-kde-backup/`.

Import census (measured with ripgrep, 2026-08-13): 269 QML files under
`/etc/xdg/quickshell/caelestia`; **226 import `Caelestia.*`**, **134 import `Quickshell.*`**.
