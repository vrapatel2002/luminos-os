# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-30 — Response 1 (GLM chat: build-skill mod)

## Aim right now — WUKONG CRASH INVESTIGATION (GLM chat R4, 2026-10-30) — read seat handoff first
Source docs: gameos branch `seat/seat/2026-10-30-wukong-handoff` → docs/handoff/WUKONG-CRASH-2026-10-30.md +
~/vela-remote/SESSION-LOG.md on the server. Crash: b1-Win64-Shipping.exe+0xcb53190 reads 0xffffffffffffffff,
~2-8 s after launch, before window; thread does NtQuerySystemInformation(0x66), SystemCpuInformation, SGDT,
direct syscalls, openssl.cnf/Afd lookups (environment fingerprinting).
MY INDEPENDENT FINDINGS (R4, all on Luminos directly):
1. **IT CRASHES ON LUMINOS TOO** — reproduced 20:15 (dgpu-exec-v2 + GE-Proton11-6-dx12fix + shared dx12fix prefix,
   same env shape as nvk-play): dead at ~10 s, crash dir UECC-…2B37CCD3, same -1 read at base 0x140000000.
   NOT Vela/MUX/image specific. Test log /var/tmp/wukong-luminos/run.log + run.sh (rerunnable).
2. ALL runs on all 3 OSes share: game folder /mnt/win-os (files FROZEN since Sept — only vkd3d-proton.cache moves),
   runner ~/.local/share/lutris/runners/wine/GE-Proton11-6-dx12fix (ON LUMINOS HOME — Vela mounts it), prefix
   ~/Games/umu/dx12fix (shared; crash dirs from every OS land here).
3. Runner mods (MW4 BUG-209, 10-23: bin/wine wrapper + proton LD_PRELOAD=mw4map.so) EXONERATED: mw4map.so does not
   exist anywhere (no-op), the UMU branch never fires under nvk-play (no UMU_ID), AND the good 10-29 16:40 run
   postdates the mods. Seat missed that `proton` was also replaced (backup proton.orig-mw4) — diff is 3 lines.
4. Nothing in shared game state changed 10-29 17:00→22:25 (find sweep; only the good run's own artifacts until
   17:00:32, then Control prefix rebuild 20:41 in its own folder). Clock sane, NTP synced.
