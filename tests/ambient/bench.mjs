// [CHANGE: claude-code | 2026-10-11]
// Real-browser A/B/C benchmark: no extension vs Ambient light (Shawn's stored settings) vs Luminos Ambient.
// Throwaway Chromium profile, muted. Never touches Shawn's Chrome. Thresholds live in docs/ambient/SPEC.md.
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';

const HOME = os.homedir(), REPO = path.join(HOME, 'luminos-os');
const UPSTREAM = path.join(REPO, '.scratch-ambient/upstream');
const OURS = path.join(REPO, 'scripts/chrome-luminos-ambient');
const AL_ID = 'paponcgjfojgemddooebbgniglhkajkj';
const AL_SETTINGS = path.join(HOME, '.config/google-chrome/Default/Local Extension Settings', AL_ID);
const URL_ = 'https://www.youtube.com/watch?v=' + (process.env.VIDEO || 'yy2UOE4Ab2Q');
const WARM = +(process.env.WARM || 20), WINDOW = +(process.env.WINDOW || 30), ROUNDS = +(process.env.ROUNDS || 2);
const OUT = path.join(REPO, 'docs/ambient/bench'); fs.mkdirSync(OUT, { recursive: true });
const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));
const log = (...a) => { const l = `[${new Date().toISOString().slice(11, 19)}] ${a.join(' ')}`; console.log(l); fs.appendFileSync(path.join(OUT, 'bench.log'), l + '\n'); };

function tree(root) {
  const kids = {};
  for (const p of fs.readdirSync('/proc').filter((d) => /^\d+$/.test(d))) {
    try { const ppid = fs.readFileSync(`/proc/${p}/stat`, 'utf8').split(') ')[1].split(' ')[1]; (kids[ppid] ||= []).push(p); } catch {}
  }
  const out = [], q = [String(root)];
  while (q.length) { const p = q.shift(); out.push(p); q.push(...(kids[p] || [])); }
  return out;
}
function cpuByType(root) {
  const res = {};
  for (const p of tree(root)) {
    try {
      const f = fs.readFileSync(`/proc/${p}/stat`, 'utf8').split(') ')[1].split(' ');
      const cmd = fs.readFileSync(`/proc/${p}/cmdline`, 'utf8');
      const t = (cmd.match(/--type=([a-z-]+)/) || [, 'browser'])[1] + (cmd.includes('--extension-process') ? '(ext)' : '');
      res[t] = (res[t] || 0) + (+f[11] + +f[12]);
    } catch {}
  }
  return res;
}
const ppt = () => { try { return +execFileSync('sensors', [], { encoding: 'utf8' }).match(/PPT:\s+([\d.]+)/)[1]; } catch { return NaN; } };

async function cdp(port) {
  for (let i = 0; i < 40; i++) {
    try {
      const t = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((x) => x.type === 'page' && x.url.includes('youtube'));
      if (t) { const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => ws.onopen = r); let id = 0; const pend = {};
        ws.onmessage = (m) => { const d = JSON.parse(m.data); if (pend[d.id]) { pend[d.id](d.result); delete pend[d.id]; } };
        const send = (method, params = {}) => new Promise((r) => { pend[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
        const ev = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }))?.result?.value;
        return { send, ev, close: () => ws.close() }; }
    } catch {}
    await sleep(0.5);
  }
  throw new Error('no CDP page');
}
const STATE = `(() => { const v = document.querySelector('#movie_player video'); const p = document.querySelector('#movie_player');
  const g = document.getElementById('luminos-ambient-glow'); const vr = v && v.getBoundingClientRect(); const gr = g && g.getBoundingClientRect();
  return { playing: !!v && !v.paused, t: v && +v.currentTime.toFixed(1), vh: v && v.videoHeight, ad: !!p && p.classList.contains('ad-showing'),
    vrect: vr && [vr.width|0, vr.height|0], glow: g && { display: getComputedStyle(g).display, ticks: +g.dataset.ticks, w: gr.width|0, h: gr.height|0, cw: g.width, ch: g.height },
    htmlOn: document.documentElement.classList.contains('luminos-ambient-on'),
    ambientlight: !!document.querySelector('.ambientlight') || !!document.querySelector('#ambient-light') || !!document.querySelector('[class*=ambientlight]') }; })()`;

