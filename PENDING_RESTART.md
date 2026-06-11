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
| Flat 100% fan curves (cpu/gpu/mid) on Balanced profile via asusctl | 2026-06-11 | Automatic — luminos-power re-applies fan curve v5 on its restart (above) or any profile switch |

Then delete this file and update LUMINOS_STATUS.md.
