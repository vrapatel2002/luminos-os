# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-08-11 — Response 1

> **This file was reset on 2026-08-11.** It had grown to 82 KB by being *appended* to for
> weeks, which is the one thing AGENTS.md §0.2 forbids — it is meant to be a single
> always-current snapshot, overwritten. Everything that was in it is preserved in git
> (`git show 1b74898a:HANDOFF.md`), in `LUMINOS_DECISIONS.md`, and in `docs/BUGS.md`.
> **Do not append to this file. Rewrite it.**

---

## Goal (the durable end objective)

Run the **real Caelestia shell on KWin** as a third, opt-in login session — Caelestia's
look and animations, KWin's compositor — without touching or endangering the two sessions
that already work (Plasma, and Hyprland+Caelestia). DECISION 63.

## Aim right now

Close the last two live complaints from the user's own testing of that session:

1. ~~Every popup stayed locked open — clicking outside never dismissed it.~~ **FIXED
   2026-08-10, BUG-116.** Live in the running shell. **Awaiting the user's own confirmation**,
   in particular for the detached popouts (volume / brightness / notifications), which
   were never exercised by hand.
2. **OPEN — apps "open fullscreen, crash, and reopen in the Hyprland split style."**
   Not reproduced, not root-caused. **Blocked on the user naming one offending app.**

## Why / motivation

