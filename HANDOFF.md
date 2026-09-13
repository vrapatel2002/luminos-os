# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-13

> **The previous goal is not abandoned — it is parked.** This file was carrying an
> in-progress note for the `org.luminos.style` QML work (shape done, size not started).
> That note is preserved at **`git show 4273ed7e:HANDOFF.md`**. Read it before resuming
> that task; do not try to reconstruct it from memory.

## Goal (the durable end objective)
Gaming on Luminos actually uses the RTX 4050, and the system stays current without an
upgrade quietly breaking something that only shows up at the next login.

## Aim right now
**Done and verified.** Nothing is mid-flight. The one outstanding action is a **reboot**,
which is Shawn's to take whenever convenient.

## Why / motivation (context a newcomer would be missing)
Shawn asked for "the latest version of everything" for gaming. Installing the runners
surfaced a much bigger finding: **no Lutris game had ever been reaching the dGPU.** Not a
regression — it had never worked, and it was invisible because the AMD 780M is fast enough
that the symptom reads as "a bit slow" rather than "no picture".

## Process / approach being used
Fix it **without weakening the gate**. The one-command answer (`usermod -aG dgpu shawn`)
was rejected on purpose — it would delete DECISION 25 and re-open the 8 W idle regression
(BUG-047) and the VRAM contention DECISION 81 exists to arbitrate.

## State — what is DONE

**1. Lutris routed through the dGPU gate (DECISION 90).**
`~/.config/lutris/system.yml` → `prefix_command: dgpu-exec-v2 --` + `mangohud: true`.
Repo copy: `config/lutris-system.yml`.

**2. Gaming stack brought current.**
GE-Proton11-6 into Lutris runners **and** Flatpak Steam's `compatibilitytools.d`;
mangohud 0.8.4 + lib32-mangohud + nvidia-prime; Flatpak MangoHud Vulkan layer 25.08.

**3. Full `pacman -Syu` — 522 packages, five weeks stale — completed with pins intact.**
`nvidia-utils` held at 610.57.04 (615.71.09 ignored), `linux` held at 7.0.5 (7.2.4
ignored). glibc 2.44+r24, systemd 261.3, mesa 26.2.2, plasma-workspace 6.7.5,
qt6-base 6.11.2-3. Three hand-built KCMs survived — 0 missing libs, checked.

**4. BUG-155 caught and fixed before Shawn could hit it.**
The Qt6 bump made `quickshell-git` unloadable (`Qt_6_PRIVATE_API`), which would have
killed **both** Caelestia greeter sessions at the next login. Rebuilt to
`0.3.1.r11.ge3d52a7-1`.

**5. 53 GB reclaimed** — three abandoned 007 First Light directories under `/mnt/win-os`.

**6. Docs updated** (this was the explicit ask): DECISION 90, DECISION 26 amendment,
BUG-155, AGENTS.md §1/§9/§14, LUMINOS_STATUS.md, docs/CODE_REFERENCE.md,
docs/LUMINOS_HANDBOOK.md Part 5.7, and the stale scope comment in `dgpu-exec-v2.c`.

## State — what is IN PROGRESS
Nothing.

## Next steps (ordered)
1. **Reboot.** glibc and systemd were both upgraded; the running system is on the old ones.
   Nothing is known to be broken — this is hygiene, not a fix.
2. **Confirm a game actually renders on the card.** Launch anything in Lutris, then
   `dgpu-exec-v2 -- nvidia-smi`. If the game is not in the process list it is on the 780M,
   regardless of what MangoHud claims.
3. **Build DECISION 26 rung L3** (AGENTS.md §14 item 0f) — auto-rebuild the custom AUR
   builds after an upgrade, and *read the result back*. BUG-155 is the case for it.
4. Optional, deliberate: the NVIDIA 610.57.04 → 615.71.09 unpin window, following the
   DECISION 26 procedure (unpin → upgrade → DKMS rebuild → verify true-0W gating + KCMs
   → re-pin). Not urgent. Nothing is asking for it.

