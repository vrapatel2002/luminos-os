// [CHANGE: claude-code | 2026-10-11]
// Pure helpers for Luminos Ambient. No DOM, no chrome.* — unit-tested under node.
(function () {
  const DEFAULTS = { enabled: true, spread: 30, fps: 6, intensity: 80 }; // fps 12 -> 6: re-plan after benchmark

  function clamp(v, lo, hi) {
    return Math.min(hi, Math.max(lo, v));
  }

  function intOr(value, fallback, lo, hi) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
    return clamp(Math.round(value), lo, hi);
  }

  function clampSettings(raw) {
    const r = raw && typeof raw === 'object' ? raw : {};
    return {
      enabled: r.enabled !== false,
      spread: intOr(r.spread, DEFAULTS.spread, 0, 60),
      fps: intOr(r.fps, DEFAULTS.fps, 1, 30),
      intensity: intOr(r.intensity, DEFAULTS.intensity, 0, 100),
    };
  }

  function isPositive(n) {
    return typeof n === 'number' && Number.isFinite(n) && n > 0;
  }

  function sampleSize(videoW, videoH, longSide = 16) {
    if (!isPositive(videoW) || !isPositive(videoH)) return null;
    const long = Math.max(videoW, videoH);
    const short = Math.max(1, Math.round(longSide * (Math.min(videoW, videoH) / long))); // divide first: no overflow
    return videoW >= videoH ? { w: longSide, h: short } : { w: short, h: longSide };
  }

  function glowRect(rect, spread) {
    const s = clamp(spread, 0, 60) / 100;
    const width = rect.width * (1 + 2 * s);
    const height = rect.height * (1 + 2 * s);
    const left = rect.left - (width - rect.width) / 2;
    const top = rect.top - (height - rect.height) / 2;
    return { left, top, width, height };
  }

  function frameDelay(fps) {
    if (typeof fps !== 'number' || !Number.isFinite(fps)) return 83;
    return Math.round(1000 / clamp(fps, 1, 30));
  }

  function blendAlpha(dtMs, tauMs = 300) {
    if (tauMs <= 0) return 1;
    if (typeof dtMs !== 'number' || !Number.isFinite(dtMs) || dtMs < 0) return 0.05;
    return clamp(1 - Math.exp(-dtMs / tauMs), 0.05, 1);
  }

  function shouldRun(s) {
    const st = s || {};
    return Boolean(st.enabled && !st.paused && !st.ended && !st.hidden &&
      !st.fullscreen && st.onScreen && st.videoW > 0);
  }

  function rectChanged(a, b, eps = 0.5) {
    if (!a || !b) return true;
    return ['left', 'top', 'width', 'height'].some((k) => !(Math.abs(a[k] - b[k]) <= eps));
  }

  const api = { clampSettings, sampleSize, glowRect, frameDelay, blendAlpha, shouldRun, rectChanged };
  globalThis.LuminosAmbientCore = api;
  if (typeof module !== 'undefined') module.exports = api;
})();
