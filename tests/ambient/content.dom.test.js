'use strict';
// Behavioural test of content.js in a fake DOM (node:vm). Asserts only the observable contract
// from CONTRACTS.md / SPEC.md. Failures append "[harness]" notes naming DOM APIs the fake lacked.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { makeHarness } = require('./fakedom.js');

const DIR = path.join(__dirname, '../../scripts/chrome-luminos-ambient');
const DEF = { enabled: true, spread: 30, fps: 6, intensity: 80 };
function src(name) {
  const p = path.join(DIR, name);
  if (!fs.existsSync(p)) assert.fail(`source file missing: ${p}`);
  return fs.readFileSync(p, 'utf8');
}
function boot(h) {
  const core = src('core.js');
  const content = src('content.js');
  try { h.run(core, 'core.js'); } catch (e) { assert.fail(`core.js threw while loading: ${(e && e.stack) || e}${h.note()}`); }
  try { h.run(content, 'content.js'); } catch (e) { assert.fail(`content.js threw while loading: ${(e && e.stack) || e}${h.note()}`); }
}
async function settle(h) { for (let i = 0; i < 8; i++) { await new Promise((r) => setImmediate(r)); h.flushIO(); } }
async function play(h, v = h.video) { v.paused = false; v.ended = false; h.fire(v, 'play'); h.fire(v, 'playing'); await settle(h); }
async function pause(h, v = h.video) { v.paused = true; h.fire(v, 'pause'); await settle(h); }
async function start(h, opts = {}) {
  if (opts.settings) h.store.luminosAmbient = opts.settings;
  h.setVideoRect(h.video, 100, 80, 640, 360);
  boot(h);
  await settle(h);
  assert.strictEqual(h.pending(), 0, 'a timer is pending before any video plays');
  await play(h);
}
async function runTimers(h, n) { let ran = 0; for (let i = 0; i < n; i++) { if (!h.runNextTimer()) break; ran++; await settle(h); } return ran; }
const glow = (h) => h.document.getElementById('luminos-ambient-glow');
function ticks(h) {
  const c = glow(h);
  assert.ok(c, 'no <canvas id="luminos-ambient-glow"> in the document');
  const t = c.dataset.ticks;
  assert.match(String(t), /^\d+$/, `dataset.ticks is not an integer string: ${t}`);
  return Number(t);
}
const classOn = (h) => h.html.classList.contains('luminos-ambient-on');
function assertShown(h) {
  const c = glow(h);
  assert.ok(c, 'glow canvas missing');
  assert.ok(classOn(h), '<html> lacks class luminos-ambient-on while glow should show');
  assert.notStrictEqual(c.style.display, 'none', 'canvas display:none while glow should show');
}
function assertIdle(h, why) {
  assert.strictEqual(h.pending(), 0, `${why}: a setTimeout is still pending`);
  assert.ok(!classOn(h), `${why}: <html> still has class luminos-ambient-on`);
  const c = glow(h);
  if (c) assert.strictEqual(c.style.display, 'none', `${why}: canvas not display:none`);
}
function px(v, name) {
  assert.match(String(v), /^-?\d+(\.\d+)?(e[-+]?\d+)?px$/, `style.${name} is not a px length: "${v}"`);
  return parseFloat(v);
}
function assertPlaced(h, l, t, w, hh) {
  const s = glow(h).style;
  const got = { left: px(s.left, 'left'), top: px(s.top, 'top'), width: px(s.width, 'width'), height: px(s.height, 'height') };
  const want = { left: l, top: t, width: w, height: hh };
  for (const k of Object.keys(want)) assert.ok(Math.abs(got[k] - want[k]) <= 1, `glow ${k}=${got[k]} want ${want[k]} (±1px); all: ${JSON.stringify(got)}`);
}
function finish(h) {
  assert.deepStrictEqual(h.forbidden, [], 'forbidden APIs used');
  assert.deepStrictEqual(h.errors, [], 'uncaught errors in callbacks');
  assert.ok(h.maxPending <= 1, `more than one setTimeout pending at once (max ${h.maxPending})`);
  const big = h.ctxCalls.filter((c) => c.w > 64 || c.h > 64);
  assert.deepStrictEqual(big.map((c) => `${c.name} on ${c.w}x${c.h} canvas`), [], '2D work on a canvas larger than 64x64');
}
function T(name, fn) {
  test(name, async () => {
    const h = makeHarness();
    try { await fn(h); finish(h); } catch (e) {
      if (e && typeof e.message === 'string') e.message += h.note();
      throw e;
    }
  });
}

T('loads cleanly; nothing runs while the video is paused', async (h) => {
  h.setVideoRect(h.video, 100, 80, 640, 360);
  boot(h);
  await settle(h);
  assert.strictEqual(h.pending(), 0);
  assert.ok(!classOn(h));
});

