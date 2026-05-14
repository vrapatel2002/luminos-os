# BUG-049 — Claude Desktop Memory Leak

- **Status:** MONITORING
- **Severity:** MEDIUM
- **Component:** Claude Desktop (Electron), `cmd/luminos-ram`
- **Date Found:** 2026-05-10
- **Date Fixed:** 2026-05-10 (workaround only)
- **Agent:** gemini-cli

## Description
Claude Desktop Electron renderer running 101+ hours grew from 300MB to 2.1GB RAM usage.
Eventual OOM risk if left running indefinitely.

## Root Cause
All Electron apps exhibit renderer memory growth over long sessions.
Electron's V8 garbage collector does not aggressively reclaim memory between sessions.
Not fixable without upstream Electron/Claude Desktop changes.

## Fix Applied (Workaround)
- Manual: Restart Claude Desktop daily
- Automated: Added background leak detection to `luminos-ram` v3.1
  - Alerts when any process grows >500MB over baseline in background
  - Logs to `/var/log/luminos-telemetry.csv`

## Monitoring
Check with: `ps aux | grep claude | awk '{print $6}'` (RSS in KB)
Alert threshold: >1.5GB RSS for Claude Desktop renderer

## Notes
- Will resolve itself if Claude Desktop moves off Electron
- Same pattern expected from Antigravity if it's Electron-based
