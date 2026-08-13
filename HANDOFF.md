# HANDOFF — Caelestia desktop on KDE
# [CHANGE: claude-code | 2026-08-13]

**Read this whole file before touching anything. The direction changed on 2026-08-13 and most of
the older reasoning in git history is now superseded.**

---

## The goal, in Shawn's words

> "i want the exact shell but not as shell."

The Caelestia **look** — its bar, launcher, dashboard, volume and brightness bars, notifications,
and eventually its window styling — on a desktop that otherwise behaves like normal KDE. Nothing
covering the screen. Clicks land where you aim them.

---

## THE PIVOT — 2026-08-13. Read this before proposing anything.

The previous plan was: **bare `kwin_wayland`, and rebuild every desktop feature by hand.**
That plan is **retired.** It was my call, and it was the wrong one.

**Why it was wrong.** I assumed the list of things we'd need to add back was short. It is not —
it is most of Plasma. Two days of real use produced: Chrome hanging ~25 s on every launch
(BUG-120), dead volume keys, dead brightness keys, no notifications, no idle screen-off, no
password safe. Every one of those is a separate hand-built piece with its own bugs, and each one
is something Plasma already does correctly for free.

Shawn named the constraint plainly, and it governs from here:

> "we have to as much less work as possible to avoid bugs and save time"

**The new plan: run FULL Plasma, and take away its panel. Caelestia goes on top.**

### The trap that made me reject this originally — and why it does not apply

DECISION 63 rejected `startplasma-wayland` because suppressing plasmashell needs
`systemctl --user set-environment LUMINOS_SHELL=caelestia` plus a `ConditionEnvironment=` drop-in,
and **this user has `Linger=yes`** — the systemd user manager outlives logout, so the variable
would still be set the next time Shawn picked plain Plasma at the greeter, handing him a session
with no shell at all and no clue why.

**That reasoning is still correct — but it only applies if you switch plasmashell OFF.**

We are not doing that. **plasmashell keeps running.** We only remove the *panel it draws*. No env
variable, no systemd drop-in, no `ConditionEnvironment=`, so the linger trap never exists.

### The one real cost, and why it is acceptable

`plasma-org.kde.plasma.desktop-appletsrc` is **per-user, not per-session**. There is exactly one of
it. Remove the panel and **plain Plasma loses its panel too.**

Explained to Shawn in these terms, and accepted:

| | plasmashell OFF (rejected) | panel removed (chosen) |
|---|---|---|
| What you see | black screen, nothing | desktop + wallpaper, no panel |
| Right-click | dead | works |
| Way out | none, no clue why | right-click → Add Panel, ~10 s |

Different class of problem entirely. One is a landmine; the other is a light switch you can find
in the dark.

---

## Shawn's answers — decided, do not re-litigate

| Question | His answer |
|---|---|
| Shortcut conflicts between Plasma and Caelestia | **"May be keep the plasma ones."** Plasma wins by default. Only take a key for Caelestia when its version is clearly better AND he has said so. |
| plasmashell's RAM cost (~300–500 MB) | **"got it no problem."** Accepted. Do not re-raise it as a concern. |
| Two wallpapers (Plasma's and Caelestia's) | **Decide later, after seeing both live.** Do not pick for him. |
| Keep the current bare-KWin session? | **"for now its working good so do not delete it."** It stays as the fallback and as the only place to test Caelestia without Plasma helping. |
| How much of Caelestia does he want? | **All of it.** Bar, launcher, dashboard, **volume bar, brightness bar, notifications, "and more"**, plus **Caelestia's window styling**. |
| Caelestia's own settings panel | He pointed at it — bottom-right → popup → gear icon — as a **reference to lift from later**. Explicitly *"this but for later part."* Do not build it now. |

---

## 🚫 DEAD ENDS — do not propose these again

1. **Porting Caelestia to Plasma applets.** Measured 2026-08-13: **269 QML files, 226 import
   `Caelestia.*`, 134 import `Quickshell.*`**, and `Caelestia.Config` is a compiled C++ plugin
   with its QML embedded as a Qt resource. Plasma has none of that. This is a rewrite, not a port.
2. **Repainting Plasma in Caelestia's colours.** Shawn rejected this outright on 2026-08-09 and was
   right: tokens are not a shell. A purple Plasma panel is not Caelestia's launcher.
3. **Porting Hyprland's tiling to KWin.** He asked for the opposite. KWin's window behaviour stays
   **stock**.
4. **Switching plasmashell off via a systemd environment variable.** See the linger trap above.

---

## 🔒 Standing scope rules

- Caelestia is a **look**. KWin's window behaviour stays stock.
- **Drop a feature rather than rebuild a Hyprland mechanism.**
- **Prefer removing a patch to adding one.**
- **A new session is only ever additive.** Never edit an existing greeter entry.
- **Least work that works.** This is now the governing rule, stated by Shawn directly.

---

## 📋 NEW RULE — how a "step" is defined from now on

