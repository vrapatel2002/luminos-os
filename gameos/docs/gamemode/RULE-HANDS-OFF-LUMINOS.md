# docs/gamemode/RULE-HANDS-OFF-LUMINOS.md — STANDING RULE, set by Shawn 2026-09-20
# [CHANGE: claude-code | 2026-09-20]

## The rule

**Luminos is the reference installation. It does not change.**

No packages installed. No `/etc` edits. No systemd units. No driver rebuilds. No
persistent config changes of any kind for gaming-OS work. Luminos exists to *run* tests
and produce measurements — it is not the place any of this gets built or deployed.

**Everything is built elsewhere. When it is finished and tested, it all moves to the new OS.**

## What that means in practice

| activity | where |
|---|---|
| Cloning, compiling, patching (DXVK, probes, daemons) | **Cowork cloud container** — Ubuntu 24.04, full toolchain, no consequence |
| Toolchain installs (meson, mingw-w64, glslang) | **Cloud container only.** `luminos-brain safe` already said NO twice for this box; that answer stands and should not be overridden for convenience |
| Running a test binary | Luminos, from `/tmp`, through `dgpu-exec-v2` |
| Testing a patched library | Per-game Lutris override only (System options -> a single env var), reversible by deleting one line |
| Anything that writes to `/etc`, installs a package, or changes a daemon | **Not on Luminos. Ever.** |

## Allowed, because it is transient and self-reverting

- Writing and compiling a probe in `/tmp` (the toolchain for these is already present)
- Launching a game and logging it
- Reading sysfs and `/proc/vmstat`

## Explicitly forbidden after the 2026-09-20 incident

- **`swapoff -a`.** The rehearsal harness did this and permanently dropped
  `/swapfile.luminos`, because `luminos-pagefile` owns it and it is not in `/etc/fstab`.
  Repaired, and the harness is patched — but the general lesson stands: **no global
  state-clearing commands on this machine.**
- Writing to `~/.config/MangoHud`, `~/.config/lutris/system.yml`, or any other live config.
  Use `MANGOHUD_CONFIGFILE` and per-game overrides instead.

## Audit at the time this rule was written

Verified on 2026-09-20 after a full session of gaming-OS work:
- **No packages installed** (`pacman.log` clean) — brain said NO twice, both honoured
- **No `/etc` changes attributable to this work** (the `asusd`/`supergfxd` files touched
  that day are daemon-restart artifacts from a reboot)
- `power_dpm_force_performance_level` restored to `auto`; `platform_profile` is managed
  dynamically by `luminos-power`, not by us
- `~/.config/MangoHud` never created; Lutris configs byte-identical to the repo copies
- Swap repaired and confirmed to survive a reboot via `luminos-pagefile`
- **One violation**, the swapfile incident above, repaired and fixed at the source

The only remaining footprint is documentation and probe source in this repo.

## Open question for Shawn

The gaming-OS work currently lives inside the Luminos repo (`docs/gamemode/`,
`tools/vram-probe/`, `tools/gamemode-bench/`) following the precedent set by
`FEASIBILITY.md`. Given the rule above and the standing position that this is a
**separate project**, it may belong in its own repository instead. Not moved unilaterally.
