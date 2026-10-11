'use strict';
// Example + property tests for core.js (CONTRACTS.md "core.js export").
// Seed: AMBIENT_SEED env var (default 0xC0FFEE). Failures print seed, case index and input.
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const CORE_PATH = path.join(__dirname, '../../scripts/chrome-luminos-ambient/core.js');
let core = null;
let loadError = null;
try { core = require(CORE_PATH); } catch (e) { loadError = e; }
function C() {
  if (!core) assert.fail(`core.js could not be loaded from ${CORE_PATH}: ${loadError && loadError.message}`);
  return core;
}

// ---------- seeded PRNG + generators ----------
const BASE_SEED = Number(process.env.AMBIENT_SEED || 0xC0FFEE) >>> 0;
const N = 600;
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function hash(s) { let h = 2166136261; for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return h >>> 0; }
function fmt(v) {
  if (typeof v === 'number') return Object.is(v, -0) ? '-0' : String(v);
  if (typeof v === 'string') return JSON.stringify(v);
  if (v === undefined) return 'undefined';
  if (typeof v === 'function') return '[function]';
  if (Array.isArray(v)) return `[${v.map(fmt).join(', ')}]`;
  if (v && typeof v === 'object') return `{${Object.keys(v).map((k) => `${k}: ${fmt(v[k])}`).join(', ')}}`;
  return String(v);
}
function property(name, gen, check, n = N) {
  test(`property: ${name} (${n} cases)`, () => {
    C();
    const seed = (BASE_SEED ^ hash(name)) >>> 0;
    const rng = mulberry32(seed);
    for (let i = 0; i < n; i++) {
      const input = gen(rng, i);
      try { check(...input); } catch (e) {
        e.message = `${name} FAILED  seed=${BASE_SEED} (prop seed ${seed}) case=${i}\n  input: (${input.map(fmt).join(', ')})\n  ${e.message}`;
        throw e;
      }
    }
  });
}
const pick = (rng, arr) => arr[Math.floor(rng() * arr.length)];
const EDGE_NUMS = [0, -0, 1, -1, 0.5, -0.5, 0.4999999, 1.5, 2.5, -2.5, 29.5, 30.5, 59.5, 60.5, 61, 100, 1000,
  NaN, Infinity, -Infinity, 1e308, -1e308, Number.MAX_VALUE, Number.MIN_VALUE, Number.MAX_SAFE_INTEGER, -Number.MAX_SAFE_INTEGER, 1e-9];
const NON_NUMS = ['', '10', '12.5', 'abc', ' ', 'NaN', null, undefined, true, false, {}, [], [5], () => 1];
function num(rng) {
  const r = rng();
  if (r < 0.3) return pick(rng, EDGE_NUMS);
  if (r < 0.55) return Math.floor(rng() * 141) - 20; // ints around the ranges
  if (r < 0.8) return (rng() - 0.3) * 200; // fractional
  return (rng() - 0.5) * Math.pow(10, Math.floor(rng() * 20)); // wide magnitudes
}
function anyVal(rng) { return rng() < 0.75 ? num(rng) : pick(rng, NON_NUMS); }
function finiteNum(rng) { let v; do { v = num(rng); } while (!Number.isFinite(v)); return v; }
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const isInt = (v) => typeof v === 'number' && Number.isInteger(v);
const relClose = (a, b, tol) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(a), Math.abs(b));

// ---------- export shape ----------
const FNS = ['clampSettings', 'sampleSize', 'glowRect', 'frameDelay', 'blendAlpha', 'shouldRun', 'rectChanged'];
test('core.js exports exactly the contract functions, also on globalThis.LuminosAmbientCore', () => {
  const c = C();
  assert.deepStrictEqual(Object.keys(c).sort(), [...FNS].sort());
  for (const f of FNS) assert.strictEqual(typeof c[f], 'function', `${f} is not a function`);
  assert.strictEqual(globalThis.LuminosAmbientCore, c, 'globalThis.LuminosAmbientCore !== module.exports');
});

