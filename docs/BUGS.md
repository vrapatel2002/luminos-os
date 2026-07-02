# Luminos OS — Bug Tracker
Last Updated: 2026-07-01 (BUG-078 FIXED — monitoring itself kept the dGPU awake: nvidia-smi polls from powerwidget + luminos-monitor took runtime-PM refs; runtime_status reads are wake-free)

## Open Bugs

### BUG-074 — `model.to(bfloat16)` corrupts the complex `freqs_cis` RoPE buffer (discards the imaginary part)
<!-- [CHANGE: claude-code | 2026-06-28] -->
- Status: OPEN (found during offload Phase 5 validation; the offload engine works around it, generate.py may not)
- Severity: MEDIUM (silently degrades RoPE → wrong positional encoding → worse generations; no crash)
- Component: hope-llm `scripts/generate.py` (`model = model.bfloat16().to(device)`), any code that dtype-casts a HOPELLM after construction
- Description: HOPELLM registers `freqs_cis` as a non-persistent **complex64** buffer (`torch.polar(...)`). A blanket `model.to(torch.bfloat16)` / `model.bfloat16()` casts **all** buffers, including `freqs_cis`, to bf16 — which is REAL, so the imaginary part is silently discarded (PyTorch warns "Casting complex values to real discards the imaginary part"). `apply_rotary_emb` then multiplies the complex query/key by a now-real "freqs", giving incorrect rotation → broken/weakened RoPE. Found because the offload validator's reference models (built with `.to(bf16)`) diverged from the engine by rel≈0.21 until `freqs_cis` was recomputed as complex.
- Root Cause: complex buffers don't survive a real-dtype `.to()`. The cast is applied module-wide rather than param-only.
- Workaround in the offload engine: `build_offload_hope` recomputes `freqs_cis` (complex) on-device AFTER materialising weights, so streamed inference is unaffected.
- Candidate fix (NOT applied — hope-llm owns generate.py): cast only floating params to bf16 and leave complex buffers alone, or recompute `freqs_cis` after the cast (as the engine does). Verify with a shuffle/position test before/after.
- Date Found: 2026-06-28

### BUG-077 — HOPE single-token "memory-carries-context" decode degenerates; full re-feed is coherent
<!-- [CHANGE: claude-code | 2026-06-28] -->
- Status: OPEN (characterised during offload Phase 5 first real generation; not a defect in the offload engine)
- Severity: MEDIUM (model is unusable for generation in its "intended" decode mode; works fine with standard re-feed)
- Component: hope-llm decode contract — `scripts/generate.py` (line ~103 `ids = next_id`, "memory carries context") and the offload runner `scripts/offload_run.py`
- Description: After the first token, the reference decode feeds ONLY the new token and relies on the DGD self-modifying memory state to carry prior context (no KV cache, no re-feed). On the 10.4B qwen3_transplant (step 3500, val_loss 1.57) this degenerates immediately: `The capital of France is` → `Paris,d,d,d,d,…` (token 0 "Paris" is correct; everything after collapses to a repeated token). Switching the offload runner to **re-feed the full growing sequence each step** (`--refeed`, memory reset per step) yields coherent text: `Paris, which is located in the Seine River.` then fluent multilingual continuation. So the forward, weights, nf4 quant and resident DGD path are all correct — only the single-token memory recurrence fails to preserve context.
- Root Cause (suspected): the checkpoint was trained teacher-forced (val_loss is a full-sequence metric) and the DGD memory recurrence with `memory_chunk_size=8` does not propagate context across length-1 decode steps — the memory update likely fires per-chunk, so single-token steps never commit usable state. Undertrained recurrence is plausible at only 3500 steps.
- Workaround: use `--refeed` in `offload_run.py` for coherent generation (cost: O(seq) streaming per step → ~0.88 tok/s vs ~2.0 tok/s single-token).
- Candidate fix (NOT applied — hope-llm owns the architecture): implement a real KV cache for the attention layers + verify the DGD memory commits state on single-token steps; or continue training the memory recurrence. Verify by comparing single-token vs re-feed logits per step.
- Date Found: 2026-06-28

### BUG-076 — Offload runner used the GPT-2 tokenizer (vocab 50257) for a Qwen3 transplant (vocab 151936)
<!-- [CHANGE: claude-code | 2026-06-28] -->
- Status: FIXED (2026-06-28)
- Severity: HIGH (pure-garbage output from a correct model — `athen,d,d,d,…`)
- Component: hope-llm `scripts/offload_run.py` (was importing `src.tokenizer.Tokenizer`, a tiktoken GPT-2 wrapper)
- Description: The transplant grafts DeepSeek-R1-0528-Qwen3-8B weights (vocab 151936) but `src.tokenizer.Tokenizer` is a GPT-2 BPE wrapper (vocab 50257). The runner encoded the prompt with GPT-2 ids (model receives the wrong embeddings) and decoded Qwen3 output ids with the GPT-2 vocab (correct " Paris" id renders as garbage). The model was perfect; the tokenizer was mismatched.
- Fix: `offload_run.py` now loads `AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")` and stops on `tok.eos_token_id` (151645). NB: `scripts/generate.py` still uses the GPT-2 tokenizer and has the same latent bug for Qwen3 checkpoints (hope-llm owns it).
- Date Found / Fixed: 2026-06-28

### BUG-075 — Offload head OOM: untied lm_head dequantises to a single ~2.3 GB temp during multi-token prefill
<!-- [CHANGE: claude-code | 2026-06-28] -->
- Status: FIXED (2026-06-28)
- Severity: HIGH (CUDA OOM at generation time on the 6 GB GPU; build-only path was unaffected)
- Component: hope-llm `src/offload_engine.py` (`StreamedLinear` / lm_head streaming)
- Description: `bnb.matmul_4bit` only takes its fused gemv path for single-token inputs; for any multi-token input (prompt prefill) it falls back to `linear(A, dequantize_4bit(B))`, materialising the full weight. For the untied head (151936×4096) that transient is ~2.3 GB, which OOMs with only ~1.2 GB free. Other streamed weights are ≤0.4 GB dequantised, so the head was the sole offender.
- Fix: added `ChunkedStreamedLinear` (and `HEAD_CHUNKS=8`) — the head is quantised in 8 vocab-row chunks, each streamed + matmul'd separately and concatenated, capping the dequant transient at ~0.3 GB. Bonus: smaller head chunks shrank the shared StagingPool slot from the head (311 MB) to the FFN size (~50 MB), dropping post-build VRAM from 3.53 → 2.18 GB.
- Date Found / Fixed: 2026-06-28

