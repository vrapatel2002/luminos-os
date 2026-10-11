# SPEC — Luminos Ambient (lightweight YouTube glow)
# [CHANGE: claude-code | 2026-10-11]

## What Shawn asked for, in his words
"investigate the extension, it's the one I am sure, the blur effect may be spiking heat. We need to write
better code to avoid the heat. Debug it, find loose-end code and heavy code."

Two deliverables:
1. **AUDIT** of the installed "Ambient light for YouTube™" 2.38.17 (Wessel Kroos, GPL-3, ID
   `paponcgjfojgemddooebbgniglhkajkj`). Lists the heavy code paths and the loose ends, with line numbers
   and Shawn's actual settings (blur2 44.3, spread 76.2, edge 17; everything else default). → `AUDIT.md`
2. **Luminos Ambient**: our own small Chrome extension. It draws the same kind of coloured glow around
   the YouTube player for a fraction of the CPU/GPU cost. Code in `scripts/chrome-luminos-ambient/`, tests in
   `tests/ambient/`.

## Why the original is heavy (measured 2026-10-11, see BUILD_LOG)
YouTube tab with the extension on: renderer 45 % + GPU process 39 % of a core while playing; PPT 7–14 W
vs 6 W idle. Per video frame (up to 60/s) it does a full-size drawImage into a 2× buffer, a WebGL texture
upload + generateMipmap, renders N layers (N = spread/edge + …, ≈6 with Shawn's settings), then
re-blurs the whole result through a Canvas2D `filter: blur()` whose radius and canvas size grow with spread.

## How ours stays cheap (the design rules — these are the point of the build)
- **Tiny canvases only.** Every canvas we draw to per tick is ≤ 64×64 px. The browser stretches the
  result to full size with ordinary image smoothing. A stretched tiny image is already soft, so the
  blur is nearly free.
- **Low, fixed tick rate.** Default 6 updates/s (`fps` setting, 1–30). Ambient colour does not need
  60 fps. Changes are smoothed by blending each new sample over the last one (time constant 300 ms),
  so the glow never flickers.
- **No WebGL, no readback in the tick, no CSS `filter`, no `requestAnimationFrame` loop,
  no MutationObserver.** A `setTimeout` chain that only exists while the glow should be running.
- **Fully idle when it should be.** No timer runs when: disabled, video paused/ended, tab hidden,
  document fullscreen, player scrolled off-screen, or no video. Resumes from events
  (`play`, `visibilitychange`, `fullscreenchange`, IntersectionObserver, storage change).
- **Positioned in page coordinates** (absolute, top = rect.top + scrollY), so scrolling needs no work.
  Rect is re-read once per tick; styles are written only when the rect actually changed.

## Assumptions (gaps filled with a default)
- A1 Only `https://www.youtube.com/*`; excludes `/live_chat*` and `/embed/*` (Shawn watches on the site).
- A2 Settings: `enabled` (true), `spread` (% of video size added on each side, 0–60, default 30),
  `fps` (1–30, default 6 — re-plan 2026-10-11 after benchmark: 12 added +4.7 % of a core, 6 is inside the noise), `intensity` (glow opacity %, 0–100, default 80). Stored in
  `chrome.storage.local`, applied live without reload. Popup with a toggle + 3 sliders.
- A3 YouTube paints opaque page backgrounds. While the glow is active the extension adds the class
  `luminos-ambient-on` to `<html>`, and one injected stylesheet makes the watch-page wrappers
  transparent. Removing the class restores YouTube exactly.
- A4 Glow sits behind page content (z-index −1 in the root stacking context) and has
  `pointer-events: none`. It never covers text or controls.
- A5 Theater / default view are supported. Fullscreen: glow off (nothing to show around a full screen).
- A6 Only one video at a time: the most recently `play`ed `<video>` (captured at document level).
  Mini-player and hover previews on the home page are ignored (previews are muted `ytd-video-preview`
  videos and are excluded by requiring the video to be inside `#movie_player`).
- A7 Coexistence: Ambient light for YouTube stays installed but must be **disabled by Shawn** when ours is
  on, or both draw. Ours does not detect or fight the other one.
- A8 Install path is "Load unpacked" from the repo folder (same as Luminos Tab Sleeper). Chrome 137+
  ignores `--load-extension`, so that one click is Shawn's.

## Blind spots, decided
- SPA navigation (YouTube never reloads): handled by the capture-phase `play` listener; a new video
  re-attaches, the old one is released.
- Video element reused with a new src or a resolution change: sample size is recomputed when
  `videoWidth/videoHeight` change.
- `videoWidth` is 0 before metadata: shouldRun is false and nothing is drawn.
- Cross-origin taint: we never read pixels in the tick, so a tainted frame cannot throw there. A
  drawImage exception is caught once, the glow is turned off for that video, and a single
  console.warn is logged.
- Rapid setting changes / slider drag: settings are clamped, and the timer is rescheduled once (never two
  chains: a single `timer` handle is guarded).
- Restart / extension reload: all state is in the content script, no background worker.
  An orphaned canvas from a previous injection is removed on start (found by id).
- Huge or odd aspect videos (vertical shorts 9:16, 32:9): sample size keeps aspect, long side fixed.
- Dark/light theme: glow drawn the same; the light theme just shows it less.

## Done means
1. Unit + property tests pass (`node --test tests/ambient/*.test.js` — node 22 cannot take the bare directory).
2. Budgets hold: each file ≤ 150 lines, all code ≤ 400 lines, functions ≤ 40 lines, nesting ≤ 3,
   no dependencies.
3. **Benchmark on the G14** (real YouTube, same video, fresh Chromium profile, muted, 20 s warm-up,
   30 s window, renderer+GPU+browser CPU summed from /proc). Thresholds **fixed now, before any run**:
   - T1 Luminos Ambient's *added* CPU (vs. no extension) ≤ **25 %** of Ambient light's added CPU
     (Ambient light running with Shawn's exact stored settings).
   - T2 Luminos Ambient's added CPU ≤ **8 % of one core**.
   - T3 The glow is really drawn: our canvas is in the DOM, visible, larger than the video rect, and
     its tick counter advances while playing.
   - T4 Pausing stops it: the tick counter does not advance for 2 s while paused.
4. A screenshot of each (Ambient light vs. ours) is saved for Shawn to judge the look.
5. AUDIT.md lists the heavy paths and loose ends with line numbers.
