# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-08-11 — Response 2
# [CHANGE: claude-code | 2026-08-11]

> One file, overwritten in place every response (AGENTS.md §0.2). A snapshot, not a log.
> Do not append to it — it reached 82 KB that way once already.

## Where things stand right now

**Task just finished:** aggressive Chrome tab sleeping, wired to the RAM monitor.

Shawn asked for: *"use things with our ram monitoring thing … i want aggressive only keep the
active tab on ram rest is sent to sleep."* Both halves are done and proven.

### The one thing waiting on Shawn
**Install the extension by hand.** `chrome://extensions` → Developer mode ON → **Load unpacked** →
`~/luminos-os/scripts/chrome-tab-sleeper`. Nothing else can do this: **Chrome 137+ disabled the
`--load-extension` command-line switch outright**, which makes the `chromium-flags.conf` advice
from the previous session wrong for Chrome (it still works on Chromium, which is how this was
tested). While in settings, turn **Memory Saver OFF** at `chrome://settings/performance` —
`chrome-luminos` passes `--enable-features=MemorySaver`, and two systems deciding about the same
tabs makes the behaviour unexplainable.

Chrome will warn *"Read and change all your data on all websites"* at install. That is the content
script; it listens for `input` events and sends one message, and reads nothing.

### What was built — scripts/chrome-tab-sleeper v2.0 (DECISION 65)
Aggressive by default: only the tab on screen stays in RAM. Reads `luminos-ram`'s own
`http://127.0.0.1:9091/meminfo` every 20 s and escalates:

| Level | `effective_available` | Behaviour |
|---|---|---|
| NORMAL | ≥ 3.0 GB | 10 s grace after you leave a tab, then it sleeps |
| PRESSURE | < 3.0 GB | grace → 0 |
| CRITICAL | < 1.5 GB | pinned + typed-into exemptions drop; non-focused windows lose their active tab too |

Always kept resident: the focused tab, unmuted audio, and *"Never sleep this tab"*. The manual
Alt+S / toolbar / right-click path ignores all of it — asking by hand is an instruction, not a hint.

**No Go change was needed.** `host_permissions` exempts the extension from same-origin, so the
daemon needed no CORS header. Confirmed live from inside the worker: `{level:"normal",
effective_available: 8.41, ok: true}`. If the daemon is down the extension stays aggressive and
just stops escalating.

**Measured:** same profile, page renderers only — **8 / 1266 MB → 3 / 424 MB** (~842 MB freed).

### BUG-118 — the finding that came out of it
`luminos-ram` has **never discarded a single tab**, and has been saying so every 60 seconds since
**2026-06-26** (339 errors in the last 24 h). Chrome 136+ refuses `--remote-debugging-port` on the
default profile, so 9222 is closed; `checkCDPHealth()` returns only on success, so
`discardBrowserTabs()` is unreachable. `LUMINOS_RAM_ARCHITECTURE.md` advertised *"Browser Tabs:
Discard via CDP (freed 100%)"* the whole time. BUG-102 had already noticed the dead flag but nobody
connected it to the daemon. **Left unrepaired on purpose** — the extension is the better path and
`cmd/` is off limits without instruction (§11). Side effect worth knowing: that same loop calls
`luminos-brain log` on every failure, so the brain log has taken a junk line a minute for six weeks.

### Three traps found the hard way, worth not repeating
- **MV3 tears the service worker down after ~30 s idle.** Module-scope state (the `Set` of tabs you
  typed into) is wiped with it — silently, and **only in production**, because a worker you are
  actively debugging never idles long enough to die. Moved to `chrome.storage.session` and proven
  by force-killing the worker: `workerUptime_s: 8`, `typedStillProtected: true`.
- **`chrome.tabs.discard()` gives the tab a NEW id and does not run `beforeunload`.** Old ids go
  stale (a test died on `No tab with id: 74611065`) and a half-written comment vanishes with no
  prompt. Hence the dirty-tab tracking, and the id pruning in `sweep()`.
- Chrome's built-in `network_speech_synthesis` component extension **looks exactly like your own
  extension's service worker** in a CDP target list. It cost an hour of debugging an extension that
  was never loaded. Check `chrome.runtime.id` is not null.

## Not committed, not pushed — Shawn's call
The doc changes above and the v2.0 extension are **written but not committed**. There is also an
older commit **`fc84917f` (tab sleeper v1.1) sitting locally unpushed** — the previous session asked
about pushing it and got no answer, so it is still waiting.

## Standing repo rules (carry these forward)
- **NEVER `git add -A`.** An API key got published that way (BUG-086, WONTFIX per Shawn — do not
  re-raise rotation). The tree holds unrelated in-flight work: `_to_delete/`, `reference_code/`,
  `config/kde/caelestia-design-spec.json`, `scripts/jobhunt/moe-server.py`, `scripts/brightnessctl`,
  `switch-to-old-claude.sh`, `fix-claude-legacy.sh`, dirty `research/turboquant` submodules, and
  modified `scripts/luminos-session-recorder`. **Stage by name.**
- **Luminos scripts print success on failed paths.** Verify writes by reading them back —
  `luminos-notes.sh add` and `luminos-brain log` were both verified that way this time.
- **`luminos-brain safe` NOs are usually false** — it greps its own header banner.
- **BUG-080: the forex bot is live trading.** Check before anything that reboots or kills processes.

## Previous goal, still open
**Caelestia-on-KWin (DECISION 63)** — AGENTS.md §14 item 0d. Blocked on Shawn naming one app that
opens fullscreen and then reshapes itself; BUG-117 (`luminos-maximize`'s `metadata.json` lacks
`KPackageStructure`, so KWin rejects it every startup while the settings UI shows it ticked) is
ruled out as the cause but still open on its own.
