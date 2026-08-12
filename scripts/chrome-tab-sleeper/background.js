// [CHANGE: claude-code | 2026-08-11] v3.0 — DECISION 66
// Aggressive tab residency: only the tab you are looking at stays in RAM.
//
// Two things escalate it, both read from the luminos-ram daemon on
// http://127.0.0.1:9091/meminfo (the same number the RAM widget shows):
//
//   1. memory pressure  — effective_available drops → grace shrinks, exemptions drop
//   2. a loaded model   — model_running goes true   → HARD CAP of 2 live tabs
//
// After every sweep it POSTs what it did to http://127.0.0.1:9091/tabs, which is the
// only way anything outside the browser can tell whether tabs were really put to sleep.
// Read it back with `luminos-tabs`.
//
// If the daemon is down this degrades to plain aggressive mode — it never blocks.
//
// ⚠️ HASTE DECISION. The cap is a fixed count, not a measurement. It sleeps the 3rd tab
// whether that tab holds 8 MB or 800 MB, and it does not look at what the model actually
// needs. It was built this way because it is provably correct and shippable in one pass.
// The smart version — rank tabs by real RSS, free only the shortfall — is future work.
// See LUMINOS_DECISIONS.md DECISION 66.

const DEFAULTS = {
  aggressive: true,     // master switch
  graceSeconds: 10,     // how long a tab you just left survives, at normal pressure
  exemptPinned: true,   // pinned tabs survive until CRITICAL
  exemptDirty: true,    // tabs you have typed into survive until CRITICAL
  ramEnabled: true,     // read luminos-ram and escalate under pressure
  pressureGB: 3.0,      // effective_available below this → PRESSURE (grace drops to 0)
  criticalGB: 1.5,      // below this → CRITICAL (pinned/dirty/background-window actives go too)

  // ---- cap mode (new in v3.0) ----
  capEnabled: true,     // enforce a hard live-tab cap when a model is loaded
  capOnPressure: true,  // ...and also when memory alone goes PRESSURE/CRITICAL
  tabCap: 2,            // total tabs allowed to stay in RAM while capped
  audioSlots: 1,        // how many of those the background-audio tab may take
  awaySeconds: 60       // Chrome unfocused this long → even the active tab sleeps (capped only)
};

const MEMINFO_URL = 'http://127.0.0.1:9091/meminfo';
const REPORT_URL = 'http://127.0.0.1:9091/tabs';
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

// Last reading from luminos-ram. `level` and `model` are what the sweep consumes.
let ram = { level: 'normal', effective_available: null, model: false, modelName: '', at: 0, ok: false };

let graceTimer = null;

async function config() {
  return { ...DEFAULTS, ...(await chrome.storage.local.get(DEFAULTS)) };
}

// ---- luminos-ram ---------------------------------------------------------

async function pollRam(cfg) {
  if (!cfg.ramEnabled) {
    ram = { level: 'normal', effective_available: null, model: false, modelName: '', at: Date.now(), ok: false };
    return ram;
  }
  try {
    const r = await fetch(MEMINFO_URL, { cache: 'no-store' });
    const m = await r.json();
    // effective_available already subtracts whatever HIVE has reserved for a model.
    const free = typeof m.effective_available === 'number' ? m.effective_available : m.available;
    const level = free < cfg.criticalGB ? 'critical' : free < cfg.pressureGB ? 'pressure' : 'normal';
    ram = {
      level,
      effective_available: free,
      // The daemon scans /proc for a resident llama-server / .gguf / MoE process.
      // Absent on an old daemon build, which reads as false — the cap just never fires.
      model: m.model_running === true,
      modelName: m.model_name || '',
      at: Date.now(),
      ok: true
    };
  } catch (e) {
    // Daemon not running, or not reachable. Stay aggressive, just stop escalating.
    ram = { level: 'normal', effective_available: null, model: false, modelName: '', at: Date.now(), ok: false };
  }
  return ram;
}

