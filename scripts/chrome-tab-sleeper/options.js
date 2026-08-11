// [CHANGE: claude-code | 2026-08-11]
const DEFAULTS = {
  aggressive: true,
  graceSeconds: 10,
  exemptPinned: true,
  exemptDirty: true,
  ramEnabled: true,
  pressureGB: 3.0,
  criticalGB: 1.5
};

const fields = Object.keys(DEFAULTS);

function el(id) { return document.getElementById(id); }

async function load() {
  const cfg = { ...DEFAULTS, ...(await chrome.storage.local.get(DEFAULTS)) };
  for (const k of fields) {
    const node = el(k);
    if (node.type === 'checkbox') node.checked = cfg[k];
    else node.value = cfg[k];
  }
}

async function save() {
  const out = {};
  for (const k of fields) {
    const node = el(k);
    out[k] = node.type === 'checkbox' ? node.checked : Number(node.value);
  }
  await chrome.storage.local.set(out);
}

for (const k of fields) el(k).addEventListener('change', save);

// Live status. Reads the same endpoint the extension does, so if this line is
// wrong the extension is wrong too — no separate code path to drift.
async function refresh() {
  const tabs = await chrome.tabs.query({});
  const asleep = tabs.filter((t) => t.discarded).length;
  let ramLine;
  try {
    const m = await (await fetch('http://127.0.0.1:9091/meminfo', { cache: 'no-store' })).json();
    const free = typeof m.effective_available === 'number' ? m.effective_available : m.available;
    const cfg = { ...DEFAULTS, ...(await chrome.storage.local.get(DEFAULTS)) };
    const level = free < cfg.criticalGB ? 'CRITICAL' : free < cfg.pressureGB ? 'PRESSURE' : 'normal';
    ramLine = `luminos-ram: ${free.toFixed(2)} GB free of ${m.total.toFixed(1)} GB  —  ${level}`
            + `\nzram: ${m.zram_used.toFixed(2)} GB used, ${m.zram_saved.toFixed(2)} GB saved by compression`;
  } catch (e) {
    ramLine = 'luminos-ram: not reachable on 127.0.0.1:9091 '
            + '— aggressive mode still works, it just will not escalate.';
  }
  el('status').textContent = `${tabs.length} tabs, ${asleep} asleep, ${tabs.length - asleep} in RAM\n${ramLine}`;
}

load().then(refresh);
setInterval(refresh, 3000);
