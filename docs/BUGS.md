# Luminos OS — Bug Tracker
Last Updated: 2026-08-05 (BUG-104 FIXED — **mempalace reported "success" and threw every memory away, for at least ten days.** `add_drawer` returned a drawer_id, the WAL logged the call, and the drawer did not exist; the WAL shows `"result": null` on every add since 2026-07-26, and content is redacted there so none of it is recoverable. Root cause is in ChromaDB 0.6.3, not MemPalace: the palace's per-segment `max_seq_id` watermark held a poisoned ~1.23e18 timestamp while `embeddings_queue` — an `INTEGER PRIMARY KEY` with no AUTOINCREMENT — had been emptied and restarted numbering at 1, so `_notify_one` skipped every record as "already consumed" and `upsert()` raised nothing. Repaired by setting each watermark to the queue's current max row id; zeroing it does NOT work, because `start = start or self._next_seq_id()` treats 0 as falsy. Verified by readback in a fresh process. **The running MCP server keeps the poisoned subscription in memory and `mempalace_reconnect` does not rebuild it** — restart the server or file through the library. BUG-103 FIXED — the dGPU never went back to sleep after you used it: all three GPU launchers wrote `on` to `power/control`, which *disables runtime PM for the device*, and nothing anywhere ever wrote `auto` back, so the card sat at 1.63 W / P8 / `active` with zero processes holding it. The fix was to **stop writing `on`** — with `control=auto` the driver takes a runtime-PM reference when a device node is opened, so the card wakes on demand and re-suspends by itself ~20 s after the last close. No release mechanism was needed; the one line meant to help was the only thing preventing sleep. Proven end to end: NVIDIA Chrome came up on `renderD128` with `glRenderer = ANGLE (NVIDIA, … RTX 4050 …)`, then the card returned to `suspended` on its own, and `luminos-verify` section 3 now passes all three checks. Two side-findings: `luminos-wine-launcher` had silently diverged from its installed copy (repo newer but missing both EGL exports — reconciled), and it **never calls the dGPU gate at all**, so Wine-on-NVIDIA is still denied like BUG-102. `luminos-gpu-launch` was also promoted from `dgpu-exec` to `dgpu-exec-v2` in the same pass. BUG-102 FIXED — picking "NVIDIA" in the Chrome GPU dialog silently gave you the AMD iGPU for a month, with a notification claiming otherwise. Three stacked causes: `chrome-luminos` never called the dGPU gate at all; the gate itself is defeated by **any launcher written in shell**, because setgid raises only the *effective* gid and bash resets it (fixed by `dgpu-exec-v2`, which `setresgid`s so the group is real); and Chrome is single-instance per profile, so the picker could never take effect while a window was open. Now proven on the card — `ANGLE (NVIDIA, Vulkan …RTX 4050…)`, 20 fds on `/dev/nvidia0`, listed in `nvidia-smi`. Two Chromes on two GPUs at once works, given separate `--user-data-dir`. BUG-101 FIXED — the SUPER launcher's app list "barely scrolled", on the touchpad only: Caelestia ships `input:touchpad:scroll_factor = 0.3`, and in a viewport only `maxShown` rows tall, 30% of a swipe travels less than one row. The mouse wheel uses the **separate** `input:scroll_factor`, already 1.0 — which is why the two devices behaved differently. Overridden to 1.0 in `hypr-vars.lua`; no QML touched. BUG-100 FIXED — every hyprpm plugin was dead because hyprpm was still building against an April compositor. BUG-094 FIXED **AND VERIFIED ON A REAL LOGIN** — Hyprland is now the live session, the pin took effect, the dGPU is `suspended`, and Claude Desktop runs on the AMD `renderD129`. Original report: the Hyprland session bounced straight back to SDDM: `AQ_DRM_DEVICES` is a COLON-separated list and the GPU pin was written as a PCI by-path, so one device path split into three nonexistent ones and the compositor aborted with "Found no gpus to use". Neither stock name works (by-path has colons, cardN is unstable), so a colon-free udev alias `/dev/dri/luminos-igpu` was created. BUG-093 FIXED — a user-site `packaging` copy shadowed the pacman one, so pacman said 26.2 while Python said 26.0 and every AUR python build failed; fixed with `PYTHONNOUSERSITE=1`, nothing removed. BUG-092 FIXED — SDDM greeter wallpaper pointed at a missing file *under `$HOME`*, which the `sddm` user could never read anyway; the resulting black login screen was misread as a Hyprland crash. **Note:** BUG-092 was first filed as BUG-091 and renumbered — 091 was already taken by the suspend bug below. BUG-091 FIXED — lid close and idle now suspend; the machine never had a suspend bug, only three layers of deliberate config, and the first fix landed in a PowerDevil config group nothing reads. BUG-087 FIXED — MCP tooling now reaches Claude Code, Claude Desktop and Antigravity; hooks moved to user scope because Cowork ignores project scope. BUG-085 FIXED — MCP tooling silently rotted; now pinned + verified by `luminos-verify --mcp`. BUG-086 CLOSED/WONTFIX — leaked OpenRouter key accepted by user as a dead account, no rotation. BUG-084 OPEN — DrKonqi gdb+debuginfod ate 7.4GB and filled zram; durable MemoryMax cap NOT yet applied. BUG-083 FIXED + measured. BUG-082 FIXED (pending live verify). BUG-080 still OPEN — Wine/MT5.)

## Open Bugs

### BUG-086 — Live OpenRouter API key committed to git AND pushed to GitHub
<!-- [CHANGE: claude-code | 2026-07-25] -->
- Status: **CLOSED — WONTFIX (accepted by user, 2026-07-25).** User: *"fuck the OpenRouter thing its dropped deal"* — the account/arrangement is dead, so the key has no value to protect and no rotation is being done. **No further action; do not re-raise this.** The file stays as-is unless the user says otherwise.
  - Kept on record only because the *mechanism* is reusable knowledge (see "How it got there" below): a force-add can put a secret past `.gitignore`, and `.gitignore` cannot untrack it afterwards. If a **live** credential is ever committed, that is a different bug and the order is: rotate first, then `git rm --cached`, then decide about history.
- Severity: **CRITICAL** (credential disclosure)
- Component: `.claude/settings1.json` — a stale leftover Claude Code settings file
- Description: `.claude/settings1.json` is **tracked by git** and contains a live key in plaintext:
  `"ANTHROPIC_BASE_URL": "https://openrouter.ai/api/v1"` + `"ANTHROPIC_API_KEY": "sk-or-98117e…"`.
  It is present in `origin/main` on `git@github.com:vrapatel2002/luminos-os.git` — i.e. **already pushed**, not merely local. Confirmed with `git cat-file -e origin/main:.claude/settings1.json` and by reading the key back out of `git show origin/main:.claude/settings1.json`.
- How it got there — **`.gitignore` did not fail; it was overridden.** `.gitignore` line 11 has had `.claude/` since commit `b3919feb` (2026-03-25). The file was nevertheless added in `f1415d5e` (2026-04-24), i.e. **force-added** (`git add -f`, or staged explicitly) a month *after* the ignore rule existed — and the key was already in it in that first commit. Only that one commit ever touched the file, but the blob has been in every commit's tree since, so it is in the pushed history.
  Note the consequence: **adding `.claude/` to `.gitignore` again fixes nothing.** `.gitignore` only affects *untracked* files; once a path is tracked git keeps tracking it. The file must be explicitly removed (`git rm --cached`), and `.claude/settings.json` + `.claude/skills/*` are tracked the same way for the same reason.
  Context: AGENTS.md §7 records that OpenRouter was removed on 2026-05-27 for causing Signal 5 TRAP crashes. The config was abandoned but the file was never deleted, so the credential stayed.
- Required fix, in order:
  1. **Rotate/revoke the key at openrouter.ai first.** Assume it is compromised. History rewriting is pointless until the key is dead — clones and GitHub's cached views may already hold it.
  2. Delete `.claude/settings1.json` (it is a dead config — duplicates `settings.json` and re-adds the banned OpenRouter routing).
  3. Add `.claude/settings*.local.json` + any credential-bearing settings to `.gitignore`.
  4. Optional and destructive, user's decision only: purge from history with `git filter-repo`, which requires a force-push to a shared remote.
- Verify: `git log --all -p -- .claude/settings1.json | grep -c "sk-or-"` should be 0 after a history purge; the key should be rejected by OpenRouter after rotation.
- Date Found: 2026-07-25

### BUG-084 — DrKonqi crash handler stalls the whole desktop: gdb + debuginfod ate 7.4 GB and filled zram
<!-- [CHANGE: claude-code | 2026-07-24] -->
- Status: OPEN (incident cleared by hand 2026-07-24; the durable cap is NOT applied yet — it WILL recur on the next app crash)
- Severity: HIGH (whole-system stall — the desktop, Chrome and input all become unresponsive; this is the real cause of the "Chrome and the OS are not responding" report)
- Component: KDE `drkonqi` — `drkonqi-coredump-launcher@*.service` (systemd --user), spawning `/usr/bin/gdb ... --init-eval-command=set debuginfod enabled on --core=...`
- Description: Filelight segfaulted (SIGSEGV, 18:39:58, 364 MB core extracted to `~/.cache/drkonqi/cores/`). DrKonqi launched `gdb` with **debuginfod enabled** to build a submittable backtrace. gdb grew to **7.4 GB RSS / 16.3 GB VSZ at 70% CPU and was still running 12 minutes later**. Meanwhile **five** `drkonqi-coredump-launcher@*` units were active simultaneously (Filelight, plus several `kscreen-doctor` and `qml` crashes — `kscreen-doctor` segfaults reliably on this box and each crash arms another launcher).
  Measured at peak: RAM **13 of 14 GiB used, 1.8 GiB available**, **zram swap 100% full (80 KiB free of 8 GiB)**, `pswpout` 2.47 M pages, **PSI `/proc/pressure/memory` full avg10 = 7.85%** (the entire system doing no work 8% of the time, waiting on memory), io full avg10 = 4.22%. CPU PSI stayed ~1% — this was a *memory* stall, not a CPU shortage, which is why it feels like a freeze rather than slowness.
- Root Cause: an unbounded, unprioritised debug job runs in the user session with no memory cgroup limit. `debuginfod` downloads and loads full debug symbol sets, and a 364 MB core plus Qt/KDE debuginfo is enough to exhaust a 14 GiB box. Nothing caps it, nothing serialises the launchers, so N crashes = N concurrent gdb processes.
- Immediate clear (what was done): `systemctl --user stop 'drkonqi-coredump-launcher@*.service'`. Recovery was immediate — RAM used 13 → 5.6 GiB, available 1.8 → 9.3 GiB, swap 8.0 GiB full → 1.6 GiB, PSI memory full **7.85% → 0.08%**. No data lost: the cores remain in `~/.cache/drkonqi/cores/` and `coredumpctl`.
- Candidate durable fix (NOT applied — needs user go-ahead): a systemd drop-in on `drkonqi-coredump-launcher@.service` with `MemoryMax=` (e.g. 2G) + `MemoryHigh=`, so a runaway backtrace is OOM-killed **inside its own cgroup** instead of taking the desktop down. Crash reporting keeps working. Optionally also disable `debuginfod` for drkonqi (`DEBUGINFOD_URLS=`) and/or serialise the launchers so only one runs at a time.
- Related: `kscreen-doctor` reliably SIGABRTs on this box (23:55/23:58 on 2026-07-23, 18:38 on 2026-07-24) — every invocation risks arming another launcher. Worth fixing or avoiding separately.
- Verify: `cat /proc/pressure/memory` — `full avg10` should sit at ~0. `systemctl --user list-units --all 'drkonqi-coredump-launcher@*'` should show nothing running.
- Date Found: 2026-07-24

### BUG-083 — Live wallpaper decoded a 4K video 24/7 behind fullscreen windows (desktop/browser jank)
<!-- [CHANGE: claude-code | 2026-07-24] -->
- Status: FIXED (2026-07-24, measured)
- Severity: MEDIUM (no crash — steady-state CPU/iGPU contention felt as Chrome + desktop "not responding"/janky)
- Component: `src/wallpapers/org.luminos.livewallpaper/` (`contents/config/main.xml`, `contents/ui/main.qml`, `contents/ui/config.qml`) + the wallpaper source video
- Description: plasmashell sat at a **constant 24% of a core, 810 MB RSS and ~16–18% iGPU busy, forever**, including when a maximized Chrome window completely hid the desktop. Two independent causes stacked:
  1. **`PauseWhenObscured=false`** — set during BUG-081 so *web* wallpapers keep animating while covered — also applied to the **video** path, so the MediaPlayer decoded, uploaded and composited every frame with nothing visible.
  2. **The source video was 3840×2160** on a 2880×1800 panel — 8.3 MP decoded per frame to fill a 5.2 MP screen, ~1.8× more pixels than the display can show.
  The cost lands on the **iGPU (renderD129)**, which is the same device KWin composites on and Chrome renders on, so it shows up as input lag and dropped frames rather than as a fault. Confirmed *not* a fault: no amdgpu ring resets/hangs, no OOM, PSI cpu/memory/io all 0, 8.5 GB available.
- Root Cause: the obscured guard was a single bool that OR-ed `IsMaximized || IsFullScreen`, so it could only be all-or-nothing; turning it off (needed for web) removed the guard from video too. Nothing ever right-sized the video to the panel.
- Fix:
  - `PauseWhenObscured` (bool) → **`ObscurePolicy` (int)**: `0` never freeze, `1` freeze only under a **fullscreen** window, `2` freeze whenever the desktop is hidden (fullscreen **or** maximized) — **default 2**. Fullscreen and maximized are now graded separately per window (`cover` 2/1/0) instead of OR-ed.
  - 400 ms **debounce** (`coverDebounce`) so alt-tab / window drags don't stop-start the decoder several times a second.
  - Video transcoded 3840×2160 → **2880×1620** H.264 CRF 20, audio stripped (it is muted anyway). Original 4K file kept alongside.
- Measured (plasmashell, jiffies of one core):
  | State | CPU | RSS | iGPU |
  |---|---|---|---|
  | 4K, always render (before) | 240/10s (24%) | 810 MB | 16–18% |
  | 2880×1620, always render | 128/10s (12%) | 589 MB | 12% |
  | 2880×1620, hidden (now, default) | **1/10s (~0%)** | 617 MB | — |
  | 2880×1620, desktop visible | 61/6s (~10%) | — | — |
  Right-sizing alone ≈ **−47% CPU / −27% RSS**; the occlusion policy removes essentially all of it while hidden. Resume on uncover verified (minimize/restore Chrome via a KWin script → 0 → 61 jiffies/6s → 0).
- Interaction with BUG-081 / DECISION 31: the session-wide `QTWEBENGINE_CHROMIUM_FLAGS` anti-throttle is **kept** — it is what makes `ObscurePolicy=0` actually work for web wallpapers. The plugin policy is now the authority; the flags only remove the *involuntary* Chromium throttle.
- Known remaining gap (NOT fixed): the desktop wallpaper still plays while the **session is locked or the screen is DPMS-off** if no maximized window happens to be up — the lock greeter is not a window in `TasksModel`, so `coverLevel` stays 0. Needs a lock/idle signal. The lock screen's own copy is deliberately `ObscurePolicy=0`.
- Gotcha for future tests: KWin's **"Show Desktop"** does NOT set `IsMinimized`, so it does not change `coverLevel` — use a real minimize/unmaximize to test the guard.
- Verify: `awk '{print $14+$15}' /proc/$(pgrep -x plasmashell)/stat` twice 10 s apart with a maximized window up — the delta should be ~0.
- Date Found / Fixed: 2026-07-24

### BUG-082 — Video live-wallpaper freezes on resume from sleep (stale MediaPlayer decode surface)
<!-- [CHANGE: claude-code | 2026-07-24] -->
- Status: FIXED (2026-07-24, applied — pending live suspend/resume verification by user)
- Severity: MEDIUM (cosmetic — desktop shows a frozen last frame after wake; no crash, no data loss)
- Component: `src/wallpapers/org.luminos.livewallpaper/contents/ui/main.qml` (`videoComp`, the QtMultimedia `MediaPlayer`)
- Description: On lid-open / unlock after suspend, the video wallpaper shows a frozen still frame and never resumes playing. On suspend the kernel tears down the MediaPlayer's GPU decode surface / pipeline; on resume it holds the last decoded frame but does not restart decoding. Playback was driven ONLY by `shouldPlay` (battery + window-obscured) via `onActiveChanged`, and neither of those changed across a plugged-in / unobscured suspend — so `player.play()` was never re-invoked. Even if it had been, a bare `play()` cannot revive a pipeline whose decode surface was destroyed; the source must be re-seated. GIF (CPU `AnimatedImage`) and web (`WebEngineView` self-recovers) modes were unaffected — video only.
- Root Cause: no suspend/resume handler existed in the plugin; the `MediaPlayer` pipeline is invalid after resume and nothing re-loads it.
- Fix: added a 1s repeating `Timer` inside `videoComp`. Timers don't tick during suspend, so a wall-clock gap >3s between ticks means the machine just resumed — on that first wake tick it `stop()`s, clears `source` to `""`, re-assigns `root.effectiveVideo`, and `play()`s, rebuilding the decode surface. Nothing runs during sleep; the check only fires on wake and is a no-op during normal playback.
- Known limitation: for YouTube sources the reload re-uses the previously resolved googlevideo URL (does NOT re-run yt-dlp), so a very long sleep can still black-out on YouTube until the resolver refreshes; direct local video files recover cleanly every wake.
- Verify (live): `kquitapp6 plasmashell && kstart plasmashell`, set a local video wallpaper, suspend, wait, reopen — video should re-seat and play instead of freezing.
- Date Found / Fixed: 2026-07-24

### BUG-080 — Wine 11.8→11.13 upgrade breaks the headless MT5 trading stack (forex-bot crash-loops)
<!-- [CHANGE: claude-code | 2026-07-21] -->
- Status: OPEN (deferred — fix in a future session; live-trading infra, needs a deliberate window)
- Severity: HIGH (the live forex trading bot cannot run — it refuses to trade without a broker link, so no wrong trades, but no trading either)
- Component: `wine` (11.8-1 → 11.13-1, upgraded 2026-07-21 in the big -Syu), `~/.config/systemd/user/mt5-terminal.service` + `mt5linux.service` + `forex-bot.service`
- Description: After the full system upgrade, the two Wine-based services start and **exit cleanly (status 0) after ~3s** instead of staying resident: `mt5-terminal.service` (MetaTrader 5 `terminal64.exe` headless on Xvfb :99) and `mt5linux.service` (Windows-Python310 RPyC daemon that should listen on port 18812). Result: **port 18812 stays CLOSED**, so `forex-bot.service`'s `ExecStartPre` bridge-readiness gate (waits up to 120s for 18812) times out with "bridge port 18812 never came up", the bot fails, and systemd auto-restarts it in a crash loop (StartLimitBurst=3 / 600s). The bot itself, its venv, CUDA path etc. are NOT the fault — the Wine layer under MT5 is.
- Root Cause (suspected, NOT yet confirmed): Wine 11.13 (+ wine-mono 11.1→11.2) changed prefix/loader behaviour vs 11.8; the MT5 terminal + Python310-under-Wine now terminate immediately. Most likely the `~/.wine` prefix needs a `wineboot -u` migration after the version bump, or a genuine regression in 11.13 for this headless GUI workload.
- Candidate fixes (NOT applied — awaiting a deliberate session; do NOT touch live-trading infra casually):
  (a) least invasive — `WINEPREFIX=~/.wine wineboot -u` to migrate the prefix under 11.13, then `systemctl --user start mt5-terminal mt5linux` and re-check port 18812;
  (b) surgical rollback — reinstall `wine 11.8-1` (+ wine-mono 11.1.0) from the Arch Linux Archive (NOT in local pkg cache) and add `wine` to IgnorePkg so it stays pinned to the known-good version, keeping all 640 other upgrades;
  (c) run `mt5-terminal.service`'s ExecStart manually under Wine 11.13 with WINEDEBUG to capture the real exit reason.
- Verify: `(exec 3<>/dev/tcp/127.0.0.1/18812)` should succeed (port OPEN) and `systemctl --user status forex-bot` should reach `active (running)`.
- Date Found: 2026-07-21

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

### BUG-091 — Laptop never slept: lid close and idle were both disabled on purpose, and the fix went to a config file PowerDevil no longer reads
<!-- [CHANGE: claude-code | 2026-08-02] -->
- Status: **FIXED (2026-08-02) — VERIFIED END TO END (2026-08-03).** No longer pending. The journal caught a real, unprompted lid close by the user:
  `00:50:11 systemd-logind: Lid closed.` → `suspend requested from client PID 27911 ('org_kde_powerde')` → `The system will suspend now!` → **40 h in s2idle** → `Aug 03 16:56:23 systemd-logind: Lid opened.` → `PM: suspend exit`, clean resume, session intact. `suspend_stats` success 2 / fail 1.
  The ~41 `Timekeeping suspended for ~3600 s` lines all share one wallclock stamp because the kernel ring buffer only drains at full resume — they are the hourly s2idle re-arm cycles (`PM: Triggering wakeup from IRQ 9` → `ACPI: PM: Rearming ACPI SCI for wakeup`), **not** 41 separate suspends. Bracket by `PM: suspend entry`/`exit`, which occur exactly once each.
- **Residual (minor, self-recovering): the FIRST lid close aborted the suspend.**
  `PM: Wakeup pending, aborting suspend` / `PM: active wakeup source: mmc0` / `systemd-sleep: Failed to put system to sleep. System resumed again: Device or resource busy` — the **empty SD card reader** (`rtsx_pci_sdmmc`) raised a spurious wakeup 600 ms into device suspend. PowerDevil retried 11 s later and that attempt held for 40 h.
  Note the PCI device's `power/wakeup` **already reads `disabled`**, so this is not a PCI PME wake — it is a kernel wakeup source registered by the mmc core (card-detect), and toggling PCI wakeup will not silence it. `/sys/kernel/debug/wakeup_sources` shows `mmc0` with `active_count 2`, `prevent_suspend_time 3295248`. Same device already logs ~12 errors per boot with no card inserted. Fixing it means constraining `rtsx_pci_sdmmc` — that removes SD-reader function, so it is a **user decision, not applied**.
- Severity: MEDIUM (battery drain in a bag; the machine had already run flat once)
- Component: `/etc/systemd/logind.conf.d/`, `~/.config/powerdevilrc`, `/etc/udev/rules.d/99-luminos-lid.rules`, `/etc/systemd/sleep.conf`
- Symptom as reported: *"this laptop g14 is not going to sleep when lid is closed or after certain time of inactivity."*
- **Not a bug in the suspend path.** Proven with a controlled `rtcwake -m freeze -s 30` before changing anything: slept the full 30 s, reached `s0i3`, `ACPI: \_SB_.PEP_: Successfully transitioned to state lps0 entry`, resumed on IRQ 9, `suspend_stats` success 0→1 / fail 0. An earlier reading of the journal that concluded "suspend bounces out after 5 s" was **wrong** — those were `upowerd` critical-battery suspends while the user repeatedly opened the lid, and the final one had no exit because the battery died.
- Root cause — **deliberate configuration, three independent layers**, all from commit `f8e00ab0` (2026-06-03), task line *"keep all processes running on lid close, screen off only"*:
  1. `luminos-nolidsleep.conf` → `HandleLidSwitch`/`ExternalPower`/`Docked` all `ignore` (confirmed live via `busctl`, **not** `systemctl show` — these are Manager properties and `systemctl show` returns empty for them, which reads as "unset" rather than erroring).
  2. `powermanagementprofilesrc` → `lidAction=0` on both profiles.
  3. `99-luminos-lid.rules` → `luminos-lid.service` → `kscreen-doctor` blanked the panel instead of sleeping.
  Idle-suspend was never configured **at all** on either profile, and logind `IdleAction` is `ignore`.
- **The silent-failure trap** (this is the reusable part): the first fix wrote `LidAction=1` into `~/.config/powerdevilrc` under a bare `[AC]` group. KConfig parsed it happily and PowerDevil **opened the file** — confirmed with `inotifywait` — and the setting did nothing. PowerDevil 6.7's `ProfileSettings` registers its items against **subgroups**, so the live key is `[AC][SuspendAndShutdown] LidAction`. Same shape as BUG-088/089: a write that succeeds into a location nothing reads.
  Also note `powermanagementprofilesrc` is legacy: `ProfileSettings` is a `KConfigSkeleton` over **`powerdevilrc`**. Editing `[AC][DPMSControl] idleTime` in the old file provably changed nothing.
- Verify (do this, do not assume):
  ```
  qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/Actions/HandleButtonEvents \
    org.kde.Solid.PowerManagement.Actions.HandleButtonEvents.lidAction     # -> 1 (Sleep)
  busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
    org.freedesktop.login1.Manager HandleLidSwitch                         # -> "suspend"
  ```
  ⚠️ Do **not** use `triggersLidAction()` as the check — it returns `true` for every configuration including `LidAction=0`. It reports that PowerDevil owns the lid event, not what it will do. Caught only by negative-testing.
- Fix: see LUMINOS_DECISIONS.md DECISION 38. Backups in `backups/power-2026-08-02/`.
- Date Found: 2026-08-02

### BUG-085 — MCP tooling (code-review-graph + MemPalace) silently rotted: hooks never ran, MemPalace was registered twice, crg rode Arch's rolling python
<!-- [CHANGE: claude-code | 2026-07-25] -->
- Status: FIXED (2026-07-25) — all six defects fixed and negative-tested
- Severity: HIGH (the two tools AGENTS.md makes *mandatory* before every task were degrading with no error surfaced anywhere; the graph silently went stale and MemPalace answered from an unintended install)
- Component: `.claude/settings.json` hooks, `.mcp.json`, `~/.claude.json`, `~/.local/bin/code-review-graph`, `~/.local/bin/mempalace`
- Symptom as reported: *"they work, we add some new things, it breaks its environment and it stops working."*
- Root cause — **every dependency was a moving target and every failure was silent.** Six distinct defects:
  1. **The hooks had never once run.** `.claude/settings.json` invoked bare `code-review-graph` on PostToolUse (`Edit|Write|Bash`) and SessionStart. Hooks execute in a **non-interactive shell** whose `PATH` is only `/usr/local/bin:/usr/bin`; `~/.local/bin` is added by `~/.zshrc` line 33, which such shells never source. Result: `code-review-graph: command not found`, every single time, exit status swallowed. The 30 s timeout was never the issue — a real update takes **1.1 s**.
  2. **MemPalace was registered twice under the same name**, in two files pointing at two different installs: `~/.claude.json` (local scope) → `/home/shawn/mempalace-venv` = uv venv, **editable**, v3.1.0; `.mcp.json` (project scope) → `/home/shawn/.mempalace-venv` = pyenv 3.12.13, pinned, v3.3.1. Local scope wins, so the **editable v3.1.0** was live while AGENTS.md §6 documented the other one.
  3. **That install was editable** (`direct_url.json` → `{"editable": true, "url": "file:///home/shawn/mempalace"}`). A `git pull` in `~/mempalace` mutated the running server instantly. **This is the mechanism behind the reported symptom.**
  4. **Three MemPalace copies existed**, the third being an editable install in `~/.local/lib/python3.14/site-packages` — a shared user-site with **301 packages** (chromadb, hnswlib, llama-cpp-python, onnxruntime, PyQt6 …) sitting on Arch's rolling python. Every `pip install --user` mutated the environment these tools resolved against. All three wrote the same 2.0 GB store at `~/.mempalace/palace`.
  5. **`code-review-graph` was nailed to a rolling interpreter** — shebang `#!/usr/bin/python3`, packages in `~/.local/lib/python3.14/site-packages`. The next Arch python minor bump would have made them vanish. (Notes confirm this already bit once: `2026-05-07 | Removed all references to code-review-graph from AGENTS.md and GEMINI.md to stop startup errors.`)
  6. **5,951 stale lock files** in `~/.mempalace/locks`, oldest 2026-04-22, never reaped.
- Fix applied:
  - `code-review-graph` installed into its own **pyenv 3.12.13** venv `~/.code-review-graph-venv` (pinned `==2.3.1`, no extras — the `all` extra pulls `ollama`, banned by Rule 9). `~/.local/bin/code-review-graph` is now a symlink into it, so the shebang is absolute and Arch upgrades cannot reach it.
  - Duplicate `mempalace` entry removed from `~/.claude.json`; **`.mcp.json` is now the single authoritative registration** (version-controlled, travels with the repo).
  - `~/.local/bin/mempalace` (CLI) repointed at the same pinned venv, so CLI and MCP can no longer disagree.
  - Hooks rewritten to **absolute paths** with an explicit `--repo`, so neither PATH nor cwd can break them.
  - `scripts/luminos-verify` gained **section [5] MCP tooling** + a `--mcp` flag; SessionStart now runs `luminos-verify --mcp --quiet` instead of the broken `code-review-graph status`.
  - Locks reaped 5,951 → 0.
- **Why it will not silently rot again:** section [5] performs a *real* MCP `initialize` handshake per server and hard-fails on: duplicate registration, an interpreter under `/usr/bin/python*`, an interpreter outside `~/.pyenv` (house rule), any editable install, a missing binary, or a server that starts but returns no valid result. Each of those was negative-tested by deliberately reintroducing the fault. `--quiet` was also fixed to still print the summary line — it previously printed **nothing at all**, so a FAIL looked exactly like a PASS, which would have re-created the same silent-rot disease inside the very check meant to catch it.
- Gotcha found while writing the check (do not repeat): **never `os.path.realpath()` a venv's `bin/python` to locate its site-packages.** It resolves the symlink *out* of the venv into `~/.pyenv` or `~/.local/share/uv`, so you inspect the wrong tree. An earlier version of section [5] did this and reported a clean PASS for a known-editable install. Derive the venv from the **configured** command path instead.
- Also note: pip/uv mark editable installs differently — pip writes `<dist-info>/direct_url.json`, uv drops a bare `_<pkg>.pth`. Section [5] checks both.
- Verify: `luminos-verify --mcp` → 8 checks, expect PASS. Functionally confirmed by real `tools/call`: MemPalace 29 tools, `mempalace_search("dGPU power gating RTD3")` → 15 hits; code-review-graph 24 tools, `list_graph_stats_tool` → 259 files / 3161 nodes / 21658 edges, `query_graph_tool(callers_of, setEPPAfterAsusctl)` → 4 callers.
- Date Found / Fixed: 2026-07-25

### BUG-081 — Web live-wallpaper freezes (0 fps) whenever a window fully covers the desktop, regardless of the plugin's freeze checkbox
<!-- [CHANGE: claude-code | 2026-07-23] -->
- Status: FIXED (2026-07-23)
- Severity: MEDIUM (web wallpapers appeared "broken/frozen"; user almost always has a maximized window up, so the wallpaper was frozen ~all the time)
- Component: `org.luminos.livewallpaper` web mode (WebEngineView) + KWin/QtWebEngine occlusion throttling + `~/.config/plasma-workspace/env/luminos-wallpaper-nothrottle.sh`
- Description: When any normal window is maximized/fullscreen and fully covers the desktop, the web wallpaper's renderer drops to **0 CPU jiffies** (measured) — the rAF loop stops. Unchecking the plugin's "Freeze when a window covers the desktop" box did NOT help, because the freeze happens BELOW the plugin: KWin stops driving frame callbacks to the occluded desktop surface and Chromium background-throttles the occluded WebEngine. So the plugin's `PauseWhenObscured=false` was overridden by the engine's own throttle.
- Root Cause: Chromium/QtWebEngine renderer backgrounding + occluded-window throttling on the always-present desktop surface. Not the plugin's `shouldPlay`/lifecycleState logic (that correctly kept the page Active).
- Fix Applied: session env `QTWEBENGINE_CHROMIUM_FLAGS="--disable-backgrounding-occluded-windows --disable-renderer-backgrounding"` via `~/.config/plasma-workspace/env/luminos-wallpaper-nothrottle.sh` (KDE sources it at session start). The plugin's checkbox still works: CHECKED → plugin explicitly freezes when covered (power save); UNCHECKED → these flags let it keep animating while covered.
- Verify (measured 2026-07-23): renderer jiffies over 3–4s while `cover_count=1` — BEFORE flags = **0** (frozen); AFTER flags = **17–24** (~30fps, animating). Confirmed with both the particles and aurora samples.
- Note: the *particles* sample is cursor-reactive only, so even un-frozen it looks static when covered (no cursor reaches the desktop). Autonomous samples (aurora) and video wallpapers show visible motion. Desktop switched to aurora to demonstrate.
- Date Found / Fixed: 2026-07-23

### BUG-079 — Conductor fan PID hunts/winds-up at idle: fan surges 2100↔3500 rpm on a flat 49.8°C
<!-- [CHANGE: claude-code | 2026-07-04] -->
- Status: FIXED (2026-07-04) — tuned + idle-validated; Conductor still gated OFF by default (LUMINOS_CONDUCTOR=1)
- Severity: MEDIUM (loud/wasteful — audible "breathing"; thermally safe, only over-cools. This is the behavior that blocked enabling the Conductor after the 2026-07-03 test that maxed the fan at ~53°C)
- Component: cmd/luminos-power/fan_control.go (FanController PID), driven by the Conductor (DECISION 24)
- Description: First clean idle live test (2026-07-04, dGPU suspended, correctly classified idle/light → 47°C target) showed the CPU fan climbing 2400→3500 rpm while Tctl sat FLAT at 49.8°C, then oscillating 2600↔3500 on a ~30s period. Not a temp rise — the fan chased a target the workload parked ~2.8°C above.
- Root Cause: four compounding flaws — (1) `Kp=14` too hot (1°C→5.5% fan); (2) integral windup via a hard ±120 clamp that unwound only when error went negative (slow slew-down kept it pinned); (3) no smoothing on the spiky per-core Tctl the PID reacted to; (4) a fixed 47°C idle target below the workload's natural settling temp (~50°C) → permanent positive error the integral kept accumulating.
- Fix Applied: `fan_control.go` — (1) Kp 14→8, Ki 0.6→0.5; (2) ±2°C **deadband** around the target (no correction in-band → stops the surge); (3) **EMA smoothing** of the control temp (TempAlpha=0.30); (4) **back-calculation anti-windup** (Kbc=0.5) replacing the hard clamp, plus an in-band **integral leak** (0.90/tick) so the fan settles down after a hot spell. `NewFanController` retuned; `Reset()` re-primes the temp EMA on intent change.
- Verify: re-run the same 75s auto-reverting test (drop-in `LUMINOS_CONDUCTOR=1` + restart). Post-fix result: fan held a STEADY ~2100–2200 rpm (CPU) / ~2400–2500 rpm (GPU) with Tctl 48–50°C — no surging, hunting eliminated. Reverted to the static curve after the test; not yet made persistent (idle validated; a load test is still recommended before default-on).
- Date Found / Fixed: 2026-07-04

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

### BUG-087 — MCP tooling reached only one of three clients; hooks were dead in Cowork
<!-- [CHANGE: claude-code | 2026-07-25] -->
- Status: **FIXED** (follow-on to BUG-085)
- Severity: HIGH (tools silently unavailable / silently stale)
- Components: `~/.claude/settings.json`, `~/.config/Claude/claude_desktop_config.json`, `~/.config/Antigravity/User/mcp.json`, `.mcp.json`, `.claude/settings.json`, `scripts/luminos-verify`, `scripts/luminos-hook-*`
- Trigger: user asked whether Claude Desktop / Antigravity / the CLI could all use MemPalace and code-review-graph, then challenged how the tools were being "used" at all in a Desktop-hosted session.
- Findings:
  1. **Claude Desktop had no `mcpServers` key at all**; Antigravity had only `hive-brain`. Neither could use either tool. Three stale 0-byte `~/.gemini/*/mcp_config.json` files were unrelated leftovers.
  2. **Cowork launches Claude Code with `--setting-sources=user`.** The repo's `.mcp.json` and `.claude/settings.json` are therefore never read there. BUG-085's fix had put both the registration and the hooks in project scope, so in Cowork the registration was absent and **both hooks were dead**. Proven, not inferred: `graph.db` mtime stayed at 19:00:49 across an editing session whose last edit was 19:28:30.
  3. `~/.claude/settings.json` was a **third** `mcpServers` location the BUG-085 health check never looked at, and it pinned `ANTHROPIC_BASE_URL` to a dropped OpenRouter account — harmless in Cowork (OAuth token) but would route plain `claude` in a terminal to a dead endpoint.
  4. **`code-review-graph` fails silently when it cannot find a repo.** From a non-repo cwd it returns `status: ok` with `Files: 0` rather than erroring — so a GUI client with an arbitrary cwd would answer every query with "nothing found".
- Fix:
  - Registration and hooks moved to **user scope**, the only scope loaded by both the CLI and Cowork. `.mcp.json` emptied with a comment explaining why, so nobody re-adds it and recreates the duplicate-scope trap.
  - Both tools registered in Claude Desktop and Antigravity, pointing at the same pinned venvs. `--repo` explicit for GUI clients, omitted for Claude Code so it follows the current repo.
  - Hooks became self-gating wrappers (`scripts/luminos-hook-*`) so user scope does not fire them in unrelated projects.
  - Dead OpenRouter `env` block removed.
  - `luminos-verify --mcp` widened from 2 config files to 5, and now checks: per-client coverage, cross-client binary agreement, GUI `--repo`, hooks-in-user-scope, hooks-not-double-defined, hook commands executable, and **hook liveness**.
- Verification: all three client configs spawned exactly as that client would spawn them, from a GUI-like `cwd=/` — mempalace v3.3.1 / 29 tools / 15 search hits and code-review-graph v2.14.7 / 24 tools / 3161 nodes, in every client. Eight negative tests (duplicate scope, missing client registration, divergent binary, missing `--repo`, hooks absent from user scope, hooks in both scopes, non-executable hook command, corrupted client JSON) each produced the expected failure and the check returned to PASS after restore.
- **Open caveat — RESOLVED 2026-07-26, and the answer is NO.** <!-- [CHANGE: claude-code | 2026-07-26] --> A fresh Cowork session on 2026-07-26 (started 18:16, checked against `date -Is`) wrote **nothing** to `~/.luminos-hooks.log`: no `SessionStart` line, and no `PostToolUse` line after ~15 `Bash`/`Edit` tool calls. The log's only entry remains `2026-07-25T20:18:16 SessionStart pid=334453`, written by a *terminal* CLI session. So hooks fire in the Claude Code **CLI** and do **not** fire in **Cowork** — the registration is correct and simply never executed, which is precisely the failure shape this bug is about. `luminos-verify --mcp` correctly reports `PASS — 1 warning`, that warning being the dead `PostToolUse`. **Consequence: inside Cowork the code graph never refreshes by itself** (confirmed: `last_updated 2026-07-25T19:58:58` while editing on 2026-07-26). Options, none installed yet — user decision pending: a `systemd --user` **path** unit on `~/luminos-os/.git/index` running `~/.code-review-graph-venv/bin/code-review-graph update --skip-flows --repo ~/luminos-os` (~1.1 s, idle when nothing changes), or an explicit `build_or_update_graph_tool` call at the top of each Cowork session. Note that a plain `PathModified` on the repo *directory* is **not** sufficient — systemd path units are not recursive, so edits inside subdirectories would never fire it.
- Gotcha for future work: two concurrent MemPalace servers against the one 2.0 GB store are fine for reads (tested: both handshook, concurrent searches in 0.6s, ~290 MB RSS each). Writes go through Chroma's embedded SQLite in `journal_mode=delete` with a 5 s busy timeout, so simultaneous heavy ingest from several clients can raise `database is locked` — contention, not corruption. Ingest paths take a real `fcntl.flock`.
- Correction to BUG-085: the "5,951 stale locks" listed there were harmless zero-byte litter, not stuck locks — `flock` releases on process death. That entry overstated the fault count as six; five were real.

### BUG-088 — Ubuntu (Yaru) look reverts to Breeze on every lock/idle; the heal script reported success while doing nothing
<!-- [CHANGE: claude-code | 2026-07-26] -->
- Status: **FIXED**
- Severity: MEDIUM (cosmetic, but the "fix" actively lied about its own result)
- Components: `~/.config/kdeglobals`, `scripts/luminos-ubuntu-persist`, `systemd/luminos-ubuntu-look.service`, kded module `lookandfeelautoswitcher`
- Symptom (user): "the ubuntu theme is set back to plasma… I told you to make it hold reboot/sleep and more but it didn't even survive a lock and login back."
- **Root cause 1 — the reset was never prevented, only cleaned up after.** `kdeglobals [KDE] AutomaticLookAndFeel=true` enables KDE's automatic Global-Theme switcher, served by the autoloaded kded module `/usr/lib/qt6/plugins/kf6/kded/lookandfeelautoswitcher.so` (confirmed loaded via `qdbus6 org.kde.kded6 /kded org.kde.kded6.loadedModules`; the binary links `KIdleTime` + `KDarkLightSchedule`). Per `/usr/share/config.kcfg/lookandfeelsettings.kcfg` it switches on **time of day** and, separately, on `AutomaticLookAndFeelOnIdle` — whose default is **`true`**, with `AutomaticLookAndFeelIdleInterval` defaulting to **5 seconds**. Applying a Look-and-Feel package rewrites colour scheme, icons, cursor, widget style, Plasma style and window decoration. So every lock, every resume, every 5 s of idle re-slammed `org.kde.breezedark.desktop` back on. A login-time oneshot can never win that race. **Both keys must be written explicitly — setting only `AutomaticLookAndFeel=false` leaves the on-idle path at its `true` default.**
- **Root cause 2 — `plasma-apply-colorscheme` no-ops when the name key already matches.** The heal script wrote `ColorScheme=Yaru` *before* calling it, so the tool answered `The requested theme "Yaru" is already set…` and exited 0 **without writing the `[Colors:*]` blocks**. Result: the name said `Yaru` while the payload was Breeze Dark. Measured, not guessed: live `kdeglobals` matched `/usr/share/color-schemes/BreezeDark.colors` on **96 of 96** colour keys, and `Yaru.colors` on 4 of 60.
- **Root cause 3 — the drift check read the name, so defect 2 made it self-blinding.** It saw `ColorScheme=Yaru`, concluded all was well, and printed `Ubuntu (Yaru) look re-affirmed.` on every login for four days while the desktop was visibly Breeze. The script had no failure path at all — that string was unconditional.
- Fix:
  - `AutomaticLookAndFeel=false` **and** `AutomaticLookAndFeelOnIdle=false`; kded module unloaded live so it stops in the running session, not only at next login. Backup: `~/.config/kdeglobals.bak-yaru-20260726`.
  - `luminos-ubuntu-persist` now (a) re-asserts both keys and unloads the module on every run, (b) checks the colour **payload** (`[Colors:Button] DecorationFocus == 233,84,32`, Yaru's #E95420) instead of the name, (c) clears the name key before re-applying so `plasma-apply-colorscheme` cannot short-circuit, (d) exits **non-zero and prints the actual values** when the end state is wrong.
- Verification: after the fix, live `kdeglobals` matches `Yaru.colors` on **60/60** keys and BreezeDark on 4/60; accent `233,84,32`; module absent from `loadedModules`; `kdeglobals` md5 unchanged across a 20 s idle window. Negative-tested by recreating the exact broken state (`plasma-apply-colorscheme BreezeDark` then `kwriteconfig6 ColorScheme Yaru`) — the old script would have printed "re-affirmed"; the new one printed `colour payload drifted (accent='61,174,233') — re-applying Yaru` and healed it.
- Not a defect, do not "fix": `widgetStyle=Breeze` and Plasma style `default` are **intentional** per DECISION 30 — there is no maintained Yaru widget/Plasma theme; the Ubuntu identity comes from the orange colour scheme, Yaru icons/cursor and Ubuntu fonts.
- Known cosmetic residue: `Icon theme "Humanity" not found.` spams the journal from every KDE process. `luminos-ubuntu-look` deliberately sets Yaru's `Inherits=Humanity,Papirus,breeze,hicolor` and `humanity-icon-theme` is not installed. Harmless (the chain falls through to Papirus) but noisy — drop `Humanity,` from that list if the spam matters.
- Also observed while diagnosing: **Plasma is now 6.7.3**, not the 6.6.4 recorded in AGENTS.md §1. `plasma-apply-colorscheme` / `plasma-apply-cursortheme` have SIGABRT coredumps on 2026-06-24 and 2026-07-22 (same family as the known `kscreen-doctor` SIGABRTs). They do not crash today, but a crashing applier is a second way this heal can silently fail — which is why the script now verifies the end state rather than trusting the exit code.
- Date Found: 2026-07-26 · Date Fixed: 2026-07-26

### BUG-089 — `luminos-notes.sh` silently discarded any note containing an apostrophe, while printing "Note added"
<!-- [CHANGE: claude-code | 2026-07-26] -->
- Status: **FIXED**
- Severity: HIGH (silent, ongoing loss of the project knowledge base)
- Component: `scripts/luminos-notes.sh`
- Root Cause: `add` and `search` interpolated their arguments straight into the SQL string —
  `sqlite3 "$DB" "INSERT INTO notes (tag, note) VALUES ('$TAG', '$NOTE');"`. Any `'` in the text
  ("KDE's", "don't", "user's") terminated the string literal and sqlite3 failed with a parse error.
  **`echo "Note added to $TAG."` then ran unconditionally**, so the failure looked like a success.
  Also a plain SQL-injection shape, in a script run with arbitrary text every task.
- Impact: AGENTS.md §13 makes `luminos-notes.sh add` mandatory after **every** task, so every summary
  containing an apostrophe was lost — silently, since 2026-04-26. Found by accident: the BUG-088
  note above was written, reported added, and was not in the DB when searched back.
- Fix: `sql_quote()` doubles single quotes (SQL's own escape) for tag, note and search term; `add`
  now tests sqlite3's exit status and fails loudly with a non-zero exit instead of lying.
- Verification: `add TESTTAG "KDE's auto-switcher won't survive a lock"` → stored and retrievable by
  `search`; previously this produced a parse error and an empty table with a success message. The
  three real notes for this session were re-added and confirmed present.
- Related: same failure shape as BUG-088 root cause 3 — an unconditional success message on a path
  that can fail. Worth grepping other `scripts/` helpers for `echo "…done"` after an unchecked command.
- Also affected: `luminos-brain log` printed `Action logged to Brain and Notes.` past the identical
  SQL error. Not fixed here (separate tool, outside this repo); re-log without apostrophes until it is.
- Date Found: 2026-07-26 · Date Fixed: 2026-07-26

### BUG-090 — GTK apps left on Breeze icons after a Global-Theme reset; Yaru's fallback chain pointed at an uninstalled theme
- Status: ✅ FIXED
- Severity: Low (cosmetic, but it is what made the desktop look "half Ubuntu")
- Reported as: "still icons are not of yaru", "why do i have 2 different icons for folder",
  "the dock is using old icons".
- **First, what was NOT broken.** The Qt/KDE side was already fully Yaru. Proven by cropping a
  fresh Dolphin window at native resolution and diffing against the theme files: `go`,
  `Documents` and the `.md` file icons are pixel-identical to
  `/usr/share/icons/Yaru/256x256/{places/folder.png, places/folder-documents.png,
  mimetypes/text-markdown.png}`. The "two different folder icons" is Dolphin's
  `directorythumbnail` preview plugin compositing content thumbnails onto the *same* Yaru
  folder — a preview feature, not a second icon theme. Turn it off in
  Configure Dolphin → Interface → Previews → uncheck *Folders*.
- Root cause 1 — **GTK was never re-synced.** `~/.config/gtk-{3,4}.0/settings.ini` and
  `gsettings org.gnome.desktop.interface` still read `icon-theme=breeze-dark` and
  `cursor-theme=breeze_cursors` while `gtk-theme-name` was already `Yaru`. A Look-and-Feel
  apply (BUG-088) rewrites the GTK files through the `kde-gtk-config` `gtkconfig` kded
  module, and `luminos-ubuntu-persist` only ever re-affirmed the *Qt* keys — so GTK stayed
  broken permanently once reset. `plasma-changeicons Yaru` exits 0 but does **not** push the
  change into the GTK files, so it cannot be relied on for this.
- Root cause 2 — **the fallback chain named a theme that is not installed.**
  `Inherits=Humanity,Papirus,breeze,hicolor`; Humanity is not packaged for Arch. Every icon
  miss logged `Icon theme "Humanity" not found` — **58 times in one day**. Now
  `Inherits=Papirus,breeze,hicolor`; the log line is gone.
- Root cause 3 — **`kwriteconfig6` mangled the theme index.** It rewrites a file with its
  groups sorted, which pushed `[Icon Theme]` from line 1 to **line 651 of 789**. The
  freedesktop Icon Theme spec requires `[Icon Theme]` to be the first group. Replaced with
  `scripts/luminos-icon-inherits.py`, which edits `Inherits=` in place and keeps the group
  order. Both `Yaru` and `Yaru-dark` are back to `[Icon Theme]` at line 1.
- Not a defect — **the dock's launcher icons come from Papirus and always will.** Yaru is a
  GNOME/Ubuntu theme and ships no `org.kde.dolphin`, `org.kde.konsole`, `firefox` or
  `google-chrome`; breeze has none of those four either. `kiconfinder6` resolves all of them
  to `/usr/share/icons/Papirus/32x32/apps/`. Papirus was the *previous* Luminos icon theme,
  which is why they read as "old icons". The only way to change this is to pick a different
  fallback theme, not to fix Yaru.
- Conflicting setting (AGENTS.md Rule 11): `~/.config/kdedefaults/kdeglobals` (written by the
  Look-and-Feel package, and on `XDG_CONFIG_DIRS`) carried `[Icons] Theme=breeze-dark`. The
  user file outranks it, but it is a live disagreement, so it is now aligned to `Yaru` and
  `luminos-ubuntu-persist` keeps it aligned. Backup: `kdeglobals.bak-yaru-20260726`.
- Fix / survival:
  - `scripts/luminos-ubuntu-persist` now re-affirms GTK icon/cursor/theme in gtk-3.0, gtk-4.0
    and gsettings, aligns `kdedefaults/kdeglobals`, and its final verdict checks the GTK keys
    too — so it can no longer print OK while GTK is on Breeze.
  - `scripts/luminos-icon-inherits.py` (new) + `config/pacman-hooks/luminos-yaru-icons.hook`
    (installed to `/etc/pacman.d/hooks/`) restore the chain after every `yaru-icon-theme`
    upgrade, which previously reverted it silently.
- Verification: positive run prints OK; **negative test 1** — set both GTK files back to
  `breeze-dark`, re-ran, healed to `Yaru`; **negative test 2** — `chattr +i` on
  `gtk-4.0/settings.ini` so the heal cannot succeed → script printed
  `FAILED — … gtk4='breeze-dark'` and exited 1; **negative test 3** — restored the shipped
  `Inherits=Humanity,hicolor` and ran the hook's `Exec` → repaired, `[Icon Theme]` at line 1.
- Date Found: 2026-07-26 · Date Fixed: 2026-07-26

### BUG-092 — SDDM login screen renders black; a healthy logout was mistaken for a Hyprland crash
<!-- [CHANGE: claude-code | 2026-08-04] Renumbered 091 → 092. It was first filed as BUG-091, which
     collided with the existing suspend bug at line 157. This is the newer of the two, so it moved. -->
- Status: ✅ FIXED
- Severity: Low technically, HIGH in consequence — it produced a false crash report and a reboot,
  and it stalled Phase 3 of the Hyprland work.
- Reported as: "hey the thing is crashing i only see black screen after log out so i rebooted"
- **Hyprland was not involved.** SDDM's own log shows what it was told to start every time:

      15:19:59  Session ".../plasma.desktop" selected, command: ... for VT 3
      15:21:50  Session ".../plasma.desktop" selected, command: ... for VT 4

  The greeter *had* read both Hyprland entries at 15:19:53, so they are installed and valid — the
  session picker was simply never moved off Plasma. It was a Plasma → Plasma logout/login.
- Root cause 1 — **the greeter had no wallpaper, so it painted black.**
  `/usr/share/sddm/themes/breeze/theme.conf.user` contained
  `background=/home/shawn/luminos-wallpaper-tests/sample.jpg`. That file does not exist; the
  greeter logged `QML QQuickImage: Cannot open: file:///home/shawn/...` twice per start and fell
  back to a black background.
- Root cause 2 — **the path was unreachable regardless of the missing file.** The greeter runs as
  user `sddm` (uid 966), which has no read access to `/home/shawn`. Any wallpaper under `$HOME`
  is unusable here. This is the real lesson: it was never going to work, even unbroken.
- Contributing — **Plasma itself took 30 s of black screen to start**: greeter exited 15:20:01,
  `kwin_wayland` did not start until 15:20:31. Combined with root cause 1, the user saw black,
  then more black, then a desktop, and reasonably concluded something had crashed.
- Fix: `theme.conf.user` now points at the package-owned
  `/usr/share/wallpapers/Next/contents/images/5120x2880.png`. Old file preserved as
  `theme.conf.user.bak-2026-08-04`.
- Verified, not assumed: `sudo -u sddm test -r <path>` → readable **as the greeter's own user**,
  which is the check that root cause 2 shows actually matters. Confirming the file merely exists
  would have reproduced the original mistake.
- **Generalised lesson — belongs with the silent-failure family (BUG-088 / BUG-089).** On this
  machine a black screen is the normal appearance of at least three healthy states: the SDDM
  greeter with a broken wallpaper, the gap between greeter exit and compositor start, and a bare
  Hyprland with no bar or wallpaper. *Black is not evidence of a crash.* Before diagnosing any
  "session crashed", first ask what the display manager says it launched:

      journalctl -b -1 --no-pager | grep "selected, command:"

- Follow-on hardening: `exec-once = kitty` added to `~/.config/hypr/hyprland.conf` so a live
  Hyprland session is visually unmistakable rather than an empty dark screen.
- Date Found: 2026-08-04 · Date Fixed: 2026-08-04

### BUG-093 — pacman and Python disagreed about an installed version, and it silently broke every AUR python build
<!-- [CHANGE: claude-code | 2026-08-04] -->
- Status: ✅ FIXED (worked around; nothing was removed)
- Severity: Medium — it blocked the Caelestia install outright, and the error message pointed
  nowhere near the actual cause.
- Component: `~/.local/lib/python3.14/site-packages` (user-site) vs `/usr/lib/python3.14/site-packages`
- Symptom: `yay -S caelestia-cli` failed in `build()` with:

      ERROR Missing dependencies:
          hatch-vcs -> setuptools-scm>=8.2.0 -> vcs-versioning<3,>=2.0.0.dev0 -> packaging>=26.2

- **The false trail (recorded because it is convincing and wrong).** The obvious reading is a
  missing makedep, so `python-hatch-vcs` and `python-vcs-versioning` were installed from `extra`.
  **The build failed again with the byte-identical error.** The PKGBUILD had in fact declared
  `python-hatch-vcs` in `makedepends` all along — the dependency was never missing.

- **Root cause — two answers to "what version is installed", both true:**

      pacman -Q python-packaging                          # 26.2-1
      python3 -c "import importlib.metadata as m; print(m.version('packaging'))"   # 26.0

  There is a **user-site copy** at `~/.local/lib/python3.14/site-packages/packaging-26.0.dist-info`
  that shadows the pacman-owned 26.2 in `/usr/lib`. User-site precedes system site-packages on
  `sys.path`. The PKGBUILD builds with `python -m build --wheel --no-isolation`, and `--no-isolation`
  means the backend resolves against **`importlib.metadata`**, not against pacman. So Python
  correctly saw 26.0, and `packaging>=26.2` genuinely was not satisfied. Both tools were telling
  the truth about different files.

- Fix — disable user-site for the build only:

      PYTHONNOUSERSITE=1 yay -S caelestia-cli

- **What NOT to do:** do not `rm` the user-site `packaging`, and do not `pip install -U` over it.
  That tree has 301 entries and is load-bearing — `mempalace`, `code_review_graph`, `chromadb`,
  `llama_cpp`, `PyQt6`, `onnxruntime` all live there. "Fixing" the version conflict by deleting
  the shadowing copy would break the MCP tooling (BUG-085/087 territory) to fix a one-off build.
  `PYTHONNOUSERSITE=1` is scoped to the single command and touches nothing.

- **Generalised lesson — this will recur for any python AUR package on this machine.** A pacman
  version number is a claim about `/usr`. It says nothing about what an interpreter will import.
  When a build complains about a version constraint that pacman insists is satisfied, compare the
  two views before believing either:

      python3                  -c "import importlib.metadata as m; print(m.version('X'))"
      PYTHONNOUSERSITE=1 python3 -c "import importlib.metadata as m; print(m.version('X'))"

  Different answers = a shadowing user-site install. Also useful: `python3 -c "import X; print(X.__file__)"`
  shows which copy actually wins.

  This belongs to the same family as BUG-088/089 — a tool reporting success (or here, reporting a
  version) for a path that is not the one in effect.

### BUG-094 — Hyprland session bounced straight back to the login screen: the GPU pin was written in a format aquamarine parses as a list
<!-- [CHANGE: claude-code | 2026-08-04] -->
- Status: ✅ **FIXED AND VERIFIED ON A REAL LOGIN (2026-08-04 16:32).** Not "awaiting retry" — the
  user logged in and is using the session. Live evidence: `AQ_DRM_DEVICES=/dev/dri/luminos-igpu` in
  the compositor's own `/proc/<pid>/environ`, `XDG_CURRENT_DESKTOP=Hyprland`, panel up at
  2880x1800@120, dGPU `0000:01:00.0` `runtime_status = suspended`, and Claude Desktop's GPU process
  on `--render-node-override=/dev/dri/renderD129` — the **AMD** node. The pin works, the 0 W gating
  survived, and the project's hard acceptance criterion is met.
- Severity: **HIGH** — the Hyprland session was 100% unusable. Every attempt died in ~2 s.
- Component: `AQ_DRM_DEVICES` in `~/.config/hypr/hyprland.conf` and `~/.config/uwsm/env-hyprland`.
  **Now lives in `~/.config/caelestia/hypr-user.lua`** — `hyprland.conf` was superseded by the
  stock Caelestia Lua config (DECISION 41). The `uwsm/env-hyprland` copy is unchanged and is the
  one that actually wins on a uwsm login.
- Reported as: *"i select the Hyprland (uwsm-managed) enter password it shows black screen and than we are back to login screen"*
- **This one was real.** Unlike BUG-092, SDDM confirms Hyprland genuinely ran — three attempts,
  two via uwsm and one plain, each `SIGABRT` within ~2 seconds:

      sddm[891]: Session ".../hyprland-uwsm.desktop" selected, command: "uwsm start -e -D Hyprland hyprland.desktop"
      uwsm_hyprland.desktop[98645]: terminate called after throwing an instance of 'std::runtime_error'
      uwsm_hyprland.desktop[98645]:   what():  CBackend::create() failed!
      systemd-coredump[98672]: Process 98645 (Hyprland) ... signal 6/ABRT

- **Root cause — the pin was correct in intent and unparseable in form.** From Hyprland's own log:

      drm: Enumerated device .../0000:01:00.0/drm/card1        <- NVIDIA, seen
      drm: Enumerated device .../0000:65:00.0/drm/card2        <- AMD, seen, "supports kms"
      drm: Explicit device list /dev/dri/by-path/pci-0000:65:00.0-card
      ERR drm: Failed to canonicalize path /dev/dri/by-path/pci-0000
      ERR drm: Failed to canonicalize path 65
      ERR drm: Failed to canonicalize path 00.0-card
      ERR drm: Explicit device /dev/dri/by-path/pci-0000 not found
      ERR drm: Explicit device 65 not found
      ERR drm: Explicit device 00.0-card not found
      ERR drm: Found no gpus to use, cannot continue
      ERR DRM Backend failed

  **`AQ_DRM_DEVICES` is a COLON-SEPARATED LIST**, and a PCI by-path name is full of colons. One
  device path was split into three nonexistent ones. aquamarine had *already enumerated the right
  card* and confirmed it supports KMS — then discarded it because the filter matched nothing, found
  no usable GPU, and aborted. Note the split is not inferred: one input produced exactly three
  errors, cut at exactly the two colons.

- **The irony worth remembering:** the by-path form was chosen *deliberately over* `/dev/dri/card2`,
  and the config carried a comment explaining that card numbers are enumeration order and unstable.
  That reasoning is correct — the NVIDIA dGPU really does enumerate first here as `card1`. The
  mistake was assuming the more-correct-looking identifier was also a *legal value for this
  variable*. **Neither stock name works: `by-path` is stable but has colons; `cardN` is colon-free
  but unstable.**

- Fix — create a name that is both, via udev, matched on the PCI address:

      # /etc/udev/rules.d/99-luminos-gpu-alias.rules
      SUBSYSTEM=="drm", KERNEL=="card*", ENV{ID_PATH}=="pci-0000:65:00.0", SYMLINK+="dri/luminos-igpu"

  then `AQ_DRM_DEVICES=/dev/dri/luminos-igpu` in both `hyprland.conf` and `uwsm/env-hyprland`.
  Verified: `/dev/dri/luminos-igpu -> card2`, vendor `0x1002` (AMD), zero colons.
  `env-hyprland` also carries a `readlink -f` fallback for the case where the udev rule goes
  missing — negative-tested by pointing it at a nonexistent alias, which correctly yielded the
  colon-free `/dev/dri/card2`.

- **Generalised lesson:** when an env var takes a *path*, find out whether it takes a **list**
  before choosing the prettiest path form. Separators (`:` for paths, `,` for lists) silently
  turn one valid value into several invalid ones. The tell is in the error text — three errors
  from one input, split at the separator.

- **Also worth knowing:** aquamarine enumerates **every** DRM device before applying
  `AQ_DRM_DEVICES`, so the NVIDIA card is opened briefly at every Hyprland start regardless of
  pinning. That is what produced `NVRM: nvAssertFailedNoLog ... kernel_gsp.c:1447` in the journal.
  It is a side effect of enumeration, **not** evidence that the compositor landed on the dGPU.
  Judge that with `hyprctl systeminfo` and the dGPU `runtime_status`, never by the presence of an
  NVRM line.

---

## BUG-095 — one keystroke deletes the whole desktop, and nothing brings it back
**[CHANGE: claude-code | 2026-08-04] — FIXED**

**Symptom.** Shawn: *"the left side pannel and notification and other thigns are gone"*. Hyprland
itself was fine (pid 1532, windows still tiling). What was gone was **Quickshell** — and under
Caelestia that single process is the bar, the launcher, the notification daemon, the lock screen
and the wallpaper. Losing it looks like losing the desktop.

**Diagnosis — how we know it was killed, not crashed.** `/run/user/1000/quickshell/by-id/ra1vok9jt/`
(the login instance, started 17:22) ends at 18:01 with nothing but routine warnings — missing
`~/.face`, null-property TypeErrors in `Notification.qml`. **No fatal, no stack, no coredump.** A
log that simply stops mid-life is the signature of a signal, not a fault.

**Cause.** Stock Caelestia, `~/.config/hypr/hyprland/keybinds.lua:68`:

    create_bind("CTRL + SUPER + SHIFT + R", hl.dsp.exec_cmd("qs -c caelestia kill"), release)

Kill with **no restart** — and it sits one finger from `CTRL+SUPER+ALT+R` on line 69, which *does*
restart. Upstream this is a Quickshell-developer bind. On a daily-driver desktop it is a trapdoor:
after pressing it there is no bar and no launcher left *with which to fix it*.

**Fix.** `/usr/local/bin/luminos-shell-guard` + a second bind on the same combo in
`~/.config/caelestia/hypr-user.lua`. The stock bind could not be removed — **the `hl` Lua API has
no `unbind`** (`/usr/share/hypr/stubs/hl.meta.lua`), and a second `hl.bind` on the same combo
*stacks* rather than replaces (`hyprctl binds` shows two entries at `modmask=69 key=R`, both fire).
So the override is a **guard**, not a restart: stock kills at t≈0, the guard runs at t≈0.6s and
starts the shell *only if nothing is running*. Healthy shell ⇒ no-op, so it is safe to run anytime.

**Two traps that made every short version of this silently wrong:**

1. **`pgrep -f` self-matches.** `pgrep -f "qs -c caelestia"` matches *any* command line containing
   that string — its own, and the shell that invoked it. It twice reported a **dead** shell as
   alive and produced a **passing test for a broken guard**. The `[q]s` bracket trick fixes the
   self-match but *not* the invoker-match: a wrapper whose cmdline held `qs -c caelestia kill`
   still matched. Detection now uses `pgrep -x qs` (process **name**) and only then reads that
   pid's `/proc/PID/cmdline`.

2. **`caelestia shell -d` does not reliably start the shell from a detached context.** Killed the
   shell, ran it exactly as bound, got nothing — no process, no layers. `setsid qs -c caelestia`
   works every time and is what the guard uses. Note `caelestia shell` with *no* flag is not a
   start at all: it sends an empty IPC message and exits 0, which looks like success.

**Proved, not asserted.** Killed the shell (`pgrep -x qs` empty, `hyprctl layers | grep -c
caelestia-` = **0**), ran the guard, got `restarted Caelestia shell (pid 16801)` and **6** layers
back. Re-run with the shell healthy: `shell already running — nothing to do`.

**A third trap, in the test harness rather than the product:** `hyprctl dispatch exec '<cmd>'` is
parsed as **Lua** on this build — it returned ``[string "return hl.dispatch(exec sh -c ..."]:1: ')'
expected near 'sh'`` and did nothing. Two "tests" that appeared to show the bind was harmless had
in fact never run the command. Same family as the known `hyprctl keyword` gotcha: **under the Lua
config, `hyprctl` subcommands take Lua, and the classic string form fails without changing state.**

**Related, same session:** the `Luminos Look` tuner (`FloatingWindow`, `qs -p`) had no titlebar
under Hyprland, no close button, no Escape handler — Shawn: *"I CAN'T REMOVE THE THINGS THATS BEEN
FLOATINIG RIGHT IN CENTRE"*. The only exits were `SUPER+SHIFT+T` (which you had to already know)
or killing the pid. Added a `Shortcut` for **Escape / Ctrl+W** and a visible **✕** in the header.
Lesson: a window with no server-side decoration must ship its own way out.

---

## BUG-096 — the HIVE popup toggle killed the wrong process, so the window could not be closed
**[CHANGE: claude-code | 2026-08-04] — FIXED**

**Symptom.** `SUPER+SPACE` opened the HIVE chat window. Pressing it again did nothing visible —
the window stayed on screen. Pressing a third time opened a **second** window on top of the first.

**Cause.** `luminos-hive-popup` claimed its toggle lock with `echo $$ > "$LOCKFILE"` — the pid of
the **bash wrapper** — and then ran `qml6` in the foreground as a child. The comment above that
line even explained the choice: *"Run qml6 in foreground (NOT exec) so this bash process stays
alive to manage the keep-alive loop and lockfile."* That reasoning is sound for cleanup and wrong
for the toggle. The second press did `kill -TERM` on the pid in the lockfile, which killed bash;
bash's `EXIT` trap then removed the lockfile; and `qml6` — which is the process that actually owns
the window — was never signalled and carried on as an orphan. With the lockfile now gone, the next
press saw no lock and launched a fresh window.

Measured on 2026-08-04: lockfile contained `56165`, the mapped window belonged to pid `56174`.

**Fix.** Publish the pid of the thing that owns the window. `qml6` is started in the background,
its pid is written over the lockfile, and the wrapper `wait`s on it — so the wrapper still lives
long enough to run the keep-alive loop and cleanup, but the toggle now signals the window. The
`EXIT` trap also kills `$QML_PID`, so the reverse failure (someone TERMs the wrapper) cannot strand
a visible window either. Proved with four consecutive presses: open → close → open → close, window
count `1 → 0 → 1 → 0`, with the lockfile resolving to `/usr/bin/qml6 .../HiveChat.qml` throughout.

**General shape.** *A toggle must hold the pid of the process that owns the resource, not the pid of
the script that started it.* Any wrapper-plus-child launcher has this bug latent in it.

**Two other things fixed in the same script, both found by enabling `luminos-hive.service`:**

1. The `EXIT` trap ran `pkill -f 'hive-daemon.py'`. That was harmless while the popup owned the
   daemon, but the daemon is a **systemd user unit** now — so closing one chat window would have
   torn down a service behind systemd's back and left the backend dead for every other client.
   Removed. The popup also no longer forks its own daemon; it asks `systemctl --user start` and
   waits for `127.0.0.1:8078` to listen. Two daemons would have raced for the port anyway, and the
   loser dies with `EADDRINUSE`.
2. The `WAYLAND_DISPLAY` fallback looped over a hardcoded `wayland-0 wayland-1`. The Hyprland
   session came up on **`wayland-1`**, so this happened to work — but it is one socket away from a
   silent failure. It now globs `"$XDG_RUNTIME_DIR"/wayland-*` and takes the first real socket.

**Also note the launcher had simply drifted.** `/usr/local/bin/luminos-hive-popup` was still the
PyQt6 + `QWebEngineView` version from 2026-05-08, while `scripts/luminos-hive-popup` in the repo
had already been rewritten to use `qml6`. CLAUDE.md documented the qml6 behaviour, so the installed
copy was the odd one out. Measured cost of the drift:

| HIVE UI | processes | RSS |
|---|---|---|
| `qml6 src/hive/HiveChat.qml` | 1 | **265 MB** |
| `hive-popup-app.py` (PyQt6 + QWebEngine) | 5 | **604 MB** |

`QWebEngineView` embeds an entire Chromium to render local HTML, and it resolved PyQt6 out of
`~/.local/lib/python3.14/site-packages` — the user-site path that shadows pacman (BUG-093).
`HiveChat.qml` imports only QtQuick / QtQuick.Controls / QtQuick.Layouts / QtQuick.LocalStorage —
zero Plasma, zero KDE — so it reuses the Qt6 libraries Quickshell already keeps resident.
**Lesson: `/usr/local/bin` copies drift from the repo silently. Install, then `diff -q` to verify.**

---

## BUG-097 — llama-server cannot start: its CUDA build was replaced by a CPU-only one
**[CHANGE: claude-code | 2026-08-04] — OPEN, needs a decision**

**Symptom.** Opening the HIVE popup logs `[LAUNCHER] llama-server not running, starting...` and
then nothing happens. `/tmp/hive-server.log` fills with:

```
/usr/local/bin/llama-server: error while loading shared libraries: libllama-common.so.0: cannot open shared object file
```

The dGPU stays `suspended`, `hive-daemon.py` reports `{"model": null, "ready": false}`, and no
model ever loads. **HIVE answers nothing.**

**This is not a Hyprland regression.** The UI, the keybind and the daemon all work; the inference
backend underneath them is what is broken, and it has been for months.

**Cause.** `/usr/local/bin/llama-server` (built 2026-04-24) has **seven** `DT_NEEDED` entries that
nothing on the library path resolves — `ldd` reports all seven `not found`:

```
libllama-common.so.0  libmtmd.so.0  libllama.so.0
libggml.so.0  libggml-cpu.so.0  libggml-cuda.so.0  libggml-base.so.0
```

They are not in `/usr/local/lib` (which holds only `default.sfx` and `rarfiles.lst`), `ldconfig -p`
has never heard of them, and no pacman package owns the binary. They exist in **two** places on
disk, and **neither set is complete for this binary**:

| location | ggml version | `libllama-common.so.0` | `libggml-cuda.so.0` |
|---|---|---|---|
| `src/hive/.venv/lib/python3.12/site-packages/lib` (2026-05-09) | **0.10.2** | present | **missing** |
| `~/.pyenv/versions/3.12.13/lib/python3.12/site-packages/lib` | **0.9.11** | **missing** | present |

So the venv was refreshed on 2026-05-09 to a **newer, CPU-only** llama.cpp (0.10.2, no CUDA
backend), and the CUDA-enabled 0.10.2 build the April binary was linked against no longer exists
anywhere — including inside the Timeshift snapshots from 2026-07-21 and 2026-08-04, both of which
have an empty `/usr/local/lib`. Pointing `LD_LIBRARY_PATH` at the venv gets six of seven libs and
still dies on `libggml-cuda.so.0`. **Mixing the two directories is not a fix** — 0.9.11 and 0.10.2
are different ABIs, and `libggml-cuda` is the one library that must match `libggml-base` exactly.

Because `libggml-cuda.so.0` is a hard `DT_NEEDED` and not a `dlopen`ed backend, this binary cannot
even fall back to CPU. It refuses to start at all.

**Two ways out — Shawn's call:**

1. **Rebuild llama.cpp with CUDA** and install the libraries to a path that survives, e.g.
   `/usr/local/lib` plus an `/etc/ld.so.conf.d` entry so `ldconfig` resolves them without
   `LD_LIBRARY_PATH`. Keeps the TurboQuant llama.cpp architecture that CLAUDE.md specifies. Costs a
   CUDA compile, and the sources are already vendored under `research/turboquant/`.
2. **Serve through `llama_cpp.server`** — `~/.pyenv/versions/3.12.13` has `llama_cpp` **0.3.20**
   with its CUDA libs intact, and `python -m llama_cpp.server` exposes exactly the
   `/v1/chat/completions` endpoint on `:8080` that `hive-daemon.py` already calls. No compile.
   But it is a different process model from `hive-start-model.sh`, so the swap/idle logic in
   `hive-daemon.py` would need adapting.

**Lesson.** The libraries a hand-built `/usr/local/bin` binary needs must be installed somewhere
`ldconfig` looks. Leaving them inside a **venv** means the next `pip install` can silently swap them
for a differently-configured build, and the binary that depends on them breaks with no package
manager, no version pin, and no warning.

## BUG-098 — Qt/KDE apps keep the old palette under Hyprland; `plasma-apply-colorscheme` no-ops on name
**[CHANGE: claude-code | 2026-08-05] — FIXED**

**Symptom.** Under Hyprland + Caelestia, the shell is dark Material You but Dolphin and System
Settings still render the light Ubuntu/Yaru palette with orange accents, and GTK apps are light too.

**Cause — three unplugged wires, not one.** Caelestia *does* generate a palette for every toolkit:

| toolkit | Caelestia writes | why it was ignored |
|---|---|---|
| GTK | `~/.config/gtk-{3,4}.0/gtk.css` (correct dark values) | `settings.ini` still said `gtk-theme-name=Yaru` + `prefer-dark-theme=false`. Yaru is a complete stylesheet that hardcodes its own colours and never reads Caelestia's variables |
| Qt/KDE | `~/.config/qtengine/caelestia.colors` (a valid KDE scheme) | targets **`qtengine`, which is not installed here**. We run `QT_QPA_PLATFORMTHEME=kde`, which reads `kdeglobals` — a file Caelestia never touches |
| icons | nothing | `Theme=Yaru` in `kdeglobals` drew the orange folders |

Also note `~/.config/gtk-3.0/colors.css` only defines `*_breeze` names and is generated by
kde-gtk-config's **kded module, which does not run under Hyprland** — so it is frozen at whatever
light values existed when Plasma last ran. Only the `Breeze` GTK theme consumes those names.

**The trap.** The obvious fix — `plasma-apply-colorscheme Caelestia` — *appears* to work:

```
$ plasma-apply-colorscheme Caelestia
Successfully applied the color scheme Caelestia to your current Plasma session   # exit 0
```

There is no Plasma session. Worse, once `ColorScheme=Caelestia` is already in `kdeglobals` it
short-circuits on the **name** and writes nothing at all:

```
$ plasma-apply-colorscheme Caelestia
The requested theme "Caelestia" is already set as the theme ...   # exit 0, colours untouched
```

Caelestia always regenerates under the same name, so this tool no-ops on *every run that matters*
and still exits 0. Proven 2026-08-05 by setting `BackgroundNormal=#ff0000` and watching it survive.
This is the write-side twin of the existing rule **never verify a colour scheme by name**.

**Fix.**
- GTK: `gtk-theme-name=Adwaita-dark`, `gtk-application-prefer-dark-theme=true`,
  `gtk-icon-theme-name=Papirus-Dark` in both `settings.ini` files, plus matching `gsettings` keys for
  the portal. Only `settings.ini` is edited — Caelestia overwrites `gtk.css`/`colors.css`.
- Qt: `scripts/luminos-qt-theme-sync` merges the `[Colors:*]`, `[ColorEffects:*]` and `[WM]` groups
  from Caelestia's scheme straight into `kdeglobals`, leaving fonts, `widgetStyle` and icon theme
  alone. It verifies by reading the colour **value** back, never by name.
- `systemd/luminos-qt-theme-sync.path` watches `~/.config/qtengine/caelestia.colors` so a wallpaper
  or scheme change re-syncs automatically. Proven end to end: switching to gruvbox moved
  `kdeglobals` from `#201f23` to `#1c2021` with no manual step.

**Lesson.** A generator writing a file is not the same as anything reading it. When a theme "doesn't
apply", check the *consumer* exists before touching the generator — here the whole Qt palette was
being written correctly all along, to a path belonging to a package that was never installed.

---

## BUG-099 — Thunar was the one ugly window: the GTK theme it was told to use was never installed
**[CHANGE: claude-code | 2026-08-05] — FIXED**

**Symptom.** Every window matched the dark Caelestia palette except Thunar, which rendered as plain
grey stock Adwaita — and it opened at a postage-stamp size while everything around it filled the
screen. Two unrelated causes wearing one complaint.

### Half 1 — the theme

BUG-098 above set `gtk-theme-name=Adwaita-dark`. That made GTK *dark*, which is why it looked fixed,
but it did not make GTK **Caelestia-coloured**. Caelestia writes its palette into
`~/.config/gtk-3.0/gtk.css` using **libadwaita** variable names:

```
@define-color window_bg_color #131317;   @define-color headerbar_bg_color #131317;
@define-color view_bg_color   #131317;   @define-color accent_color       #c2c1ff;
```

Stock GTK3 Adwaita **does not use those names** — they are GTK4/libadwaita. So the file parsed
cleanly, reported no error, and applied almost nothing. `adw-gtk3` is precisely the theme that
backports those names to GTK3, which is why Caelestia is built around it.

And the machine was already *asking* for it — but with two sources disagreeing, and the winner
pointing at nothing:

```
$ gsettings get org.gnome.desktop.interface gtk-theme     → 'adw-gtk3-dark'   ← portal uses this
$ grep gtk-theme-name ~/.config/gtk-3.0/settings.ini      → Adwaita-dark
$ ls -d /usr/share/themes/adw-gtk3-dark                    → No such file or directory
```

A GTK theme name that does not resolve is **not an error** — GTK silently falls back to built-in
Adwaita. Nothing logs, nothing warns. Same shape as BUG-090 (Yaru's fallback chain pointing at an
uninstalled theme): *the config was right and the package was missing.*

**Fix.** `pacman -S adw-gtk-theme` (official **extra** repo, 0.12 MiB — not AUR), then name it in
`settings.ini` so both sources agree. Verified by asking a real GTK client what it resolved, not by
reading the config back:

```
$ python3 -c "import gi;gi.require_version('Gtk','3.0');from gi.repository import Gtk;
              print(Gtk.Settings.get_default().get_property('gtk-theme-name'))"
adw-gtk3-dark
```
…and then by screenshotting the window with `grim` and looking at it.

> **Do NOT "fix" this by installing `qtengine`.** The header of `scripts/luminos-qt-theme-sync` says
> qtengine is not installed, which invites exactly that. qtengine is the **Qt** side and is already
> solved via `kdeglobals` (BUG-098); it is not in the official repos; and per `hypr-user.lua:85` it
> would seize Qt styling from KDE. Thunar is **GTK**. Different toolkit, different bug.

### Half 2 — the size

Measured, not eyeballed: `hyprctl clients -j` → Thunar `640x480` on a `1440x900` logical desktop,
next to Claude at `1348x858`. `640x480` is Thunar's compiled-in fallback, used because it has never
saved a size:

```
$ xfconf-query -c thunar -l
/last-icon-view-zoom-level  /last-separator-position  /last-view  /last-window-maximized
```

No `/last-window-width`, no `/last-window-height`. Thunar only writes those when closed
*un-maximized*, so it can stay in that state forever. The float-everything catch-all in
`hypr-user.lua` was **not** at fault — it sets only `float`, deliberately, so the stock sized-floater
tags keep their own dimensions. Those tags cover pavucontrol, nwg-look, GNOME Settings and file
*dialogs*, but never Thunar itself, so nothing sized it.

**Fix.** A window rule in `hypr-user.lua` setting **only** `size` + `center` (never `float`, so
`hypr-locked.conf` can still tile it), at the stock 0.6×0.7 → `864x630`. Confirmed by reading the
size back off the live window after `hyprctl reload`, because window-rule tables are not validated —
an unknown key returns ok and does nothing. Also widened `/last-separator-position` 170 → 215, which
needs a Thunar **restart**: it is read at window construction, so setting it live appears to do
nothing.

**Lesson.** "It looks ugly" and "it is too small" felt like one theming problem and were two
independent ones. Also: dark ≠ themed. A dark fallback is the most convincing way for a broken theme
to look deliberately applied.

## BUG-100 — every Hyprland plugin was dead, because hyprpm was still building for an April compositor
**[CHANGE: claude-code | 2026-08-05] — FIXED**

**Symptom.** The plugins simply were not there. No error, no notification, nothing on screen.
`hyprctl plugin list` reported **no plugins loaded**, and `hyprpm list` showed **nine plugins, all
disabled, two of them failing to build**.

### The cause is one line of state
hyprpm plugins are C++ shared objects compiled against the **exact Hyprland commit** in use, so
hyprpm records which commit it last built for:

```
# /var/cache/hyprpm/shawn/state.toml   (BEFORE)
hash = '521ece463c4a9d3d128670688a34756805a4328f_aq_0.10_hu_0.12_hg_0.5_hc_0.1_hlg_0.6'
```

`521ece46…` is Hyprland **0.54.3, April**. The compositor is **0.56.1** (`5c9377c1…`), and the
support libraries moved with it — aquamarine 0.10 → 0.14, hyprutils 0.12 → 0.14. One stale hash
produces **both** symptoms: the plugins touching changed APIs fail to compile, and none of the
rest were ever rebuilt or loaded.

```bash
hyprpm update      # pulls headers matching the RUNNING Hyprland, rebuilds every plugin
hyprpm reload
```

### Two things that made this hard to find
**1. The state is not in `$HOME`.** Upstream documents `$XDG_DATA_HOME/hyprpm`. Arch's package
uses **`/var/cache/hyprpm/$USER/`**. Every search under `~` came back empty while `hyprpm list`
cheerfully printed a repository — which reads like a phantom. Settled without guessing:

```bash
env HOME=/tmp/fakehome hyprpm list    # identical output → the state cannot be HOME-based
```

**2. `hyprpm enable` does not load anything.** It only writes the choice into `state.toml`.
Hyprland never acts on it, so even after a successful rebuild the plugins are absent again after
the next logout — silently. Fixed by adding to the `hyprland.start` handler in `hypr-user.lua`:

```lua
hl.exec_cmd("hyprpm reload -n")
```

`-n` is `--notify` — it **sends** a notification, it does not suppress one. Deliberate: a
wrong-version plugin fails to load with no visible sign, so the login toast is the only positive
confirmation. Verified by unloading both `.so`s (`hyprctl plugin list` → empty) and running that
exact command; both returned with their config intact, no root required.

### ⚠️ This bug will come back on schedule
Any `pacman -Syu` that moves Hyprland off 0.56.1 re-breaks every plugin, silently and completely.
The compositor starts fine, nothing errors, the borders and the overview just stop existing.
**If a plugin feature vanishes after an update, run `hyprpm update && hyprpm reload` before
debugging anything else.**

### Related trap, opposite shape
While proving the fix: `hyprctl dispatch 'hl.plugin.hyprexpo.expo("toggle")'` **opens the
overview and then prints `error: expected a dispatcher`.** The plugin call executes as a side
effect and returns nil, which hyprctl's own Lua wrapper rejects — the error describes hyprctl,
not the plugin. `hyprctl submap` returns `hyprexpo` and tells the truth. This is the **inverse**
of the BUG-088/089 family: a tool reporting failure for work it actually completed. Both shapes
cost the same amount of time; neither exit code can be trusted alone.

Full context and the configuration in **DECISION 49**.

---

## BUG-101 — the SUPER launcher's app list barely scrolled, because the touchpad was turned down to 30%
**[CHANGE: claude-code | 2026-08-05] — FIXED**

**Symptom.** In the Caelestia launcher (SUPER), a full two-finger swipe on the touchpad moved the
app list a hair, or looked like it did nothing at all. Mouse wheel scrolled it fine. Nothing was
logged, and the list was visibly longer than its viewport, so it read as a broken widget.

### It was never the widget
Hyprland exposes **two separate** scroll multipliers, and Caelestia sets only one of them:

```
input:scroll_factor            = 1.0    # mouse wheel     — untouched
input:touchpad:scroll_factor   = 0.3    # touchpad        — ~/.config/hypr/variables.lua:17
```

`0.3` forwards three-tenths of the distance libinput reported. On a tall page that reads as
"slow". The launcher list is deliberately **short** — its height is exactly
`Config.launcher.maxShown` rows (`modules/launcher/AppList.qml:64`) while its content is every
installed app — so 30% of one swipe travels **less than a single row**, and a list that moves less
than one row looks frozen. Two devices, two multipliers, one of them cut to a third: that is the
whole bug.

Fixed by overriding the variable, not the upstream file:

```lua
-- ~/.config/caelestia/hypr-vars.lua   (mirrored at config/caelestia/hypr-vars.lua)
touchpadScrollFactor = 1.0,
```

`hyprland.lua` merges `hypr-vars.lua` over `variables.lua` **before** `require("hyprland.input")`,
so `~/.config/hypr/` stays byte-identical to upstream and `caelestia update` never conflicts.
Hyprland auto-reloads on write; `hyprctl getoption input:touchpad:scroll_factor` → `1.000000`.

### Three dead ends, all worth writing down
**1. Reading QML and guessing is not evidence.** Two separate MouseAreas were accused of eating
the wheel event — `StateLayer`, then the full-screen `CustomMouseArea` in `Interactions.qml`. Both
were wrong. `QQuickMouseArea` only *accepts* a wheel event if an `onWheel` handler is connected
(`isWheelConnected()`), and `ContentWindow.qml:262` nests `Panels` **inside** `Interactions`, so
the list is the child and receives the wheel first regardless.

**2. `ydotool` cannot test a touchpad fix.** It creates a virtual **mouse** emitting `REL_WHEEL`,
which is governed by `input:scroll_factor` — the option that was already correct. A green wheel
test would have proved nothing about the option actually changed.

**3. `ydotool mousemove -a` takes raw panel pixels, not logical coordinates.** eDP-2 is 2880x1800
at `scale 2.0`. Asking for `746,600` landed the pointer at logical `373,300`, inside a different
window. The resulting before/after screenshots were byte-identical — which looked exactly like a
frozen list and was in fact a correctly scrolling *other* window. `hyprctl cursorpos` settles it
in one command; run it **before** believing an unchanged screenshot.

One more hazard for anyone scripting input here: `kbLauncher` is `SUPER + SUPER_L`, so any
synthetic bare `SUPER` press opens the launcher on release and it then swallows the user's typing.

---

## BUG-102 — "pick NVIDIA" gave you the iGPU, silently, for a month
**[CHANGE: claude-code | 2026-08-05] — FIXED and proven on the card**

**Symptom.** `chrome-luminos` pops a dialog asking which GPU to use. Picking **NVIDIA RTX 4050**
produced a notification saying "Running on NVIDIA RTX 4050" — and a Chrome rendering on the AMD
iGPU. No error, no log line, no crash. The lie was in the notification, which is why it survived
a month unnoticed.

There were **three** independent causes stacked on top of each other. Fixing any one alone
changed nothing, which is what made this hard to see.

### Cause 1 — the launcher never opened the gate at all
DECISION 25 made `/dev/nvidia*` default-deny (`0660 root:dgpu`, and user `shawn` is deliberately
not in `dgpu`). The sibling launcher `luminos-gpu-launch` was updated on 2026-07-03 to route the
NVIDIA choice through `dgpu-exec`. `chrome-luminos` was written in May and **was never brought in
line** — its NVIDIA branch just set env vars and exec'd Chrome.

The trap that hides this: `/dev/dri/renderD128` (the NVIDIA **DRM render node**) is `0666` and
opens fine, so it looks like access works. It buys nothing. The NVIDIA proprietary Vulkan/GLX/EGL
libraries need `/dev/nvidiactl` + `/dev/nvidia0` — the gated nodes. Proven side by side:

```
VK_ICD_FILENAMES=…/nvidia_icd.json vulkaninfo --summary
  → ERROR: Failed to detect any valid GPUs in the current configuration
…the identical command under `dgpu-exec`
  → deviceName = NVIDIA GeForce RTX 4050 Laptop GPU
```
Only **Mesa/AMD** lives entirely in DRM. Anything NVIDIA — browser, game, CUDA — needs the gated
character devices.

### Cause 2 — the gate itself was defeated by any launcher written in shell
Inserting `dgpu-exec` was necessary and **still did not work**. `dgpu-exec` (v1) relies purely on
the setgid bit, which raises only the **effective** gid and leaves the real gid at 1000. That is
fine for a direct ELF exec — `dgpu-exec nvidia-smi`, the one test anyone ever ran — and broken for
almost everything else:

1. **bash/sh reset egid → rgid at startup** as setgid protection, unless given `-p`. Chrome is
   launched through *two* bash wrappers (`/usr/bin/google-chrome-stable` →
   `/opt/google/chrome/google-chrome` → `chrome`), so the `dgpu` group was dropped at the **first**
   wrapper. This breaks the gate for **every app whose launcher is a shell script**, not just Chrome.
2. **`access(2)` consults the REAL gid** — so the shell tests `[ -r ]` / `[ -w ]` report DENIED even
   when the device opens fine. A permission check that consults the wrong identity is worse than
   no check, and it sent this investigation down a false trail once already.
3. **A setgid exec sets `AT_SECURE=1`**, and Chrome's setuid-root `chrome-sandbox` then refuses to
   start: *"Running as root without --no-sandbox is not supported."* So bypassing the wrappers and
   exec'ing the ELF directly does not rescue it either.

**Fix:** `dgpu-exec-v2` (`scripts/dgpu-gate/dgpu-exec-v2.c`) calls `setresgid(g, g, g)` before
exec, making the `dgpu` gid **real** as well as effective. Real == effective means the process is
no longer privileged, so all three problems vanish at once — bash keeps the group, `access(2)`
tells the truth, and `AT_SECURE` is not set.

```
                       rgid/egid     via bash       direct ELF
  v1 dgpu-exec         1000 / 948    DENIED         chrome-sandbox refuses
  v2 dgpu-exec-v2       948 / 948    OPEN           starts normally
  no gate              1000 / 1000   DENIED         — (gate still intact)
```

### Cause 3 — Chrome is single-instance, so the dialog was theatre
Chrome permits **one** browser process per `--user-data-dir`. A second launch does not start a
browser: it hands the URLs to the running process over `SingletonSocket` and exits, **discarding
every command-line flag**, GPU flags included. So showing a GPU picker while Chrome is already
running is a lie — whatever you pick, you get the GPU the running instance already has.
The script now detects this and hands off silently instead of asking (which is also exactly what
makes `chrome-luminos <url>` work as the system link handler). **To change GPU you must close
every Chrome window first.**

### Proven, not asserted
Launched through the installed `/usr/local/bin/chrome-luminos`, then asked Chrome itself via the
DevTools `SystemInfo.getInfo` endpoint:

```
glRenderer: ANGLE (NVIDIA, Vulkan 1.4.329
            (NVIDIA GeForce RTX 4050 Laptop GPU (0x000028E1)), NVIDIA-595.71.5.0)
glVendor:   Google Inc. (NVIDIA)
```
Corroborated three more ways, at the same moment:
- GPU process credentials `Gid: 948,948,948,948`, holding **20 fds on `/dev/nvidia0`** plus
  `/dev/nvidiactl` and `/dev/nvidia-modeset`.
- Loaded `libnvidia-glcore` + `libGLX_nvidia`, with **zero** Mesa/radeon libraries.
- `nvidia-smi`'s own process table listed the Chrome PID.

And **both GPUs at once is real**: while the above ran on the RTX 4050, the everyday Chrome
(pid 131073) was simultaneously on the iGPU — its GPU process holding `/dev/dri/renderD129` and
`libvulkan_radeon.so`. Two Chromes, two GPUs, same moment. The only requirement is a **separate
`--user-data-dir`**; that, not the GPU, is what the single-instance rule is about.

### Two side findings worth keeping
- **`--remote-debugging-port=9222` is dead weight now.** Current Chrome (150.0.7871.128) refuses
  DevTools on a *default* data directory — `ss -ltn` shows nothing listening on 9222 even though
  the running browser carries the flag. It only prints a confusing error on every fresh launch.
  Left in place for now, flagged for removal.
- **The single-instance guard must resolve the profile the way Chrome does**, i.e.
  `${XDG_CONFIG_HOME:-$HOME/.config}`, not a hardcoded `$HOME/.config`. Your login session does not
  set `XDG_CONFIG_HOME` so the two agree there, but they diverge under any shell that does — and
  then the guard watches a lock file Chrome never writes. Fixed.

### Scope
`dgpu-exec-v2` is installed **alongside** v1 and wired into `chrome-luminos` only. Everything else,
including `luminos-gpu-launch`, still calls v1 — and therefore still has Cause 2 whenever the app
it launches is a shell script. Chrome first, the rest once they are re-verified. See DECISION 52.

**Revert:** `/usr/local/bin/chrome-luminos.bak-bug102-20260805`

---

## BUG-103 — the dGPU never goes back to sleep after you use it
# [CHANGE: claude-code | 2026-08-05]
**Status:** FIXED 2026-08-05 — all three `echo "on"` lines deleted, tested end to end on the card
**Severity:** Low-impact, always-on — 1.63 W burned continuously for nothing
**Found:** 2026-08-05, while auditing the gate for BUG-102

### The symptom
Hours after the last NVIDIA Chrome was closed and killed, with **zero processes holding any
`/dev/nvidia*` file descriptor**, the card was still awake:

```
/sys/bus/pci/devices/0000:01:00.0/power/control        = on
/sys/bus/pci/devices/0000:01:00.0/power/runtime_status = active
nvidia-smi: 1.63 W, 2 MiB, P8, 55 °C
```

P8 with 2 MiB allocated is an *idle* card — nothing is using it. It is simply not allowed to sleep.

### The cause
Every GPU launcher writes `on` to `power/control` to force the card up before launch, and **nothing,
anywhere in the tree, ever writes `auto` back.** Confirmed by grep — these are all the writers:

| File | Line | Writes |
|---|---|---|
| `/usr/local/bin/chrome-luminos` | 174 | `echo "on" > …/power/control` |
| `/usr/local/bin/luminos-gpu-launch` | 76 | `echo "on" > …/power/control` |
| `/usr/local/bin/luminos-wine-launcher` | 40 | `echo "on" > …/power/control` |

and the only readers — `luminos-verify:74` and `luminos-session-recorder:144` — never write.

`power/control=on` doesn't merely wake the card, it **disables runtime power management for the
device entirely**. So the setting outlives the app, outlives the session, and persists until
something writes `auto` or the machine reboots. Nothing does.

The structural reason nobody noticed: all three launchers end in `exec`, which replaces the shell.
There is no "after the app exits" for a trap to run in. So the wake is trivially easy to write and
the release has nowhere to live.

### Why this is a real bug and not a preference
The project's own verifier already says so. `scripts/luminos-verify:76-79`:

```sh
if [ "$ctrl" = "auto" ]; then ok "power/control=auto (runtime PM enabled)"
else bad "power/control='$ctrl' (expected 'auto' — RTD3 gating disabled; a driver update can reset this)"
```

So after any single use of the GPU picker, `luminos-verify` reports a failure — for a state our own
launcher created. `d3cold_allowed=1`, meaning the hardware *can* reach true-0 W; we are preventing it.

Counters at the time of discovery: `runtime_active_time=5198354 ms` vs
`runtime_suspended_time=49928507 ms` — 9.4 % of tracked time awake, a good chunk of which was
today's BUG-102 testing.

### Immediate mitigation (done, by hand, not in code)
```
echo auto | sudo tee /sys/bus/pci/devices/0000:01:00.0/power/control
→ control=auto  status=suspended
```

### Fix not yet applied — and why it needs a test first
The obvious fix is **stop writing `on` at all.** `auto` does not mean "keep asleep", it means "let
the kernel decide"; the NVIDIA driver takes a runtime-PM reference the moment a device node is
opened, so the card wakes on demand anyway. The `echo on` is very likely a leftover belt-and-braces
from the era of the PCIe link-training stall (see the AC/DPM P-state finding), not a live requirement.

**Do not remove it on that reasoning alone.** Test it: set `auto`, launch NVIDIA Chrome through
`chrome-luminos`, and confirm via DevTools `SystemInfo.getInfo` that `glRenderer` still reports the
RTX 4050 and the card actually woke. If it does, delete all three `echo on` lines. If it doesn't,
the release belongs in the single choke point instead — see DECISION 53, which puts wake **and**
release in one place because everything already has to pass through it.

### THE FIX — applied and proven on the card, 2026-08-05
# [CHANGE: claude-code | 2026-08-05]
The test above was run, it passed, and all three `echo "on"` lines are gone. **The card now sleeps
by itself and no release mechanism was needed at all** — which is the interesting part. `auto` does
not mean "stay asleep"; the nvidia driver takes a runtime-PM reference when a device node is opened,
so the kernel wakes the card on demand and re-suspends it when the last fd closes.

Full measured cycle, with `control=auto` the whole way through and never written by anything:

```
BEFORE  control=auto status=suspended     nvidia fd holders: 0
        ↓  LUMINOS_GPU=nvidia chrome-luminos --user-data-dir=/tmp/chrome-bug103 …
DURING  control=auto status=active        nvidia fd holders: chrome 367925
        gpu-process cmdline: --render-node-override=/dev/dri/renderD128  (the NVIDIA node)
        DevTools SystemInfo.getInfo → auxAttributes.glRenderer =
          ANGLE (NVIDIA, Vulkan 1.4.329 (NVIDIA NVIDIA GeForce RTX 4050 Laptop GPU
                 (0x000028E1)), NVIDIA-595.71.5.0)
        ↓  close Chrome
19:52:34 control=auto status=active     nvidia_fds=0
19:52:44 control=auto status=active     nvidia_fds=0
19:52:54 control=auto status=suspended  nvidia_fds=0     ← asleep on its own, ~20 s after close
19:53:04 … 19:53:25  control=auto status=suspended
```

`luminos-verify` section 3 now passes all three checks instead of failing the first:
```
[3] dGPU power gating (RTX 4050 — read-only, no nvidia-smi)
  ✓ power/control=auto (runtime PM enabled)
  ✓ runtime_status=suspended (true-0W idle achieved)
  ✓ NVreg_DynamicPowerManagement=0x02 (fine-grained)
```

So the answer to "how do we put it back to sleep when it isn't being used" turned out to be:
**stop telling it not to.** There is nothing to add — the kernel was always willing to do this, and
the one line meant to help was the only thing preventing it.

Changed (all with `[CHANGE: claude-code | 2026-08-05]` comments explaining *why*, so nobody
"restores" the wake later): `scripts/chrome-luminos`, `scripts/luminos-gpu-launch`,
`scripts/luminos-wine-launcher`; installed to `/usr/local/bin/` (previous copies backed up to
`~/.luminos-backups/launchers-bug103-20260805-195035/`).

**Two things found while testing — do not lose these:**

1. **`scripts/luminos-wine-launcher` had silently diverged from the installed copy.** The repo copy
   was newer (it has the isolated-Wine-prefix picker, 2026-07-08) but had *lost* both
   `__EGL_VENDOR_LIBRARY_FILENAMES` exports that the installed 2026-05-14 copy still had — someone
   edited an older base and committed over the top. Reconciled by hand: repo features kept, the two
   EGL lines restored, then installed. If you diff a launcher and the *repo* side looks older in one
   place, do not assume the repo wins wholesale.
2. **The Wine launcher never calls the dGPU gate at all.** It sets the NVIDIA env vars and ends in
   `exec wine …` — no `dgpu-exec`, so its NVIDIA path is denied exactly the way `chrome-luminos` was
   in BUG-102. Removing `echo on` does not make that worse (a woken card you cannot open is no more
   useful than a sleeping one), but Wine-on-NVIDIA is still broken until it is gated. Not fixed here.

Also promoted in the same pass: `luminos-gpu-launch` now calls **`dgpu-exec-v2`** instead of v1, so
every app launched through the universal picker gets the real-gid fix from BUG-102, not just Chrome.

**A trap in testing this, worth writing down:** the first NVIDIA test looked like a total failure —
the GPU process came up on `renderD129` (the iGPU) with none of the NVIDIA flags. The cause was not
the GPU at all: `chrome-luminos`'s singleton guard saw the everyday Chrome's `SingletonLock` and
took its hand-off branch, `exec google-chrome-stable "$@"`, which drops every GPU flag. That guard
keys on the **default profile's** lock even when you pass your own `--user-data-dir`, so a
throwaway-profile test is hijacked by whatever Chrome you already have open. Work around it with
`XDG_CONFIG_HOME=/tmp/somewhere` so the guard looks for the lock somewhere it isn't.
(Two smaller ones: DevTools rejects a websocket whose Origin it did not expect — use
`suppress_origin=True` or `--remote-allow-origins`; and `pkill -f 'chrome-bug103'` matches **your own
shell's command line** and kills the shell running it — write the pattern as `chrome-bug10[3]`.)

---

## BUG-104 — mempalace reported "success" and threw every memory away, for at least ten days
# [CHANGE: claude-code | 2026-08-05]
**Status:** FIXED (root-caused in ChromaDB, repaired in the palace database, verified by readback)
**Severity:** HIGH — total, silent loss of everything written to long-term memory
**Found:** 2026-08-05, only because I read back what I had just written

### The symptom
`mempalace_add_drawer` returned `{"success": true, "drawer_id": "drawer_…"}`. The write-ahead log
recorded the call. And the drawer did not exist:

```
add_drawer  -> success: true, drawer_id: drawer_luminos_os_decisions_5c38628748735ade94749871
get_drawer  -> error: "Drawer not found: drawer_luminos_os_decisions_5c38628748735ade94749871"
```

`mempalace_list_drawers` for `luminos_os/decisions` returned the same **two April drawers** it had
returned before the writes. Nothing had been added since 2026-04-18.

`~/.mempalace/wal/write_log.jsonl` shows `"result": null` on **every** `add_drawer` going back to
**2026-07-26**. The WAL redacts content, so nothing written in that window is recoverable. Every
"filed to mempalace" claimed in those sessions was false.

### Root cause — a falsy-zero bug in ChromaDB 0.6.3, triggered by a poisoned counter
MemPalace stores drawers in ChromaDB. Chroma's local write path is a log plus per-segment consumers:
`upsert()` appends to `embeddings_queue`, then notifies each segment, which applies records whose
`log_offset` is greater than the segment's stored `max_seq_id`.

`~/.mempalace/palace/chroma.sqlite3` held this:

```
max_seq_id (per segment) = 1229819390157206833      (~1.23e18, a nanosecond timestamp)
max seq_id in embeddings =             280552
embeddings_queue rows    =                  0
```

`embeddings_queue.seq_id` is `INTEGER PRIMARY KEY` with **no AUTOINCREMENT** and there is no
`sqlite_sequence` table, so an emptied queue restarts numbering at 1. Every new record therefore
arrived with an offset of 1, 2, 3 — against a stored watermark of 1.23e18. In
`chromadb/db/mixins/embeddings_queue.py::_notify_one`:

```python
if embedding["log_offset"] <= sub.start:
    continue          # silently skipped
```

Every record was discarded as "already consumed". `upsert()` raised nothing, so MemPalace's
`try/except` around it saw success and reported success. `automatically_purge` then deleted the
orphaned queue rows. The data was gone with no error at any layer.

The second half of the trap, which cost an hour: setting the watermark to `0` does **not** fix it.
`_validate_range` does

```python
start = start or self._next_seq_id()
```

and `0` is falsy, so a zeroed segment silently starts *after* everything currently in the queue —
still dropping writes. The watermark must be **truthy and below the next row id**.

### The repair
```bash
cp -a ~/.mempalace/palace/chroma.sqlite3 ~/.luminos-backups/chroma.sqlite3.bak-maxseqid-20260805-192814
# set every segment watermark to the queue's current max row id (was 4 at repair time)
UPDATE max_seq_id SET seq_id = (SELECT max(seq_id) FROM embeddings_queue);
```

This is self-sustaining afterwards: chroma's purge deletes rows strictly *below* the lowest
subscriber position, so the queue always keeps its highest row and the row-id counter never resets
again. The original reset was almost certainly a `chromadb utils vacuum` — the client still prints
*"It looks like you upgraded from a version below 0.5.6 and could benefit from vacuuming"* on every
open, and vacuuming empties the log.

**Verified after the repair** — count moved and the content read back, in a fresh process:
```
before 13575 -> upsert -> after 13576, get(['zzz_probe6']) -> ['zzz_probe6']
two more consecutive writes -> 13578, both readable
fresh process -> still readable
4 real drawers filed -> 13579, all four VERIFIED_READBACK=True
```

### The part that will bite the next agent
The **running MCP server process keeps the poisoned subscription in memory**, and
`mempalace_reconnect` does *not* rebuild segments — it only reopens the client. After repairing the
database, a drawer filed through the `mempalace_add_drawer` MCP tool still failed to read back
immediately, while the identical call through the library succeeded. **Restart the MCP server, or
file through `/home/shawn/.mempalace-venv/bin/python3 -c "import mempalace.mcp_server as m; m.tool_add_drawer(...)"`,
and always read the drawer back before believing the write.**

### The general lesson, which is the one that matters
This is the same shape as BUG-088/089 and `luminos-brain log`: **a Luminos tool printed success while
doing nothing.** Memory tooling is the worst possible place for it, because the failure erases the
evidence of itself and nobody notices for ten days. Never trust a write receipt. Read it back.
