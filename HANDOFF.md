# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-08-11 — DECISION 66 complete
# [CHANGE: claude-code | 2026-08-11]

> One file, overwritten in place every response (AGENTS.md §0.2). A snapshot, not a log.
> Do not append to it — it reached 82 KB that way once already.

## 🔴 The one thing left, and only Shawn can do it

**`chrome://extensions` → Luminos Tab Sleeper → Reload.**

v3.0 is written, tested, and on disk. **Chrome does not auto-reload unpacked extensions**, so the
worker running right now is still v2.0 and the 2-tab cap is not yet in force. This was verified,
not assumed: 70 seconds after v3.0 hit disk, `/tabs` still read `NEVER REPORTED`.

While in there, turn **Memory Saver off** at `chrome://settings/performance` — `chrome-luminos`
passes `--enable-features=MemorySaver`, so two systems are deciding about the same tabs.

**Check it afterwards with `luminos-tabs`.** Before the reload it says `NEVER REPORTED`; after,
live counts within ~30 s. That is the whole point of this round of work.

## What was asked, and what it does now

> *"when a model is running we dont over use ram so mainly the chrome max only 2 tabs should work
> like one background music and one which tab i am using. i am not using any tab than all tabs goes
> to sleep also we need something that can say that this thing is surely put to sleep."*

| Asked | Where it lives | Behaviour |
|---|---|---|
| Cap Chrome at 2 tabs while a model runs | `background.js` `pickKeepers()` | Tab on screen + one playing audio. No grace, no pinned/typed exemption. |
| "Not using any tab" → all sleep | `background.js` `awayFor()` | Chrome unfocused **60 s** → the on-screen slot is dropped too. Only audio and *"never sleep"* tabs remain. The 60 s exists so a glance at a terminal does not blank your page. |
| Prove a tab is really asleep | `:9091/tabs` + `luminos-tabs` | Every sweep POSTs its result; `luminos-tabs` reads it back beside independent `/proc` evidence. |

*"Never sleep this tab"* beats everything and **consumes no slot** — otherwise ticking it on three
tabs would silently evict the tab you were reading.

## How the three pieces connect

```
 luminos-ram  ──/meminfo──►  background.js  ──POST /tabs──►  luminos-ram  ──GET──►  luminos-tabs
 (model_running)              (MV3 worker)                    (mailbox)
                                    │
                            chrome.tabs.discard()
```

- **`model_running`** comes from `detectModel()`, a cached `/proc/*/cmdline` scan with a **0.2 GB
  RSS floor**. Two dead ends already ruled out, do not re-walk them: `offload_reserved_gb` is
  always `0` (nothing in `hive-daemon.py` calls the reserve path, so the cap would have been dead
  code that tested green), and `pgrep -f llama` matches the `pgrep` itself.
- **`/tabs` is a mailbox and nothing else.** One report, in memory, server-stamped so a client
  cannot backdate it. It is never read by the LIRS ranking or the `madvise` path. Losing it costs
  visibility only. It is on `:9091` because the extension already holds `host_permissions` there —
  any other port means a new permission and a fresh install prompt.

## ⚠️ This is a haste decision and it is documented as one

Shawn asked for it to be flagged, and it is — in DECISION 66, in `docs/CODE_REFERENCE.md`, in
LUMINOS_STATUS.md, in AGENTS.md §14 0e, and in the options page the user actually sees.

**The cap counts tabs, not megabytes.** The third tab sleeps whether it holds 8 MB or 800 MB
(measured spread on this machine: 8–190 MB), and the policy ignores `model_rss_gb` even though the
daemon publishes it. **DECISION 66 §"What is dumb about this, and what smart looks like"** lists
six specific things to fix. Making it measurement-driven is the real follow-up task.

## How it was proven (so nobody re-does it)

- **Go:** `go test ./cmd/luminos-ram/` — 8 tests, 7 of them negative. Garbage POSTs are rejected
  *without clobbering the last good report*; never-reported is distinguishable from reported-zero;
  `detectModel()` both fires on a real `/proc` process holding `.gguf` and does **not** fire on the
  test binary, whose own command line contains "luminos-ram".
- **Extension:** `node scripts/chrome-tab-sleeper/test-policy.js` — 22 checks against the **real
  `background.js`** under a stubbed Chrome, so it cannot drift from what ships. The stub throws if
  the visible active tab is ever handed to `discard()`.
- **The test was negative-tested twice.** `tabCap: 99` → 8 failures. Removing the `if (!chromeAway)`
  guard → exactly the 2 away-rule failures. A green test never made to go red is not evidence.
- **On the wire:** `node test-policy.js --live` POSTs what the extension really emits to the running
  daemon and reads the mailbox back. `luminos-tabs` then rendered it correctly, including flagging a
  491-second-old test report as **STALE**.

## Deployed this round

- `/usr/local/bin/luminos-ram` rebuilt + reinstalled (21:19). Backup:
  `~/.luminos-backups/luminos-ram.bak-pre-tabs-20260811-211949`. **The daemon sleeps 30 s before it
  listens** — curl exits 7 until then, which is not a failure.
- `/usr/local/bin/luminos-tabs` — new.
- Extension v3.0 written to `scripts/chrome-tab-sleeper/` but **not loaded** (see the red block).

## Not committed, not pushed — Shawn's call

Nothing from this round is committed. Also still sitting locally unpushed: **`5321eada`** (tab
sleeper v1.1 + BUG-118 docs) and the older **`fc84917f`**. The previous session asked about pushing
and got no answer, so they are still waiting. **Ask before pushing.**

## Standing repo rules (carry these forward)

- **NEVER `git add -A`.** An API key got published that way (BUG-086, WONTFIX per Shawn — do not
  re-raise rotation). The tree holds unrelated in-flight work: `_to_delete/`, `reference_code/`,
  `config/kde/caelestia-design-spec.json`, `scripts/jobhunt/moe-server.py`, `scripts/brightnessctl`,
  `switch-to-old-claude.sh`, `fix-claude-legacy.sh`, dirty `research/turboquant` submodules, and
  modified `scripts/luminos-session-recorder`. **Stage by name.**
- **Luminos scripts print success on failed paths.** Verify writes by reading them back. Caught one
  this round: `luminos-brain log` with no argument silently appends a blank incident line.
- **`luminos-brain safe` NOs are usually false** — it greps its own header banner.
- **BUG-080: the forex bot is live trading.** Check before anything that reboots or kills processes.
- **Measuring Chrome:** `pgrep -f "type=renderer"` matches every Chromium app on the box (once gave
  9 renderers / 1266 MB when Chrome's real share was 5 / 499 MB). Filter on
  `readlink /proc/<pid>/exe`. And sum **PSS, not RSS** — RSS counts shared libraries once per
  process: 528 MB claimed vs 195 MB real here.

## Previous goal, still open

**Caelestia-on-KWin (DECISION 63)** — AGENTS.md §14 item 0d. Blocked on Shawn naming one app that
opens fullscreen and then reshapes itself; BUG-117 (`luminos-maximize`'s `metadata.json` lacks
`KPackageStructure`, so KWin rejects it every startup while the settings UI shows it ticked) is
ruled out as the cause but still open on its own.
