# nvdefer — stop the NVIDIA driver waking a sleeping dGPU just to read a firmware note

## What Shawn wants (his words)
"why is the NVIDIA card waking up — that thing should be cold until anything uses it"; "make sure this never happens in future";
"tell firmware it's not needed". /build: fix the remaining wakes (BUG-203, BUG-204, unplug D2).

## The bug, measured (docs/BUGS.md BUG-198/203/204, docs/spectrum/ab/{unplug3,replug3,smooth-ac2,smooth-ac-nodaemon})
Firmware/asusd send ACPI notifies to the dGPU while it is runtime-suspended (D3cold). nvidia-open 610.57 handles each one by
taking a runtime-PM reference → full GPU power-up (~20 s awake) to process a value nobody needs while the GPU is off:
- PEGP 0xD1..0xD5 "D-notifier" (EC power level; charging under load ≈ 2/s; firmware D2 on every unplug) → RmHandleDNotifierEvent
- PEGP 0xC0 GPS status change (EC _QD9 etc.) → RmHandleGPSStatusChange
- NPCF 0xC0 (asusd fan-curve / profile writes, every plug/unplug) → rm_acpi_nvpcf_notify. Its only consumer, nvidia-powerd, is MASKED here.
- AC adapter 0x80/0x00 → rm_power_source_change_event (once per cable event)

## Fix
In kernel-open/nvidia (open source part of the driver, rebuilt by DKMS): when one of those four events arrives while the dGPU is
runtime-suspended, do not wake it. Remember it (latest D-level, GPS flag, NVPCF flag, latest AC state — coalesced, only the newest
value matters). When the GPU next resumes for real work, deliver the remembered events once (same functions as today), so the
GPU always ends up with the current limits. Upstream precedent: NVIDIA PR #1299 does exactly this for NPCF only.

## Assumptions (defaults chosen, change if wanted)
- Single NVIDIA GPU (this laptop). The deferral keys off that GPU's runtime-PM state.
- Replay happens from a work item after resume completes, only if the GPU is still active (pm_runtime_get_if_active); if it has
  gone back to sleep first, the events stay pending for the next real wake. Replay never itself wakes the GPU.
- A module parameter `nv_acpi_defer` (default 1) turns it off without rebuilding (0 = stock behaviour).
- Read-only counters (module params) `nv_acpi_deferred`, `nv_acpi_replayed` so the effect is measurable.
- Display hotplug probe (0x80 on PEGP / ACPI_VIDEO_NOTIFY_PROBE) is NOT deferred — a monitor plug must work instantly.
- When the GPU is awake, behaviour is byte-for-byte stock.
- Survives driver upgrades: an apply script re-applies the patch (or refuses loudly if it no longer applies — stock behaviour then).

## Hunted blind spots → decisions
- Event arrives while GPU is *resuming* (not "suspended") → handled stock (may already be waking anyway).
- Event arrives, GPU resumes before we store it → handler re-checks after storing and schedules replay itself.
- Two events of same kind while asleep → keep newest D-level / AC value; GPS and NVPCF are flags.
- Module unload with work pending → cancel work, drop pending (driver re-inits everything on next load).
- System suspend/resume (not runtime) → pending survives; replayed on next runtime-active.
- Shared nvidia_stack_t: replay uses its own allocated stack, never the notifier's.
- Unpatched version upgrade → apply script fails closed: no patch, stock driver, warning in journal.

## Done means
1. With the GPU asleep: `asusctl fan-curve --enable-fan-curves true` (proven NPCF 0xC0 source), charger plug/unplug, and charging
   under heavy CPU load cause **0** dGPU wakes; `nv_acpi_deferred` counts them.
2. When something real uses the GPU (nvidia-smi / CUDA), the pending events replay once (`nv_acpi_replayed` rises) and
   `nvidia-smi -q -d POWER` shows sane limits. CUDA works.
3. GPU goes back to sleep normally afterwards.
4. `nv_acpi_defer=0` restores stock wake behaviour (proves the patch is the cause of the difference).
5. Patch + apply/revert script + pacman hook in repo; rollback in one command.
