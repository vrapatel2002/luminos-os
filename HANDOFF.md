# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-07-24 — Response 2

## Goal (the durable end objective)
Three threads:
1. **Make the desktop feel fast again.** DONE for the wallpaper (BUG-083 / DECISION 32) — it must
   never spend CPU/iGPU on frames nobody can see, nor be encoded above the panel resolution.
2. **BUG-084 — stop the crash handler from taking the machine down.** This turned out to be the
   *actual* cause of the reported freeze. Cleared by hand; the durable cap is NOT applied yet.
3. **"Pseudo-unified memory architecture"** — the user's clarified ask: *"24/7 unified memory across
   the CPU and dGPU, as the dGPU will be mostly not used, so it's CPU/iGPU only regardless of what
   we are doing, HIVE or not."* i.e. always-on and general-purpose, NOT a HIVE-session-scoped thing.
   NOT STARTED — there is a hard hardware constraint to resolve with the user first (below).

## Aim right now
Thread 1 done. Thread 2 awaiting a yes/no on the `MemoryMax` drop-in. Thread 3 needs the user to
absorb one constraint before any code: **dGPU VRAM cannot be made into general 24/7 system memory on
this box**, and trying would destroy the true-0W idle work.

## Why / motivation (context a newcomer would be missing)
The user reported "Chrome and the OS are actually not responding" and suspected the live wallpaper.
The wallpaper *was* a genuine chronic cost — and for a non-obvious reason: it lands on the **iGPU
(renderD129)**, the *same* device KWin composites on and Chrome renders on. But it was **not** the
freeze. Mid-session the box went into a real **memory stall** (BUG-084) and that is what the user
was feeling. Both were worth fixing; do not conflate them.

## Process / approach being used
Measure first, then change, then re-measure the same counter. The counter used throughout is
`awk '{print $14+$15}' /proc/$(pgrep -x plasmashell)/stat` (utime+stime jiffies) sampled twice N
seconds apart, plus `/sys/class/drm/card2/device/gpu_busy_percent` and RSS.

## State — what is DONE (thread 1, BUG-083 / DECISION 32)
- **`PauseWhenObscured` (bool) → `ObscurePolicy` (int)** in `contents/config/main.xml`:
  `0` never freeze · `1` freeze only under a **fullscreen** window · `2` freeze whenever the desktop
  is hidden (fullscreen **or** maximized) — **default 2**.
- Per-window cover is now **graded** (`fullscreen=2`, `maximized=1`, `minimized/normal=0`) and the max
  across windows is **debounced 400 ms** (`coverDebounce`) so alt-tab does not stop-start the decoder.
  The old code OR-ed `IsMaximized || IsFullScreen` into one bool, so the two cases were indistinguishable.
- `config.qml`: the checkbox became a 3-option combo + an explanatory caption.
- **Video right-sized**: `3840×2160 → 2880×1620` H.264 CRF 20, `-an` (it is muted anyway). Panel is
  2880×1800, so the 4K source was decoding 8.3 MP per frame to fill 5.2 MP. **4K original kept.**
- Live config switched (desktop `ObscurePolicy=2`, lock screen deliberately `0`), plugin deployed,
  plasmashell restarted, loads with **zero QML errors**.
- **Measured** (plasmashell, one core):
  | State | CPU | RSS | iGPU |
  |---|---|---|---|
  | 4K, always render (before) | 240/10s (24%) | 810 MB | 16–18% |
  | 2880×1620, always render | 128/10s (12%) | 589 MB | 12% |
  | 2880×1620, hidden (now, default) | **1/10s (~0%)** | 617 MB | — |
  | 2880×1620, desktop visible | 61/6s (~10%) | — | — |
- **Resume verified**, not assumed: minimize Chrome via a KWin script → 61 jiffies/6s, restore → 0.
- Docs written: BUG-083, DECISION 32, LUMINOS_STATUS.md row, luminos-notes, luminos-brain.

## State — what is DONE (thread 2, BUG-084 — the actual freeze)
Diagnosed and cleared live, fully written up in `docs/BUGS.md` BUG-084. Summary:
- KDE **DrKonqi** launched `gdb ... --init-eval-command=set debuginfod enabled on` on a **364 MB
  Filelight core**. gdb reached **7.4 GB RSS / 16.3 GB VSZ at 70% CPU, still running after 12 min**,
  with **five** `drkonqi-coredump-launcher@*` units active at once.
