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
