// [CHANGE: claude-code | 2026-08-11]
// Marks a tab as "you typed in this" so an aggressive sweep will not throw it away.
//
// This exists because chrome.tabs.discard() does NOT run beforeunload — a tab with a
// half-written comment in it is discarded silently, with no prompt and no recovery.
// Chrome's own Memory Saver does the same check; we have to do it ourselves.

let reported = false;

function report() {
  if (reported) return;
  reported = true;
  try {
    chrome.runtime.sendMessage({ type: 'dirty' });
  } catch (e) {
    // Extension reloaded out from under the page; nothing to do.
  }
}

// Capture phase so it still fires inside components that stop propagation.
// Not `change` — that only fires on blur, which is too late for a tab switch.
addEventListener('input', report, { capture: true, passive: true });

// [CHANGE: claude-code | 2026-10-15] BUG-198 — runaway guard for YouTube watch pages.
// On 2026-10-15 a YouTube autoplay tab leaked (renderer 510 MB → 1.4 GB) until its main thread sat at
// 100 % of a core and heated the laptop. Measured healthy page: JS heap ~120 MB, long tasks ~0.5 % of the
// time. So: memory over 600 MB, or long tasks over 50 % for two minutes in a row → ask the background
// to reload this tab at the same spot in the video. Long tasks only count tasks over 50 ms; a runaway built
// from many short tasks would not register here, and the heap check is what catches the leak itself.
const GUARD = { windowMs: 60000, busyLimit: 0.5, strikes: 2, heapLimit: 600 * 1048576 };

function startRunawayGuard() {
  let busy = 0, strikes = 0, last = performance.now();
  try {
    new PerformanceObserver((list) => { for (const e of list.getEntries()) busy += e.duration; })
      .observe({ type: 'longtask' });
  } catch (e) { return; } // no long-task support: stay out of the way
  setInterval(() => {
    const now = performance.now(), frac = busy / Math.max(1, now - last);
    busy = 0; last = now;
    if (!location.pathname.startsWith('/watch')) { strikes = 0; return; }
    strikes = frac >= GUARD.busyLimit ? strikes + 1 : 0;
    const heap = (performance.memory && performance.memory.usedJSHeapSize) || 0;
    const reason = heap > GUARD.heapLimit ? `JS heap ${Math.round(heap / 1048576)} MB`
      : strikes >= GUARD.strikes ? `main thread ${Math.round(frac * 100)}% busy for ${strikes} min` : null;
    if (!reason || reported) return; // never reload a tab the user has typed into
    strikes = 0;
    const v = document.querySelector('#movie_player video');
    try {
      chrome.runtime.sendMessage({ type: 'runaway', reason, t: v ? Math.floor(v.currentTime) : 0 });
    } catch (e) { /* extension reloaded; nothing to do */ }
  }, GUARD.windowMs);
}

if (location.hostname === 'www.youtube.com' && window.top === window) startRunawayGuard();