### BUG-073 — App-launcher (Kickoff) stutter on open — swap page-faults, NOT the iGPU
<!-- [CHANGE: claude-code | 2026-06-24] -->
- Status: OPEN (diagnosed, not yet fixed)
- Severity: LOW-MEDIUM (cosmetic latency hitch; no crash)
- Component: plasmashell (Kickoff launcher) + system memory policy (zram/swap) + luminos-ram interaction
- Description: Clicking the application launcher produces a visible stutter on first open. User reasonably suspected the iGPU — but the Radeon 780M runs AAA titles at 1080p, so raw GPU throughput is not the bottleneck. Measured: `plasmashell` had `VmSwap: 50020 kB` (~50MB swapped out) under normal desktop load. The launcher hitch is plasmashell page-faulting its Kickoff QML scene + icon-cache pages back in **from swap** on open — a latency-bound paging stall, not a GPU fill-rate problem.
- Root Cause: 16GB LPDDR5x is shared across CPU + iGPU + OS, and under pressure (Chrome, HIVE models, zram) the kernel pushes plasmashell's cold pages to swap. KWin blur on the translucent Kickoff panel (`BlurStrength=4`, `backgroundcontrastEnabled=true`) adds GPU fill on a 2880×1800 HiDPI surface but the iGPU absorbs that; the perceptible jank is the swap-in fault when those pages were evicted. luminos-ram's OnScreen guard is **window-keyed (KWin focus)**, so the plasmashell shell process's own launcher pages are not its protection target — they remain swap-eligible.
- Candidate Fixes (NOT applied — need a memory-policy decision, see future DECISION): (a) keep plasmashell resident — `vm.swappiness` lower for interactive desktop, or a per-process `memory.low`/`oom_score_adj` cgroup for plasmashell; (b) teach luminos-ram to pin/protect the plasmashell PID, not just focused windows; (c) warm the icon cache at session start. Verify with `grep VmSwap /proc/$(pgrep -x plasmashell)/status` before/after.
- Date Found: 2026-06-24

### BUG-069 — luminos-power v4.2 GPU TGP switching is a silent no-op: `nvidia-smi -pl` unsupported on mobile but exits 0
<!-- [CHANGE: claude-code | 2026-06-11] -->
- Status: OPEN (code fix pending; workaround reverted 2026-06-12 — nvidia-powerd re-masked. Reusable interim: `scripts/luminos-train-mode` on/off wraps nvidia-powerd + 100% fan pin for training runs)
- Severity: HIGH
- Component: cmd/luminos-power/main.go (setGPUTGP, line ~1304)
- Description: The v4.2 "GPU TGP dynamic switching" feature (55W↔90W, shipped 2026-06-03) never changed the GPU power limit once. `nvidia-smi -pl 90` on the mobile RTX 4050 prints "Changing power management limit is not supported … Treating as warning and moving on" and **exits 0**, so `runCmd` sees success and the daemon logs "GPU TGP → 90W" while hardware stays at 55W. All TGP log lines since 2026-06-03 are fiction; the daemon's internal state (`currentGPUTGPW=90`) diverges from reality, which also suppresses retry attempts. Discovered during HOPE training: GPU pegged at 55.0W/55W limit, P0, 92% util, clocks 2385/3105 MHz.
- Root Cause: nvidia-smi treats the unsupported -pl operation as a warning, not an error (exit 0). On Ada laptops TGP above base is controlled by Dynamic Boost (`nvidia-powerd`) or ASUS `nv_dynamic_boost` firmware attribute — `asus-armoury` reports nv_dynamic_boost/nv_temp_target "unavailable" on GA403UU, so nvidia-powerd is the only working mechanism. It was masked (BUG-047 idle-drain era, unmask undocumented).
- Workaround Applied (2026-06-11, temporary): unmasked + started `nvidia-powerd` → limit rose 55→88W dynamically, clocks 2385→2655 MHz (+11%) at 71°C with flat-100% fan curves. Revert steps in PENDING_RESTART.md.
- Proper Fix (after training): in setGPUTGP, parse nvidia-smi output for "not supported" OR read back `power.limit` after write and compare; manage Dynamic Boost via nvidia-powerd lifecycle instead of -pl; decide nvidia-powerd policy (idle drain vs boost) in LUMINOS_DECISIONS.md.
- Date Found: 2026-06-11

## Fixed Bugs (new)

### BUG-078 — Monitoring kept the dGPU awake: `nvidia-smi` polling (powerwidget every 5s, luminos-monitor every 2s) takes a runtime-PM ref per call
<!-- [CHANGE: claude-code | 2026-07-01] -->
- Status: FIXED (2026-07-01)
- Severity: MEDIUM (idle power: dGPU held at P8 ~1.8–8W instead of D3cold ~0W whenever polling ran)
- Component: src/widgets/org.luminos.powerwidget (main.qml updateAll), /usr/local/bin/luminos-monitor (_snapshot/watch)
- Description: Every `nvidia-smi` invocation opens /dev/nvidia0 and takes a runtime-PM reference, waking a suspended GPU and resetting its autosuspend window. powerwidget polled `nvidia-smi --query-gpu=power.draw` every 5s from plasmashell; `luminos-monitor watch` polled the full query every 2s. Result observed 2026-07-01: `runtime_suspended_time = 0 ms` over a 55.7h uptime despite `d3cold_allowed=1` and the BUG-047 udev gating being correct. (Separate, legitimate wake-holders also present: forex bot with a live CUDA mmap on /dev/nvidia0+uvm, and nvidia-powerd left running — those hold the GPU awake by design; the monitoring wakes were pure waste.)
- Root Cause: monitoring used a side-effectful query tool to ask "are you asleep?". `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status` answers the same question with zero side effects.
- Fix Applied: (1) luminos-monitor v1.2 sleep-guard — read runtime_status first; if `suspended`, report SLEEP/0W and skip nvidia-smi entirely. (2) powerwidget now reads runtime_status instead of nvidia-smi for its awake-dot. (3) new org.luminos.monitorwidget consumes `luminos-monitor stats` (v1.3) and inherits the guard.
- Verify: with no CUDA holders running, `cat .../power/runtime_suspended_time` should start climbing; monitor shows `SLEEP/0W` without flipping runtime_status to active.
- Date Found / Fixed: 2026-07-01

