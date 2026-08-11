// [CHANGE: claude-code | 2026-08-11]
// Aggressive tab residency: only the tab you are looking at stays in RAM.
//
// Escalates with real memory pressure read from the luminos-ram daemon
// (http://127.0.0.1:9091/meminfo), which is the same number the RAM widget shows.
// If the daemon is down this degrades to plain aggressive mode — it never blocks.

const DEFAULTS = {
  aggressive: true,     // master switch
  graceSeconds: 10,     // how long a tab you just left survives, at normal pressure
  exemptPinned: true,   // pinned tabs survive until CRITICAL
  exemptDirty: true,    // tabs you have typed into survive until CRITICAL
  ramEnabled: true,     // read luminos-ram and escalate under pressure
  pressureGB: 3.0,      // effective_available below this → PRESSURE (grace drops to 0)
  criticalGB: 1.5       // below this → CRITICAL (pinned/dirty/background-window actives go too)
};

const MEMINFO_URL = 'http://127.0.0.1:9091/meminfo';
const RAM_POLL_SECONDS = 20;

// Tabs the user has typed into. Chrome's discard does not run beforeunload, so
// without this an aggressive sweep silently throws away half-written comments.
//
// This MUST NOT be a plain in-memory Set. An MV3 service worker is torn down after
// ~30 s idle and respawned on the next event, which would wipe every mark and take
// the protection with it — silently, and only in production, because a worker being
// actively debugged never idles long enough to die. chrome.storage.session survives
// the worker, stays in memory, and is cleared when the browser closes.
async function getDirty() {
  const { dirty = [] } = await chrome.storage.session.get('dirty');
  return new Set(dirty);
}

async function setDirty(set) {
  await chrome.storage.session.set({ dirty: [...set] });
}

async function markDirty(tabId) {
  const s = await getDirty();
  if (s.has(tabId)) return;
  s.add(tabId);
  await setDirty(s);
}

async function unmarkDirty(tabId) {
  const s = await getDirty();
  if (s.delete(tabId)) await setDirty(s);
}

// Last reading from luminos-ram. `level` is what the sweep actually consumes.
let ram = { level: 'normal', effective_available: null, at: 0, ok: false };

let graceTimer = null;

async function config() {
  return { ...DEFAULTS, ...(await chrome.storage.local.get(DEFAULTS)) };
}

// ---- luminos-ram ---------------------------------------------------------

async function pollRam(cfg) {
  if (!cfg.ramEnabled) {
    ram = { level: 'normal', effective_available: null, at: Date.now(), ok: false };
    return ram;
  }
  try {
    const r = await fetch(MEMINFO_URL, { cache: 'no-store' });
    const m = await r.json();
    // effective_available already subtracts whatever HIVE has reserved for a model.
    const free = typeof m.effective_available === 'number' ? m.effective_available : m.available;
    const level = free < cfg.criticalGB ? 'critical' : free < cfg.pressureGB ? 'pressure' : 'normal';
    ram = { level, effective_available: free, at: Date.now(), ok: true };
  } catch (e) {
    // Daemon not running, or not reachable. Stay aggressive, just stop escalating.
    ram = { level: 'normal', effective_available: null, at: Date.now(), ok: false };
  }
  return ram;
}

// ---- policy --------------------------------------------------------------

// Returns null if the tab should stay resident, otherwise the reason it may go.
function mayDiscard(tab, { cfg, level, focusedWindowId, dirty, now, grace }) {
  if (tab.discarded) return null;
  if (!tab.autoDiscardable) return null;                       // per-tab opt-out, always honoured
  if (tab.audible && !(tab.mutedInfo && tab.mutedInfo.muted)) return null;  // playing sound

  // The active tab of each window normally stays — a discarded tab that is still
  // in front is a blank page. Under CRITICAL only the focused window keeps one.
  if (tab.active) {
    if (level !== 'critical') return null;
    if (tab.windowId === focusedWindowId) return null;
  }

  if (cfg.exemptPinned && tab.pinned && level !== 'critical') return null;
  if (cfg.exemptDirty && dirty.has(tab.id) && level !== 'critical') return null;

  if (now - tab.lastAccessed < grace) return null;
  return 'eligible';
}

async function focusedWindow() {
  try {
    const w = await chrome.windows.getLastFocused();
    return w ? w.id : chrome.windows.WINDOW_ID_NONE;
  } catch (e) {
    return chrome.windows.WINDOW_ID_NONE;
  }
}

