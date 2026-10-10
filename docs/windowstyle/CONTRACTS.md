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