- Peak: RAM **13 of 14 GiB used**, **zram swap 100% full (80 KiB free of 8 GiB)**, `pswpout` 2.47 M
  pages, **PSI memory `full` avg10 = 7.85%** while **CPU PSI stayed ~1%** — a *memory* stall, not a
  CPU shortage. That asymmetry is the fingerprint; check it first next time.
- Cleared with `systemctl --user stop 'drkonqi-coredump-launcher@*.service'` → RAM 13 → 5.6 GiB,
  swap 8 GiB full → 1.6 GiB, PSI memory full **7.85% → 0.08%**. Cores kept, nothing lost.
- **Durable cap NOT applied** — it will recur on the next app crash.

## State — what is IN PROGRESS
Nothing half-built. Thread 3 has **no code written** — deliberately.

## Thread 3 — the constraint that has to be settled before any code
The user asked for "24/7 unified memory across the CPU and dGPU". The honest hardware position,
which must be put to them before building anything:
- **dGPU VRAM cannot become general system memory on this box.** A consumer RTX 4050 over PCIe has no
  mechanism to expose VRAM as a NUMA node or a block device to the kernel (that exists on
  Grace-Hopper / CXL, not here). The only routes are userspace hacks (FUSE `vramfs`, NBD) that cannot
  safely host swap.
- **It would also destroy the true-0W work.** Holding VRAM 24/7 means the dGPU can never RTD3-suspend
  → ~8 W constant idle draw on a laptop, undoing BUG-047, DECISION 25 and the `DPM=0x02` tuning. The
  user's own reason for wanting it ("the dGPU will be mostly not used") is exactly why it is
  currently free — it is *asleep*. This is a Rule 11 conflict and must be documented as one.
- **The genuinely unified half already exists and is measurable.** Live readings this session:
  `mem_info_vram_total = 512 MB` with **501 MB used (98% full)**, `mem_info_gtt_total = 7633 MB` with
  1218 MB used. The 512 MB is the BIOS UMA carve-out for the 780M; everything beyond it spills to
  GTT. That carve-out being pinned at 98% on a 2880×1800 HiDPI desktop is the most concrete
  unified-memory lead we have, and it is on the CPU/iGPU side the user says they actually live on.
- Suggested first move, pending user agreement: **characterise the iGPU VRAM/GTT split under real
  load** (idle vs Chrome vs wallpaper vs HIVE) before proposing any allocator. Measure, then design.

## Next steps (ordered)
1. **BUG-084 durable fix** — user go-ahead for a systemd drop-in on
   `drkonqi-coredump-launcher@.service` with `MemoryMax=`/`MemoryHigh=`, so a runaway backtrace is
   OOM-killed in its own cgroup. Optionally also blank `DEBUGINFOD_URLS` for drkonqi and serialise
   the launchers. Until this lands, every app crash can repeat the stall.
2. Separately: **`kscreen-doctor` SIGABRTs reliably on this box** (three times in 24 h) and each crash
   arms another launcher. Fix or avoid it.
3. **Thread 3** — put the dGPU-VRAM constraint above to the user, get a direction, then measure the
   iGPU VRAM/GTT split under load before writing any allocator code.
   Cache-theory mapping to reuse when it does get built: L1 dGPU VRAM 4.6 GB / L2 system RAM 16 GB
   (already genuinely unified with the iGPU — zero-copy there, only the dGPU needs a PCIe transfer) /
   L3 zram / L4 NVMe. Weights are **read-only → clean lines → eviction is free, no write-back**; KV
   cache is read-write → pin or write back. The replacement policy already exists in-tree:
   **luminos-ram's LIRS/IRR + HotSet**. Prefetch = the layer N+1 double-buffer (DECISION 23).
   "Way-locking" = resident weights/KV/embeddings/output head that must never be evicted.
4. Optional wallpaper follow-up: detect **session locked / DPMS-off** and freeze then too. Today the
   lock greeter is not a window in `TasksModel`, so `coverLevel` stays 0 and the desktop copy keeps
   decoding behind the lock screen if no maximized window is up.
