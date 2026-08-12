// [CHANGE: claude-code | 2026-08-11] DECISION 66 — run with: node test-policy.js
//
// Exercises the real background.js against a stubbed Chrome. Written because the cap
// is the entire feature and there is no other way to check it: the alternative is
// opening six tabs by hand, loading a model, and squinting at chrome://discards.
//
// It loads the actual file — not a copy — so it cannot drift from what ships.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

let failures = 0;
function check(name, cond, detail) {
  if (cond) { console.log(`  ok   ${name}`); return; }
  failures++;
  console.log(`  FAIL ${name}${detail ? `\n         ${detail}` : ''}`);
}

// ---- the stub ------------------------------------------------------------

function makeChrome(world) {
  const noop = () => {};
  const listener = { addListener: noop };
  // Lives on `world` so a test can seed it — that is how the away clock is wound
  // forward without actually waiting a minute.
  const session = world.session;
  return {
    chrome: {
      storage: {
        local: { get: async (d) => ({ ...d, ...world.localCfg }), set: async () => {} },
        session: {
          get: async (k) => (typeof k === 'string' ? { [k]: session[k] } : { ...session }),
          set: async (o) => Object.assign(session, o)
        }
      },
      tabs: {
        query: async () => world.tabs.map((t) => ({ ...t })),
        get: async (id) => world.tabs.find((t) => t.id === id),
        update: async () => {},
        discard: async (id) => {
          const t = world.tabs.find((x) => x.id === id);
          if (!t) throw new Error(`No tab with id: ${id}`);
          // Chrome refuses to discard the tab that is actually on screen. If our policy
          // ever asks for that, this stub must fail loudly rather than pretend.
          if (t.active && t.windowId === world.focusedWindowId && world.focused) {
            throw new Error('cannot discard the visible active tab');
          }
          t.discarded = true;
          world.discarded.push(id);
        },
        onActivated: listener, onUpdated: listener, onRemoved: listener, onCreated: listener
      },
      windows: {
        WINDOW_ID_NONE: -1,
        getLastFocused: async () => ({ id: world.focusedWindowId, focused: world.focused }),
        onFocusChanged: listener
      },
      action: {
        setBadgeBackgroundColor: noop, setBadgeText: noop, setTitle: noop, onClicked: listener
      },
      contextMenus: { create: noop, update: noop, onClicked: listener },
      commands: { onCommand: listener },
      alarms: { create: noop, onAlarm: listener },
      runtime: { onMessage: listener, onStartup: listener, onInstalled: listener }
    },
    fetch: async (url, opts) => {
      if (url.includes('/meminfo')) {
        return { json: async () => world.meminfo };
      }
      world.reports.push(JSON.parse(opts.body));
      // --live sends the report on to the real daemon as well. This is the only check
      // that the bytes background.js actually emits are the bytes the Go handler
      // accepts — the stub would happily swallow a body the daemon would reject.
      if (LIVE) return globalThis.fetch(url, opts);
      return { ok: true };
    }
  };
}

const LIVE = process.argv.includes('--live');

function load(world) {
  const src = fs.readFileSync(path.join(__dirname, 'background.js'), 'utf8');
  const ctx = {
    ...makeChrome(world),
    console: { warn: () => {}, log: () => {} },
    setTimeout: () => 0,
    clearTimeout: () => {},
    Date, JSON, Math, Set, Map, Infinity, isFinite, Number, String, Object, Array, Promise
  };
  vm.createContext(ctx);
  // Hand the internals back out. background.js has no exports of its own — it is a
  // service worker — so the names are appended here rather than changing the file.
  vm.runInContext(src + '\n;globalThis.__t = { sweep, pickKeepers, pollRam, config };', ctx);
  return ctx.__t;
}

// ---- fixtures ------------------------------------------------------------

const T0 = Date.now();

// Tabs default to minutes old, i.e. well past the 10 s grace. A fixture only seconds
// old made two cases look like failures when the grace was doing its job correctly.
// Tests that care about a freshly-left tab set lastAccessed themselves.
function tab(id, over = {}) {
  return {
    id, windowId: 1, active: false, discarded: false, pinned: false,
    autoDiscardable: true, audible: false, mutedInfo: { muted: false },
    lastAccessed: T0 - id * 60 * 1000, ...over
  };
}