// ---------- clampSettings ----------
const DEF = { enabled: true, spread: 30, fps: 6, intensity: 80 };
const RANGES = { spread: [0, 60], fps: [1, 30], intensity: [0, 100] };
test('clampSettings: examples', () => {
  const { clampSettings: cs } = C();
  for (const raw of [undefined, null, {}, 'x', 42, true, [], () => 1]) assert.deepStrictEqual(cs(raw), DEF, `raw=${fmt(raw)}`);
  assert.deepStrictEqual(cs({ spread: 100, fps: 0, intensity: -5 }), { enabled: true, spread: 60, fps: 1, intensity: 0 });
  assert.deepStrictEqual(cs({ spread: 12.6, fps: 12.4, intensity: 49.5 }), { enabled: true, spread: 13, fps: 12, intensity: 50 });
  assert.deepStrictEqual(cs({ spread: NaN, fps: 'abc', intensity: undefined }), DEF);
  assert.deepStrictEqual(cs({ spread: {}, fps: [], intensity: 'x' }), DEF);
  assert.deepStrictEqual(cs({ fps: 31 }), { ...DEF, fps: 30 });
  assert.deepStrictEqual(cs({ enabled: false }), { ...DEF, enabled: false });
  for (const e of [0, '', null, 'false', undefined, 'no', true]) assert.strictEqual(cs({ enabled: e }).enabled, true, `enabled=${fmt(e)}`);
});
function rawGen(rng) {
  if (rng() < 0.1) return [anyVal(rng)];
  const o = {};
  for (const k of ['enabled', 'spread', 'fps', 'intensity']) {
    if (rng() < 0.85) o[k] = k === 'enabled' && rng() < 0.5 ? pick(rng, [true, false]) : anyVal(rng);
  }
  if (rng() < 0.1) o.extra = anyVal(rng);
  return [o];
}
property('clampSettings: shape, strict boolean, ints in range', rawGen, (raw) => {
  const out = C().clampSettings(raw);
  assert.deepStrictEqual(Object.keys(out).sort(), ['enabled', 'fps', 'intensity', 'spread']);
  assert.strictEqual(typeof out.enabled, 'boolean');
  for (const [k, [lo, hi]] of Object.entries(RANGES)) {
    assert.ok(isInt(out[k]) && out[k] >= lo && out[k] <= hi, `${k}=${fmt(out[k])} not an int in [${lo},${hi}]`);
  }
});
property('clampSettings: idempotent', rawGen, (raw) => {
  const { clampSettings: cs } = C();
  const once = cs(raw);
  assert.deepStrictEqual(cs(once), once);
});
property('clampSettings: enabled === (raw.enabled !== false)', rawGen, (raw) => {
  const out = C().clampSettings(raw);
  const expect = raw !== null && typeof raw === 'object' ? raw.enabled !== false : true;
  assert.strictEqual(out.enabled, expect);
});
property('clampSettings: finite numbers are rounded then clamped; NaN/missing/non-numeric → default',
  (rng) => {
    const o = {};
    for (const k of Object.keys(RANGES)) {
      const r = rng();
      if (r < 0.6) o[k] = finiteNum(rng);
      else if (r < 0.75) o[k] = NaN;
      else if (r < 0.9) o[k] = pick(rng, ['abc', '', undefined, {}, [1, 2], () => 1]);
    }
    return [o];
  },
  (raw) => {
    const out = C().clampSettings(raw);
    for (const [k, [lo, hi]] of Object.entries(RANGES)) {
      const v = raw[k];
      const want = typeof v === 'number' && Number.isFinite(v) ? clamp(Math.round(v), lo, hi) : DEF[k];
      assert.ok(out[k] === want, `${k}: got ${fmt(out[k])}, want ${fmt(want)}`);
    }
  });

