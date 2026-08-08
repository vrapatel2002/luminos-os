// [CHANGE: claude-code | 2026-08-07]
// Full manual control over when a background tab is unloaded.
// Chrome's own Memory Saver has a 5 minute floor in its UI; this has none.

// ---- the line you actually tune ------------------------------------------
const IDLE_SECONDS = 10;   // 0 = discard the instant you switch away
const DISCARD_PINNED = false;
// --------------------------------------------------------------------------

const sweepTimers = new Map();

function eligible(tab, now) {
  if (tab.active || tab.discarded) return false;
  if (tab.audible) return false;
  if (!tab.autoDiscardable) return false;          // per-tab opt-out still honoured
  if (tab.pinned && !DISCARD_PINNED) return false;
  return now - tab.lastAccessed >= IDLE_SECONDS * 1000;
}

async function sweep() {
  const now = Date.now();
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs) {
    if (!eligible(tab, now)) continue;
    try {
      await chrome.tabs.discard(tab.id);
      console.log(`[sleeper] discarded ${tab.id} after ${((now - tab.lastAccessed) / 1000).toFixed(1)}s idle`);
    } catch (e) {
      console.warn(`[sleeper] refused ${tab.id}: ${e.message}`);
    }
  }
}

// Switching away from a tab starts that tab's own countdown, so short
// timeouts fire on time instead of waiting for the next coarse sweep.
chrome.tabs.onActivated.addListener(({ tabId, windowId }) => {
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
chrome.runtime.onInstalled.addListener(sweep);
