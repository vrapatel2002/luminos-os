// [CHANGE: claude-code | 2026-10-11]
// Popup: reads/writes chrome.storage.local.luminosAmbient; the content script applies it live.
const core = globalThis.LuminosAmbientCore;
const SLIDERS = ['spread', 'fps', 'intensity'];
const el = (id) => document.getElementById(id);

function render(settings) {
  el('enabled').checked = settings.enabled;
  for (const key of SLIDERS) {
    el(key).value = settings[key];
    el(`${key}-out`).textContent = settings[key];
  }
}

function readForm() {
  const raw = { enabled: el('enabled').checked };
  for (const key of SLIDERS) raw[key] = Number(el(key).value);
  return core.clampSettings(raw);
}

function save() {
  const settings = readForm();
  render(settings);
  chrome.storage.local.set({ luminosAmbient: settings });
}

chrome.storage.local.get('luminosAmbient', (res) => render(core.clampSettings(res && res.luminosAmbient)));
el('enabled').addEventListener('change', save);
for (const key of SLIDERS) el(key).addEventListener('input', save);
