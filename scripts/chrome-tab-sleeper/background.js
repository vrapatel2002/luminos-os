// [CHANGE: claude-code | 2026-08-07]
// Full manual control over when a background tab is unloaded.
// Chrome's own Memory Saver has a 5 minute floor in its UI; this has none.

// ---- the two lines you actually tune -------------------------------------
const AUTO_SLEEP = false;   // true = also sleep tabs automatically, on a timer
const IDLE_SECONDS = 60;    // how long a tab sits unused before AUTO_SLEEP fires
// --------------------------------------------------------------------------

const sweepTimers = new Map();

// Manual sleep. Deliberately ignores the automatic-path guards: if you asked
// for it by hand, you get it.
async function sleepTab(tab) {
  if (!tab || tab.discarded) return;
  if (tab.active) {
    // A discarded tab that is still in front just shows a blank page, so hand
    // focus to the nearest live neighbour before unloading this one.
    const siblings = await chrome.tabs.query({ windowId: tab.windowId, discarded: false });
    const next = siblings
      .filter((t) => t.id !== tab.id)
      .sort((a, b) => Math.abs(a.index - tab.index) - Math.abs(b.index - tab.index))[0];
    if (next) await chrome.tabs.update(next.id, { active: true });
  }
  try {
    // Note: discarding replaces the tab, so tab.id is stale after this point.
    await chrome.tabs.discard(tab.id);
  } catch (e) {
    console.warn(`[sleeper] refused ${tab.id}: ${e.message}`);
  }
}

chrome.action.onClicked.addListener(sleepTab);

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== 'sleep-current-tab') return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await sleepTab(tab);
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'sleep-tab') {
    await sleepTab(tab);
  } else if (info.menuItemId === 'sleep-others') {
    for (const t of await chrome.tabs.query({ windowId: tab.windowId })) {
      if (t.id !== tab.id) await sleepTab(t);
    }
  }
});

// ---- automatic path ------------------------------------------------------

function eligible(tab, now) {
  if (tab.active || tab.discarded) return false;
  if (tab.audible) return false;
  if (!tab.autoDiscardable) return false;          // per-tab opt-out still honoured
  if (tab.pinned) return false;
  return now - tab.lastAccessed >= IDLE_SECONDS * 1000;
}

async function sweep() {
  if (!AUTO_SLEEP) return;
  const now = Date.now();
  for (const tab of await chrome.tabs.query({})) {
    if (!eligible(tab, now)) continue;
    try {
      await chrome.tabs.discard(tab.id);
      console.log(`[sleeper] slept ${tab.id} after ${((now - tab.lastAccessed) / 1000).toFixed(1)}s idle`);
    } catch (e) {
      console.warn(`[sleeper] refused ${tab.id}: ${e.message}`);
    }
  }
}

// Switching away from a tab starts that tab's own countdown, so short
// timeouts fire on time instead of waiting for the next coarse sweep.
chrome.tabs.onActivated.addListener(({ tabId, windowId }) => {
  if (!AUTO_SLEEP) return;
  chrome.tabs.query({ windowId }, (tabs) => {
    for (const tab of tabs) {
      if (tab.id === tabId) continue;
      if (sweepTimers.has(tab.id)) clearTimeout(sweepTimers.get(tab.id));
      sweepTimers.set(tab.id, setTimeout(() => {
        sweepTimers.delete(tab.id);
        sweep();
      }, IDLE_SECONDS * 1000 + 250));
    }
  });
});

// Backstop for anything the event path misses, and for after the MV3
// service worker has been unloaded and respawned.
chrome.alarms.create('sweep', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(sweep);
chrome.runtime.onStartup.addListener(sweep);

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'sleep-tab', title: 'Sleep this tab', contexts: ['tab'] });
  chrome.contextMenus.create({ id: 'sleep-others', title: 'Sleep other tabs', contexts: ['tab'] });
  sweep();
});