T('play on-screen → exactly one pending timeout; canvas styled per contract', async (h) => {
  await start(h);
  assert.strictEqual(h.pending(), 1, 'expected exactly one pending setTimeout after play');
  await runTimers(h, 1);
  const c = glow(h);
  assert.ok(c, 'canvas#luminos-ambient-glow not created');
  assert.strictEqual(c.localName, 'canvas', 'glow element is not a <canvas>');
  assert.strictEqual(c.parentNode, h.body, 'glow canvas is not a child of document.body');
  assert.strictEqual(c.style.position, 'absolute');
  assert.strictEqual(String(c.style.zIndex), '-1');
  assert.strictEqual(c.style.pointerEvents, 'none');
  assert.ok(Math.abs(parseFloat(c.style.opacity) - 0.8) < 1e-6, `opacity "${c.style.opacity}" != intensity/100 = 0.8`);
  assert.ok(c.width <= 64 && c.height <= 64, `glow canvas bitmap ${c.width}x${c.height} > 64`);
  assertShown(h);
});

T('each fired tick increments dataset.ticks by exactly 1; draws happen; delay = frameDelay(6) (default fps)', async (h) => {
  await start(h);
  let prev = null;
  for (let i = 0; i < 12; i++) {
    assert.strictEqual(h.pending(), 1, `tick ${i}: expected exactly one pending timeout`);
    assert.ok(h.runNextTimer(), 'timer chain ended while playing');
    await settle(h);
    const t = ticks(h);
    if (prev !== null) assert.strictEqual(t, prev + 1, `ticks went ${prev} → ${t} on one timer`);
    prev = t;
  }
  assert.ok(h.ctxCalls.some((c) => c.name === 'drawImage'), 'no drawImage call while playing — glow never drawn');
  const chained = h.delays.filter((d) => d.fromTimer).map((d) => d.delay);
  assert.ok(chained.length >= 10, 'tick did not reschedule itself');
  for (const d of chained) assert.ok(Math.abs(d - 167) <= 2, `tick delay ${d}ms, want ≈167 (default 6 fps)`);
});

T('placed at glowRect(videoRect, spread) in page coordinates; follows rect changes', async (h) => {
  h.setScroll(30, 200);
  await start(h);
  await runTimers(h, 2);
  // viewport rect (100,80,640,360) + scroll (30,200) → page (130,280); s = 0.3
  assertPlaced(h, 130 - 192, 280 - 108, 1024, 576);
  h.setScroll(0, 0);
  h.setVideoRect(h.video, 130, 280, 640, 360); // same page position after scrolling back
  await runTimers(h, 2);
  assertPlaced(h, 130 - 192, 280 - 108, 1024, 576);
  h.setVideoRect(h.video, 0, 56, 1280, 720); // theater mode
  await runTimers(h, 2);
  assertPlaced(h, -384, 56 - 216, 2048, 1152);
});

T('pause → no pending timeout, class removed, display:none, ticks frozen; play resumes', async (h) => {
  await start(h);
  await runTimers(h, 3);
  await pause(h);
  assertIdle(h, 'after pause');
  const t0 = ticks(h);
  h.advance(2000);
  assert.strictEqual(await runTimers(h, 5), 0, 'a timer fired while paused');
  assert.strictEqual(ticks(h), t0, 'ticks advanced while paused');
  await play(h);
  assert.strictEqual(h.pending(), 1, 'did not resume on play');
  await runTimers(h, 2);
  assert.ok(ticks(h) > t0, 'ticks did not advance after resuming');
  assertShown(h);
});

T('ended → idle', async (h) => {
  await start(h);
  await runTimers(h, 2);
  h.video.paused = true; h.video.ended = true;
  h.fire(h.video, 'pause'); h.fire(h.video, 'ended');
  await settle(h);
  assertIdle(h, 'after ended');
});

T('document hidden → no pending timeout; visible again → resumes', async (h) => {
  await start(h);
  await runTimers(h, 2);
  h.document.hidden = true; h.document.visibilityState = 'hidden';
  h.fire(h.document, 'visibilitychange');
  await settle(h);
  assertIdle(h, 'tab hidden');
  h.document.hidden = false; h.document.visibilityState = 'visible';
  h.fire(h.document, 'visibilitychange');
  await settle(h);
  assert.strictEqual(h.pending(), 1, 'did not resume when tab became visible');
});

