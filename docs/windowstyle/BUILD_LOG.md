# BUILD_LOG — windowstyle (DECISION 138)
<!-- [CHANGE: claude-code | 2026-10-10] -->
- 17:50 Asked Shawn which part (history: DECISION 71/72). Answer: both, all KDE/Qt apps.
- Research (2 Opus agents): Chromium frame constants; KWin 6.7 options. Key find: KDecoration3 `setBorderRadius` rounds the client, so no effect plugin needed.
- Found BUG-193: patched Kirigami silently reverted by 6.30.
- Workers (Opus high): frame plugin; Darkly + Kirigami + `luminos-windowstyle`; test writer → checker. All in parallel, file boundaries respected.
- Checker: 3/11 before, 11/11 after.
- Reviewer (Fable high): 8 findings — null deref in button factory (crash), revert restoring whole files (wrong behaviour), clip idiom, font repaint, header floor, --notify, env word-splitting, unpinned patch checksum. All fixed; checker 11/11 again.
- Budgets: plugin 496/500, windowstyle 146/150, checker 200/200.
- 21:50 Shawn: "no where near close" (System Settings vs Nexus). Showed ChromeOS; he picked Nexus + paint fixes.
- Phase 2 workers (Opus high): font+colours, M3 switch (qqc2 patch), mono icons (YAMIS), test writer (+6 checks → 17).
- Tester/implementer disagreement on icons-mono: probe counted Inkscape namedview colours → probe bug, fixed by test writer.
- Reviewer (Fable): 9 findings — login persist dead heal + Yaru colour clobber, ubuntu-look Yaru apply, revert gaps, sudo hang, fc_family crash, thumb jump, maintainer label. All fixed; qqc2 → 1.2; checker accepts -1.N.
- Checker 17/17. Budgets: windowstyle 147/150, checker 320/320.