Shawn caught a real failure: *"one step at a time"* meant two different things to us. I meant
"take Caelestia's shell apart one panel at a time." He heard "everything else keeps working."
Both are fair readings; mine silently hid ~15 broken things.

**Every step from now on is written down BEFORE work starts, with three lines:**

1. **When this is done, you will be able to:** _(the concrete thing he can do)_
2. **These will still be broken:** _(named individually — this is the line that was missing)_
3. **You'll know it worked when:** _(what he looks at)_

---

## THE PLAN

### STEP A — a fourth greeter entry: full Plasma + Caelestia's bar

1. **When this is done, you will be able to:** log in to "Luminos (Caelestia on Plasma)" and get a
   complete, working KDE desktop with Caelestia's bar on the left — volume keys, brightness keys,
   notifications, Chrome opening instantly, idle screen-off, all working because Plasma is doing them.
2. **These will still be broken:** Plasma's own panel is still on screen (STEP B removes it), so
   there are two bars. Caelestia's dashboard / sidebar / session menu / OSD / notifications are
   still absent. Workspace pips and the active-window entry still read wrong — they are Hyprland
   IPC and always will be here.
3. **You'll know it worked when:** volume keys move the volume, and Chrome opens in under 2 seconds.

**How:** copy `scripts/luminos-caelestia-kwin` to a new script. Replace the `exec kwin_wayland …`
tail with `startplasma-wayland`, and keep the shell-retry loop, but start it **after** Plasma is up.

**⚠️ The one thing to get right here.** Do **not** start Caelestia from an XDG autostart `.desktop`
— Plasma 6 runs those through the **systemd user manager**, which under `Linger=yes` has a stale
environment from whichever session ran last, and it would also fire in plain Plasma. Start it from
the session script itself, after waiting for the Wayland socket. That is the same shape the
existing script already uses, so it is mostly copy-paste.

Keep: the `KWIN_DRM_DEVICES=/dev/dri/luminos-igpu` pin, the `unset HYPRLAND_INSTANCE_SIGNATURE`,
the `XDG_MENU_PREFIX=plasma-` line (BUG-112), and the logging to
`~/.local/state/luminos/caelestia-plasma/`.

Drop: the hand-started polkit agent and portal — **Plasma starts both itself.** Starting them twice
is exactly the kind of added patch the scope rules say to avoid.

### STEP B — remove the Plasma panel

1. **When this is done, you will be able to:** see only Caelestia's bar. One bar, not two.
2. **These will still be broken:** plain Plasma also has no panel until you right-click → Add Panel.
   Everything else in plain Plasma is untouched.
3. **You'll know it worked when:** the bottom strip is gone in both sessions, and right-clicking the
   desktop in plain Plasma still offers "Add Panel".

**Back up `~/.config/plasma-org.kde.plasma.desktop-appletsrc` before touching it.** Restoring that
one file is the whole undo.

**Open question to settle first, with a measurement, not a guess:** does removing the panel also
kill the **volume keys**? On Plasma 6 the media-key shortcuts may be registered by the `plasma-pa`
applet, which lives in the panel. If so, removing the panel re-breaks the exact thing STEP A fixed.
**Check this before deleting anything.** If it is true, the fallback is auto-hide instead of
removal — the panel still exists, still owns its shortcuts, and just is not drawn. Auto-hide is
also non-destructive to plain Plasma, so it may be the better answer regardless.

### STEP C — prove the gaps are actually closed

Not a build step, a measurement step. Confirm on the real login: volume keys, brightness keys,
notification popups, Chrome launch time, idle screen-off, the password safe. Close BUG-120 and
BUG-121 with evidence, or find out the plan is wrong early.

### STEP D — bring Caelestia's own surfaces across, one at a time

Order, easiest first: launcher (**already built and working**, see below) → volume/brightness OSD →
notifications → dashboard → sidebar → session menu.

**Rule for every one of these:** Plasma's version keeps working until Caelestia's replacement is
proven. Never remove Plasma's until Caelestia's is on screen and working. That is what makes this
plan cheap to abandon at any point.

### LATER — explicitly deferred by Shawn

- **Caelestia window styling / decorations.**
- **Caelestia's settings panel** (bottom-right popup → gear). Lift the design from upstream when
  we get there.

---

## What already exists and works — reuse it, do not rebuild it

### `config/quickshell/caelestia-bar/shell.qml` — bar + launcher in their own windows

Commit `296d0586`. This is the piece that carries forward **unchanged** into the Plasma session.
It hosts upstream's `modules/bar/BarWrapper.qml` and `modules/launcher/Wrapper.qml` **unmodified**,
each in its own `PanelWindow`. No Caelestia code was copied or rewritten.

Why it works: `BarWrapper` is a plain QML `Item`, not a window, with four required properties and
an already-computed `readonly property int exclusiveZone`. It is *designed* to be dropped into a
container. Upstream's container is the full-screen sheet; ours is a thin `PanelWindow`.