### BUG-072 — Light/dark fragmentation: `gtk-theme-name=Breeze-Dark` is a fixed-dark theme that ignores the prefer-dark flag (regression introduced by BUG-068/BUG-071)
<!-- [CHANGE: claude-code | 2026-06-24] -->
- Status: FIXED (live `~/.config` + repo mirror). Cross-ref: introduced by **BUG-068** and **BUG-071** (both set GTK to `Breeze-Dark` believing it was the correct Breeze value).
- Severity: MEDIUM (whole-desktop visual incoherence; the "stitched-together" feel persisted after the macOS revert)
- Component: `~/.config/gtk-{3,4}.0/settings.ini`, repo `config/gtk-{3,4}.0/settings.ini`, gsettings `org.gnome.desktop.interface gtk-theme`
- Description: Foreign-toolkit apps (Electron/Chromium/Flatpak) and GTK apps disagreed with Qt/Plasma about light vs dark — at the same time, on the same desktop. Traced to a 3-way contradiction: GTK theme name said `Breeze-Dark`, the GTK `gtk-application-prefer-dark-theme` flag said light, and the xdg portal `org.freedesktop.appearance color-scheme` said light. The single bad value was the **theme name**: `Breeze-Dark` is a *permanently dark* theme (`/usr/share/themes/Breeze-Dark/` ships only `gtk.css`), so it ignores the prefer-dark flag entirely. The adaptive theme is plain **`Breeze`** (`/usr/share/themes/Breeze/` ships both `gtk.css` (light) and `gtk-dark.css` (dark), selected by the flag).
- Root Cause: KDE already owns light/dark as a single source of truth — kded's `gtkconfig` module auto-syncs the GTK prefer-dark flag AND the xdg portal (which Electron/Chromium/Flatpak read) to the active Plasma color scheme on every change. But it only ever sets the **flag**, never the theme **name**. BUG-068/BUG-071 hand-set the name to the fixed-dark `Breeze-Dark`, which overrode the flag → the flag and the theme permanently contradicted each other, and nothing self-corrected because no KDE mechanism rewrites the name. Verified: applying a light Plasma scheme flipped the flag to `false` but `Breeze-Dark` stayed dark.
- Fix Applied: `gtk-theme-name=Breeze` (adaptive) in live `~/.config/gtk-{3,4}.0/settings.ini` and repo `config/gtk-{3,4}.0/settings.ini`; `gsettings set org.gnome.desktop.interface gtk-theme Breeze`. Verified round-trip: switching **only** the KDE color scheme (System Settings → Colors, or `plasma-apply-colorscheme`) now flips the GTK flag + xdg portal + GTK rendering together — Qt, GTK, Electron, Chromium, Flatpak all follow. **No daemon, no timer, no extra process** — KDE's built-in kded gtkconfig does it.
- Why this fix (not a daemon): an earlier attempt (`scripts/luminos-theme-switch` Go daemon, committed 15ff0ba4 then removed in f50cb496) re-implemented what KDE already does and fought kded's gtkconfig. Removed. The correct, durable fix is one config value + letting KDE be the authority.
- Remaining risk (tracked): `scripts/smart_build.sh` bakes `gtk-theme-name=Adwaita-dark` (also fixed-dark) into `/etc/skel` for the ISO, so a freshly built/installed Luminos would reship this contradiction. Not changed here (installer theme identity is a product decision) — flagged for a follow-up.
- Date Found: 2026-06-24
- Date Fixed: 2026-06-24

### BUG-071 — Repo config mirror still shipped WhiteSur-Dark after BUG-068's live fix (latent re-fragmentation)
<!-- [CHANGE: claude-code | 2026-06-14] -->
- Status: FIXED (repo-only; live `~/.config` was already correct from BUG-068)
- Severity: MEDIUM
- Component: config/gtk-3.0/settings.ini, config/gtk-4.0/settings.ini, config/kde/kwinrc
- Description: BUG-068 (2026-06-11) fixed the LIVE GTK theme to Breeze-Dark, but the repo mirrors under `config/gtk-{3,4}.0/settings.ini` still declared `gtk-theme-name=WhiteSur-Dark` + `gtk-cursor-theme-name=WhiteSur-cursors`. Any redeploy of repo configs would have resurrected the three-way Breeze/WhiteSur hybrid "stitched-together" look. The deprecated `AnimationSpeed=3` (Plasma-6-obsolete, conflicts with `AnimationDurationFactor=1.0`) also lingered in repo `config/kde/kwinrc` `[Compositing]`.
- Root Cause: BUG-068's fix used `kwriteconfig6`/filesystem ops on live `~/.config` and `~/.local/share` but never updated the repo's `config/` mirror — the repo is the deploy source, so the divergence was a loaded gun.
- Fix Applied: repo `settings.ini` ×2 → `Breeze-Dark` + `breeze-dark` icons + `breeze_cursors`; removed `AnimationSpeed=3` from repo `kwinrc`. Added generated `config/gtk-{3,4}.0/gtk.css` (token `@define-color` accent overrides, reaches libadwaita). NOT applied live (training run in progress, no checkpoint) — repo edits are inert until deploy. See DECISION 21.
- Date Found: 2026-06-14
- Date Fixed: 2026-06-14

