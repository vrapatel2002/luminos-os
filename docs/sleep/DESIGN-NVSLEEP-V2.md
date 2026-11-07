# nvsleep v2 — design proven against the kernel source BEFORE any code
# [CHANGE: claude-code | 2026-11-06]  Source: docs/sleep/ksrc/ = Linux v7.0 (machine runs 7.0.5).

## What went wrong in v1 (live run 2026-11-06 17:47, /var/tmp/nvsleep-live/20261106-174705/)
Topology (sysfs, 2026-11-06): root port 0000:00:01.1 (ACPI \_SB.PCI0.GPP0, pcieport) → bus 01 = only 0000:01:00.0
(nvidia) + 0000:01:00.1 (snd_hda_intel; child hdaudioC0D0 + sound/card0 + inputs). GPP0 power_resources_D0/D2/D3hot =
PG00 (LNXPOWER:00); no D3cold list ⇒ port D3cold == PG00 OFF == the whole slot unpowered. No power_resources_wakeup
(so acpi_enable_wakeup_devices never powers PG00, drivers_acpi_wakeup.c:38-53).
1. THE SLOT IS RE-POWERED BEHIND RM. pcieport sets NO_DIRECT_COMPLETE|SMART_SUSPEND but NOT MAY_SKIP_RESUME
   (portdrv.c:707) ⇒ device_suspend sets must_resume=true (main.c:1924) ⇒ resume_noirq runs pci_pm_resume_noirq(port)
   (pci-driver.c:976): pci_pm_default_resume_early powers the port D3cold→D0 (= PG00 _ON = slot power ON), then
   pci_pm_bridge_power_up_actions → pci_resume_bus(children) (pci-driver.c:594-616). Measured: 722 ms. The card is now
   physically powered/uninitialised while RM believes it is in RTD3, and v1 also ran pci_pm_resume(card), which restored
   its config (pci-driver.c:1018-1027). RM later ran its RTD3-exit on a card that never went through RTD3-exit power-up.
   Result: "Unable to determine the device handle", NVRM status 0x11 on every ACPI event, dead until reboot.
2. A SECOND WAKER AT EVERY RESUME. hda_codec_pm_complete (sound_hda_common_codec.c:2941-2952) calls
   pm_request_resume(codec) for HDMI codecs → codec → parent 0000:01:00.1 → device-link supplier 0000:01:00.0 (the
   kworker stack rpm_resume→rpm_resume→rpm_callback→rpm_get_suppliers in idle-trace.txt:121-135). The syscore flag
   v1 put on 01:00.1 did not cover its CHILD hdaudioC0D0, whose complete() still ran.
3. A THIRD WAKER (user space): luminos-brightness.service (2026-05-08, undocumented) runs after every wake:
   `echo 399000 > amdgpu_bl2/brightness && echo 100 > nvidia_0/brightness` — forces the panel to 100 % and its nvidia_0
   write goes nvKmsSetBacklight → RM → wakes the card (idle-trace.txt:225-249), then fails EINVAL.

## The principle of v2
While the system sleeps, the dGPU's whole slot is owned by RUNTIME PM only. If at PM_SUSPEND_PREPARE the port, the
card and every function on bus 01 are runtime-suspended (slot unpowered, RM state saved by RM itself), the system-sleep
machinery must not touch ANY device in that subtree — so nothing powers the slot, nothing restores config, nothing
queues a resume. After resume the subtree is bit-for-bit in the state RTD3 left it, which is the state RM handles
every day. The only way the card ever powers up again is the normal runtime path (port runtime resume → PG00 _ON →
card pci_pm_runtime_resume → nv_pmops_runtime_resume), exactly as when an app opens it today.

## Mechanism (kernel facts it relies on, all from ksrc)
- dev->power.syscore = true (dev_pm_syscore_device) makes the PM core skip a device's prepare/suspend/late/noirq/
  resume_noirq/early/resume/complete CALLBACKS: main.c:2146 (prepare), :1902 (suspend), :1656 (late), :1446 (noirq),
  :737 (resume_noirq), :912 (early), :1051 (resume), :1213 (complete). It still does, symmetrically:
  prepare pm_runtime_get_noresume (:2137) ↔ complete pm_runtime_put (:1247); late pm_runtime_disable (:1654) ↔
  early pm_runtime_enable (:947). So runtime PM is OFF for the subtree from late-suspend to early-resume, and the
  get_noresume blocks runtime suspend (irrelevant: already suspended). Syscore devices never call
  dpm_superior_set_must_resume (that is inside device_suspend_noirq after the syscore goto, :1446/:1495).
