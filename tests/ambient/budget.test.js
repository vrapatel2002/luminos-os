'use strict';
// Budgets from CONTRACTS.md: each file <= 150 lines, total <= 400, function <= 40 lines,
// block nesting inside a function <= 3 beyond the body. A module-wrapper IIFE is exempt from the
// line limit only (same as ESLint max-lines-per-function's IIFEs:false default); its nesting is checked.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { scanFunctions, countLines } = require('./jsscan.js');

const DIR = path.join(__dirname, '../../scripts/chrome-luminos-ambient');
const FILES = ['manifest.json', 'core.js', 'content.js', 'popup.html', 'popup.js'];
const JS = ['core.js', 'content.js', 'popup.js'];
const MAX_FILE = 150;
const MAX_TOTAL = 400;
const MAX_FN = 40;
const MAX_DEPTH = 3;

function read(name) {
  const p = path.join(DIR, name);
  if (!fs.existsSync(p)) assert.fail(`source file missing: ${p}`);
  return fs.readFileSync(p, 'utf8');
}

test('scanner self-check (guards the checker itself)', () => {
  const sample = [
    'function a(x) {',
    '  if (x) {',
    '    for (;;) {',
    '      while (x) { x--; }',
    '    }',
    '  }',
    '  const s = "{{{"; const t = `${ {a:1}.a } }}`; const r = /\\{[}]/g;',
    '  return { k: () => { return 1; } };',
    '}',
    'const b = async (y) => {',
    '  return y / 2 / 3;',
    '};',
    'class C { m() { return 1; } get g() { return 2; } }',
    'const o = { f() { if (1) { if (2) { if (3) { if (4) {} } } } } };',
    "// function z() { if (1) { if (2) { if (3) { if (4) {} } } } }",
    '(function () {',
    '  const q = (() => { return 1; })();',
    '})();',
  ].join('\n');
  const got = scanFunctions(sample).map((f) => [f.name, f.lines, f.maxDepth, f.iife]);
  assert.deepStrictEqual(got, [['a', 9, 3, false], ['k', 1, 0, false], ['b', 3, 0, false], ['m', 1, 0, false],
    ['g', 1, 0, false], ['f', 1, 4, false], ['<function>', 3, 0, true], ['<arrow>', 1, 0, true]]);
});

for (const f of FILES) {
  test(`${f}: <= ${MAX_FILE} lines`, () => {
    const n = countLines(read(f));
    assert.ok(n <= MAX_FILE, `${f} has ${n} lines (budget ${MAX_FILE})`);
  });
}

test(`all extension files together <= ${MAX_TOTAL} lines`, () => {
  const per = FILES.map((f) => [f, countLines(read(f))]);
  const total = per.reduce((a, [, n]) => a + n, 0);
  assert.ok(total <= MAX_TOTAL, `total ${total} lines (budget ${MAX_TOTAL}): ${JSON.stringify(per)}`);
});

for (const f of JS) {
  test(`${f}: every function <= ${MAX_FN} lines and nesting <= ${MAX_DEPTH}`, () => {
    const fns = scanFunctions(read(f));
    const bad = [];
    for (const fn of fns) {
      if (fn.endLine === undefined) bad.push(`${fn.name} @${fn.startLine}: unbalanced braces`);
      else if (fn.lines > MAX_FN && !fn.iife) bad.push(`${fn.name} @${fn.startLine}: ${fn.lines} lines (max ${MAX_FN})`);
      if (fn.maxDepth > MAX_DEPTH) bad.push(`${fn.name} @${fn.startLine}: nesting ${fn.maxDepth} (max ${MAX_DEPTH})`);
    }
    assert.deepStrictEqual(bad, [], `${f} over budget:\n  ${bad.join('\n  ')}`);
  });
}
