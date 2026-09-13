# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-03 — Response 2

## Goal (the durable end objective)
Make native KDE/Qt windows on Luminos look like Caelestia's **Nexus** settings window —
the **inside** of the window (rows, cards, sub-sections), not the window frame.

## Aim right now (this can differ from the first prompt — keep it current)
Working in order: **shape → size → the rest.** Shape is done and proven live.
Size (row height, padding, the 2px gap that makes a group read as one card) is next
and has NOT been started.

## Why / motivation (context a newcomer would be missing)
Third attempt. DECISION 71 rounded the window **frame** and was rejected —
*"what i mean by windows look alike was inside design not the out side keep it default
try making sound and other sub section rectangle look like the ones from nexus."*
DECISION 72 went after the inside via a patched Kirigami and is still live, but it set
a **uniform 16** on all four corners of every row, which is a different shape from
Nexus's asymmetric connected group, not a smaller version of it.

## Process / approach being used
A **QtQuick Controls style module**, `org.luminos.style`. It is plain QML on disk,
selected by one environment variable, and changes every Qt Quick app at once with
**zero package rebuilds**. Opposite of DECISION 72's approach (fork + rebuild Kirigami),
and it can be tested on a single app launch without touching the live desktop.

## State — what is DONE
- **Nexus opened as the live reference** (no new process, no config edits):
  `WAYLAND_DISPLAY=wayland-0 qs -p ~/.config/quickshell/caelestia-bar ipc call nexus open`
- **DECISION 72 confirmed still live:** `kirigami 6.28.0-1.1` + `/etc/environment` lines
  52–54 (`KIRIGAMI_CORNER_RADIUS=16`, `MEDIUM_SPACING=12`, `SMALL_SPACING=6`).
- **`org.luminos.style` built and proven working** on System Settings. Sidebar rows now
  draw as filled slabs with Nexus's per-corner radii, and every other control still
  renders as stock Breeze.
- **Nothing persisted.** `/etc/environment` has no style variable, there is no
  `~/.config/qtquickcontrols2.conf`. The style only applies to a launch that sets the
  env vars by hand. Reverting is "do nothing".

## State — what is IN PROGRESS (and where exactly it was left off)
Shape landed but the group does **not** visually connect yet. Every sidebar row currently
draws with the **inner** radius (4) on all four corners because with KDE's stock row
spacing each row is separated by padding, so a run of rows reads as separate slabs rather
than one sliced card. Closing that gap is a **size** change (step 2), not a shape one, and
was deliberately not started.

### Nexus row anatomy — measured from source, not guessed
Files: `reference_code/caelestia-shell-2.2.0/modules/nexus/common/`

| Part | Source | Value |
|---|---|---|
| Row background | `ConnectedRect.qml` | `m3surfaceContainer` |
| Corner, group **outer** edge | `ConnectedRect.qml:11-14` | `rounding.extraLarge` = **28** |
| Corner, group **inner** edge | same | `rounding.extraSmall` = **4** |
| Gap between rows in a group | `pages/AudioPage.qml:20` | `spacing.extraSmall / 2` = **2** |
| Row vertical padding | `NavRow.qml:30` | `padding.medium` = **12** |
| Row left/right padding | `NavRow.qml:31-32` | `padding.largeIncreased` = **20** |
| Icon | `NavRow.qml:39` | `font.icon.medium` = 18px Material Symbols Rounded |
| Title | `NavRow.qml:50` | `body.small` = 12px / 400 |
| Subtitle | `NavRow.qml:60-61` | `label.small` = 11px / 400, colour `m3outline` |
| Gap between sections | `PageBase.qml:23` | `spacing.extraLargeIncreased` = **32** |
| Page title | `PageBase.qml:55` | `title.large` = 22px / 500 |
| Button radius | `components/controls/ButtonBase.qml` | 16 default · 8 pressed · 12 checked · h/2 round |

## Next steps (ordered)
1. **Step 2 — size.** Give the rows Nexus's geometry so the group actually connects:
   vertical padding 12, horizontal 20, and a 2px gap between rows instead of KDE's
   inset-based spacing. This is where `isFirst`/`isLast` start to be visible.
