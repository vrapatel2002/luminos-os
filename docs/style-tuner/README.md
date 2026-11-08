# Style Tuner (DECISION 176)
<!-- [CHANGE: claude-code | 2026-11-08] -->
Open **Style Tuner** from the app menu (or run `luminos-style-tuner`). Move a bar: open KDE apps change right away.

| Piece | Where |
|---|---|
| Values file | `~/.config/luminos/style.json` (delete it = stock look) |
| Live module | `org.luminos.style` → `src/luminos-style/style.{h,cpp}`, package `packages/luminos-style` |
| Tuner window | `src/luminos-style/tuner/StyleTuner.qml`, launcher `luminos-style-tuner` |
| Fonts + Darkly corners | `luminos-style-apply` via user unit `luminos-style-apply.path` |
| Fork patches | `packages/*-luminos/*-tunables.patch`, made by `scripts/style-tuner/make-tunables.py` |
| Proof shots | `shots/1-default.png`, `2-tuned.png`, `3-back.png` (System Settings never restarted), `t1/t2` (font live) |

Keys (default): textSizePt 10, pageTitlePx 30, groupLabelPx 12, cornerOuterPx 28, cornerInnerPx 4, cornerButtonPx 16,
rowHeightPx 60, rowGapPx 4, cardPaddingPx 20, sidebarWidthPx 330, pageWidthPx 756, iconCirclePx 40, animationMs 180,
sidebarBottomPx 16, searchHeightPx 48, searchLeftPx 16, searchRightPx 16, searchTopPx 16, searchBottomPx 8,
iconDiscColor "" / iconGlyphColor "" ("" = theme, else "#rrggbb"), iconGlyphPx 22, iconOffsetXPx 0, iconOffsetYPx 0,
buttonsLeftPx/RightPx/TopPx/BottomPx 6 (System Settings C++ only; live via its own file watcher).
Isolated test recipe (does not touch the real desktop): `~/builds/style-tuner/nested-test.sh` pattern — dbus-run-session +
`kwin_wayland --virtual` + private XDG_CONFIG_HOME + `spectacle -b -n -f`.

Rebuilding a fork after an upstream bump: apply its own patches, then the tunables patch last. If the tunables patch no
longer applies, regenerate it: `makepkg -o` (without the tunables line), then
`python3 scripts/style-tuner/make-tunables.py <pkg> <src-tree> <out.patch>` — it stops on any rule that no longer matches.