5. `git push` is **on hold by explicit user decision** — commit locally, do not push yet.

## Key decisions & constraints so far
- **DECISION 32 amends DECISION 31.** The session-wide `QTWEBENGINE_CHROMIUM_FLAGS` anti-throttle is
  **kept** — it removes the *involuntary* Chromium/KWin throttle, which is what makes `ObscurePolicy=0`
  work at all. The plugin's policy is now the **authority**; the flags are the enabler.
- Default `2` is a deliberate trade: a *maximized* window stops the wallpaper. Anyone wanting motion
  behind a maximized window sets `1` or `0` and pays ~12% of a core.
- Rule recorded in DECISION 32: **never encode a wallpaper above the panel resolution** — the extra
  pixels are decoded and then thrown away by the scaler.

## Gotchas / dead-ends / things NOT to redo
- **The running wallpaper loads from the INSTALLED copy**
  (`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/`). Editing the repo source alone does
  nothing — run the deploy recipe below + restart plasmashell. (This already cost a wasted test during
  BUG-082.)
- **KWin's "Show Desktop" does NOT set `IsMinimized`**, so it does not change `coverLevel`. It is
  useless as a test of the occlusion guard — use a real minimize or unmaximize.
- The jank was **not** a fault. Do not go looking for amdgpu hangs/OOM again: journal is clean, PSI is
  0, 8.5 GB available. It is contention.
- iGPU busy stays at ~12–21% even with the wallpaper fully frozen — that residue is Chrome / Claude /
  KWin, **not** the wallpaper. Do not attribute it to the wallpaper.
- **The wallpaper was not the freeze.** It was a real chronic cost (24% of a core, forever) and worth
  fixing, but the unresponsiveness was BUG-084. Do not let the wallpaper fix "explain" a future stall
  — check `/proc/pressure/memory` `full` vs `/proc/pressure/cpu` first. Memory-full high + CPU-some
  low = a memory stall, and something is eating RAM.
- **`ps --sort=-rss | head` found it in one command.** Reach for that before any deep GPU forensics.
- **NOT pushed to origin** (user's explicit decision this session). Committed locally only.
  `git add -A` would sweep in files the previous
  session explicitly parked as "awaiting user OK" (`scripts/luminos-ubuntu-persist`,
  `systemd/luminos-ubuntu-look.service`, `share/`, the wine scripts) — stage by name, never `-A`.
- Still unverified from the previous session: BUG-082's real suspend/resume cycle (close lid, wait
  ~10 s, reopen). A plasmashell restart does not test that path.

## Files touched / relevant files
- `src/wallpapers/org.luminos.livewallpaper/contents/config/main.xml` — `ObscurePolicy` replaces `PauseWhenObscured`
- `src/wallpapers/org.luminos.livewallpaper/contents/ui/main.qml` — graded `cover`, `coverDebounce`, `notVisible`, `shouldPlay`
- `src/wallpapers/org.luminos.livewallpaper/contents/ui/config.qml` — 3-option combo + caption
- `docs/BUGS.md` (BUG-083), `LUMINOS_DECISIONS.md` (DECISION 32), `LUMINOS_STATUS.md`
- Live config (not in repo): `~/.config/plasma-org.kde.plasma.desktop-appletsrc`,
  `~/.config/kscreenlockerrc` — backups `*.bak-wallpaper-20260724`
- Video: `~/Videos/4K Video Downloader+/Sabrina Carpenter Kissing Screen Wallpaper (2880x1620 h264).mp4`
  (4K original kept next to it)
- Relevant for thread 2: `LUMINOS_DECISIONS.md` DECISION 23, `cmd/luminos-ram/main.go`,
  `docs/LUMINOS_RAM_ARCHITECTURE.md`, `scripts/hive-daemon.py`

### Deploy / reload recipe
```
SRC=~/luminos-os/src/wallpapers/org.luminos.livewallpaper
DST=~/.local/share/plasma/wallpapers/org.luminos.livewallpaper
rm -rf "$DST"; mkdir -p "$DST"; cp -r "$SRC/." "$DST/"
mkdir -p "$DST/contents/samples"; cp ~/luminos-os/src/wallpapers/samples/*.html "$DST/contents/samples/"
systemctl --user restart plasma-plasmashell.service
```
