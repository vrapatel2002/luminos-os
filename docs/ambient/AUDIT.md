# AUDIT — Ambient light for YouTube™ 2.38.17
# [CHANGE: claude-code | 2026-10-11]

Source audited: `.scratch-ambient/upstream/` (read-only). All line numbers are `scripts/content-main.js` unless another file is named.

## Summary

1. Most of the heat comes from how the extension works, not from your three changed sliders. Every time the video shows a new picture, it copies the whole full-HD picture into the graphics chip, then shrinks it in several steps (lines 9433-9435).
2. Your changes (more spread, more blur, bigger edge) make the glow about 2.6 times bigger on screen in the normal player. They add only about 4% to the copying and shrinking work.
3. A bigger glow can still cost something, because Chrome has to redraw the whole window behind the page every time the glow changes. That is probably where much of the 39% "GPU process" load goes (UNCONFIRMED, not measured).
4. The settings that help most: lower the YouTube video quality (720p cuts the main cost by about 56%), set the frame-rate limit to 15–20, and turn on "Save energy on static videos" for music videos that are a still image. Spread back near 17 helps a little. Blur below 20 makes things worse.
5. Code problems: a timer that takes "frames per second" as milliseconds, a cancel call made with the value `true` where a timer ID belongs, a listener that is never removed, a page-wide watcher that is never switched off, and two leftover pieces from the non-WebGL renderer. None of these is the main cause of the heat.

## Heavy code

### How one ambient frame runs with your settings (webGL=true, frameSync=2, no blending/overlay)

1. `scheduleNextFrame` (12760-12772) calls `scheduleRequestVideoFrame` (11536-11539), which registers `onVideoFrame` with `requestVideoFrameCallback`. With frameSync=2 (FRAMESYNC_VIDEOFRAMES=2, line 6687), a visible video, and no blending, fading or frametimes, it **returns without using requestAnimationFrame** (12763). The loop is therefore driven by **decoded video frames**: 24/25/30/60 per second, depending on the video. It is not driven by the 120 Hz display.
2. `onVideoFrame` (11540-11555) first registers an extra no-op `requestVideoFrameCallback(function prescheduledVFC(){})` (11545). Then it calls `onNextFrame` (11290).
3. `framerateLimit=60` is truthy, so every frame goes through `onNextLimitedFrame` (11312-11332). A video at 60 fps or less is never throttled.
4. `nextFrame` (11353-11400) runs `drawAmbientlight` (12840-13000). For a new frame with no blending, the else-branch (12957-12977) runs:
   - **A.** `projectorBuffer.ctx.drawImage(videoElem, 0,0, w,h)` (12966). The projectorBuffer is a `WebGLOffscreenCanvas` with a fake "2d" context implemented in WebGL (`initProjectorBuffers` 12140-12177, `WebGLContext.drawImage` 9394-9456). It does:
     - `texImage2D(video)` (9433): **a full re-allocation and upload of the whole decoded frame** every frame. It is not `texSubImage2D`.
     - `generateMipmap` (9435): builds the full mip chain of the 1920×1080 texture (about 11 levels).
     - `drawArrays` into the 2p-sized buffer (9439).
   - **B.** `projector.draw(projectorBuffer.elem)` (12970 → `ProjectorWebGL.draw` 8436-8520). This is a second WebGL context. It does:
     - `texSubImage2D` from the other context's OffscreenCanvas (8496): a cross-context copy.
     - `generateMipmap` (8498).
     - `drawArrays` into the projector canvas (8502). The fragment shader `multiTexture` loop (8876-8880) runs about `impreciseI+1` iterations (≤ levels) per pixel, then samples once.
   - **C.** `blurCtx.clearRect` + `blurCtx.drawImage(webglCanvas, …)` (8509, 8514), with `blurCtx.filter = blur(px)` set in `rescale` (9165). This is a **third** GPU context, a Canvas2D, and it applies the Gaussian blur every frame. `blurCanvas` is the only on-screen canvas. It is stretched with a CSS `transform: scale(...)` (9162) to cover the area around the player.
5. After the draw, the page compositor has to re-composite the stretched glow layer. Its on-screen rectangle (below) usually covers the whole viewport.

Three GPU contexts are written every video frame: WebGL #1 (buffer), WebGL #2 (projector), Canvas2D (blur). Each one has its own command stream to Chrome's GPU process. This is consistent with high GPU-process CPU, but the attribution is UNCONFIRMED (not profiled).

