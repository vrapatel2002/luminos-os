# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-29 — Response 3

## Goal (the durable end objective)
Keep Luminos OS + the home setup working as a daily-driver; Vela (gaming OS, gameos/) gets more graphics + frames.

## Aim right now (Vela, three threads)
1. **BUG-221 controller dead in Home after quitting a game** — FIXED in code, on TEST OS only (R25), proven off-hardware.
   Waiting on Shawn's hardware test (BOARD "Next test" step 7). Then promote to /vela.img (VELA_R25_ALLOW_MAIN=1).
2. **Music card** (PS-menu → small Music panel: search, ±10 s, prev/next, album, discover, no ads) — interactive prototype
   published as Design canvas "Vela Music Card" (artifact Mr9nMHvPe7HUxqHhSsK9pk). Waiting on Shawn's approval/changes.
   Planned backend: mpv + yt-dlp (YouTube Music, no ads by construction) driven over mpv IPC from vela-core; QML page in Guide.
3. **DLSS 5 on the 4050** — first game Control (Shawn). DLSS 5 is OFFICIAL since 2026-09-03 (RTX 50; NVIDIA says RTX 40
   "later this fall"). Linux 610/615 drivers do NOT ship nvngx_dlssnr.dll (checked). Shawn asked Claude to fetch the leaked
   DLL — declined (leak mirror = NVIDIA's unreleased IP + malware risk). Options given: his own NBA 2K27 copy, or wait for
   NVIDIA's RTX 40 rollout. Everything else (installer, ReShade, test plan) can be prepped. Details: gameos/docs/tracks/DLSS5.md.

4. **Input lag in Wukong on /vela.img (Shawn 10-29, session 16:40–17:00)** — diagnosis given, nothing changed yet.
   Evidence: pad WIRED (usb5) → not Bluetooth. GPU 95–97 % all run, VRAM 5.8/6.0 GB, SW-thermal throttle (0x20) in 57 %
   of rows, 4050 68–76 W (boost on), CPU 26 % (not the limit). Reflex WORKS (nvapi: SetSleepMode Enabled, latency markers).
   Game (dx12fix prefix): no fps cap, vsync off, DLSS Perf (ResolutionQuality 50) at 2880x1800, RT off, Shadows+GI 3, Tex 2.
   Panel VRR range 48–120 Hz (eDP-2, vrr_capable=1); gamescope --adaptive-sync on. Wukong ~35–45 fps = BELOW 48 → LFC only.
   No fps CSV this run: nvk-play promises a MangoHud log, /var/log/vela/mangohud/ has nothing since 09-27 (bug, not traced).
   Asked Shawn: is it "heavy/slow" (latency) or "hitches" (frame spikes)? Proposed: lower Shadows/GI/Textures, Reflex
   On+Boost, cap a few fps below what holds; Claude to fix fps logging; MUX dGPU-direct (BOARD #12) = his call.

## Key facts / evidence
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
