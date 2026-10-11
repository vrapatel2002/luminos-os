# CONTRACTS — Luminos Ambient (frozen; change only by re-plan)
# [CHANGE: claude-code | 2026-10-11]

## Files and owners
| Path | Owner | Notes |
|---|---|---|
| scripts/chrome-luminos-ambient/manifest.json | implementer | MV3, permissions: ["storage"] only |
| scripts/chrome-luminos-ambient/core.js | implementer | pure functions, no DOM, no chrome.* |
| scripts/chrome-luminos-ambient/content.js | implementer | DOM glue; loaded after core.js |
| scripts/chrome-luminos-ambient/popup.html, popup.js | implementer | toggle + 3 sliders |
| tests/ambient/*.test.js | test writer | `node --test tests/ambient/` |
| tests/ambient/bench.mjs | PM | real-browser benchmark (CDP over node's built-in WebSocket) |

## core.js export
Defines `globalThis.LuminosAmbientCore` and, when `module` exists, `module.exports` = the same object
(CommonJS, so tests use `require`). Exactly these functions:

- `clampSettings(raw)` → `{enabled:boolean, spread:int, fps:int, intensity:int}`
  defaults `{enabled:true, spread:30, fps:6, intensity:80}` (fps was 12; changed by re-plan after the benchmark); spread clamped 0..60, fps 1..30,
  intensity 0..100; non-numeric / NaN / missing → default; numbers rounded to int;
  enabled is `raw.enabled !== false`. `raw` may be null/undefined/non-object → all defaults.
- `sampleSize(videoW, videoH, longSide = 16)` → `{w, h}` ints, or `null` if either input is not a
  finite number > 0. The longer side equals `longSide`; the other is `max(1, round(longSide*short/long))`.
- `glowRect(rect, spread)` → `{left, top, width, height}`. `s = clamp(spread,0,60)/100`;
  width = rect.width*(1+2s), height = rect.height*(1+2s), same centre as rect.
- `frameDelay(fps)` → `Math.round(1000 / clamp(fps, 1, 30))`; non-finite fps → 83 (≈12 fps).
- `blendAlpha(dtMs, tauMs = 300)` → `tauMs <= 0 ? 1 : clamp(1 - Math.exp(-dtMs / tauMs), 0.05, 1)`;
  non-finite or negative dt → 0.05.
- `shouldRun(s)` with `s = {enabled, paused, ended, hidden, fullscreen, onScreen, videoW}` →
  `enabled && !paused && !ended && !hidden && !fullscreen && onScreen && videoW > 0` (strict boolean).
- `rectChanged(a, b, eps = 0.5)` → true if either is null/undefined, or any of left/top/width/height
  differs by more than eps.

## content.js — observable contract (what the benchmark and tests can see)
- One display element `<canvas id="luminos-ambient-glow">` appended to `document.body`, style
  `position:absolute; z-index:-1; pointer-events:none`, placed at `glowRect(videoRect, spread)` in page
  coordinates (top/left include scrollY/scrollX). `opacity` = intensity/100.
- `canvas.dataset.ticks` = integer tick counter as a string, incremented once per drawn tick.
- `<html>` has class `luminos-ambient-on` exactly while a glow is shown; `display:none` on the canvas
  otherwise.
- Per tick work only on canvases with both sides ≤ 64 px. No WebGL, no getImageData/readPixels,
  no CSS filter, no requestAnimationFrame, no MutationObserver, no setInterval.
- One `setTimeout` handle at most; the chain exists only while `shouldRun` is true.

## Settings storage
`chrome.storage.local` key `luminosAmbient` → raw object passed through `clampSettings`.
content.js listens to `chrome.storage.onChanged` and applies changes live.

## Budgets
Each file ≤ 150 lines; all extension code ≤ 400 lines; function ≤ 40 lines; nesting ≤ 3;
no dependencies (tests: node built-ins only, property tests via a seeded PRNG loop, ≥ 500 cases each).