### BUG-070 — Training OOM-killed with no traceback: zram-only swap is not a real spill valve
<!-- [CHANGE: claude-code | 2026-06-13] -->
- Status: FIXED (luminos-os side mitigated by reversible toggle; app-side data-path fix owned by the hope-llm repo)
- Severity: HIGH
- Component: system memory policy (swap) + ML training interaction (`~/hope-llm/scripts/train.py`, `~/hope-llm/src/dataset.py`)
- Description: HOPE training was SIGKILLed mid-run with no Python traceback ("just gone"). Blamed on VRAM, but the GPU was idle (1880MB / 6GB — see `~/hope-llm/cosmo_train.log`). Real exhaustion is CPU/RAM-side: dataset is a 7.6GB uint16 memmap (`data_cosmo/train.npy`, 3.795B tokens) and the DataLoader ran `--workers 2 pin_memory=True shuffle=True`. For a pre-tokenized memmap, `__getitem__` is a slice+cast — workers add fork + IPC + per-worker page-locked pin buffers (×prefetch_factor) + a ~237MB RandomSampler permutation, for ~zero throughput gain. On 14GB RAM with **only zram swap (prio 100, compressed RAM, no disk spill)**, anon/pinned pressure has nowhere to go → instant global OOM-kill.
- Root Cause: (1) No real disk swap — zram compresses cold pages back into the same RAM, so it can't relieve true RAM exhaustion. (2) App data-path over-allocates (workers/pin) for a workload that doesn't benefit. `luminos-ram` was investigated and RULED OUT: its evict/freeze/kill sets are window-keyed (KWin focus) and `isSafeToFreeze` bails at CPU>5%, so a headless busy trainer isn't its target.
- Fix Applied (luminos-os side, reversible): `scripts/luminos-train-ram` toggle. ON = low-priority on-disk swapfile (`/swapfile.train`, default 16G, **not** in fstab) + `vm.swappiness` 60→10 (reclaim the reclaimable memmap page cache before the trainer's anon set) + optional memory-cgroup `run` (clean cgroup-OOM instead of nuking Plasma). OFF = removes swapfile, restores swappiness exactly. Verified add/revert leaves the zram-only / swappiness-60 baseline with no leftover. NOTHING permanent (no /etc, fstab, or sysctl.d) — normal desktop policy unchanged.
- App-side fix (OWNED BY hope-llm repo, NOT this repo — DONE + benchmarked 2026-06-13): replaced DataLoader/workers/pin/RandomSampler with a vectorized `get_batch` (torch.randint offsets into the uint16 memmap, int32 on CPU → int64 on GPU). Result: 4,383 tok/s (was ~3,700), peak anon RAM 1.29GB / 14GB, swap flat → swapfile confirmed a safety net, not load-bearing. CORRECTION to earlier advice: on this 6GB GPU, raising seq_len does NOT help throughput (DGD memory-kernel activations scale with batch×seq and aren't cut by attention-only grad-ckpt) — seq_len is a quality lever; batch size (ceiling 8 at seq 128) is the throughput lever.
- Date Found: 2026-06-13
- Date Fixed: 2026-06-13

### BUG-068 — Incomplete Tahoe revert: GTK ran WhiteSur-Dark + Kvantum pinned to MacTahoe for a month
<!-- [CHANGE: claude-code | 2026-06-11] -->
- Status: FIXED
- Severity: MEDIUM
- Component: GTK settings.ini, ~/.config/Kvantum, kwinrc, AUR whitesur-* packages
- Description: The 2026-05-11 Tahoe revert ("restored clean KDE Plasma Breeze Dark state") only reverted Plasma-side settings. Left behind: GTK3/4 `gtk-theme-name=WhiteSur-Dark` (GTK apps rendered macOS-style while Qt rendered Breeze), `~/.config/Kvantum/kvantum.kvconfig` still `theme=MacTahoe`, legacy `AnimationSpeed=3` in kwinrc [Compositing] (set by apply-tahoe-theme.sh; conflicts with Plasma 6 `AnimationDurationFactor=1.0`), 6× MacTahoe GTK themes in ~/.themes, MacTahoe icons/aurorae decorations/desktoptheme/wallpapers in ~/.local/share, and 3 AUR packages (whitesur-gtk/icon/cursor-theme-git). Net effect: a three-way Breeze/WhiteSur/MacTahoe hybrid — the "stitched-together" UI feel.
- Root Cause: Revert only undid kwriteconfig6/Plasma changes; never touched GTK configs, Kvantum, ~/.themes, ~/.local/share assets, or pacman packages installed for Tahoe.
- Fix Applied: GTK3/4 → `Breeze-Dark`; deleted ~/.config/Kvantum, ~/.themes/MacTahoe-*, MacTahoe icons/aurorae/desktoptheme/wallpapers (incl. TahoeDusk.webp — verified not referenced by desktop or lockscreen); removed `AnimationSpeed` key from kwinrc; `pacman -Rns whitesur-{gtk,icon,cursor}-theme-git`; KWin reconfigured. Verified zero mac/tahoe/whitesur remnants on disk.
- Date Found: 2026-06-11
- Date Fixed: 2026-06-11

### BUG-067 — Shared RuntimeDirectory: restarting one daemon unlinks every other daemon's socket
- Status: FIXED — ACTIVE (one-time daemon restart done 2026-06-12; all /run/luminos sockets rebound and verified)
- Severity: HIGH
- Component: systemd units — luminos-ai, luminos-power, luminos-router, luminos-sentinel, luminos-ram
- Description: All daemons share `RuntimeDirectory=luminos` (/run/luminos). When luminos-power restarted on 2026-06-08 07:07, systemd removed and recreated /run/luminos, unlinking ai.sock, sentinel.sock, and ram.sock. The daemons kept listening on unlinked inodes (visible in `ss -xl`), but any client connecting by path got ENOENT. Sentinel→AI threat reports and the RAM widget were silently dead for 2 days.
- Root Cause: systemd removes a RuntimeDirectory on service stop by default. With a SHARED directory, the first service to stop destroys every sibling's socket. luminos-ram additionally never declared RuntimeDirectory at all — it depended on the other units creating the dir first.
- Fix Applied: `RuntimeDirectoryPreserve=yes` added to all five units (repo `systemd/` + `/etc/systemd/system/`), and `RuntimeDirectory=luminos` added to luminos-ram so it is self-sufficient. `systemctl daemon-reload` done. NOT restarted (HOPE model training in progress) — see PENDING_RESTART.md.
- Date Found: 2026-06-10
- Date Fixed: 2026-06-10

### BUG-066 — luminos-ram capability bounding set stripped CAP_KILL/CAP_SYS_NICE — freeze/kill/boost silently EPERM
- Status: FIXED — ACTIVE (daemon restart 2026-06-12; caps verified: cap_kill cap_sys_ptrace cap_sys_nice)
- Severity: HIGH
- Component: systemd/luminos-ram.service
- Description: The unit ran the daemon as root but with `CapabilityBoundingSet=CAP_SYS_PTRACE`, which strips ALL other capabilities — including CAP_KILL (SIGSTOP/SIGCONT/SIGKILL of other users' processes), CAP_SYS_NICE (setpriority boost AND process_madvise(MADV_PAGEOUT)). Every freeze/thaw/cold-kill/priority action failed with EPERM, and all those syscall errors were ignored in code (audit finding), so nothing was ever logged.
- Root Cause: Bounding set chosen when madvise() was still a stub (BUG-065) — nothing exercised the missing capabilities, so the gap was invisible.
- Fix Applied: `CapabilityBoundingSet=CAP_SYS_PTRACE CAP_SYS_NICE CAP_KILL` + matching AmbientCapabilities.
- Date Found: 2026-06-10
- Date Fixed: 2026-06-10

### BUG-065 — luminos-ram madvise() was a stub: every MADV_PAGEOUT in the eviction pipeline was a no-op
- Status: FIXED — ACTIVE (v3.5 binary running since 2026-06-12 restart)
- Severity: CRITICAL
- Component: cmd/luminos-ram/main.go
- Description: `madvise(pid, hint)` logged a debug line for MADV_WILLNEED and returned nil. All call sites — evictLast() hot→cold eviction, bottom-tier compression, Chrome renderer compression — did nothing. The madvPageoutCounter metric incremented anyway, so telemetry claimed compression was happening. The RAM manager's core memory-reclaim function never existed.
- Root Cause: Stub left in during v3.0 development; metric increments masked it.
- Fix Applied: Real `process_madvise(2)` implementation — `pidfd_open` on target, iovecs built from /proc/<pid>/maps (readable private mappings, kernel special mappings skipped), chunked at UIO_MAXIOV=1024. MADV_WILLNEED EINVAL treated as soft-miss for older kernels. Also fixed in same pass: D-Bus AddMatch errors now logged (silent focus-tracking death), session-bus connection cached instead of re-dialed every 3s tick, getChildPIDs() rewritten from full /proc/*/stat scan (O(all processes), direct children only — never found Chrome renderers, which hang off the zygote) to recursive /proc/<pid>/task/*/children walk (O(descendants), full tree).
- Verification: standalone test against a 64MB perl process — RSS 70,412 KB → 2,420 KB (68 MB reclaimed to zram) via the exact same code path.
- Date Found: 2026-06-10
- Date Fixed: 2026-06-10

### BUG-064 — MT5 KDE launcher waking NVIDIA GPU
- Status: FIXED
- Severity: MEDIUM
- Component: ~/.local/share/applications/wine/Programs/MetaTrader 5/MetaTrader 5.desktop
- Description: Launching MT5 via KDE app menu woke NVIDIA GPU because the .desktop Exec used plain `wine` with no GPU env vars. Without DRI_PRIME=0 and Mesa EGL/GLX/Vulkan overrides, Wine's GL falls back to the NVIDIA libGL (registered by nvidia-drm kernel module).
- Root Cause: The .desktop file was auto-generated by Wine install and not updated with the AMD-forcing env vars that mt5-luminos/luminos-wine-launcher had. Previous fix (gemini-cli 2026-05-11) created mt5-luminos but didn't wire it to the .desktop.
- Fix Applied: Created /usr/local/bin/luminos-mt5 — AMD forced (DRI_PRIME=0, __GLX_VENDOR_LIBRARY_NAME=mesa, 50_mesa.json EGL, radeon_icd Vulkan, radeonsi VAAPI). Desktop file Exec updated to luminos-mt5. Also adds market-closed warning (kdialog) on weekends. mt5-terminal.service updated with same env vars for headless service path.
- Date Found: 2026-05-30
- Date Fixed: 2026-05-30

### BUG-063 — HIVE web search returns "llama-server not running" error
- Status: FIXED
- Severity: HIGH
- Component: scripts/hive-daemon.py — _handle_chat
- Description: Web search queries always failed with "(llama-server not running — start it first)" even though web search doesn't need a model loaded.
- Root Cause: Web intent detection relied on Nexus routing (Path B). Path B calls `_swap_model("nexus")` immediately, which fails if llama-server isn't running. The [ROUTE:WEB] tag never reached the web handler.
- Fix Applied: Added early web intercept at the TOP of `_handle_chat`, before any `_swap_model` call. `detect_intent()` runs first — if result is "web", search runs immediately. If llama IS loaded, Nexus synthesizes the results. If llama is NOT loaded, raw formatted results are returned directly to the user.
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-062 — Chrome NVIDIA path: --ozone-platform=wayland + Vulkan crashes on PRIME offload
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos (NVIDIA path)
- Description: Selecting NVIDIA in the GPU picker caused Chrome to crash with SIGTRAP. Error: `'--ozone-platform=wayland' is not compatible with Vulkan` and `importing the supplied dmabufs failed (error 7)`.
- Root Cause: NVIDIA is a PRIME offload device — it renders offscreen and hands frames to the AMD KWin compositor via DMA-BUF. On Wayland + Vulkan, this cross-device DMA-BUF import between NVIDIA and AMD fails. Chrome's own Wayland platform code explicitly rejects this combination and crashes. AMD path is unaffected because AMD IS the KWin compositor (same device, no DMA-BUF handoff needed).
- Fix Applied: NVIDIA path switched from `--ozone-platform=wayland` to `--ozone-platform=x11` (XWayland). XWayland handles the NVIDIA→AMD frame handoff via X11 protocol instead of Wayland DMA-BUF — well-tested with NVIDIA PRIME. Also removed VAAPI feature flags from NVIDIA path (LIBVA_DRIVER_NAME=nvidia and VaapiVideoDecodeLinuxGL are non-functional on NVIDIA Linux; removing them avoids spurious init errors).
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-061 — Chrome AMD path: wrong Vulkan ICD filename → no AMD Vulkan device → SwiftShader CPU fallback → --use-gl=disabled
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos (AMD path)
- Description: After BUG-060 fix switched to --use-gl=angle --use-angle=vulkan, Chrome AMD path still landed on --use-gl=disabled. GPU process could not initialize Vulkan on AMD.
- Root Cause: BUG-060 fix set `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json` for the AMD path. This file does NOT exist on Arch Linux. Arch Mesa installs `radeon_icd.json` (no architecture suffix). Some other distros (Ubuntu, Fedora) install `radeon_icd.x86_64.json` — the Arch package does not. With a non-existent ICD path, the Vulkan loader finds no AMD ICD, enumerates only SwiftShader (CPU software Vulkan). ANGLE Vulkan then uses SwiftShader as its Vulkan device. Chrome detects software Vulkan and sets --use-gl=disabled to avoid software rendering overhead.
- Fix Applied: `radeon_icd.x86_64.json` → `radeon_icd.json` in chrome-luminos AMD path. Also cleared Chrome GPU/shader caches (GPUCache, GrShaderCache, ShaderCache) to remove stale --use-gl=disabled state from previous crash sessions.
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-060 — Chrome native: --use-gl=egl crashes GPU process → software rendering → YouTube stutter
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos
- Description: GPU process at 81.5% CPU, --use-gl=disabled, all GPU features disabled, YouTube stuttering on battery. chrome://gpu showed "GPU process was unable to boot: GPU access is disabled due to frequent crashes."
- Root Cause: Launcher passed --use-gl=egl which native Chrome 148 maps to gl=egl-gles2,angle=none. Native Chrome 148 only allows ANGLE backends: (gl=egl-angle,angle=opengl), (gl=egl-angle,angle=opengles), (gl=egl-angle,angle=vulkan). gl=egl-gles2 is not in the allowlist → GPU process exits immediately → Chrome retries 7 times → declares GPU broken → disables all hardware acceleration for the session. This happened on every Chrome launch since switching from Flatpak to native (BUG-059). On battery, software decode + luminos-power CPU cap = double throttle → severe stutter.
- Fix Applied: Changed --use-gl=egl to --use-gl=angle --use-angle=vulkan for both AMD and NVIDIA paths. AMD uses Mesa radv (VK_ICD_FILENAMES=radeon_icd.json), NVIDIA uses proprietary Vulkan (VK_ICD_FILENAMES=nvidia_icd.json). Cleared Chrome GPU/shader caches to remove stale crash state. Note: AMD ICD filename was still wrong at time of BUG-060 fix (see BUG-061).
- Date Found: 2026-05-28
- Date Fixed: 2026-05-28

### BUG-059 — Chrome GPU subprocess --use-gl=disabled — three layered mistakes (corrected)
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos (AMD path), AGENTS.md section 2
- Description: Chrome GPU subprocess spawns with `--use-gl=disabled --render-node-override=/dev/dri/renderD129` even after BUG-057 and BUG-058 fixes. Software rendering, GPU process at 50%+ CPU, severe video stutter.
- Root Cause (confirmed via sysfs /sys/class/drm/renderD*/device/vendor):
  1. WRONG RENDER NODE DOCS: AGENTS.md section 2 had render nodes backwards. Actual mapping: renderD128=NVIDIA (0x10de, card1 pci 01:00.0), renderD129=AMD (0x1002, card2 pci 65:00.0). Chrome was correctly selecting renderD129 (AMD) all along. The problem was EGL init failure on AMD, not wrong device selection.
  2. WRONG EGL VENDOR PATH (BUG-059 first attempt): Set __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json — this path does NOT exist inside the Flatpak sandbox. File is actually at /usr/lib/x86_64-linux-gnu/GL/glvnd/egl_vendor.d/50_mesa.json. Setting a non-existent path causes GLVND to load zero EGL vendors → guaranteed EGL failure.
  3. WRONG GL BACKEND: --use-gl=egl uses Chrome's bundled ANGLE. Even though ANGLE bypasses GLVND for most operations, on Wayland it still uses system GLVND EGL for display backend selection. Inside the Flatpak, NVIDIA EGL vendors (09_nvidia_wayland2.json, 10_nvidia.json) have lower sort numbers than Mesa (50_mesa.json) and claim the Wayland EGL display first. NVIDIA EGL cannot drive AMD hardware (renderD129) → ANGLE EGL init fails → --use-gl=disabled.
- Fix Applied (final): Abandoned Flatpak Chrome entirely. Installed native google-chrome-stable 148.0.7778.178 via AUR (yay). The Flatpak Freedesktop SDK 25.08 runtime has the NVIDIA GL extension installed which injects NVIDIA EGL vendors (09_nvidia_wayland2, 10_nvidia) that sort before Mesa (50_mesa) — this is baked into the Flatpak runtime and cannot be overridden at the launcher flag level without removing the NVIDIA GL extension from the Flatpak runtime itself. Native Chrome inherits /etc/environment directly (includes __EGL_VENDOR_LIBRARY_FILENAMES=50_mesa.json), no GL layer indirection, no NVIDIA EGL contamination. chrome-luminos updated to use google-chrome-stable with env vars via exec env. Created ~/.config/chrome-flags.conf (--ozone-platform=wayland). AGENTS.md section 2 render node table corrected (renderD128=NVIDIA, renderD129=AMD).
- Date Found: 2026-05-27
- Date Fixed: 2026-05-27

### BUG-058 — Chrome --use-gl=disabled recurring — chrome-flags.conf injecting --enable-zero-copy globally
- Status: FIXED
- Severity: CRITICAL
- Component: ~/.var/app/com.google.Chrome/config/chrome-flags.conf
- Description: Chrome GPU process running at 51% CPU with `--use-gl=disabled` and `--render-node-override=/dev/dri/renderD129` again after BUG-057 fix. Identical symptom: software rendering, severe lag.
- Root Cause: `chrome-flags.conf` contained `--enable-zero-copy` as a global flag, applied to every Chrome launch before the per-GPU launcher flags. `--enable-zero-copy` forces Chrome to open a DRM render node directly for DMA-BUF buffer sharing. Inside the Flatpak sandbox, Chrome's zero-copy subsystem picks `renderD129` (NVIDIA — first DRM device enumerated) regardless of `DRI_PRIME=0`. This hits the same EGL init failure as BUG-057, producing `--use-gl=disabled` in the spawned GPU process. The chrome-luminos launcher had already removed `--enable-zero-copy` from its flags (BUG-054 fix), but the global conf file re-injected it on every launch.
- Fix Applied: Stripped `chrome-flags.conf` to only `--ozone-platform=wayland`. Removed `--enable-zero-copy`, `--enable-gpu-rasterization`, `CanvasOopRasterization`, `UseSkiaRenderer`. All GPU-specific flags now live exclusively in `/usr/local/bin/chrome-luminos` where they are controlled per-GPU choice.
- Date Found: 2026-05-27
- Date Fixed: 2026-05-27

### BUG-057 — Chrome --use-gl=disabled on AMD Wayland Flatpak path
- Status: FIXED
- Severity: CRITICAL
- Component: /usr/local/bin/chrome-luminos
- Description: Chrome GPU process ran with `--use-gl=disabled` — entire browser rendered in software (CPU only). No GPU compositing, no hardware acceleration, severe Chrome lag.
- Root Cause: `--render-node-override=/dev/dri/renderD129` was passed to Chrome Flatpak on AMD path. On Wayland, Chrome gets its EGL context from KWin (the Wayland compositor), not by directly opening a DRM render node. The forced render node bypassed the Wayland EGL path, causing EGL initialization failure. Chrome then disabled GL entirely for the session. Second issue: `DRI_PRIME=0` and `VK_ICD_FILENAMES` were set via shell `export` before `flatpak run` — Flatpak sandbox does not inherit parent shell exports; they must be passed via `--env=` to `flatpak run`.
- Fix Applied: Removed `--render-node-override` from AMD path entirely. Moved `DRI_PRIME`, `VK_ICD_FILENAMES`, and `LIBVA_DRIVER_NAME` from shell exports to `--env=` arguments on `flatpak run`. NVIDIA path retains `--render-node-override=/dev/dri/renderD128` (correct for PRIME offload with desktop GL).
- Date Found: 2026-05-26
- Date Fixed: 2026-05-26

### BUG-056 — Chrome YouTube stutter — VAAPI not enabled on AMD path
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/chrome-luminos
- Description: Chrome video (YouTube) stuttered on AMD iGPU path.
- Root Cause: `radeonsi_drv_video.so` (Mesa VAAPI driver) is present at `/usr/lib/dri/` and supports H264/HEVC/VP9/AV1, but `LIBVA_DRIVER_NAME` was not passed into the Flatpak sandbox. Chrome couldn't discover the VAAPI driver → fell back to software video decode → CPU doing all decode work → GPU compositor sync stalls → stutter.
- Fix Applied: Added `--env=LIBVA_DRIVER_NAME=radeonsi` to `flatpak run` in chrome-luminos AMD path. Added `--enable-features=VaapiVideoDecodeLinuxGL,VaapiVideoEncoder` and `--ignore-gpu-blocklist` to Chrome flags. YouTube VP9+AV1 decode now hardware-accelerated on AMD 780M.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

### BUG-055 — Thermal zone oscillation + YT stutter (ZoneWarm/ZoneHot freq caps)
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-power/main.go — applyThermalGovernor(), thermalACZone3C
- Description: YouTube video stuttered. Logs showed zone 1↔2 oscillating every 12s (was 2s after BUG-053 hold-ticks fix), and then zone 2↔3 oscillating every 10s. Every zone transition changed max_freq (5.1→4.0→5.1 GHz or 5.1→3.0→5.1 GHz), causing renderer hitches.
- Root Cause: Any hard freq cap creates a self-defeating cooling loop: cap → CPU cools → cap removed → CPU boosts → reheats → cap reapplied. BUG-053's hold ticks extended the period but did not break the loop. Two issues: (1) ZoneWarm (72°C) had a 4.0GHz cap despite fans running at 100% above 70°C; (2) ZoneHot threshold was 80°C — too conservative for 8845HS (TJmax 105°C) during YouTube.
- Fix Applied: (1) Removed the 4.0GHz AC cap from ZoneWarm — fans at 100% handle cooling above 70°C without a hard cap. Battery path keeps 3.5GHz cap (correct behavior). (2) Raised thermalACZone3C from 80°C→87°C and thermalEmergencyC from 85°C→92°C. YouTube at 82°C stays in ZoneWarm with no cap. ZoneHot (3.0GHz) only triggers at genuine overheating (87°C+).
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

### BUG-053 — Thermal zone 1↔2 oscillation every 2s / Chrome rendering stutter
- Status: SUPERSEDED by BUG-055
- Severity: HIGH
- Component: cmd/luminos-power/main.go — applyThermalGovernor()
- Description: Thermal zone bounced between 1 and 2 every 2-4 seconds under load. Caused visible Chrome tab stutter.
- Root Cause: The 4.0GHz freq cap (applied at zone 2 entry, 72°C) cools the CPU from ~75°C to ~64°C in a single 2s tick, which crosses the 67°C exit threshold. Cap removed, CPU boosts, reheats → loop.
- Fix Applied (partial): Added `thermalDownholdTick` counter requiring 5 consecutive ticks below exit threshold before downgrading. Extended period to 12s but did not break the loop. Full fix in BUG-055: remove cap entirely from ZoneWarm on AC.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24 (fully resolved by BUG-055)

### BUG-054 — Chrome tab stutter on AMD iGPU path (--enable-zero-copy)
- Status: FIXED
- Severity: MEDIUM
- Component: /usr/local/bin/chrome-luminos
- Description: Tab scrolling and rendering hitches on AMD iGPU path.
- Root Cause: `--enable-zero-copy` causes intermittent rendering hitches with AMD Mesa on Wayland. Also compounded by BUG-053 CPU freq oscillation.
- Fix Applied: Removed `--enable-zero-copy` from the AMD (igpu) path in chrome-luminos. NVIDIA path keeps it (works correctly with desktop GL). Added `--enable-features=MemorySaver` to both paths to enable tab sleeping.
- Date Found: 2026-05-24
- Date Fixed: 2026-05-24

## Format
Each bug entry:
### BUG-XXX — Short title
- Status: OPEN / FIXED / WONTFIX
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Component: which file/module affected
- Description: what happens
- Root Cause: why it happens
- Fix Applied: what was changed
- Date Found: date
- Date Fixed: date

---

## Fixed Bugs

### BUG-052 — Kickoff Launcher Empty / Chrome Not Searchable
- Status: FIXED
- Severity: HIGH
- Component: ~/.config/plasma-org.kde.plasma.desktop-appletsrc, ~/.local/share/applications/com.google.Chrome.desktop
- Description: Opening the Start button showed a blank screen. Searching "chrome" returned nothing.
- Root Cause 1: `applicationsDisplay=0` — Kickoff defaults to Favorites tab. No apps were pinned to Favorites, so the launcher appeared empty. The All Applications tab existed but user had no way to know.
- Root Cause 2: Chrome desktop file Exec line had `@@u %U @@` — Flatpak-specific URL forwarding syntax that is invalid for a plain wrapper script. Caused incorrect desktop file parsing.
- Fix Applied: Set `applicationsDisplay=1` in plasma-org.kde.plasma.desktop-appletsrc (Kickoff opens to All Applications by default). Fixed Exec to `Exec=/usr/local/bin/chrome-luminos %U`. Rebuilt sycoca index via `kbuildsycoca6 --noincremental`. Restarted plasmashell via `systemctl --user restart plasma-plasmashell`.
- Date Found: 2026-05-21
- Date Fixed: 2026-05-21

### BUG-051 — Display Stutter / 120Hz Compositing Lag
- Status: FIXED
- Severity: MEDIUM
- Component: ~/.config/kwinoutputconfig.json, ~/.config/kwinrc
- Description: Desktop felt unsmooth/stuttery at 120Hz. Fans spinning without reason. kwin_wayland at 19% CPU idle.
- Root Cause: `vrrPolicy` was `"Never"` — compositor locked to hard 120Hz deadline every 8.33ms. Any frame taking slightly longer caused a dropped frame. Also: `GLPreferBufferSwap=a` (auto) and no latency policy set, both leaving performance on the table.
- Fix Applied: Set `vrrPolicy: "Automatic"` in kwinoutputconfig.json. Set `LatencyPolicy=Low` and `GLPreferBufferSwap=e` in kwinrc. KWin reloaded via `qdbus6 org.kde.KWin /KWin reconfigure`.
- Date Found: 2026-05-21
- Date Fixed: 2026-05-21

### BUG-050 — System Processes Keeping NVIDIA dGPU in D0 State
- Status: FIXED
- Severity: HIGH
- Component: /etc/environment
- Description: NVIDIA GPU staying awake (D0, ~8W) even when idle. KDE system processes (ksecretd, plasmashell, Xwayland, baloorunner) were opening NVIDIA EGL by default.
- Root Cause: No EGL vendor preference set — libEGL defaulted to NVIDIA (60_nvidia.json) for all processes. KWin also advertising renderD129 (NVIDIA) to Wayland clients via linux-dmabuf protocol.
- Fix Applied: Added to /etc/environment: `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json` (force AMD Mesa EGL for all session apps) and `KWIN_DRM_DEVICES=/dev/dri/card2` (restrict KWin to AMD DRM only). PRIME render offload for games still works.
- Date Found: 2026-05-14
- Date Fixed: 2026-05-14

### BUG-049 — Claude Desktop Memory Leak
- Status: MONITORING
- Severity: MEDIUM
- Component: Claude Desktop (Electron)
- Description: Electron renderer running 101+ hours. Memory grows from 300MB to 2.1GB over time.
- Root Cause: All Electron apps exhibit this growth pattern.
- Fix Applied: [Workaround] Restart Claude Desktop daily. Added background leak detection to `luminos-ram` (v3.1) to alert on future occurrences.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10 (Monitoring)

### BUG-048 — luminos-power Thermal Oscillation
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-power
- Description: CPU temperature oscillating between 60-88°C constantly.
- Root Cause: Profile switching thresholds had no hysteresis and no hold time, causing rapid toggling between Balanced and Performance. Performance mode raised TDP, causing more heat.
- Fix Applied: Removed auto-Performance switching. System stays in Balanced on AC with an aggressive fan curve (100% at 80°C). Added 30s hold time between profile changes and hysteresis for emergency Quiet mode (>85°C to enter, <75°C to exit).
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-047 — NVIDIA GPU Always Active
- Status: FIXED
- Severity: MEDIUM
- Component: NVIDIA Driver / Power Management
- Description: NVIDIA GPU wasting ~8W constantly by staying in D0 state.
- Root Cause: No power gating configured.
- Fix Applied: Implemented udev rules for auto power gating and enabled `NVreg_DynamicPowerManagement=0x02` in modprobe.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-046 — Chrome Using NVIDIA GPU
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/chrome-luminos
- Description: NVIDIA GPU active during all browsing, wasting 8-15W.
- Root Cause: Wrapper had `--render-node-override=/dev/dri/renderD129` (NVIDIA).
- Fix Applied: Removed render-node-override. `DRI_PRIME=0` correctly forces AMD iGPU.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-046b — luminos-ram "blind" to user desktop session
- Status: FIXED
- Severity: HIGH
- Component: cmd/luminos-ram, systemd/luminos-ram.service
- Description: The RAM management daemon was not tracking any active windows.
- Root Cause: The daemon was running as `root` and could not connect to user D-Bus.
- Fix Applied: Updated service to run as `User=shawn` with `CAP_SYS_PTRACE`.
- Date Found: 2026-05-10
- Date Fixed: 2026-05-10

### BUG-045 — Touchpad Input Lag / Jump Detection
- Status: FIXED
- Severity: MEDIUM
- Component: /etc/libinput/local-overrides.quirks
- Description: Input lag during browsing; stuttery scrolling.
- Root Cause: libinput discarding "touch jump" events on G14 touchpad.
- Fix Applied: libinput quirks + schedutil CPU governor.
- Date Found: 2026-05-09
- Date Fixed: 2026-05-09

### BUG-043 — HIVE popup crash (import: command not found)
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/luminos-hive-popup
- Description: SUPER+SPACE launch crash.
- Root Cause: Agent wrote GTK4 Python script for a bash-executed shortcut.
- Fix Applied: Rewrote to native bash + kdialog.
- Date Found: 2026-04-26
- Date Fixed: 2026-04-26
