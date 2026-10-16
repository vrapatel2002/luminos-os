# nvdefer contracts (frozen)
Source: /usr/src/nvidia-610.57.04 (nvidia-open-dkms 610.57.04-1). Work copy: ~/luminos-os/patches/nvdefer/work/ (never edit /usr/src by hand).
Patch file: ~/luminos-os/patches/nvdefer/nvdefer-610.57.04.patch (unified diff, -p1 relative to the source root). Touches ONLY
kernel-open/nvidia/nv-acpi.c and kernel-open/nvidia/nv.c (+ kernel-open/nvidia/nv-linux.h or a new header only if unavoidable).
Must not touch src/ (the RM core).

Kernel-open API added:
  module params (nvidia.ko): nv_acpi_defer (int, 0644, default 1); nv_acpi_deferred, nv_acpi_replayed (ulong, 0444)
  void nv_acpi_defer_on_runtime_resume(nv_linux_state_t *nvl);   // called from nv_pmops_runtime_resume on success
  void nv_acpi_defer_cancel(void);                                // called on notifier unregister / module exit
Intercepted handlers (only when nv_acpi_defer && dGPU pm_runtime_suspended):
  nv_acpi_notify_event: events 0xC0 (GPS), 0xD1..0xD5 → pending; others stock
  nv_acpi_nvpcf_event: ACPI_NVPCF_EVENT_CHANGE → pending
  nv_acpi_powersource_hotplug_event: 0x80/0x00 → pending latest !ac_plugged
Replay order: power source, GPS, D-level, NVPCF. Each via the unchanged rm_* entry point.

Script: ~/luminos-os/scripts/luminos-nvidia-defer  --apply | --revert | --check   (root; exit 0 ok, 1 failed, 2 patch no longer applies)
  --apply: patch /usr/src/nvidia-<ver> (idempotent), dkms build+install, keeps pristine copy of the 2 files as *.nvdefer-orig
Pacman hook: ~/luminos-os/config/pacman-hooks/luminos-nvidia-defer.hook (PostTransaction on nvidia-open-dkms → --apply)
Budgets: patch ≤ 160 added lines; any new function ≤ 40 lines; nesting ≤ 3. Script ≤ 120 lines.