## Key decisions & constraints so far
- **shawn stays out of the `dgpu` group.** Non-negotiable — it is the whole of DECISION 25.
- **`dgpu-exec-v2` is the gate for nearly everything now**, and its own header comment plus
  AGENTS.md §9 both still claimed it was "wired into `chrome-luminos` only". Re-grepped and
  corrected. v1 `dgpu-exec` is down to **one** caller — the Caelestia VRAM card's
  `nvidia-smi` query. Repoint that and v1 can be deleted. A change to v2 now changes how
  games launch, not just Chrome.
- Kernel + NVIDIA stay pinned (DECISION 26). Moving them is a deliberate window, never a
  side effect of `-Syu`.

## Gotchas / dead-ends / things NOT to redo
- **`prime-run` does nothing on this machine.** It sets environment variables; the obstacle
  is file permissions on `/dev/nvidia*`. Its `Found no drivers!` /
  `ERROR_INCOMPATIBLE_DRIVER` output looks like a broken driver and is not one. Do not
  spend time on it again.
- **v1 `dgpu-exec` is not a substitute here.** Lutris launches through shell/python
  wrappers which reset the effective gid (BUG-102), and v1 does not re-assert the NVIDIA
  vendor env past the `/etc/environment` Mesa pin (BUG-145).
- **Do not put `mangohud` into `prefix_command`.** Lutris prepends it *before* the prefix,
  so `mangohud: true` already yields the correct `dgpu-exec-v2 -- mangohud <game>`. Doing
  it by hand inverts the order and the overlay loses GPU access.
- **Flatpak Steam does not read `~/.local/share/Steam/compatibilitytools.d/`** — the path
  every guide names. It reads `~/.var/app/com.valvesoftware.Steam/data/Steam/...`.
- **`lib32-libpcap` is gone from the Arch repos.** If something reinstalls
  `wine-ge-custom-bin-opt` (discontinued — GE-Proton8-26 was its last release), every
  future `-Syu` blocks again. `checkupdates` and `pacman -Qu` will not warn you; it only
  appears at dependency resolution.
- **`luminos-brain safe` misfires on pacman actions** — it returns the pyenv/ML rule
  ("NO: ML/AI always use pyenv 3.12.13") for system package work. Re-run with an explicit
  `--reason` naming pacman/no-Python to get the override. This is AGENTS.md §14 item 0b,
  still open.
- **A `-Syu` post-transaction wall is 35 hooks long and a fatal finding is one line in it.**
  BUG-155 was hook 32/35 and the transaction still reported success. Read it, or build L3.

## Files touched / relevant files
**Live system (not in the repo):**
- `~/.config/lutris/system.yml` — new; the whole of DECISION 90

**Repo:**
- `config/lutris-system.yml` — repo copy of the above
- `scripts/dgpu-gate/dgpu-exec-v2.c` — SCOPE comment corrected (comment only, no code)
- `LUMINOS_DECISIONS.md` — DECISION 90; DECISION 26 amendment
- `docs/BUGS.md` — BUG-155
- `AGENTS.md` — §1 Plasma version, §9 two rows corrected + one added, §14 item 0f
- `LUMINOS_STATUS.md` — new top entry + 3 System rows
- `docs/CODE_REFERENCE.md` — `config/lutris-system.yml`
- `docs/LUMINOS_HANDBOOK.md` — new Part 5.7 (gaming / why prime-run does nothing)

**Untouched on purpose:** the `org.luminos.style` work in `config/qml/` and
`scripts/luminos-qml-style-build`, and the initramfs-looking untracked tree at the repo
root (`init`, `kernel/`, `usr/`, `etc/`, `lib`, `sbin`, `hooks/`). Neither was part of this
task and neither was staged. **Find out what that tree is before anyone commits or deletes
it** — it may be someone's in-progress work.