Shawn explicitly rejected the cheap version of this ("Plasma wearing Caelestia's colour
tokens") — he wants the actual QML shell. Both existing sessions stay; he picks at the
SDDM greeter. **The Hyprland session is the fallback and must never break.**

## Process / approach

- Everything **additive and reversible**. Back up before changing. The installer has an
  `uninstall` that reverts fully.
- The shell config is an **overlay**, not a fork: `~/.config/quickshell/caelestia-kwin` is
  279 symlinks into `/etc/xdg/quickshell/caelestia` plus 4 real patched files. Patches are
  re-derived from current upstream on every build and each anchor must match **exactly
  once**, so a Caelestia package upgrade fails the build loudly instead of shipping a
  stale copy. Rerunning the overlay script is the entire maintenance story.
- **Prove it, don't assert it.** Run the tool end to end; negative-test any health check.

---

## State — what is DONE

| Thing | Status |
|---|---|
| Session installed as a greeter entry, "Luminos (Caelestia on KWin)" | ✅ logs in |
| Overlay build + `--check` + `--remove` guard | ✅ clean, 279 symlinks / 4 patches |
| `check` subcommand — 14 assertions incl. "Hyprland session still present" | ✅ all green |
| BUG-112 — empty KService cache killed every KDE global shortcut | ✅ fixed |
| BUG-113 — all drawers no-op (`ShellState.forActive()` null under KWin) | ✅ fixed |
| BUG-114 — trackpad click dead (KDE ships tap-to-click **off**) | ✅ fixed |
| BUG-115 — "session feels slow" | ✅ **not a graphics problem**, see below |
| BUG-116 — every popup locked open | ✅ fixed, proven with a synthetic click |
| Drag bands eating clicks | ✅ fixed (`ad5b8e3e`) |

**BUG-115 is answered with the compositor's own words.** The session now records what KWin
actually chose, 8 s after login, to `~/.local/state/luminos/caelestia-kwin/kwin-render.log`:

```
Compositing Type: OpenGL
OpenGL renderer: AMD Radeon 780M Graphics (radeonsi, phoenix, ACO, Mesa 26.1.6)
Scale: 2   Refresh Rate: 120000   Adaptive Sync: never
```

Hardware GL on the iGPU at 120 Hz, VRR off. **The `eglInitialize failed` lines in the
session log are noise** — KWin probes EGL several ways and expects some probes to fail.
Do not chase them again.

## State — what is IN PROGRESS

**Nothing is half-applied.** Working tree is clean of this work; `main == origin/main` at
`1b74898a`. The last change is live in the running shell (pid started 17:34:55, patch files
written 17:34:39 — verified by mtime, not assumed).

The only unfinished item is *verification by a human*: the detached-popout half of BUG-116.

## Next steps (ordered)

1. **Ask the user which app** opens fullscreen and re-shapes itself. Then watch it open
   under a KWin `windowAdded` + `frameGeometryChanged` script (recipe below). Do **not**
   guess further without that name.
2. **Get confirmation** that volume / brightness / notification popouts now dismiss.
3. **BUG-117** — `luminos-maximize` is marked enabled in `kwinrc` but its
   `metadata.json` is missing `"KPackageStructure": "KWin/Script"` and `X-Plasma-API`, so
   KWin has rejected it at every single startup. It has never run. Either fix the metadata
   or stop claiming it is enabled. (It is **not** the cause of item 1 — it cannot be, it
   never loads.)
4. Known gaps in this session, all documented under DECISION 63, none of them regressions:
   empty workspace pills; active-window always reads "Desktop"; no idle screen-off (no
   powerdevil, by design); **Caelestia's lock screen is impossible here** — KWin has no
   `ext-session-lock-v1`; KWin draws titlebars.
5. Offered and **not** accepted yet: the Hyprland session is running the 120 Hz panel at
   60 Hz. And, for the 8th time, the ~50-line userspace dwell timer for BUG-110.

---

## Key decisions & constraints

- **DECISION 63** — Caelestia on KWin is a *third session*, not a migration. Plasma stays
  the default and supported session.
- **NEVER port Hyprland's tiling / split behaviour into it.** The user said this in as many
  words: *"do not try to copy the hyperland. things that split thing and all"*.
- **Hyprland session must stay untouched.** The overlay `check` asserts it still exists.
- The session is bare `kwin_wayland --xwayland`, **not** `startplasma-wayland` — the user
  has `Linger=yes`, so a `systemctl --user set-environment LUMINOS_SHELL=…` would outlive
  logout and hand him a shell-less Plasma desktop the next time he picked plain Plasma.
- When the user says he has a time budget, honour it literally and report back rather than
  finishing.

---

## Gotchas / dead-ends / things NOT to redo

### The single pattern behind every bug in this session

**Caelestia asks Hyprland questions. Under KWin those calls return null, and null silently
evaluates false.** No error, no log line — the feature just takes the wrong branch. Four
separate features broke this exact way: `ShellState.forActive()`, `Brightness.getMonitor()`,
`dragMaskPadding`, and the `hasFullscreen` chain. **When something in this shell "does
nothing", suspect a compositor API before suspecting the QML.**

There is a nastier variant: **a *write* to a stub component is dropped, so the property
reads back false forever and every binding on it freezes.** `HyprlandFocusGrab.active` does
this. The first version of the BUG-116 patch keyed off it, silently did nothing, and looked
like a syntax error. It also makes upstream's own `if (focusGrab.active) return 0;` dead
code here. **Recompute the condition into a local `readonly property`; never read back a
property you set on a component that may be a stub.**

### Tooling that does not work on this session

- **There is no scriptable screenshot.** `grim` fails outright (needs wlr-screencopy, a
  wlroots thing). `spectacle -b -n -f -o out.png` **exits 0 and writes no file** — it
  SIGABRTs, confirmed by three coredumps. Use textual state instead.
- **`qs ipc` is the honest state oracle:** `qs -p <dir> ipc call drawers isOpen launcher`
  returns 1/0. That removed the need for screenshots entirely.
- **KWin's scripting engine is a fine read-only probe.** `print()` output lands in the
  session log:
  ```
  printf 'print("CURSOR "+workspace.cursorPos.x+" "+workspace.cursorPos.y);' > /tmp/p.js
  id=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript /tmp/p.js probe)
  qdbus6 org.kde.KWin /Scripting/Script$id org.kde.kwin.Script.run
  ```
  Same trick gives `workspace.windowList()` geometry and `windowAdded` /
  `frameGeometryChanged` watching. **This is the recipe for next step 1.** Unload scripts
  when done.
- **`ydotool mousemove --absolute` teleports the cursor to (1,1) here**, whatever you ask
  for. Only relative moves in a convergence loop that reads `workspace.cursorPos` back each
  step are reliable — and even relative is accelerated (`-x 100` measured as +183 logical
  px). Needs `sudo ydotoold`; stop it afterwards.
- **Nested testing works, but hover does not survive it.** A nested `kwin_wayland` +
  `qs` receives clicks but never hover events, so hover instrumentation logs nothing and
  reads as "my patch didn't load". The nested kwin also **cannot acquire `org.kde.KWin`**
  on DBus (the outer one holds the name), so Scripting calls always hit the host.
- **`pkill -f "qs -p …/caelestia-kwin"` kills the LIVE session's shell too** — the pattern
  matches both. It happened. Capture the PID. (The supervising loop now resets its retry
  budget after 60 s of uptime, so this can no longer strand the user with a terminal.)
- zsh does not word-split unquoted variables, and unquoted `--include=*.qml` gets
  glob-expanded into "no matches found". Use the Grep tool.

### Already ruled out for "apps open fullscreen then re-shape"

Do not re-investigate these without new evidence:
- **Not crashes** — `coredumpctl` for the window showed only my own three spectacle aborts.
- **Not `luminos-maximize`** — it has never loaded (BUG-117).
- **Not KWin tiling** — the four `[Tiling]` blocks are stock and inert (25/50/25);
  `kwinrulesrc` holds one unrelated Wine rule.
- **Not universal** — a control `kitty` opened at `448,41 594x818`, not fullscreen, not
  tiled, and never moved under a geometry watcher.
- Remaining hypothesis: **per-app state restore** — a window that was fullscreen or tiled
  under Hyprland asking for that shape back.

---

## Files touched / relevant files

| Path | Role |
|---|---|
| `scripts/luminos-caelestia-kwin-session` | installs / checks / uninstalls the greeter session |
| `scripts/luminos-caelestia-kwin` | the session itself → `/usr/local/bin` |
| `scripts/luminos-caelestia-kwin-overlay` | builds the symlink+patch overlay; `--check`, `--remove`. **Run with `python3`, it is Python.** |
| `~/.config/quickshell/caelestia-kwin/` | the built overlay (has a `.luminos-overlay` marker) |
| `/etc/xdg/quickshell/caelestia/` | upstream, never edited |
| `~/.local/state/luminos/caelestia-kwin/` | `session.log`, `shell.log`, `kwin-render.log`, `sycoca.log` |
| `docs/BUGS.md` | BUG-112 … BUG-117 |
| `LUMINOS_DECISIONS.md` | DECISION 63 + "the shape every KWin bug has taken" |

The 4 patched files inside the overlay: `modules/drawers/ContentWindow.qml`,
`modules/drawers/Interactions.qml`, `services/Brightness.qml`, `services/ShellState.qml`.

---

## Standing repo rules (carried forward — still true)

- **Never `git add -A`.** That is how an API key got published, and the tree still holds
  parked work that must not ride along: `_to_delete/`, `reference_code/`,
  `scripts/jobhunt/moe-server.py`, `switch-to-old-claude.sh`, `fix-claude-legacy.sh`, and
  three dirty `research/turboquant` submodules. **Stage by name.**
- **Luminos helper scripts have a habit of printing success on a failed path**
  (BUG-088, BUG-089). `luminos-brain log` still does it — avoid apostrophes when calling
  it, and verify writes by reading them back.
- **`luminos-brain safe` keyword-matches, it does not reason.** Its NOs are usually false —
  it greps `hive-brain.md`'s own header banner. Check whether the warning is substantive,
  then override with `--reason`. (Open task 0b.)
- **BUG-086 (OpenRouter key) is CLOSED / WONTFIX** — dead account, dropped 2026-07-25.
  Do not re-raise rotation.
- **BUG-080 open** — Wine 11.8→11.13 broke the MT5/forex stack. **Check
  `systemctl is-active forex-bot` before any reboot; it is live trading.**
- **BUG-084 not durably fixed** — DrKonqi's gdb+debuginfod ate 7.4 GB once and will again
  on the next app crash. Needs user go-ahead for a `MemoryMax=` drop-in.
- Under Cowork, **hooks never fire**, so the code graph does not refresh itself. Check
  `list_graph_stats_tool`'s `last_updated` before trusting "this function has no callers".
