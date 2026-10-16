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
