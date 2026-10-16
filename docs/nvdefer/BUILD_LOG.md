# nvdefer build log
- 2026-10-16 15:55 Charger matrix finished (USB-C full / USB-C charging / brick full / battery / cable edges). Only charging and
  cable edges wake the dGPU; all via ACPI notifies the nvidia driver turns into a full GPU power-up. Chose the driver-side fix
  (defer + replay) over (a) charge limit — only hides charging, does nothing for cable edges, costs Shawn 20 % battery; (b) killing
  asusd curve writes — covers 1 of 4 sources and risks fan behaviour; (c) ACPI table override — AGENTS/BUG-198 said not recommended.
  Precedent: NVIDIA PR #1299 (NPCF only, unmerged). Extended to PEGP D-notifier, GPS 0xC0 and AC events, which are 3 of our 4 sources.
- nvidia-powerd is masked on this box → NPCF events have no consumer at all; deferring them loses nothing.
- Workers: implementer (Opus) and test writer (Opus) spawned in parallel, each only sees SPEC + CONTRACTS.
- Loading the new module needs a reboot (or a module reload that would make KWin drop the NVIDIA DRM device — not worth risking
  Shawn's session). Plan: install via DKMS, ask Shawn for one reboot, then run tests/nvdefer/live.sh.
- 16:10 Tester delivered tests/nvdefer/{lib,static,live,charger}.sh (thresholds fixed in headers). Implementer delivered the
  patch (2 files, 160 added lines, compiles clean, modinfo shows the 3 params), scripts/luminos-nvidia-defer, pacman hook.
  static.sh: ALL PASS. File boundary held (tester only tests/nvdefer, implementer no tests/). Reviewer (Fable) spawned on the
  patch before anything is installed — kernel code, so no install until it is clean.
- 16:25 Review (Fable): 1 blocking (nvidia loads from the initramfs — script never rebuilt it, so the patched module would never
  have booted), 1 high (stale held value could overwrite a newer live one), 4 medium (race skipping replay; patch fuzz; root
  compiling a user-writable patch; one bad kernel reverting all). Kernel-side locking/refcount/UAF checked clean. All sent back to
  the implementer; contract re-planned (budgets 180/150, hook renamed). Tester asked to update static checks to the new contract.
- 16:40 Round-2 review: all 7 fixed, "no blocking findings, safe to install". static.sh ALL PASS (14/14) after the tester fixed its
  own -F0 false negative (the check missed an options array — test bug, not code bug).
- 16:42 Installed: `sudo scripts/luminos-nvidia-defer --install` → dkms build+sign OK, mkinitcpio OK, --check: source patched,
  initramfs nvidia.ko == patched dkms module; loaded module still stock until reboot. Backup: /boot/initramfs-linux.img.pre-nvdefer.
  Rollback: `sudo luminos-nvidia-defer --revert` then reboot (or runtime: `echo 0 | sudo tee /sys/module/nvidia/parameters/nv_acpi_defer`).
