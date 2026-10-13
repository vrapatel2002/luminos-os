# CONTRACTS — windowstyle build (frozen 2026-10-10)
<!-- [CHANGE: claude-code | 2026-10-10] -->

## Files and owners
| Path | Owner | Notes |
|---|---|---|
| `src/kdecoration-chromeos/` (CMakeLists.txt, *.cpp, *.h, metadata.json) | frame implementer | C++20, KDecoration3 + Qt6 only |
| `packages/luminos-kdecoration-chromeos/PKGBUILD` | frame implementer | builds from repo path, installs plugin to `/usr/lib/qt6/plugins/org.kde.kdecoration3/` |
| `packages/kirigami-luminos/` (PKGBUILD, patch), `/etc/pacman.d/hooks/luminos-kirigami.hook` | insides implementer | rebuild for 6.30 |
| `scripts/luminos-windowstyle` (apply / revert / status) | insides implementer | the only thing that writes kwinrc, kdeglobals, darklyrc |
| `scripts/luminos-windowstyle-check`, `tests/windowstyle/*` | test writer ONLY | implementers never edit |
| `docs/windowstyle/{SPEC,CONTRACTS,BUILD_LOG}.md` | PM | |

## Plugin identity
- Plugin id / metadata `KPlugin.Id`: `org.kde.luminos.chromeos`; library file `org.kde.luminos.chromeos.so`.
- kwinrc: `[org.kde.kdecoration2] library=org.kde.luminos.chromeos`, `theme=` (empty), `BorderSize=None`, `BorderSizeAuto=false`.
- Config file `~/.config/luminos-chromeosrc`, group `[Frame]`: `CornerRadius=16` (int 0–32), `HeaderHeight=40`, `ShowTitle=false`.
  Missing/garbage values fall back to these defaults.

## Frame constants (logical px, from Chromium — cite file in a comment)
HeaderHeight 40 · ButtonW 36 · ButtonH 40 · CloseTrailingPad 8 · IconSize 16 · HoverCircleR 14 ·
HoverAlpha 0x14 (8 %) · PressedAlpha 0x24 (14 %) · InactiveIconAlpha 0.38 · ResizeOutside 6 ·
ShadowActive e=24 · ShadowInactive e=12 · key `0 e e #000 20 %` · ambient `0 0 e #000 10 %` ·
Ring outer 1px #000 8 % · Ring inner 1px #fff 6 % · Radius 0 when maximized or tiled.
Header colour = `window()->palette().color(QPalette::Window)`; icon colour = `QPalette::WindowText`.

## Insides
- `kdeglobals [KDE] widgetStyle=Darkly`; `~/.config/darklyrc` `CornerRadius=16`; Darkly must not change `ColorScheme` (stays `Caelestia`).
- Kirigami patched build: `pkgver=6.30.0`, `pkgrel=1.1`; `Kirigami.Units.cornerRadius` == 16 with `/etc/environment` as today.

## Checker interface
`scripts/luminos-windowstyle-check [--no-screenshot]` → prints one `PASS|FAIL <name>: <detail>` per check, exit 0 iff all pass.
Needs on the G14: `XDG_RUNTIME_DIR=/run/user/1000`, `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`, `WAYLAND_DISPLAY=wayland-0`.

## Budgets
Decoration plugin ≤ 500 lines total, any file ≤ 250, function ≤ 40, nesting ≤ 3. `luminos-windowstyle` ≤ 150. Checker ≤ 200.
Deps: kdecoration, Qt6, KF6 already installed + AUR `darkly`. Nothing else.

## Machine rules (all workers)
- The G14 is reached ONLY through `mcp__remote-devices__host-shell__run_command`. `device_bash` is a different VM — never use it.
- Session env for anything touching the desktop: `export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus WAYLAND_DISPLAY=wayland-0`.
- Each host-shell call must finish well under 60 s; run long builds detached with `systemd-run --user --unit=<name>` and poll.
- Identity tag `[CHANGE: claude-code | 2026-10-10]` on every file/block written. Back up any config before writing it to `~/.local/share/luminos-kde-backup/pre-windowstyle-20261010/`.
- Before any package action: `~/luminos-os/scripts/luminos-brain safe "<action>"`; known false NO → `--reason "<why>"`.
- Never `pkill -f` broad patterns, never `git add -A`, never `swapoff`, never run `nvidia-smi`/`lspci`. Do not commit — PM commits.
- Restart KWin's decoration via `qdbus6 org.kde.KWin /KWin reconfigure` — **never** `kwin_wayland --replace` (kills the session).