// ---------- sampleSize ----------
test('sampleSize: examples', () => {
  const { sampleSize: ss } = C();
  assert.deepStrictEqual(ss(1920, 1080), { w: 16, h: 9 });
  assert.deepStrictEqual(ss(1080, 1920), { w: 9, h: 16 });
  assert.deepStrictEqual(ss(640, 640), { w: 16, h: 16 });
  assert.deepStrictEqual(ss(3200, 900), { w: 16, h: 5 });
  assert.deepStrictEqual(ss(100000, 1), { w: 16, h: 1 });
  assert.deepStrictEqual(ss(1920, 1080, 32), { w: 32, h: 18 });
  for (const [a, b] of [[0, 1080], [1920, 0], [-1, 5], [NaN, 5], [5, Infinity], ['1920', 1080], [null, 1], [undefined, 1], [1, true]]) {
    assert.strictEqual(ss(a, b), null, `sampleSize(${fmt(a)}, ${fmt(b)})`);
  }
});
property('sampleSize: valid input → int sides, long side == longSide, aspect error ≤ 1px', (rng) => {
  const dim = () => (rng() < 0.3 ? pick(rng, [Number.MIN_VALUE, 1e-6, 0.5, 1, 2, 1e9, 1e300, Number.MAX_VALUE]) : rng() * 8000 + 1e-3);
  const ls = rng() < 0.3 ? undefined : 1 + Math.floor(rng() * 64);
  return [dim(), dim(), ls];
}, (W, H, ls) => {
  const out = ls === undefined ? C().sampleSize(W, H) : C().sampleSize(W, H, ls);
  const L = ls === undefined ? 16 : ls;
  assert.ok(out && isInt(out.w) && isInt(out.h), `not int sides: ${fmt(out)}`);
  assert.strictEqual(Math.max(out.w, out.h), L);
  assert.ok(Math.min(out.w, out.h) >= 1);
  if (W >= H) assert.strictEqual(out.w, L, 'wide/square: w must be the long side');
  else assert.strictEqual(out.h, L, 'tall: h must be the long side');
  const ideal = W >= H ? L * (H / W) : L * (W / H);
  const short = W >= H ? out.h : out.w;
  assert.ok(Math.abs(short - ideal) <= 1, `aspect error ${Math.abs(short - ideal)} > 1px`);
  if (ideal >= 1) assert.ok(Math.abs(short - ideal) <= 0.5 + 1e-9, `not rounded: ${short} vs ${ideal}`);
  else assert.strictEqual(short, 1, 'short side below 1px must be max(1, …) = 1');
});
property('sampleSize: invalid input → null', (rng) => {
  const bad = () => pick(rng, [0, -0, -1, -1e-9, -Infinity, Infinity, NaN, null, undefined, '640', '', true, {}, []]);
  const good = () => rng() * 4000 + 1;
  const r = rng();
  return r < 0.4 ? [bad(), good()] : r < 0.8 ? [good(), bad()] : [bad(), bad()];
}, (W, H) => assert.strictEqual(C().sampleSize(W, H), null));

// ---------- glowRect ----------
test('glowRect: examples', () => {
  const { glowRect: gr } = C();
  const r = { left: 100, top: 80, width: 640, height: 360 };
  const close = (got, want) => { for (const k of Object.keys(want)) assert.ok(Math.abs(got[k] - want[k]) < 1e-9, `${k}: ${got[k]} vs ${want[k]}`); };
  close(gr(r, 30), { left: -92, top: -28, width: 1024, height: 576 });
  close(gr(r, 0), r);
  close(gr(r, -10), r);
  close(gr(r, 100), { left: 100 - 384, top: 80 - 216, width: 640 * 2.2, height: 360 * 2.2 });
});
property('glowRect: same centre (1e-6 rel) and size × (1+2s)', (rng) => {
  const f = () => (rng() < 0.2 ? pick(rng, [0, -0, 1e-9, 1e6, -1e6, 0.5]) : (rng() - 0.3) * 4000);
  const size = () => (rng() < 0.2 ? pick(rng, [0, 1, 1e-6, 1e7]) : rng() * 4000);
  const spread = rng() < 0.3 ? pick(rng, [0, -0, -1, 60, 61, 1000, -1e9, 1e9, 0.5, 59.999]) : (rng() - 0.2) * 100;
  return [{ left: f(), top: f(), width: size(), height: size() }, spread];
}, (rect, spread) => {
  const out = C().glowRect(rect, spread);
  const s = clamp(spread, 0, 60) / 100;
  for (const k of ['left', 'top', 'width', 'height']) assert.ok(Number.isFinite(out[k]), `${k} not finite: ${fmt(out[k])}`);
  assert.ok(relClose(out.width, rect.width * (1 + 2 * s), 1e-9), `width ${out.width}`);
  assert.ok(relClose(out.height, rect.height * (1 + 2 * s), 1e-9), `height ${out.height}`);
  const cx = rect.left + rect.width / 2; const cy = rect.top + rect.height / 2;
  assert.ok(relClose(out.left + out.width / 2, cx, 1e-6), `centre x ${out.left + out.width / 2} vs ${cx}`);
  assert.ok(relClose(out.top + out.height / 2, cy, 1e-6), `centre y ${out.top + out.height / 2} vs ${cy}`);
});

