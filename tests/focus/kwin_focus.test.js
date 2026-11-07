'use strict';
// [CHANGE: claude-code | 2026-11-07] Tests for the luminos-focus KWin script's pure functions (CONTRACTS §1, §2).
// Run: node --test tests/focus/
const test = require('node:test');
const assert = require('node:assert');

// KWin globals do not exist under node: absorb any top-level wiring the script does on load.
function stub() {
  return new Proxy(function () {}, {
    get: (_, k) => (k === Symbol.toPrimitive ? () => 0 : k === Symbol.iterator ? function* () {} : stub()),
    apply: () => stub(),
    construct: () => stub(),
  });
}
for (const g of ['workspace', 'callDBus', 'print', 'readConfig', 'registerShortcut', 'options', 'KWin', 'QTimer']) {
  if (!(g in globalThis)) globalThis[g] = stub();
}
const m = require('../../config/kwin-scripts/luminos-focus/contents/code/main.js');

// mulberry32: small seeded generator so failures reproduce.
function rng(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const int = (r, lo, hi) => lo + Math.floor(r() * (hi - lo + 1));
const rect = (x, y, width, height) => ({ x, y, width, height });
const randRect = (r, span = 60) => rect(int(r, -10, span), int(r, -10, span), int(r, 0, span), int(r, 0, span));
const area = (a) => Math.max(0, a.width) * Math.max(0, a.height);
function inter(a, b) {
  const x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
  const w = Math.min(a.x + a.width, b.x + b.width) - x, h = Math.min(a.y + a.height, b.y + b.height) - y;
  return w > 0 && h > 0 ? rect(x, y, w, h) : rect(x, y, 0, 0);
}
const contains = (o, i) => i.x >= o.x && i.y >= o.y && i.x + i.width <= o.x + o.width && i.y + i.height <= o.y + o.height;
const OUT = rect(0, 0, 50, 40);
const near = (a, b, msg) => assert.ok(Math.abs(a - b) < 1e-9, `${msg}: ${a} vs ${b}`);

// Brute force on a 1-unit grid: cells of frame∩output not under any coverer, over the WHOLE frame area
// (CONTRACTS Re-plan 1). [CHANGE: claude-code | 2026-11-07]
function bruteFraction(frame, output, coverers) {
  const on = inter(frame, output);
  let seen = 0;
  for (let x = on.x; x < on.x + on.width; x++) {
    for (let y = on.y; y < on.y + on.height; y++) {
      if (!coverers.some((c) => x >= c.x && x < c.x + c.width && y >= c.y && y < c.y + c.height)) seen++;
    }
  }
  return area(frame) ? seen / area(frame) : 0;
}

test('rectArea', () => {
  assert.strictEqual(m.rectArea(rect(3, 4, 10, 20)), 200);
  assert.strictEqual(m.rectArea(rect(0, 0, 0, 20)), 0);
});

test('subtract: disjoint pieces inside r covering exactly r minus cutter', () => {
  const r = rng(1);
  for (let i = 0; i < 3000; i++) {
    const a = randRect(r), c = randRect(r);
    const parts = m.subtract(a, c);
    assert.ok(Array.isArray(parts) && parts.length <= 4, `≤ 4 rects, got ${JSON.stringify(parts)}`);
    let sum = 0;
    parts.forEach((p, j) => {
      assert.ok(p.width >= 0 && p.height >= 0, 'no negative sizes');
      if (area(p) === 0) return;
      assert.ok(contains(a, p), `piece ${JSON.stringify(p)} outside ${JSON.stringify(a)}`);
      assert.strictEqual(area(inter(p, c)), 0, 'piece overlaps the cutter');
      parts.slice(j + 1).forEach((q) => assert.strictEqual(area(inter(p, q)), 0, 'pieces overlap'));
      sum += area(p);
    });
    near(sum, area(a) - area(inter(a, c)), `area of ${JSON.stringify(a)} minus ${JSON.stringify(c)}`);
  }
});

// Denominator = WHOLE frame area (CONTRACTS Re-plan 1). [CHANGE: claude-code | 2026-11-07]
test('visibleFraction properties (seeded random)', () => {
  const r = rng(2);
  for (let i = 0; i < 2000; i++) {
    const frame = randRect(r), covs = Array.from({ length: int(r, 0, 4) }, () => randRect(r));
    const f = m.visibleFraction(frame, OUT, covs), ctx = JSON.stringify({ frame, covs });
    assert.ok(f >= 0 && f <= 1, `in [0,1]: ${f}`);
    near(f, bruteFraction(frame, OUT, covs), `grid count over the whole frame, ${ctx}`);
    const f0 = area(frame) ? area(inter(frame, OUT)) / area(frame) : 0;
    near(m.visibleFraction(frame, OUT, []), f0, `no coverers → on-output area / frame area, ${ctx}`);
    const more = m.visibleFraction(frame, OUT, covs.concat([randRect(r)]));
    assert.ok(more <= f + 1e-9, 'adding a coverer never increases f');
    const big = rect(frame.x - int(r, 0, 5), frame.y - int(r, 0, 5), frame.width + 10, frame.height + 10);
    near(m.visibleFraction(frame, OUT, covs.concat([big])), 0, 'coverer containing the frame → 0');
  }
});

test('visibleFraction: only the on-output part of a window counts', () => {
  const out = rect(0, 0, 1920, 1080), frame = rect(-100, 0, 200, 100); // half off the left edge
  near(m.visibleFraction(frame, out, []), 0.5, 'half off-screen, uncovered');
  near(m.visibleFraction(frame, out, [rect(-100, 0, 100, 100)]), 0.5, 'coverer over the off-output half');
  near(m.visibleFraction(frame, out, [rect(0, 0, 50, 100)]), 0.25, 'half of the on-output part covered');
  near(m.visibleFraction(frame, out, [rect(0, 0, 100, 100)]), 0, 'on-output part covered');
  near(m.visibleFraction(rect(2000, 0, 100, 100), out, []), 0, 'entirely off its output');
  near(m.visibleFraction(rect(10, 10, 0, 100), out, []), 0, 'zero-area window');
});

const win = (pid, frame, o = {}) => ({ pid, active: false, minimized: false, onCurrent: true, frame, output: OUT, ...o });
const snap = (wins, seq = 7) => JSON.parse(m.buildSnapshot(seq, wins));
const byPid = (s) => Object.fromEntries(s.windows.map((w) => [w.pid, w]));

test('buildSnapshot: exact JSON shape', () => {
  assert.strictEqual(typeof m.buildSnapshot(1, []), 'string');
  const s = snap([win(10, rect(0, 0, 10, 10), { active: true }), win(20, rect(20, 0, 10, 10))], 42);
  assert.deepStrictEqual(Object.keys(s).sort(), ['seq', 'v', 'windows']);
  assert.strictEqual(s.v, 1);
  assert.strictEqual(s.seq, 42);
  assert.strictEqual(s.windows.length, 2);
  for (const w of s.windows) {
    assert.deepStrictEqual(Object.keys(w).sort(), ['active', 'f', 'pid']);
    assert.ok(Number.isInteger(w.pid) && typeof w.active === 'boolean' && typeof w.f === 'number');
  }
  assert.deepStrictEqual(byPid(s)[10], { pid: 10, active: true, f: 1 });
  assert.deepStrictEqual(byPid(s)[20], { pid: 20, active: false, f: 1 });
  assert.deepStrictEqual(snap([]).windows, []);
});

test('buildSnapshot: only windows ABOVE cover (bottom→top order)', () => {
  const a = rect(0, 0, 20, 10), b = rect(10, 0, 20, 10);
  let s = byPid(snap([win(10, a), win(20, b)]));
  assert.strictEqual(s[10].f, 0.5);
  assert.strictEqual(s[20].f, 1);
  s = byPid(snap([win(20, b), win(10, a)]));
  assert.strictEqual(s[10].f, 1);
  assert.strictEqual(s[20].f, 0.5);
});

test('buildSnapshot: minimized / off-desktop → f 0 and they cover nothing', () => {
  const a = rect(0, 0, 20, 10);
  for (const o of [{ minimized: true }, { onCurrent: false }]) {
    const s = byPid(snap([win(10, a), win(20, a, o), win(30, a, { ...o, active: true })]));
    assert.strictEqual(s[10].f, 1, `window under a ${JSON.stringify(o)} one stays visible`);
    assert.strictEqual(s[20].f, 0);
    assert.strictEqual(s[30].f, 0);
    assert.strictEqual(s[30].active, true);
  }
});

test('buildSnapshot: f rounded to 3 decimals, pid ≤ 0 dropped, one entry per window', () => {
  const s = snap([
    win(0, rect(40, 30, 5, 5)), win(-1, rect(40, 30, 5, 5)),
    win(10, rect(0, 0, 30, 10)), win(20, rect(0, 10, 30, 10)),
    win(30, rect(0, 0, 10, 10)), win(30, rect(0, 10, 20, 10)), // same pid, two windows
  ]);
  assert.strictEqual(s.windows.length, 4);
  assert.ok(s.windows.every((w) => w.pid > 0), 'pid ≤ 0 must be dropped');
  const fs = s.windows.map((w) => w.f).sort();
  assert.deepStrictEqual(fs, [0.333, 0.667, 1, 1]);
});

// [CHANGE: claude-code | 2026-11-07] Re-plan 1: pid ≤ 0 windows are dropped but still cover; Show Desktop.
test('buildSnapshot: a pid ≤ 0 window is dropped but still covers windows below it', () => {
  const s = snap([win(10, rect(0, 0, 20, 10)), win(0, rect(0, 0, 10, 10)), win(-1, rect(10, 0, 5, 10))]);
  assert.deepStrictEqual(s.windows, [{ pid: 10, active: false, f: 0.25 }]);
});

test('buildSnapshot: Show Desktop (every window onCurrent=false) → every f 0', () => {
  const wins = [win(10, rect(0, 0, 20, 10), { active: true }), win(20, rect(30, 0, 10, 10)), win(30, rect(0, 20, 50, 20))];
  const s = snap(wins.map((w) => ({ ...w, onCurrent: false })));
  assert.strictEqual(s.windows.length, 3);
  assert.ok(s.windows.every((w) => w.f === 0), JSON.stringify(s.windows));
});

test('buildSnapshot: f = round3(grid count over visible windows above) (seeded random)', () => {
  const r = rng(3);
  for (let i = 0; i < 500; i++) {
    const wins = Array.from({ length: int(r, 1, 6) }, (_, j) =>
      win(r() < 0.2 ? -j : 100 + j, randRect(r), { active: r() < 0.2, minimized: r() < 0.2, onCurrent: r() > 0.2 }));
    const s = byPid(snap(wins, i));
    assert.strictEqual(Object.keys(s).length, wins.filter((w) => w.pid > 0).length, 'one entry per pid > 0 window');
    wins.forEach((w, j) => {
      if (w.pid <= 0) return;
      const cov = wins.slice(j + 1).filter((u) => !u.minimized && u.onCurrent).map((u) => u.frame);
      const f = w.minimized || !w.onCurrent ? 0 : Math.round(bruteFraction(w.frame, OUT, cov) * 1000) / 1000;
      near(s[w.pid].f, f, `window ${j} of ${JSON.stringify(wins)}`);
      assert.strictEqual(s[w.pid].active, w.active);
      assert.ok(Math.abs(s[w.pid].f * 1000 - Math.round(s[w.pid].f * 1000)) < 1e-9, '3 decimals');
    });
  }
});
