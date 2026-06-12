# PENDING_RESTART.md — One-Time Restart Required
# [CHANGE: claude-code | 2026-06-10]

**DO NOT restart anything while HOPE model training is running**
(`~/hope-llm/scripts/train.py` — check with `pgrep -af train.py`).

Fixes were installed on 2026-06-10 but deliberately NOT activated to avoid
interrupting training. A **one-time restart of the five Go daemons** (no reboot
needed) is required to activate them.

## What is waiting on the restart

| Fix | Installed | Active now? |
|---|---|---|
| BUG-065: luminos-ram real `process_madvise` (binary `/usr/local/bin/luminos-ram`) | ✅ | ❌ old binary still running (PID from boot) |
| BUG-066: luminos-ram caps `CAP_SYS_NICE CAP_KILL` (unit file) | ✅ | ❌ applies on next service start |
| BUG-067: `RuntimeDirectoryPreserve=yes` on all 5 units | ✅ (daemon-reload done) | ⚠️ prevents FUTURE wipes, but ai.sock / sentinel.sock / ram.sock are still unlinked since the 2026-06-08 wipe — clients get ENOENT until daemons rebind |

## The one-time command (run AFTER training finishes)

```bash
sudo systemctl restart luminos-ai luminos-sentinel luminos-ram luminos-power luminos-router
# Verify all sockets exist again:
ls -la /run/luminos/   # expect: ai.sock, sentinel.sock, ram.sock, power.sock
# Verify ram daemon came up with new caps:
journalctl -u luminos-ram -n 20
```

## Training-performance overrides to revert AFTER training (added 2026-06-11)
<!-- [CHANGE: claude-code | 2026-06-11] -->

User-requested max-performance state for HOPE training (BUG-069 context):

| Override | Applied | Revert with |
|---|---|---|
| `nvidia-powerd` unmasked + started (Dynamic Boost 55→90W — only working TGP mechanism; daemon's nvidia-smi -pl is a no-op, see BUG-069) | 2026-06-11 | `sudo systemctl stop nvidia-powerd && sudo systemctl mask nvidia-powerd` (was masked for idle-drain reasons, BUG-047 era) |
| Fan lock: transient user unit `luminos-train-fanlock` (`/tmp/luminos-train-fanlock.sh`) re-asserts flat 100% curves on Balanced every 60s — needed because luminos-power clobbers manual curves on profile/zone transitions | 2026-06-11 | Automatic — unit watches `pgrep -f scripts/train.py`, exits when training ends and restores fan curve v5 itself. Manual stop: `systemctl --user stop luminos-train-fanlock` (also restores v5 via script exit path only if training ended; otherwise re-run apply v5 per AGENTS.md §12) |

Then delete this file and update LUMINOS_STATUS.md.