T('fullscreen → idle; exit fullscreen → resumes', async (h) => {
  await start(h);
  await runTimers(h, 2);
  h.document.fullscreenElement = h.player;
  h.fire(h.player, 'fullscreenchange', true);
  await settle(h);
  assertIdle(h, 'fullscreen');
  h.document.fullscreenElement = null;
  h.fire(h.player, 'fullscreenchange', true);
  await settle(h);
  assert.strictEqual(h.pending(), 1, 'did not resume after leaving fullscreen');
});

T('player scrolled off-screen (IntersectionObserver) → idle; back on-screen → resumes', async (h) => {
  await start(h);
  await runTimers(h, 2);
  assert.ok(h.ios.length > 0, 'no IntersectionObserver was created');
  h.onScreen = false; await settle(h);
  assertIdle(h, 'player off-screen');
  h.onScreen = true; await settle(h);
  assert.strictEqual(h.pending(), 1, 'did not resume when player came back on-screen');
});

T('storage change {enabled:false} → idle; enabled again → resumes; intensity/spread/fps apply live', async (h) => {
  await start(h);
  await runTimers(h, 2);
  h.setSettings({ enabled: false }); await settle(h);
  assertIdle(h, 'disabled via storage');
  h.setSettings({ ...DEF, intensity: 50, spread: 0, fps: 30 }); await settle(h);
  assert.strictEqual(h.pending(), 1, 'did not resume when re-enabled');
  const before = h.delays.length;
  await runTimers(h, 3);
  assert.ok(Math.abs(parseFloat(glow(h).style.opacity) - 0.5) < 1e-6, `opacity "${glow(h).style.opacity}" after intensity 50`);
  assertPlaced(h, 100, 80, 640, 360); // spread 0 → glow == video rect
  const chained = h.delays.slice(before).filter((d) => d.fromTimer).map((d) => d.delay);
  assert.ok(chained.length > 0 && chained.every((d) => Math.abs(d - 33) <= 2), `fps 30 → delays ${JSON.stringify(chained)}, want ≈33`);
});

T('starts disabled when stored settings say so', async (h) => {
  h.store.luminosAmbient = { enabled: false };
  h.setVideoRect(h.video, 100, 80, 640, 360);
  boot(h); await settle(h);
  await play(h);
  assertIdle(h, 'stored enabled:false');
});

T('rapid setting changes never create a second timer chain', async (h) => {
  await start(h);
  for (let i = 0; i < 25; i++) {
    h.setSettings({ ...DEF, fps: 1 + ((i * 7) % 30), spread: (i * 13) % 61, intensity: (i * 17) % 101 });
    assert.ok(h.pending() <= 1, `after change ${i}: ${h.pending()} timers pending`);
    if (i % 3 === 0) { h.runNextTimer(); }
    await settle(h);
  }
  assert.strictEqual(h.pending(), 1, 'chain lost after rapid changes');
});

T('video without metadata (videoWidth 0) → nothing runs', async (h) => {
  h.video.videoWidth = 0; h.video.videoHeight = 0;
  h.setVideoRect(h.video, 100, 80, 640, 360);
  boot(h); await settle(h);
  await play(h);
  await runTimers(h, 3);
  assertIdle(h, 'videoWidth 0');
});

T('a playing video outside #movie_player (hover preview) is ignored', async (h) => {
  h.setVideoRect(h.previewVideo, 10, 10, 320, 180);
  boot(h); await settle(h);
  await play(h, h.previewVideo);
  await runTimers(h, 3);
  assertIdle(h, 'preview video');
});

T('orphaned glow canvas from a previous injection is removed', async (h) => {
  const old = h.document.createElement('canvas');
  old.id = 'luminos-ambient-glow';
  h.body.appendChild(old);
  await start(h);
  await runTimers(h, 2);
  const all = h.document.querySelectorAll('#luminos-ambient-glow');
  assert.strictEqual(all.length, 1, `${all.length} glow canvases in the document`);
  ticks(h);
});

T('SPA navigation: a new <video> takes over, the old one is released', async (h) => {
  await start(h);
  await runTimers(h, 2);
  const old = h.video;
  old.remove();
  const nv = h.document.createElement('video');
  h.container.appendChild(nv);
  h.setVideoRect(nv, 100, 80, 640, 360);
  await play(h, nv);
  assert.strictEqual(h.pending(), 1, 'new video did not start the glow');
  const t0 = ticks(h);
  old.paused = true; h.fire(old, 'pause'); await settle(h); // detached old video
  assert.strictEqual(h.pending(), 1, 'pausing the released old video stopped the new one');
  await runTimers(h, 3);
  assert.strictEqual(ticks(h), t0 + 3);
});