### Sizing formulas (exact code)

| Quantity | Line | Formula |
|---|---|---|
| levels | 12268 | `max(2, round(spread/edge) + innerStrength + 1)`, innerStrength = 2 (10933) |
| projector min size | 12430-12432 | `relativeBlur = resolution/100*blur2`; `pMinSize = resolution/100 * (relativeBlur>=20 ? 128 : >=10 ? 192 : 256)` (halved if spread>200) |
| pScale | 12433 | `min(0.5, max(pMin/vw, pMin/vh), min(1024/vw, 1024/vh))` |
| p (projector) | 12438-12441 | `ceil(vw*pScale) × ceil(vh*pScale)`, based on the **video's pixel size, not the player size** |
| projectorBuffer (WebGL2) | 12451-12457 | `2p.w × 2p.h` |
| scale per level | 12666-12688 | `scaleStep = edge/100`; last level `pos = levels-1-2`; `scaleX = 1+scaleStep*pos`, `scaleY = 1+scaleStep*(p.w/p.h)*pos` (ratio 12652-12658) |
| projector WebGL canvas | 9145-9150 | `floor(p.w*scaleX) × floor(p.h*scaleY)` |
| blurPx | 9152 | `blur2 * (p.h/512) * 1.275`, where `this.height` = p.h (set by `resize`, 8664-8667) |
| blurBound | 9154 | `max(1, ceil(blurPx*2.64))` |
| blur canvas | 9151, 9155-9161 | `floor((W+2*bound)/2) × floor((H+2*bound)/2)` (blurCanvasScale = 2 when blur2>1); filter = `blurPx/2` px |
| on-screen glow | 9162 | CSS scale `(scaleX + 2*bound/p.w, scaleY + 2*bound/p.h)` × player size |

Side effect of the formula: spread is rounded to whole multiples of edge. Your 76.2 behaves as `round(76.2/17)=4` × 17 = **68%**. The default 17/12 behaves as `round(1.42)=1` × 12 = **12%**.

### Arithmetic, 1920×1080 video (identical result for a 1280×720 video, because p comes out the same: `ceil(1280*0.17778)=228`)

| | Defaults (blur2 30, spread 17, edge 12) | Yours (blur2 44.3, spread 76.2, edge 17) |
|---|---|---|
| relativeBlur → pMinSize | 30 → 128 | 44.3 → 128 |
| pScale | min(0.5, max(128/1920=0.0667, 128/1080=**0.11852**), 0.533) = 0.11852 | same |
| p | ceil(227.6)=**228 × 128** | **228 × 128** |
| projectorBuffer (2p) | 456 × 256 = 116,736 px | 456 × 256 = 116,736 px |
| levels | max(2, round(1.417)=1 + 3) = **4** | max(2, round(4.482)=4 + 3) = **7** |
| last pos | 4-3 = 1 | 7-3 = 4 |
| scaleX / scaleY | 1+0.12·1 = 1.12 / 1+0.12·1.781·1 = 1.2138 | 1+0.17·4 = 1.68 / 1+0.17·1.781·4 = 2.2113 |
| WebGL canvas | floor(255.4)×floor(155.4) = **255 × 155** = 39,525 px | floor(383.0)×floor(283.0) = **383 × 283** = 108,389 px |
| blurPx | 30·(128/512)·1.275 = **9.56** | 44.3·0.25·1.275 = **14.12** |
| blurBound | ceil(9.56·2.64)=26 | ceil(14.12·2.64)=38 |
| blur canvas | floor(307/2)×floor(207/2) = **153 × 103** = 15,759 px | floor(459/2)×floor(359/2) = **229 × 179** = 40,991 px |
| Canvas2D blur filter radius | 4.78 px | 7.06 px |
| Glow on screen, 1280×720 player | 1280·(1.12+52/228) × 720·(1.2138+52/128) = **1726 × 1166 ≈ 2.01 Mpx** (CSS px) | 1280·(1.68+76/228) × 720·(2.2113+76/128) = **2577 × 2020 ≈ 5.20 Mpx** |
| Glow on screen, theater 1900×1070 | **2561 × 1733 ≈ 4.44 Mpx** | **3825 × 3001 ≈ 11.48 Mpx** |

