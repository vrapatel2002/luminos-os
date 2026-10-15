// [CHANGE: claude-code | 2026-10-15] BUG-198 — live end-to-end test of the runaway guard in a throwaway
// Chromium on real YouTube. Never touches Shawn's Chrome or luminos-ram (host_permissions stripped from the copy).
// Run via: systemd-run --user … node test-runaway-live.mjs heap|busy   (takes 1–3 min, longer than a host-shell call)
import { spawn } from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path';
const mode = process.argv[2] || 'heap';
const SRC = path.dirname(new URL(import.meta.url).pathname);
const ext = fs.mkdtempSync('/tmp/ts-ext-'), prof = fs.mkdtempSync('/tmp/ts-prof-'), port = 9500 + Math.floor(Math.random() * 300);
for (const f of ['manifest.json', 'background.js', 'content.js', 'options.html', 'options.js']) fs.copyFileSync(path.join(SRC, f), path.join(ext, f));
const m = JSON.parse(fs.readFileSync(path.join(ext, 'manifest.json'))); delete m.host_permissions; fs.writeFileSync(path.join(ext, 'manifest.json'), JSON.stringify(m));
const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));
const log = (...a) => console.log(`[${new Date().toISOString().slice(11, 19)}] [${mode}]`, ...a);
const ch = spawn('chromium', [`--user-data-dir=${prof}`, `--remote-debugging-port=${port}`, '--no-first-run', '--no-default-browser-check', '--mute-audio',
  '--autoplay-policy=no-user-gesture-required', '--ozone-platform=wayland', '--disable-features=DisableLoadExtensionCommandLineSwitch',
  `--load-extension=${ext}`, 'https://www.youtube.com/watch?v=aSugSGCC12I&list=RDaSugSGCC12I'], { stdio: 'ignore', detached: true });
async function page() { for (let i = 0; i < 40; i++) { try { const t = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((x) => x.type === 'page' && x.url.includes('youtube')); if (t) return t; } catch {} await sleep(0.5); } }
async function evalIn(t, expression) { const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => ws.onopen = r);
  const p = new Promise((r) => ws.onmessage = (e) => r(JSON.parse(e.data))); ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
  const v = (await p).result?.result?.value; ws.close(); return v; }
let result = 'FAIL';
try {
  await sleep(25);
  const t = await page();
  const before = await evalIn(t, `(() => { const v=document.querySelector('#movie_player video'); return { url: location.href, t: v && Math.floor(v.currentTime) }; })()`);
  log('before', JSON.stringify(before));
  const load = mode === 'none' ? `'nothing (healthy page)'` : mode === 'heap'
    ? `(() => { window.__leak = []; for (let i = 0; i < 70; i++) window.__leak.push(new Array(1250000).fill(i + 0.5)); return Math.round(performance.memory.usedJSHeapSize/1048576) + ' MB'; })()`
    : `(() => { window.__burn = setInterval(() => { const e = performance.now() + 70; while (performance.now() < e); }, 100); return 'burning 70%'; })()`;
  log('inject', await evalIn(t, load));
  const t0 = Date.now(), limit = mode === 'heap' ? 80 : mode === 'none' ? 150 : 200;
  if (mode === 'none') result = 'PASS';   // a healthy page must survive the whole window
  while ((Date.now() - t0) / 1000 < limit) {
    await sleep(5);
    const p = await page(); if (!p) continue;
    const st = await evalIn(p, `({ url: location.href, leak: !!window.__leak, burn: !!window.__burn })`).catch(() => null);
    if (st && new URL(st.url).searchParams.has('t') && (mode === 'none' || (!st.leak && !st.burn))) { const s = Math.round((Date.now() - t0) / 1000); log(`RELOADED after ${s}s →`, st.url); // Busy needs two consecutive 60 s windows ≥ 50 %; the first window may be partly before the burn started,
    // so the guarantee is: never under 60 s of burning, always within 180 s.
    result = mode === 'none' ? 'FAIL (reloaded a healthy page)' : mode === 'busy' && s < 60 ? 'FAIL (reloaded on a single short burst)' : 'PASS'; break; }
  }
} catch (e) { log('error', String(e)); }
log('RESULT', result);
try { process.kill(-ch.pid, 'SIGKILL'); } catch {}
fs.rmSync(prof, { recursive: true, force: true }); fs.rmSync(ext, { recursive: true, force: true });
