# Luminos RAM Architecture — Precise Design v3.0
# Version: 3.0
# Date: May 2026
# Algorithm: LIRS IRR + OnScreen Absolute Protection

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
    - **Browser Tabs**: Discard via CDP (freed 100%).
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
- **CDP**: Connects to port 9222 for browser tab management.
- **D-Bus**: Uses `org.kde.KWin` for window-to-PID mapping.

## Restore Speed Optimizations (v3.1)
- **MADV_WILLNEED Prefetch**: Before `SIGCONT`, `process_madvise(MADV_WILLNEED)` is called on process memory to warm up pages from ZRAM/Disk.
- **Staged Thaw**: For large processes (> 500MB), a 200ms delay is inserted between prefetch and `SIGCONT` to allow the kernel to finish page-ins.
- **Priority Boosting**: Process priority is boosted to `nice -10` for 5 seconds upon focus to speed up initial response.
- **Bulk Page Reads**: `vm.page-cluster=3` set via sysctl to read 8 pages per fault instead of 1, reducing restore latency.
