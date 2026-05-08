# Luminos RAM Architecture — Final Design
# Version: 2.0
# Date: May 2026
# Algorithm: LIRS + MADV_PAGEOUT + Process Freeze

## Philosophy
Compress instantly when not in use.
Restore instantly when needed.
Never wait for timers when we know something is cold.
Battery and RAM are saved by acting fast not slow.

## Why MADV_PAGEOUT Over MADV_COLD
MADV_COLD: hints to kswapd, waits 1-5 minutes.
MADV_PAGEOUT: forces kernel to compress NOW.
User never feels MADV_PAGEOUT because they are
not using the window being compressed.
No stutter risk. Immediate benefit.
kswapd bypassed entirely for cold apps.

## Algorithm: LIRS (Low Inter-Reference Recency Set)
Tracks IRR (Inter-Reference Recency) per window.
IRR = number of unique other windows accessed
      between last two accesses to this window.
Low IRR = frequent relative use = HOT set (LIR)
High IRR = infrequent relative use = COLD set (HIR)

### IRR Tracking
Per window/process group track:
  last_access_time
  second_last_access_time
  IRR = unique_windows_between_last_two_accesses
  access_count_30min
  access_count_2hr

### Hot Set (LIR blocks)
Low IRR windows stay in RAM uncompressed.
Size: dynamic based on RAM pressure.
Default: top 8 windows by IRR score.
Always included regardless of IRR:
  Active audio processes (PipeWire clients)
  Active game process (high GPU usage)
  luminos-* system daemons
  kwin, plasmashell, pipewire, systemd

### Cold Set (HIR blocks)  
High IRR windows get compressed.
MADV_PAGEOUT called immediately on IRR rise.
Kernel compresses to ZRAM within 5-10 seconds.
Restore: decompress from ZRAM in ~50ms.

## Memory Hierarchy
RAM (16GB) → ZRAM (8GB zstd) → zswap (NVMe)

Hot apps: full RAM speed (100ns)
ZRAM compressed: ~500ns restore
zswap NVMe: ~200ms restore (avoid if possible)

## Process Freeze System (Universal — Not Just Chrome)
Applies to ALL apps with multiple windows or tabs:
  Chrome tabs, Firefox tabs
  Electron app windows (Discord, Slack, VSCode)
  Terminal multiplexer tabs (Konsole, Kitty)
  File manager windows (Dolphin)
  Any app with multiple child processes

### 15 Minute Rule
App/window cold for 15+ minutes:
  Step 1: MADV_PAGEOUT already done (from LIRS)
  Step 2: SIGSTOP sent to process group
          Freezes entirely: 0 CPU, 0 memory access
          Process stays in RAM but frozen
          Restore: SIGCONT → instant (~10ms)
  Step 3: For browser tabs specifically
          Chrome/Firefox DevTools Protocol
          tab.discard() → 0MB completely freed
          Restore: tab reloads (~2 seconds)

### 2 Hour Rule
App frozen for 2+ hours:
  Non-essential apps: SIGKILL entirely
  RAM freed 100%
  Relaunch when opened (seamless if autostart)
  Protected from kill:
    Terminals with active sessions
    Code editors with unsaved work
    Any app currently downloading
    Music/video players
    luminos-* daemons

## Dynamic Hot Set Sizing
Normal mode: 8 hot windows
RAM > 70% used: reduce to 6 hot windows
RAM > 85% used: reduce to 4 hot windows
Gaming mode: 2 hot windows (game + voice chat)
AI mode: 6 hot windows (HIVE needs headroom)

## Scan Interval
Every 3 seconds: check window focus events
Every 10 seconds: update IRR for all processes
Every 60 seconds: enforce freeze rules
Every 5 minutes: enforce kill rules

## Integration Points
luminos-power → signals gaming/AI mode
luminos-ai socket → receives mode changes
KWin D-Bus → window focus events
PipeWire D-Bus → audio activity detection
/proc/PID/ → process stats and memory maps
DevTools Protocol → browser tab management

## Memory Savings Expected
Cold Chrome tabs (10 tabs): 2GB → 0MB (discarded)
Frozen Electron apps: 1.5GB → 400MB compressed
Frozen native apps: 800MB → 0MB (killed, relaunch)
Total expected savings: 3-5GB vs current state
