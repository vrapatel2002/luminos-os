# Luminos RAM Management Plan
# Created: May 2026
# Goal: 16GB feels unlimited. Swap never fills.
#        Compress idle, protect active, restore fast.

## Current State (Diagnosed May 2026)
- Total RAM: 15GB
- Normal usage: 12GB (80%)
- Swap: 4GB completely full
- Main culprit: Chrome 15+ processes = 8.5GB
- Secondary: pyrefly LSP 913MB, Gemini CLI 847MB

## Philosophy
Compress early. Compress idle. Never compress active.
Audio and network threads always protected.
Restore in under 500ms when user returns.

## Tier Timing (tuned for Sam's workflow)
TIER 0 — Active: full RAM, no touch
TIER 1 — 15min idle: KSM merge (invisible savings)
TIER 2 — 2hr idle: ZRAM compress (light)
TIER 3 — 12hr idle: ZRAM heavy compress
Protected always: audio threads, network threads,
Go daemons, KWin, active game

## Stack Components

### ZRAM (replaces current 4GB SSD swap)
Size: 8GB
Algorithm: zstd
Priority: higher than SSD swap
Expected: 8GB ZRAM holds ~22GB compressed data
Result: swap never hits SSD again

### swappiness tuning
Current: default 60
Target: 30
Effect: kernel prefers ZRAM over SSD swap

### KSM (Kernel Same-page Merging)
Merges identical pages across Chrome processes
Expected saving: 1-2GB from Chrome alone
Cost: ~1% CPU

### earlyoom
Trigger: RAM < 10% available AND swap > 90%
Kill order: largest idle process first
Never kill: luminos-*, plasmashell, active game

### Chrome process limit
Max renderers: 8 (down from 15+)
Effect: tabs share renderer processes
Saving: ~2-3GB from Chrome

### cgroups v2 profiles (Phase 2 — luminos-ram)
browser: 4GB ceiling
background: 1GB ceiling  
hive: 5GB ceiling
system: unlimited

## Future: luminos-ram daemon (Phase 2)
Go daemon that:
- Watches window focus via KWin
- Detects audio via PipeWire
- Applies MADV_PAGEOUT to idle processes
- Reports metrics to KDE widget
- Integrates with luminos-power modes

## KDE Monitoring Widget
Install: plasma6-applets-resources-monitor
Shows: RAM free, VRAM, GPU%, CPU temp, GPU temp