`Launcher.Wrapper.panels` is a plain `var`, and only four sub-properties are ever read
(`panels.bar.implicitWidth`, `panels.popouts.{hasCurrent,currentName,currentCenter}` at
`launcher/WallpaperList.qml:26-31`, plus `utilities.implicitWidth` / `dashboard.nonAnimHeight`
behind guards). So a 4-property `QtObject` shim replaces the entire `Panels` item.

Config dir `~/.config/quickshell/caelestia-bar/` — `assets components modules services utils` are
symlinks into `~/.config/quickshell/caelestia-kwin/`, so it inherits the KWin patches to
`services/{Brightness,ShellState}.qml`. Run by hand: `qs -c caelestia-bar`.

**Proven:** bar `xywh: 60 10 60 880`; launcher `xywh: 459 346 632 534`, bottom-anchored, verified
over three open/close cycles with 0 surfaces after each close. Shawn confirmed it live on KWin.

### Two QML gotchas that cost real time — do not rediscover them

1. **`Tokens` is an attached property from the compiled `Caelestia.Config` plugin, not a global.**
   `Tokens.rounding.*` without `import Caelestia.Config` fails at **runtime** with
   `ReferenceError: Tokens is not defined` — it loads fine, then breaks.

2. **Never bind a `PanelWindow.visible` to an animated property of its own contents.** The first
   launcher build used `visible: launcher.visible`, and `Wrapper.qml:34` is `visible: offsetScale < 1`
   driven by a `Behavior` animation. Under `QSG_RENDER_LOOP=threaded` a hidden window gets **no
   frames**, so the animation never advances and `visible` never leaves `false`. **The launcher
   opened exactly once, then the key was dead forever.** It failed silently from every angle: no
   log warning, and `ipc call drawers isOpen launcher` cheerfully answered `1` the entire time.
   Only `hyprctl layers` revealed there was no surface. Fix:
   `visible: scope.screenState.launcher || launcher.visible`.

### Shortcuts

`~/.local/share/applications/luminos-cael-*.desktop`, each carrying its own `X-KDE-Shortcuts=`.
**Meta+P → launcher** is repointed at `caelestia-bar` and its generator
(`scripts/luminos-caelestia-kwin-session`) was changed to match, so a re-install cannot clobber it.

**The other five (Meta+K, Meta+N, Meta+Escape, Meta+U, Ctrl+Alt+C) deliberately still point at
`caelestia-kwin`.** Do not "fix" this. `drawers toggle dashboard` against the bar config would
*succeed*, set `screenState.dashboard = true` with nothing rendering it, and then the launcher's
`maxHeight` reads `panels.dashboard.nonAnimHeight` off the zero-size stand-in → `NaN` → the one
panel that works breaks. **A shortcut that fails is better than one that quietly breaks something else.**

`ipc call` only ever talks to an **already running** instance and never starts one — so a shortcut
aimed at a config that is not running does nothing at all, silently.

---

## Open bugs this plan is expected to close

- **BUG-120** — Chrome hangs ~25 s on launch in the bare-KWin session. Leading theory:
  `XDG_CURRENT_DESKTOP=KDE` makes Chrome pick KWallet for password storage, and no `kwalletd6`
  is running, so it blocks until the D-Bus timeout. **Not yet measured.** The tell is the clock: a
  consistent ~25 s says D-Bus timeout; a variable delay says memory/disk and the theory is wrong.
- **BUG-121** — volume and brightness keys dead. Caelestia's own handler needs
  `hyprland_global_shortcuts_v1` (KWin has no such protocol) and Plasma's handler is not running.
  Two possible handlers, both absent for different reasons.

---

## Still open, carried forward

- **BUG-117** — the `luminos-maximize` KWin script is marked enabled and has never once loaded.
- Unreproduced report: some apps open fullscreen, appear to crash, then reopen split. Crashes,
  `luminos-maximize`, KWin tiling and a control window are all ruled out with evidence. **Blocked
  on Shawn naming one offending app.** Do not "fix" it by porting Hyprland tiling.
- Tab Sleeper v3.0 needs Shawn to click Reload at `chrome://extensions`.
- **5 commits unpushed. Ask before pushing.**
- Deferred: delete the four `[Tiling]` groups from `~/.config/kwinrc` (back it up; **not proven**
  these cause anything — this is "restore stock default", not "fix confirmed bug").

---

## Working with Shawn — what actually helps

- **He cannot open screenshots I save to disk.** Run things live on his session instead.
- **Plain words, full depth.** Strip the jargon, keep the exact numbers and the analogies.
- **Separate what I measured from what I am guessing.** He fact-checks confident claims, and he is
  right to. Say "leading suspect, not yet measured" when that is what it is.
- **He is good at this even though he says he is not.** He spotted that all the Chrome windows
  appeared *simultaneously* — the single most diagnostic fact in that bug. He caught the "one step
  at a time" ambiguity. He proposed the step-definition rule. Take his observations seriously.
- **Show him before killing a test instance.** He asked for this explicitly.
