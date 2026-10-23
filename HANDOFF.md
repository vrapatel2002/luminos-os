# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-22 21:50 — R2 of the post-reboot session (GLM-5.3 window, host-shell available)

**RESET this date per §0.2 tripwire** (file had grown to ~470 lines). Pre-reset content is in git:
`git show HEAD:HANDOFF.md` (HEAD = `e3177cd4`, 2026-10-22 18:47, the GLM side-by-side commit). Only
what a newcomer must not re-learn or re-break is carried forward. The 2026-10-22 evening updates
(Vela MW4 result, BUG-210 renumber) are committed by the post-reboot GLM session via host-shell.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now (2026-10-22 evening, GLM window) — get CoD "MW4" running on Luminos, then Vela
Game: **Call of Duty - Modern Warfare 4 (2026) campaign repack** at `/mnt/win-os/Games/Call of Duty -
Modern Warfare 4` (`sp26/sp26-cod.exe` = campaign, `cod.exe` = online HQ launcher, NOT used; Ricochet
attestation only matters for MP). Lutris entry `mw4` (id row name "mw4", configpath
`mw4-1792553189`), added by hand 2026-10-20, **never launched** (no prefix existed).
**DONE this turn:** rewrote `~/.config/lutris/games/mw4-1792553189.yml` — Control's proven settings
(DXVK, VKD3D, dxvk_nvapi for DLSS/Reflex, d3d_extras, esync+fsync, fresh prefix `~/Games/mw4`,
PROTON_LOG on for first launches), runner `GE-Proton11-6-dx12fix` (= GE-Proton11-6 + the
gameos rayquery-validate vkd3d patch; neutral on proprietary, required on Vela/NVK). Working dir =
the `sp26/` folder. Global dGPU gate + MangoHud apply automatically (system.yml, DECISION 90).
**LAUNCH 1 (19:11) hung — ROOT CAUSE FOUND AND FIXED (R6, ~21:40).** wchan capture: sp26-cod.exe
single-threaded, blocked in `anon_pipe_read` = launcher stub waiting on a child. Child identified
from its own log `sp26/ccsdownloader.log`: the FitGirl-style repack wraps the exe with a
**ccsdownloader.exe** (custom "CCS Downloader v0.02", 2026-10-16) that at every launch queries
Activision's live CDN (`rex-gvs` / `objectstore-publishers-rex.prod.demonware.net`, 3–10 s timeouts,
config `sp26/ccsconfig.json`) and on failure **"cleans up" content files it manages** then leaves the
stub hanging. This exactly reproduces Shawn's Windows symptom (runs once from installer, crashes,
never again until reinstall — reinstall re-places the packs the downloader deletes). The needed packs
are already on disk (`cod26/main/extccs/31/*_1196.bin`); ccs_history.json = `[]` (never a successful
download). Game is campaign-only, no Ricochet/anticheat in the path (Shawn confirmed). Crack layer =
Goldberg Steam emu (`sp26/steam_settings/`, offline=1). Playtime 17 h in Lutris = Windows Steam
data; never played on Linux.
**FIX APPLIED (R6):** `sp26/ccsconfig.json` → `{"downloadsubconfigs": []}` (downloader now exits
cleanly doing nothing; game uses on-disk packs). Faithful backup: `sp26/ccsconfig.json.orig`.
Fallback if still hangs: rename `sp26/ccsdownloader.exe` → `.off`. Lutris was left stuck believing
the game runs; Shawn kills with `pkill -9 -f sp26-cod; pkill -9 -f ccsdownloader; pkill -9 -f umu;
pkill -9 -f wineserver` then relaunches. **PENDING: relaunch result.**

