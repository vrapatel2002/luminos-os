# SPEC — strong sleep, quick wake (G14 GA403UU, Luminos)
# [CHANGE: claude-code | 2026-11-06]

## What Shawn wants (his words)
"make the sleep strong — sleep means sleep, nothing else — and also make the wake up quick and faster."

## Measured today (docs/sleep/SESSION-2026-11-05-06.md, /var/tmp/sleeptest/)
- Deep sleep itself works: 34.9 s of 40 s in hardware S0i3.
- Sleep ENTRY costs 2.4-4.5 s and resume 0.8 s extra because the NVIDIA driver WAKES the RTX 4050 out of D3cold:
  stack: nv_pm_notifier → nv_set_system_power_state → nvkms_suspend → nvShutDownApiHeads → nvSetDispModeEvo →
  nvRmSetGc6Allowed → RM control → nv_indicate_not_idle → rpm_resume(0000:01:00.0). And even without that, the
  driver sets DPM_FLAG_NO_DIRECT_COMPLETE (kernel-open/nvidia/nv-pci.c:2251) and no DPM_FLAG_SMART_SUSPEND, so the
  PCI core's pci_pm_suspend() runtime-resumes the card anyway. Resume pays again (PCIe port 00:01.1 noirq 0.6 s).
- First attempt often ABORTS: wakeup source `mmc0` (empty SD reader, rtsx_pci_sdmmc) wakeup_count=3 this boot.
- AC adapter (ACAD) is a wake source (wakeup_count 2): plugging/unplugging the charger wakes the machine.
- luminos-lid fires ONE `systemctl suspend` per lid close and never checks it happened; a failed or vetoed attempt
  leaves the laptop awake with the lid shut (PowerDevil's own retry is vetoable by app inhibitors).
- A spontaneous wake with the lid shut (seen 10-31 23:10→23:18) relies on luck to re-sleep.

## Done means (plain language)
1. Lid shut ⇒ laptop asleep, always. A failed/aborted/vetoed attempt is retried until it sleeps (never gives up
   while the lid is shut). If it wakes by itself with the lid still shut, it goes back to sleep within ~7 s.
2. While asleep only the lid and the power button wake it. Not the charger, not USB devices, not HDMI/USB-C/USB4,
   not the SD reader, not Wi-Fi.
3. The NVIDIA card is NOT powered up to go to sleep or to wake up when it was already off. Measured: zero
   rpm_resume of 0000:01:00.0 during a test sleep, the NVIDIA PM notifier < 0.2 s (was 2.4 s).
4. After waking the NVIDIA card still works (a CUDA/nvidia-smi run through dgpu-exec-v2 succeeds) and goes back
   to sleep by itself; if the card WAS busy when the lid closed, sleep still works (stock path) or aborts cleanly
   and is retried — never a hang, never a dead card.
5. Entry time (lid close → hardware sleep) and resume time measured before/after; both lower.
6. Everything has a one-command revert and is documented (AGENTS.md §9, LUMINOS_DECISIONS.md, BUGS.md).

## Assumptions (gaps filled with defaults)
- Idle-suspend stays OFF (DECISION 105). Only lid-close (and manual Sleep) are in scope.
- Lid shut with an external screen still sleeps (today's HandleLidSwitchDocked=suspend). No clamshell mode.
- Internal keyboard (ASUS 0b05:*) may keep USB wake (only reachable with the lid open). All other USB devices: no wake.
- Retry schedule while shut: 2 s, 5 s, 10 s, then every 30 s. Grace 5 s after any resume before re-sleeping, so a
  real lid-open is never fought (lid state may lag a resume).
- SD reader: unbound just before sleep, re-bound just after → SD cards still work when awake.
- Hibernate is untouched (stock NVIDIA path) — the broken low-battery hibernate is BUG-228, a separate job.
- NVIDIA change = DKMS patch on the open kernel modules (same mechanism as nvdefer, DECISION 147), module param
  `nv_sleep_skip_idle` (default 1, 0 = stock behaviour at runtime), applied after nvdefer by luminos-nvidia-defer.
- Loading the patched module needs ONE reboot — the PM asks Shawn before rebooting.