// ---------- frameDelay ----------
test('frameDelay: examples', () => {
  const { frameDelay: fd } = C();
  const cases = [[6, 167], [12, 83], [30, 33], [1, 1000], [0, 1000], [-5, 1000], [100, 33], [24, 42], [NaN, 83], [Infinity, 83], [-Infinity, 83]];
  for (const [fps, want] of cases) assert.strictEqual(fd(fps), want, `frameDelay(${fmt(fps)})`);
});
property('frameDelay: always an int in [33,1000]; exact for finite fps', (rng) => [anyVal(rng)], (fps) => {
  const d = C().frameDelay(fps);
  assert.ok(isInt(d) && d >= 33 && d <= 1000, `frameDelay(${fmt(fps)}) = ${fmt(d)}`);
  if (typeof fps === 'number') {
    const want = Number.isFinite(fps) ? Math.round(1000 / clamp(fps, 1, 30)) : 83;
    assert.strictEqual(d, want);
  }
});

// ---------- blendAlpha ----------
test('blendAlpha: examples', () => {
  const { blendAlpha: ba } = C();
  assert.ok(Math.abs(ba(300) - (1 - Math.exp(-1))) < 1e-12);
  assert.strictEqual(ba(0), 0.05);
  assert.strictEqual(ba(1e9), 1);
  assert.strictEqual(ba(-10), 0.05);
  assert.strictEqual(ba(NaN), 0.05);
  assert.strictEqual(ba(Infinity), 0.05);
  assert.strictEqual(ba(50, 0), 1);
  assert.strictEqual(ba(50, -1), 1);
  assert.ok(Math.abs(ba(83, 100) - (1 - Math.exp(-0.83))) < 1e-12);
});
property('blendAlpha: number in [0.05,1] for any dt (tau default or > 0)', (rng) => {
  const tau = rng() < 0.4 ? undefined : pick(rng, [1e-9, 1, 300, 1e9]) * (rng() < 0.5 ? 1 : rng() + 0.01);
  return [anyVal(rng), tau];
}, (dt, tau) => {
  const a = tau === undefined ? C().blendAlpha(dt) : C().blendAlpha(dt, tau);
  assert.ok(typeof a === 'number' && a >= 0.05 && a <= 1, `blendAlpha(${fmt(dt)}, ${fmt(tau)}) = ${fmt(a)}`);
});
property('blendAlpha: exact formula; tau<=0 → 1; negative/non-finite dt → 0.05', (rng) => {
  const r = rng();
  const tau = r < 0.15 ? pick(rng, [0, -0, -1, -300]) : r < 0.3 ? undefined : rng() * 2000 + 1e-3;
  const dt = rng() < 0.2 ? pick(rng, [-1, -1e-9, -Infinity, Infinity, NaN, 0]) : rng() * 5000;
  return [dt, tau];
}, (dt, tau) => {
  const T = tau === undefined ? 300 : tau;
  const a = tau === undefined ? C().blendAlpha(dt) : C().blendAlpha(dt, tau);
  const validDt = Number.isFinite(dt) && dt >= 0;
  if (T <= 0 && validDt) assert.strictEqual(a, 1);
  else if (T > 0 && !validDt) assert.strictEqual(a, 0.05);
  else if (T > 0) assert.ok(Math.abs(a - clamp(1 - Math.exp(-dt / T), 0.05, 1)) < 1e-12, `got ${a}`);
});
property('blendAlpha: monotonic non-decreasing in dt for fixed tau > 0', (rng) => {
  const tau = rng() < 0.2 ? undefined : rng() * 3000 + 1e-3;
  const a = rng() < 0.2 ? pick(rng, [0, 1e-9, 1e6, 1e300]) : rng() * 5000;
  const b = rng() < 0.2 ? a : rng() * 5000;
  return [Math.min(a, b), Math.max(a, b), tau];
}, (lo, hi, tau) => {
  const f = (d) => (tau === undefined ? C().blendAlpha(d) : C().blendAlpha(d, tau));
  assert.ok(f(lo) <= f(hi), `blendAlpha(${lo}) = ${f(lo)} > blendAlpha(${hi}) = ${f(hi)}`);
});

