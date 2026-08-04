# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-08-04 — Response 1 (Cowork session; Hyprland + Caelestia — **PLANNING ONLY, NOTHING INSTALLED**)

## FIRST ACTION IN A NEW CHAT
Read this file, then `cat ~/luminos-os/AGENTS.md`. The **active thread is a proposed
Hyprland + Caelestia Shell install** (below). **Nothing has been installed, nothing has been
changed on disk, and the user has not yet approved the ban override.** Do not start installing.

---

# ACTIVE THREAD — Hyprland + Caelestia — PHASE 3 INSTALLED, AWAITING FIRST LOGIN TEST

## Goal (the durable end objective)
User (2026-08-04) sent https://youtu.be/Na7tPZv2ckk — *"Install Hyprland + Caelestia Shell
(Complete Guide)"* by **Lau (@laustoic)** — and asked to install it, with two hard conditions:
1. **Push everything to git first** so there is a way back if it breaks.
2. **A detailed plan that assumes the Claude Desktop app may crash mid-install** —
   "I don't want to be stranded in a broken OS."

## ✅ BLOCKER CLEARED — the ban was lifted by the user on 2026-08-04
The user's words, verbatim: *"bro its no longer banned now got it? you can start now working on
all phase just make sure that you have claude desktop running in hyprland got it ?"*
Plus, on ownership: *"its all your project got it ?"* — make the calls, don't ask permission for
each step.

**Two things follow from that message:**
1. The ban is lifted; Phases 0–5 are all authorised in one go.
2. **New hard acceptance criterion for Phase 3:** Claude Desktop (`claude-desktop-bin`, Electron)
   must actually run *under Hyprland*. A Hyprland session that starts but cannot run the desktop
   app is a FAILED phase, because it strands the user with no agent. Escape hatches already in the
   launcher if Electron misbehaves on Wayland: `CLAUDE_USE_XWAYLAND=1`, `CLAUDE_DISABLE_GPU=1|full`
   (`xorg-xwayland` is installed).

The historical objection, kept for context:
`AGENTS.md` §1 said **"PERMANENTLY BANNED: Hyprland, GTK4, HyprPanel, Python UI, Docker, Ollama,
Snapd."** That line is now factually wrong and **still needs editing in Phase 1.**

Also: **this ground was already covered and abandoned.** MemPalace surfaced BUG-035, BUG-036,
BUG-037 (March 2026) — an earlier Hyprland attempt on Ubuntu 24.04 that hit missing packages,
silent `set -e` build skips, and a too-old CMake. It was eventually built in a chroot, then the
whole direction was dropped in favour of KDE Plasma. **Arch changes the difficulty completely**
(Hyprland is a first-class Arch package now), so the old bugs are not predictive — but the
*decision* to drop it was deliberate and needs an explicit reversal.

**Required before any install:** a new numbered entry in `LUMINOS_DECISIONS.md` reversing the ban
(scope it: Hyprland allowed as an *additional, opt-in session*, Plasma stays the default), plus an
edit to `AGENTS.md` §1 so the banned list stops contradicting reality.
**✅ Both done 2026-08-04 — see `LUMINOS_DECISIONS.md` DECISION 39 and `AGENTS.md` §1.**

Note: **Caelestia itself never violated anything.** It is a Quickshell (Qt6/QML) shell — the same
Qt/QML stack Luminos already standardised on. Only **Hyprland** was the banned component, and that
ban is now lifted. **HyprPanel remains banned** — it is GTK4, banned on its own merits, and is not
part of this work.

## Git state — VERIFIED 2026-08-04, and it corrects two stale beliefs
| Claim | Reality |
|---|---|
| "two separate repos, luminos and server" | **One repo.** `server/` is a *directory* inside `luminos-os` (commit `01d33684` "give the media server its own directory"). One push covers both. |
| HANDOFF's "11+ commits unpushed, push is on hold" | **STALE — delete this belief.** `git rev-list --left-right --count origin/main...main` → `0 0`. `main` is fully in sync with `origin/main` (`git@github.com:vrapatel2002/luminos-os.git`). Nothing is waiting to be pushed. |

Working tree is clean apart from **3 dirty submodules**, and the dirt is worthless:
`research/turboquant/repo-{ggml,main,thetom-correct}` each have 4 deleted Windows `.bat` files
(`examples/sycl/win-*.bat`, `scripts/install-oneapi.bat`), plus one stray `cmake_log.txt` in
`repo-thetom-correct`. Those are *upstream llama.cpp* trees, not ours. Precedent (notes, 2026-07-30):
**"Left the 3 research/turboquant nested repos alone."** Keep doing that.

### ⚠️ THE REAL BACKUP HOLE — 8 gitlinks and NO `.gitmodules`
`git ls-files -s | awk '$1=="160000"'` returns 8 entries; **`.gitmodules` does not exist.**
Consequence: **a fresh `git clone` of luminos-os produces 8 EMPTY directories.** The commit
pointers are pushed, the mapping to fetch them is not. "Everything is pushed" is therefore false
for these paths:

| Path | Upstream (read from the local checkout — NOT recorded in the repo) |
|---|---|
| `reference_code/Triton-XDNA` | https://github.com/amd/Triton-XDNA.git |
| `reference_code/dragon-npu` | https://github.com/In2infinity/dragon-npu.git |
| `reference_code/mlir-aie` | https://github.com/Xilinx/mlir-aie.git |
| `reference_code/xdna-driver` | https://github.com/amd/xdna-driver.git |
| `research/turboquant/repo-ggml` | https://github.com/ggml-org/llama.cpp |
| `research/turboquant/repo-main` | https://github.com/ggerganov/llama.cpp |
| `research/turboquant/repo-pytorch` | https://github.com/tonbistudio/turboquant-pytorch |
| `research/turboquant/repo-thetom-correct` | https://github.com/TheTom/llama-cpp-turboquant |

