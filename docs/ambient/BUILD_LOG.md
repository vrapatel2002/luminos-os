# BUILD_LOG — Luminos Ambient
# [CHANGE: claude-code | 2026-10-11]

- 18:01 Measured: hot hour (52–61 °C) = YouTube in Chrome. Tab renderer 45 % + GPU proc 39 % of a core
  while playing, PPT 7–14 W vs 6 W idle. Extension processes ~0 CPU; the work runs inside the tab.
- 18:27 Shawn: it's the Ambient light extension, write better code, audit heavy + loose-end code.
- Read upstream content-main.js (13,462 lines, not minified). Shawn's stored settings: blur2 44.3,
  spread 76.2, edge 17. Layers = max(2, round(spread/edge) + innerStrength + 1) → ~6 vs 2 at defaults.
- Decision: write our own small extension instead of forking 13k lines. A GPL fork would be ours to
  maintain forever; a 300-line extension that does the one thing he uses is easier to own.
- Decision: benchmark in a throwaway Chromium profile (`--load-extension` still works in unbranded
  Chromium 153), muted, never in Shawn's Chrome. Probe at 18:30: extension loads under its real ID.
- Thresholds T1–T4 written into SPEC.md before any benchmark run.
- Workers (all Opus, high): auditor → AUDIT.md; implementer → scripts/chrome-luminos-ambient/ (293 lines);
  test writer → tests/ambient/ (72 tests incl. 600-case property tests, budget scanner, fake-DOM run of
  content.js). File boundaries held: implementer never touched tests/, tester never touched scripts/.
- First test run 71/72: real bug, sampleSize overflowed to Infinity for absurd sizes (L*short before /long).
  Sent back to implementer, fixed (divide first). 72/72.
- `node --test tests/ambient/` does not work on node 22 (directory treated as a module) → command is
  `node --test tests/ambient/*.test.js`; SPEC updated.
- Real-browser smoke run: glow canvas 64×36 stretched to 1731×974, ~11 ticks/s, pause froze ticks and hid it.
  First screenshot showed no visible glow → probed: every YouTube wrapper is transparent, html paints
  rgb(15,15,15), canvas pixels are non-empty; the frame was simply dark. Second screenshot on a bright frame
  shows the teal glow under the masthead, left edge and behind the title. Works.
- Benchmark run 1 (1600×1000 window): baseline 29.8 % of a core, Ambient light 43.7 (clean run; the other
  run was an unskippable ad and is void), ours 39.1–40.8 → ours added ~10 %, over T2 (8 %). Most of it in the
  page renderer. Also: power readings are polluted, because the worker VM runs on the same laptop.
- Independent reviewer (Fable): 8 findings. Real bugs: glow keeps ticking after the extension is disabled
  (orphaned content script), one draw error disables it for the whole tab (YouTube reuses the <video>),
  glow runs in the mini-player on non-watch pages. Perf: tiny canvas not on its own compositor layer, so
  each tick repaints its stretched viewport-sized rect → added will-change:transform; ctx.filter was re-set
  every tick → moved to resize. All fixed by the implementer; tester added 8 tests that fail on the old code
  and pass on the new (80/80).
- Benchmark run 2: window maximized like Shawn's Chrome, any run that sees an ad is redone (max 3).
- Run 2 (maximized, ad runs redone): plain 33.4/39.1, Ambient light 51.6/57.5 (+18.3), ours@12/s 41.9/40.0
  (+4.7) → T2 pass, T1 narrow fail (26 % vs 25 %). Threshold kept, not loosened.
- Re-plan: default fps 12 → 6 (SPEC + CONTRACTS updated; implementer changed one line; tester updated defaults,
  80/80). Run 3: plain 41.2/39.2/39.9 (40.1), ours@6/s 40.1/36.9/37.3 (38.1) → no measurable cost.
  T1–T4 pass. Pause froze ticks in every run.
- Look: screenshots in bench/run2-maximized. Ours is softer and greyer than Ambient light at spread 76; it does
  not fill the page behind the sidebar. That's the price; spread/intensity sliders in the popup.
- Strip-down pass: nothing left to delete. content.js is at 150/150 lines and every line traces to SPEC or a
  review fix. Total 295/400.
- NOT done here: installing into Shawn's Chrome (Load unpacked is his click), and a measurement inside his real
  Chrome 150 profile. The benchmark used Chromium 153 with a fresh profile.