The on-screen glow is clipped to the window, so the compositor actually redraws at most one viewport. In theater mode both setups already exceed a normal window, so your settings change little there. In the small player, yours fills the window and the defaults may not. The physical pixel count depends on the G14 display scale factor (UNCONFIRMED).

Approximate texture pixels touched per ambient frame. Mip chain is counted as +1/3; blur canvas is counted twice, for clear and draw:

| Step | Line | Defaults | Yours |
|---|---|---|---|
| Upload whole video frame | 9433 | 2,073,600 | 2,073,600 |
| Mipmap of that frame | 9435 | ~691,200 | ~691,200 |
| Draw into projectorBuffer | 9439 | 116,736 | 116,736 |
| Cross-context copy of buffer | 8496 | 116,736 | 116,736 |
| Its mipmap | 8498 | ~38,912 | ~38,912 |
| Projector shader draw | 8502 | 39,525 | 108,389 |
| Blur canvas clear + blur draw | 8509/8514 | 31,518 | 81,982 |
| **Total** | | **≈3.11 M** | **≈3.23 M (+3.8%)** |

At 30 fps that is about 93 M vs 97 M texture pixels per second. **About 86% of it is the full-resolution re-upload and mipmap (A), which none of the ambient-light sliders can change.** Only the YouTube quality setting changes it. A 720p stream gives 921,600 + 307,200 → total ≈1.69 M/frame (−48% vs yours at 1080p).

Derived, not measured: the buffer pass samples the video at mip bias 1 (`mipmapLevel = 1`, 9427; shader 9638). For 1920→456 the natural level is about 2.07, so it actually reads the mip level near 3 (≈240×135). The projector pass uses bias `log2(256/128)=1` (8443). The 2× projectorBuffer and most of the 11-level mip chain therefore add cost but no visible detail. UNCONFIRMED in practice; based on GLSL ES texture2D bias semantics.

### Other recurring costs

| What | Line | How often (your settings) | Scaling / note |
|---|---|---|---|
| No-op `requestVideoFrameCallback` | 11545 | once per video frame | one extra callback per frame. No comment explains it; it may keep Chrome's video-frame callback path active (UNCONFIRMED) |
| `getVideoPlaybackQuality()` | 12833-12838 (via `getVideoFrameCount` in 12849) | once per video frame | allocates an object per call; small |
| async/await chain onVideoFrame → onNextFrame → onNextLimitedFrame → nextFrame → drawAmbientlight | 11540-11556, 11290-11400 | once per video frame | 4–5 Promises per frame; adds garbage-collection churn; small |
| `afterNextFrame` → `updateSizesChanged(true)` → `getSizesChanged` → `getElemRect` ×2 (getBoundingClientRect + offsetParent) | 11367, 11384-11388, 11414-11419, 12690-12741 | about every 2 s during playback (because `delayedUpdateSizesChanged` is true every frame, 11367) | forces a synchronous layout of YouTube's large page every 2 s |
| stats `detectFrameRates` + `stats.update` | 11420-11428, 10853 | 1 per second (`updateStatsInterval=1000`, 10955) via requestIdleCallback | small; returns early when stats are hidden |
| ResizeObservers on html, player and video | 11965-12001 | on every resize | debounced by a ±2 px check (11963); each fires `resize()`, which forces a frame |
| `window resize` → `updateCrop` (2× getBoundingClientRect) + frame | 8418-8422, 11962 | every resize event, no throttle | low |
| MutationObserver on whole document, subtree childList | 13205-13252 | every DOM insert/remove anywhere on YouTube (comments, recommendations, menus) | small per call, very frequent, never disconnected |
| MutationObserver on player `class` + thumbnail `style` | 12008-12031 | every player class toggle (autohide on mouse move, buffering, etc.) | cheap per call |
| styles/content.css (250,349 bytes, 3,282 lines) | content.js 5413-5432 | parsed once per youtube.com page, including pages with no video | 532 `:not(`, 40 `:has(`, 6 `backdrop-filter` (e.g. content.css 334 masthead `blur(30px)` when the header is transparent and scrolled; 442, 1200, 1272, 2809, 3128); 150-layer box-shadows on slider thumbs (2465-2521, settings menu only). A backdrop-filter over the animating glow has to re-filter every frame, but only in those states (UNCONFIRMED effect size) |
| Surrounding-content text/button shadows | 12596-12606, defaults 4386-4421 | on by default (size 15 → 3 px, opacity 30%) | painted once; normally not re-rasterised per frame (UNCONFIRMED) |