Fix = write a `.gitmodules` with these 8 url/path pairs and commit it. Until then that table above
is the only record of where they came from.

## The thing the user most needs to hear
**Git does not protect against a broken OS.** The repo holds source and docs. It does **not** hold
`/etc`, `~/.config`, the KDE setup, or the installed package set. Pushing to GitHub is *not* a
rollback plan for "stranded in a broken OS" — the OS-level safety net has to be built separately
(see Pre-flight below).

## Machine facts gathered 2026-08-04 (all verified, don't re-measure)
- **Filesystem: ext4** on `/dev/nvme0n1p5` (629 G, 117 G free). **No btrfs → no cheap CoW
  snapshots.** `/boot` is on root; `/boot/efi` is `nvme0n1p1` (vfat, 260 M).
- **Timeshift IS installed and IS in rsync mode** (`btrfs_mode: false`). Two problems:
  1. **It excludes `/home/shawn/**` and `/root/**`.** Every Hyprland/Caelestia config lands in
     `~/.config` → **not covered by any snapshot.** Home must be backed up separately.
  2. **Exactly one snapshot exists: `2026-07-21_18-48-09` (58 G), and every schedule is off.**
  Backup target UUID `ff4655be-…` **is the root partition itself** — fine for undoing a bad config,
  useless if the disk dies.
- **`pacman -Sy` was last run 2026-07-21 — the package DB is ~14 days stale.** 5 upgrades pending
  against that stale DB; against a fresh DB it will be far more.
- **`/etc/pacman.conf` pins (live, verified):**
  `IgnorePkg = linux linux-headers nvidia-utils nvidia-open-dkms opencl-nvidia lib32-nvidia-utils lib32-opencl-nvidia`
- **`/etc/environment` (live, verified)** — the two lines that matter:
  `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json` (global force-Mesa;
  this is what keeps the dGPU at true 0 W — BUG-047/BUG-050) and
  `KWIN_DRM_DEVICES=/dev/dri/card2` (KWin-only, inert under Hyprland).
- **Sessions installed: `/usr/share/wayland-sessions/plasma.desktop` ONLY.** `/usr/share/xsessions/`
  is empty. Hyprland would *add* `hyprland.desktop` — **additive, Plasma is not touched.** This is
  the single most important safety property of the whole job.
- Packages: 1365 total, 216 explicit, **61 foreign/AUR**. `yay` present, `paru`/`pikaur` absent.
- **Nothing hypr/quickshell/caelestia is installed yet** — clean slate.
- Repo is 10 G on disk, `.git` alone is 3.8 G.

## The four real landmines (in priority order)
1. **PARTIAL UPGRADE — the top risk, and it is an Arch-killer.** The DB is 14 days stale *and*
   kernel + NVIDIA are pinned in `IgnorePkg`. `pacman -Sy hyprland` (sync-then-install-one) is the
   classic way to brick an Arch box. Hyprland pulls a live wayland/wlroots/mesa/libdrm stack that
   will be built against packages the pins hold back. **Never `-Sy` + `-S`. Full `-Syu` only, and
   decide deliberately what to do about the pins first** (AGENTS.md §9 documents the un-pin →
   upgrade → rebuild DKMS → verify 0 W gating → re-pin ladder).
