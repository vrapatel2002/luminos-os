# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-07-24 — Response 1

## Goal (the durable end objective)
Two threads, in this order:
1. **Make the desktop feel fast again.** The live wallpaper must never spend CPU/iGPU on frames
   nobody can see, and must not be encoded above the panel's resolution. DONE + measured this
   session (BUG-083 / DECISION 32).
2. **Design and build the "pseudo-unified memory architecture"** — treat VRAM / system RAM / zram /
   NVMe as a CPU-style cache hierarchy with one allocator, one replacement policy and one budget,
   instead of four disconnected pools. NOT STARTED — scope question is out with the user.

## Aim right now
Thread 1 is finished and verified. Thread 2 is blocked on **one scope decision from the user**
(see "Next steps"): which workload the tier manager serves first — HIVE model swapping, HOPE
weight-streaming inference (DECISION 23), or a general OS-wide allocator.

## Why / motivation (context a newcomer would be missing)
The user reported "Chrome and the OS are actually not responding" and suspected the live wallpaper.
They were right, and for a non-obvious reason: the wallpaper's cost lands on the **iGPU
(renderD129)**, the *same* device KWin composites on and Chrome renders on. It never showed up as a
crash — no amdgpu ring resets, no OOM, PSI cpu/memory/io all 0 — it was pure steady-state
contention. The user's own framing was the fix: "when the app is fullscreen there is no point using
iGPU/CPU to render frames we are not seeing."

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

## State — what is IN PROGRESS
Nothing half-built. Thread 2 has **no code written** — deliberately, pending the scope answer.

## Next steps (ordered)
1. **User answers the scope question** for the pseudo-unified memory architecture. The three framings
   put to them:
   - (a) **HIVE model cache** — only one GPU model fits 4.6 GB VRAM, so swapping Nexus↔Bolt today
     kills llama-server and re-reads a ~4.5 GB GGUF from NVMe. Keep the cold model's weights hot in
     system RAM/zram so a swap is a RAM→VRAM PCIe copy, not a disk reload. Smallest, most obviously
     useful, directly exercises the tier machinery.
   - (b) **HOPE weight-streaming** — build DECISION 23 for real (PCIe P0/Gen4 session pin in
     luminos-power + pinned-region exemption in luminos-ram + a shared start/stop signal).
   - (c) **General OS-wide tier manager** — a `luminos-uma` broker owning one budget across
     VRAM/RAM/zram/NVMe for all clients.
2. Whichever is chosen, the cache-theory mapping to reuse (already sketched, not yet written down in
   the repo): tiers = L1 VRAM 4.6 GB / L2 system RAM 16 GB (already genuinely unified with the iGPU —
   zero-copy there, only the dGPU needs a PCIe transfer) / L3 zram / L4 NVMe. Weights are **read-only
   → clean lines → eviction is free, no write-back**; KV cache is read-write → must be pinned or
   written back. Replacement policy already exists in-tree: **luminos-ram's LIRS/IRR + HotSet**.
   Prefetch = the layer N+1 double-buffer. "Way-locking" = the resident weights/KV/embeddings/output
   head that must never be evicted.
3. Optional wallpaper follow-up: detect **session locked / DPMS-off** and freeze then too. Today the
   lock greeter is not a window in `TasksModel`, so `coverLevel` stays 0 and the desktop copy keeps
   decoding behind the lock screen if no maximized window is up.
4. Decide whether to `git push` — the wallpaper work is committed locally but NOT pushed (see Gotchas).

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
- **NOT pushed to origin.** Committed locally only. `git add -A` would sweep in files the previous
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
