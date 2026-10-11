// [CHANGE: claude-code | 2026-10-11]
// Soft glow behind the YouTube player. Every canvas touched per tick is <= 64 px; the browser stretches it.
(function () {
  const core = globalThis.LuminosAmbientCore;
  const GLOW_ID = 'luminos-ambient-glow';
  const ON_CLASS = 'luminos-ambient-on';
  // emptied/loadedmetadata mean a new source: YouTube reuses the <video> element across navigations.
  const VIDEO_EVENTS = [['play', evaluate], ['pause', evaluate], ['ended', evaluate],
    ['emptied', onNewSource], ['loadedmetadata', onNewSource]];
  const WRAPPERS = ['ytd-app', 'ytd-page-manager', 'ytd-watch-flexy', '#columns', '#primary',
    '#player-container-outer', '#player-container-inner', '#player', 'ytd-player', '#full-bleed-container',
    '#player-full-bleed-container', '#player-theater-container', '#cinematics', '#cinematics-container'];
  const [glow, sample, accum, mask] = [0, 0, 0, 0].map(() => document.createElement('canvas'));
  const failed = new WeakSet();
  const st = { video: null, settings: core.clampSettings(null), onScreen: false, timer: null,
    lastRect: null, lastTick: 0, accumKey: '', inner: 1 };
  function setup() {
    document.getElementById(GLOW_ID)?.remove(); // orphan from a previous injection
    Object.assign(glow, { id: GLOW_ID }).dataset.ticks = '0';
    glow.style.cssText = 'position:absolute;z-index:-1;pointer-events:none;display:none;opacity:0.8;will-change:transform;';
    document.body.appendChild(glow);
    if (document.getElementById('luminos-ambient-style')) return;
    const style = Object.assign(document.createElement('style'), { id: 'luminos-ambient-style' });
    // YouTube's own ambient mode (#cinematics) would paint over ours, so hide it while we run.
    style.textContent = `${WRAPPERS.map((w) => `html.${ON_CLASS} ${w}`).join(',\n')} ` +
      '{ background: transparent !important; }\n' +
      `html.${ON_CLASS} #cinematics { display: none !important; }`;
    document.head.appendChild(style);
  }
  function canRun() {
    const v = st.video;
    if (!v || failed.has(v) || v.closest('ytd-miniplayer')) return false; // A6: no glow on the mini-player
    return core.shouldRun({ enabled: st.settings.enabled, paused: v.paused, ended: v.ended, hidden: document.hidden,
      fullscreen: Boolean(document.fullscreenElement), onScreen: st.onScreen, videoW: v.videoWidth });
  }
  // Single re-evaluation point: every event funnels here, so there is never more than one chain.
  function evaluate() {
    if (!alive() || !glow.isConnected || !canRun()) return stop(); // disconnected = orphaned by a newer injection
    if (st.timer !== null) return;
    glow.style.display = 'block';
    document.documentElement.classList.add(ON_CLASS);
    st.lastTick = 0;
    st.timer = setTimeout(tick, 0);
  }
  // The extension was disabled/removed/reloaded: this orphaned script must clean up and go quiet.
  function alive() {
    if (globalThis.chrome?.runtime?.id) return true;
    stop(); glow.remove();
    return false;
  }
  function stop() {
    clearTimeout(st.timer); st.timer = null; // clearTimeout(null) is a no-op
    if (!glow.isConnected) return;
    glow.style.display = 'none';
    document.documentElement.classList.remove(ON_CLASS);
  }
  function tick() {
    st.timer = null; if (!alive()) return;
    try { draw(); } catch (err) {
      failed.add(st.video);
      console.warn('[Luminos Ambient] drawImage failed; glow off for this video.', err); // once: video is now in failed
    }
    if (glow.isConnected && canRun()) st.timer = setTimeout(tick, core.frameDelay(st.settings.fps));
    else stop();
  }
  function place(rect) {
    const r = core.glowRect(rect, st.settings.spread);
    const page = { left: r.left + window.scrollX, top: r.top + window.scrollY, width: r.width, height: r.height };
    if (!core.rectChanged(page, st.lastRect)) return r;
    st.lastRect = page;
    const px = (n) => `${n}px`;
    Object.assign(glow.style, { left: px(page.left), top: px(page.top), width: px(page.width), height: px(page.height) });
    return r;
  }
  function sizeSample(v) {
    const s = core.sampleSize(v.videoWidth, v.videoHeight, 16);
    if (s && (sample.width !== s.w || sample.height !== s.h)) Object.assign(sample, { width: s.w, height: s.h });
    return Boolean(s);
  }
  // Resizing clears the accumulation canvas, so the next blend restarts at full strength.
  function sizeAccum(r) {
    const a = core.sampleSize(r.width, r.height, 64);
    if (!a) return false;
    const key = `${a.w}x${a.h}x${st.settings.spread}`;
    if (key === st.accumKey) return true;
    st.accumKey = key;
    for (const c of [accum, mask, glow]) Object.assign(c, { width: a.w, height: a.h });
    st.inner = 1 / (1 + 2 * st.settings.spread / 100); // video's share of the glow's size
    // Elliptical fade mask, built once per size: opaque over the video area, clear at the outer edge.
    const ctx = mask.getContext('2d');
    ctx.setTransform(a.w / 2, 0, 0, a.h / 2, a.w / 2, a.h / 2);
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
    [[0, '#000'], [Math.min(0.99, st.inner), '#000'], [1, 'rgba(0,0,0,0)']].forEach(([o, c]) => g.addColorStop(o, c));
    Object.assign(ctx, { fillStyle: g }).fillRect(-1, -1, 2, 2);
    // Blur reaches ~2x its radius, so margin/2 carries colour to the edge. Set after resizing (it resets state).
    const margin = Math.max(a.w, a.h) * (1 - st.inner) / 2;
    accum.getContext('2d').filter = `blur(${Math.max(1, Math.round(margin / 2))}px)`;
    st.lastTick = 0;
    return true;
  }
  function draw() {
    const v = st.video, r = place(v.getBoundingClientRect());
    if (!sizeSample(v) || !sizeAccum(r)) return;
    sample.getContext('2d').drawImage(v, 0, 0, sample.width, sample.height);
    const now = performance.now();
    const iw = accum.width * st.inner, ih = accum.height * st.inner;
    const actx = accum.getContext('2d');
    actx.globalAlpha = st.lastTick ? core.blendAlpha(now - st.lastTick) : 1;
    actx.drawImage(sample, (accum.width - iw) / 2, (accum.height - ih) / 2, iw, ih);
    st.lastTick = now;
    const gctx = glow.getContext('2d'); // copy the glow, then cut it with the edge-fade mask
    Object.assign(gctx, { globalCompositeOperation: 'copy' }).drawImage(accum, 0, 0);
    Object.assign(gctx, { globalCompositeOperation: 'destination-in' }).drawImage(mask, 0, 0);
    glow.dataset.ticks = String(Number(glow.dataset.ticks) + 1);
  }
  const observer = new IntersectionObserver((entries) => {
    const mine = entries.filter((e) => e.target === st.video).pop(); // ignore stale entries for an old video
    if (mine) { st.onScreen = mine.isIntersecting; evaluate(); }
  });
  function onNewSource(e) { failed.delete(e.target); evaluate(); } // a failure belonged to the old source
  function attach(video) {
    if (video === st.video) return;
    const old = st.video;
    if (old) { VIDEO_EVENTS.forEach(([e, f]) => old.removeEventListener(e, f)); observer.unobserve(old); }
    clearTimeout(st.timer); st.timer = null; // no visual reset: the next evaluate() decides, so no class flip
    Object.assign(st, { video, lastRect: null }); // onScreen kept: observer corrects it
    VIDEO_EVENTS.forEach(([e, f]) => video.addEventListener(e, f));
    observer.observe(video);
  }
  function onPlay(e) {
    if (!(e.target instanceof HTMLVideoElement) || !e.target.closest('#movie_player')) return;
    attach(e.target); evaluate();
  }
  function applySettings(raw) {
    st.settings = core.clampSettings(raw);
    glow.style.opacity = String(st.settings.intensity / 100);
    st.lastRect = null; // spread may have changed, so force a style write
    evaluate();
  }
  setup();
  document.addEventListener('play', onPlay, true);
  document.addEventListener('visibilitychange', evaluate);
  document.addEventListener('fullscreenchange', evaluate);
  const first = document.querySelector('#movie_player video');
  if (first) attach(first);
  chrome.storage.local.get('luminosAmbient', (res) => applySettings(res && res.luminosAmbient));
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.luminosAmbient) applySettings(changes.luminosAmbient.newValue);
  });
})();