2. **The NVIDIA env vars every Hyprland guide tells you to set.** Guides say to export
   `GBM_BACKEND=nvidia-drm`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`, `LIBVA_DRIVER_NAME=nvidia`,
   `WLR_DRM_DEVICES=…`. On this box that **directly undoes BUG-047/BUG-050** — the dGPU stops
   sleeping, ~8 W idle returns, and if it goes in `/etc/environment` it degrades **Plasma too**.
   **Rule: nothing NVIDIA goes in `/etc/environment`. Session-scoped inside `hyprland.conf` only.**
   The G14 renders on the **iGPU** (`card2`, renderD129, AMD); the dGPU is `card1`/renderD128 and
   should stay asleep. Hyprland must be pointed at the AMD node, not NVIDIA.
3. **What Plasma-only work stops existing under a Hyprland session** (none of it is *lost*, it just
   does not run there): all 5 `kcm_luminos_*` System Settings modules; the 3 Plasma widgets
   (`powerwidget`, `ramwidget`, `monitorwidget`); the **SUPER+SPACE HIVE popup** (a KDE global
   shortcut — must be rebound in `hyprland.conf`); `luminos-ram`'s **KWin D-Bus** integration; the
   `org.luminos.livewallpaper` plugin; the SDDM-Breeze/lock-screen match (DECISION 28).
   **The 5 Go daemons are systemd *system* units and are unaffected** — power, thermal and fan
   control keep working under Hyprland.
4. **AUR churn.** `quickshell`/`caelestia-shell` are AUR (`yay`), source-built against whatever libs
   are live at build time. With kernel/NVIDIA pinned, a mismatch is plausible. 61 foreign packages
   already in play.

## Plan — phased, each phase independently resumable
**Phase 0 — make "getting back" actually true — ✅ DONE 2026-08-04**
  a. ✅ `.gitmodules` written from the 8-row table above. All 8 URLs reachable AND all 8 pinned
     commits proven fetchable (`--filter=blob:none --depth=1`). Run the fetches as **flat top-level
     statements** — the sandbox silently breaks `$(...)` and some commands inside `while` loops and
     will report every repo as unfetchable, which is a lie.
  b. ✅ Package set → `backups/preflight-2026-08-04/` (216 explicit, 61 AUR, 1365 total w/ versions,
     plus enabled system+user units).
  c. ✅ `/etc` (3.4M), `~/.config` (11M), `~/.local/share` desktop dirs (3.4M) →
     `~/luminos-backups/preflight-2026-08-04/`. **These stay OUT of git — the repo is public and
     they contain wifi passwords and tokens.**
  d. ✅ Timeshift snapshot **`2026-08-04_14-35-50`** ("PRE-HYPRLAND baseline"). See the disk
     incident below — the config had to be fixed first.
  e. ✅ Escape card at `docs/ESCAPE-CARD.md`, every claim in it verified by running it.
  f. ✅ Session black-box `scripts/luminos-session-recorder` + user unit
     `luminos-session-recorder.service`, enabled and tested end-to-end.

### 🔥 Disk incident during Phase 0 — READ THIS, IT WILL RECUR
The first timeshift run **filled the root filesystem to 0 bytes free** and, in doing so,
**truncated `scripts/luminos-session-recorder` to 0 bytes** (it was untracked, so the work was
simply gone and had to be rewritten). Timeshift snapshots root *onto root* — same partition,
`/dev/nvme0n1p5`, 619 G.

Cause: timeshift's exclude list was only `/home/shawn/**` and `/root/**`, so it was trying to copy
`/srv/media` (82 G) and `/opt/rocm` + `/opt/cuda` (33 G) as if they were operating system. Its own
config recorded `snapshot_size: 174 GB` against 117 G free. It could never have fitted.

Fix applied (original saved as `/etc/timeshift/timeshift.json.bak-2026-08-04`) — added excludes:
`/srv/**`, `/opt/rocm/**`, `/opt/cuda/**`, `/var/cache/pacman/pkg/**`,
`/var/lib/systemd/coredump/**`, `/swapfile`. Snapshot then took **135 s and 8 G**.

Lessons that generalise:
- **`df -h /` before anything that writes in bulk.** A full root presents as unrelated random
  breakage — truncated files, failed logins, half-finished pacman transactions.
- **Commit early.** Untracked work has no floor under it.
- A `foo/**` exclude skips the *contents* and leaves an empty `foo/` — which is what you want,
  the directory survives a restore. Verify with `ls -A`, not `test -e`; `test -e` says "present"
  for the empty stub and looks like the exclude failed.
- Excluding `/var/cache/pacman/pkg` is deliberate: it keeps the 12 G / 760-package downgrade
  cache safe from being wiped by a restore.

**Phase 1 — decision + docs — ✅ DONE 2026-08-04.** `LUMINOS_DECISIONS.md` **DECISION 39** written
  (ban reversed, scoped to an opt-in session, with acceptance criteria and a reversal path), and
  `AGENTS.md` §1 amended so the banned list no longer contradicts reality. HyprPanel stays banned.
  Checked the whole repo for other places still asserting the ban; the only remaining hits are
  historical records (`docs/PROJECT_AUDIT_2026-04-27.md`) and are correct as history.
**Phase 2 — system upgrade — ✅ RUN 2026-08-04, 0 errors. REBOOT STILL PENDING.**
  135 packages, 2.6 GB, `pacman -Syu`, completed clean. Details below.
**Phase 3 — Hyprland only** (no Caelestia yet): install, minimal config, log out, pick Hyprland at
  SDDM, confirm it starts, confirm dGPU still asleep, log out, back to Plasma.
**Phase 4 — Caelestia Shell** on top of a Hyprland that is already known good.
**Phase 5 — reconnect Luminos**: rebind SUPER+SPACE → HIVE popup, decide what replaces the widgets.

## Escape card — ✅ WRITTEN, at `docs/ESCAPE-CARD.md`
Full version is in that file and every command in it was verified by running it. The user should
photograph it before Phase 2 — a card readable only on the broken machine is not a card. Core:
- **`Ctrl`+`Alt`+`F3`** → text login (TTY3). `F1`/`F2` gets back to the graphical one.
- **The agent survives a dead GUI**: `/usr/bin/claude` → `claude-code` **v2.1.101**, confirmed
  installed as a symlink to `../lib/node_modules/@anthropic-ai/claude-code/cli.js`.
  `cd ~/luminos-os && claude` from any TTY, and it reads this file to pick up the thread.
- **What broke, without needing memory**: `scripts/luminos-session-recorder --show`.
- Plasma is still there and unmodified; pick it from the SDDM session picker.
- Roll back the OS: `sudo timeshift --restore --snapshot '2026-08-04_14-35-50'` (works from a TTY).
  **This does not touch `/home`, `/srv` or the pacman cache** — see the exclude list above — so it
  cannot undo a bad `~/.config`; for that use `~/luminos-backups/preflight-2026-08-04/`.
- Downgrade one package instead: 760 cached versions in `/var/cache/pacman/pkg` (12 G), exact
  prior versions in `backups/preflight-2026-08-04/pkgs-all-with-versions.txt`.
- **`systemctl status luminos-power`** — if fans are dead at high temp, `sudo systemctl restart luminos-power`.

## Session black box — ✅ INSTALLED (this is how "resume" works)
`scripts/luminos-session-recorder`, run by the **systemd user unit**
`~/.config/systemd/user/luminos-session-recorder.service` (`WantedBy=graphical-session.target`),
enabled and verified — it produced `2026-08-04_14-38-19_KDE.txt`, 180 lines.

**Why a systemd unit and not `~/.config/autostart`:** XDG autostart is processed by the *desktop
environment*. KDE does it; a bare Hyprland does **not**. An autostart `.desktop` would have been
missing for exactly the session it was written to observe. `graphical-session.target` is honoured
by Plasma today and by Hyprland when launched via **uwsm — already installed at `/usr/bin/uwsm`**,
which is a strong reason to start Hyprland through uwsm in Phase 3 (it also gives correct
environment propagation and xdg-desktop-autostart).

Records land in `~/luminos-backups/session-log/`. It captures disk space, the systemd-logind
login/logout ledger, session-manager lifecycle, errors, coredumps, Hyprland's own log, the 5 Go
daemons, dGPU sysfs power state (**never `nvidia-smi`** — BUG-078), DRM vendor IDs, last 15 pacman
transactions, installed sessions.

Two design points worth not re-deriving:
- Filtering that section by *process name alone does not work*. kwin_wayland emits hundreds of
  routine QML/portal warnings and the video wallpaper pipes ffmpeg stream metadata through
  `kwin_wayland_wrapper`; both flood the tail and push the real login lines off the end. It now
  requires a process **AND** a lifecycle verb, and logind gets its own separate line budget.
- The final status block is **conditional and reads the file back** (greps for `=== END OF RECORD ===`)
  because Luminos scripts have a documented habit of printing success on a failed path
  (BUG-088/089). Negative-tested: with `HOME=/proc/nonexistent-readonly` it exits 1 and says so.

Useful fact discovered from the journal: **SDDM reads both `/usr/share/wayland-sessions/` and
`/usr/local/share/wayland-sessions/`** (the latter does not currently exist). Only
`plasma.desktop` is installed today.

## Crash-resilience rules for the install itself (the user's explicit ask)
- **Every long build runs inside `tmux`**, detached, so it survives the agent/desktop app dying:
  `tmux new -s hypr` → run → `Ctrl-b d` → reattach with `tmux attach -t hypr`.
- **Update this file at the end of every phase** with exactly what was done and what is next.
- **One phase per session.** Never two blast radii at once.
- **Never `git add -A`** (AGENTS.md/notes rule — it is how the old API key got published, and the
  tree still holds parked work). Stage by name.

## Phase 2 result — what the upgrade actually did (2026-08-04)

**135 packages, 2593 MB, `pacman -Syu`, exit clean, `grep -icE '^error|failed'` on the log → 0.**
Full log preserved at `~/luminos-backups/postupgrade-2026-08-04/phase2-upgrade.log` (it was written
to `/tmp`, which the reboot wipes). Post-upgrade package state is committed at
`backups/postupgrade-2026-08-04/pkgs-all-with-versions.txt` — diff it against
`backups/preflight-2026-08-04/pkgs-all-with-versions.txt` to see exactly what moved, and use the
preflight file plus `/var/cache/pacman/pkg` to downgrade any single package.

**The pins held, which was the whole point:**
| Package | Installed (kept) | Available (deliberately skipped) |
|---|---|---|
| `linux` / `linux-headers` | **7.0.5.arch1-1** | 7.1.5.arch1-2 |
| `nvidia-open-dkms` / `nvidia-utils` / `opencl-nvidia` | **595.71.05-2** | 610.43.03-5 |

Because *both* the kernel and the NVIDIA stack are pinned, they stay mutually consistent and
**no DKMS rebuild was required**. `mkinitcpio` still regenerated `/boot/initramfs-linux.img`
against 7.0.5 as part of the transaction, successfully.

`lib32-nvidia-utils` and `lib32-opencl-nvidia` are listed in `IgnorePkg` but **are not installed
at all** — harmless, don't be confused by them not appearing in the "ignored" output.

What did move: `glibc` 2.43→2.44, `systemd` 261.1→261.2, `mesa` 26.1.5→26.1.6, the vulkan/radeon
set (consistent, all 26.1.6), `dkms` 3.4.1→3.4.2, `wine` 11.14-2 (+ new dep `ntsync-autoload`).
**Plasma did not upgrade** — only a `qt6-tools` rebuild — so the desktop stack is nearly untouched
and the blast radius is much smaller than the package count suggests.

### ⚠️ Three `.pacnew` files exist and were deliberately NOT merged
`/etc/locale.gen.pacnew`, `/etc/pacman.d/mirrorlist.pacnew`, `/etc/mkinitcpio.conf.pacnew`.

**`mkinitcpio.conf.pacnew` must never be blindly applied.** It would:
- reset `MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)` → `MODULES=()`, dropping the
  NVIDIA early-load, and
- swap `HOOKS=(base udev autodetect …)` → `HOOKS=(base systemd … sd-vconsole …)`, changing the
  init system inside the initramfs.

The current file is deliberate Luminos configuration. Leave all three alone unless there is a
specific reason, and diff before ever merging one.

### Post-upgrade verification (all run, not assumed)
- `scripts/luminos-verify` → **PASS, 0 failures**, 2 warnings (one was the dGPU being awake at the
  moment of checking, which the script itself says to recheck at idle; the other is the known
  PostToolUse-hook-never-observed warning).
- All 5 Go daemons `active`.
- `/etc/environment` EGL forcing line **intact** (this is what holds the dGPU at 0 W — BUG-047/050).
- **dGPU: went `active` during the upgrade, then re-suspended on its own after ~175 s.** Nothing
  was holding `/dev/nvidia*` (`fuser -v` empty). The 0 W gating survived. Expect a transient
  `active` after any big package transaction — it is not a regression, just recheck at idle.
- `systemctl --failed` → only `forex-resume.service`, which is the **pre-existing** BUG-080
  Wine/MT5 breakage on a demo account. User has explicitly said not to care about it. Not caused
  by this upgrade, not a blocker.

### ⏸️ NOT YET REBOOTED
`glibc` and `systemd` both moved, so a reboot is genuinely needed before trusting the system.
This was left for the user to trigger because a reboot closes whatever they have open.

## Post-reboot verification (2026-08-04 15:00) — all clean
Rebooted at `2026-08-04 14:59:59`. `uname -r` = **7.0.5-arch1-1** (pin held). All 5 Go daemons
active. **0 failed units** — even `forex-resume` is fine, it only fails after a resume, not a boot.
dGPU `suspended` straight out of boot. `scripts/luminos-verify` → **PASS, 0 failures**, and the
only warning left is the known "PostToolUse hook never observed" one.

**The session recorder fired on its own at login** (`2026-08-04_15-00-24_KDE.txt`,
`Result=success`, `ExecMainStatus=0`). The black box works unattended — which is the thing Phase 3
depends on.

# Phase 3 — Hyprland INSTALLED + PROVEN NESTED 2026-08-04; real-session login still pending
#
# The 15:20 "black screen crash" was a FALSE ALARM — Hyprland was never launched. See the
# red section below before touching anything.

`hyprland 0.56.1-3` + `xdg-desktop-portal-hyprland 1.4.1-1` from **extra** (official repo, not AUR).
16 packages, 52 MB, 0 errors.

**It does not violate the GTK ban** — checked the dependency list before installing. Hyprland pulls
cairo/pango, which are GTK-adjacent but not GTK. Nothing GTK4 was added. `xorg-xwayland` is already
a hard dependency of Hyprland, which is convenient for Electron.

Almost everything else was already present: `uwsm` 0.26.6, `kitty`, `polkit-kde-agent`,
`qt6-wayland`, `xdg-desktop-portal` + `-kde` + `-gtk`.

## ⚠️⚠️ THE SINGLE MOST IMPORTANT FACT IN THIS PHASE — GPU SELECTION
**This laptop enumerates the NVIDIA dGPU FIRST:**

| node | vendor | device | PCI |
|---|---|---|---|
| `card1` / `renderD128` | `0x10de` | **NVIDIA RTX 4050** | `0000:01:00.0` |
| `card2` / `renderD129` | `0x1002` | **AMD iGPU** | `0000:65:00.0` |

If Hyprland is left to pick, it can land on the NVIDIA card, which would (a) hold the dGPU awake
forever and destroy the 0 W gating, and (b) probably fail to start at all, because
`/etc/environment` forces **Mesa-only EGL** so there is no NVIDIA EGL vendor to use.

So it is pinned to the iGPU **by PCI path, never by card number** (numbering is enumeration order
and is not stable across boots — and here a wrong guess picks NVIDIA):

    AQ_DRM_DEVICES=/dev/dri/by-path/pci-0000:65:00.0-card

Set in **two** places on purpose — `~/.config/hypr/hyprland.conf` (`env =`) and
`~/.config/uwsm/env-hyprland` (`export`) — because uwsm builds the environment before the
compositor is exec'd while Hyprland applies its own `env` during config parse. Verified the path
resolves to vendor `0x1002`. **No NVIDIA env vars anywhere.**

## Config
- `~/.config/hypr/hyprland.conf` — deliberately minimal, `hyprland --verify-config` → **`config ok`**.
  Animations off for the first run (fewer moving parts while diagnosing). Repo copy at
  `config/hypr/hyprland.conf`.
- **`SUPER+SPACE` is deliberately NOT bound** — it is the Luminos HIVE popup shortcut and gets
  wired up in Phase 5. Binding it now would create a conflict that is irritating to find later.
- `SUPER+SHIFT+M` exits via `uwsm stop`, not Hyprland's `exit` dispatcher, so the systemd user
  session tears down cleanly.

## 🔑 USE THE uwsm SESSION ENTRY, NOT THE PLAIN ONE
Hyprland ships **two** entries in `/usr/share/wayland-sessions/`:
- `hyprland.desktop` — plain. **Does not join `graphical-session.target`**, so the session
  recorder and the log rescue never fire.
- `hyprland-uwsm.desktop` → **"Hyprland (uwsm-managed)"** — this is the one to pick. It runs
  `uwsm start -e -D Hyprland hyprland.desktop`, which wires the session into systemd.

## Hyprland log rescue — built and PROVEN, because the log deletes itself
`scripts/luminos-hypr-log-save` + user unit `luminos-hypr-log-save.service` (enabled).

Hyprland logs to `$XDG_RUNTIME_DIR/hypr/<instance>/hyprland.log`, and logind **deletes
`$XDG_RUNTIME_DIR` when the last session ends** — so the evidence destroys itself in the act of
logging out to report the problem. The unit uses `RemainAfterExit=yes` with a no-op `ExecStart`,
so its **`ExecStop`** runs during `graphical-session.target` teardown, while the runtime dir still
exists. Logs land in `~/luminos-backups/hypr-session/` (last 20 kept).

Tested three ways, not assumed: clean no-op outside Hyprland; positive copy from a fake runtime
log; and the real systemd path by starting the unit and stopping it, which rescued the file.

## 🟥 FALSE ALARM 2026-08-04 15:20 — "Hyprland is crashing, black screen". It never ran.
The user logged out to try Hyprland, saw black, and rebooted. **Hyprland was never launched.**
Do not go looking for a Hyprland bug here; there wasn't one. What SDDM was actually told to start:

    15:19:59  Session ".../plasma.desktop" selected ... for VT 3
    15:21:50  Session ".../plasma.desktop" selected ... for VT 4

The greeter *listed* both Hyprland entries at 15:19:53 (`sddm-greeter-qt6: Reading from
".../hyprland-uwsm.desktop"`) — they are present and valid. The **session picker was simply never
changed off Plasma**. So it was a Plasma→Plasma logout/login.

Two things conspired to make that look like a crash. Both are now fixed:

1. **The login screen had no wallpaper, so it was black.**
   `/usr/share/sddm/themes/breeze/theme.conf.user` pointed at
   `/home/shawn/luminos-wallpaper-tests/sample.jpg`, which does not exist — the greeter logged
   `QML QQuickImage: Cannot open` and fell back to black. Worse, the greeter runs as user `sddm`,
   which cannot read `/home/shawn` **at all**, so a wallpaper under `$HOME` was never going to
   work there even if the file had existed. Now points at the package-owned
   `/usr/share/wallpapers/Next/contents/images/5120x2880.png`, verified readable *as user sddm*.
   Old file kept at `theme.conf.user.bak-2026-08-04`.
2. **Plasma took 30 s of black screen to come up** — greeter exited 15:20:01, `kwin_wayland`
   didn't start until 15:20:31. Not investigated further; not a Hyprland problem.

**Lesson, and it generalises:** on this machine a black screen is the default appearance of at
least three different healthy states. Never read black as "crashed" — read the logs. Ask "what
did SDDM say it started?" before anything else:

    journalctl -b -1 --no-pager | grep "selected, command:"

## ✅ Hyprland PROVEN WORKING 2026-08-04 15:35 — including Claude Desktop
Rather than send the user to log out again on a hope, Hyprland was smoke-tested **nested inside
the running Plasma session** — no logout, no risk, full log. Recipe, because it is reusable:

    WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 Hyprland

Aquamarine tries the DRM backend, fails (`libseat: ... Could not take control of session: Device
or resource busy` — Plasma holds the seat), and falls back to its **Wayland backend**. That is
expected and correct, not an error. Results:

- Hyprland 0.56.1 starts, parses `~/.config/hypr/hyprland.conf`, runs indefinitely.
- dmabuf formats negotiated are `GFX11,...` = **RDNA3 = the AMD iGPU**. Right card.
- **🎯 Claude Desktop runs.** Window mapped with `class: claude`, **`xwayland: 0`** — a *native*
  Wayland window, no XWayland fallback needed. Screenshotted via `grim`: renders fully.
  Its GPU process picked `--render-node-override=/dev/dri/renderD129`, the AMD iGPU. **None of
  the `CLAUDE_USE_XWAYLAND` / `CLAUDE_DISABLE_GPU` escape hatches were needed.**

### ⚠️ Gotcha that will bite you again: Electron single-instance
The first attempt to launch Claude Desktop inside the nested Hyprland appeared to do nothing.
It was not a Hyprland failure — Claude Desktop was **already running under Plasma**, and Electron's
single-instance lock just refocused that window. To get a genuinely separate instance you must
give it its own profile:

    /usr/lib/claude-desktop-bin/claude --no-sandbox --ozone-platform=wayland \
      --user-data-dir=/tmp/claude-hypr-test \
      /usr/lib/claude-desktop-bin/resources/app.asar

Second gotcha, same test: `hyprctl dispatch exec` gives the child **Hyprland's own environment**.
A nested Hyprland inherited `WAYLAND_DISPLAY=wayland-0`, so exec'd clients connected back to
*Plasma*, not to Hyprland. Set `WAYLAND_DISPLAY=wayland-1` explicitly when testing nested.
(Under a real session this is a non-issue — Hyprland sets it correctly for its children, proven
by `exec-once = kitty` mapping inside the nested instance.)

### What this test does NOT prove
It ran on the **Wayland backend**, not DRM. So it does not prove `AQ_DRM_DEVICES` GPU pinning,
real monitor/mode handling, or that the dGPU stays asleep. Those still need a real login.

## Status right now — 2026-08-04
**Plasma is untouched and still the default.** `/usr/share/wayland-sessions/` has `plasma.desktop`
plus the two Hyprland entries. 0 failed units, dGPU still `suspended`.

In place and verified:
- `.gitmodules` (8 submodules, all URLs + pinned commits proven fetchable)
- Timeshift snapshot `2026-08-04_14-35-50`, and a timeshift config that can actually complete
- `/etc` + `~/.config` + `~/.local/share` tarballs in `~/luminos-backups/preflight-2026-08-04/`
- package/unit inventory in `backups/preflight-2026-08-04/`
- `docs/ESCAPE-CARD.md`
- session black-box recorder, enabled as a systemd user unit
- SDDM greeter wallpaper fixed — the login screen is no longer black
- `exec-once = kitty` in `hyprland.conf`, so a live Hyprland is visually unmistakable

## ▶ IMMEDIATE NEXT STEP — the first Hyprland login (user action required)
Log out of Plasma. At SDDM the session picker is in the **bottom-left corner** of the Breeze
greeter — it says "Plasma (Wayland)". Click it and pick **"Hyprland (uwsm-managed)"** — not plain
"Hyprland". *Then* type the password. Selecting the session after typing does not help; SDDM sends
whatever is selected when Enter is pressed.

`/etc/sddm.conf.d/hidpi.conf` sets `DefaultSession=plasma.desktop` and `RememberLastSession=false`,
so **the picker resets to Plasma at every single login**. This is deliberate and is being kept:
it means a broken Hyprland can never trap the user in a login loop. The cost is that Hyprland must
be picked by hand every time.

**You will know it worked**: a kitty terminal appears on a mostly-empty screen. If you see the
Plasma panel, you're in Plasma and the picker didn't take.

**This session dies at logout.** Everything needed to resume is committed. On return, say
**"resume"** and read, in order:
1. `scripts/luminos-session-recorder --show`
2. `ls -lt ~/luminos-backups/hypr-session/` then read the newest — that is Hyprland's own log,
   rescued past the runtime-dir deletion.

### What to check while inside Hyprland
Only the things the nested test could **not** cover. Claude Desktop and basic compositor health
are already proven above — don't re-litigate them, check the DRM-backend-specific things.

1. **Did it start at all** — kitty should be on screen. A bounce back to SDDM means the GPU pin
   failed. `Ctrl+Alt+F3` → TTY → `cd ~/luminos-os && claude`; the CLI agent works with no desktop.
2. **🎯 GPU pinning — the real unknown.** This is what the nested test could not check:

       hyprctl systeminfo | grep -i -A3 'GPU information'

   Must be the **AMD** card. If it names NVIDIA, `AQ_DRM_DEVICES` did not take.
3. **dGPU must still sleep**: `cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status`
   → expect `suspended` at idle. **Never `nvidia-smi`** (BUG-078). If it says `active` and stays
   there for minutes, the compositor is on the wrong card.
4. **Scaling/mode** — `monitor = ,preferred,auto,auto` is a guess. Plasma presents this panel as
   1800x1125 logical, implying 2880x1800 at 1.6. If it looks wrong, set it explicitly.
5. **Claude Desktop** — just `claude-desktop`. Expected to work with no flags; it did nested,
   natively, on the iGPU. If it *doesn't*, that's DRM-backend-specific and worth logging properly.
6. **Exit with `SUPER+SHIFT+M`**, then log back into Plasma from SDDM.

### If it goes wrong
Plasma was never modified — just pick it at SDDM. To remove the Hyprland entries entirely:

    sudo rm -f /usr/share/wayland-sessions/hyprland.desktop \
               /usr/share/wayland-sessions/hyprland-uwsm.desktop
    sudo systemctl restart sddm

Full details in `docs/ESCAPE-CARD.md`.

**Phase 4 (Caelestia) must NOT start until Hyprland alone is known good**, including the Claude
Desktop test.

---

# Recently closed — sleep/suspend (2026-08-02/03) — DONE, do not redo
Lid close + idle suspend re-enabled and **proven in the wild** (40 h s2idle, `Aug 02 00:50` →
`Aug 03 16:56`). BUG-091 / DECISION 38 / AGENTS.md §9 all written.
Traps worth remembering:
- **PowerDevil 6.7 keys live in a *subgroup*: `[AC][SuspendAndShutdown] LidAction`.** A bare `[AC]`
  group parses fine and does nothing.
- **Never health-check with `triggersLidAction()`** — it returns `true` for every config including
  `LidAction=0`. Use `lidAction()` (int) via `qdbus6 … HandleButtonEvents lidAction`.
- **`systemctl show systemd-logind -p HandleLidSwitch` prints nothing** (Manager D-Bus property, not
  a unit property). Use `busctl`.
- Kernel log timestamps all flush at resume — ~41 `Timekeeping suspended` lines sharing one
  timestamp are **not** 41 suspends. Count `PM: suspend entry`/`exit`.
Residuals still open:
1. **`mmc0` (empty SD reader) eats roughly the first suspend attempt** — `PM: active wakeup source:
   mmc0`, PowerDevil retries ~11 s later and succeeds. Fix costs the SD reader entirely → user's
   call, untouched.
2. **BUG-082 (video wallpaper on resume) is HALF-verified.** plasmashell never restarted and there
   are no QML/gstreamer errors post-resume, but 0.0 % CPU looks identical for "correctly paused" and
   "frozen". **Needs a human to look at the desktop and say whether the video moves.**
3. The **idle** suspend path (900/600/300 s) is configured but has never been caught firing — the
   lid always beat it.

---

# Settled — do not re-litigate (condensed from earlier threads)

## MCP tooling (BUG-085 / BUG-087, DECISIONS 33 & 34) — DONE
- **Claude Code reads `~/.claude/settings.json` (USER scope), not the repo's `.mcp.json`.** Cowork /
  Claude Desktop launch it with `--setting-sources=user`, so repo-scoped config is never loaded
  there. `.mcp.json` is intentionally empty. Desktop and Antigravity have their own configs — that
  is correct, not duplication. The invariant is **one pinned binary**, not one file.
- **User-scope hooks do NOT fire in Cowork.** Proven 2026-07-26 with a cleared log: no `SessionStart`,
  no `PostToolUse` after ~15 tool calls. Hooks work in the CLI only. **Consequence: in Cowork the
  code graph never refreshes itself** — check `list_graph_stats_tool`'s `last_updated` before
  trusting "this function has no callers", or call `build_or_update_graph_tool` at session start.
  MemPalace is unaffected (queried on demand).
- One tool = one pyenv 3.12.13 venv, pinned, never editable. `luminos-verify --mcp` does a real MCP
  `initialize` handshake and hard-fails on duplicate registration / rolling-python interpreter /
  editable install / missing binary. Every check was negative-tested.
- **DECISION STILL OPEN:** install a `systemd --user` path unit watching **`~/luminos-os/.git/index`**
  (not the repo directory — path units are **not recursive**) to refresh the graph in Cowork? Or
  just refresh manually each session?

## Theme / Ubuntu (Yaru) look (BUG-088 / BUG-090, DECISION 30) — DONE
- `AutomaticLookAndFeelOnIdle` **defaults to `true`** with a **5 s** idle interval. Writing only
  `AutomaticLookAndFeel=false` leaves the idle path armed and looks like an intermittent bug. Both
  keys are now `false` in `~/.config/kdeglobals`.
- **Never verify a KDE colour scheme by its name.** `plasma-apply-colorscheme` no-ops with exit 0
  when the name already matches, without writing the `[Colors:*]` payload — so the name said Yaru
  while the payload stayed Breeze Dark for four days. Compare an actual colour value.
- GTK is the half that breaks: a Look-and-Feel apply rewrites `~/.config/gtk-{3,4}.0/settings.ini`
  via the `kde-gtk-config` kded module. **`plasma-changeicons Yaru` exits 0 and does NOT fix them.**
- **Never `kwriteconfig6` an `index.theme`** — it sorts groups and buries `[Icon Theme]`, which the
  freedesktop spec requires first. Use `scripts/luminos-icon-inherits.py`.
- **Settled:** dock/launcher icons come from **Papirus** and cannot come from Yaru (Yaru ships no
  `org.kde.dolphin`/`konsole`/`firefox`/`google-chrome` icon; breeze has none either). Changing them
  is a taste decision, not a bug.
- **TRADEOFF ACCEPTED:** KDE automatic light/dark switching is off and cannot coexist with the Yaru
  look. Re-enabling it in System Settings silently undoes DECISION 30.
- **NOT installed:** `systemd/luminos-theme-sync.{path,service}` exist in the repo but were never
  copied to `~/.config/systemd/user/`. Ask before installing.
- ⚠️ **All of this is Plasma-only and becomes irrelevant inside a Hyprland session.**

## Wallpaper (BUG-083 / BUG-082, DECISION 32) — DONE
- `ObscurePolicy` (int: 0 never / 1 fullscreen / 2 desktop-hidden, **default 2**) replaced the old
  `PauseWhenObscured` bool. plasmashell went 24% of a core → ~0 while hidden.
- **Never encode a wallpaper above panel resolution** — 2880×1800 panel was decoding a 4K source.
- **The running wallpaper loads from the INSTALLED copy**
  (`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/`), not the repo. Deploy recipe at the
  bottom of this file.
- **KWin's "Show Desktop" does NOT set `IsMinimized`** — useless for testing the occlusion guard.

## Memory / hardware ceiling — settled
- **15.6 GiB is the planning ceiling.** 4× soldered Micron LPDDR5, no SO-DIMM. But **"impossible to
  upgrade" is WRONG** — 32 GiB is reachable via 4 BGA reworks + a **three-byte** firmware patch.
  ASUS already ships three 32 GiB SPD profiles unedited; selection is by **BoardMask**, so the SPD
  contents never need editing. Exact offsets, checksum rule (all APCB bytes sum to `0x00`) and the
  PSB analysis (no OEM key, no RTM signature → not signed) are in git history for this file.
- **Bandwidth, not capacity, is the contended resource: 102.4 GB/s shared with the 780M iGPU**, which
  has no private VRAM. A RAM upgrade would not relieve it.
- **dGPU VRAM cannot become 24/7 system memory.** ReBAR is on (BAR1 = 8192 MB) so the CPU *can*
  address it, but: the GPU die is the memory controller; GDDR6 needs refresh; D3cold cuts the rails
  (measured **89% of uptime suspended** — the VRAM is free *because* the dGPU is asleep); MMIO reads
  are µs-scale vs ~80 ns DRAM and swap-in is a read; and there is no kernel NUMA path without a
  coherent interconnect. **The real unified-memory lead is the iGPU 512 MB carve-out (98% full) with
  7633 MB GTT behind it.** Next concrete move if resumed: measure the VRAM/GTT split under load.
- dGPU VRAM upgrade is hard-blocked: **AD107 never shipped above 8 GB anywhere**, so no signed VBIOS
  describing more exists. Unlike the RAM case, there is no vendor config to select.

## Other open items
- **BUG-084 — durable fix NOT applied.** DrKonqi's `gdb` + debuginfod ate 7.4 GB and filled zram;
  cleared by hand. **It will recur on the next app crash.** Needs user go-ahead for a `MemoryMax=`
  drop-in on `drkonqi-coredump-launcher@.service`. Fingerprint to check first next time:
  `/proc/pressure/memory` `full` high while `/proc/pressure/cpu` stays ~1% = memory stall.
  `ps --sort=-rss | head` found it in one command.
- **`kscreen-doctor` SIGABRTs reliably on this box** (3× in 24 h) and each crash arms another
  drkonqi launcher. `luminos-lid` called it on every lid event — **that path was removed 2026-08-02**
  with the udev rule, so this trigger is gone. Others may remain.
- **BUG-086 (OpenRouter key) is CLOSED/WONTFIX** — dead account, user dropped it 2026-07-25.
  **Do not re-raise rotation.** (`.claude/settings1.json` is still tracked in git; `.gitignore` has
  `.claude/` but gitignore does not untrack an already-tracked file.)
- **BUG-080 open** — Wine 11.8→11.13 broke the MT5/forex stack. Live-trading infra; needs a
  deliberate window. **Re-check `systemctl is-active forex-bot` before any reboot** — it is live
  trading, and Phase 2/3 above both involve reboots.

## Repo hygiene — READ BEFORE COMMITTING
- **The old "push is on hold / 11 commits unpushed" note is STALE and was removed 2026-08-04.**
  `main` == `origin/main`.
- **Never `git add -A`.** That is how the API key got published, and the tree still holds parked
  work that must not ride along: `share/`, `scripts/luminos-wine-*`, `scripts/luminos-ubuntu-look`,
  `systemd/luminos-theme-sync.*`, `systemd/luminos-ubuntu-look.service`, the `cmd/luminos-power`
  conductor edits, and three dirty `research/turboquant` submodules. **Stage by name.**
- **Luminos scripts have a recurring habit of printing success on a failed path** (BUG-088's
  `Ubuntu (Yaru) look re-affirmed.`, BUG-089's `Note added to $TAG.`). Both hid faults for days.
  **`luminos-brain log` still has it** — avoid apostrophes when calling it. When touching any
  `scripts/` helper, check its "done" message is *conditional*.
- **`luminos-brain safe` keyword-matches, it does not reason** — it has blocked correct plans with an
  unrelated canned reason. That is open task 0b.

### Wallpaper deploy / reload recipe
```
SRC=~/luminos-os/src/wallpapers/org.luminos.livewallpaper
DST=~/.local/share/plasma/wallpapers/org.luminos.livewallpaper
rm -rf "$DST"; mkdir -p "$DST"; cp -r "$SRC/." "$DST/"
mkdir -p "$DST/contents/samples"; cp ~/luminos-os/src/wallpapers/samples/*.html "$DST/contents/samples/"
systemctl --user restart plasma-plasmashell.service
```
