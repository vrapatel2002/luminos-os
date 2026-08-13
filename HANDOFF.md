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

## Aim right now

**Shawn is LIVE in "Luminos (Caelestia on Plasma)" as of 2026-08-13.** STEP A shipped, STEP B is
done (he deleted the Plasma panel himself), and STEP C parts 1–3 are done: Caelestia's OSD shows
**volume** and **brightness** from the right edge, and **Plasma's own OSD is silenced**.

The next thing on the list is **STEP 4 — hover-to-peek** (the OSD should nose out when the cursor
reaches the right edge). Shawn asked for it and explicitly parked it as step 4. It is **not built.**

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
| Two bars during STEP A — can't we just turn Plasma's off? | Asked 2026-08-13. Answer given: **yes, and he can do it himself from the GUI in ~10 s** (right-click panel → Enter Edit Mode → More Options → Auto Hide), which is also the safest version of STEP B. Deliberately left as his switch to flip rather than a config edit, so STEP A's login tests one change, not two. |

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
5. **Reading `WAYLAND_DISPLAY` out of `kwin_wayland`'s `/proc/<pid>/environ`.** Measured
   2026-08-13: it returns **EACCES even to its own user**, because `/usr/bin/kwin_wayland` carries
   `cap_sys_nice=ep` and the kernel therefore clears the process's dumpable flag. It is also the
   wrong file even without the capability — `environ` is the environment a process was *exec'd*
   with, so later `setenv()` calls never appear there.

---

## 🔒 Standing scope rules

- Caelestia is a **look**. KWin's window behaviour stays stock.
- **Drop a feature rather than rebuild a Hyprland mechanism.**
- **Prefer removing a patch to adding one.**
- **A new session is only ever additive.** Never edit an existing greeter entry.
- **Least work that works.** This is now the governing rule, stated by Shawn directly.

---

## 📋 RULE — how a "step" is defined

Shawn caught a real failure: *"one step at a time"* meant two different things to us. I meant
"take Caelestia's shell apart one panel at a time." He heard "everything else keeps working."
Both are fair readings; mine silently hid ~15 broken things.

**Every step from now on is written down BEFORE work starts, with three lines:**

1. **When this is done, you will be able to:** _(the concrete thing he can do)_
2. **These will still be broken:** _(named individually — this is the line that was missing)_
3. **You'll know it worked when:** _(what he looks at)_

---

## STATE — what is DONE

### ✅ STEP A — built and installed 2026-08-13. NOT yet logged into.

Two new files, additive only. No existing file was edited.

| File | What |
|---|---|
| `scripts/luminos-caelestia-plasma` | the session → `/usr/local/bin/luminos-caelestia-plasma` |
| `scripts/luminos-caelestia-plasma-session` | `install` / `check` / `uninstall` |
| `/usr/share/wayland-sessions/luminos-caelestia-plasma.desktop` | greeter entry **"Luminos (Caelestia on Plasma)"** |

The greeter now offers three visible entries — Hyprland (uwsm), Caelestia on KWin, Caelestia on
Plasma. All verified present and unmodified. `check` passes every item.

**Kept from the KWin session** (each was paid for once already): the
`KWIN_DRM_DEVICES=/dev/dri/luminos-igpu` pin (BUG-094), `unset HYPRLAND_INSTANCE_SIGNATURE`,
`XDG_MENU_PREFIX=plasma-` + sycoca rebuild before start (BUG-112), and the 3-try retry loop with
the kitty escape hatch and 60 s uptime reset (BUG-092).

**Dropped:** the hand-started polkit agent and `xdg-desktop-portal-kde`. Plasma starts both.

**`config/quickshell/caelestia-bar/shell.qml` was not touched.** Same file, same symlinks.