- s2idle never re-syncs ACPI power resources (acpi_s2idle_restore, drivers_acpi_sleep.c:821-841; the resync
  acpi_resume_power_resources is S3-only, :505). So PG00 stays OFF across the whole sleep.
- The PCI core touches a device only through those callbacks; pci_pm_complete (pci-driver.c:763) is skipped too.
- pm_wakeup_pending() is checked in device_suspend (:1896) and device_suspend_late (:1640); pm_system_wakeup() (exported
  GPL) makes it true and also ends an s2idle in progress ⇒ a clean, built-in way to ABORT a sleep.

## Exact behaviour
PM_SUSPEND_PREPARE, only if nv_sleep_skip_idle && pm_suspend_target_state == PM_SUSPEND_TO_IDLE (exported GPL):
  a. For every nvidia GPU in nv_linux_devices: port = pci_upstream_bridge(pdev). Conditions (ALL, else stock path):
     port exists; every pci_dev on port->subordinate is in the GPU's slot (PCI_SLOT equal); pm_runtime_suspended() is
     true for port, and for every device on port->subordinate.
  b. Set syscore on the port device and on EVERY descendant device of the port (device_for_each_child, recursive:
     pci devs, port services pcie00x, hdaudioC0D0, sound/card0 and its children, drm/backlight/i2c children of the card).
  c. Set nv_sleep_skipping = TRUE, down_write(&nv_system_pm_lock) (blocks /dev/nvidia* open + ioctl as the stock path
     does), DO NOT call nv_suspend_devices. nv_system_power_state = IN_STANDBY.
PM_POST_SUSPEND (delivered after success AND after an abort, pm_notifier_call_chain_robust):
  if nv_sleep_skipping: walk the same subtree and clear syscore on every device (idempotent, covers devices added in
  between), up_write, nv_sleep_skipping = FALSE, nv_system_power_state = RUNNING, DO NOT call nv_resume_devices,
  nv_sleep_skipped++. One printk(KERN_INFO) line each way.
Race guard: in nv_pmops_runtime_resume (and only while nv_sleep_skipping): call pm_system_wakeup() BEFORE resuming,
  and log it. Any kernel path that powers the card during the window (nvkms backlight, a DRM ioctl, an ACPI replay)
  therefore aborts the system sleep cleanly; POST then clears syscore and the card is simply awake under RM's control.
  (Before late-suspend runtime PM is enabled so such a resume works normally; after late-suspend it is disabled for
  the subtree, so no resume can start; tasks are frozen; pm_wq is freezable.)
Everything else = STOCK. v1's changes to nv-pci.c (SMART_SUSPEND/MAY_SKIP_RESUME), nv_pmops_suspend/resume/suspend_late
  changes and the PCI-state re-save are REMOVED: with the card syscore none of its system callbacks run.
Hibernate (PM_HIBERNATION_PREPARE) and deep S3: stock, untouched.

## Why the three problems cannot recur
1. Port is syscore ⇒ pci_pm_resume_noirq(port) never runs ⇒ PG00 never switched on ⇒ no D0-uninitialised card, no
   config restore. 2. hdaudioC0D0 is a descendant ⇒ its complete() never runs ⇒ no pm_request_resume. If something else
   does request a resume after early-resume, it is a normal runtime resume of a card in genuine RTD3 (safe).
3. User space: replace luminos-brightness.service by a system-sleep hook that saves amdgpu_bl2 at `pre` and writes it
   back at `post` only if it changed; never touches nvidia_*.

## Residual risks (to test, not to argue)
- A device in the subtree whose runtime PM is enabled but which is NOT runtime-suspended (e.g. class devices with
  "unsupported" runtime status) gets no system callbacks while the slot is off — correct, there is no hardware to save.
- If firmware/EC powers PG00 on its own during s2idle (not seen), the card would be D0-uninitialised at resume. Test:
  read LNXPOWER:00 resource_in_use and 0000:01:00.0 power_state right after resume; card must still be D3cold.