T('drawImage throwing (tainted frame) is caught: one console.warn, glow off for that video', async (h) => {
  await start(h);
  await runTimers(h, 2);
  h.drawThrows = true;
  await runTimers(h, 3);
  assert.deepStrictEqual(h.errors, [], 'drawImage exception escaped');
  assertIdle(h, 'after drawImage threw');
  assert.strictEqual(h.warns.length, 1, `expected exactly one console.warn, got ${JSON.stringify(h.warns)}`);
  await pause(h); await play(h);
  await runTimers(h, 3);
  assert.strictEqual(h.pending(), 0, 'glow restarted on the same tainted video');
  assert.strictEqual(h.warns.length, 1, 'warned more than once');
});

// ---------- round 2: review findings ----------

T('orphaned context: chrome.runtime.id gone → next tick removes/hides glow, class off, no timer', async (h) => {
  await start(h);
  await runTimers(h, 2);
  assert.strictEqual(h.context.chrome.runtime.id, 'test', 'fake chrome.runtime.id should start as "test"');
  h.orphan();
  assert.ok(h.runNextTimer(), 'no timer pending before the orphan check');
  await settle(h);
  assert.strictEqual(h.pending(), 0, 'timer still pending after the extension context was invalidated');
  assert.ok(!classOn(h), '<html> still has luminos-ambient-on after orphaning');
  const c = glow(h);
  assert.ok(!c || c.style.display === 'none', 'orphaned glow canvas still in the DOM and visible');
  h.advance(5000);
  assert.strictEqual(await runTimers(h, 3), 0, 'a timer fired after orphaning');
});

T('drawImage failure, then same <video> fires loadedmetadata (new src) and plays → glow runs again; still one warn', async (h) => {
  await start(h);
  await runTimers(h, 2);
  h.drawThrows = true;
  await runTimers(h, 3);
  assertIdle(h, 'after drawImage threw');
  assert.strictEqual(h.warns.length, 1, `expected one console.warn, got ${JSON.stringify(h.warns)}`);
  h.drawThrows = false;
  await pause(h);
  h.video.src = h.video.currentSrc = 'blob:https://www.youtube.com/next';
  h.video.videoWidth = 1280; h.video.videoHeight = 720;
  h.fire(h.video, 'loadedmetadata');
  await settle(h);
  await play(h);
  assert.strictEqual(h.pending(), 1, 'glow did not restart after the video loaded new metadata');
  const t0 = ticks(h);
  await runTimers(h, 3);
  assert.strictEqual(ticks(h), t0 + 3, 'ticks did not advance after recovery');
  assertShown(h);
  assert.strictEqual(h.warns.length, 1, `warned again: ${JSON.stringify(h.warns)}`);
});

T('mini-player: video inside ytd-miniplayer never glows; moved back out and played → resumes', async (h) => {
  assert.strictEqual(h.video.closest('ytd-miniplayer'), null, 'fake closest(tag) sanity');
  await start(h);
  await runTimers(h, 2);
  h.miniplayer.appendChild(h.player); // YouTube moves the player into the mini-player while playing
  assert.ok(h.video.closest('ytd-miniplayer'), 'fake closest(tag) sanity');
  await runTimers(h, 1);
  assertIdle(h, 'playing inside ytd-miniplayer (next tick)');
  await pause(h); await play(h);
  await runTimers(h, 2);
  assertIdle(h, 'play event inside ytd-miniplayer');
  h.playerParent.appendChild(h.player);
  await pause(h); await play(h);
  assert.strictEqual(h.pending(), 1, 'did not resume after leaving the mini-player');
  const t0 = ticks(h);
  await runTimers(h, 2);
  assert.strictEqual(ticks(h), t0 + 2);
  assertShown(h);
});

T('mini-player: a fresh page load with the video already in ytd-miniplayer stays idle', async (h) => {
  h.miniplayer.appendChild(h.player);
  h.setVideoRect(h.video, 900, 500, 400, 225);
  boot(h); await settle(h);
  await play(h);
  await runTimers(h, 3);
  assertIdle(h, 'video in ytd-miniplayer');
});

T('stale IntersectionObserver entry for the OLD video does not stop the new video', async (h) => {
  await start(h);
  await runTimers(h, 2);
  const old = h.video;
  old.remove();
  const nv = h.document.createElement('video');
  h.container.appendChild(nv);
  h.setVideoRect(nv, 100, 80, 640, 360);
  await play(h, nv);
  assert.strictEqual(h.pending(), 1, 'new video did not start the glow');
  h.deliverIO(old, false); // stale entry: only the old target, not intersecting
  await settle(h);
  assert.strictEqual(h.pending(), 1, 'stale IO entry for the old video stopped the new video');
  const t0 = ticks(h);
  await runTimers(h, 3);
  assert.strictEqual(ticks(h), t0 + 3, 'ticks stopped after a stale IO entry');
  assertShown(h);
});