async function run(cfg, round) {
  const prof = fs.mkdtempSync('/tmp/amb-bench-'), port = 9400 + Math.floor(Math.random() * 400);
  const args = [`--user-data-dir=${prof}`, `--remote-debugging-port=${port}`, '--no-first-run', '--no-default-browser-check',
    '--mute-audio', '--autoplay-policy=no-user-gesture-required', '--ozone-platform=wayland', '--start-maximized',
    '--disable-features=DisableLoadExtensionCommandLineSwitch'];
  if (cfg === 'ambientlight') {
    args.push(`--load-extension=${UPSTREAM}`);
    fs.cpSync(AL_SETTINGS, path.join(prof, 'Default/Local Extension Settings', AL_ID), { recursive: true });
    fs.rmSync(path.join(prof, 'Default/Local Extension Settings', AL_ID, 'LOCK'), { force: true });
  }
  if (cfg === 'luminos') args.push(`--load-extension=${OURS}`);
  // Unpacked extension id = sha256(path) first 32 hex digits mapped 0-f → a-p. Used to set OURS_FPS from the popup page.
  const oursId = [...(await import('node:crypto')).createHash('sha256').update(OURS).digest('hex').slice(0, 32)].map((h) => String.fromCharCode(97 + parseInt(h, 16))).join('');
  const ch = spawn('chromium', [...args, URL_], { stdio: 'ignore', detached: true });
  const r = { cfg, round, oursFps: cfg === 'luminos' ? +(process.env.OURS_FPS || 12) : undefined };
  try {
    const c = await cdp(port);
    if (cfg === 'luminos' && process.env.OURS_FPS) {
      const t = await (await fetch(`http://127.0.0.1:${port}/json/new?chrome-extension://${oursId}/popup.html`, { method: 'PUT' })).json();
      const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => ws.onopen = r); await sleep(1);
      const done = new Promise((r) => ws.onmessage = (m) => r(JSON.parse(m.data)));
      ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { awaitPromise: true, returnByValue: true,
        expression: `chrome.storage.local.set({ luminosAmbient: { enabled: true, spread: 30, intensity: 80, fps: ${+process.env.OURS_FPS} } }).then(() => 'set')` } }));
      r.fpsSet = (await done).result?.result?.value; ws.close();
      await fetch(`http://127.0.0.1:${port}/json/close/${t.id}`);
    }
    await sleep(WARM);
    for (let i = 0; i < 45; i++) {   // ads distort everything: skip or wait them out, max ~90 s
      const ad = await c.ev(`(() => { const p = document.querySelector('#movie_player'); if (!p || !p.classList.contains('ad-showing')) return false;
        const b = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button'); if (b) b.click(); return true; })()`);
      if (!ad) break; await sleep(2);
    }
    await sleep(5);
    await c.ev(`(async () => { const v = document.querySelector('#movie_player video'); if (v && v.paused) { try { await v.play(); } catch {} } })()`);
    await sleep(2);
    r.before = await c.ev(STATE);
    const c0 = cpuByType(ch.pid), p = [];
    for (let i = 0; i < WINDOW / 2; i++) { await sleep(2); p.push(ppt()); }
    const c1 = cpuByType(ch.pid);
    r.after = await c.ev(STATE);
    r.cpu = {}; let tot = 0;
    for (const k of Object.keys(c1)) { const v = ((c1[k] - (c0[k] || 0)) / WINDOW); if (v > 0.2) r.cpu[k] = +v.toFixed(1); tot += v; }
    r.total = +tot.toFixed(1); r.pptAvg = +(p.reduce((a, b) => a + b, 0) / p.length).toFixed(2);
    const shot = await c.send('Page.captureScreenshot', { format: 'png' });
    if (shot?.data) fs.writeFileSync(path.join(OUT, `${cfg}-r${round}.png`), Buffer.from(shot.data, 'base64'));
    if (cfg === 'luminos') {   // T4: pause → ticks frozen
      await c.ev(`document.querySelector('#movie_player video').pause()`); await sleep(1);
      const a = await c.ev(STATE); await sleep(2); const b = await c.ev(STATE);
      r.pause = { ticksA: a.glow?.ticks, ticksB: b.glow?.ticks, display: b.glow?.display, htmlOn: b.htmlOn };
    }
    c.close();
  } catch (e) { r.error = String(e); }
  try { process.kill(-ch.pid, 'SIGTERM'); } catch {}
  await sleep(2); try { process.kill(-ch.pid, 'SIGKILL'); } catch {}
  fs.rmSync(prof, { recursive: true, force: true });
  log(JSON.stringify(r));
  return r;
}

const results = [];
log(`start video=${URL_} warm=${WARM}s window=${WINDOW}s rounds=${ROUNDS}`);
for (let i = 1; i <= ROUNDS; i++) {
  const all = (process.env.CONFIGS || 'baseline,ambientlight,luminos').split(',');
  const order = i % 2 ? all : [...all].reverse();
  for (const cfg of order) {
    let r;   // a run that saw an ad measures the ad, not the glow: redo it (max 3 tries)
    for (let t = 0; t < 3; t++) { r = await run(cfg, i); if (!r.error && !r.before?.ad && !r.after?.ad) break; r.invalid = true; await sleep(5); }
    results.push(r); await sleep(8);
  }
}
fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify(results, null, 1));
log('done');