- Wake-up from a USB-C/HDMI hotplug on the dGPU: port syscore ⇒ its PME/hotplug wake not armed for system sleep.
  Accepted (SPEC: only lid + power button wake).

## v2.1 — corrections from the design review (briefs/review3.txt.out, Fable xhigh, verdict "unsound as written,
## sound with these changes"). THESE OVERRIDE the "Exact behaviour" section above where they differ.
1. pm_suspend_target_state is still PM_SUSPEND_ON inside the notifier (set later in suspend_devices_and_enter). So:
   NOTIFIER (PM_SUSPEND_PREPARE): if param && port/card/all bus-01 functions runtime-suspended → mark syscore on the
   PORT and EVERY descendant EXCEPT the card itself; nv_sleep_skipping = TRUE; down_write(nv_system_pm_lock); skip
   nv_suspend_devices. Else stock.
   CARD .prepare (new nv_pm_ops.prepare, runs after freeze_processes, called from pci_pm_prepare): if !nv_sleep_skipping
   → return 0 (stock-equivalent: nvidia already sets NO_DIRECT_COMPLETE). If skipping: require pm_suspend_target_state
   == PM_SUSPEND_TO_IDLE, pm_runtime_barrier(port), and pm_runtime_suspended() of port, card and every bus-01 function;
   then dev_pm_syscore_device(card, true) and return 0. Otherwise return -EBUSY (NOT -EAGAIN, main.c:2247 swallows it)
   → dpm_prepare aborts, POST clears everything, luminos-lid retries. (Closes the notifier→freeze window too: anything
   that woke the card before freeze is caught here.)
2. RM must never be entered while the subtree's runtime PM is disabled (late-suspend..early-resume): rpm_resume returns
   -EACCES and nv_indicate_not_idle ignores it → RM programs an unpowered GPU → lost until reboot.
   a. nvdefer's defer condition becomes `pm_runtime_status_suspended(dev) || nv_sleep_skipping` (nv-acpi.c:168 area).
   b. While nv_sleep_skipping: the ACPI handlers (nv_acpi_notify_event, NVPCF, power-source) defer the kinds nvdefer
      knows (latest value kept, replayed on the next real wake as today) and DROP + log every other event before any
      rm_* call.
   c. Defensive: nv_indicate_not_idle returns an error (balancing its usage-count get with pm_runtime_put_noidle) if
      the device is still pm_runtime_status_suspended after its resume attempt, and logs it.
3. POST: clear syscore on card + port + all descendants; dev_pm_set_strict_midlayer(card, false); if the card is
   status-suspended but the port is not (a queued port resume ran at late-suspend, finding 4) → pm_request_resume(card)
   once + log (resyncs through the normal path). up_write; nv_sleep_skipping = FALSE; nv_sleep_skipped++ only if the
   card's .prepare had set syscore (i.e. the sleep really skipped).
4. Race guard in nv_pmops_runtime_resume kept: if nv_sleep_skipping → pm_system_wakeup() (log only if
   pm_suspend_target_state != PM_SUSPEND_ON).
5. Corrections: the port's wake GPE IS armed in s2idle via its runtime-wake prepare_count (dGPU hotplug wakes the box
   exactly as stock — harmless, do not touch port wakeup). dev_pm_syscore_device is in include/linux/device.h.
   Stale direct_complete can leave some descendants' runtime PM enabled during sleep — balanced, harmless.
Allowed calls (from review): dev_pm_syscore_device, device_for_each_child, pci_upstream_bridge, pci_walk_bus or
pci_get_slot/pci_dev_put, pm_runtime_suspended, pm_runtime_status_suspended, pm_runtime_barrier (prepare, port only),
pm_request_resume (POST only), pm_runtime_get_noresume/put_noidle, pm_system_wakeup, pm_suspend_target_state (read in
.prepare/.runtime_resume only), dev_pm_set_strict_midlayer(card,false), existing locks/printk.
FORBIDDEN in the skip path: pm_runtime_disable/enable, pm_runtime_set_active/suspended, forbid/allow, pci_save_state/
pci_restore_state/pci_set_power_state, any dpm_*, device_set_pm_not_required, ACPI power calls,
nv_suspend_devices/nv_resume_devices, extra dev_pm_set_driver_flags. v1's nv-pci.c flag changes and pmops changes are
REMOVED (main.c:771-772 pm_runtime_set_active is what left the card "active" behind RM in v1).