function world(over = {}) {
  return {
    tabs: [], focusedWindowId: 1, focused: true, discarded: [], reports: [],
    localCfg: {}, session: {},
    meminfo: { effective_available: 9.0, available: 9.0, total: 14.9, model_running: false },
    ...over
  };
}

const awake = (w) => w.tabs.filter((t) => !t.discarded).map((t) => t.id).sort((a, b) => a - b);

// ---- cases ---------------------------------------------------------------

async function main() {
  // 1. The headline case: a model is loaded, six tabs open, one playing music.
  {
    const w = world({
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true, model_name: '.gguf' },
      tabs: [tab(1, { active: true }), tab(2, { audible: true }), tab(3), tab(4), tab(5), tab(6)]
    });
    await load(w).sweep();
    check('model loaded → exactly 2 tabs left awake', awake(w).length === 2, `awake: ${awake(w)}`);
    check('...and they are the active one and the audio one',
      String(awake(w)) === '1,2', `awake: ${awake(w)}`);
    check('the sweep reported what it did', w.reports.length === 1 && w.reports[0].model === true,
      JSON.stringify(w.reports[0]));
    check('report counts match reality',
      w.reports[0].awake === 2 && w.reports[0].asleep === 4 && w.reports[0].cap === 2,
      JSON.stringify(w.reports[0]));
  }

  // 2. No audio playing: the second slot goes to the most recent tab, not a random one.
  {
    const w = world({
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true },
      tabs: [tab(1, { active: true }), tab(2), tab(3), tab(4)]
    });
    await load(w).sweep();
    check('no audio → cap still filled, most-recent wins', String(awake(w)) === '1,2', `awake: ${awake(w)}`);
  }

  // 3. Three tabs making noise. The cap is a total, so only one of them survives.
  {
    const w = world({
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true },
      tabs: [
        tab(1, { active: true }),
        tab(2, { audible: true, lastAccessed: T0 - 500 }),   // most recently opened
        tab(3, { audible: true, lastAccessed: T0 - 9000 }),
        tab(4, { audible: true, lastAccessed: T0 - 9000 })
      ]
    });
    await load(w).sweep();
    check('3 audible tabs → only the newest survives', String(awake(w)) === '1,2', `awake: ${awake(w)}`);
  }

  // 4. Walked away from Chrome. The active tab must survive a short glance elsewhere
  //    and only sleep once you have really gone — otherwise checking a terminal for
  //    ten seconds blanks the page you were reading.
  {
    const w = world({
      focused: false,
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true },
      tabs: [tab(1, { active: true }), tab(2, { audible: true }), tab(3), tab(4)]
    });
    await load(w).sweep();   // first sweep only starts the away clock
    check('glanced away → the tab you were reading is NOT dropped yet', !w.tabs[0].discarded);
    check('...but the idle tabs still went', w.tabs[2].discarded && w.tabs[3].discarded, `awake: ${awake(w)}`);

    // Wind the stored clock back past awaySeconds (60) and sweep again.
    w.session.awaySince = Date.now() - 90 * 1000;
    await load(w).sweep();
    check('genuinely away → even the active tab sleeps', w.tabs[0].discarded, `awake: ${awake(w)}`);
    check('...but the music keeps playing', !w.tabs[1].discarded, `awake: ${awake(w)}`);
  }

  // 4b. Away with nothing playing means nothing at all stays in RAM. This is the
  //     "I am not using any tab, so all tabs go to sleep" case, and it is the one
  //     most likely to be quietly undone by a slot-filling bug.
  {
    const w = world({
      focused: false,
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true },
      tabs: [tab(1, { active: true }), tab(2), tab(3), tab(4)]
    });
    w.session.awaySince = Date.now() - 90 * 1000;
    await load(w).sweep();
    check('away with no audio → every tab asleep', awake(w).length === 0, `awake: ${awake(w)}`);
  }

  // 4c. Coming back must reset the clock, or the first sweep after you return would
  //     still think you were away and blank the tab in front of you.
  {
    const w = world({
      focused: false,
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true },
      tabs: [tab(1, { active: true }), tab(2), tab(3)]
    });
    w.session.awaySince = Date.now() - 90 * 1000;
    w.focused = true;
    await load(w).sweep();
    check('returning to Chrome clears the away clock', w.session.awaySince === 0, `awaySince: ${w.session.awaySince}`);
    check('...and the tab in front of you survives', !w.tabs[0].discarded, `awake: ${awake(w)}`);
  }

  // 5. "Never sleep this tab" is a hand instruction and must outrank the cap —
  //    and must not eat a slot, or ticking it would evict the tab you are reading.
  {
    const w = world({
      meminfo: { effective_available: 4.0, available: 4.0, total: 14.9, model_running: true },
      tabs: [
        tab(1, { active: true }), tab(2, { autoDiscardable: false }),
        tab(3, { autoDiscardable: false }), tab(4), tab(5)
      ]
    });
    await load(w).sweep();
    check('opted-out tabs survive the cap', !w.tabs[1].discarded && !w.tabs[2].discarded, `awake: ${awake(w)}`);
    check('...and do not consume the cap (tab 4 still awake)',
      String(awake(w)) === '1,2,3,4', `awake: ${awake(w)}`);
  }

  // 6. No model, plenty of RAM: the cap must NOT engage, and the grace must hold.
  {
    const w = world({
      tabs: [tab(1, { active: true }), tab(2, { lastAccessed: Date.now() }), tab(3), tab(4)]
    });
    await load(w).sweep();
    check('no model + no pressure → uncapped, grace protects a just-left tab',
      !w.tabs[1].discarded, `awake: ${awake(w)}`);
    check('...but stale tabs still sleep', w.tabs[2].discarded && w.tabs[3].discarded, `awake: ${awake(w)}`);
    check('report says uncapped', w.reports[0].cap === 0 && w.reports[0].model === false,
      JSON.stringify(w.reports[0]));
  }

  // 7. Memory pressure alone caps too, with no model in sight.
  {
    const w = world({
      meminfo: { effective_available: 2.0, available: 2.0, total: 14.9, model_running: false },
      tabs: [tab(1, { active: true }), tab(2), tab(3), tab(4), tab(5)]
    });
    await load(w).sweep();
    check('PRESSURE with no model → capped at 2', awake(w).length === 2, `awake: ${awake(w)}`);
    check('...and reported as pressure', w.reports[0].level === 'pressure', JSON.stringify(w.reports[0]));
  }

  // 8. The daemon being down must not stop tabs sleeping — it only stops escalation.
  {
    const w = world({ tabs: [tab(1, { active: true }), tab(2), tab(3)] });
    const src = load(w);
    w.meminfo = null;   // makes the stub's json() throw, like an unreachable daemon
    await src.sweep();
    check('daemon down → still sweeps, does not throw', w.tabs[2].discarded, `awake: ${awake(w)}`);
  }

  // 9. The visible active tab must never be handed to chrome.tabs.discard(). The stub
  //    throws if it is, which would otherwise show up as a console warning nobody reads.
  {
    const w = world({
      meminfo: { effective_available: 1.0, available: 1.0, total: 14.9, model_running: true },
      tabs: [tab(1, { active: true }), tab(2), tab(3)]
    });
    await load(w).sweep();
    check('never tries to discard the tab on screen', !w.tabs[0].discarded);
  }

  if (LIVE) {
    // Every case above just POSTed for real. Read the mailbox back and require that
    // the daemon kept the last one — a 400 would have left it holding an older report.
    const back = await (await globalThis.fetch('http://127.0.0.1:9091/tabs')).json();
    check('live daemon accepted a real sweep report', back.reported === true, JSON.stringify(back));
    check('...and it is the one we just sent',
      back.reported && back.report.age_seconds < 10, JSON.stringify(back.report));
  }

  console.log(failures === 0 ? '\nall policy checks passed' : `\n${failures} FAILED`);
}

main().then(() => process.exit(failures === 0 ? 0 : 1));
