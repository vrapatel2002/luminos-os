# Luminos OS — Bug Tracker
Last Updated: 2026-08-08 (BUG-111 FIXED — **the plugin death BUG-100 predicted came back on the first Hyprland bump, and the config error blamed the wrong file.** A login popup read `hypr-user.lua:397: unknown config key 'plugin.hyprexpo...'`, but nothing was wrong at line 397: Hyprland parses the config before plugins load, so an unloaded plugin turns its entire option namespace into unknown keys and sends you to edit Lua. hyprpm was built for 0.56.1 (`5c9377c1…`) while the compositor was 0.56.2 (`efb50993…`) — three days after DECISION 49 closed with "just run `hyprpm update` after upgrades". Now automated by `scripts/luminos-hyprpm-sync` from `hyprland.start`: compares build hash to running commit, rebuilds only on mismatch, then reads the loaded count back from `hyprctl` because `hyprpm update` prints a green `✔ Loaded` per plugin while loading none. **A pacman hook cannot do this** — hyprpm builds against the *running* compositor (so mid-transaction it would target the version being replaced) and hooks run as root (wrong `/var/cache/hyprpm/$USER`). Negative-tested all three failure paths before wiring it in. A brief error flash on the first login after an upgrade is now expected; only a popup that stays is a fault. BUG-105 FIXED — **the local LLM server was OOM-killed by long prompts, and every symptom pointed at the GPU.** `llama-cpp-python`'s server defaults `--logits_all` to True, keeping a logit vector for every prompt token: 19k tokens x 151,936 vocab x 4 B = ~11.5 GB of SYSTEM RAM on a 14 GB box. Short prompts worked, long ones died at ~30 s with a tidy `Shutting down` in the log — which is a lie; the real exit was rc=137/SIGKILL from the OOM killer, while VRAM sat at 4630 of 6141 MiB. Fixed with `--logits_all false`: peak RSS 8830 MB -> 817 MB, same request now answers in 13.4 s. Lesson: get the exit code before theorising, and don't assume the accelerator is at fault just because the workload runs on it. BUG-104 FIXED — **mempalace reported "success" and threw every memory away, for at least ten days.** `add_drawer` returned a drawer_id, the WAL logged the call, and the drawer did not exist; the WAL shows `"result": null` on every add since 2026-07-26, and content is redacted there so none of it is recoverable. Root cause is in ChromaDB 0.6.3, not MemPalace: the palace's per-segment `max_seq_id` watermark held a poisoned ~1.23e18 timestamp while `embeddings_queue` — an `INTEGER PRIMARY KEY` with no AUTOINCREMENT — had been emptied and restarted numbering at 1, so `_notify_one` skipped every record as "already consumed" and `upsert()` raised nothing. Repaired by setting each watermark to the queue's current max row id; zeroing it does NOT work, because `start = start or self._next_seq_id()` treats 0 as falsy. Verified by readback in a fresh process. **The running MCP server keeps the poisoned subscription in memory and `mempalace_reconnect` does not rebuild it** — restart the server or file through the library. BUG-103 FIXED — the dGPU never went back to sleep after you used it: all three GPU launchers wrote `on` to `power/control`, which *disables runtime PM for the device*, and nothing anywhere ever wrote `auto` back, so the card sat at 1.63 W / P8 / `active` with zero processes holding it. The fix was to **stop writing `on`** — with `control=auto` the driver takes a runtime-PM reference when a device node is opened, so the card wakes on demand and re-suspends by itself ~20 s after the last close. No release mechanism was needed; the one line meant to help was the only thing preventing sleep. Proven end to end: NVIDIA Chrome came up on `renderD128` with `glRenderer = ANGLE (NVIDIA, … RTX 4050 …)`, then the card returned to `suspended` on its own, and `luminos-verify` section 3 now passes all three checks. Two side-findings: `luminos-wine-launcher` had silently diverged from its installed copy (repo newer but missing both EGL exports — reconciled), and it **never calls the dGPU gate at all**, so Wine-on-NVIDIA is still denied like BUG-102. `luminos-gpu-launch` was also promoted from `dgpu-exec` to `dgpu-exec-v2` in the same pass. BUG-102 FIXED — picking "NVIDIA" in the Chrome GPU dialog silently gave you the AMD iGPU for a month, with a notification claiming otherwise. Three stacked causes: `chrome-luminos` never called the dGPU gate at all; the gate itself is defeated by **any launcher written in shell**, because setgid raises only the *effective* gid and bash resets it (fixed by `dgpu-exec-v2`, which `setresgid`s so the group is real); and Chrome is single-instance per profile, so the picker could never take effect while a window was open. Now proven on the card — `ANGLE (NVIDIA, Vulkan …RTX 4050…)`, 20 fds on `/dev/nvidia0`, listed in `nvidia-smi`. Two Chromes on two GPUs at once works, given separate `--user-data-dir`. BUG-101 FIXED — the SUPER launcher's app list "barely scrolled", on the touchpad only: Caelestia ships `input:touchpad:scroll_factor = 0.3`, and in a viewport only `maxShown` rows tall, 30% of a swipe travels less than one row. The mouse wheel uses the **separate** `input:scroll_factor`, already 1.0 — which is why the two devices behaved differently. Overridden to 1.0 in `hypr-vars.lua`; no QML touched. BUG-100 FIXED — every hyprpm plugin was dead because hyprpm was still building against an April compositor. BUG-094 FIXED **AND VERIFIED ON A REAL LOGIN** — Hyprland is now the live session, the pin took effect, the dGPU is `suspended`, and Claude Desktop runs on the AMD `renderD129`. Original report: the Hyprland session bounced straight back to SDDM: `AQ_DRM_DEVICES` is a COLON-separated list and the GPU pin was written as a PCI by-path, so one device path split into three nonexistent ones and the compositor aborted with "Found no gpus to use". Neither stock name works (by-path has colons, cardN is unstable), so a colon-free udev alias `/dev/dri/luminos-igpu` was created. BUG-093 FIXED — a user-site `packaging` copy shadowed the pacman one, so pacman said 26.2 while Python said 26.0 and every AUR python build failed; fixed with `PYTHONNOUSERSITE=1`, nothing removed. BUG-092 FIXED — SDDM greeter wallpaper pointed at a missing file *under `$HOME`*, which the `sddm` user could never read anyway; the resulting black login screen was misread as a Hyprland crash. **Note:** BUG-092 was first filed as BUG-091 and renumbered — 091 was already taken by the suspend bug below. BUG-091 FIXED — lid close and idle now suspend; the machine never had a suspend bug, only three layers of deliberate config, and the first fix landed in a PowerDevil config group nothing reads. BUG-087 FIXED — MCP tooling now reaches Claude Code, Claude Desktop and Antigravity; hooks moved to user scope because Cowork ignores project scope. BUG-085 FIXED — MCP tooling silently rotted; now pinned + verified by `luminos-verify --mcp`. BUG-086 CLOSED/WONTFIX — leaked OpenRouter key accepted by user as a dead account, no rotation. BUG-084 OPEN — DrKonqi gdb+debuginfod ate 7.4GB and filled zram; durable MemoryMax cap NOT yet applied. BUG-083 FIXED + measured. BUG-082 FIXED (pending live verify). BUG-080 still OPEN — Wine/MT5.)

## Open Bugs

### BUG-120 — Chrome takes ~25 s to open in the Caelestia-on-KWin session, then opens every window you asked for at once
<!-- [CHANGE: claude-code | 2026-08-13] -->
- Status: **OPEN — theory only, NOT measured.** Reported by Shawn from a real login, 2026-08-13.
- Severity: High (the session is unusable as a daily driver with this in it)
- Component: the bare-`kwin_wayland` session (`scripts/luminos-caelestia-kwin`) — **not Chrome, and not Caelestia**
- Symptom: Claude Desktop launched normally. Chrome then took so long that Shawn assumed it had crashed and relaunched it several times. After "a few seconds" **all of the windows appeared together**.
- **The diagnostic fact is the simultaneity, and it came from the user, not from me.** Genuine slowness — disk, CPU, memory pressure — produces *staggered* windows, each launch making the next worse. Windows arriving together mean one process was **blocked on a single shared thing and then released**: Chrome's singleton check handed each later launch to the first process as a queued "open a window" request, and the queue drained in one go when it unblocked. So exactly **one** Chrome ever started. This is not a crash and not N browsers fighting.
- **Leading theory (unverified): Chrome is waiting on a password safe that is not running.** The session exports `XDG_CURRENT_DESKTOP=KDE` (it must — the portal keys off it). Chrome reads that same variable to choose a password store and picks **KWallet**. The session deliberately starts almost nothing and **`kwalletd6` is not among it**, so Chrome blocks on a D-Bus call whose default reply timeout is **25 s**. Under Hyprland the variable reads `Hyprland`, Chrome does not recognise it, falls back to its own plaintext store, and starts instantly — which is why this is new and session-specific.
- Alternative suspects, ranked: the **portal** (the session starts `xdg-desktop-portal-kde`, the backend, but not the frontend multiplexer apps actually talk to — same 25 s wall on the startup dark-mode query); the **dGPU** (Chrome probes DRM devices, does not know about `KWIN_DRM_DEVICES`, and waking the card from D3cold on AC is slow — ranked lower because a GPU stall gives a *blank window*, not *no window*); **memory** (Electron + Chrome on a 15.6 GiB box, paging in from zram/NVMe — **not excluded**, because the queued windows would arrive together either way).
- **The measurement that settles it, and it is a stopwatch:** a consistent **~25 s** (or 120 s) is a D-Bus timeout and is eerily repeatable. **8 s once and 40 s the next** is I/O or memory and the wallet theory is dead. These point in opposite directions and one timing run separates them. Then: launch from a terminal and read stderr; check the waiting process's kernel wait-channel (socket read and disk wait look nothing alike); `busctl --user list | grep -E 'kwallet|portal|secrets'`.
- **The one-flag confirmation:** start Chrome once with `--password-store=basic`. That is exactly what it already does under Hyprland. Instant launch confirms the cause and the fix is a permanent flag.
- **Do NOT fix this by bolting `kwalletd6` + the portal frontend + a keyring onto the session.** That is three new moving parts to fix an unmeasured guess, and it cuts against the scope rule. Under **DECISION 68** this bug is expected to disappear entirely, because full Plasma starts the wallet itself.
- **2026-08-13 — DECISION 68 STEP A is now installed, so the measurement is available.** The
  "Luminos (Caelestia on Plasma)" greeter entry runs full Plasma, which starts `kwalletd6` itself.
  Time Chrome cold-start **three times in each session** (`time chrome-luminos`, from a terminal, with
  no Chrome already running):
  - Slow in KWin, instant in Plasma, and the KWin figure clusters tightly around 25 s → **theory confirmed**, close this as fixed by the session change.
  - Slow in **both** → the wallet theory is wrong; do not patch around it, go measure the blocked process directly (`cat /proc/<pid>/wchan`, `busctl --user list`, strace on the connect).
  - Times that scatter (8 s, then 40 s) → **the theory was wrong regardless of the outcome**; that is memory/IO, and it must be written up as wrong rather than quietly dropped because the symptom went away.

### BUG-121 — Volume and brightness keys do nothing in the Caelestia-on-KWin session
<!-- [CHANGE: claude-code | 2026-08-13] -->
- Status: **OPEN.** Reported by Shawn from a real login, 2026-08-13.
- Severity: High
- Component: the bare-`kwin_wayland` session — again the session, not the shell
- Root cause: **two possible handlers, both absent, for different reasons.** (1) Under Hyprland, Caelestia listens for the media keys itself via `hyprland_global_shortcuts_v1`; **KWin does not implement that protocol**, so Caelestia's handler is loaded, running, and deaf. (2) Plasma's own handler is not running in this session by design — see the correction below for *which* piece of Plasma that actually is. Nobody is listening.
- This is the same shape as BUG-113 and BUG-116: a Hyprland-only mechanism evaluating to nothing on KWin, with no error anywhere.
- **Expected to be fixed by DECISION 68** (full Plasma handles media keys natively). **Do not hand-build a media-key handler for the bare session** — that is precisely the "rebuild the desktop from parts" road that DECISION 68 retired.
- ✅ **The STEP B watch-out is ANSWERED — measured 2026-08-13, from disk, before anything was deleted.**
  The earlier note guessed the volume keys might belong to the `plasma-pa` **applet inside the panel**.
  **They do not.** `plasma-pa` ships the applet and the shortcut handler as **two separate plugin binaries**:
  ```
  /usr/lib/qt6/plugins/plasma/applets/org.kde.plasma.volume.so   <- the panel applet
  /usr/lib/qt6/plugins/kf6/kded/audioshortcutsservice.so         <- the shortcut handler
  ```
  The handler is a **KDED module** loaded into `kded6` — its own process, started by
  `plasma-workspace.target`, with no dependency on plasmashell and none on the panel. It declares
  `X-KDE-Kded-autoload`, and `kded6rc` carries no `Module-audioshortcutsservice` override disabling it.
  `kglobalshortcutsrc` independently agrees: the component that owns `increase_volume` / `mute` /
  `mic_mute` is **`[kmix]`**, not any applet.
  Brightness is the same story one level further out — the owner is **`[org_kde_powerdevil]`**, the
  PowerDevil daemon, a systemd user service that was never in the panel to begin with.
  **Conclusion: removing the Plasma panel does not re-break this bug.** Auto-hide remains the gentler
  and preferred option on its own merits, but it is no longer *required* in order to protect the keys.
  ⚠️ **The limit of this evidence, stated plainly:** this is packaging and config evidence, not a live
  test. Confirm it inside the new session before STEP B deletes anything —
  `pgrep -x kded6` should show the process, and
  `busctl --user tree org.kde.kglobalaccel | grep -iE 'kmix|powerdevil'` should show it holding both
  components. If either is missing, stop and use auto-hide.

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

### BUG-134 — The app launcher vanished as soon as you typed in it
<!-- [CHANGE: claude-code | 2026-08-16] -->
- Status: **FIXED (2026-08-16) — reproduced on demand, fixed, then re-run against the exact failing case plus three hover regressions.**
- Severity: High (the launcher was unusable for its one job)
- Component: `config/quickshell/caelestia-bar/shell.qml`, `scope.onLauncherHoveredChanged` and `launcherSurfaceHover`
- Symptom, in Shawn's words: *"the app launcher menu when i try to type something . it just crash"*.
- **It was not a crash.** `qs` never died: same PID before and after, no coredump (`coredumpctl` had only llama-server), and `shell.sh` logged no restart. The *window* disappeared, which looks identical from the outside.
- Root cause: the launcher window is sized to its content — `implicitHeight: launcher.implicitHeight` — and the content gets **shorter** as a query filters the result list. The window's top edge slides **down**, away from a pointer that never moved. The compositor sends a leave. `onLauncherHoveredChanged`'s `else` branch could not tell that from the user walking away, so it set `screenState.launcher = false` mid-word. This was written down as an "ACCEPTED COST" in the file when the `else` was added; the cost was much worse in practice than it read on paper.
- **The A/B that proved it** (`ydotool` typing, KWin's `workspace.cursorPos` as the oracle, `ipc call drawers isOpen launcher` as the readout):

  | pointer | query | result |
  | --- | --- | --- |
  | away (284,302) | `fir` (5 hits) | stays open |
  | over it (747,540) | `fir` (5 hits) | stays open — the list barely shrinks, the pointer is still inside |
  | over it (747,540) | `zzqqxw` (0 hits) | **closes** |
  | away (284,302) | `zzqqxw` (0 hits) | stays open |

  Identical keystrokes; only the pointer position differs. That isolates it to the one pointer-dependent close path in the file.
- Fix (4 lines, no timers): record the launcher's height when the pointer lands on it, and on leave **only close if the launcher is at least as tall as it was then**. Shorter means the surface moved, not the pointer. Hover-ownership is still surrendered — the pointer genuinely is off the surface, so hover can no longer be trusted to close what it opened — but the launcher stays up. Walking back onto it re-arms hover-to-close, so it is self-healing.
- The baseline has to be taken in **two** places. The usual way in is the bottom tripwire strip, which flips `launcherHovered` true while the launcher is still closed; the scope handler therefore records 0 and never fires again as the pointer walks up onto the now-open launcher. Hence the extra `onHoveredChanged` on `launcherSurfaceHover`. The scope handler reads `launcher.visible ? launcher.implicitHeight : 0` because a *closed* launcher keeps its last height (`launcher/Wrapper.qml:31` deliberately breaks the binding on the way out) and a stale tall value there would swallow a real leave.
- Regressions re-run after the fix, all pass: hover the strip → opens; move away → closes; strip → up onto the body → away → closes; Escape → closes; hover-open → type a filtering query → **stays**; keep typing to zero results → **stays**.
- Alternative considered and rejected: latch the window height to the tallest it reached while open, so the surface never shrinks under the pointer at all. It preserves dismiss-on-leave perfectly, but it adds mutable geometry state with a reset path, risks clipping the slide-up animation, and starts at 0 on first open (the same hazard `Wrapper.qml:37`'s hard-coded `|| 630` width fallback already works around). The height comparison is smaller and has no geometry risk.
- Related, not fixed: `implicitWidth`/`implicitHeight` on `launcherWindow` are bound to a changing property, which is the shape BUG-123 warns about. It is not the same severity — these change once per keystroke, not 24–38 times per animation — so it is left alone.
- Date Found: 2026-08-16 (reported by Shawn) / Date Fixed: 2026-08-16

### BUG-131 — The bar popout opened a bar-width away from the bar, and you could not reach it
<!-- [CHANGE: claude-code | 2026-08-16] -->
- Status: **FIXED (2026-08-16) — measured, then re-proven by travelling into the panel and clicking a button in it.**
- Severity: Medium (the panel BUG-130 had just made possible was unusable in practice)
- Component: `config/quickshell/caelestia-bar/shell.qml`, `popoutWindow`
- Symptom, in Shawn's words: *"its way to far keep it attached to the bar and also the pannel is un usable"*. Two complaints, **one cause**.
- Root cause: a **double offset**. Upstream's `drawers/Panels.qml:39` sets `anchors.leftMargin: bar.implicitWidth`, and BUG-130 copied it. Upstream needs it because upstream paints its bar *inside* the same full-screen surface, so it has to step around its own bar by hand. Here the bar is a **separate window** that reserves its width with `exclusiveZone: bar.exclusiveZone`, and a layer-shell surface with `exclusiveZone: 0` means *"honour everyone else's reservations"* — the compositor had already moved the popout window past the bar. Applying the margin on top of that pushed it a second 60px.
- **Why that also made it unusable, which is the non-obvious half.** The 60px gap is dead space belonging to neither surface. Reaching for the panel means the pointer is on neither the bar nor the popout, so `!barHover.hovered && !popoutHover.hovered` goes true, and the 250 ms close timer fires *while you are still on your way*. The panel deleted itself as you approached. With the gap at zero there is nothing to cross and the handoff is instant.
- Fix: delete the `anchors.leftMargin` line. Nothing replaces it.
- **Measured rather than reasoned about, and that mattered** — the two candidate explanations (window starts at the screen edge vs. window starts after the bar) predict the same screenshot but opposite fixes. Logging the window's own geometry settled it in one line: **`win=1380x900` on a `1440x900` screen**. 1440 would have meant the margin was right; 1380 means the compositor had already applied it.
- Verified end to end afterwards: hovered the wifi icon, walked the pointer across into the panel (which stayed open), landed on "Rescan networks" and clicked — the button became a spinner and the scan ran. Repeated on a clean restart with bluetooth.
- **Trap worth remembering, cost about ten minutes:** `pkill -x qs` is how you reload this shell, but `shell.sh` gives up after **3 non-zero exits inside 60 s** and opens a kitty window instead of the bar. Three quick debug restarts is exactly that budget. Either wait 60 s between restarts, or run `qs -p ~/.config/quickshell/caelestia-bar` yourself with `WAYLAND_DISPLAY` read from a live process.
- Second trap: the probe must run **after layout**. `Component.onCompleted` reported `100x100` (Qt's default) and `barW=10`, which is the window before it has been configured — nearly a wrong conclusion. And a `PanelWindow` that is `visible: false` keeps that default size, so the window has to be forced visible to be measured at all.
- Date Found: 2026-08-16 (reported by Shawn) / Date Fixed: 2026-08-16

### BUG-130 — The wifi, bluetooth and battery icons on the bar were pictures: hovering them did nothing
<!-- [CHANGE: claude-code | 2026-08-16] -->
- Status: **FIXED (2026-08-16) — all three popouts opened, read correct, and closed, checked by screenshot.**
- Severity: Medium (the state was visible but not reachable — no way to see which network, no way to switch one)
- Component: `config/quickshell/caelestia-bar/shell.qml` (new `popoutWindow`, `HoverHandler` on `BarWrapper`)
- Symptom: the left bar shows a wifi glyph, a bluetooth glyph and a battery glyph. Hovering any of them does nothing at all.
- **The icons were never wrong.** Early on I read a screenshot showing `wifi_off` while the machine was plainly connected and nearly went and "fixed" the state binding. The screenshot was taken 2 s after a shell restart, before `nmcli` had answered; a later one showed full bars. **A status icon read within a few seconds of start is reading a service that has not replied yet, not reading it wrong.**
- Root cause, and it was already written down in this file's own header comment: the popouts Wrapper was instantiated as a **decoy** — `visible: false`, zero size, present only because `BarWrapper` requires one — and **`checkPopout()` was never called**. That call lives in upstream's `modules/drawers/Interactions.qml:240`, which belongs to the full-screen drawers sheet that DECISION 68's port deliberately does not have. So nothing ever told the popout which icon the pointer was on.
- Fix, three small parts:
  1. A `HoverHandler` on the `BarWrapper` calling `bar.checkPopout(point.position.y)` — the same one line Interactions.qml runs.
  2. A new `popoutWindow` holding upstream's `BarPopouts.ClipWrapper` unmodified, offset by `anchors.leftMargin: bar.implicitWidth`.
  3. A 250 ms `Timer` to close it.
- **`HoverHandler`, not `MouseArea`, on purpose.** A handler is passive: it watches the pointer and never takes a press, so it cannot swallow the clicks underneath it. A `MouseArea` laid over the bar would have re-created BUG-128 one day after fixing it.
- **The popout window covers the whole output and uses `mask: Region { item: popoutsWrapper }` — it is never resized.** The obvious design is to size the window to the popout, and that is precisely the mistake BUG-123 documents: binding a layer-shell window dimension to an animating property costs a compositor configure round trip *per frame* (24–38 resizes were measured for one dashboard tab switch). Checking BUG-123 before writing the code is what stopped it. Covering the output is safe because outside the mask there is no input region at all, so clicks fall through to the windows behind.
- **The close needed a grace period because the bar and the popout are two separate surfaces.** "Left the bar" and "entered the popout" arrive as separate events in that order, so closing on the first leave would make the popout permanently unreachable — you could never travel to it. The 250 ms timer is bound to `hasCurrent && !barHover.hovered && !popoutHover.hovered`; entering the popout does not merely postpone the close, it unbinds `running` and cancels it outright.
- Had to add a `StyledRect` backdrop. Upstream never paints one because the sheet's blob is behind the popout; without the sheet the first render was white text floating over whatever windows were behind it. Same pattern the launcher, OSD and dashboard already use here.
- `keyboardFocus` deliberately left at its default `None`: `popouts/Wrapper.qml:98-104` already flips it to `OnDemand` by `Binding` when the wifi-password field needs it. Setting it would have fought that.
- Verified: **WiFi** → "Wireless / Enabled / 21 networks available" with BELL851 marked connected; **Bluetooth** → "Enabled / Discovering / ULT WEAR"; **Battery** → "Remaining: 100% / Fully charged!". Handoff proven by hopping the pointer from icon into panel (stayed open); close proven by moving away (gone within 1.5 s).
- **Known dead end inside the fix, not caused by it:** the battery popout's three power-profile buttons probably do nothing — `PowerProfiles` is masked on this machine (`Could not start PowerProfilesDaemon` in the shell log). Separate problem, not investigated.
- Date Found: 2026-08-16 (reported by Shawn) / Date Fixed: 2026-08-16

### BUG-129 — The power menu opened from the bar button and then stayed out forever
<!-- [CHANGE: claude-code | 2026-08-15] -->
- Status: **FIXED (2026-08-15) — PROVEN ON SCREEN, both directions.**
- Severity: Medium (a panel that will not go away is in the way of everything behind it)
- Component: `config/quickshell/caelestia-bar/shell.qml`, `rightEdgeMouse`
- Symptom: click the power button on the left bar, the four session options slide out — and nothing ever puts them back. Reported by Shawn immediately after BUG-128 made the panel usable.
- **Root cause is a rule that was correct for every case that existed when it was written.** The close rule is `onContainsMouseChanged`: leaving closes the panel, *but only if `ownedByPointer`* — the pointer earns the right to close a panel by having been inside it. Every opening route that existed at the time put the pointer inside: the right-edge drag starts under your finger, and the drag handler sets the flag by hand. **The bar button is a different window.** `containsMouse` on this surface never goes true, so the flag is never set — and the leave that would close it never happens either, because there was never an enter. Nothing was left to close it.
  Note this only became visible *because* BUG-128 was fixed. Before that the button's effect was invisible anyway.
- Fix: a 3 s `Timer` whose `running` is a **binding** — `screenState.session && !rightEdgeMouse.containsMouse`. Moving onto the panel stops and resets the countdown; moving off starts it again from zero. No new state, no new handler, and the existing leave-closes rule is untouched.
- **Deliberately session-only.** The notification list next to it is something you *read*; a 3 s timer would yank it away mid-sentence, which is a worse bug than the one being fixed.
- The load-bearing assumption, verified rather than assumed: **hover reaches a parent**, so `rightEdgeMouse.containsMouse` stays true while the pointer is on the session panel's own buttons — which is what makes "keep it open while I am looking at it" fall out for free. Parked the pointer on the panel for 6 s and it stayed open; moved it away and it closed inside 4 s. Both checked by screenshot.
- Date Found: 2026-08-15 (reported by Shawn) / Date Fixed: 2026-08-15

### BUG-128 — Notification toasts, the power menu and the notification list were all unclickable: one invisible mouse area sat on top of every panel
<!-- [CHANGE: claude-code | 2026-08-15] -->
- Status: **FIXED (2026-08-15) — PROVEN ON SCREEN with synthetic input, not asserted.**
- Severity: HIGH (a notification you cannot act on is a notification you cannot use — Shawn's example was an update notice he wanted to click through to)
- Component: `config/quickshell/caelestia-bar/shell.qml` (the `rightEdge` PanelWindow), Caelestia-on-Plasma / DECISION 68
- Symptom: toasts appear at the top right, render perfectly, show the expand chevron — and **nothing responds**. No hover highlight, no expand, no action buttons, no close. Same for the power menu and the notification-list drawer.
- **What it was NOT, each ruled out by evidence rather than by reasoning:**
  - Not the notification server. A live `notify-send` with two actions was delivered, tracked and drawn, and `services/Notifs.qml` already sets `actionsSupported: true`.
  - Not the UI. `modules/notifications/Notification.qml` already has the whole thing — `expanded`, the drag-to-expand, the chevron at :351, the action `Repeater` at :451 calling `modelData.invoke()`, the close at :475. It was all there and all unreachable.
  - Not the input mask. `mask: Region { ... }` already contained `Region { item: notifPanel }`, so the compositor was delivering the events. They were being eaten *inside* the window.
- **Root cause — declaration order, one line of structure.** The four panels (`osdWrapper`, `sessionWrapper`, `notifPanel`, `sidebarDrawer`) were **siblings** of `MouseArea { id: rightEdgeMouse; anchors.fill: parent }`, and the MouseArea was declared **last**. Among Qt Quick siblings with equal `z`, the last-declared is on top for painting *and* for hit-testing. So a full-screen invisible mouse area covered every panel and swallowed every press. One mistake, three broken features.
- Fix: make the panels **children** of the MouseArea. Children are always above their parent, so clicks land on the panels; hover still propagates *up* to a parent, so the edge gesture and the close-on-leave handler are untouched. This is the shape upstream already has — `drawers/ContentWindow.qml:251-262` nests `Panels` inside `Interactions`. **The fix deletes a difference from upstream rather than adding a mechanism.**
- **The tempting one-liner `z: -1` on the MouseArea is WRONG and was rejected.** `components/StateLayer.qml`'s root is itself a `MouseArea`. Qt hover reaches parents but **not siblings below**, so `z: -1` would make panels clickable while killing (a) the OSD opening on edge-hover and (b) `onContainsMouseChanged` closing panels — drawers would open and never close.
- How it was proven (ydotoold on a throwaway socket + `workspace.cursorPos` from a KWin script as the position oracle):
  - chevron shows a hover ring → expand → app name, full body, and the `Open W…` / `Later` / close / copy row appear
  - clicking `Open Window` made the waiting `notify-send` print **`open`** — the action really is invoked, not just drawn
  - the `×` button dismissed the toast
- **Regression check, A/B against the pre-change file:** the right-edge press-and-drag gesture does not respond to a synthetic drag — **and it behaved identically on the backup**, so the gesture is unchanged by this fix. It is not proven working by hand; a real pointer test is still owed.
- Trap worth keeping: the first synthetic pointer move overshot to `1439,1` (pointer acceleration) before the verify-and-correct loop converged. Never trust one `ydotool mousemove`; read `workspace.cursorPos` back. Also `notify-send -A` **blocks** until the notification is answered — background it or it hangs the whole script.
- Date Found: 2026-08-15 (reported by Shawn) / Date Fixed: 2026-08-15

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

> ### RE-MEASURED 2026-08-16 — the diagnosis below is STALE. The blocker moved.
> *[CHANGE: claude-code | 2026-08-16]*
>
> **`libllama-common.so.0` is no longer missing.** All seven libraries now exist,
> installed by llama-cpp-python 0.3.34 on 2026-08-05 — but in **two** directories,
> which is why a search for one of them can still come back empty:
> ```
> …/site-packages/llama_cpp/lib/   libllama, libggml{,-base,-cpu,-cuda}, libmtmd
> …/site-packages/lib/             libllama-common     <- different directory
> ```
> With `LD_LIBRARY_PATH` set to both, `ldd` resolves everything and the binary
> starts. **It then aborts before parsing a single argument:**
> ```
> common/arg.cpp:2493: GGML_ASSERT(params.n_gpu_layers < 0) failed
> #6 common_params_parser_init(...)  from …/lib/libllama-common.so.0
> ```
> **The binary is 2026-04-24; the libraries are 2026-08-05.** llama.cpp changed the
> default `n_gpu_layers` from `0` to `-1` ("all") in between, and the new library
> asserts the new convention against a struct the old binary initialised the old
> way. This is a version mismatch, not a missing file — **and no flag can work
> around it, because it dies during parser setup, before any flag is read.**
>
> **`--version` and `--help` crash too**, so the binary cannot report anything
> about itself. Read the *library's* flag table instead (`strings` on
> `libllama-common.so.0`) — that is what will be in charge after a rebuild.
>
> **The prize is bigger than tool calling.** That August library advertises
> **`--jinja`** (parses Gemma's tool calls natively → BUG-133's proxy gets deleted),
> **`--override-tensor` and `--n-cpu-moe`** (MoE expert offload as a *first-class
> flag* → `scripts/luminos_moe_offload.py` may get deleted too), **`--swa-full`**
> (the DECISION 74 context fix, no ctypes needed) and `--flash-attn`. Every custom
> mechanism in the serving stack exists because llama-cpp-python's server does not
> expose these. **NONE of it is tested** — the binary will not run.
>
> **Fix is a rebuild**, not a file copy: build `llama-server` from the same
> llama.cpp revision the libraries came from. Note CUDA fails in an ordinary shell
> (`no CUDA-capable device is detected`) because of the DECISION 25 `dgpu` group
> gate — that is the gate working, not a llama.cpp fault. Test through
> `dgpu-exec-v2` or as the service user.

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

> **It did come back**, on the very next bump (0.56.2), three days later — see **BUG-111**. The
> rebuild is now automatic at session start via `scripts/luminos-hyprpm-sync`, so this prediction
> should no longer come true. The manual command above still works for debugging.

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

---

## BUG-105 — the local LLM server was OOM-killed by long prompts, and blamed the GPU
# [CHANGE: claude-code | 2026-08-05]
**Status:** FIXED (one flag; verified by reproducing the kill, then not reproducing it)
**Severity:** HIGH — made the whole agent stack unusable, and pointed at the wrong subsystem
**Found:** 2026-08-05, while wiring OpenClaw to the local model

### What it looked like
Short prompts worked perfectly. Any prompt over roughly 15k tokens made the server vanish
about 30 seconds in. The client saw a dropped connection or an HTTP 500 from the proxy.
The server's own log ended with:

```
INFO:     Uvicorn running on http://127.0.0.1:8081
INFO:     Shutting down
INFO:     Waiting for connections to close. (CTRL+C to force quit)
```

That reads like a clean, deliberate shutdown. It is not. Wrapping the launcher to report
its exit code gave **rc=137 — SIGKILL**, which nothing can catch and which uvicorn cannot
have handled. The "Shutting down" line is emitted as the process is torn down and is
actively misleading.

### Why it looked like a GPU problem, and wasn't
Everything about the context pointed at VRAM: a GPU-offloaded model, a 6 GB card, a
context increase immediately before the failures started, and a known 4.6 GB budget.
VRAM was fine the whole time — 4630 MiB of 6141 MiB.

Sampling `/proc/<pid>/status` once a second during a failing request showed the truth:

```
t=7s  rss=4955MB avail=5932MB swapfree=5000MB
t=16s rss=8830MB avail=1898MB swapfree=4937MB
t=24s rss=5678MB avail=1828MB swapfree=0MB     <- zram exhausted
t=29s rss=7418MB avail=334MB  swapfree=5MB
t=30s rss=0MB    avail=7466MB                  <- killed
```

**System RAM**, not VRAM. The process ate 14 GB of RAM and all 5 GB of zram, and the
kernel killed it.

### Root cause
`llama-cpp-python`'s bundled server defaults **`--logits_all` to True**. That keeps the
full logit vector for *every* prompt token instead of just the last one. With Qwen3's
151,936-token vocabulary:

```
19,000 tokens x 151,936 vocab x 4 bytes = ~11.5 GB
```

on a machine with 14 GB of RAM. Chat generation never needs those logits; only
perplexity/scoring work does.

### The fix
`--logits_all false` in `scripts/jobhunt/llm-server.sh`.

Measured on the identical 19,380-token request that previously killed it:

| | before | after |
|---|---|---|
| peak RSS | 8830 MB | **817 MB** |
| outcome | rc=137 at ~30 s | answered in 13.4 s |

### Testing traps hit while chasing this
- **`pkill -f 'llama_cpp.server'` kills the shell running it**, because the pattern matches
  that shell's own command line. It cost two shells here. The bracket trick does not save
  you if the *rest* of the command also contains the literal string — put the pattern in a
  script, or kill a PID you captured earlier. Same shape as the `chrome-bug10[3]` trap in
  BUG-103.
- A background server started from a tool-call shell dies when that shell is reset. Use
  `setsid nohup ... < /dev/null &`, or a crash and a cleanup look identical.
- `journalctl -k` showed nothing for an OOM kill under this user, so "no OOM in the log"
  was not evidence of no OOM. Watching RSS directly was what settled it.

### The general lesson
**A tidy shutdown message is not evidence of a tidy shutdown.** When a process disappears,
get its exit code before theorising — rc=137 would have redirected this from "GPU/CUDA" to
"memory" immediately. And when a component runs on an accelerator, the accelerator is the
first thing everyone suspects and often the last thing at fault; measure both sides.

## BUG-106 — the OpenClaw dashboard could not connect, and `openclaw status` said auth was off
# [CHANGE: claude-code | 2026-08-06]
**Status:** FIXED (config + supervision; verified in a real browser, not by assertion)
**Severity:** HIGH — the Control UI was the only way to drive the agent, and it was unusable.
Also CRITICAL-adjacent: it closes `gateway.loopback_no_auth`, and OpenClaw's tools run
**unsandboxed on the host**.
**Found:** 2026-08-06

### What it looked like
`http://127.0.0.1:18789/chat` rendered "Could not connect" forever. Everything below the UI
looked healthy, which is what made it slow to place:
- the gateway was listening on 18789,
- the WebSocket handshake **succeeded** — `curl` got `101 Switching Protocols` and a
  `connect.challenge` nonce back,
- `openclaw status` reported **`auth none`**.

### Root cause
The gateway had **no token configured**, but it still *requires* one for control RPCs on
loopback. So the browser had nothing to send, and the server hung up right after the
handshake. The real message was only visible by pulling it out of the page with JS:

```
unauthorized: gateway token missing
(open the dashboard URL and paste the token in Control UI settings)
```

**`auth none` is a description of the config, not of the requirement.** Read as "no auth is
needed" it sends you looking for a network fault. The CLI said the same thing more honestly:
`openclaw gateway health` -> *"reachable, but this CLI has no token/password or paired
device token"*.

### Fix
1. Generated a token into `~/.openclaw/gateway-token` (`chmod 600`, never echoed).
2. Set `gateway.auth.mode: "token"` with the token as a **literal** value.
3. Restarted the gateway under a supervised systemd user unit.

Verified by loading the Control UI in Chrome: it now renders **"Ready to chat"** with the
model line `luminos-local · luminos · Off`.

### Three traps found on the way, all silent
- **`${ENV_VAR}` in `openclaw.json` is stored VERBATIM and resolved at read time**, not baked
  in at write time. Setting the token as `"${OPENCLAW_GATEWAY_TOKEN}"` therefore works only
  for a process that inherited that variable — start the gateway from a plain shell and it
  comes back unauthenticated. The log is explicit once you look:
  `SECRETS_RELOADER_DEGRADED ... Environment variable "OPENCLAW_GATEWAY_TOKEN" is missing`.
  Credit where due: the gateway **stayed on last-known-good** rather than opening up.
- **A SecretRef token disables dashboard auto-auth.** `{source:"file", provider, id}` is the
  tidier design and it works, but then `openclaw dashboard` refuses to put the token in the
  URL and a human has to paste the secret by hand. Two non-obvious sub-rules: the provider
  must be declared under `secrets.providers.*` *first* or the patch is rejected, and `id` is
  **not a path** — for a `singleValue` provider it must be the literal string `"value"`.
- **The gateway does a full process restart when `gateway.auth.token` changes and expects a
  supervisor to bring it back.** Under a transient unit with `Restart=on-failure` it exited
  0, so nothing restarted it and the unit was garbage-collected — looking exactly like "the
  fix crashed it". `Restart=always` is required.

### Still open
The gateway runs as a **transient** unit (`systemd-run --user`), so it does not survive a
reboot. `openclaw gateway install` writes a permanent unit — not done, needs Shawn's OK.
Before this it was worse: it was running inside `claude-cowork.service`'s own cgroup, i.e. an
agent session had started it by hand, so it died whenever Cowork restarted.

### The general lesson
**A successful handshake is not a successful connection.** Auth here failed *after* the
WebSocket upgrade, so every layer-4 check passed and pointed away from the real cause. When a
status line and an error message disagree, believe the error message.

---

## BUG-107 — the free filter put European-only roles in the Canadian pool
**Status: FIXED 2026-08-06** · `scripts/jobhunt/locations.py`

`classify()` returned `global` for **"Anywhere in France, Belgium, Spain"**. The `_GLOBAL`
regex contains a bare `\banywhere\b`, and that branch only cross-checks the **title** for a
country — never the location string it just matched. So 16 European-only roles reached the
scored pool, where they cost GPU time and would have cost application time.

**"Anywhere IN <somewhere>" is a scope, not the absence of one.** Fixed with a dedicated
`_SCOPED_ANYWHERE = r"\banywhere\s+in\s+(?!the\s+world\b)"`; when it matches, the global
branch is skipped so the country checks below get their turn. The negative lookahead is what
keeps "Anywhere in the World" global. It deliberately does **not** catch
"Worldwide (excl. China)" — an exclusion list is still worldwide, and treating the named
country as a scope there would be the same bug pointing the other way.

**How it was found matters: not by a test.** `locations.py`'s 17 built-in cases all passed
before and after. It surfaced from reading `SELECT location, bucket, COUNT(*)` over the live
pool — i.e. by looking at what the classifier actually did to real data, not at what it was
asked to do. Five regression cases added; 26/26 now pass.

**Consequence for the design:** `score.py` now **recomputes the bucket on every rules pass**
instead of trusting what `ingest.py` stored. Bucket is derived data, and derived data that is
only computed at crawl time means a classifier fix cannot land without a full re-crawl of
every board.

---

## BUG-108 — the scorer promoted jobs the filter had already rejected
**Status: FIXED 2026-08-06** · `scripts/jobhunt/score.py`

A Twilio posting whose location read **`Remote - US`** appeared at the top of the shortlist,
with `bucket = us_only` still correctly set on the row.

The same role is posted for both Canada and the US and shares one `dedup_key`. The scorer
writes a score across every listing of the same role — correct, since one job on three boards
is one job and scoring it three times wastes the GPU. But the `UPDATE ... WHERE dedup_key=?`
had **no status predicate**, so it also set `status='shortlist'` on the sibling row the rules
pass had put in `filtered`. Fixed by adding `AND status IN ('pool','scored','shortlist')`.

The failure is worth remembering for its shape: **the visible number was right and the row
underneath it was wrong.** The score of 88 was computed from the Canadian listing and was
defensible; only the location column gave it away.

---

## BUG-109 — the model scored four out of five jobs as exactly 40
**Status: FIXED 2026-08-06** · `scripts/jobhunt/score.py`

First run of the Phase 2 scorer: five jobs, four scored **40**, one scored 59. A ranking in
which most rows share one value is not a ranking.

The model was not confused. Its written reasoning was correct every time — it found "requires
7 years", "requires 5+ years", "requires 2+ years" straight out of the postings. It was asked
for a 0-100 rating against a banded rubric (`0-39 / 40-59 / 60-79 / 80-100`) and **parked on
the floor of a band**. The same hedging showed up in `seniority_match`, which came back
`unclear` on 5 of 5 even where the posting stated a number.

**Fix: the model reports facts, Python does the arithmetic.** The schema now asks for
`years_required` (integer), `degree_required`, `hard_blocker`, and a `fit_signal` enum, and
`compute_score()` derives the number. Measured on 15 jobs afterwards: nine distinct values
across 20-88.

Two further defects were only visible *because* the number came apart into its inputs:
- A posting returned `fit_signal: strong` while listing **thirteen** required technologies the
  candidate lacks, with a `one_line_why` that said exactly that. The prose was right, the
  label was wrong. `missing_skills` (a reading) now overrides `fit_signal` (a judgement).
- The `Remote - US` row above — see BUG-108.

**The general lesson: an LLM is a reliable reader and an unreliable judge.** Ask it what a
document says, not what it is worth. A side benefit is that re-tuning is now free —
`score.py --recompute` re-ranks from stored answers in about a second instead of a 25-minute
GPU pass.

---

## BUG-110 — the desktop's own dashboard was swallowing every window's titlebar clicks
**Status: FIXED 2026-08-06, then DELIBERATELY REVERTED 2026-08-08 — see the box below before
"fixing" this again** · `~/.config/caelestia/shell.json`, `~/.config/caelestia/hypr-user.lua`

> ### ⚠️ 2026-08-08 — `dashboard.showOnHover` is back to `true`, on purpose
> # [CHANGE: claude-code | 2026-08-08]
> Shawn asked for the top-edge drop-down back, was shown the trade-off below in full, and chose
> to take it. **The titlebar-click problem described in this entry is therefore LIVE again and is
> now accepted behaviour, not an open bug.** In apps that draw their own titlebar (Claude Desktop
> and similar Electron apps) the close/maximize buttons and double-click-to-maximize at the very
> top edge will be swallowed by the dashboard.
>
> **Do not "fix" this by flipping `showOnHover` back to `false`** — that just restarts the loop.
> If it becomes annoying, the real fix is a hover *dwell delay* (only open once the pointer
> **rests** at the top edge for ~200 ms, so an overshoot while reaching for a button does not
> trigger it). That was offered and declined as too much machinery for now. It needs a patch to
> `inTopPanel`/the hover handler at `modules/drawers/Interactions.qml:211`, which is **owned by
> the `caelestia-shell` package**, so it would also need a pacman hook to survive upgrades.
>
> Re-verified working after the revert (config hot-reloads, no shell restart needed): sweeping
> the cursor down x=720 with `hl.dsp.cursor.move`, `drawers isOpen dashboard` returns `0` at
> y≥12 and `1` at y≤4, and the panel renders. Note the trigger band is **~4 logical px**, not the
> 10 estimated below, and once open the hover region expands to the panel's full ~660 px height —
> which is why it stays open until you move well clear of it.

Shawn: *"when i double click any other window like chrome top left corner it goes to fullscreen
and back to normal but this does not work with claude desktop … and the buttons even are not
working."*

It reads like an Electron bug. It is not. It is not an app bug at all.

Caelestia's `caelestia-drawers` is a **full-screen layer surface** — `hyprctl layers` reports it
at `0,0 1440x900` on level 2, above every window on the screen. Its dashboard panel opens on
hover: `modules/drawers/Interactions.qml:211` calls `inTopPanel()`, whose trigger band is
`y < max(border.minThickness, border.thickness)` — the **top 10 logical pixels**, spanning
roughly `x 285..1185`. Reaching for a titlebar button means slamming the pointer at the top edge
of the screen, which is exactly that band. The panel drops down to about `y 660` and, being a
layer surface, it is what receives the click. The window underneath never hears it.

DECISION 50 made this unavoidable: every window is tiled at `y=20`, so its titlebar sits
directly under the panel.

**Measured, not reasoned** — throwaway `claude-desktop --profile=tbtest`, ydotool + grim:

| dashboard | target | result |
|---|---|---|
| open | close button | dead, three attempts |
| **shut** | **same pixel, one click** | **window closed immediately** |
| shut | maximize button, live Claude window | `fullscreen 0 -> 1` |
| shut | double-click titlebar | `fullscreen 0 -> 1` |

So the buttons were never broken. Chrome "worked" only because Shawn double-clicks its **top-left
corner** (`x 70..285`) — the one part of a titlebar that falls outside the panel's span. Chrome
in fact draws no window buttons at all under Wayland; it has only a tab strip.

**Fix:** `dashboard.showOnHover = false` in `shell.json`, plus `SUPER+B` bound to
`caelestia:dashboard` so it is still reachable (`SUPER+D` is `kbCommunicationWs`; `SUPER+K` still
toggles every panel at once). Verified after reload by sweeping the whole top edge — the panel
stays shut — then maximizing Claude by double-clicking the strip it used to cover.

**Minimize is a separate, unfixable case.** Hyprland has no minimize concept, so the app's request
has nothing to land on and no `minimize>>` event is emitted. `SUPER+H` (`luminos-win min`) and
`SUPER+SHIFT+H` are the working equivalents. A titlebar that offers a button the compositor cannot
honour will keep generating this bug report.

**The transferable lesson:** *a hover-triggered overlay on a screen edge is in direct competition
with every window's titlebar.* Any edge-hover panel — dashboard, launcher, sidebar, OSD — is a
click sink for whatever it covers. `launcher.showOnHover` is still `true` here and owns the bottom
edge for the same reason; it is left on only because nothing clickable lives there.

**Two traps found on the way, both worth remembering:**
- `hyprctl dispatch <classic-dispatcher>` is **dead** in Hyprland 0.56.1. The argument is parsed as
  Lua now: `hyprctl dispatch 'hl.dsp.window.close()'`. The old spelling errors out rather than
  doing nothing, but every script written against 0.4x needs checking. `luminos-win` was already
  correct.
- `ydotool mousemove --absolute` coordinates on this machine are **logical / 2** (raw / 4), not raw
  pixels, and the mapping drifts across a session. Read `hyprctl cursorpos` back after every move;
  never trust the number you sent. A negative Y clamps to 1 — straight into the hover band, which
  is what made the first round of tests look random.

---

## BUG-111 — the plugin breakage BUG-100 predicted came back, on the first Hyprland bump
**[CHANGE: claude-code | 2026-08-08] — FIXED, and this time automated**

**Symptom.** A config-error popup at login, four lines of it plus "(12 more...)":

```
/home/shawn/.config/caelestia/hypr-user.lua:397: unknown config key 'plugin.hyprexpo...'
```

### The message points at the wrong file
Line 397 is the `hl.config { plugin = {...} }` block, and there is nothing wrong with it. Those
keys do not exist because **the plugins that own them were never loaded** — Hyprland parses the
config before any plugin is in memory, so an unloaded plugin turns its whole option namespace
into unknown keys. Anyone who reads the error literally goes and edits Lua, which is exactly the
wrong place. `hyprctl plugin list` said `no plugins loaded` while `hyprpm list` showed three
enabled, which is the real tell.

The cause is the one BUG-100 documented, one version later:

```
built   5c9377c1…   (Hyprland 0.56.1)
running efb50993…   (Hyprland 0.56.2, installed 2026-08-05)
```

`hyprpm update` rebuilt all five plugins and loaded the three enabled ones. Total elapsed: about
two minutes, almost all of it cloning Hyprland for headers.

### Why a pacman hook is the obvious fix and does not work
The tempting answer is a hook on the `hyprland` package. It cannot work, for two independent
reasons:

1. **hyprpm builds against the *running* compositor**, not the installed one — it prints
   `checked out to running ver`. During a pacman transaction the running Hyprland is still the
   old one, so the hook would rebuild every plugin against the version being replaced.
2. **Pacman hooks run as root**, and hyprpm's state is `/var/cache/hyprpm/$USER/`. Root would
   read and write root's state, and Shawn's would stay stale.

The first moment the new compositor is actually running, as the right user, is **session start**.

### The fix — `scripts/luminos-hyprpm-sync`
Called from the `hyprland.start` handler in `hypr-user.lua`, replacing the bare
`hyprpm reload -n`. It compares hyprpm's build hash against the running commit, runs
`hyprpm update` only if they differ, reloads, then **asks the compositor** how many plugins are
actually loaded and notifies if that is fewer than are enabled. Async, so the rare multi-minute
rebuild never delays login.

The readback matters. `hyprpm update` prints a cheerful green `✔ Loaded <plugin>` for each one
and will do so while leaving you with nothing loaded — same family as BUG-088/089. The only
trustworthy source is `hyprctl plugin list`.

Negative-tested before being wired in, because a health check that cannot fail is worse than
none: stale hash → takes the rebuild path; `hyprpm update` exits non-zero → script exits 1 and
notifies; 5 enabled but 3 loaded → script exits 1 and notifies.

### What is still expected behaviour
A **brief** config-error flash at login on the first boot after a Hyprland upgrade is normal and
unavoidable: the config is parsed before plugins load, always. It clears as soon as the reload
completes. Only a popup that *stays* means something is wrong.

---

## BUG-112 — `XDG_MENU_PREFIX=hyprland-` silently emptied the KService cache, killing every KDE global shortcut
# [CHANGE: claude-code | 2026-08-09]
**Status: FIXED.** Present since ~2026-04-19.

### Symptom
No KDE global shortcut registered. Not the new Caelestia ones, and — the clue that this was
older and bigger than the task at hand — **not Shawn's own `net.local.*` custom shortcuts
either.** They had simply never worked and nobody had connected the two.

### The two-part cause
**Part one, the thing everyone gets wrong.** A shortcut is registered by
`X-KDE-Shortcuts=<accel>` **inside the `.desktop` file**. The `[services][<id>.desktop] _launch=`
group in `kglobalshortcutsrc` is only a *user override store* and does nothing on its own.
Proof: `org.kde.dolphin.desktop` is a live component with `Meta+E` bound and **has no group in
`kglobalshortcutsrc` at all**. Confirmed against upstream `globalshortcutsregistry.cpp` —
`loadSettings()` explicitly `continue`s past the `services` group and any group ending in
`.desktop`; the real work is `detectAppsWithShortcuts()` calling `KApplicationTrader::query`.

**Part two, the actual fault.** `KApplicationTrader` reads the sycoca service cache — and the
cache contained **zero applications**. `XDG_MENU_PREFIX` selects which file in `/etc/xdg/menus`
`kbuildsycoca6` reads. Only `plasma-applications.menu` ships on this box, but the Hyprland
session sets `XDG_MENU_PREFIX=hyprland-`. With no matching menu file `kbuildsycoca6`
**exits 0 and writes a 264 KB database containing nothing.** Silently. Every rebuild from inside
the Hyprland session wiped the cache.

A C++ `KService` probe is what finally proved it: `allServices() == 0` even for Dolphin.

Also worth knowing: **the sycoca filename is a hash of `XDG_DATA_DIRS`**, so a rebuild run from
the wrong environment writes a different file and leaves the live one stale.

### Fix, in three places
1. `ln -sfn plasma-applications.menu /etc/xdg/menus/hyprland-applications.menu` — additive, and it
   repairs the *Hyprland* session's cache too, which is why Shawn's own shortcuts now work.
2. `export XDG_MENU_PREFIX=plasma-` in `scripts/luminos-caelestia-kwin`.
3. `kbuildsycoca6 --noincremental` from the launcher **before kwin starts, in kwin's own
   environment** — kwin hosts kglobalaccel and scans for shortcuts once at startup, so a cache
   written later, or under another prefix, is too late.

Verified by `busctl --user tree org.kde.kglobalaccel` showing all seven `luminos_cael_*`
components, and by `invokeShortcut _launch` flipping a real drawer's state 0 → 1.

### Dead ends, recorded so they are not re-run
- `X-KDE-GlobalAccel-CommandShortcut=true` — red herring; Shawn's entries had it and still failed.
- `NoDisplay=true` — red herring; the working trader query returns `NoDisplay` entries fine.
- "user `~/.local/share/applications` isn't scanned" — disproved with a clean probe in
  `/usr/share/applications`, which also failed.
- `grep -a` on the sycoca binary returned 0 for our entries **and 0 for `dolphin`** — the negative
  control invalidated the test. Do not draw conclusions from it.
- A standalone `/usr/lib/kglobalacceld` exits instantly with an empty log: on Plasma 6
  **`kwin_wayland` itself owns `org.kde.kglobalaccel`** (only kwin links `libKGlobalAccelD.so`).
- `busctl list` shows *activatable* names too, which makes a missing service look present. Use
  `busctl --user list --acquired`.

---

## BUG-113 — Caelestia's drawers all no-op on KWin because `ShellState.forActive()` returns null
# [CHANGE: claude-code | 2026-08-09]
**Status: FIXED** (patched in the overlay; upstream unchanged).

Every drawer toggle resolves its target screen through `Hypr.focusedMonitor`. With no Hyprland
IPC that is null, `Hypr.monitorFor()` never matches, and the function falls out to `return null`.
Callers then throw in `modules/Shortcuts.qml` at `Object.keys(screenState)` and
`typeof screenState[drawer]`, and `drawers list` comes back as an **empty string**. Nothing
errors visibly. This is *the* reason Caelestia looks dead on KWin; everything else is cosmetic.

**The fallback must go after the loop, not before it.** An earlier version bailed out on
`if (!focusedMonitor)` and that was not enough: `focusedMonitor` can be non-null and still match
none of KWin's screens, because a reachable Hyprland socket describes *Hyprland's* outputs. That
case fell straight through to `return null` and the drawers were dead again — with the patch
present and looking correct. Patching the exit covers both.

Related: `scripts/luminos-caelestia-kwin` now `unset`s `HYPRLAND_INSTANCE_SIGNATURE` and
`HYPRLAND_CMD`. A greeter login never sets them; a session started by hand from a Hyprland
terminal does, and the shell then quietly describes the *wrong compositor*.

### Testing notes that cost time
- **`qs ipc` is display-scoped.** Nested testing needs `WAYLAND_DISPLAY=wayland-0` for `qs ipc`
  (kwin's socket) and `wayland-1` for `grim` (Hyprland). `grim` on wayland-0 fails outright —
  the nested kwin offers no wlr-screencopy.
- **zsh does not word-split unquoted variables.** `Q="qs -p … ipc call"; $Q drawers toggle bar`
  is "command not found", and with `>/dev/null 2>&1` attached it is *silent*. Two rounds of
  "the bar does not render" were this and nothing else. The bar, launcher and dashboard all
  render correctly under KWin.

---

## BUG-114 — The trackpad goes dead on KWin: KDE ships tap-to-click off, Hyprland ships it on
# [CHANGE: claude-code | 2026-08-09]
**Status: FIXED.**

### Symptom
In the Caelestia-on-KWin session the cursor moves normally and **taps do nothing at all**.
Reported as *"i can move the cursore but when i click nothing happen."* Nothing on screen, and
nothing in any log, says why.

### Cause
`~/.config/kcminputrc` held exactly one key for the touchpad — `NaturalScroll=true`. No
`TapToClick`. **KDE's libinput default for tap-to-click is `false`; Hyprland's is `true`.**
`~/.config/hypr/hyprland/input.lua` never mentions tap, so on Hyprland it has always worked by
default and there was nothing to carry over.

### Fix
`TapToClick`, `TapAndDrag` on; `TapDragLock` off; `DisableWhileTyping` on — written into the
`[Libinput][2362][12305][ASUP1208:00 093A:3011 Touchpad]` group and **read back to confirm**
(`kwriteconfig6` has mangled a config before — BUG-090). Done from
`luminos-caelestia-kwin-session install`, not by hand, because `kcminputrc` is not in the repo
and a reinstall elsewhere would land on a dead trackpad again. Negative-tested: key deleted,
installer run, key confirmed restored. Only KDE sessions read this file, so Hyprland is
untouched either way.

### The wrong answer that looked right
This was first blamed on BUG-113's sibling — a screen-edge drag band swallowing clicks — and
that patch was written and shipped. **Timestamps disproved it:** the patch was built 21:53:49 and
the second failing login was 21:56:36, so the clicks were already dead with the fix in place.
The drag-band patch is still correct (that code genuinely cannot disarm itself without Hyprland)
but it was never this bug. Check *when* a fix landed against *when* the symptom was seen before
crediting it.

---

## BUG-115 — The KWin session felt sluggish: VRR was forced on for the internal panel
# [CHANGE: claude-code | 2026-08-09]
**Status: fixed. The instrumentation answered the open question on 2026-08-10.**

`~/.config/kwinoutputconfig.json` had `vrrPolicy: "Always"` on `eDP-2`. Adaptive sync on a laptop
panel lets the refresh rate follow the content, and a mostly-static desktop drops it to the
panel's floor — which reads as **input lag**, not as a low frame rate. Set to `Never`. This file
is KWin's alone, so it is a true KWin-vs-Hyprland difference and Hyprland never saw it. The
nested test had also left a fake `WL-0` output in there; removed, after asserting it was the last
entry so the positional `outputIndex` in `setups` could not shift.

### Ruled out, with evidence
- **`[Compositing] AnimationSpeed=4` in kwinrc** — looks like "slow animations", is a **dead
  legacy key**. Current KWin reads `animationDurationFactor()`, watched on group `KDE`, key
  `AnimationDurationFactor`, which is `1.0`. Confirmed in upstream `options.cpp`.
- **The GPU** — `eglinfo -B` gives AMD Radeon 780M / Mesa 26.1.6 on the GBM platform. Mesa's EGL
  vendor JSON is present and the dGPU gate only touches `/dev/nvidia*`.

### Were the EGL errors real? No — answered 2026-08-10
Both real logins log `eglInitialize failed` / `EGL_NOT_INITIALIZED` **twice**, which was not
enough to declare software rendering: KWin probes EGL several ways and some probes fail normally.
So the session now asks the compositor directly 8 s in and appends `supportInformation` to
`kwin-render.log`. Two logins later it says, in KWin's own words:

```
Scale: 2            Refresh Rate: 120000      Adaptive Sync: never
Compositing Type: OpenGL
OpenGL renderer string: AMD Radeon 780M Graphics (radeonsi, phoenix, ACO, DRM 3.64, 7.0.5-arch1-1)
OpenGL version string: 4.6 (Core Profile) Mesa 26.1.6-arch1.1
```

Hardware OpenGL on the iGPU, 120 Hz, adaptive sync off — so the VRR change took, the dGPU is not
being held awake, and **the `eglInitialize failed` lines are noise**. Do not chase them again.
Keep the `kwin-render.log` block: it is four seconds of work and it converts "it feels slow" from
an argument into a lookup.

**Unrelated but worth knowing:** the panel is 2880x1800 **@120 Hz** and the *Hyprland* session is
currently running it at **60 Hz**. KWin's saved mode already asks for 120.

---

## BUG-116 — Every Caelestia popup stays locked open on KWin: clicking away is a Hyprland-only protocol
# [CHANGE: claude-code | 2026-08-10]
**Status: fixed in the overlay. Click-outside proven with a real synthetic click; see "What was
actually clicked" for the part that was not.**

Reported as: *"if i open a launcher than if i want to close i will put the curose any thing out of
that are and it has to close but its not its just locked it same for all pops got it volume
brightness notification and more"*.

### Root cause
`modules/drawers/ContentWindow.qml` has exactly **one** code path that closes a drawer when you
click away — `HyprlandFocusGrab.onCleared`, which sets `launcher/session/sidebar/dashboard = false`,
`popouts.hasCurrent = false` and calls `bar.closeTray()`. There is no other. And the shell log has
been saying, verbatim, twice per run since the session was built:

```
WARN: The active compositor does not support the hyprland_focus_grab_v1 protocol.
      HyprlandFocusGrab will not work.
```

`modules/bar/popouts/Wrapper.qml` has a second one for **detached** popouts (the volume,
brightness and notification panels the user was complaining about) — same protocol, same silence.

There are really two layers to the problem, and fixing only one does nothing:

1. **The click never arrives.** The drawers window covers the whole screen but its input mask
   deliberately leaves the middle click-*through*, so a click "outside the launcher" is delivered
   to the app underneath. Upstream does not need to see it; the focus-grab protocol intercepts it
   at the compositor.
2. **Nothing acts on it.** Even with the click delivered, no handler closes anything.

### The trap that cost the first attempt: `focusGrab.active` reads back false forever
The obvious fix is `mask: ... focusGrab.active ? null : regions`. It does not work, and it does not
error. The QML binding *assigns* to `active`, but `HyprlandFocusGrab` drops the write when the
protocol is missing, so the property never changes value and **nothing that depends on it ever
re-evaluates**. Measured, not reasoned: with that version the launcher opened and the debug line
printed `maskIsNull=false` every time.

The same trap explains a line of upstream code that looked fine and is dead here — `dragMaskPadding`
opens with `if (focusGrab.active || ...) return 0;`, which on KWin can never fire.

So the condition is **copied out of** `focusGrab.active` and evaluated in our own property.

### The fix (two patched files, both in `luminos-caelestia-kwin-overlay`)
- `modules/drawers/ContentWindow.qml` — a `luminosGrab` property mirroring `focusGrab.active` plus
  `popouts.isDetached`, and `mask: hasFullscreen ? emptyRegion : (luminosGrab ? null : regions)`.
  A null mask means the whole surface is ours, which is exactly what a focus grab does.
- `modules/drawers/Interactions.qml` — `onPressed` now runs the `onCleared` body (plus
  `popouts.close()`, so a *detached* popout also goes away — clearing `hasCurrent` alone leaves
  `detachedMode` set) when the press is dismissible and lands outside every open panel. The
  geometry test reuses upstream's own `inBottomPanel` / `inTopPanel` / `inRightPanel` /
  `inLeftPanel` helpers so "inside a panel" means the same thing here as it does for hover.

**Accepted cost:** while a drawer is open the shell owns the whole screen, so clicks and scrolls do
not reach the app below. That is not a new bargain — it is what the focus grab did on Hyprland.

### What was actually clicked (and what was not)
Verified in a nested KWin with a real pointer, not by reading the diff:
- launcher open, click at (690, 280) → debug says `dismissible=true onPanel=false`, and
  `drawers isOpen launcher` flips **1 → 0**. Before the `luminosGrab` fix the same click produced
  no press at all.
- Geometry checked against real numbers: with the launcher open the panel measured
  `x 409..1041, y 356..890` on a 1400x900 screen, and `inBottomPanel` computes its threshold as
  `900 - (thickness + 534) = 356` — the panel top exactly.

Not clicked: the **detached popout** path. Nothing in the nested instance would detach one (the
bar icon positions were unknown and probing five points found none), so volume/brightness/
notifications rest on the same mechanism but were not exercised by hand.

### Two testing notes worth keeping
- **`ydotool mousemove --absolute` teleports the cursor to (1,1)** on this setup. Relative moves
  work but are scaled and accelerated: `-x 100` moved 183 logical px. The only reliable method is
  to converge in a loop, reading the truth back from KWin each step via a scripted
  `print(workspace.cursorPos)`. Absolute positioning is not available; do not trust one move.
- **Hover events do not reach the shell in a nested KWin** even though clicks do, so hover-based
  instrumentation silently logs nothing. It works on the real session (that is how the popouts
  open in the first place). Do not conclude hover is broken from a nested test.

## BUG-117 — The `luminos-maximize` KWin script is enabled and has never once loaded
# [CHANGE: claude-code | 2026-08-10]
**Status: open, not fixed. Ruled OUT as the cause of the "apps open fullscreen then jump" report.**

`kwinrc` has `luminos-maximizeEnabled=true`, and every KWin startup logs:

```
KPackageStructure of KPluginMetaData(pluginId:"luminos-maximize", ...metadata.json)
does not match requested format "KWin/Script"
```

`~/.local/share/kwin/scripts/luminos-maximize/metadata.json` has only a `KPlugin` block. A KWin
script also needs `"KPackageStructure": "KWin/Script"` and an `X-Plasma-API` entry, so KPackage
refuses it. The script — "maximize toggles to 80% centered" — has therefore never run, in any
session, while the settings UI happily shows it ticked. Another entry for the
"reports success, does nothing" list.

It was the first suspect for *"the apps ... open in full screen mode and than crash and try to
reopen in hyperland style the split"*, because 80%-centered-on-unmaximize is exactly that shape.
It is not the cause: it does not load. Also ruled out for that report, with evidence:
- **No app crashes.** `coredumpctl --since -3h` lists only three `spectacle` SIGABRTs, which were
  mine (that is also why screenshots kept silently producing no file).
- **No tiling is armed.** The four `[Tiling]` blocks in `kwinrc` are KWin's stock 25/50/25 custom
  layout, inert unless you drag with Shift. `kwinrulesrc` holds one unrelated Wine rule.
- **A control window behaves.** Launching `kitty` under a KWin script watching `windowAdded` and
  `frameGeometryChanged` gave `geo=448,41 594x818 fs=false tile=no` and then no geometry churn at
  all — normal centred placement, no maximize, no jump.

So the remaining hypothesis is app-specific state restore (a window that was fullscreen/tiled under
Hyprland asking for that geometry back). Needs the name of one app that does it.

## BUG-118 — luminos-ram has never discarded a single browser tab, and has said so every 60 seconds since June
# [CHANGE: claude-code | 2026-08-11]
**Status: root-caused. Superseded rather than repaired — see DECISION 65.**

`cmd/luminos-ram/main.go:288 checkCDPHealth()` polls `http://localhost:9222/json/list`, and on
failure logs and retries forever:

```
Aug 11 18:46:15 archlinux luminos-ram[775]: [ERROR] Chrome CDP unavailable (port 9222) - retrying in 60s
```

**339 of those in the last 24 hours. The first is `Jun 26 12:50:54`.** Nothing has ever listened on
9222: `ss -ltn` shows the port closed and no `DevToolsActivePort` file exists in the profile.

The cause is already written down in BUG-102 as a footnote — *"`--remote-debugging-port=9222` is now
dead on Chrome's default profile"* — because Chrome 136+ refuses DevTools when the data dir is the
default one. `/usr/local/bin/chrome-luminos` still passes the flag (lines 171 and 204); Chrome still
ignores it. What nobody connected at the time is what **else** hangs off that port:

- `checkCDPHealth()` `return`s only on success, so it never reaches `scanAndCompressChrome()`.
- `manageChromeMemory()` / `discardBrowserTabs()` (main.go:739-807) are therefore unreachable.
- `docs/LUMINOS_RAM_ARCHITECTURE.md` advertised **"Browser Tabs: Discard via CDP (freed 100%)"** as
  the 15-minute rule for the single largest memory consumer on the machine. It has been false since
  at least 2026-06-26.

**Second-order damage:** the same loop runs `luminos-brain log "Chrome CDP unavailable"` on every
failed pass, so the brain log has been taking a junk entry a minute for six weeks.

**What was NOT wrong.** The rest of luminos-ram is fine — `/meminfo` serves live numbers and
`process_madvise` works (BUG-065/066/067). Only the browser arm is dead. And the ordinary
`MADV_PAGEOUT` path does still touch Chrome renderers as generic processes; it just pushes them to
zram instead of freeing them, which is a fraction of the win a discard gives.

**Why it is not being fixed in Go.** Reopening CDP means running the everyday browser on a
non-default `--user-data-dir` purely so a daemon can talk to it — a large, permanent change to how
the user's browser starts, to regain a capability the browser will hand over for free to an
extension. Replaced by `scripts/chrome-tab-sleeper` v2.0, which reads the same `/meminfo` the RAM
widget reads. See DECISION 65.

**Left in place on purpose:** the Go code and the 60s log line. Ripping out `manageChromeMemory()`
touches `cmd/` (AGENTS.md §11, "only when explicitly instructed") and the log line is now the honest
statement of a known-dead path. Muting it is a one-line change whenever Shawn wants it.

## BUG-119 — a model offload took the whole machine down with 8 GB of swap sitting free
**Status: FIXED 2026-08-07** · `scripts/jobhunt/llm-server.sh`, `scripts/luminos_moe_offload.py`

Loading the 26B MoE with its experts offloaded to system RAM produced a **kernel panic**, not an
OOM kill:

```
unevictable:14512768kB   mlocked:12347344kB
Free swap  = 8041640kB        <-- 8 GB of spill space, never touched
Out of memory and no killable processes...
Kernel panic - not syncing: System is deadlocked on memory
```

Two separate faults, and it is worth keeping them apart.

**The architectural one.** llama.cpp hands CPU-side offloaded weights to CUDA as **pinned**
(page-locked) host memory via `cudaHostRegister`, so the GPU can DMA them across PCIe without a
bounce buffer. Pinned pages cannot be swapped or evicted, ever. That silently deletes the bottom
tier of this box's VRAM → RAM → NVMe hierarchy: for those weights RAM stops being a spill point
and becomes a hard wall. 14.5 GB of the machine's 15.3 GiB was locked down while a full 8 GB of
swap sat untouched, because not one page was legally movable.

Fixed with `GGML_CUDA_NO_PINNED=1`, confirmed present in the `venv-jobhunt` build. Weights become
ordinary pageable memory; transfers cost more, the machine survives. Verified by measurement, not
assertion — `Unevictable` held at **3 MB** through a full load, against **14.5 GB** before.

**The self-inflicted one.** The process had been OOM-killed twice, so it was given
`oom_score_adj = -1000` to stop that. That is what turned a survivable kill into a panic: the
kernel went looking for something to kill and found every candidate protected. The OOM kills were
the *diagnosis* — a model that did not fit — and disabling the safety net treated them as the
obstacle. **Never do this.** Same reasoning applies to `earlyoom`'s exempt regex.

**The third failure, once the first two were fixed.** With paging working, `earlyoom` SIGTERMs the
largest process at *mem avail ≤5% AND swap free ≤90%*, killing the model at 12.4 GB RSS. It leaves
**no traceback and nothing in the process's own log**, so it reads as a crash inside llama.cpp. It
is not. Check `journalctl -u earlyoom` before debugging the library.

**Root cause under all three: the file was too big.** `Q4_K_XL` is 15.84 GiB and needs ~12.4 GB
resident. `IQ4_XS` is 12.66 GiB and needs ~8.2 GB, which coexists with a browser. See DECISION 67.

**Guard added:** `llm-server.sh` now refuses to start when the model exceeds free RAM + swap, and
prints the shortfall instead of taking the box down.

## BUG-122 — the hover launcher on the Plasma shell has no way to close, and both panels float 10px off the edge
<!-- [CHANGE: claude-code | 2026-08-13] Filed as BUG-120 on 2026-08-13 and renumbered
     the same day: 120 and 121 were already taken by the Chrome-hang and dead-media-keys
     reports in the Open Bugs section above. Same renumbering mistake BUG-092 records. -->

# [CHANGE: claude-code | 2026-08-13]
**Status: FIXED 2026-08-13** · `config/quickshell/caelestia-bar/shell.qml`

Reported as: *"the hover launcher should go back when i click any where else. but it snot it just
stuck also can you make it stick to corners both the top dashboad and bottom app launcher"*.

### Why BUG-116 did not already cover this
BUG-116 is the same disease and its cure does not reach here. That fix lives in
`luminos-caelestia-kwin-overlay`, patching upstream's `ContentWindow.qml` and `Interactions.qml`.
DECISION 68 moved us onto full Plasma with our **own** `shell.qml`, which builds the drawers itself
and loads neither patched file. The overlay is still correct for what it patches; it simply is not
in this path.

### Root cause — one thing, not two
`HyprlandFocusGrab.onCleared` (`ContentWindow.qml:112-135`) is the **only** code upstream has that
closes a drawer on a click elsewhere. It is `hyprland_focus_grab_v1`, and KWin does not implement
it:

```
$ strings $(which kwin_wayland) | grep -c hyprland_focus_grab
0
```

So on this machine that handler is dead code. `Interactions.qml:200-202` opens the launcher on
hover with a bare `if` and no `else`, because upstream does not need one. Our shell copied that
asymmetry, so the launcher had no way out but Escape, Meta+P, the logo button, or launching
something.

**Correction to an earlier note in this file.** BUG-116 lists "the click never arrives" as a
separate layer. It is not a second cause — `Regions.qml` shows the root region is
`Intersection.Xor` with the panels `Subtract`ed, so **upstream cannot see a click in the middle of
the screen either**. It never needed to. Nothing is being blocked: Wayland only delivers a click to
the surface under the pointer, so the shell is simply never told one happened.

### The fix — no new windows, no new mechanism
Mirrors the pattern already proven for the dashboard and the OSD in this same file:

- `launcherHovered` ORs the bottom tripwire's `MouseArea.containsMouse` with a `HoverHandler` on
  the launcher window. The strip and the launcher are two surfaces and the pointer is only ever on
  one; without the OR, reaching for the search box reads as a leave.
- `onLauncherHoveredChanged` supplies the missing `else`, gated by a `launcherOwnedByHover` flag —
  only hover may close what hover opened, so a launcher opened by Meta+P or the logo button with
  the pointer parked elsewhere is not killed by the next stray mouse move.
- The old edge-triggered open handler on the strip is gone. It existed so a pointer resting on the
  strip could not instantly undo Escape; with the margin deleted (below) the launcher now covers
  the strip whenever it is open, so that hazard cannot arise.

**Accepted cost:** hover it open, then move the pointer off it while typing, and it closes under
you. Keyboard-opened ones are safe. This is the price of not adding a full-screen click-catcher
window, which was considered and rejected as more machinery than the problem is worth.

### The 10px gap, same root, different symptom
Both panels carried `margins.{top,bottom}: Config.border.thickness`, copied from upstream. Upstream
earns that gap: it paints a 10px frame around the entire screen (`BlobInvertedRect`), and the
panel's edge meets the frame's edge. We paint no such frame, so the margin was just 10px of
desktop showing through — visible as YouTube content in a band under the launcher's search box.
Margins deleted; the two corners that now touch the screen edge are squared off, since a rounded
corner there would show the same sliver.

### The trap that made every earlier test lie
`shell.qml:49` sets `settings.watchFiles: false`. **Quickshell hot-reload is off in this config.**
Edits change nothing until the process is restarted, and the old behaviour is a perfectly plausible
"the fix did not work". Restart with `kill <qs pid>` — `~/.local/state/luminos/caelestia-plasma/
shell.sh` supervises it and restarts on any non-zero exit, so SIGTERM (rc=143) reloads it and a
clean rc=0 does not.

### Verified by hand on the live session
Synthetic pointer via ydotool, position read back from KWin each step, state read from
`qs ... ipc call drawers isOpen launcher`, plus screenshots:
- bottom strip → launcher **opens**; walk up into its body → **stays open**; leave it → **closes**
  (`isOpen` 1 → 0). This is the behaviour that did not exist before.
- opened by IPC with the pointer far away, then jiggled around the screen → **stays open**
  (ownership flag doing its job). Escape then closes it.
- logo button toggles open and closed; dashboard hover open/close unaffected; volume OSD unaffected.
- screenshots confirm both panels now sit flat on their screen edge, with no desktop showing.

---

## BUG-123 — the dashboard stutters when you switch tabs (Caelestia on Plasma)
**Status:** FIXED — 2026-08-13 · **Component:** `config/quickshell/caelestia-bar/shell.qml`

### The symptom, narrowed down by the user
"It only stutters when I switch from Weather to Media to Performance to Dashboard. It stutters in
animation." Not the drop-down, not the drop-up — the **tab switch**, and only in the dashboard.
The user also noted this never happened in the Hyprland session, which was the clue that mattered:
it is not the machine, it is this port.

### An earlier diagnosis in this project was wrong
A previous pass blamed the CPU governor and the iGPU sitting pinned at 800 MHz of 2700. Those are
real (measured: CPU capped at 3.12 GHz of 5.14, EPP `balance_power`, iGPU 23–27% busy and never
ramping) and they make everything a bit worse, but they are **not** this bug. Refresh rate is
identical between the two sessions (`hypr-user.lua:75-80` is `2880x1800@120, scale 2`, same as
KWin's), and KWin blur, HDR, VRR, plasmashell CPU and log spam were all ruled out by measurement.

### Root cause — one line, and it is ours, not upstream's
Upstream's `modules/dashboard/Content.qml:190-196` deliberately animates the dashboard's own size:

```qml
Behavior on implicitWidth  { Anim {} }
Behavior on implicitHeight { Anim {} }
```

That is how the panel grows and shrinks smoothly between tabs, and it is fine upstream, because
upstream's `ContentWindow` is **the whole screen and never resizes** — only the Item inside it does.

This port gave the dashboard a window of its own and sized the window to the panel:

```qml
anchors.top: true
implicitWidth:  dashboardPanel.implicitWidth    // ← animated
implicitHeight: dashboardPanel.implicitHeight   // ← animated
```

So the **layer-shell surface itself was resized on every frame of the tab animation** — a configure
round trip with the compositor and a new render target, per frame. The animation the resizing was
supposed to follow is the thing it stalled.

**Measured**, with a temporary counter on the window's `widthChanged`/`heightChanged` and a timer
cycling `screenState.dashboardTab` 0→1→2→3:

| tab switch | surface resizes (before) | after |
|---|---|---|
| → Media | 26 | 0 |
| → Performance | 24 | 0 |
| → Weather | 38 | 0 |
| → Dashboard | 12 | 0 |

### The fix — copy upstream's shape, which was right all along
`ContentWindow.qml:73-79`: cover the whole screen, never resize, and use a `mask` so only the
panel's rectangle takes pointer input.

```qml
anchors.top: true
anchors.bottom: true
anchors.left: true
anchors.right: true

mask: Region { item: dashboardPanel }
```

The `HoverHandler` moved off the window and onto `dashboardPanel`. On a full-screen window it would
have reported "hovered" everywhere and the dashboard would never have closed on unhover.

### This does NOT bring back the swallow-the-screen bug
Full-screen shell surfaces are exactly what the separate-windows design was adopted to escape, so
this was tested rather than argued. With the dashboard open, a `Region` masked to the panel:
- moving the pointer over an unrelated window's sidebar **renders its hover highlight** — proof the
  compositor is delivering pointer events there, and a Wayland input region governs hover and
  clicks identically;
- a click into another window's text field **placed the caret**;
- `isOpen dashboard` stayed 1 throughout, so wandering outside the panel does not close it.

The old bug was a surface with **no** mask. The window size was never the problem; the input region
was.

### Also verified
- hover the top edge → opens (`isOpen` 0 → 1); move away → closes (1 → 0), with the handler in its
  new home on the panel;
- clicking the Performance tab switches and the wider pane draws in full — the mask tracks the
  panel as it grows, so the tab row stays clickable at the new width;
- launcher toggle unaffected.

### Still open, separately
The remaining ~90 ms hitch on every dashboard **open** is a different thing: `Wrapper.qml`'s
`Loader.active` destroys the content on close and rebuilds it on open. And the Media tab's
`CoverVisualiser` rebuilds one `ShapePath` per bar per cava frame, which is what puts that tab at
~66% of a core. Neither is fixed here.

---

## BUG-124 — notifications arrive, are stored, and never draw (Caelestia on Plasma)
**Status:** FIXED — 2026-08-13 · **Component:** `config/quickshell/caelestia-bar/shell.qml`

### The symptom
`notify-send` returns rc=0. `busctl --user list` shows `org.freedesktop.Notifications` owned by
`qs`, so the D-Bus server is genuinely ours. The notification is written to
`~/.local/state/caelestia/notifs.json`. And **nothing appears on screen**. No error, no warning, no
log line — the toast simply does not exist.

This is the failure mode that keeps costing days in this port: everything reports success.

### Root cause — a ListView that is too short to lay out, and a height that only re-reads on `count`
Three upstream lines have to line up for this, and in this port they do.

**1.** `notifications/Content.qml:29-57` computes its height by *calling a function*:

```qml
implicitHeight: {
    const count = list.count;
    if (count === 0)
        return 0;
    let height = (count - 1) * Tokens.spacing.medium;
    for (let i = 0; i < count; i++)
        height += (list.itemAtIndex(i) as NotifWrapper)?.nonAnimHeight ?? 0;
    ...
}
```

`itemAtIndex()` is a method call, not a property read, so QML registers **no dependency on it**. The
only reactive thing in that whole block is `list.count`. The binding therefore re-runs on exactly
one signal: `countChanged`.

**2.** `notifications/Wrapper.qml:13` is `visible: height > 0`.

**3.** So with an empty list the panel is invisible, and the ListView inside it is born **-27 px
tall** (padding arithmetic on a zero height). **A ListView that is invisible and has a negative
height never runs its layout pass.** On a model insert it creates no delegate — and because no
delegate was created, it never emits `countChanged`.

That closes the loop:

> no layout → no delegate → no `countChanged` → the height binding never re-runs → height stays 0 →
> the panel stays invisible → the view is never laid out.

**Measured, live**, with a temporary IPC probe: after one `notify-send`, `list.count` reads **1**
(that query goes straight to the model, bypassing the view) while `contentHeight` is **0** and
`contentItem.children.length` is **0**. The model has the row. The view has never looked at it.

### Why upstream never trips it
Upstream puts every panel in **one full-screen window** shared with the bar and the border, which
repaint constantly. That traffic keeps the layout pass running, so the view is always laid out and
the deadlock has nothing to bite. This port gives each panel its own window; a window with nothing
in it does nothing at all. Same class as BUG-123: **upstream code written for a single always-busy
sheet, moved into a window of its own.**

### Two theories that were wrong, recorded so they are not re-tried
- **"The height is negative, make it zero."** Set `anchors.topMargin: 22` so the ListView started at
  0 px instead of -27. Measured: still no delegate. A non-negative height is **not** sufficient —
  the view has to actually be laid out. Reverted.
- **"The `Behavior` animation driver has stalled."** Disproved by forcing the value: it read 0
  immediately and 400 two seconds later, i.e. the animation runs normally.

Also worth knowing: the binding **short-circuits on `if (count === 0) return 0;`** before it ever
touches `screenState.osd` / `session` / `utilities`, so those dependencies are never registered
either. Proven by toggling `screenState.session` from outside and watching nothing happen.

### The fix — one kick, in our file, upstream untouched
`ListView.forceLayout()` runs the layout pass on demand. Hang it off the one signal that *is*
reliable, the service's own:

```qml
Connections {
    target: Notifs
    function onPopupsChanged(): void {
        Qt.callLater(notifWindow.layOutNotifs);
    }
}
```

Upstream gives the ListView an `id` but no way to reach it from outside, so `layOutNotifs()` walks
`notifPanel`'s children looking for **anything with a `forceLayout` method**. Searching for the
capability rather than a fixed path of child indices means an upstream reshuffle makes this find
nothing — the same as today's behaviour — instead of silently grabbing the wrong item.

### Measured, before and after
| state | popups | window visible | panel height | list contentHeight | delegates |
|---|---|---|---|---|---|
| idle | 0 | false | 0 | 0 | 0 |
| one notification, **before** the fix | 1 | false | 0 | 0 | 0 |
| one notification, **after** | 1 | true | 88 | 66 | 1 |
| burst of 3 more | 4 | true | 322 | 300 | 5 |
| after they expire | 0 | false | 0 | 0 | 0 |

### The other half: getting the D-Bus name at all
Only one process can own `org.freedesktop.Notifications`. plasmashell claims it at login **without
the ALLOW_REPLACEMENT flag**, so Quickshell's `RequestName` comes back with reply code 3 (EXISTS)
and is simply refused. Quickshell has no "replace" option and cannot force a takeover — but it does
watch `NameOwnerChanged` and retry the moment the name is released. So the handover is one restart:

```bash
systemctl --user restart plasma-plasmashell.service
```

**Verified that plasmashell does not steal it back:** with `qs` holding the name, plasmashell was
restarted (came back as a new PID) and `qs` still owned it afterwards. `scripts/luminos-caelestia-plasma`
now does this once at login, **conditionally** — if Caelestia already owns the name it does nothing,
and if the handover fails it logs and stops rather than looping, leaving Plasma drawing notifications
and the desktop intact.

### Input region
The window covers the output and never resizes (BUG-123's shape, because `Content.qml` animates
`implicitHeight`), masked with `mask: Region { item: notifPanel }`. It is **also** gated on
`visible: Notifs.popups.length > 0 || notifPanel.visible`, so it is not even mapped while idle.
"An empty Region yields an empty input region" is probably true, but it is not worth betting the
whole screen on when not mapping the surface costs nothing.

### Seen on screen — 2026-08-13
Confirmed in pixels once the session was genuinely unlocked. A `notify-send` produced a toast at the
top right: icon, title row, body text, chevron, all legible in an `-pix_fmt rgb24` crop. Roughly nine
seconds later it was gone and Chrome's own window buttons were visible in exactly that spot, which is
the useful half — it proves nothing is left covering the corner.

Two traps in the *verification*, both of which produced a confident wrong answer first:
- `loginctl` session **1** is `Class=manager` and always reports `LockedHint=no`. The real session is
  **3** (`Type=wayland, Class=user`). Checking the wrong one says "unlocked" while the lock screen is
  up and every screenshot comes back black.
- `spectacle -b -n -o` PNGs carry an alpha channel; re-render with `ffmpeg -pix_fmt rgb24` before
  believing what you see.

---

## BUG-125 — the sidebar drawer opens in state but never on screen (Caelestia on Plasma)
# [CHANGE: claude-code | 2026-08-13]
**Status:** ✅ Fixed 2026-08-13 · **Component:** `config/quickshell/caelestia-bar/shell.qml`

### Symptom
`qs -p … ipc call drawers toggle sidebar` returned cleanly, `ipc call drawers isOpen sidebar`
answered `1`, and the screen showed nothing at all. No error, no warning in the shell log.

### Root cause — QML `visible` is *effective* visibility, so reading a child's is circular
The notification window is gated so it is not mapped while idle:

```qml
visible: Notifs.popups.length > 0 || notifPanel.visible
```

Adding the sidebar, the obvious third term is `|| sidebarDrawer.visible`. It cannot work. In QML,
`visible` is **inherited**: a child of a hidden parent reads back `false` no matter what its own
binding says. So the window is hidden → the child reads hidden → the window stays hidden. Nothing
ever breaks the loop.

The notification term only *looks* like the same thing. It works because of the term next to it:
`Notifs.popups.length` is a service property that owes nothing to the window, so it flips first and
maps the surface; `notifPanel.visible` is then merely a **hold**, keeping the window up through the
collapse animation on the way back down. A hold with no bootstrap is a deadlock.

### Fix
Use the panel's own intent, not its rendered state:

```qml
visible: Notifs.popups.length > 0 || notifPanel.visible
      || sidebarDrawer.shouldBeActive || sidebarDrawer.visible
```

`shouldBeActive` is upstream's own `screenState.sidebar && Config.sidebar.enabled`
(`modules/sidebar/Wrapper.qml`) — plain properties, no window in the chain. It bootstraps; `.visible`
holds through the slide-out.

### The rule
**Never gate a window on a descendant's `visible`.** Every such binding needs two terms: something
outside the window's own visibility chain to turn it on, and the child's state to keep it on.

### Why the sidebar is safe to anchor to, and the notification panel is not
`sidebar/Wrapper.qml` has a **constant** `implicitWidth` and slides by animating
`anchors.rightMargin` through `offsetScale`. It never resizes, so BUG-123 (a `wl_surface` resized
every frame) cannot recur here. It also lives in the **same** window as the toasts on purpose:
upstream anchors it to the notification panel's bottom edge (`drawers/Panels.qml:145-154`), and
anchors do not cross windows.

### Two smaller things found on the way
- **`sidebarPanel: sidebarPanel` is a self-binding.** Name resolution checks the scope object's own
  properties *before* component ids, so the right-hand side resolves to the property being assigned,
  not to the `id`. The drawer is `id: sidebarDrawer` for that reason.
- **The shell is supervised.** `~/.local/state/luminos/caelestia-plasma/shell.sh` re-runs `qs` in a
  loop on any non-zero exit, so `kill <qs-pid>` **is** the restart (`settings.watchFiles: false`
  means every edit needs one). Launching `qs` by hand on top of that gives two shells drawing two
  bars — the tell is a doubled bar down the left edge.

---

## BUG-126 — a global shortcut keeps running the OLD command after you edit its .desktop
*[CHANGE: claude-code | 2026-08-13]* — **FIXED 2026-08-13**

**Symptom.** Meta+N did nothing. The key was in `~/.config/kglobalshortcutsrc`, the `.desktop` file
had the right `Exec=`, and editing the file changed nothing at all — including after
`kbuildsycoca6 --noincremental`.

**What it actually was.** KDE caches every `.desktop`'s `Exec` line in **ksycoca**, and the shortcut
service keeps using the cached copy. The journal is where it admits this:

```
qs[85453]: No running instances for ".../caelestia-kwin/shell.qml"
```

— a path that had **already been edited out of the file**. The rebuild did not dislodge it. A **new
filename** did: `net.local.luminos-cael-sidebar.desktop`, plus
`unregister("luminos-cael-sidebar.desktop", "_launch")` and stripping `X-KDE-Shortcuts` from the old
file so it cannot re-register at the next login.

### Three things worth keeping, each of which cost a wrong turn

- **KWin owns the global-shortcut server in Plasma 6.7, not kglobalaccel.** `org.kde.kglobalaccel`
  is owned by `kwin_wayland`; `plasma-kglobalaccel.service` reads `inactive` and is a dead stub.
  "Restart kglobalaccel" is a **no-op**, and it looks exactly like a fix that did not take.
- **`X-KDE-Shortcuts=` is the line that makes a `.desktop` register at all.** A probe file without it
  never produced a component. That is the autoloading trigger, not `X-KDE-GlobalAccel-CommandShortcut`.
- **`invokeShortcut` is the perfect non-intrusive test** — it is the exact call KWin makes when the
  key fires, so it separates "the key is not reaching the action" from "the action does not work":

  ```bash
  busctl --user call org.kde.kglobalaccel /component/<mangled_desktop_name> \
      org.kde.kglobalaccel.Component invokeShortcut s "_launch"
  ```

  And to check the **key** side, which is the half `invokeShortcut` skips:

  ```bash
  # who holds this key? Meta+N == Qt::MetaModifier|Qt::Key_N == 0x1000004E == 268435534
  busctl --user call org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel \
      getGlobalShortcutsByKey i 268435534
  ```

  ⚠️ `shortcutKeys` takes a **four**-element action id
  (`component`, `action`, `componentFriendly`, `actionFriendly`). Passing three returns an **empty
  list with no error**, which reads exactly like "the shortcut is not registered" — it fooled me into
  thinking a working Meta+Space was broken too. Cross-check any such answer against a shortcut you
  know works before believing it.

---

## BUG-127 — a KWin effect that is installed, enabled and healthy, and silently does nothing
*[CHANGE: claude-code | 2026-08-13]* — **FIXED 2026-08-13**

**Symptom.** `kwin-effect-rounded-corners` 0.8.7-1 was installed and enabled in
`kwinrc [Plugins]`. Windows stayed square. `isEffectLoaded` returned false and
`isEffectSupported kwin4_effect_shapecorners` returned **false** — with no
explanation anywhere.

**Everything that should have reported it, didn't:**

- `journalctl --user -u plasma-kwin_wayland` — **not one line** about the effect.
- `ldd` on the plugin `.so` — **no missing libraries**. Everything resolved.
- The blur effect returned `isEffectSupported` = true from the same call, and
  OpenGL was healthy (kwin 6.7.4, radeonsi/phoenix, Mesa 26.1.6, GL 4.6 Core),
  so "supported = false" looked like a driver or capability problem and it was
  neither.

**What it actually was.** An **ABI break**. A five-line C probe that just called
`dlopen(..., RTLD_NOW|RTLD_LOCAL)` on the plugin and printed `dlerror()`:

```
undefined symbol: _ZN4KWin6Effect14prePaintScreenERNS_18ScreenPrePaintDataENSt6chrono8durationIlSt5ratioILl1ELl1000EEEE
```

`KWin::Effect::prePaintScreen` changed signature. The package was built in **May
2026** against the older KWin; we run 6.7.4. KWin's plugin loader catches the
failure and reports it as "not supported", which is true and useless.

**Fix.** Built AUR **0.9.0-3** from its PKGBUILD and installed it.
`isEffectSupported` then returned true and the journal started logging
`ShapeCorners: shaders loaded.`

**The lesson worth keeping.** `ldd` only checks that the **libraries** are
findable; it does not check that the **symbols inside them** still exist. When a
plugin is "unsupported" for no visible reason, `dlopen` it by hand — it is the
only thing that prints the real error. Applies to every KWin effect, every Qt
plugin and every Plasma applet after a system upgrade.

**Related.** DECISION 71 (what the effect was being installed for) and
`reference_linux_silent_failures` — this is the same shape as the rest of that
list: a tool that reports success, or reports a plausible wrong reason, while
doing nothing.

## BUG-132 — the model picker only ever listed ONE model, because the HIVE window landed on the wrong URL
*[CHANGE: claude-code | 2026-08-16]* — **FIXED 2026-08-16**

> **Renumbered from BUG-128 on 2026-08-16.** This file runs two number sequences
> at once — Caelestia work files into *Open Bugs* at the top, HIVE/LLM work
> appends down here — and both reached 128 and 129 on the same two days. The
> Caelestia entries were filed first (2026-08-15) so they keep the numbers.
> Anything elsewhere that says "BUG-128" about the model picker means this entry.
> **Before filing the next bug, run `grep -oP '^#{2,3} BUG-\K[0-9]+' docs/BUGS.md
> | sort -n | tail -1` — reading only one section of this file will collide again.**

**Symptom.** Two models were configured and only one appeared in HIVE's model
picker. The one that showed was labelled with its raw id — `luminos-local ·
luminos` — instead of the friendly name in the config. Pressing **Ctrl+R** made
both appear, correctly named, every single time.

**Everything on the config side checked out, four separate ways:**

- `~/.openclaw/openclaw.json` — both models under `models.providers.luminos`.
- `openclaw models list` — both listed, `luminos-local` tagged default.
- `~/.openclaw/agents/main/agent/models.json` — both.
- `curl 127.0.0.1:8082/v1/models` — `['luminos-local', 'luminos-local-moe']`.

The gateway had hot-reloaded after the edit (`[reload] config hot reload applied
(models.providers.luminos.models)` at 12:27:59) and, captured off the wire, was
sending **both** models with `available: true`. So the data was right at every
layer and the UI still drew one row. That is what made this look like a config
problem for so long, and it never was one.

**Cause.** `HiveWeb.qml` opened the gateway **root** (`/#token=…`) and let the
React app route itself to `/chat`. The Control UI builds its picker from the
catalog delivered on `chat.startup` / `chat.metadata`, and it only sends those
two calls when the session is named in the query string at load time. Measured
over the DevTools protocol, cold boot of the same window:

| landing URL | RPCs the page sends |
|---|---|
| `/` | `connect` — and nothing else |
| `/chat` | `connect` — and nothing else |
| `/chat?session=agent%3Amain%3Amain` | `connect`, `chat.startup`, `chat.metadata` |

With no catalog, the picker falls back to rendering the *current* model as its
only entry, labelled `id · provider` because it has no name to use. Ctrl+R fixed
it because by then the URL had been rewritten to `/chat?session=…`.

**Nothing reported it.** The sidebar filled in (`sessions.list` is unrelated and
works either way), the connection dot went green, the console logged no error,
and the gateway logged a healthy client. Another entry for
`reference_linux_silent_failures`.

**Fix.** `src/hive/HiveWeb.qml` now lands on
`/chat?session=agent%3Amain%3Amain` with the token fragment appended. Verified
cold, with no reload: the picker lists **Qwen3 4B Instruct** and **Gemma 4 26B
A4B MoE**.

**Labelled haste.** `agent:main:main` is hardcoded. `openclaw.json` has exactly
one agent, so it is right today and wrong the day a second is added. The smart
version asks the gateway for its default session key first, which needs a
WebSocket round trip from QML.

**How this was found, worth keeping.** `QTWEBENGINE_REMOTE_DEBUGGING=9333` on
the qml6 process exposes a normal Chrome DevTools endpoint for the embedded web
view — the live DOM, the console, and every WebSocket frame. It is the only way
to tell "the server sent the wrong thing" apart from "the client asked the wrong
question", and here it was the second one.

**Related.** DECISION 71 and 73 (why HIVE is a web view at all), BUG-102.

---

## BUG-133 — tool calling was dead for both Gemma models, and reported success
**Status:** FIXED — 2026-08-16
**Component:** `scripts/jobhunt/toolcall-proxy.py` (port 8082)
**Renumbered from BUG-129 on 2026-08-16** — see the note under BUG-132 above.

**Symptom.** Ask the local model to use a tool and it answers like a normal chat
turn. No error, HTTP 200, `finish_reason: "stop"` — and the tool call sitting in
the message body as text the client has no reason to read:

```
content:    '<|tool_call>call:get_weather{city:<|"|>Toronto<|"|>}<tool_call|>'
tool_calls: null
```

**How long, and what actually broke it.** Since **DECISION 74 (2026-08-14)**, when
gemma-4-26B became a served model. Not caused by DECISION 75's swap of the small
slot — the E4B and the 26B were measured failing *identically*, which is what
proved the age of it. Before that the only served model was Qwen3-4B, whose
dialect is the one the proxy was written for.

**Cause.** `toolcall-proxy.py` existed because llama-cpp-python does not parse the
model's tool syntax. It knew exactly one dialect — Qwen's `<tool_call>{json}
</tool_call>`. Gemma emits `<|tool_call>call:NAME{key:VALUE}<tool_call|>`, where
values are not JSON: strings are fenced with the literal token `<|"|>`, and
`true`/`false`/`null`/numbers are bare. It matched no pattern and fell through as
prose.

**Why this hid.** Every layer reported success. The model did its job. The server
did its job. The proxy did what it was told. Only the client, which never asked a
question, could have noticed — and an agent that receives prose instead of a tool
call simply answers from what it already knows, which reads like a slightly
unhelpful model rather than a broken pipeline.

**The round trip is the real difficulty, and the two layers contradict each other.**
MEASURED against llama-cpp-python 0.3.34 with the Gemma 4 template:

| what was sent back | result |
|---|---|
| `assistant.tool_calls`, `arguments` as a **dict** | **500** — request schema rejects it; `ChatCompletionMessageToolCall.function.arguments` must be a `str` |
| `assistant.tool_calls`, `arguments` as a **string** | **500** — the GGUF template itself raises: *"arguments must be a JSON object (mapping), not a string"* |

There is no value that satisfies both. Structured tool calls **cannot** be handed
back to this server at all, so replaying history has to go back as text in the
model's own dialect. That is what the proxy's `normalize_request` does, and it is
not merely a workaround for `content: null` as the old comment claimed.

**A second silent failure rides along.** A standalone `role: "tool"` message
**validates fine and is then discarded by the template.** Gemma's message loop
opens with `{% if message['role'] != 'tool' %}`, and tool results are rendered
only by a forward-scan from an assistant turn that still carries `tool_calls` —
which the paragraph above forces us to strip. Leave the tool message in place and
the model answers as if the tool never ran. No error, anywhere. The fix folds the
tool results into the same assistant text as the calls.

**Fix.** Both dialects are parsed on the way out; the way back in emits Gemma's.

- **A regex cannot parse the Gemma form.** `\{(.*?)\}` stops at the first `}`, so
  any nested object silently truncates the arguments — and a call made with half
  its arguments is worse than no call. Replaced with a small recursive-descent
  reader that is strict on purpose: anything it cannot read is left as text rather
  than guessed at.
- Argument keys are emitted `sorted()` to match the template's `| dictsort`.
- The Qwen parser is kept. It costs nothing and is already proven; nothing on this
  box currently serves a Qwen.

**Proven end to end, not asserted.** Turn 1 returns
`finish_reason: "tool_calls"` with a real `tool_calls` array and `content: null`;
turn 2 replays that history plus the tool result and the model answers *"The
weather in Toronto right now is 18C and sunny, with a wind speed of 12 km/h."*
Confirmed on **both** `luminos-local` and `luminos-local-moe`. Plain chat with no
tools was re-tested for regression. Unit-tested besides: nested objects, arrays,
booleans, numbers, nulls, two calls in one reply, Qwen's form, plain prose
containing `{braces}`, and a deliberately malformed call — which correctly
produces **no** tool call rather than an invented one.

**How to spot the next one of these.** `finish_reason: "stop"` on a request that
carried a `tools` array, with tool-ish punctuation in `content`, means the parser
does not know the model's dialect. Print the raw `content` — the model is usually
doing exactly the right thing in a format nothing downstream reads.

**Related.** DECISION 74 and 75 (which models are served), BUG-097 (the real fix
is llama.cpp's own `llama-server --jinja`, which parses this natively; this file
should be deleted, not maintained, once that binary starts).

---

## BUG-134 — Dolphin "took forever and never replied" because its context did not fit on the card
**Status:** FIXED — 2026-08-17
**Component:** `scripts/jobhunt/systemd/jobhunt-llm.service`, `scripts/jobhunt/llm-server.sh`, `scripts/jobhunt/openclaw-provider.json5`

**Symptom, in Shawn's words.** *"it's just taking too long to load and is not
replying on openclaw nor the server thing."* Two symptoms, one cause.

**Cause.** `luminos-dolphin` was added on 2026-08-16 at **36,864 context, 20 GPU
layers, q8_0 KV**. That does not fit:

```
4685 MiB weights + 2448 MiB KV (36864 tok, q8_0) = 7133 MiB   card has 6141 MiB
```

`LLM_NGL3=20` is what made it load anyway — **13 of its 33 layers computing on
the CPU, once per token**. Measured **7.13 tok/s** against Gemma's 51.37 on the
same port. Nothing was broken; the numbers were simply impossible.

**Why "not replying" looked separate.** Two things stacked on top of the slowness:
a 7,816-token prompt came back with a **2-token** reply, because Dolphin's bare
ChatML template never reads the `tools` variable, so tool schemas are rendered
into nothing and the model has no idea it was asked to act (see BUG-133 — the
proxy's `normalize_request` also rewrites history into Gemma's dialect
unconditionally, which this model does not speak). And every switch between
Dolphin and Gemma is a full unload + reload of 4.92 GB with mmap off.

**Fix.** 16,384 context, **all 33 layers on the GPU**, q4_0 KV. Measured on the
real card: **5348 MiB used / 793 MiB free, 36.7 tok/s** short, and a
13,888-token prompt answered correctly in 12.3 s through the 8082 proxy. **5.1x.**
`KV_TYPE` in `llm-server.sh` was one global for the whole port and is now
per-model (`entry(..., kv=)`), so only Dolphin got q4_0 and Gemma's q8_0 is
untouched. Full reasoning, and why sliding window cannot buy the 36k back, in
**DECISION 76**.

**Two traps found while fixing it.**

1. **A leftover test server on another port is invisible until something else
   needs VRAM.** `jobhunt-llm.service` failed to start with
   `cudaMalloc failed: out of memory` **on the first model (Gemma)**, which reads
   like a Gemma problem and is not one — a `llama-server` left on port 8083 from
   an earlier measurement was holding 5.2 GB. Check `pgrep -x llama-server`
   before believing an OOM.
2. **A prompt longer than `n_ctx` returns HTTP 400, it does not truncate.**
   (A prompt that fits with a `max_tokens` that would overrun just clamps the
   generation — 15,856 tokens + `max_tokens: 2048` is fine.) So `contextWindow`
   in `~/.openclaw/openclaw.json` must **equal** `LLM_CTX3`; setting it higher
   turns a silent trim into a visible failure mid-conversation. Both were changed
   together, and the live config was read back after patching.

**How to spot the next one of these.** A positive `LLM_NGL*` is not a tuning
knob, it is a confession that the model did not fit. Before accepting one, do the
arithmetic: weights + (ctx x bytes-per-token of KV) against the card. If the
answer is over, the context is the thing to cut — dropping layers to the CPU
costs a factor of five, and it costs it on **every** token forever.

---

## BUG-135 — OpenClaw's compaction never runs, because the part it can shrink is the small part
**Status:** FIXED — 2026-08-17
**Component:** `~/.openclaw/openclaw.json` (`tools.deny`), `scripts/jobhunt/openclaw-provider.json5`

**Symptom.** Shawn: *"the compact thing is not working."* Long chats either stop
answering or die outright.

**Evidence, read out of the trajectory logs.** Across **32 recorded sessions,
`compactionCount` was greater than zero exactly ONCE** (2026-08-05). Two sessions
ended with:

```
promptError = "Context overflow: prompt too large for the model (precheck)"
```

That is OpenClaw refusing to send **without compacting first**.

**Cause.** OpenClaw re-sends a fixed block on **every** turn: its system prompt
plus the full JSON schema of every tool. **Compaction can only shrink the
conversation history — it cannot touch either of those.** Measured against the
model's own tokenizer (never OpenClaw's estimate, which is less than half the
truth — see the Phase 0b note, 9456 estimated vs 19929 actual):

| | Gemma, 24576 window | Dolphin, 16384 window |
|---|---|---|
| system prompt alone | 8577 | 7776 |
| **+ 28 tool schemas** | **15956** | 7776 |
| OpenClaw budget (`0.8 x ctx - 2048`) | 17612 | 11059 |
| **left for the actual chat** | **1656** | 3283 |

On Gemma the fixed part was **91% of the budget**. Compaction was summarising the
9% while the 91% stayed. There was nothing left to cut, so the precheck failed.

**Fix.** `tools.deny` — 28 tools down to **11**. Measured after, same method:

| | overhead | room for chat |
|---|---|---|
| Gemma before | 15956 | 1656 |
| **Gemma after** | **9944** | **7668** — 4.6x |
| Dolphin before | 7776 | 3283 |
| **Dolphin after** | **6885** | **4174** — 1.3x |

The saving beats the schema arithmetic (6012 vs a projected 5001) because the
**system prompt lists the tools too**: 32224 -> 28330 chars.

**Why Dolphin barely moves, and it is not good news.** Its overhead was *already*
low because **its prompt template silently ignores the `tools` variable** — adding
28 tool schemas changed its token count by **zero**. They cost nothing because
they are thrown away. Dolphin cannot call tools at all. Same shape as BUG-133;
the `--jinja` server in the BUG-097 migration is the real fix.

**Why `deny` and not `allow`/`profile`.** Deny always wins and is unambiguous.
`tools.profile` sets a base allowlist that `allow` then modifies, and the docs do
not state whether `allow` widens or narrows it. Blunt on purpose.

**What was removed and what it costs** — `cron` (5868 chars, 19% of the block;
reminders and wake events — systemd timers already do this), `gateway` (the agent
can no longer restart itself), `message` (no channel is connected), `nodes` +
`node_inference` (no paired devices, and the latter runs Ollama, which AGENTS.md
bans), the seven `sessions_*`/`subagents`/`agents_list` tools (a 6 GB card holds
one model, so a sub-agent would fight its parent for the same VRAM),
`skill_workshop`, the three goal tools, and `tts`. **Kept:** read, write, edit,
apply_patch, exec, process, web_search, web_fetch, memory_search, memory_get,
session_status.

**Verified by running it, not by reading the config.** `openclaw agent --agent
main -m "..."` drove a real turn; the new trajectory's `context.compiled` event
lists **11 tools**, exactly the intended set. Config backed up first to
`~/.openclaw/openclaw.json.pre-toolcut`.

**How to spot the next one of these.** When an agent "runs out of context"
immediately, measure the **fixed** overhead before touching history settings —
send the system prompt and tool block to the server with `max_tokens: 1` and read
`usage.prompt_tokens`. If the fixed part is most of the window, no history
setting can save it. And never trust the harness's own token estimate.

**Not done, deliberately.** `maxHistoryShare` is 0.8 and `reserveTokens` 2048;
raising the share to ~0.95 would add roughly 3700 more tokens on Gemma. Left
alone because 0.8 was set deliberately by another agent on 2026-08-16 and the
reason is not recorded. One change at a time — the tool cut is measured and
sufficient.

---

## BUG-136 — the NVIDIA card looked like a dead driver, twice, for two unrelated reasons
<!-- [CHANGE: claude-code | 2026-08-18] -->
**Status:** FIXED — 2026-08-18. Both halves proven on the card.
**Component:** `/etc/environment` (`__EGL_VENDOR_LIBRARY_FILENAMES`), `scripts/luminos-wine-launcher`

**Symptom.** Every Wine app silently ran on the Radeon 780M no matter what the GPU
dialog was told. A direct check appeared to show the driver itself was broken:

```
Could not get 'vkCreateInstance' via 'vk_icdGetInstanceProcAddr' for ICD libGLX_nvidia.so.0
```

Three earlier sessions read that line and concluded the NVIDIA Vulkan driver was
dead. **It was not.** There were two separate faults stacked on top of each other,
and each one alone is enough to produce the same fallback.

### Half one — `__EGL_VENDOR_LIBRARY_FILENAMES` is a *replace*, not an *add*

Luminos pins it system-wide to `/usr/share/glvnd/egl_vendor.d/50_mesa.json`. That
is the BUG-046c / BUG-050 fix and it is correct on its own terms: it stops NVIDIA
becoming the default EGL vendor so the dGPU can actually sleep.

But the variable does not *prefer* Mesa, it makes Mesa **the only vendor GLVND can
see**. And **NVIDIA's Vulkan ICD initialises through EGL.** With NVIDIA's own EGL
vendor removed from the list, the ICD fails its own init and then reports nothing:
`vk_icdGetInstanceProcAddr(NULL, ...)` returns NULL for every global entry point,
the loader concludes the library is not a Vulkan driver, and throws it away.

Measured directly with a 40-line `dlopen` harness (`/tmp/icdtest2.c`), which skips
the loader entirely and calls the ICD's own entry points:

| `__EGL_VENDOR_LIBRARY_FILENAMES` | `vk_icdNegotiateLoaderICDInterfaceVersion` | `vkCreateInstance` | instance |
|---|---|---|---|
| `50_mesa.json` | **-3** (`VK_ERROR_INITIALIZATION_FAILED`), for **every** interface version 1–7 | **-3** | `(nil)` |
| `60_nvidia.json` | **0** | **0** | `0x557e90579430` |
| both, colon-joined | **0** | **0** | `0x564796076610` |

Then `vulkaninfo` under `60_nvidia.json`:

```
deviceName = NVIDIA GeForce RTX 4050 Laptop GPU
deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU
apiVersion = 1.4.329   driverInfo = 595.71.05
```

**What it is NOT, each ruled out by measurement, not by argument:**
- **Not the DECISION 25 dgpu gate.** `dgpu-exec-v2 id` → `gid=948(dgpu)`;
  opening `/dev/nvidiactl` and `/dev/nvidia0` through it both succeed;
  `dgpu-exec-v2 nvidia-smi` lists the card. It fails **identically** with the gate
  open and as **root**, so it was never a permissions problem.
- **Not a missing symbol.** `nm -D --defined-only libGLX_nvidia.so.0` lists
  `vkCreateInstance`, and `dlsym` hands back a live pointer (`0x7f9d4c573a10`).
  The prior "the library doesn't export it" claim was simply wrong.
- **Not the glibc `__malloc_hook` removal.** An `LD_PRELOAD` shim supplying
  `__malloc_hook`/`__realloc_hook`/`__free_hook`/`__memalign_hook`/`ErrorF` changed
  nothing — still `-3`. `LD_DEBUG` prints those as "(fatal)" and they are noise.
- **Not a driver/userspace version skew.** Kernel module and userspace both 595.71.05.

`strace` is what closed it: during the failing init the ICD loads
`libEGL_mesa.so.0` and `libgallium-26.1.6-arch1.1.so`, reads `/proc/self/maps`,
re-opens its own libraries — and **never opens `/dev/nvidiactl` at all.** It gives
up long before it would ask the kernel for the card. (`strace` was not installed;
`luminos-brain safe` said NO on the install, which is the known false positive that
greps `hive-brain.md`'s own header banner — overridden with `--reason`.)

**Fix.** Do not unpin the global default — the sleep behaviour it buys is worth
keeping. Instead every launcher that selects NVIDIA must set
`__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/60_nvidia.json`
alongside `VK_ICD_FILENAMES`. `luminos-gpu-launch`, `chrome-luminos` and
`luminos-wine-launcher` already do; `docs/LUMINOS_HANDBOOK.md:1141` already
documented the pairing. **A bare `VK_ICD_FILENAMES=nvidia_icd.json` on its own is a
broken test, not a broken driver** — that is what produced three sessions of wrong
conclusions.

### Half two — `luminos-wine-launcher` never entered the gate

The NVIDIA branch set `DRI_PRIME=1`, the ICD, and the EGL vendor correctly, and
then ended in a bare `exec wine`. `/dev/nvidia0` and `/dev/nvidiactl` are
`root:dgpu 0660` and the `dgpu` group is deliberately **empty** (DECISION 25), so
the process could not open the card and fell back to the 780M, while
`notify-send` cheerfully announced "running on NVIDIA RTX 4050".

This was **already written down** — the BUG-103 close-out noted "it never calls the
dGPU gate at all" — and was never acted on. `luminos-gpu-launch` has always ended
in `exec dgpu-exec-v2`; this launcher was the one that was missed.

**Fix** (`scripts/luminos-wine-launcher`, installed to `/usr/local/bin/`):

```bash
if [ "$GPU_CHOICE" = "nvidia" ]; then
  exec dgpu-exec-v2 wine "$EXE" $ARGS
fi
exec wine "$EXE" $ARGS
```

`dgpu-exec-v2`, not `dgpu-exec` — v1 raises only the *effective* gid and bash drops
it at startup (BUG-102). Proven on a running Wine game: `/proc/82256/status` reads
`Gid: 948 948 948 948`.

**Verified end to end.** *007 First Light* now reaches a live swapchain on the card:
`Found device: NVIDIA GeForce RTX 4050 Laptop GPU (NVIDIA 595.71.5)`,
`Creating swapchain (1920 x 1080)`, `Got 3 swapchain images`.

### Three traps found on the way, worth keeping

- **Setgid processes are non-dumpable.** Anything launched through `dgpu-exec-v2`
  gives `Permission denied` on `/proc/PID/maps` and `/proc/PID/environ` even as
  yourself. Use `sudo`. `/proc/PID/status` still reads fine.
- **DXVK reports an AMD GPU while running on NVIDIA, on purpose.**
  `dxgi.nvapiHack` / `dxgi.hideNvidiaGpu` default true and spoof
  `vendor 0x1002 device 0x73df`. Seeing that line is *evidence you are on NVIDIA*,
  not evidence you are not. Set both `False` for Streamline/DLSS titles.
- **On Optimus, DXGI divides by zero.** The NVIDIA adapter has no attached display,
  so DXVK logs `Found monitors not associated with any adapter, using fallback`,
  then `readMonitorEdidFromKey: Failed to get EDID reg key size`, then crashes
  inside `dxgi.dll` computing a refresh rate from an empty mode. Running inside
  `wine explorer /desktop=Name,1920x1080` supplies a synthetic monitor and it goes
  away. Not a driver fault.

**Not done, deliberately.** The launcher's NVIDIA branch still does not set
`__NV_PRIME_RENDER_OFFLOAD=1` / `__GLX_VENDOR_LIBRARY_NAME=nvidia` the way
`luminos-gpu-launch` does. Those two are the **GLX/OpenGL** offload path; Wine
games go through Vulkan, which is already correct. Left out to keep the fix to one
branch and one line. Add them if a GL-only Wine app turns up on the wrong card.

**Undo.** Delete the three added lines from `/usr/local/bin/luminos-wine-launcher`.
Nothing else on the system was changed for this bug.

---

## BUG-137 — 007 First Light does not crash and does not hang; it waits on nine dialogs you cannot see
<!-- [CHANGE: claude-code | 2026-08-19] -->

**Status: FIXED, 2026-08-19. The game runs on the RTX 4050.** Type `007`.

**The fix is one component.** GE-Proton10-34 ships a vkd3d-proton that generates
SPIR-V which segfaults NVIDIA's shader compiler. **vkd3d-proton 3.0.1 does not.**
Same Wine, same DXVK, same prefix contents, same 610.57.04 driver, same game —
only the D3D12-to-Vulkan translator was swapped, by
`007-mkproton.sh GE-Proton10-34-vkd3d301 ~/re/007/downloads/vkd3d-proton-3.0.1`.

| | stock GE-Proton10-34 | + vkd3d-proton 3.0.1 |
|---|---|---|
| assert dialogs | **9** | **0** |
| GPU utilisation | 0% | **100%** |
| VRAM held | — | 2064 MiB |
| result | black window forever | title screen, 2880x1800 |

Verified three ways before this was written: a 199-second run with
`nvidia-smi --query-compute-apps` showing `007FirstLight.exe` on the card, a
screenshot of the in-game graphics menu (DLSS options now listed), and a
screenshot of the title screen after launching the installed `/usr/local/bin/007`
with no arguments. Also re-tested on the Radeon 780M (`assert=0`, 95% busy), so
the swap did not cost the path that already worked.

`007` now defaults to **NVIDIA**; `007 --igpu` selects the Radeon. GE-Proton11-5
also passes (`assert=0`) and is installed as a second option.

Everything below is the investigation that got here. It is kept because most of
it is a list of things that are *not* the cause, and re-chasing any of them is
pure loss.

**Symptom.** Under GE-Proton10-34 on the RTX 4050 the game starts normally, opens
a real 1920x1080 window, holds ~1960 MiB of VRAM, spawns `vkd3d-swapchain`,
`vkd3d_queue` and `vkd3d_fence` threads — and then stops. GPU utilisation falls to
**0%**, SM clock to **210 MHz**, RSS freezes at a fixed value, and the window stays
black forever. Nothing is logged. `rc` is never returned; the process lives.

**Cause.** Nine of the game's threads are each blocked inside a `MessageBox` that
Wine creates but never paints. All nine carry the same text:

    Assertion failed!
    Program: <program name unknown>
    File:    ../src-wine/dlls/winevulkan/loader_thunks.c
    Line:    3151
    Expression: !status && "vkCreateComputePipelines"

`status` there is the **NTSTATUS of the Unix-side call**, not a `VkResult`. Under
system Wine 11.14 the identical fault prints
`err:vulkan:vkCreateComputePipelines Exception 0xc0000005 in Unix call.` and kills
the process instead of opening a dialog. **Proton and system Wine are hitting one
bug, not two** — an earlier working theory that mixing GE-Proton's VKD3D-Proton
with system Wine's winevulkan caused the segfault is hereby **retracted**.

### How to see the dialogs

They are invisible to screenshots, so ask the wineserver:

```bash
cd "/mnt/win-os/007 First Light/Retail"
STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam" \
STEAM_COMPAT_DATA_PATH="$HOME/re/007/protondata" \
dgpu-exec-v2 env DISPLAY=:0 XAUTHORITY=/run/user/1000/xauth_* WINEDEBUG=-all \
  "$GE/proton" runinprefix winedbg --command "info wnd"
```

Look for class **`#32770`** (the Win32 dialog class) with `&Abort` / `&Retry` /
`&Ignore` buttons. **`winedbg` truncates window text to 14 characters**, so it will
only ever show you `Assertion fail`. To read the whole message, grep the process's
memory — and note the process is setgid via `dgpu-exec-v2` and therefore
**non-dumpable**, so `/proc/PID/mem` and `/proc/PID/maps` need `sudo`.

The `+err` log gives the same hint one step earlier and much more cheaply:
`fixme:oleacc:find_class_data unhandled window class: L"#32770"` x29 alongside
`L"Button"` x9. **A `#32770` in a Wine log means a message box exists.**

### Ruled out by measurement — do not re-chase these

| Theory | How it died |
|---|---|
| Shader compilation / still working | 4 threads did grind in `libnvidia-gpucomp.so` for ~10 min, but that was the game's own 259 MB `Retail/PipelineCache.bin`; its fd position reached the file size exactly. A second run with a warm `vkd3d-proton.cache.write` hit the *identical* stall in **46 s**. |
| VRAM exhaustion | `jobhunt-llm.service` was holding 3576 MiB of the 6141 MiB card. Stopped it → 2 MiB used → stalled in the same place. |
| Online / DRM check | Zero TCP sockets. The RUNE Steam emulator works fine; it writes `drive_c/users/Public/Documents/Steam/RUNE/3768760/stats.ini`. |
| Missing virtual desktop | Adding the desktop *did* produce a window (keep it — see below), but the stall is unchanged. |
| `VK_EXT_shader_module_identifier` | `VKD3D_DISABLE_EXTENSIONS=VK_EXT_shader_module_identifier` → still `assert=9`. |
| `VK_EXT_device_generated_commands`, `VK_EXT_descriptor_buffer`, stale `vkd3d-proton.cache` | All tested under system Wine; all still crashed (7 s / 15 s / 19 s / 6 s). |
| Wrong Wine version under VKD3D-Proton | Disproved by this bug's own evidence: real Proton hits the same assert. |

**The decisive split:** the same build on the **AMD Radeon 780M** gives
`assert=0` and 72% GPU busy. So the fault is on the NVIDIA side of
`vkCreateComputePipelines`, not in Wine's thunk and not in the game.

### What made it work (AMD path)

1. **GE-Proton10-34 via `proton run`,** not system Wine. Needs *both*
   `STEAM_COMPAT_CLIENT_INSTALL_PATH` and `STEAM_COMPAT_DATA_PATH` or it refuses.
2. **A virtual desktop, set in the prefix registry.** `proton run` has no
   `explorer /desktop=` equivalent, so:
   ```
   HKCU\Software\Wine\Explorer          Desktop = Default
   HKCU\Software\Wine\Explorer\Desktops Default = 1920x1080
   ```
   `007-run.sh` now rewrites these whenever `--res=` disagrees with the prefix.
3. `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/**radeon_icd.json**` — *not*
   `radeon_icd.x86_64.json`, which does not exist on Arch and is still the stale
   path in `luminos-gpu-launch:65`.
4. `__EGL_VENDOR_LIBRARY_FILENAMES=…/50_mesa.json` (the system default; on the
   NVIDIA branch this **must** become `60_nvidia.json` — BUG-136).

First launch spends **~8 minutes** on a "PRE-LOADING SHADERS" screen (24% → 65% →
done). It is cached after that: the next start reached the title screen in **72 s**.

### The bisection harness

`~/re/tools/007-try.sh <label> [--igpu] [VAR=VAL …]` runs one configuration and
prints one line: `label alive=Y assert=9 gpu=0% rss=… secs=…`. `assert` counts
`#32770` windows, so **`assert=0` with `gpu>0` is the shape of a run that works**.
Negative-tested against the known-bad config before it was trusted; it correctly
reported `assert=9`.

### Two traps that cost time here

- **`pgrep -x 007FirstLight.exe` matches nothing.** Linux truncates `comm` to 15
  characters; the name to match is `007FirstLight.e`.
- **"No window" in a screenshot is usually a stacking problem, not a missing
  window.** KWin reported it the whole time as
  `steam_proton | Wine Desktop | 960x568 @270,166` — and 960x568 is *correct*, not
  half-scale: KDE runs at scale 2, so a 1920x1080 physical window is 960x540
  logical plus a 28px titlebar. It simply sits behind Chrome. Raise it with a KWin
  script (`workspace.windowList()` → set `workspace.activeWindow`) before capturing.

### Next steps on the NVIDIA path, cheapest first

1. Delete `Retail/PipelineCache.bin` (259 MB, the game's own D3D12 pipeline
   library) and let it rebuild against this driver.
2. Bisect `VKD3D_DISABLE_EXTENSIONS` more widely, and try
   `VKD3D_CONFIG=pipeline_library_ignore_spirv`.
3. Capture the faulting address on the Unix side to confirm the fault is inside
   `libnvidia-gpucomp.so` rather than Wine's structure conversion.
4. ~~Unpin and upgrade the NVIDIA driver.~~ **DONE 2026-08-19. Did not fix it.**
   See "ROOT CAUSE FOUND" below.

## ROOT CAUSE FOUND — [CHANGE: claude-code | 2026-08-19]

**It is a segfault inside NVIDIA's SPIR-V compiler. Proven, not inferred.**

`WINEDEBUG=+seh` finally prints what the MessageBox was hiding. Nine threads, one
address, every time:

```
0148:warn:seh:handle_syscall_fault backtrace: --- Exception 0xc0000005 at
0x7f04a4746fd8: /usr/lib/libnvidia-glvkspirv.so.610.57.04 + 0x346fd8.
```

`libnvidia-glvkspirv.so` is the NVIDIA driver's SPIR-V → machine-code compiler.
vkd3d-proton hands it the compute shaders it translated from the game's DXIL, and
the compiler dereferences a bad pointer. Wine's thunk is a bystander: it faithfully
reports the Unix call died, `assert(!status)` fires, and nine `MessageBox`es open.

That closes the question the AMD/NVIDIA split only pointed at. **This is an
upstream NVIDIA driver bug.** Nothing in Wine, Proton, vkd3d or Luminos can fix it;
they can only avoid feeding the compiler the shader it chokes on.

### Eliminated on 2026-08-19, each by a measured run

| Hypothesis | Test | Result |
|---|---|---|
| Stale driver branch | `595.71.05` → `610.57.04`, full DKMS rebuild | `assert=9`, identical |
| Stale shader cache | moved `PipelineCache.bin` (259 MB) + `vkd3d-proton.cache` aside, cold run | `assert=9` |
| A misbehaving Vulkan extension | disabled `shader_module_identifier`, `pipeline_creation_feedback`, `subgroup_size_control`, `descriptor_buffer`, `device_generated_commands`, `graphics_pipeline_library` together | `assert=9` |
| The DECISION 25 dGPU gate | see below | never plausible |

The driver upgrade is worth keeping regardless — it is now pinned at `610.57.04`
instead of `595.71.05`, and the DECISION 26 protections were re-verified after it:
RTD3 reaches `suspended` within 10 s of the last consumer exiting, `power/control`
returns to `auto`, `d3cold_allowed=1`, and all three `kcm_luminos_*.so` plugins
resolve with zero missing libraries.

**Rollback, if the 610 branch ever causes trouble:** the three `595.71.05-2`
packages are saved at `~/re/nvidia-rollback-595/` (308 MB, fetched from
archive.archlinux.org because they were NOT in the pacman cache). Restore with
`sudo pacman -U ~/re/nvidia-rollback-595/*.pkg.tar.zst`, then reload the modules.
`/etc/pacman.conf.bak-20260819-nvidia610` holds the pre-change pin line.

## The two GPUs are not compiling the same shaders — [CHANGE: claude-code | 2026-08-19]

The framing that matters: we cannot fix NVIDIA's compiler, but the SPIR-V it
chokes on is **generated by vkd3d-proton**, and vkd3d has many valid ways to emit
the same shader. Change the emitter, and the compiler may never see the construct
that kills it.

That turned out to be more than a hope. Dumping every shader on *both* cards with
`VKD3D_SHADER_DUMP_PATH` and diffing them shows vkd3d does not generate one
program and hand it to whichever GPU is present — it generates **vendor-specific
code**:

| | AMD Radeon 780M (works) | NVIDIA RTX 4050 (asserts) |
|---|---|---|
| SPIR-V modules translated | 6657 | 4430, then it stops |
| Modules the other card also has | — | 4430 of 4430 |
| **Same shader hash, different SPIR-V bytes** | — | **4047 of 4430** |
| Modules using `SPV_NV_raw_access_chains` | **0** | **4039** |
| Compute modules using it | 0 | 561 of 886 |
| Modules using `SPV_NV_shader_subgroup_partitioned` | 0 | 1 (a compute shader) |

`SPV_NV_raw_access_chains` is an NVIDIA-only SPIR-V extension. It is present in
91% of the shaders the crashing card compiles and in **none** of the shaders the
working card compiles. That is the single largest difference between the code
that survives and the code that does not.

**The measurement that moved it from suspicion to evidence:** substituting a
do-nothing compute shader for just those 561 modules — via `VKD3D_SHADER_OVERRIDE`
— dropped the fault from **`assert=9 gpu=0%` to `assert=4 gpu=100%`**. Fourteen
consecutive runs before it had produced `assert=9 gpu=0%` without variation. The
GPU doing real work at all is new. So the killer shaders are in that set, and
there is more than one of them.

### Measured and eliminated — do NOT re-chase

Every row is a real run of `007-try.sh <label> --nvidia`. `assert=9 gpu=0%` is the
unchanged failure.

| Test | Result |
|---|---|
| `VKD3D_CONFIG=no_nvx` (NVIDIA-only bindless path off) | `assert=9` |
| `VKD3D_CONFIG=force_static_cbv` | `assert=9` |
| `VKD3D_CONFIG=force_raw_va_cbv` | `assert=9` |
| `VKD3D_CONFIG=skip_driver_workarounds` | `assert=9` |
| `VKD3D_SHADER_MODEL=6_0` | `assert=9` |
| `VKD3D_FEATURE_LEVEL=11_0` | `assert=9` |
| all four of the above at once | `assert=9` |
| `VKD3D_DISABLE_EXTENSIONS=VK_NV_raw_access_chains` | `assert=9` — see caveat |
| Feed NVIDIA the Radeon's SPIR-V for **every** shader | `assert=9` |
| Feed NVIDIA the Radeon's SPIR-V for compute shaders only | `assert=9` |
| No-op the one `subgroup_partitioned` compute shader | `assert=9` |
| **No-op the 561 raw-access-chain compute shaders** | **`assert=4`, GPU 100%** |

**Caveat on the `VKD3D_DISABLE_EXTENSIONS` row, and it matters:** that run was
*not* confirmed to have taken effect. Turning the extension off should have made
vkd3d regenerate those shaders without `RawAccessChainsNV`, yet no-oping the same
shaders demonstrably helps. Those two results disagree, so one of them is lying.
Before trusting the disable, re-dump with the variable set and check whether
`RawAccessChainsNV` is actually gone from the output.

Handing NVIDIA the Radeon's own SPIR-V not helping is also worth a thought rather
than a shrug: those modules address descriptors a different way, so vkd3d's
NVIDIA-side pipeline layout may not match them. It is not a clean experiment.

### Closed: there is no newer NVIDIA driver

Way #3 ("try a beta driver") is dead, and cheaply so. The AUR beta packages
`nvidia-open-beta-dkms`, `nvidia-beta-dkms` and `nvidia-utils-beta` are all at
**610.57.04** — byte-identical in version to what is installed. 595 already
failed. There is nothing newer in existence to install.

### Tooling built for this — [CHANGE: claude-code | 2026-08-19]

- `007-try.sh` gained `--proton=NAME`, and gives every non-default build **its own
  prefix clone**, because a Proton prefix upgrade is one-way and letting a newer
  build touch `~/re/007/protondata` could cost the working setup.
- `007-mkproton.sh <name> <vkd3d-dir>` clones GE-Proton10-34 with `cp -al` and
  swaps in a different vkd3d-proton. A 1.4 GB Proton variant costs ~25 MB. Safe
  only because the dlls are *replaced* (rm then cp); editing a hardlink in place
  would corrupt the real GE-Proton10-34.
- `007-sweep-codegen.sh`, `007-sweep2.sh`, `007-sweep3.sh` — unattended batches.
- `007-bisect-shader.sh` — binary search for the killer shader via
  `VKD3D_SHADER_OVERRIDE`, ~10 runs to go from 990 candidates to 1.

**Two traps this cost:**
- Seeding a Proton prefix by copying only `pfx/` is not enough. Proton also reads
  `tracked_files` and `version` from the compatdata directory, and without them
  `setup_prefix()` dies with `FileNotFoundError` before the game starts — which
  the harness reports as a bland "exited early" and reads as *the Proton build
  failed*. Copy the whole directory.
- `N=$(grep -c ... || echo 0)` yields `"0\n0"` when grep finds nothing, because
  grep already printed `0` before failing. `[ "$N" -lt 1 ]` then errors instead of
  being true, so a guard written that way never fires. Use `N=${N:-0}` on its own line.

### What fixed it, and the lesson

| Proton build | vkd3d-proton | Result on the RTX 4050 |
|---|---|---|
| GE-Proton10-34 (stock) | bundled | `assert=9 gpu=0%` |
| GE-Proton10-34-vkd3d301 | **3.0.1** | **`assert=0 gpu=100%`** |
| GE-Proton10-34-vkd3d2141 | 2.14.1 | exited early — too old for this prefix |
| GE-Proton11-5-x86_64 | its own, newer | `assert=0 gpu=34%` |

**The lesson is about search order, not about graphics.** Before this session the
bug had absorbed a driver upgrade, a cache purge, six Vulkan extensions disabled,
a full SPIR-V dump-and-diff and eight codegen flags — all of it sophisticated, all
of it `assert=9`. The thing that actually worked was noticing that exactly *one*
Proton was installed, so the most obvious experiment in the whole problem had
never been run. Swapping one 5 MB DLL fixed it in under five minutes.

The elimination table above is still worth keeping: it is the reason nobody
should spend another evening on driver branches, shader caches or `VKD3D_CONFIG`.

### Still open (optional, nothing depends on them)

1. Report upstream. The crash address inside `libnvidia-glvkspirv.so`, plus the
   fact that vkd3d-proton 3.0.1 avoids it, is a complete NVIDIA bug report.
   Narrowing to the exact shader would need `007-bisect-shader.sh` to be finished
   — it proved the culprits are game compute shaders (`all-noop` → `assert=0`)
   before a run aborted at step 1.
2. The `VKD3D_DISABLE_EXTENSIONS=VK_NV_raw_access_chains` contradiction noted
   above was never settled. It is now academic.
3. Decide whether stock `GE-Proton10-34` and `~/re/007/protondata` are still worth
   keeping as a fallback. They cost 1.4 GB + 679 MB and nothing points at them.

### Launchers — [CHANGE: claude-code | 2026-08-19]

Three ways in, all pointing at the same `/usr/local/bin/007`:

- **Terminal:** `007`
- **App menu:** `~/.local/share/applications/007-first-light.desktop`, with
  right-click actions for 1920x1080 and for the known-broken NVIDIA path.
- **Lutris:** row in `~/.local/share/lutris/pga.db` + config at
  `~/.config/lutris/games/007-first-light.yml`. Verified by actually launching
  `lutris lutris:rungame/007-first-light` (pid up, iGPU 90%), not just by the
  entry appearing. DB backed up first to `pga.db.bak-20260819`.

**Trap.** A Lutris *game config* in `~/.config/lutris/games/` is **flat** —
top-level `game:` / `system:` keys. It is NOT the installer-script shape
(`name:`/`slug:`/`runner:`/`config:`) used by the neighbouring
`black-myth-wukong-installer.yml`. Copying that neighbour as a template fails with
`MissingGameExecutableError: This game has no executable set.` even though the
`exe:` key is plainly present, because it is nested one level too deep.

Lutris uses the `linux` runner, not `wine`, on purpose: the `007` script already
owns the Proton build, the prefix, the GPU pinning and the virtual desktop, and
Lutris' wine runner would fight it for the prefix.

### Not the cause: the DECISION 25 dGPU gate

Worth writing down because it is the intuitive suspect and it is wrong. The gate
is real — `/dev/nvidia0` and `/dev/nvidiactl` are `crw-rw---- root dgpu`, group
`dgpu` (gid 948) is **empty**, and `shawn` is not a member — so an ordinary
process cannot open the card and the NVIDIA Vulkan ICD silently falls back to the
Radeon 780M. That is a real effect and it does explain "Wine seems pinned to the
iGPU" for *other* apps.

It is not what breaks 007, for three measured reasons:
1. `007-run.sh` already goes through the gate: the NVIDIA branch is
   `exec dgpu-exec-v2 env … nvidia_icd.json … 60_nvidia.json`, and
   `dgpu-exec-v2` is `-rwxr-sr-x root dgpu`, i.e. setgid into the group.
2. The gate passes right now: `dgpu-exec-v2 nvidia-smi …` returns
   `NVIDIA GeForce RTX 4050 Laptop GPU, 595.71.05`, while the same command
   without the wrapper returns `Failed to initialize NVML: Insufficient Permissions`.
3. **The symptom is the wrong shape.** A gate failure means no NVIDIA device is
   ever found — zero dialogs and a quiet fall back to AMD. What actually happens
   is nine dialogs, which can only be reached *after* Vulkan has opened the
   device, enumerated the GPU and created a logical device. Reaching
   `vkCreateComputePipelines` is proof the gate was already passed.

**One correction to a plausible-sounding next step:** capturing "the real
`VkResult`" with `VK_LOADER_DEBUG=all` will not work, because there is no
`VkResult`. The assert is on the **NTSTATUS of the Unix-side call** and the value
is `0xc0000005` — an access violation. The driver did not *return* an error; it
*crashed*. The useful capture is a faulting address, not a return code.

### Fullscreen — [CHANGE: claude-code | 2026-08-19]

The game first ran in a box in the middle of the screen. Not a game setting: the
Wine virtual desktop was hardcoded to `1920x1080`, the panel is `2880x1800`
physical, and XWayland is unscaled — so the window covered 67% x 60% of the panel.
`007-run.sh` now defaults `RES` to the panel's native mode and writes it into
`HKCU\Software\Wine\Explorer\Desktops`. Verified full-bleed at 2880x1800, 96% iGPU,
zero `err:` lines, zero `#32770` windows.

Read the mode from **sysfs**, not the compositor, so it works under KDE and
Hyprland alike:

```sh
for _m in /sys/class/drm/card*-eDP-*/modes; do
  _r=$(head -1 "$_m" 2>/dev/null)
  case "$_r" in [0-9]*x[0-9]*) RES="$_r"; break ;; esac
done
```

**Trap (cost me one wasted launch):** do NOT filter those files with `[ -s "$f" ]`.
Every sysfs file reports 4096 bytes whether or not it has any content, so `-s`
matches the *disconnected* `card1-eDP-1` connector first, yields an empty string,
and falls silently back to the default. Test the **content**, not the size.

**Undo.** `007` is a single file. Restore the previous NVIDIA-default behaviour by
changing `GPU=igpu` back to `GPU=nvidia` in `~/re/tools/007-run.sh` and
re-installing it; restore the old window size with `007 --res=1920x1080`. Nothing
else on the system was changed for this bug; the `jobhunt-llm.service` stop was
temporary and it was restarted.

---

## BUG-138 — 007 First Light: black screen, audio playing, GPU at 100%. The window was 120 pixels too small.
<!-- [CHANGE: claude-code | 2026-08-20] -->

**Status: FIXED, 2026-08-20.** Type `007`.

**This is NOT a relapse of BUG-137.** BUG-137 was `assert=9 gpu=0%` — nine invisible
dialogs, nothing rendering because the shader compiler had segfaulted. This is
`assert=0 gpu=100%` — the game is running perfectly, computing every frame, and
throwing all of them away because it cannot get a surface to put them on.

### The one-line cause

The launcher asked for a **2880x1800** virtual desktop. KWin can only give it
**2760x1800**, because Caelestia's left bar reserves an exclusive zone of 60
logical (= 120 physical) pixels. **NVIDIA refuses a swapchain that is not exactly
the window size.** AMD does not care. `2880 − 2760 = 120` = the bar.

```
xprop -root _NET_DESKTOP_GEOMETRY  ->  2880, 1800     what the panel is
xprop -root _NET_WORKAREA          ->  120, 0, 2760, 1800   what you can actually have
```

### What it looked like

One error, 894 times in 68 seconds, in a 42,599-line log — and **nothing else**:

```
info:vkd3d-proton:dxgi_vk_swap_chain_init: Creating swapchain (2880 x 1800), BufferCount = 2.
err:vkd3d-proton:dxgi_vk_swap_chain_recreate_swapchain_in_present_task:
    Failed to create swapchain, vr -13.
```

`vr -13` is **`VK_ERROR_UNKNOWN`**, which is the driver's way of saying "no".
The *initial* create succeeds; every *recreate-in-present* fails, forever, so no
frame is ever presented. Hence: audio fine, GPU pegged, screen black.

### Why NVIDIA and not AMD

`vulkaninfo` reports, for an NVIDIA surface:

```
minImageExtent = maxImageExtent = currentExtent
```

All three are the same number. There is no range to negotiate — the swapchain
must match the X window **exactly**. RADV reports a real min/max range and clamps,
which is the entire reason `007 --igpu` never showed this and why it looked for a
while like an NVIDIA driver fault.

### The fix — it has TWO halves, and the first one alone is not enough

**Correction, same day.** This was first fixed with work-area sizing alone, and
Shawn came straight back with *"the game is still not fullscreen its windowed
mode."* He was right. Sizing to the work area stops the black screen, but a Wine
virtual desktop is an **ordinary window** — KWin gives it a titlebar and parks it
beside the bar. Fixing the crash is not the same as fixing the game.

**Half 2 is a KWin rule**, `~/.config/kwinrulesrc` `[3]`:

```ini
Description=Luminos: Wine virtual desktop is fullscreen (BUG-138)
title=Wine Desktop
titlematch=1
fullscreen=true
fullscreenrule=2      # 2 = Force
noborder=true
noborderrule=2
```

Matched on the window **title**, not `wmclass=steam_proton`, which would hit every
Proton game whether or not it wants this. Reload with
`qdbus org.kde.KWin /KWin reconfigure`. Previous config backed up as
`~/.config/kwinrulesrc.bak-2026-08-20`.

**The two halves must agree or the black screen comes straight back**, because the
rule changes what size the window gets. So the launcher **detects** the rule
rather than assuming it:

```sh
if pgrep -x kwin_wayland && grep -qF "$KWINRULE" ~/.config/kwinrulesrc; then
  RES = _NET_DESKTOP_GEOMETRY   # 2880x1800 - the window will be forced fullscreen
else
  RES = _NET_WORKAREA           # 2760x1800 - the most an ordinary window can get
fi
```

Delete the rule and the launcher quietly returns to the windowed-but-working size.
That is the property worth keeping: **neither half can silently break the other.**
Verified fullscreen by screenshot — title screen edge to edge, no titlebar, no
bar, window `0,0 1440x900` logical = 2880x1800, swapchain 2880x1800, 0 failures.

### Half 1 — the size

`~/re/tools/007-run.sh` sizes the virtual desktop from the **work area** (or the
full screen when the rule is in force), not the panel mode:

```sh
_wa=$(xprop -root _NET_WORKAREA | tr -d ' ' | cut -d= -f2)
_w=$(echo "$_wa" | cut -d, -f3); _h=$(echo "$_wa" | cut -d, -f4)
```

with the old sysfs `drm/modes` read kept as the fallback for Hyprland, a bare TTY,
or any session with no `xprop`. **This block had to move below the
session-resolution code** — `xprop` needs `DISPLAY`, and the launcher may be
started by an agent or a systemd unit with no session in its environment.

| | before | after |
|---|---|---|
| requested desktop | 2880x1800 | **2760x1800** |
| KWin window (logical) | 1380x900 | 1380x900 |
| swapchain created | 2880x1800 | **2760x1800** |
| `Failed to create swapchain` | **894** | **0** |
| GPU | 100% (wasted) | 98% |
| result | black screen | renders |

Verified by running the installed `/usr/local/bin/007`, not the harness — the
harness reads the prefix registry and does not set it, so it cannot test this fix.
KWin then reported the window as `steam_proton 60,0 1380x900 'Wine Desktop'`,
matching the swapchain exactly.

### Measured and eliminated — do NOT re-chase any of these

- **Driver mismatch.** `/proc/driver/nvidia/version` and the installed packages
  are both 610.57.04. Consistent.
- **Kernel GPU faults.** Zero NVRM/Xid lines in `dmesg` since boot.
- **NVIDIA presentation in general.** `vkcube --wsi xcb` completes 120 frames on
  both cards. (The flag is `--wsi xcb`; `--xcb` just prints usage.)
- **VRAM pressure.** Stopping `jobhunt-llm` took free VRAM from 2214 MiB to
  5799 MiB and the failure count went **up**, to 5362.
- **NVIDIA Reflex / `VK_NV_low_latency2`.** 586 failures with it disabled.
- **PRIME offload vars** (`__NV_PRIME_RENDER_OFFLOAD`, `__VK_LAYER_NV_optimus`,
  `__GLX_VENDOR_LIBRARY_NAME`). 546 failures.
- **Lutris.** Its entry uses the `linux` runner and execs `/usr/local/bin/007`;
  it is not in the path.
- **`kwinrc`.** Dated Aug 14; `[Xwayland] Scale=2` predates the working runs.

### The generalisable lesson

**A swapchain error is a window-size question first and a driver question last.**
Six experiments went looking for a broken NVIDIA stack. The measurement that
actually settled it was one `xprop` call, and the arithmetic was `2880 − 2760`.
Also: this is exactly the failure mode where a *working* second GPU misleads you —
AMD rendering fine did not mean the request was reasonable, only that RADV is
forgiving.

### The screenshot problem, and how to actually see the screen

Half of this bug was invisible for an hour because I could not look at the screen.
For the record, on **KWin/Wayland with Caelestia**:

- **`spectacle` DOES work headless** — `spectacle -b -n -f -o out.png`. It appears
  to produce nothing when run from an agent shell because it needs the *live*
  session's `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR` **and**
  `DBUS_SESSION_BUS_ADDRESS`. Lift all three out of `/proc/$(pgrep -x plasmashell)/environ`.
  This corrects the earlier "spectacle produces nothing" note.
- **`grim` does not** — KWin has no wlr-screencopy.
- **`ffmpeg -f x11grab` returns a BLACK frame.** KWin redirects XWayland windows,
  so the X root is not composited. It looks exactly like the bug you are chasing,
  which is a nasty way to be misled. Do not use it here.
- **`xwininfo`/`xdotool`/`wmctrl` are still missing.** For geometry use
  `/opt/claude-desktop-legacy/resources/locales/kwin-portal-bridge windows` (JSON,
  **logical** px) and `xprop -root` for the root properties.

### A second, unrelated thing that looks like this bug

Shawn also read the game as *"not running on nvidia."* **It was** — `nvidia-smi`
listed `./007FirstLight.exe` at 2074 MiB, 137 fds on `/dev/nvidia0`, `Gid: 948`
(the DECISION 25 gate). What he saw was the game's own VRAM meter pegged **red at
2,059 MB**, because `jobhunt-llm.service` holds **3576 of the card's 6141 MiB** and
the 4050's VRAM is *dedicated* — it does not borrow from system RAM the way the
780M does. A game reporting 2 GB of VRAM looks exactly like an integrated GPU.
The launcher already prints the holders before starting and deliberately does not
act on them; that stays the user's call.

### Undo

Two things to undo, in this order. **Delete rule `[3]` from
`~/.config/kwinrulesrc`** (or restore `kwinrulesrc.bak-2026-08-20`) and run
`qdbus org.kde.KWin /KWin reconfigure` — the launcher detects its absence and
drops back to work-area sizing by itself, so the game keeps working, just
windowed. Then, if you want the launcher back too: `007` is a single file,
`007 --res=2880x1800` restores the old (broken) request for one run, and deleting
the `_NET_WORKAREA` block in `~/re/tools/007-run.sh` restores it permanently.
Nothing else on the system was changed —
the `jobhunt-llm.service` stop during the VRAM experiment was temporary and it was
restarted and verified `active`.