**LUMINOS GAME STACK FIXED (R8, ~20:05) — BUG-208.** Shawn: no Lutris game runs on Luminos,
all run on Vela (except MW4 = the repack bug above). Root cause: `/dev/nvidia0` +
`/dev/nvidiactl` never created at boot — `nvidia_uvm` loads early from modules-load.d, so
`/dev/nvidia-uvm` exists when the PCI bind uevent fires, and its `TEST!=` guard in
`60-nvidia.rules` suppresses `nvidia-modprobe` entirely (the only creator of the main nodes) →
NVIDIA Vulkan ICD cannot init → every dGPU-gated game fails; Vela unaffected. Diagnosed via
host-shell MCP (BUG-207 verified end-to-end by this). **Fix:** `luminos-uvm-gate.sh` now
creates both main nodes when absent (mknod, major from /proc/devices, root:dgpu 0660, BUG-208
log lines) — repo `scripts/dgpu-gate/` + installed `/usr/local/bin/luminos-uvm-gate` identical.
Verified: nodes recreated live, `dgpu-exec-v2 --check` = access OK / gate OK, gated
vulkaninfo sees the RTX 4050, dGPU suspends at idle. **PENDING: real reboot test** (journal
should show BUG-208 "created" lines; `luminos-verify` section 3b would catch a failure).
Mid-session gotcha hit and repaired: `sudo nvidia-modprobe` re-opens UVM nodes to 0666
(BUG-146) — re-run `luminos-uvm-gate` after any manual use. **MW4 still blocked — BUG-209 (R9, ~21:00).** After BUG-208, other Lutris games run on Luminos
(Shawn confirmed) but MW4 dies in 13–16 s: page fault 0xC0000005 at `sp26-cod.exe+0x1D5789`
(`mov (%r10),%eax`, deterministic garbage r10) in obfuscated early-init of the RELAUNCHED game
exe; stub-structure and all ruled-out causes in docs/BUGS.md BUG-209 (GPU selection, locale,
marker, caches, fresh prefix, ccsdownloader, MangoHud, wined3d/vkd3d — all tested, all same
crash; exit 5 = 0xC0000005). The 19-min "engine ran" session was a Vela VM run (qemu CPU) —
bare-metal Luminos has never gotten past this crash. Repack chain fully mapped: bink2w64.dll →
rex_sp.dll (crack, export "r4v3n") + Goldberg emu + ccsdownloader (pack-deleter on CDN timeout
= the Windows reinstall-only symptom). ccsconfig.json = empty variant (bypass); originals kept
as `.orig`/`.empty`; marker `__sp26-cod` restored; GLCache.bak-20261022 + `~/Games/mw4.fresh-partial`
set aside. NEXT: winedbg register capture; qemu -cpu host test; newer GE-Proton; Vela real boot.
Field cleaned (no wine/umu strays); Lutris GUI restarted in -d mode (log /tmp/lutris-debug.log).
WINEDEBUG=+seh in the mw4 yml is inert (Lutris forces -all).
**VELA REAL BOOT TRIED 2026-10-22 — SAME CRASH, TWICE (R2, ~21:50).** Shawn booted Vela and launched
MW4 at 21:12:57 and again from Home at 21:16:09 (first Home Play on `/vela.img` proprietary — that
gameos open item is now closed; the launch chain itself worked: vela-core → vela-lutris → umu → same
shared runner, fresh prefix bootstrapped, NVIDIA renderD128 active under gamescope). **Both runs died
within 4 s of exe start with the same exit code 5 / 0xC0000005** (Vela journal: `Child exited with
wait status: 5`, return code 1280; Lutris: "game has run for a very short time, did it crash?").
The mw4-vela-tracker captured run 1 fully: `~/mw4-vela-capture-20261022-211213/` (per-second process
tree, dGPU state, journal). vela-telemetry: dGPU woke (active, 0% util, 12-23 MiB) and was back
suspended by 21:16:43, gpu_util=na — no frame rendered. **BUG-209 is now proven OS-independent**
(kernel 7.0.5+610.57 Luminos vs 7.2.6+615.71 Vela, Plasma vs gamescope, fresh prefix) — it is the
repack/crack/game itself or a CPU-feature branch in the obfuscated init. Only remaining known-good
run: the qemu-CPU VM. **NEXT (ordered):** (0) newer GE-Proton — **DONE 2026-10-22 ~21:55, CRASHED
(exit 5, ruled out)**; (0b) **config matrix exhausted ~22:25** — UMU_ID/GAMEID 1938090, d3d_extras/
dxvk_nvapi stripped, MangoHud off, old-prefix lineage restored, even full offline (`unshare -n`):
ALL same 2-15 s exit-5 crash. Full register capture obtained (`~/Games/mw4-evidence-20261022/`).
**HEADLINE: the demonware CDN is the surviving variable** — HTTP 200 during the only two
engine-alive runs (19:44, 20:39), HTTP 503 during every crashing run since (verified 22:22; no VPN
confounder; offline also crashes — the game needs a HEALTHY server; also explains the Windows "runs
once then dead" symptom as CDN health, not pack deletion — packs untouched all night).
**AUTO-RETRY LIVE: `mw4-cdn-watch.service`** (user unit, gameos/os/scripts/mw4-cdn-watch.sh) polls
the CDN every 5 min and auto-launches MW4 via Lutris + notifies Shawn at the first 200 (log
`~/.local/state/luminos/mw4-cdn-watch.log`, flag `mw4-cdn-launched.flag`; remove unit+script when
BUG-209 closes). NEXT when it fires: watch the run; if it STILL crashes with CDN 200, the wine-side
lead is the crash thread's two stubbed NtQuerySystemInformation classes (0x91, 0xA5) right before
the fault + a working winedbg --auto capture. Vela re-test pointless until a Luminos run survives.
Vela run
details filed in docs/BUGS.md BUG-209. Vela-side noise (not the cause): gamemoded exit-127 on its
split_lock_mitigate script; Proton "unable to use parent for game drive /mnt/win-os". BUGS.md
duplicate BUG-208 (GLM MCP entry) renumbered → BUG-210.

## Previous aim (2026-10-22, done) — GLM-5.3 in Claude Desktop, side by side with Max (DECISION 156)
- KDE menu **"Claude (GLM-5.3)"** = `scripts/luminos-claude-glm`: second app instance,
  `--user-data-dir ~/.config/Claude-glm`, 3P config in `~/.config/Claude-glm-3p`.
- `scripts/luminos-glm-proxy` on **:4141** (user unit) renames `claude-*` model ids → abliterated
  models and holds the real key. Terminal `claude-glm` unchanged. Normal Claude app = Max always
  (`luminos-claude-mode` retired). Proven live 2026-10-22 18:33.
- Model = `abliterated-model-large-v2` (GLM-5.3, 1M ctx, **text-only → images 400**, $3 in / $0.30
  cached / $5 out per 1M, reasoning always on). Abliteration speaks native Anthropic /v1/messages
  (streaming, tools, cache_control) → **no ccr needed**. Key file `~/.config/luminos/abliteration.env`
  (+`GLM_LOCAL_TOKEN`).
- UNKNOWN: whether large-v2 counts as a "higher-capacity" model (Developer plan = standard only) —
  check the Playground model list before paying. Plan credit never expires.
- claude.ai account projects don't exist for GLM → use the `~/luminos-os` folder in the GLM window;
  project docs copied to `gameos/docs/claude-project/`.
- **NOT yet seen before this chat: a real Cowork task in the GLM window** (tool use, compaction at
  1M ctx). **This session is that first test.**

## Why / motivation
Shawn wants local/GLM inference usable from the Claude Desktop UI without giving up the Max-plan
app; side-by-side (DECISION 156) avoids the sign-out trap: switching deploymentMode signs the app out
of claude.ai, and a re-login resets folder grants (BUG-187). Never set `disableDeploymentModeChooser`.

## Process / approach being used
AGENTS.md §8 session checklist: read HANDOFF → AGENTS → search luminos-notes / brain / MemPalace →
domain docs → surgical changes with `[CHANGE: agent | date]` tags → §13 doc triggers → notes + brain
+ commit (from a host shell — see gotchas). In this GLM Cowork session there is **no host-shell
MCP**; `mcp__workspace__bash` is the Cowork VM, not the G14 (it cannot see the desktop session,
systemd, the GPU, or run luminos-notes reliably).

## State — what is DONE
**GLM setup (DECISION 156 + amendment)** — everything in "Aim right now"; committed at `e3177cd4`.

**Power spectrum v5.0 (DECISION 146, live since 2026-10-15)** — one continuous PPT dial 15–45 W,
Thi AC 82 °C, fan curve v6, asusd.neutered (`asusd.ron` 3× false), config `/etc/luminos/config.toml`.
Rollback: AGENTS §15 (binary `.pre-spectrum`). Measured: 0 dGPU wakes, +14 % ops at 82 °C, quieter.

**nvdefer (DECISION 147)** — NVIDIA open driver DKMS patch holding firmware/asusd power notes while the
dGPU sleeps; installed, rebooted, live.sh ALL PASS (asusd curve rewrites → 0 wakes; replay works;
card re-sleeps in 21 s). `pacman -Qkk nvidia-open-dkms` reports 2 modified files — expected.

**Windowstyle "Nexus look" (DECISIONS 138–141, 143, 144; BUGS 193, 195–197)** — KWin decoration
`luminos-kdecoration-chromeos` + forks qqc2 6.30.0-1.6, kirigami 6.30.0-1.6, kirigami-addons
1.13.1-1.2, kcmutils 6.30.0-1.1, systemsettings 6.7.5-1.6, darkly 0.5.40-1.2, plasma-desktop 6.7.5-1.2
(all `packages/*-luminos/`, warn-only pacman hooks). Checker: `scripts/luminos-windowstyle-check`.
**BUG-199 crash catcher installed (DECISION 145)**: `luminos-greeter-catch status`, reports in
`~/.local/state/luminos/greeter-crash/` — waiting for Shawn to reproduce (lid close/open) so the
newest crash log can be read and the lock-screen wallpaper bug actually fixed.

**Media server (separate machine, `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`)** —
Playback Doctor phases done: census (21 files), log truth (46 sessions, 7 real failures; phone uses
tailnet IP even at home → DECISION 142 caps it at home too), format measurements. Applied:
DECISION 148 (throttling, segment deletion, 30-day logs), 149 (Intro Skipper: no scan on import,
nightly 04:00), 150 (`luminos-phone-cap` timer: home = no cap, away = 8 M), 151 (nft udp 41641
accept), **153 (auto-fix on import: `luminos-media-fix` + Sonarr/Radarr Custom Script hook id 2 +
nightly 03:30 timer; all 21 files fixed — 22 sidecars, 23 default flags; Roku PlaybackInfo
DirectPlay verified)**. BUG-205 (EnableTonemapping broke HDR transcodes; no OpenCL runtime) reverted
to false. Jellyfin API key at `/etc/luminos/media-fix-jellyfin.token` (root:media 0640).

**Claude Desktop** — app at 2.31226.1 (BUG-191 fixed, DECISION 133); BUG-192 host-shell MCP timeout
crash fixed in `~/.local/share/claude-host-shell/server.py`. @-mention needs the chat to be in the
folder-bound space, not an account project.

**2026-10-20 Windows partition fix** — `/etc/fstab` win-os line was missing the ntfs3 `force` option
its comment promised; added (backup `/etc/fstab.bak-20261020-ntfsforce`), mounted rw, write test OK.

**2026-10-20 `scripts/vela-wine-install`** — adds a Windows game to Lutris with Control's proven Vela
settings; folder mode proven against a sandboxed pga.db; **installer mode (setup.exe) NOT yet tested
with a real installer.**

**Tab Sleeper 3.2 runaway guard** — heap > 600 MB or long tasks ≥ 50 % for 2×60 s → reload same
second, max 1 per tab per 10 min; live tests 3/3 PASS.

## State — what is IN PROGRESS (and where it was left off)
1. **This GLM Cowork session = first real GLM-window task.** Watch for: tool-heavy behaviour,
   compaction near 1M ctx, anything the proxy/model id rename breaks.
2. **OpenCL runtime on the server (for correct HDR tonemapping)** — AUR
   `intel-compute-runtime-legacy` building via Shawn's terminal: `nohup yay --noconfirm --builddir
   /srv/media/.aur-build` (MAKEFLAGS=-j6, log `/srv/media/.aur-build/build.log`), expect 3–6 h
   (LLVM 14 + IGC on a 4c/8t U CPU). First attempt cloned llvm into `~/.cache/yay` on the 40 G root —
   killed and cleaned (root back to 21 G free); nothing was installed. `--noconfirm` makes pacman
   REFUSE (not accept) any conflict that would remove `intel-gmmlib`. A 30-min send_later check was
   armed in the Max-window chat.
3. **BUG-199 lock-screen wallpaper** — catcher installed; needs Shawn's repro (lid close/open) then
   read the newest crash log and fix.
4. **Spectrum + nvdefer tests needing Shawn present:** suspend/resume + ROG-key event tests
   (spectrum); `sudo bash tests/nvdefer/charger.sh` (unplug + replug).
5. **BUG-204 question for Shawn:** heavy CPU while battery CHARGING flaps EC GPU D-level (~75 notifies
   + 4 dGPU wakes in 40 s) — was the charger USB-C or the barrel brick?
6. **Server leftovers:** `/usr/local/bin/ozark-warm-once` (contains Jellyfin token) still on the
   server; `sudo rm` blocked by the Max session's permission classifier — needs Shawn. No live import
   through luminos-media-fix seen yet. Local llama.cpp binaries broken on CPU (llama-server asserts,
   llama-bench missing symbol) — not fixed.
7. **`main` is ahead of origin, unpushed on purpose — Shawn's call.**

## Next steps (ordered)
1. Finish/observe this GLM Cowork session; report how the GLM window handles real tool use (the
   DECISION 156 open question).
2. When the server OpenCL build finishes: verify (`clinfo`), re-test an HDR transcode, then decide
   re-enabling EnableTonemapping (BUG-205) — with a 300 s auto-revert like other server changes.
3. Shawn: chrome://extensions → Luminos Tab Sleeper → **Reload** (3.2 runaway guard + still-pending
   v3.0 2-tab cap are not live in Chrome until that click); while there turn OFF Memory Saver.
4. Shawn repro for BUG-199 (lid close/open) → read `~/.local/state/luminos/greeter-crash/` newest.
5. Spectrum suspend/resume + ROG-key tests; nvdefer charger.sh (both need Shawn at the box).
6. Commit this handoff reset from a host shell; run `luminos-notes.sh add [DOCS]` there too (VM
   cannot write `.notes.db` — disk I/O error from the bridge).
7. Open AGENTS.md §14 task list for the long-parked items (Eye model, HIVE web panel, etc.).

## Key decisions & constraints
- **No Docker, no Ollama** (inference = bare llama.cpp); **identity tags mandatory** on edits;
  `cmd/` Go daemons only when explicitly instructed (§11).
- **4.6 GB safe VRAM resident / 6 GB foreground** (DECISION 58); one GPU model at a time.
- **dGPU must stay asleep at idle** (BUG-047/182/198): nvidia-powerd MASKED (not disabled);
  `luminos-dgpu-watch` re-masks it; `lspci`/`lshw`/`inxi`/bare root `nvidia-smi` all WAKE it.
- **Profile/fan-curve writes wake the dGPU** (ACPI NVPCF notify) — route through `setProfile()`,
  deadbands on every threshold pair; nvdefer now blocks the notifies during sleep.
- **Never re-download media to fix subtitles** (Shawn). Server changes get 300 s auto-revert.
- **Never restart Claude Desktop from a bare agent shell** (BUG-187) — `scripts/luminos-claude-restart`.
- **Media server work goes in `server/`**, decision numbering continues the main sequence.
- AGENTS.md §9 System Config table is authoritative for every `/etc/` change (why + revert).
- Working preferences (CLAUDE.md): stay out of personal files; `/build` needs ≥1 Opus(high)/Fable
  worker; keep Vela `.md` docs updated; file work in MemPalace.

## Gotchas / dead-ends / things NOT to redo
**`mcp__workspace__bash` is the Cowork VM, not the G14** — no desktop session, no systemd, no GPU,
no `luminos-notes` (`.notes.db` writes fail with disk I/O error), and **git commands over the mount
time out** (seen twice, pre-reboot session). **The post-reboot session has working `mcp__host-shell`
access** (BUG-207 fix proven end-to-end again) — use host-shell for notes, git, and anything that
must touch the real machine; `mcp__workspace__bash` remains sandbox-only.

- **Never `pkill -f` broad patterns** — Cowork's sandbox is a `qemu-system-x86_64`; killing it ends
  the session. Same for anything qemu-shaped.
- **Never `git add -A` in this repo** — name paths; parallel chats share this tree.
- `luminos-brain safe` has produced a false NO five times → escape hatch `--reason "…"`.
- **BUG-171: a deploy is not a load** — restart plasmashell after every QML deploy.
- **A frozen counter dates the END of an event, not its cause**; runtime-PM has no timestamps.
- `lsof`/`/proc` answer "who has it OPEN", not "who holds a REFERENCE" (nvidia-powerd: no fd at all).
- Wallpapers/media must render on the **780M, never the 4050**; `KWIN_DRM_DEVICES` +
  `__EGL_VENDOR_LIBRARY_FILENAMES` pins must never be undone.
- Server: ground truth for transcode questions is Jellyfin's own ffmpeg command lines in
  `/var/log/jellyfin/`; `sudo -n` works over ssh.
- ⚠️ `docs/BUGS.md` was once found truncated (~14 lines) by another writer — check
  `wc -l docs/BUGS.md` (≈8 170) before committing it.
- Old-handoff detail (Roku wifi, BUG-189/188, DECISION 132 warm timer, etc.) is in git history:
  `git show HEAD:HANDOFF.md`, `docs/BUGS.md`, `server/DECISIONS.md`.

## Gaming OS (Vela) — pointer only
Own repo **`gameos/`** (parent `.gitignore`s it), own handoff **`gameos/HANDOFF.md`**. Installed on
this disk since 2026-09-20 (DECISION 130): `/vela.img` + `/boot/vela/` + one `custom.cfg` menuentry;
Luminos itself unchanged. Undo: `gameos/os/install/vela-uninstall.sh`. Rules: nothing from Vela is
installed/configured on Luminos; **never `swapoff -a`** (`/swapfile.luminos` is unit-owned, not
fstab); never export per-app GPU vars from session scripts; test in QEMU via
`gameos/os/scripts/vela-vm.sh`, kill only with `vela-vm-kill.sh`.

## Files touched / relevant files
**This turn (2026-10-22 R1, GLM window):** `HANDOFF.md` only (tripwire reset). No code, /etc,
package or service change on Luminos. AGENTS.md untouched.
**GLM setup (previous turns, committed `e3177cd4`):** `scripts/luminos-claude-glm`,
`scripts/luminos-glm-proxy`, `~/.config/Claude-glm-3p/`, `~/.config/luminos/abliteration.env`,
LUMINOS_DECISIONS.md (156), LUMINOS_STATUS.md.
**Media server this week:** `/usr/local/bin/luminos-media-fix`, `/etc/luminos/media-fix-jellyfin.token`,
Sonarr/Radarr hook id 2, nightly 03:30 timer (server/STATUS.md, server/DECISIONS.md 148–153).