## Loose ends

| Sev | Where | Issue | Why it matters |
|---|---|---|---|
| med | 12768-12770 | `Math.min(Math.max(this.videoFrameRate \|\| 30), limit)` is passed to `setTimeout` as **milliseconds**. `Math.max` has one argument, so it does nothing. | When the video is scrolled out of view but the glow is visible, a 60 fps video is polled every 60 ms (≈16 Hz) and a 24 fps video every 24 ms (≈41 Hz). This is backwards, and it also creates a new `Error().stack` each frame through `setTimeout$1`'s `wrapErrorHandler` (80-84). |
| med | 13205-13252 | `detectDetachedVideo` MutationObserver on `document` `{childList, subtree}` is never disconnected, even on non-watch pages (it only checks `isWatchPageUrl()` inside). | Runs on every YouTube DOM change for the life of the tab. |
| med | 9433 | Every frame uses `texImage2D` (re-allocation) of the full video instead of `texSubImage2D` on a fixed-size texture, plus `generateMipmap` of all levels (9435). | This is the single largest per-frame cost (≈86% of texture pixels), and most of the mip chain is never sampled. |
| low | 11434 | `cancelAnimationFrame(this.scheduledNextFrame)`, but `scheduledNextFrame` is a boolean (`true`, set at 12764/11552). | `cancelAnimationFrame(true)` cancels request ID 1, which could be some other code's frame callback, and never cancels the intended one. |
| low | 13145 vs 13130 | `removeEventListener('ytal-message', …, true)` removes a capture listener, but it was added without capture (13130). | The global message listener can never be removed, a leak, though it is a single page-lifetime listener. |
| low | 8662 | `this.containerElem.remove(this.elem)`: `Element.remove()` takes no argument. | `ProjectorWebGL.remove()` would delete the whole container, not the canvas. It appears to be unused (dead) but would be wrong if called. |
| low | 12414 | `!this.settings.webGL && blur != 0`: `blur` is not declared, so it resolves to `window.blur` (a function), which is always `!= 0`. | Dead in WebGL mode; in Canvas2D mode the CSS blur is always applied, even with blur = 0. |
| low | 8519 | `drawIndex` advances by `1 + round(random()*0.5)`. | Only matters with frameFading>0 (projectorsCount>1, 8827). It makes multi-frame fading non-deterministic and skips slots about 50% of the time. Inert with your settings (frameFading default 0, line 4840). |
| low | 12268 + 12666-12688 | Spread is quantised to multiples of edge (`round(spread/edge)`). | The slider value is not what you get (76.2 → 68%). This is confusing when tuning for cost. |
| low | 11545 | No-op rVFC registered every frame, with no comment. | It is an extra callback per frame, and its purpose cannot be checked from the code. |
| low | 11367, 11414-11419 | `delayedUpdateSizesChanged` is set every frame, so `getSizesChanged(true)` forces layout every ~2 s, forever, during playback. | Steady background layout work on a heavy page. |
| low | 12008, 12032 | `videoPlayerObserver` / `playerContainersObserver` are local consts, never disconnected. | Ambientlight is a singleton per page (`window.ambientlight`, 13297/13327), so this does not grow per navigation, but it can never be torn down. |
| low | 11707-11716 | `detectChromiumBugVideoJitterWorkaround` enables the jitter workaround on any Chrome version (`if (version)`). | Inert while the setting is false (default 4531-4540). If you turn the setting on, a 60 s infinite CSS animation (content.css 1355-1366) forces the page to render every display refresh. |
| low | 11115-11119 | When the page is hidden, a buffer `clear()` is delayed 3 s; nothing else stops the loop. | Loop stopping in background tabs relies on Chrome not firing rVFC/rAF in hidden tabs (expected browser behaviour; UNCONFIRMED here). No wasted work found while **paused**: `canScheduleNextFrame` checks `paused`/`ended`/`seeking` (11349). |
| low | 5108-5112 (content.js has its own copy) | Crash reporting (Sentry) is on by default (`technical: true, crash: true`). Its flush loop polls `setInterval(…, 1)` (3049, content.js 3028). | Privacy rather than heat. The 1 ms interval only runs during a flush. |
| low | 8302-8406, 12436, 12414 | Projector2d / non-WebGL path. | Dead code with webGL=true; only used after a WebGL crash fallback (11177-11179). |
| low | `checkForDrawErrors` 8522-8542 and ~9458-9480, `nextFrame` catch 11388-11399 | Draw errors: the first 2 only warn. After that, `catchedErrors[ex.name]` swallows repeats into `console.error`. | Failures become quiet after the first one, so a stuck glow gives no visible signal. |

