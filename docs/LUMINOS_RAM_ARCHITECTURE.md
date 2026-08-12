# Luminos RAM Architecture — Precise Design v3.0
# Version: 3.5
# Date: May 2026 (updated 2026-06-10)
# Algorithm: LIRS IRR + OnScreen Absolute Protection

> **v3.5 (2026-06-10, BUG-065/066/067):** Until this date `madvise()` was a stub —
> every MADV_PAGEOUT below was a silent no-op, and the unit's capability bounding
> set blocked SIGSTOP/SIGKILL/setpriority with EPERM. Now implemented for real via
> `process_madvise(2)`: pidfd_open + iovecs from `/proc/<pid>/maps` (readable
> private mappings, UIO_MAXIOV chunks). Verified: 64MB test process RSS
> 70MB→2.4MB into zram. `getChildPIDs()` now walks `/proc/<pid>/task/*/children`
> recursively (full descendant tree — Chrome renderers hang off the zygote and
> were previously never found). Fix is installed but inactive until the one-time
> restart in PENDING_RESTART.md.

## Philosophy
Memory management must be invisible. The user's field of view (OnScreen) is sacred.
Never compress or freeze what the user is looking at.
Rank background work by Inter-Reference Recency (IRR) to predict future use.

## The Absolute Rule: OnScreen Protection
Before any memory action (MADV_PAGEOUT, SIGSTOP, SIGKILL), check:
`if (focused OR (visible AND focused_within_60s)) → SKIP ACTION`
This ensures that the current window and all recently used visible windows (e.g. side-by-side) are never touched.

## Data Structures
### Hot Set (LIR - Low Inter-Reference Recency)
- **Capacity (N)**: 8 (default, configurable).
- **Ordering**: Sorted by IRR Score (lowest IRR = most recently used relatively).
- **Eviction**: When `size > N`, the entry with the highest IRR is moved to the Cold Set.
- **Bottom Tier (Positions 6-8)**: Timer-based compression. If idle > 10min and not OnScreen, apply `MADV_PAGEOUT` but remain in Hot Set.

### Cold Set (HIR - High Inter-Reference Recency)
- **Eviction Entry**: Immediate `MADV_PAGEOUT`.
- **15 Minute Rule**:
    - **Browser Tabs**: ⛔ **This daemon does not do this and never has.** See "Browser tabs" below.
    - **Native Apps**: `SIGSTOP` if safety checks pass.
- **2 Hour Rule**:
    - **Non-essential Apps**: `SIGKILL`.
    - **Protected from Kill**: Terminals, LISTEN sockets, active downloads, luminos-* daemons.

## LIRS IRR Algorithm
Inter-Reference Recency (IRR) is defined as the number of *unique other windows* focused between the last two focuses of a specific window.
- Low IRR = Frequent relative use.
- High IRR = Infrequent relative use.

## Safety Checks (Before SIGSTOP/SIGKILL)
- **Audio**: Check `/proc/PID/fd` for active PipeWire/ALSA.
- **Network**: Check for established TCP/UDP connections.
- **Listen**: Check for sockets in `LISTEN` state (servers).
- **Disk**: Check write rate via `/proc/PID/io` (> 1MB/s).
- **CPU**: Check CPU usage (> 5%).
- **Download**: Heuristic based on active disk/network activity.

## Configuration (~/.config/luminos-ram.conf)
- `hot_set_capacity`: Default 8.
- `bottom_tier_timer_minutes`: Default 10.
- `cold_sigstop_minutes`: Default 15.
- `cold_kill_hours`: Default 2.

## Integration
- **KWin**: Subscribes to `activeWindowChanged`, `windowMinimized`, `windowUnminimized`.
- **CDP**: ⛔ dead — see "Browser tabs" below.
- **D-Bus**: Uses `org.kde.KWin` for window-to-PID mapping.

## Browser tabs — handled outside this daemon
# [CHANGE: claude-code | 2026-08-11] BUG-118 / DECISION 65

Everything this document used to claim about CDP was **false**. `checkCDPHealth()` polls
`localhost:9222` and has failed on every attempt since at least **2026-06-26** (339 errors in the
last 24 h alone), because Chrome 136+ refuses `--remote-debugging-port` on the default profile.
`checkCDPHealth()` returns only on success, so `scanAndCompressChrome()` and
`manageChromeMemory()`/`discardBrowserTabs()` are unreachable code. **No tab has ever been
discarded by luminos-ram.**

Browser tabs are now the job of **`scripts/chrome-tab-sleeper` v3.0**, a Chrome MV3 extension that
uses `chrome.tabs.discard()` from inside the browser. It is aggressive by default — only the tab on
screen stays resident — and it reads pressure from **this daemon's own `/meminfo`** on `:9091`,
so both halves of memory management agree on one number.

**The daemon owes the extension exactly two things** (DECISION 66), and nothing else:

1. **`/meminfo`** — `effective_available` as before, plus `model_running` / `model_name` /
   `model_rss_gb`. `detectModel()` scans `/proc/*/cmdline` (cached 5 s) for `llama-server`,
   `llama_cpp.server`, `llama-cli`, `.gguf`, `moe-server.py`, `luminos_moe_offload.py`, and requires
   **≥ 0.2 GB RSS** before believing it. When `model_running` is true the extension caps Chrome at
   **2 live tabs**.
   > Do **not** rewire this to `offload_reserved_gb`. That field looks right and is always `0` —
   > nothing in `hive-daemon.py` ever calls the reserve path, so the cap would be dead code that
   > tests green. Do not rewire it to `pgrep -f` either: that matches the `pgrep` itself.
2. **`/tabs`** — a **mailbox, and nothing more**. The extension POSTs a one-line summary of each
   sweep; `luminos-tabs` GETs it back. It holds one report in memory, the daemon stamps the
   timestamp server-side so a client cannot backdate it, and **it is never consulted by the LIRS
   ranking or the `madvise` path**. Losing it costs visibility only. It exists because an extension
   cannot write a file, and without it the only evidence a sweep was running was TCP byte counters
   on the extension's `/meminfo` socket — which says nothing about whether `discard()` succeeded.

There is no callback and no CORS header: the extension declares `host_permissions` for
`127.0.0.1:9091` and polls every 20 s. **If this daemon is down the extension keeps sleeping tabs**
and simply stops escalating — including the 30 s at every restart when this daemon is deliberately
not yet listening.

Note that Chrome renderers are still touched by the generic `MADV_PAGEOUT` path as ordinary
processes. That pushes them into zram; a discard frees them outright. The two are complementary,
not duplicates.

## Restore Speed Optimizations (v3.1)
- **MADV_WILLNEED Prefetch**: Before `SIGCONT`, `process_madvise(MADV_WILLNEED)` is called on process memory to warm up pages from ZRAM/Disk.
- **Staged Thaw**: For large processes (> 500MB), a 200ms delay is inserted between prefetch and `SIGCONT` to allow the kernel to finish page-ins.
- **Priority Boosting**: Process priority is boosted to `nice -10` for 5 seconds upon focus to speed up initial response.
- **Bulk Page Reads**: `vm.page-cluster=3` set via sysctl to read 8 pages per fault instead of 1, reducing restore latency.