// Tell the outside world what happened. Fire-and-forget: a failed report must never
// stop a sweep, because the sweep is the part that actually saves memory.
async function report(body) {
  try {
    await fetch(REPORT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  } catch (e) { /* daemon down — luminos-tabs will show the report going stale */ }
}

// ---- "is Chrome even in front?" ------------------------------------------

// Asked directly rather than tracked through onFocusChanged events, because the MV3
// worker dies between those events and would come back believing whatever it last saw.
async function focusState() {
  try {
    const w = await chrome.windows.getLastFocused();
    return { id: w ? w.id : chrome.windows.WINDOW_ID_NONE, focused: !!(w && w.focused) };
  } catch (e) {
    return { id: chrome.windows.WINDOW_ID_NONE, focused: false };
  }
}

// How long Chrome has been in the background. Persisted in session storage for the
// same worker-teardown reason as the dirty set.
async function awayFor(focused, now) {
  const { awaySince = 0 } = await chrome.storage.session.get('awaySince');
  if (focused) {
    if (awaySince) await chrome.storage.session.set({ awaySince: 0 });
    return 0;
  }
  if (!awaySince) {
    await chrome.storage.session.set({ awaySince: now });
    return 0;
  }
  return now - awaySince;
}

// ---- policy --------------------------------------------------------------

// Honoured in every mode, cap included: "Never sleep this tab" is a hand instruction,
// and a hand instruction outranks a heuristic. It is the one true escape hatch.
function optedOut(tab) {
  return tab.autoDiscardable === false;
}

// UNCAPPED path. Returns null if the tab should stay resident.
function mayDiscard(tab, { cfg, level, focusedWindowId, dirty, now, grace }) {
  if (tab.discarded) return null;
  if (optedOut(tab)) return null;
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

// CAPPED path. Instead of asking each tab whether it may go, it picks the few that
// stay and everything else goes — which is the only way to enforce a total.
//
// Slots, in order:
//   1. the tab you are actually looking at   (skipped if you have left Chrome for awaySeconds)
//   2. one tab playing audio                 (the background music case)
//   ...any remaining slots go to the most recently used tabs.
//
// Ties on audio are broken by lastAccessed, newest first: if three tabs are making
// noise, the one you most recently opened on purpose is the one that survives.
function pickKeepers(tabs, { cap, audioSlots, focusedWindowId, chromeAway }) {
  const keep = new Set();
  const live = tabs.filter((t) => !t.discarded);

  // Opted-out tabs are kept and are NOT charged against the cap — otherwise ticking
  // "never sleep" on three tabs would silently evict the tab you are reading.
  for (const t of live) if (optedOut(t)) keep.add(t.id);

  if (!chromeAway) {
    const active = live.find((t) => t.active && t.windowId === focusedWindowId);
    if (active) keep.add(active.id);
  }

  const audible = live
    .filter((t) => t.audible && !(t.mutedInfo && t.mutedInfo.muted))
    .sort((a, b) => b.lastAccessed - a.lastAccessed);

  let audioKept = 0;
  for (const t of audible) {
    if (keep.has(t.id)) { audioKept++; continue; }
    if (audioKept >= audioSlots) break;
    if (countingKeepers(keep, live) >= cap) break;
    keep.add(t.id);
    audioKept++;
  }

  // Fill anything left over with the most recently used tabs, so a cap of 3+ is
  // useful rather than leaving slots idle.
  //
  // Skipped entirely when you have left Chrome. Otherwise "I am not using any tab,
  // so all tabs go to sleep" would immediately refill the slot it just freed with
  // the next most recent tab, and nothing would ever sleep.
  if (!chromeAway) {
    const recent = live.slice().sort((a, b) => b.lastAccessed - a.lastAccessed);
    for (const t of recent) {
      if (countingKeepers(keep, live) >= cap) break;
      keep.add(t.id);
    }
  }
  return keep;
}

// Opted-out tabs ride free, so the cap counts only the tabs the policy chose.
function countingKeepers(keep, live) {
  let n = 0;
  for (const t of live) if (keep.has(t.id) && !optedOut(t)) n++;
  return n;
}

async function discardTab(id) {
  try {
    // Discarding replaces the tab object, so this id is stale afterwards.
    await chrome.tabs.discard(id);
    await unmarkDirty(id);
    return true;
  } catch (e) {
    console.warn(`[sleeper] refused ${id}: ${e.message}`);
    return false;
  }
}

async function sweep() {
  const cfg = await config();
  if (!cfg.aggressive) return void updateBadge();

  if (Date.now() - ram.at > RAM_POLL_SECONDS * 1000) await pollRam(cfg);
  const level = ram.level;
  const now = Date.now();
  const { id: focusedWindowId, focused } = await focusState();
  const away = await awayFor(focused, now);

  // The cap is the model's doing first and pressure's second. Both are opt-out.
  const capped = cfg.capEnabled && (ram.model || (cfg.capOnPressure && level !== 'normal'));
  const cap = capped ? Math.max(1, cfg.tabCap) : 0;

  const tabs = await chrome.tabs.query({});
  const dirty = await getDirty();

  // A discard gives the tab a NEW id, orphaning its mark. Prune anything that no
  // longer exists, so the set cannot grow without bound or — worse — start
  // protecting an unrelated tab once Chrome recycles the id.
  const liveIds = new Set(tabs.map((t) => t.id));
  let pruned = false;
  for (const id of dirty) if (!liveIds.has(id)) { dirty.delete(id); pruned = true; }
  if (pruned) await setDirty(dirty);

  let discarded = 0;
  let soonest = Infinity;

  if (capped) {
    // "I am not using any tab, so all tabs go to sleep" — but only after awaySeconds,
    // or a ten-second glance at a terminal would blank the page you are reading.
    const chromeAway = !focused && away >= cfg.awaySeconds * 1000;
    const keep = pickKeepers(tabs, { cap, audioSlots: cfg.audioSlots, focusedWindowId, chromeAway });

    for (const tab of tabs) {
      if (tab.discarded || keep.has(tab.id)) continue;
      if (await discardTab(tab.id)) discarded++;
    }
    // If Chrome just lost focus, come back when the away grace is up rather than
    // waiting for the next 30 s alarm.
    if (!focused && !chromeAway) soonest = cfg.awaySeconds * 1000 - away;
  } else {
    const grace = level === 'normal' ? cfg.graceSeconds * 1000 : 0;
    const ctx = { cfg, level, focusedWindowId, dirty, now, grace };
    for (const tab of tabs) {
      if (mayDiscard(tab, ctx)) {
        if (await discardTab(tab.id)) discarded++;
      } else if (!tab.discarded && !tab.active && grace > 0) {
        // Track when the next tab becomes eligible so short graces fire on time
        // instead of waiting for the coarse alarm.
        soonest = Math.min(soonest, tab.lastAccessed + grace - now);
      }
    }
  }

  scheduleGrace(soonest);
  const counts = await updateBadge();

  await report({
    asleep: counts.asleep,
    awake: counts.awake,
    discarded,
    level,
    model: ram.model,
    cap,
    free_gb: ram.effective_available === null ? 0 : ram.effective_available
  });
}

function scheduleGrace(ms) {
  if (graceTimer) clearTimeout(graceTimer);
  if (!isFinite(ms)) return;
  graceTimer = setTimeout(sweep, Math.max(ms, 250) + 250);
}

// Re-queries rather than reusing the sweep's list, because every discard invalidated it.
async function updateBadge() {
  const tabs = await chrome.tabs.query({});
  const asleep = tabs.filter((t) => t.discarded).length;
  const awake = tabs.length - asleep;
  await chrome.action.setBadgeBackgroundColor({ color: ram.model ? '#b45309' : '#4b5563' });
  await chrome.action.setBadgeText({ text: asleep ? String(asleep) : '' });
  const free = ram.ok && ram.effective_available !== null
    ? ` · ${ram.effective_available.toFixed(1)} GB free (${ram.level})`
    : '';
  const model = ram.model ? ` · MODEL LOADED — capped at ${DEFAULTS.tabCap} tabs` : '';
  await chrome.action.setTitle({ title: `Sleep this tab (Alt+S) — ${asleep} asleep${free}${model}` });
  return { asleep, awake };
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
  await discardTab(tab.id);
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
chrome.tabs.onCreated.addListener(() => sweep());

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