async function sweep() {
  const cfg = await config();
  if (!cfg.aggressive) return void updateBadge();

  if (Date.now() - ram.at > RAM_POLL_SECONDS * 1000) await pollRam(cfg);
  const level = ram.level;
  const grace = level === 'normal' ? cfg.graceSeconds * 1000 : 0;
  const focusedWindowId = await focusedWindow();
  const now = Date.now();

  const tabs = await chrome.tabs.query({});
  const dirty = await getDirty();

  // A discard gives the tab a NEW id, orphaning its mark. Prune anything that no
  // longer exists, so the set cannot grow without bound or — worse — start
  // protecting an unrelated tab once Chrome recycles the id.
  const live = new Set(tabs.map((t) => t.id));
  let pruned = false;
  for (const id of dirty) if (!live.has(id)) { dirty.delete(id); pruned = true; }
  if (pruned) await setDirty(dirty);

  const ctx = { cfg, level, focusedWindowId, dirty, now, grace };

  let soonest = Infinity;
  for (const tab of tabs) {
    if (mayDiscard(tab, ctx)) {
      try {
        // Discarding replaces the tab object, so tab.id is stale afterwards.
        await chrome.tabs.discard(tab.id);
        await unmarkDirty(tab.id);
      } catch (e) {
        console.warn(`[sleeper] refused ${tab.id}: ${e.message}`);
      }
    } else if (!tab.discarded && !tab.active && grace > 0) {
      // Track when the next tab becomes eligible so short graces fire on time
      // instead of waiting for the coarse alarm.
      soonest = Math.min(soonest, tab.lastAccessed + grace - now);
    }
  }
  scheduleGrace(soonest);
  updateBadge();
}

function scheduleGrace(ms) {
  if (graceTimer) clearTimeout(graceTimer);
  if (!isFinite(ms)) return;
  graceTimer = setTimeout(sweep, Math.max(ms, 250) + 250);
}

async function updateBadge() {
  const tabs = await chrome.tabs.query({});
  const asleep = tabs.filter((t) => t.discarded).length;
  await chrome.action.setBadgeBackgroundColor({ color: '#4b5563' });
  await chrome.action.setBadgeText({ text: asleep ? String(asleep) : '' });
  const free = ram.ok && ram.effective_available !== null
    ? ` · ${ram.effective_available.toFixed(1)} GB free (${ram.level})`
    : '';
  await chrome.action.setTitle({ title: `Sleep this tab (Alt+S) — ${asleep} asleep${free}` });
}

// ---- manual actions ------------------------------------------------------

// Deliberately ignores every guard above: if you asked for it by hand, you get it.
async function sleepTab(tab) {
  if (!tab || tab.discarded) return;
  if (tab.active) {
    // Hand focus to the nearest live neighbour first, or you are left on a blank page.
    const siblings = await chrome.tabs.query({ windowId: tab.windowId, discarded: false });
    const next = siblings
      .filter((t) => t.id !== tab.id)
      .sort((a, b) => Math.abs(a.index - tab.index) - Math.abs(b.index - tab.index))[0];
    if (next) await chrome.tabs.update(next.id, { active: true });
  }
  try {
    await chrome.tabs.discard(tab.id);
  } catch (e) {
    console.warn(`[sleeper] refused ${tab.id}: ${e.message}`);
  }
  updateBadge();
}

chrome.action.onClicked.addListener(sleepTab);

chrome.commands.onCommand.addListener(async (command) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (command === 'sleep-current-tab') await sleepTab(tab);
  else if (command === 'sleep-other-tabs') await sleepOthers(tab);
});

async function sleepOthers(tab) {
  if (!tab) return;
  for (const t of await chrome.tabs.query({ windowId: tab.windowId })) {
    if (t.id !== tab.id) await sleepTab(t);
  }
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'sleep-tab') await sleepTab(tab);
  else if (info.menuItemId === 'sleep-others') await sleepOthers(tab);
  else if (info.menuItemId === 'never-sleep') {
    await chrome.tabs.update(tab.id, { autoDiscardable: !info.checked });
  }
});

// ---- dirty-tab tracking --------------------------------------------------

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg && msg.type === 'dirty' && sender.tab) markDirty(sender.tab.id);
});

// A navigation replaces the page, so whatever was typed is already gone.
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === 'loading') unmarkDirty(tabId);
  if (change.discarded) updateBadge();
});
chrome.tabs.onRemoved.addListener((tabId) => unmarkDirty(tabId));

// ---- triggers ------------------------------------------------------------

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  // Keep the checkbox honest — its state is global, so re-point it at this tab.
  try {
    const tab = await chrome.tabs.get(tabId);
    await chrome.contextMenus.update('never-sleep', { checked: !tab.autoDiscardable });
  } catch (e) { /* menu not built yet */ }
  await sweep();
});
chrome.windows.onFocusChanged.addListener(sweep);
chrome.tabs.onCreated.addListener(() => updateBadge());

// Backstop for anything the event path misses, and for after the MV3 service
// worker has been unloaded and respawned.
chrome.alarms.create('sweep', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(sweep);
chrome.runtime.onStartup.addListener(sweep);

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'sleep-tab', title: 'Sleep this tab', contexts: ['tab'] });
  chrome.contextMenus.create({ id: 'sleep-others', title: 'Sleep other tabs', contexts: ['tab'] });
  chrome.contextMenus.create({ id: 'never-sleep', title: 'Never sleep this tab', type: 'checkbox', contexts: ['tab'] });
  sweep();
});