**How it waits for Plasma** (asked for explicitly, so it is written down): it snapshots which
`wayland-*` sockets exist *before* Plasma starts, then waits for a **new** one. That cannot match a
leftover, cannot fire before the compositor exists, and yields the display name KWin actually
created. `plasmashell` appearing is a second, independent reading (it inherits `WAYLAND_DISPLAY` at
exec, so its `environ` is readable) and proof a client connected. Under `Linger=yes` an old
plasmashell can outlive its session, so it may only overrule the socket scan when the display it
names is *also* new. Socket names are matched `|`-delimited so `wayland-1` cannot be masked by
`wayland-10`; positive, negative and substring cases were all tested against the live runtime dir.

### ✅ The STEP B blocking question is ANSWERED

Whether the volume keys belong to the `plasma-pa` **applet inside the panel**: **they do not.**
`plasma-pa` ships two separate plugin binaries —
`plasma/applets/org.kde.plasma.volume.so` (applet) and
`kf6/kded/audioshortcutsservice.so` (shortcut handler). The handler is a **KDED module** in
`kded6`, its own process, started by `plasma-workspace.target`, independent of plasmashell and of
the panel. `kglobalshortcutsrc` agrees: owning component is `[kmix]`. Brightness is
`[org_kde_powerdevil]`, a systemd user service that was never in the panel.

**Removing the panel does not re-break BUG-121.** Auto-hide is still the preferred option because
it is non-destructive and less work — not because it is needed to protect the keys.

⚠️ **This is packaging evidence, not a live test.** Confirm inside the session before deleting:
`pgrep -x kded6` and `busctl --user tree org.kde.kglobalaccel | grep -iE 'kmix|powerdevil'`.

### ✅ Finding that changes STEP B's cost

`plasma.desktop` already has `NoDisplay=true` (applied by `scripts/luminos-hide-sessions`, re-applied
by a pacman hook). **Plain Plasma is not selectable at the greeter today.** So the accepted cost
"plain Plasma loses its panel too" is currently unobservable — there is no way to log in and see it.
It also means the new session becomes the only Plasma in practice, which argues further for
auto-hide over deletion.

`~/.config/plasma-org.kde.plasma.desktop-appletsrc` backed up, byte-verified, **unmodified**:
`~/.luminos-backups/appletsrc.bak-pre-step-b-20260813-111935`

---

### ✅ STEP C parts 1–3 — the OSD — SHIPPED 2026-08-13, all three proven on screen

Full reasoning in `LUMINOS_DECISIONS.md`. The short version:

1. **Volume** — added `Osd.Wrapper` in its own right-anchored `PanelWindow` in
   `config/quickshell/caelestia-bar/shell.qml`. **No shortcut was wired and none was needed:**
   `modules/osd/Wrapper.qml:51-73` reacts to PipeWire's volume *value* changing, whoever changed it.
   Wiring a key would have needed KDE's handler unbound first, or every press double-steps.
2. **Brightness** — Caelestia **observes** the backlight instead of taking the keys, so powerdevil
   keeps brightness plus its battery/lid/idle logic. `FileView` + 250 ms `Timer` on
   `/sys/class/backlight/<dev>/brightness` assigns `monitor.brightness`, which is what shows the OSD;
   it never calls `setBrightness()`, so it never writes hardware. Polling is required, not lazy —
   **sysfs raises no inotify events.** Device comes from `brightnessctl -m` (the BUG-098 shim), never
   hardcoded. First read only primes, or the OSD flies out at login.
3. **Plasma's OSD silenced** — there is no setting; a **KWin window rule** forces opacity 0.
   `~/.config/kwinrulesrc` `[2]`, snapshot at `config/kde/kwinrulesrc`.

Two traps worth keeping:
- **`wmclass=plasmashell` matches nothing.** KWin reports the OSD's class as `org.kde.plasmashell`.
  The wrong rule looks perfect and silently does nothing.
- **Never edit `/usr/lib/qt6/qml/org/kde/plasma/workspace/osd/Osd.qml`.** That `qmldir` says
  `prefer :/qt/qml/...`, so the live QML is compiled into `libplasmashell_osd.so`. Editing the file
  on disk changes nothing and reports no error.