5. pacman.log Sept-26→Oct-18: only KDE theming packages — no kernel/driver/microcode/nvidia change (all pinned).
6. Remaining suspects: (a) firmware/UEVI/EC state vs the 10-29 16:39 good boot (seat item #1 — snapshots on server),
   (b) something pre-10-17 that also broke it then (10-17 17:59 crash predates ALL MUX/runner work — unexplained),
   (c) Windows-side test never done. Minidumps fresh in the shared prefix from today.
NEXT (Shawn's order R7): music ✅ → MUX dGPU-direct → DLSS 5.
R14 — BASELINE MEASURED + MUX RESTORED (waiting on Shawn's dGPU-direct runs):
BASELINE (test OS, Hybrid, FG off, 10-30): Wukong avg 37.1 / median 39.1 / 1% low 8.5 (2.4k frames);
Control avg 30.2 / median 31.2 / 1% low 4.4 (worst 379 ms — "stuttery"; 12 stutter frames). Good-era main
10-29 reference: Wukong 43.8/12.8, Control 43.7/12.3 (different night — indicative only). CSVs live on
LUMINOS /var/log/vela/mangohud/ (nvk-play MHLOG output_folder=/mnt/luminos/...) — NOT inside the image.
MUX RESTORE DONE: from /var/log/vela/seat-r28-r29-removed-20261030/ into /vela-nv.img — merged
vela-core (r29: FG+music+EGL fix; R27 core backed up .prev-r30mux), vela-session r29 (EGL pin,
backup .prev-r30mux), vela-mux + vela-mux-enter.service (enabled) + /etc/vela/mux-direct. Verified
(FG strings, bash -n, unit symlink). Next test OS boot = MUX 0 dGPU-direct, BUG-223 EGL fix in.
⚠️ REMOVED R15: exit Vela HOWEVER you like — luminos-mux-guard is BACK (DECISION 166): any exit
path lands Luminos on Hybrid automatically (worst case one auto-reboot, never black). Vela always
boots dGPU (vela-mux enter). Verified enabled; MUX=1 today.
SHAWN'S NEXT RUNS (A/B, same areas/settings as baseline): Wukong ~5 min + Control ~5 min on test OS,
then reboot to Luminos, "done" → PM re-extracts CSVs and compares avg/1% lows. Note: quit Wukong
FROM IN-GAME (bug #22: PS-quit blocks the next launch) and expect the white flash (#21) — both filed
in BOARD, to be fixed after the A/B.
R16 — A/B DONE (numbers + verdict in BOARD #23-26, commit 2817c7c): WUKONG avg 37.1→47.5 (+28 %),
1 % low 8.5→7.3; CONTROL avg 30.2→30.9 (no gain), 1 % low 4.4→3.2, stutter 0.6→1.7 % (95 s run — repeat).
padlat PROVES input path fine in both modes (~4-5 ms usb/bt) — felt input delay = 275-368 ms frame
stalls. New dGPU-direct bugs: #24 bottom-of-screen colored pixels (scanout artifact, MUX 0 only),
#26 Control more stuttery. Gotcha: Wukong dGPU CSV APPENDED to the 10-29 filename (clock fix fakes
the date → name collision) — split sessions on repeated header rows when parsing.
OPEN: MUX verdict (Wukong +10 fps avg vs Control regression + artifacts). Next: repeat Control longer
in dGPU-direct, then #24 artifacts investigation. Per-boot either/or — MUX flip needs a reboot.
R17 — INPUT-DELAY ROOT CAUSE + LEVER 1 ARMED: stalls = VRAM-ceiling evictions (Wukong 5.84/6 GB,
Control 5.82 GB max; swap/psi 0; GPU 0x4+0x20 power/thermal capped 72-78 W throughout). This also explains
dGPU-direct giving Control nothing (MUX 0 = panel+session VRAM on the 4050) AND the good-era Control 43.7
vs tonight ~30 in BOTH modes (a separate, non-MUX Control regression — re-test tomorrow, longer).
LEVER 1: VELA_FPS_CAP 0→42 on test OS (backup vela.conf.pre-cap42-20261031; off-switch = set 0,
Shawn's R56 preference). SHAWN: one Wukong run ~5 min, same area; PM compares vs tonight's dGPU run
(47.5 avg / 7.3 low / 1.2 % stutter): if lows rise + worst frames shrink → keep, else revert to 0.
Deeper levers queued: VRAM headroom (overlay/session diet, vela-vramd), Control regression hunt.
BUGS FILED (gameos BOARD, commit 4d55ded): #21 Wukong launch white flash; #22 PS-menu-quit of
Wukong blocks launching any other game (in-game quit fine, other games fine via PS quit).
R12 — BASELINE-FIRST PLAN (Shawn: measure avg fps + lows so we can compare; optimize the OS not the
game; one thing at a time; test OS then main). NO baseline fps exists yet (checked: no MangoHud CSVs
ever written — all Wukong runs died pre-log; BOARD #5 open). Current test OS state is GOOD for
baseline: R26 logging wired (vela-core MANGOHUD_CONFIGFILE + nvk-play MHLOG block), VELA_GAME_GPU=dgpu
(FG off = clean single-variable). PROTOCOL: Shawn boots test OS → Wukong ~5-7 min same area + settings
recorded → Control ~5 min same area → reboot to Luminos → PM reads /var/log/vela/mangohud/*.csv
(avg, 1% low, 0.1% low). Then MUX phase (merged vela-core 091098a + R29 EGL pin + new MUX mechanism;
FG stays OFF for the A/B — FG comparison is a separate axis) → repeat identical runs → compare.
Tasks #3 (baseline) → #4 (MUX build) → #5 (post-MUX compare).
(0) R8 — R27 music now on BOTH images, same older tested code (no new code): TEST OS verified complete
(vela-core sha == .r27 build, vela-home MusicPage, 55 pkgs); MAIN /vela.img applied via
os/experiments/r27-music/apply.sh + VELA_R27_ALLOW_MAIN=1 (fresh installs, zero upgrades; .prev-r27
backups kept for `apply.sh revert`). SHAWN'S TEST: boot test OS → PS button → System row → Music → play;
then same on main. After his OK → MUX phase (merged vela-core 091098a + R29 EGL pin + new MUX
mechanism, luminos-mux-guard is gone per DECISION 164) → then DLSS 5. Wukong clock-helper queued.
(2) NEXT PHASE — MUX dGPU-direct: install the MERGED vela-core (gameos commit 091098a: frame gen +
music + EGL fix) + R29 vela-session EGL pin back into the test OS (os/experiments/r29-nvegl/apply.sh),
rebuild luminos-mux-guard? NO — Shawn wants MUX things gone from Luminos (DECISION 164); Vela-side MUX
(dGPU-direct) needs a NEW mechanism or BIOS-manual. NOTE: seat removed R28/R29 MUX code from the test OS
10-30 17:48 (archived /mnt/luminos/var/log/vela/seat-r28-r29-removed-20261030/). Wukong clock-fix helper
also still to build (see R6 notes below).
(3b) R9: Shawn booted test OS (Wukong crashed — expected, no fix installed) and back on Luminos
(21:46 crash, same -1 signature — confirmed). Explained to him: the clock trick was a diagnostic, the
permanent clock-back launcher is still the queued work ("Wukong clock-helper"); it must go into Vela
nvk-play (both images, needs a way for vela to set the clock) + a Luminos launcher. PRIORITY NOW per R9.
R10 — FOREVER FIX **DONE + LIVE-PROVEN** (Opus worker built, PM finished + verified; DECISION 165):
/usr/local/bin/wukong-clock (arm: set clock to fixed 2026-10-29 12:00, self-restore 90 s later,
idempotent, NTP-safe, never touches RTC) wired into (a) Lutris prelaunch on Luminos (yml patched,
.bak-wclock backup, wrapper /usr/local/bin/wukong-clock-luminos; PM fixed a YAML-space bug the worker
left) and (b) nvk-play in BOTH Vela images (gameos os/experiments/wukong-clock/apply.sh, .prev-wclock
backups, idempotent). LIVE PROOF: `lutris lutris:rungameid/4` → clock armed automatically → game alive
>55 s → clock restored at 90 s → game survived, zero new crashes, helper state clean. Tests:
~/builds/wukong-clock/TESTS.md. If the game ever updates its date check, bump FAKE_DATE in the script.
Music on main: already applied R8 (both images carry R27; Shawn boots to verify). Next: MUX dGPU-direct,
then DLSS 5.
(3) DONE R6: WUKONG ROOT CAUSE — time-keyed startup check (expired 10-29 16:40-22:25 EDT). Proof: clock
set back to 10-29 12:00 → game runs fully (survives real-clock restore mid-run = startup-only check);
faketime does NOT work (stalls pre-log even with NO_CACHE + DONT_FAKE_MONOTONIC=0 — reads time where
libfaketime can't reach). Worker evidence: Opus RE ~/re/wukong-re/REPORT.md (fault = #GP on garbage
rdi=0x49544100000070af at RVA 0xcb53190 after CPUID/syscall fingerprint + CityHash64 of a 27-byte key +
VM-obfuscated voices38.dll); Sonnet /tmp/fw-compare/REPORT.md (no BIOS/microcode/ACPI/SMBIOS drift —
firmware exonerated; no fw snapshot baseline exists = gap). FIX TO BUILD: privileged clock-back helper in
Vela nvk-play (set clock back, launch, restore ~60 s later; date changes need root). MW4 parked per Shawn.
Game closed on Shawn's word R7. Evidence ~/re/wukong-re/, test scripts /var/tmp/wukong-luminos/.

## Goal (the durable end objective)
Keep Luminos OS + the home setup working as a daily-driver; Vela (gaming OS, gameos/) gets more graphics + frames.

## GLM-5.3 Claude window (glm chat, 2026-10-30 R10) — DECISION 162 DONE, one step waits on Shawn
GLM window = second Claude Desktop (`luminos-claude-glm`, profile ~/.config/Claude-glm[-3p]) → `luminos-glm-proxy`
:4141 → Abliteration (DECISIONS 156 + 162, BUGS 207/208/211). New today, all proven by real runs:
`luminos-worker` (any model incl. real Claude on Max; `--batch` for parallel; `--resume`), `luminos-chats`
(list/read all chats, send to terminal/worker ones), `luminos-desktop-mcp` (GLM-only app control: windows, launch,
AT-SPI ui_tree/click/set_text, keys via ydotool, screenshot; a11y + ydotoold only on while used), skills via
`config/glm/luminos-skills.plugin` (built by `luminos-glm-skills`).
R11 proven: GLM itself (claude-glm -p) opened a real Opus chat via luminos-worker, continued it with luminos-chats send (answered 84 from remembered 42), and opened a Fable chat — modelUsage claude-opus-5-5 / claude-fable-5-1.
R12: skills now installed automatically (scripts/luminos-glm-skills-install mirrors the app's upload code; launcher
runs it each launch while the window is closed). VERIFIED in the GLM window UI: Customize → Skills lists build +4.
Electron's accessibility tree needs --force-renderer-accessibility (only used for that check). R14 BUG-224: both apps' Cowork helpers fight over vsock 51234 + the same unix socket; FIXED (DECISION 163): GLM app runs in netns claude-glm (vsock local) + private XDG_RUNTIME_DIR via scripts/luminos-glm-netns + luminos-claude-glm; proven two sandboxes at once + GLM task ran in its own sandbox. (Reboot at 20:31 cleared the stale Max socket.) R15 BUG-225: after reboot vsock module not loaded → netns up failed silently; up now modprobes vhost_vsock + clear error; verified. R13: build-addendum reworded — GLM has full laptop access via host-shell; sandbox Bash only sees the task folder. Copying skills into skills-plugin/ does NOT
work (the app's sync deletes them every 10 min). Desktop-window chats can't be typed into from outside.

## Aim right now (Vela) — everything new is on the TEST OS (/vela-nv.img) only
1. **R27 Music card** (Shawn asked to build it) — DONE + e2e PASS inside the image (real YouTube Music via vela-core ->
   mpv + yt-dlp, ao=null). Doc: gameos/os/docs/MUSIC-01.md. Not yet heard through speakers.
2. **R26 fps logging** — DONE (BUG-222: MangoHud logs nothing under no_display; hidden is now alpha=0). Proof table in
   gameos/os/experiments/r26-fpslog/README.md. Next game run on the test OS must produce /var/log/vela/mangohud/*.csv.
3. **dGPU only for Vela** — Shawn asked "possible?" -> yes; PROPOSAL gameos/os/docs/DGPU-DIRECT-01.md (Vela flips MUX
   in/out + a Luminos early-boot guard that forces Hybrid). Needs Shawn's go (firmware MUX + a Luminos /etc unit).
3b. Response 5: Shawn asked "launch directly on dGPU without restart?" — answered NO for the laptop panel: the MUX is
   applied by firmware at POST; NVIDIA Advanced Optimus (live switch) has no Linux support (2022 RFC only). The reboot is
   free anyway (entering Vela is already a reboot). HDMI/TV is already wired to the 4050 = dGPU-direct today.
3c. Response 6 — Shawn: dGPU-direct YES → BUILT (DECISION 161): Luminos luminos-mux-guard.service ENABLED (+ luminos-play-vela,
   desktop entry "Play on Vela (dGPU)"); Vela R28 on test OS. Lag answer = mostly "late", worst in heavy action, presses
   (game's settings/pause button) need 2-3 tries → R22 re-applied on test OS for vela-padlat (input path timing) + R26 fps log
   will show frame stalls. DLSS 5: Shawn asked Claude to get/patch the leaked DLL — declined again (won't fetch or modify
   NVIDIA's leaked binary); offered to prep the open-source chain; also DLSS 5 costs ~10-20 ms/frame = makes his lag worse.
3d. Response 7-8 — first MUX boot: Home garbled (BUG-223). Shawn hard-reset; luminos-mux-guard fixed the MUX (works).
   R29 on test OS: NVIDIA EGL pin in vela-session + merged vela-core. FOUND: seat's 10-16 frame-gen work had been dropped by
   R26-R28 builds → merged back (gameos 8e53f87). Seat now = git copy (~/vela-remote/gameos), laptop remote `seat`,
   ~/vela-remote/vela-ip finds the laptop. Seat link changed: env_018AByA5JzYVwe6w2KGWzoPK (project doc updated).
   gameos repo has NO git remote (never pushed anywhere) — told Shawn; ask whether to add a private GitHub remote.
3e. Response 9 — Shawn moves ALL Vela work to the server seat (vela-test-os) for this session, no OS switching. Prompt given.
   On return: `cd gameos && git fetch seat` and merge seat/* branches; read ~/vela-remote/SESSION-LOG.md on the server.
4. Still waiting on Shawn: R25 controller test (BUG-221), "heavy vs hitchy" lag answer, DLSS 5 DLL source.
   All of it = BOARD "Next test" steps 7 + 8 on the test OS.

## Key facts / evidence
- R25+R26+R27 binaries are all built from gameos HEAD (vela-core.r27, vela-home.r27 in /var/tmp/vela-build). Reverting R27 restores R26's vela-core (prev-r27); R26 revert restores pre-R26.
- Input lag Wukong 10-29: GPU 96 % uncapped, VRAM full, thermal 0x20, fps under VRR floor 48; Reflex works.
- BUG-221 cause: vela-shell restarts Home the same second the game exits; Home's SDL opens vela-padd's CLONE; padd deletes it;
  the real pad only gets chmod/ACL back (no udev add) → SDL never re-finds it. Fix = SDL gamepad re-init every 700 ms for 14 s
  after the last pad vanishes (gameos/ui/vela-home/src/gamepadinput.cpp). Tests: gameos/os/experiments/r25-padrescan/run.sh, run2.sh.
- Open side question: the wired pad does a full USB disconnect at game START on MW4 runs (21:13:35, 21:16:03 on 10-22) — cause unknown.
- Build: /var/tmp/vela-build/vh (cmake, host Qt 6.11.2 = image Qt; SDL 3.4.16 both). Old binary kept: /var/tmp/vela-build/vela-home.pre-r25.
- host-shell bridge returns after 60 s — run long tests with setsid in the background and read logs after.

## Next steps (ordered)
1. Shawn: test OS → wired pad → Control → quit from the game → Home responds? (read `vela-home: pad rescan` in the journal).
2. Shawn: feedback on the Music Card → then build (QML page + mpv/yt-dlp in the image, test OS first).
3. DLSS 5: Shawn decides the DLL source; meanwhile prep the 24high installer for Control on the test OS (dlaa mode first).

## Gotchas
- Vela rules: BOARD.md first; test OS first; Luminos untouched. gameos/ is its own git repo (ignored by the main repo).
- `luminos-notes.sh` needs sqlite3 — run on the host (host-shell), not the Cowork VM.

## PARKED — DLSS 5 + ad-free music (Response 1 of the previous chat)
Research DONE, nothing installed. Full write-up: `gameos/docs/tracks/DLSS5.md`. Waiting on Shawn's answers.

### DLSS key facts
- DLSS 5 = neural re-rendering for looks; it COSTS fps (5070: 138 -> 68 fps). It is not a frame booster.
- Linux/Proton installers already exist (24high/DLSS5-Reshade-Linux-Steam tested on RTX 4080; pantsoftime/dlss5-linux).
  Need proprietary driver >= 610 — Vela images are 615.71, OK. Ada: optical flow fails under Proton -> shader MVs.
- Real blocker on this laptop = 6 GB VRAM (Wukong already 5.1–5.8 GB) + ~55–79 W. Cost on 4050 unmeasured (est. 10–20 ms).
- We do NOT download the leaked DLL from mirrors; Shawn supplies it, we sha256-check it (legal + malware risk).
- Music: recommended mpv + yt-dlp (no ads by construction, ~50 MB) behind a small QML Music page in Home/Guide.

### DLSS questions put to Shawn
- Which game first (proposed: Control on the TEST OS, it already runs on Vela; Wukong VRAM is full).
- Will he supply `nvngx_dlssnr.dll` (he owns NBA 2K27 EA? / other source).
- Music: OK with mpv+yt-dlp QML page? Also Jellyfin music?

### DLSS next steps
1. Copy installer + DLL to the test OS (`/vela-nv.img`, rule R40 — never /vela.img first); `dlaa` mode, then `nr`.
2. MangoHud + vela-telemetry before/after on the same scene: fps, 1 % low, VRAM, gpu_w.
3. Music: HTML prototype of the Music page first (Shawn's UI rule), then mpv IPC backend in vela-core.

### DLSS gotchas
- Do not say "impossible"; do not promise frames either — DLSS 5 subtracts frames.
- Vela rules: gameos/docs/tracks/BOARD.md first; test OS first; Luminos untouched.
- `luminos-notes.sh` needs sqlite3 — run it on the real host (host-shell), not the Cowork VM.

## PARKED — Roku TV work (last state 2026-10-27, Response 13)
### Why / key facts a newcomer is missing
- The TV is a **Philips 65PUL7973 Roku TV at 192.168.2.13** (server/README.md). It is Roku OS, NOT Android:
  no ADB, no package disabling, no launcher replacement, no Private DNS setting. The video's steps do not transfer 1:1.
- What Roku DOES have: ECP (External Control Protocol) HTTP API on :8060 — device-info, list apps, launch apps, send
  remote keypresses (already used: server/docs/MEDIA_SERVER_PLAN.md). Developer mode allows ONE sideloaded channel.
- Network ad-blocking would have to run on the media server (Inspiron, .61/.62). Constraint: the server is powered on by
  hand — if it becomes the TV's DNS and is off, the TV loses internet. Bell Giga Hub 5690 DHCP-DNS control unverified.
- TV is on 2.4 GHz wifi with an unused ethernet port (MEDIA_SERVER_PLAN.md) — free speed win.

### Proposed final result (awaiting Shawn's confirmation)
1. Control from the G14/server over ECP (scripted, repeatable).  2. Remove unused user channels; reorder home grid.
3. Every ad/tracking/ACR privacy toggle off (driven by ECP keypresses where possible, else a checklist for the remote).
4. Optional: AdGuard Home on the server as DNS for the TV (needs decision on 24/7 server + router DNS).
5. Optional: dev-mode custom channel as a clean "home" (cannot replace Roku Home — Home button always returns there).
6. Before/after proof: ECP readouts (app list, settings state), DNS block counts. A system RAM number like the video's
   is NOT available on Roku — say so, don't fake it.

### Probe results 2026-10-27 (read-only, from the G14 via host-shell curl)
- TV IP CHANGED: now **192.168.2.18** (was .13 — .13 is dead). Now on **ethernet** (network-type: ethernet).
  Needs a DHCP reservation on the Giga Hub; server/README.md still says .13 — update when work starts.
- Roku OS 15.3.4 build 2303, model 65PUL7973/F6 (G418X), developer mode ON (port 80 installer answers 401 = login).
- ECP mode is **limited**: active-app works; query/apps, chanperf, media-player return 403. Shawn must set
  Settings > System > Advanced system settings > Control by mobile apps > Network access = Permissive.
- ECP has no screenshot and no uninstall — menu work is blind keypresses; dev installer screenshot only covers the dev channel.
- I must not type the dev-mode password (safety rule) — any sideload upload is Shawn's click.

### Step 1 DONE (Response 3)
- ECP now `enabled` (Permissive). query/apps works. Snapshot: server/docs/roku/snapshot-before-20261027.xml
- User channels (only 6): Prime Video 13, YouTube 837, Jellyfin 592369, Backdrops 773622, Netflix 12, The Roku Channel 151908 (system, likely not removable).
- query/chanperf returns per-channel memory/CPU while a channel runs -> real before/after metric (no system-wide RAM).

### Shawn's answers (Response 4)
- Remove: ONLY Backdrops (KEEP Prime + Netflix — I misread once, nothing wrong was removed). Shawn removed it with the remote;
  verified via query/apps 2026-10-27 19:05: Prime, YouTube, Jellyfin, Netflix, Roku Channel remain.
- ECP gotcha: launch/11?contentID=<id> opens the store page but Roku OS 15 shows NO Remove button there; removal is
  Home tile -> * -> Remove (blind grid nav not possible, no screenshots). ECP keypress works (Home sent OK).
- DNS ad-block: YES, server stays on 24/7 -> AdGuard Home on the Inspiron.
- Launcher: Shawn wants BOTH clean launcher and JellyRock. Dev mode = one sideloaded app. Proposed: JellyRock in dev slot
  first; launcher = HTML prototype first (his rule), then host as Roku beta channel (needs Shawn's free Roku dev account).
- NEW ASK: play files with real Dolby Vision + best audio, bypass the P5 purple bug (server docs: DV_PURPLE_HISTORY.md).

### DV research (Response 4)
- TV panel supports DV; purple = Roku player ignores DV in MKV (jellyfin-roku #472, closed "can't fix client side").
- Fix A (server): lossless remux MKV -> MP4 with dvh1 tag keeps real DV (reported working in #472). Replace or
  supplement luminos-dv-sweep (today it converts P5 -> HDR10, losing DV). Watch: .mkv->.mp4 path change for Sonarr/Radarr,
  audio codecs in MP4. PROVE on one file before any library change.
- Fix B (client): JellyRock (github jellyrock/jellyrock) tells server MKV unsupported -> HLS remux, DV MKV remux on by
  default. Sideload via dev mode (Shawn uploads; password).
- Audio: Roku TV can't do TrueHD; DTS doubtful -> server audio-only transcode to EAC3 (Atmos-capable). Asked Shawn what
  speaker/soundbar is on eARC.

### JellyRock (Response 6)
- JellyRock IS in the Roku Channel Store: channel id 819325 (github jellyrock/jellyrock v3.2.0, 2026-10-21).
  Installed via ECP `POST /install/819325` -> store page on TV -> Shawn pressed Add. Verified in query/apps (v3.2.0).
- So the dev-mode slot is FREE again for the clean launcher (HTML prototype first).
- Keep the official Jellyfin app until JellyRock's DV playback is proven on a real P5 file.

### DV test (Response 7) — PASSED 2026-10-27 19:22, test state UNDONE in Response 8
- `sudo systemctl stop luminos-dv-sweep.timer` on luminos-server (19:14) so the P5 test file is NOT auto-converted.
- Copied (not hardlinked — luminos-media-fix edits MKVs in place) P5 original to
  /srv/external/_dvtest/VisionQuest DV Test (2026)/Season 01/VisionQuest DV Test - S01E01 - No Strings.mkv
  (HEVC DV P5 compat 0 + EAC3 Atmos 5.1). Jellyfin library "DV Test" (tvshows, /srv/external/_dvtest) added via API.
- UNDO: delete Jellyfin library "DV Test" (DELETE /Library/VirtualFolders?name=DV%20Test), sudo rm -r /srv/external/_dvtest,
  sudo systemctl start luminos-dv-sweep.timer. Do not leave the timer stopped.
- Shawn's audio: SOUNDBAR on HDMI 4 (eARC). Model unknown (asked) — decides Atmos/DTS handling.
- SSH: `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`. host-shell bridge times out at 60 s and queues behind long calls.

### Response 8
- Shawn: JellyRock plays the raw DV P5 file correctly — "true 4K true color". Sound = later (soundbar on HDMI 4; test file had EAC3 Atmos).
- Undone: Jellyfin "DV Test" library deleted (204), /srv/external/_dvtest removed, luminos-dv-sweep.timer started again (active).
  Libraries now: Shows, Movies.
- OPEN DECISION for Shawn: dv-sweep still converts P5 -> HDR10 (loses DV). With JellyRock that is no longer needed on the TV,
  but other clients (old Jellyfin app, phone, browser) would show purple. Also 3 P5 originals sit in /srv/external/_dv_p5_originals.
- Launcher: HTML/Design prototype v1 published (claude.ai Design canvas "Roku Clean Launcher", artifact DeDcKVJkTdYCHx6aJtwjcu):
  clock, server/ad-block pills, Continue watching (Jellyfin resume), Apps row, Inputs row. Awaiting Shawn's approval/changes.
  v2 (Response 9, Shawn: "remove continue watching, make it simple"): clock + date, 3x2 app grid (JellyRock, YouTube,
  Netflix, Prime Video, Jellyfin, Live TV), one row of input pills (HDMI 1-4, AV). No status pills, no resume row.
  Build plan after approval: SceneGraph dev channel; launches apps by POSTing to the TV's own ECP (known technique,
  github umitic/Roku-Channel-Within); resume row from Jellyfin API; sideload = Shawn uploads zip at http://192.168.2.18.

### Launcher build (Response 10)
- Shawn pointed at github.com/humblemuzzu/dumbtv (MIT). It is Fire TV/Android only (Java APK over ADB); its own
  docs/OTHER-TVS.md says Roku = control API only. So: ported the dumbtv home DESIGN (clock, apps grid, inputs row,
  Afterglow tiles, accents, hide/move, Back -> first tile) to a Roku SceneGraph channel. No dumbtv code copied.
- Source: server/roku/dumbtv-roku/ (manifest, source/, components/Home|Tile|EcpTask, images/, README, build.sh,
  LICENSE-dumbtv). Zip: server/roku/dumbtv-roku/dist/dumbtv-roku.zip. Linted with brighterscript 0.69.13: 0 errors
  (fixed reserved words `run`, `pos`).
- Mechanism: Task node -> roUrlTransfer to the TV's own ECP (GetIPAddrs():8060) for /query/apps, /launch/<id>;
  Poster icons from /query/icon/<id>. Settings in registry section "dumbtv". The Roku Channel hidden by default.
- UNPROVEN until on the TV: (1) channel->own-ECP works on Roku OS 15.3.4, (2) icons load, (3) layout fits.
  Verify after sideload: query/active-app shows dev channel; keypress Right/Select via ECP; chanperf memory.

### On-TV result 1 (Response 11)
- Sideloaded OK: clock/date/layout render fine. App list EMPTY -> status message. LAN ECP still fine (query/apps 200
  from the G14, ecp-setting-mode enabled) so the failure is channel -> own ECP.
- Debug console: `telnet 192.168.2.18 8085` (no password) shows channel prints — read with bash /dev/tcp from host-shell.
- Build 1.0.2: EcpTask tries every base (LAN IP, 127.0.0.1, localhost), async with 5 s timeout, logs code + failure
  reason to console and on screen.
- PLAN B if Roku blocks self-ECP: relay on the media server (24/7): channel -> http://192.168.2.62:<port>/apps|launch|icon
  -> server -> TV ECP :8060 (LAN ECP proven working).

### On-TV result 2 + decision (Responses 12-13)
- 1.0.2 on TV: LAN IP, 127.0.0.1 and localhost ALL -> 403 Forbidden for /query/apps. Roku OS 15 blocks ECP from
  on-device apps. Not a setting; keep Control by mobile apps = Permissive.
- Shawn: NO server relay ("server can go down, can't afford it"). Also no DNS ad-block on the server for same reason.
- Bell Giga Hub cannot hand out custom DNS (forum.bell.ca), Roku has no DNS setting -> network ad-block needs a separate
  always-on DHCP/DNS box. Not viable under Shawn's constraint.
- ifAppManager has IsAppInstalled but NO LaunchApp (Roku docs). No public root for Roku OS 15.3.4 known.
- Build 1.0.3: when ECP query is refused, app list = built-in known ids filtered by roAppManager.IsAppInstalled,
  tiles forced to Afterglow (icons come from ECP too). Launch still via ECP POST — UNKNOWN whether also 403;
  if it is, the launcher cannot open apps and the launcher track is dead -> fall back to Roku home settings cleanup.

### Next steps (ordered)
1. Shawn confirms goal + answers: which annoyances matter, DNS-on-server yes/no, ethernet cable possible, docs location.
2. After Permissive: snapshot app list + settings; write server/scripts/luminos-roku (status/apps/launch/key).
3. Then build.

### Gotchas
- Do not claim Android-only steps are possible on Roku; do not claim everything is impossible either (ECP covers a lot).
- Server work rule: server stuff goes in server/ docs, not G14 docs.

## Still open from before (untouched)
- BUG-187 Claude Desktop re-login: supervisor fix installed in scripts/luminos-caelestia-plasma (effective next login);
  waiting on Shawn to click "Sign in again" then verify main.log (Chrome start, claudeURLHandler, no session_stale_relogin,
  MCP servers connect); write BUG-187 addendum + commit. Launch Claude Desktop via luminos-claude-restart, not the bar.
- VisionQuest DV P5 sweep verification (BUG-207/DECISION 156); MW4 BUG-209; server OpenCL build; BUG-199 repro;
  spectrum/nvdefer tests; BUG-213; coder pruned-model tests.

## Files touched / relevant files
HANDOFF.md only. Read: AGENTS.md, server/README.md, server/docs/MEDIA_SERVER_PLAN.md, server/STATUS.md.
