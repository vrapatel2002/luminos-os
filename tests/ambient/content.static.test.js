'use strict';
// Static checks on the extension source as text (CONTRACTS.md + SPEC.md design rules).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { lex } = require('./jsscan.js');

const DIR = path.join(__dirname, '../../scripts/chrome-luminos-ambient');
function read(name) {
  const p = path.join(DIR, name);
  if (!fs.existsSync(p)) assert.fail(`source file missing: ${p}`);
  return fs.readFileSync(p, 'utf8');
}
function manifest() {
  const txt = read('manifest.json');
  try { return JSON.parse(txt); } catch (e) { return assert.fail(`manifest.json is not valid JSON: ${e.message}`); }
}

test('manifest: valid JSON, MV3', () => {
  assert.strictEqual(manifest().manifest_version, 3);
});

test('manifest: permissions exactly ["storage"], no host_permissions, no background', () => {
  const m = manifest();
  assert.deepStrictEqual(m.permissions, ['storage']);
  assert.ok(!('host_permissions' in m) || (Array.isArray(m.host_permissions) && m.host_permissions.length === 0),
    `host_permissions must be absent: ${JSON.stringify(m.host_permissions)}`);
  assert.ok(!('optional_host_permissions' in m), 'optional_host_permissions must be absent');
  assert.ok(!('background' in m), `background must be absent: ${JSON.stringify(m.background)}`);
});

test('manifest: content_scripts load core.js then content.js on youtube.com only', () => {
  const cs = manifest().content_scripts;
  assert.ok(Array.isArray(cs) && cs.length > 0, 'content_scripts missing/empty');
  for (const entry of cs) {
    assert.deepStrictEqual(entry.js, ['core.js', 'content.js']);
    assert.ok(Array.isArray(entry.matches) && entry.matches.length > 0, 'matches missing');
    for (const pat of entry.matches) {
      assert.match(pat, /^https:\/\/(www\.)?youtube\.com\/.*$/, `match pattern outside youtube.com: ${pat}`);
    }
    const ex = [].concat(entry.exclude_matches || [], entry.exclude_globs || []);
    assert.ok(ex.some((p) => p.includes('live_chat')), `live_chat not excluded: ${JSON.stringify(ex)}`);
    assert.ok(ex.some((p) => p.includes('/embed/')), `/embed/ not excluded: ${JSON.stringify(ex)}`);
  }
});

test('manifest: popup is popup.html', () => {
  const m = manifest();
  assert.strictEqual(m.action && m.action.default_popup, 'popup.html');
});

const FORBIDDEN = [
  ['requestAnimationFrame', /\brequestAnimationFrame\b/],
  ['getImageData', /\bgetImageData\b/],
  ['readPixels', /\breadPixels\b/],
  ["getContext('webgl…')", /getContext\s*\(\s*['"`][^'"`]*webgl/i],
  ['webgl2', /webgl2/i],
  ['WebGLRenderingContext', /\bWebGL\w*RenderingContext\b/],
  ['MutationObserver', /\bMutationObserver\b/],
  ['setInterval', /\bsetInterval\b/],
];

for (const [label, re] of FORBIDDEN) {
  test(`content.js: does not use ${label}`, () => {
    const { noComments } = lex(read('content.js'));
    const m = re.exec(noComments);
    const line = m ? noComments.slice(0, m.index).split('\n').length : 0;
    assert.ok(!m, `content.js uses forbidden ${label} at line ${line}`);
  });
}

test('content.js: no CSS filter on elements (ctx.filter on a 2D context is allowed)', () => {
  const { code, noComments, strings } = lex(read('content.js'));
  const hits = [];
  if (/\bstyle\s*(?:\.\s*|\[\s*['"`])(?:webkit|backdrop)?filter\b/i.test(noComments)) hits.push('element .style.filter');
  if (/setProperty\s*\(\s*['"`](?:-webkit-)?(?:backdrop-)?filter['"`]/i.test(noComments)) hits.push("style.setProperty('filter')");
  if (/(?:^|[^\w$.])(?:webkitFilter|backdropFilter|filter)\s*:/.test(code)) hits.push('object key filter: (style object)');
  for (const s of strings) {
    if (/(?:^|[^\w])(?:-webkit-)?(?:backdrop-)?filter\s*:/i.test(s.text)) hits.push(`CSS "filter:" in string at line ${s.line}`);
  }
  assert.deepStrictEqual(hits, [], `content.js applies a CSS filter: ${hits.join('; ')}`);
});

const REQUIRED = [
  ["'luminos-ambient-glow'", /luminos-ambient-glow/],
  ["'luminos-ambient-on'", /luminos-ambient-on/],
  ['dataset.ticks', /dataset\s*(?:\.\s*ticks\b|\[\s*['"`]ticks['"`]\s*\])/],
  ['IntersectionObserver', /\bIntersectionObserver\b/],
  ['visibilitychange', /visibilitychange/],
  ['fullscreenchange', /fullscreenchange/],
  ['chrome.storage.onChanged', /chrome\s*\.\s*storage\s*\.\s*onChanged\b/],
  ['pointer-events', /pointer-events|pointerEvents/],
  ['chrome.runtime.id (orphan check)', /chrome\s*\.\s*runtime\s*\.\s*id\b|runtime\s*\?\.\s*id\b/],
  ['will-change: transform or a GPU transform (translateZ / translate3d)',
    /will-change\s*:\s*transform|willChange\s*=\s*['"`]transform|setProperty\s*\(\s*['"`]will-change['"`]\s*,\s*['"`]transform|translateZ\s*\(|translate3d\s*\(/],
  ['ytd-miniplayer', /ytd-miniplayer/],
];

for (const [label, re] of REQUIRED) {
  test(`content.js: references ${label}`, () => {
    const { noComments } = lex(read('content.js'));
    assert.match(noComments, re, `content.js never references ${label} (outside comments)`);
  });
}

test('popup.html: no inline script code, no inline handlers, loads popup.js', () => {
  const html = read('popup.html');
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
  assert.ok(scripts.length > 0, 'popup.html has no <script src=...>');
  for (const [tag, attrs, body] of scripts) {
    assert.match(attrs, /\bsrc\s*=/i, `inline <script> without src: ${tag.slice(0, 80)}`);
    assert.strictEqual(body.trim(), '', `<script src> must have an empty body: ${tag.slice(0, 80)}`);
  }
  assert.ok(scripts.some(([, a]) => /src\s*=\s*['"]?popup\.js/i.test(a)), 'popup.html does not load popup.js');
  const handler = /<[^>]*\son[a-z]+\s*=/i.exec(html);
  assert.ok(!handler, `inline event handler attribute (blocked by MV3 CSP): ${handler && handler[0]}`);
  assert.ok(!/javascript:/i.test(html), 'javascript: URL in popup.html (blocked by MV3 CSP)');
});

test('popup.js: no CSP-blocked constructs (eval, new Function, string timers)', () => {
  const { noComments } = lex(read('popup.js'));
  assert.ok(!/\beval\s*\(/.test(noComments), 'popup.js uses eval');
  assert.ok(!/\bnew\s+Function\b|\bFunction\s*\(/.test(noComments), 'popup.js uses Function constructor');
  assert.ok(!/\bset(?:Timeout|Interval)\s*\(\s*['"`]/.test(noComments), 'popup.js passes a string to a timer');
  assert.ok(!/\.\s*innerHTML\s*=[^=][^;]*<script/i.test(noComments), 'popup.js injects a <script> via innerHTML');
});
