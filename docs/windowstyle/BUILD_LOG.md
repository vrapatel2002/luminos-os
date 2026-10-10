# BUILD_LOG — windowstyle (DECISION 138)
<!-- [CHANGE: claude-code | 2026-10-10] -->
- 17:50 Asked Shawn which part (history: DECISION 71/72). Answer: both, all KDE/Qt apps.
- Research (2 Opus agents): Chromium frame constants; KWin 6.7 options. Key find: KDecoration3 `setBorderRadius` rounds the client, so no effect plugin needed.
- Found BUG-193: patched Kirigami silently reverted by 6.30.
- Workers (Opus high): frame plugin; Darkly + Kirigami + `luminos-windowstyle`; test writer → checker. All in parallel, file boundaries respected.
- Checker: 3/11 before, 11/11 after.
- Reviewer (Fable high): 8 findings — null deref in button factory (crash), revert restoring whole files (wrong behaviour), clip idiom, font repaint, header floor, --notify, env word-splitting, unpinned patch checksum. All fixed; checker 11/11 again.
- Budgets: plugin 496/500, windowstyle 146/150, checker 200/200.