---
## Phase 2 contracts (frozen 2026-10-10 22:00)
| Path | Owner |
|---|---|
| `packages/ttf-google-sans-flex/PKGBUILD` (if no sane AUR pkg), `scripts/luminos-kde-caelestia-theme`, `scripts/luminos-ubuntu-look` font lines | font+colour worker |
| `packages/qqc2-desktop-style-luminos/` (PKGBUILD + patch), `config/pacman-hooks/luminos-qqc2.hook` | switch worker |
| icon theme package/choice, `scripts/luminos-ubuntu-look` icon lines, `scripts/luminos-windowstyle` managed-key list (add icon key) | icon worker |
| `scripts/luminos-windowstyle-check`, `tests/windowstyle/*` | test writer only |
Two workers touch `luminos-ubuntu-look`: font worker owns FONT lines, icon worker owns ICON lines — edit only your lines, re-read the file right before editing.
Checker budget raised to **320 lines** (bash + helpers). Patch packages: pkgrel `<n>.1`, hook warns when stock replaces them.

---
## Phase 3 contracts (frozen 2026-10-11 18:40)
| Path | Owner |
|---|---|
| `packages/qqc2-desktop-style-luminos/` (new patch file `qqc2-luminos-nexus-rows.patch`, pkgrel 1.3) | qqc2 worker |
| `packages/kirigami-luminos/` (add `kirigami-luminos-icondisc.patch`, pkgrel 1.2), `packages/kirigami-addons-luminos/` (+hook) | kirigami worker |
| `packages/systemsettings-luminos/` (+hook) | systemsettings worker |
| `packages/darkly-luminos/` (+hook) | darkly worker |
| `scripts/luminos-windowstyle-check`, `tests/windowstyle/*` | test writer only (budget raised to 450 lines) |
Shared rules: one hook per fork in `config/pacman-hooks/luminos-<pkg>.hook` (warn when pkgrel loses `.N`, exit 0).
Patches pinned by sha256. Colours ONLY from the palette/Kirigami.Theme (never hex in QML) — they already map to
Caelestia (Window #1c1b1f, View #131317, Alternate #201f23, Button #2a292e, Selection #45455c, Highlight/focus #c2c1ff).
Token numbers (logical px): 4 / 12 / 16 / 28 / 32 radii; 2 px row inset; 4 px group gap; animation 350–500 ms.
Reference mock: `docs/windowstyle/mock/nexus-replica.html` (CSS = ground truth for sizes).

---
## Phase 6 contracts (frozen 2026-10-12 21:45) — target `docs/windowstyle/mock/popups.html` (approved)
| Piece | Owner | Where |
|---|---|---|
| Dolphin details/icons (BUG-196), QtWidgets menus, tooltips, scroll bars | darkly worker (new) | `packages/darkly-luminos` pkgrel 1.3 |
| QML Menu/MenuItem, ToolTip, ScrollBar | qqc2 worker | qqc2 fork pkgrel 1.7 |
| InlineMessage (4 tones), PlaceholderMessage look | kirigami worker | kirigami fork pkgrel 1.7 |
| Keyboard Layouts empty states (text + Turn on / Add layout) | kirigami worker | new `packages/plasma-desktop-luminos` (kcm_keyboard QML only) |
| Checks | test writer | checker (budget 700 lines) |
Numbers (logical px): menu r16 on #2a292e, 6 padding, items 40 tall r10, icon left, shortcut right in outline colour, separators 1 px outline-variant inset 10, danger = error colour; tooltip inverse surface r8 12.5 px, delay 500 ms, fade 120 ms; rich tooltip r12 on #353438; scroll bar: no track/arrows, 4 px pill at 45 % outline, 8 px at 75 % on hover, 4 px inset from edge; info bar r16, 4 tones (info=Selection colours; positive/warning/error from the colour scheme's Positive/Neutral/Negative backgrounds), leading icon, one text action, round close; Dolphin header on page colour, 12.5 px, no band/lines, sorted column brighter; rows 44 px r12 full width, selection one #45455c pill across all columns, hover 8 %; group labels grey; tree: chevrons only, no lines; icon tiles r16. Motion 180 ms / 120 ms, no overshoot. No new processes.
