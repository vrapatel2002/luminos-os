# SPEC — ChromeOS / Nexus window style for every KWin window
<!-- [CHANGE: claude-code | 2026-10-10] DECISION 138 -->

## What Shawn asked (his words)
"i want this window style for every window in this device currently we are using the kwin windows.
so what we want is to find a way to make kwin to exactly look like that … use the code from chromeOS"
Reference: screenshot of Caelestia **Nexus** → Connected devices page.
Clarified 2026-10-10 (Response 1): **both** the frame and the insides; **all KDE/Qt apps**.
Chrome / Electron / GTK insides are out of scope (the app draws them, KWin cannot).

## Assumptions (gaps filled)
1. Frame is a **new KDecoration3 plugin of our own** (`org.kde.luminos.chromeos`), with ChromeOS's
   constants from Chromium source (BSD-3, credited). Not Klassy: Shawn asked for ChromeOS code, and an
   own plugin has no upstream feature churn. Same rebuild-on-Plasma-bump risk as any decoration.
2. Corner radius **16** logical px (Caelestia `large`; ChromeOS is 12). One config key, `luminos-chromeosrc [Frame] CornerRadius`.
3. Header **40 px**, painted in the **window's own palette `QPalette::Window`** so it is the same colour
   as the body (no visible strip). **No title text, no app icon** by default (Nexus shows none);
   `ShowTitle=false` key. Window title still reaches the taskbar/alt-tab, which is where it is read.
4. Buttons right-aligned: minimize, maximize/restore, close. Each 36×40, close has +8 trailing pad.
   Icons 16 px line glyphs in the window foreground colour; inactive window → icons at 38 % alpha.
   Hover = filled circle r=14, white 8 % (pressed 14 %). Close hover = same circle (ChromeOS has no red).
5. Maximized / tiled → radius 0, no shadow edge rounding.
6. Shadow: ChromeOS elevation 24 active / 12 inactive: key `0 e e black 20 %` + ambient `0 0 e black 10 %`.
7. Border: no visible border; ChromeOS highlight rings — outer 1 px black 8 %, inner 1 px white 6 %, following the radius.
8. Resize: 6 px outside the window (`setResizeOnlyBorders`), borders `NoBorders`.
9. Insides for QtWidgets apps: **Darkly** widget style (AUR, Breeze fork) at CornerRadius 16, colours stay
   `Caelestia.colors` (Darkly must not override the scheme).
10. Insides for Kirigami apps: DECISION 72's patched Kirigami **silently reverted** when kirigami went
    6.28 → 6.30 (installed is stock `6.30.0-1`; `/etc/environment` still sets KIRIGAMI_* and does nothing).
    Rebuild the patch for 6.30 and add a pacman hook that warns when stock kirigami replaces it.
11. Rounded-corners effect (`kwin4_effect_shapecorners`) stays **disabled** — KDecoration3 `setBorderRadius`
    clips the client in KWin 6.7, so the effect is not needed.
12. Everything is reversible by one script: `luminos-windowstyle revert` restores the backed-up
    kwinrc / kdeglobals / darklyrc and stock decoration (Breeze).

## Blind spots → decisions
- Plugin fails to load → KWin falls back to Breeze silently. Checker reads KWin's own supportInformation.
- Plasma/kdecoration version bump → plugin ABI break. Built as a pacman package in `packages/`, so
  `pacman -Q` shows it; hook prints a warning on kdecoration/kwin upgrade.
- Apps with client-side decorations (Chrome, Electron, GTK CSD) → untouched; KWin does not decorate them.
- Very light app palettes → icons use the app's own foreground, so contrast follows the app.
- Fullscreen → no decoration (KWin default).
- HiDPI 2× → all sizes in logical px; KDecoration scales.
- Dialogs/transients → same frame.

## Done means
- Every KDE window (System Settings, Dolphin, Kate/KWrite, Konsole) shows: rounded 16 px corners top and
  bottom, no visible titlebar strip, three small round-hover buttons top-right, soft shadow.
- Their insides: rounded (16) text fields/buttons/frames from Darkly; Kirigami rows/radius bigger again.
- `scripts/luminos-windowstyle-check` exits 0, including pixel probes on a **real screenshot** of the live desktop.
- `luminos-windowstyle revert` puts the old look back, proven once.