- **Screenshot timing lies.** Firing the OSD over D-Bus then starting `spectacle` loses the race
  about half the time — the control shot "proved" a fix that was not there. Read the real opacity
  from a throwaway KWin script instead, and negative-test by forcing **50%**, not by removing the
  rule (removal leaves the last forced value on the still-existing window).

---

## NEXT STEPS (ordered)

### 1. STEP 4 — hover-to-peek from the right edge (Shawn asked; NOT built)

The OSD should nose out when the cursor reaches the right edge. It does not, because upstream's
reveal-on-hover lives in the drawers sheet's `Interactions.qml` — the full-screen surface this
config deliberately does not have. Needs a **thin** always-present hover strip that sets
`screenState.osd`. **The strip must not swallow clicks** — that is exactly BUG-110.

### 2. STEP D — Caelestia's remaining surfaces, one at a time

Remaining, easiest first: notifications → dashboard → sidebar → session menu.
(Launcher and OSD are done.)

**Rule for every one:** Plasma's version keeps working until Caelestia's replacement is proven on
screen. Never remove Plasma's first. That is what makes this plan cheap to abandon at any point.

### LATER — explicitly deferred by Shawn

- **Caelestia window styling / decorations.**
- **Caelestia's settings panel** (bottom-right popup → gear). Lift the design from upstream later.

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
**They are per-USER, not per-session, and `luminos-caelestia-kwin-session` owns them.**
`luminos-caelestia-plasma-session` deliberately only *reports* them — writing the same files from
two installers is how they drift apart.

**Meta+P → launcher** is repointed at `caelestia-bar`, so it works in both sessions.

**The other five (Meta+K, Meta+N, Meta+Escape, Meta+U, Ctrl+Alt+C) deliberately still point at
`caelestia-kwin`.** Do not "fix" this. `drawers toggle dashboard` against the bar config would
*succeed*, set `screenState.dashboard = true` with nothing rendering it, and then the launcher's
`maxHeight` reads `panels.dashboard.nonAnimHeight` off the zero-size stand-in → `NaN` → the one
panel that works breaks. **A shortcut that fails is better than one that quietly breaks something else.**

`ipc call` only ever talks to an **already running** instance and never starts one — so a shortcut
aimed at a config that is not running does nothing at all, silently.

---

## Open bugs

- **BUG-120** — Chrome hangs ~25 s on launch in the bare-KWin session. Leading theory:
  `XDG_CURRENT_DESKTOP=KDE` makes Chrome pick KWallet, no `kwalletd6` is running, so it blocks
  until the D-Bus timeout. **Still not measured.** STEP A makes the measurement possible.
- **BUG-121 — CLOSED live 2026-08-13.** `busctl --user call org.kde.kded6 /kded org.kde.kded6
  loadedModules` lists `audioshortcutsservice` **with the Plasma panel deleted**, so the volume keys
  never belonged to the panel. That upgrades the earlier packaging-only evidence to a live test.
- **BUG-117** — the `luminos-maximize` KWin script is marked enabled and has never once loaded.
- Unreproduced report: some apps open fullscreen, appear to crash, then reopen split. Crashes,
  `luminos-maximize`, KWin tiling and a control window are all ruled out with evidence. **Blocked
  on Shawn naming one offending app.** Do not "fix" it by porting Hyprland tiling.
- Tab Sleeper v3.0 needs Shawn to click Reload at `chrome://extensions`.
- Pushing: Shawn authorised a push on 2026-08-13 **for the OSD work specifically**. That is not
  standing permission — ask again next time.
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
  at a time" ambiguity. He proposed the step-definition rule. He asked "can't we turn it off?"
  about the two bars, which was the right question and had a better answer than the plan assumed.
  Take his observations seriously.
- **Show him before killing a test instance.** He asked for this explicitly.