## What you can change today

Savings are estimated from the code paths above. They are not measured.

| Change | Where in code | Effect |
|---|---|---|
| **Lower YouTube quality to 720p** (or 480p) | upload/mip at 9433-9435 scale with `videoWidth×videoHeight`; p stays 228×128 (same pScale formula) | Per-frame pixels: 3.23 M → **1.69 M (−48%)** at 720p; ≈0.78 M (−76%) at 480p (854×480). Video decoding also gets cheaper. The glow looks practically the same, because it is built from a ~240×135 mip anyway. **Biggest lever.** |
| **Limit framerate 15–20** (default 60) | `onNextLimitedFrame` 11312-11332 skips frames until `nextFrameTime` | Work scales linearly with ambient fps. For a 30 fps video: 20 → −33%, 15 → −50%. For a 24/25 fps video, 15 → about −40%. The glow is blurred, so this is hard to notice. |
| **Turn on "Save energy on static videos"** (energySaver) | 11338-11348, 11009-11023 | For still-image / lyric music videos: 1 frame per 5 s or 1 per second (−97% to −99%). Not active in the first or last 5 s (11348). Costs one storyboard fetch per video. |
| **Spread back to ≈17–25** (keep edge 17) | 12268 | levels 7 → 4. WebGL canvas 108k → 44k px; blur canvas 41k → 21k px; on-screen glow 5.20 → 2.63 Mpx (small player). Only about −2% texture pixels, but it lets the compositor redraw less than the full window in the small player. |
| **Keep blur ≥ 20** (yours 44.3 is fine) | 12431 | Below 20 the buffers get bigger. Blur 5 → p 456×256, total ≈4.52 M px/frame (+40%). Counter-intuitive. |
| Resolution 50% | 12430-12431 | Shrinks only the small buffers (p 114×64). Total 3.23 M → 2.88 M (−11%). The video upload is untouched. |
| Keep frameSync = 2 ("Video") | 12763 | 1 ("Display") draws every display refresh (`hasNewFrame=true`, 12867). On a 120 Hz panel with a 30 fps video that is about **4× the work**. 0 ("Decoded") adds a requestAnimationFrame JS wake-up every display refresh. |
| Keep frameBlending, videoOverlay, frameFading, showFrametimes, jitter-workaround **off** | 12763, 12880-12955, 11707-11784 | Each one forces requestAnimationFrame every display frame and/or extra full-size buffers (videoOverlay copies the full video every frame, 12961). |
| Fullscreen playback | 12848 | When the video fills the screen and the page is at the top, drawing is skipped entirely. |
| "Enable in layouts" excluding theater | 11276-11281 | No glow (and no cost) in that view. |

## Method

- Read the code directly with `sed -n`/`grep -n` on `scripts/content-main.js`, focusing on: settings defaults (4195-4900), `ProjectorShadow` (8126-8300), `ProjectorWebGL` (8407-9348), `WebGLOffscreenCanvas`/`WebGLContext` (9350-9640), `Ambientlight` scheduling and observers (10931-12100), sizing (12260-12690), and the draw loop (12760-13000), plus bootstrap/observers (13116-13462). `scripts/content.js` injection (5300-5488), `manifest.json`, and pattern counts for `styles/content.css` were also checked.
- Sizes were computed with a short Python script that copies the formulas at 12268, 12430-12441, 12451-12457, 12648-12688, and 9147-9165. The rounding matches `Math.ceil`/`floor`/`round`.
- Not done: no runtime profiling, no Chrome trace, and no check of whether Chrome 150/Wayland on the 780M uses hardware video decode (this changes how expensive step A is). The GPU-process attribution, display scale factor, video fps of the specific music video, cross-context copy path (GPU vs readback), and backdrop-filter/text-shadow repaint cost are all marked UNCONFIRMED.
- `bar-detection-worker.js` and `injected.js` were not examined in depth. Bar detection is off in your settings (`detectBarSize` false, 12877), so the worker does not run.