// ---------- shouldRun ----------
const BOOL_KEYS = ['enabled', 'paused', 'ended', 'hidden', 'fullscreen', 'onScreen'];
const VIDEO_W = [0, -0, -1, 1, 0.5, 1e-9, 1920, NaN, Infinity, -Infinity, undefined];
function expectRun(s) {
  return s.enabled && !s.paused && !s.ended && !s.hidden && !s.fullscreen && s.onScreen && s.videoW > 0;
}
test('shouldRun: exhaustive over 2^6 boolean combos × videoW edge values, strict boolean', () => {
  const { shouldRun: sr } = C();
  let count = 0;
  for (let mask = 0; mask < 64; mask++) {
    for (const videoW of VIDEO_W) {
      const s = { videoW };
      BOOL_KEYS.forEach((k, i) => { s[k] = Boolean(mask & (1 << i)); });
      const got = sr(s);
      assert.strictEqual(typeof got, 'boolean', `non-boolean result for ${fmt(s)}: ${fmt(got)}`);
      assert.strictEqual(got, Boolean(expectRun(s)), `shouldRun(${fmt(s)})`);
      count++;
    }
  }
  assert.ok(count >= 500);
});
property('shouldRun: random states (booleans + random videoW)', (rng) => {
  const s = { videoW: rng() < 0.5 ? num(rng) : rng() * 4000 };
  for (const k of BOOL_KEYS) s[k] = rng() < (k === 'enabled' || k === 'onScreen' ? 0.8 : 0.2);
  return [s];
}, (s) => {
  const got = C().shouldRun(s);
  assert.strictEqual(typeof got, 'boolean');
  assert.strictEqual(got, Boolean(expectRun(s)));
});

property('shouldRun: truthy/falsy non-boolean fields still give a strict boolean', (rng) => {
  const vals = [true, false, 0, 1, '', 'yes', null, undefined, {}, [], NaN, -1];
  const s = { videoW: pick(rng, [0, 1, 1920, NaN, undefined, '640', null, -5, Infinity]) };
  for (const k of BOOL_KEYS) s[k] = pick(rng, vals);
  return [s];
}, (s) => {
  const got = C().shouldRun(s);
  assert.strictEqual(typeof got, 'boolean', `non-boolean result: ${fmt(got)}`);
  assert.strictEqual(got, Boolean(expectRun(s)));
});

// ---------- rectChanged ----------
test('rectChanged: examples', () => {
  const { rectChanged: rc } = C();
  const a = { left: 10, top: 20, width: 300, height: 200 };
  assert.strictEqual(rc(a, a), false);
  assert.strictEqual(rc(a, { ...a }), false);
  assert.strictEqual(rc(a, { ...a, left: 10.4 }), false);
  assert.strictEqual(rc(a, { ...a, left: 10.6 }), true);
  assert.strictEqual(rc(a, { ...a, height: 199 }), true);
  assert.strictEqual(rc(a, { ...a, width: 302 }, 3), false);
  assert.strictEqual(rc(a, { ...a, width: 304 }, 3), true);
  for (const x of [null, undefined]) { assert.strictEqual(rc(x, a), true); assert.strictEqual(rc(a, x), true); }
  assert.strictEqual(rc(null, null), true);
  assert.strictEqual(rc(undefined, undefined), true);
});
function rectGen(rng) {
  if (rng() < 0.1) return pick(rng, [null, undefined]);
  const f = () => (rng() < 0.15 ? pick(rng, [0, -0, 0.5, -0.5, 1e6]) : (rng() - 0.3) * 2000);
  return { left: f(), top: f(), width: Math.abs(f()), height: Math.abs(f()) };
}
function nearby(rng, a) {
  if (!a || rng() < 0.2) return rectGen(rng);
  const b = { ...a };
  const k = pick(rng, ['left', 'top', 'width', 'height']);
  b[k] += pick(rng, [0, 0.25, -0.25, 0.49, 0.75, -0.75, 1, -2, 50]);
  return b;
}
property('rectChanged: symmetric, matches definition, identical → false, null → true', (rng) => {
  const a = rectGen(rng);
  const eps = rng() < 0.5 ? undefined : pick(rng, [0, 0.1, 0.5, 1, 3]);
  return [a, nearby(rng, a), eps];
}, (a, b, eps) => {
  const rc = (x, y) => (eps === undefined ? C().rectChanged(x, y) : C().rectChanged(x, y, eps));
  const E = eps === undefined ? 0.5 : eps;
  const ab = rc(a, b);
  assert.strictEqual(typeof ab, 'boolean');
  assert.strictEqual(ab, rc(b, a), 'not symmetric');
  const want = a == null || b == null || ['left', 'top', 'width', 'height'].some((k) => Math.abs(a[k] - b[k]) > E);
  assert.strictEqual(ab, want);
  if (a != null) { assert.strictEqual(rc(a, a), false); assert.strictEqual(rc(a, { ...a }), false); }
  assert.strictEqual(rc(a, null), true);
  assert.strictEqual(rc(undefined, b), true);
});