2. Decide whether DECISION 72's `/etc/environment` Kirigami knobs should be reduced or
   removed once the style module carries the same information — right now two mechanisms
   are shaping the same rows and they disagree (uniform 16 vs 28/4).
3. Only after both look right: pick how the style gets turned on permanently
   (a `~/.config/plasma-workspace/env/` script is the reversible option) and write the
   DECISION + AGENTS.md §9 row. **Not before Shawn has looked at it.**

## Key decisions & constraints so far
- Order is **shape → size → more**, one change at a time, looked at before the next.
- The **inside** of the window is the target; the frame stays default (DECISION 72).
- Desktop-wide by design — *"it either every window changes (originally what i wanted)
  or every thing breaks."*
- Colour is deliberately untouched: DECISION 72 measured that KDE and Caelestia already
  use the same selected-row recipe (30% accent tint).

## Gotchas / dead-ends / things NOT to redo
- **A partial QQC2 style is not viable.** `QT_QUICK_CONTROLS_FALLBACK_STYLE=org.kde.desktop`
  is **silently ignored** — Qt only accepts built-in styles there — so every control the
  style does not define falls back to **Basic**. Symptom: the app turns light grey with
  generic spinbox arrows and round slider handles, and reports no error. Fix already in
  place: `scripts/luminos-qml-style-build` symlinks all 51 upstream controls into the
  module so only real overrides differ.
- **QML errors on this box go to the JOURNAL, not stderr.** `qml6` prints only
  `Did not load any objects, exiting.` — even for a deliberately broken file. Use
  `journalctl --user --since "1 min ago" | grep -i qml`. This cost a `systemsettings`
  core dump before it was noticed.
- **Inside a style module, unqualified type names resolve against that module's own
  qmldir first.** Copying upstream's `Label { }` into a partial style gives
  `Label is not a type`. Qualify it (`QQC2.Label`) or declare the type.
- **Do not re-round the window frame** — tried and rejected (DECISION 71).
- **Do not edit Kirigami / kirigami-addons / org.kde.desktop `.qml` files on disk** —
  their `qmldir` carries `prefer :/qt/qml/...`, so the loaded copy is inside the `.so`.
  Editing changes nothing and reports nothing. Our module has no `prefer`, on purpose.
- **The Sound page is QML but compiled into `kcm_pulseaudio.so`** (Kirigami + QQC2, no
  `formcard`). Its layout has **no cards at all** — only section headings and rule lines.
  A style can restyle its *controls*, but nothing short of rebuilding `plasma-pa` can add
  grouped cards to that page. Same for `systemsettings`, which ships zero `.qml`.
- **`qs ipc` needs `WAYLAND_DISPLAY` exported** or it silently finds no instance.
- **A full `pacman -Syu` pulls `kirigami 6.28.0-1.1 → 6.29.0-1`** and silently reverts
  DECISION 72. Still no pacman hook guarding it.
- Re-run `luminos-qml-style-build` after any `qqc2-desktop-style` upgrade — a control
  added upstream will be missing from our module and silently fall back to Basic.

## Files touched / relevant files
**New this session (repo only — nothing installed, nothing in `/etc`):**
- `config/qml/org/luminos/style/ItemDelegate.qml` — the shape override (step 1)
- `config/qml/org/luminos/style/qmldir` — generated
- `config/qml/org/luminos/style/*.qml` — 50 symlinks to `/usr/lib/qt6/qml/org/kde/desktop/`
- `scripts/luminos-qml-style-build` — regenerates the module

**Reference / prior work:**
- `LUMINOS_DECISIONS.md` — DECISION 71 (reverted) line 4338, DECISION 72 line 4445
- `config/kde/caelestia-design-spec.json` — token source of truth
- `reference_code/caelestia-shell-2.2.0/modules/nexus/` — Nexus source
- `packages/kirigami-luminos/` + `/etc/environment` lines 52–54 — DECISION 72, still live
- Screenshots: `/tmp/nexus-open.png` (target), `/tmp/syssettings-audio.png` (before),
  `/tmp/ss-luminos2.png` (after step 1)

**Try it (one app, nothing persisted):**
```bash
QML_IMPORT_PATH=$HOME/luminos-os/config/qml \
QT_QUICK_CONTROLS_STYLE=org.luminos.style systemsettings
```
