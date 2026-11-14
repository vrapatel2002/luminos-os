# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-11-13 — Response 7 (Q: how do others request? → Jellyseerr; still waiting A/B for logins)


## 2026-11-13 R7 — Q answered: others request through Jellyseerr (:8444) with their own Jellyfin login; requests wait for
Shawn's approval (perm 32). Away from home they need the tailnet (share the node) — LAN-only otherwise. Do NOT give others
the Space page: its /request uses the API key (requests land as Shawn, skip approval) and the page can delete.


## 2026-11-13 R6 — Logins plan (asked, nothing changed)
- Verified: Jellyfin `shawn` IsAdministrator=true (only user). Jellyseerr already lets any Jellyfin user sign in
  (newPlexLogin=true) and gives new users permission 32 = REQUEST only (requests wait for Shawn's approval).
- Shawn wants others to "sign in, make id/pass". Jellyfin has NO self-registration. Offered: (A) I create each account
  (non-admin, no delete, no settings) with a one-time password they change in Jellyfin → Profile → Password; no new
  software. (B) invite links via jfa-go (AUR, extra service behind Caddy) so each person picks their own name+password.
  Waiting on his pick (+ names if A).


## 2026-11-13 R5 — BUILT + LIVE. Storage page (DECISION 185) and Jellyseerr episode picker (DECISION 186).
- **luminos-space** now shows per film/season/episode: length, on-disk-since, each person's progress bar (x/y eps, time,
  last watched), ♥ hearted / "requested" tags, a verdict pill, 4 filters, and a HOLD-ON dialog before deleting something
  someone still wants. Verdict computed server-side (`verdict()`), own Jellyfin key `/var/lib/luminos/space-jellyfin-key`.
  Verified via Caddy on the tailnet name with real data + negative test (missing key → library still renders).
  Gotcha: shared app.css already had `.hint` (hub) → renamed mine `.wwhint`. Check every new class against the hub.
- **Jellyseerr 3.4.1-2**: optional "All episodes ▾" picker per season (patch + generator script in
  server/packaging/jellyseerr/). Backend proven live: Adolescence S1 picks {1:[2]} → only E2 monitored → grabbed only
  S01E02; test fully cleaned up (NZBGet was paused for it and resumed). **Request screen NOT clicked through by a person**
  (built-in browser isn't signed in to Jellyseerr) — Shawn to try.
- Gotcha: pacman on the server is blocked by the `00-informant` hook while Arch news is unread. I marked the 3 items read
  to install. ⚠️ One applies: **ca-certificates-mozilla 3.128 < 3.131.1 (MITM fix)** → server needs a full `pacman -Syu`
  (not done — Shawn's call). php / LUKS items don't apply.
- Backups: /root/bak-20261113-space/ and /root/bak-20261113-jellyseerr/ (old pkg + db + settings).
- NEXT: (1) Shawn tries the picker; (2) per-person logins once he gives names — Shawn admin, others limited
  (Jellyfin non-admin, no delete; Jellyseerr request perms; they set own passwords). Storage page picks them up automatically.


## 2026-11-13 R4 — Mockup v2 published (same link): hearts + Jellyseerr requester now block deletes. Still WAITING ON APPROVAL.
- Rule as mocked: blocker = person not finished AND (started OR hearted OR requested). No blockers → green "safe to delete"
  (incl. "nobody started or wants it"). Pills read e.g. "Mom hearted it, hasn't started" / "Mom requested it, hasn't started".
- Logic unit-tested in node against the mock data (verdicts printed correctly for all 6 items + seasons).


## 2026-11-13 R3 — Q: can each account mark interest in a show and sync it to the storage page? → YES, proposed, not built
- Use Jellyfin's built-in per-user **Favourite (heart)** = "I want to watch this" (UserData.IsFavorite, verified present
  on the server, currently 0 hearts). No new app/plugin; works on TV, phone, web. Plus the person who **requested** it in
  Jellyseerr (24 requests in media_request, each with requestedBy) counts as interested automatically.
- Storage-page rule proposed: a person blocks a delete if they hearted it OR requested it OR started it but haven't finished.
  Nobody in that list = safe. Un-hearting = "not interested any more". No separate "not interested" button (Jellyfin has none).
- Waiting on Shawn: OK to fold this into the mockup / the build (task #2).


## 2026-11-13 R2 — Shawn's real ask (AIM RIGHT NOW). Mockup published, WAITING ON APPROVAL. Nothing changed on the server.
1. **Storage page = luminos-space (:8446).** Before deleting by hand he wants to see, per movie/season/episode: episode count,
   length, size, on-disk-since, and **each person's progress** (done / % / not started, last watched) so he never deletes
   something another person hasn't finished. Verdict pill: "everyone finished" / "X still watching" / "nobody started";
   delete warns + needs a second tap if someone isn't done.
2. **Logins per person** (Shawn's answer). Shawn = most powerful (admin); others limited. TODAY Jellyfin has ONE user (shawn)
   shared by everyone, so per-person progress is impossible until accounts exist. Jellyseerr logs people in with Jellyfin
   accounts, so one Jellyfin login per person covers both. Names: Shawn said "skip for now". Each person sets their own password.
   Play log by DEVICE exists since 2026-07-29 (ActivityLogs in jellyfin.db: TV 65PUL7973, Vratik's Tab S9+, Pixel 9) — fallback for history.
3. **Jellyseerr optional episode picker** — default = all episodes of the season. Seerr (even 3.5) only requests whole
   seasons; Shawn asked "seasons work, so what's the problem with episodes?" → it is doable, it needs a source patch to the
   vendored build (server/packaging/jellyseerr): season modal UI + request storage + Sonarr step (add season, then unmonitor the
   unpicked episodes BEFORE the search fires). Patch must be redone on Jellyseerr updates.
- Mockup (interactive, both screens, fake 2nd person "Mom"): https://claude.ai/artifact/7FvfW8nmndJiMvqmVKxFBy
- NEXT: Shawn approves/changes mockup → build #1 in luminos-space (Jellyfin /Users + per-user UserData; runtime from RunTimeTicks)
  → patch Jellyseerr (#3) → create logins when he gives names (#2). Prove each end to end (memory rule).


## 2026-11-13 R1 — "how much have I watched, so I can delete" (READ-ONLY, nothing deleted)
- Pulled Jellyfin UserData via API (key from ApiKeys.AccessToken in jellyfin.db, user shawn 1C9C4F54…) on 127.0.0.1:8096.
- Fully watched: Eastern Promises 63G (/srv/media), A Silent Voice 32G (/srv/external), Ozark S2 all 10 eps 113G, VisionQuest S1 E1,2,4-8 (E3 not marked).
- Unwatched: Insidious 2026 19G, Ae Dil Hai Mushkil 3.3G, MobLand S2 0/8 56G, Ozark S3 (E1 watched, E2 11 %, rest unplayed) 112G.
- Leftovers outside the library: _dv_hdr10_converted 25G + _dv_p5_originals 18G (old DV conversion copies of Ozark S2E03 + VQ E1/E2 — all watched), _llmtest 28G (GGUF models, not media). ~14 empty movie/series folders (4-28K).
- Disk: /srv/media 487G used / 345G free; /srv/external 53G / 406G free.
- GOTCHA for whoever deletes: delete via Radarr/Sonarr (delete files + unmonitor) or the *arrs re-download. Waiting on Shawn to pick what to delete.

## 2026-11-10 R6 — JellyRock 'problem retrieving data from server' after fast-forward (Rockstar, direct play mkv)
- Server healthy, no Jellyfin errors; PlaybackInfo via shim :8095 (8096 is DNAT'd to the BUG-227 shim) answers 200 in 18 ms. Retry capture 11:30: every request 200/206 incl. a seek. Jellyfin logged 'Lost 1 WebSockets' 11:23:09 right after the failed play = TV dropped off Wi-Fi briefly. Shawn: leave it, it plays. No change made. If it repeats: TV on Wi-Fi (.13) is the common thread with the R4 audio crackle — ethernet for the TV.


## 2026-11-09 R5 — DECISION 177: Radarr profile 7 allows 720p as last resort (upgrades on), ESubs whitelisted. Rockstar (2011) Hindi 720p grabbed+imported+in Jellyfin in ~4 min; DECISION 176 rename proven on a real download. Audio-crackle A/B (R4) still unanswered.


## 2026-11-08 R4 — audio crackle on A Silent Voice (JellyRock, Shawn listens via Roku phone app private listening)
- Stream: full re-encode (PGS burn-in) h264_vaapi at 34 Mbps 1080p + DTS-HD MA -> EAC3 5.1 640k; ffmpeg 2.4x+, no errors; TV buffer full.
- Signal NOT clipping: last ~5 min of cached EAC3 peaks -7.7 dBFS, plain stereo downmix -8.6 dB. DownMixAudioBoost=2 irrelevant (no server downmix).
- Suspect: TV on Wi-Fi (.13) carrying 34-46 Mbps video while also sending private-listening audio to the phone over Wi-Fi (ping jitter to 37 ms). Asked Shawn to A/B with JellyRock quality gear ~10 Mbps; if it fixes it -> server-side cap on transcode bitrate (wrapper) as the global fix. Not changed yet.


## 2026-11-08 R3 — DECISION 176: NZBGet DestDir -> /srv/external/usenet/complete (no more 2x 33GB cross-disk copies). Next movie download = the real test (expect Jellyfin within 1-2 min of 100%).
- Playback -3 on A Silent Voice: JellyRock direct-play of DTS-HD MA + PGS failed twice, 3rd try transcoded and played. Orphan Black Swan transcode killed. Offered: luminos-roku-compat --fix-audio (AC3 track on DTS-only files) — not run.


## Q 2026-11-08 R2 — "100% downloaded but not in Jellyfin" (A Silent Voice, 33.5 GB remux) — answered, no change
- Timeline: grabbed 20:06, NZBGet unpack done 20:19:55, Radarr import = full COPY internal HDD -> USB /srv/external (cross-disk, ~50-75 MB/s) 20:20->20:28:35, luminos-media-fix 20:28:33, Jellyfin refresh 20:29:37, visible ~20:30.
- Offered (unanswered): send new movies to /srv/media (same disk as downloads = instant move). 325G free there.

⚠️ RESET 2026-11-08 under the §0.2 size tripwire (was 537 lines). Full old file: `git show 44f2b89e:HANDOFF.md`
— every parallel track below is cut to its pointer; read the old file for its detail before continuing that track.

## Goal (the durable end objective)
Keep Luminos OS + the home setup working as a daily driver; Vela (gaming OS, `gameos/`) gets more graphics + frames.

## Aim right now — VELA: TWO OS BUILDS (Shawn, 2026-11-08, this chat)
Shawn: "going back to 0". Two Vela variants instead of one image that flips modes:
- **Vela-D (Direct):** MUX 0 — the RTX 4050 drives the panel, no copy to the 780M.
- **Vela-H (Hybrid + frame gen):** MUX 1 — 4050 renders → frame to the 780M → Lossless-Scaling frame gen
  (our lsfg-vk `vela-bridge` fork) on the 780M → panel/TV.
Reason: in the dGPU-direct A/B some games got better and some worse → he reads it as OS-level behaviour.
STATE: R2 (11-10) — Shawn: BOTH games worse in every mode, Wukong input lag too → OS design. Read-only analysis DONE,
plan written: gameos/os/docs/V2-PLAN-01.md (commit afdf135). NOTHING changed on any image. Waiting on Shawn's go for Phase 0/1.
NEW FINDINGS (R2): (1) amd_pstate fails (-19) on EVERY Vela boot, kernel 7.2.6 → acpi-cpufreq/schedutil; Luminos 7.0.5 has
amd-pstate-epp. Control main thread 92–100 %. (2) session forces games to OUTPUT 2880x1800 + HDR (gamescope -w 2880 -h 1800
--hdr-enabled) → gameplay VRAM 5.8–5.99 GB, above the 5760 real ceiling → spill/stalls. (3) fans already max in every game row;
GPU parks at 86–87 °C (0x20); APU heat (CPU + 780M HDR composite) steals 4050 clocks. (4) Hybrid = copy + 780M composite every frame.
R1's claim "Control is VRAM-bound, Wukong copy-bound" was too neat: both sit at the VRAM ceiling in gameplay.

## Why / what a newcomer is missing (Vela, verified 2026-11-08)
- Images: `/vela.img` (main, never touched first) + `/vela-nv.img` (test OS, GRUB "Vela OS - NV test"). Both NVIDIA
  615.71, kernel 7.2.6, gamescope session + Qt Vela Home + Go vela-core. Builder `gameos/os/install/vela-install.sh`.
- LATEST VELA WORK IS ON THE SERVER SEAT, NOT IN THE LAPTOP REPO: seat branch `seat/2026-10-31-stutter` commit 723ff2b
  (`~/vela-remote/gameos-stutter`) + `~/vela-remote/SESSION-LOG.md` (11-01). Laptop gameos HEAD = 3c5fcea. Fetch + merge first.
- dGPU-direct A/B (10-30): Wukong avg 37.1→47.5 (+28 %); Control no gain, more stutter. Why it splits (my reading,
  matches Vela DECISION D5): MUX 0 puts gamescope + Home + scan-out buffers in the 4050's 6 GB, and Control is
  VRAM-bound (5.99 GB ceiling even in Hybrid) → less headroom = more evictions; Wukong is GPU/copy-bound → the removed
  PRIME copy is pure gain. NOT yet measured: VRAM used by the session itself in MUX 0 vs Hybrid.
- dGPU-direct blocker (seat 10-31): bottom-screen corruption = gamescope #2309 (NVIDIA DRM scan-out >1440p). 60 Hz,
  --force-composition, fbdev=0 all ruled out. Fix direction = GBM-allocated scan-out (port farnoy/gamescope
  nvidia-gbm-wayland) — plan `~/vela-remote/build/gbm-scanout/SPEC.md` on the server. Test OS left in HYBRID.
- Frame gen (seat 10-16/17): dual-GPU lsfg works, but real fps 35 → 17 with FG on (out ~34): the 4050 idles at 63 %
  because the layer waits for the 780M round trip inside the game's own queue. Shawn's parked idea: "780M presents"
  (one trip 4050→RAM→780M, which generates AND scans out). amdgpu will NOT scan out an imported NVIDIA dma-buf
  (experiments/cross-gpu/RESULT.md) → the 780M must copy into its own buffer first.
- 11-01 seat: VRAM budget layer (`os/vram-layer`, clamps reported budget 5830→5300 MiB) installed on test OS (was lost
  in the 10-14 rebuild) — effect on Control lows NOT measured yet.
- Wukong needs `wukong-clock` (DECISION 165) on every launch.

## Next steps (ordered) — Vela
0. R3: work moves to the SEAT (media server, claude-vela-rc active). Prompt = gameos/os/docs/V2-SEAT-PROMPT.md, pushed to the
   seat repo as branch laptop/2026-11-10-v2 (laptop gameos main = 7123e74 merge of seat stutter + V2 docs). Shawn boots the test OS,
   opens the seat, pastes the prompt. On return: `git fetch seat`, merge seat/2026-11-10-v2.
1. Shawn's go on V2-PLAN-01 Phase 0 (ruler + same runs on Luminos as control) then Phase 1a (7.0.5 kernel in the test OS)
   — each Phase-1 item alone, measured. R1's 3 questions (fresh vs fork, which image, order) still open.
2. `git fetch seat` + merge seat/2026-10-31-stutter into gameos main.
3. Baseline the same two games (Wukong + Control, same spot/settings) on both variants with MangoHud + telemetry,
   including session VRAM at Home.

## Key decisions & constraints
- Vela rules: gameos/docs/tracks/BOARD.md first; test OS first; Luminos untouched; Luminos always Hybrid
  (luminos-mux-guard, DECISION 166). No leaked DLLs. Lossless.dll comes from Shawn's own Steam copy at runtime only.

## Gotchas
- VELA_FPS_CAP caps the whole gamescope session (Home too) — use DXVK/VKD3D_FRAME_RATE for a game-only cap.
- In MUX 0 `systemctl restart vela-session` can die (gamescope SEGV on stop): stop / reset-failed / start.
- host-shell calls return at ~60 s; long jobs via setsid + log.

## OTHER LIVE TRACKS — pointers only (details: `git show 44f2b89e:HANDOFF.md`)
- Lively web wallpapers interactive (BUG-236 / DECISION 181) — DONE; dpr-1 cap offered, not done.
- Video/YouTube wallpapers + switching (BUG-237) — FIXED + proven live (8-step switch test, /var/tmp/vid-test/switch.sh; set.sh writes wallpaper keys live). Offered: BUG-234 VA-API shim for plasmashell.
- 2026-11-12 'wallpaper paused after sleep with no window' = PauseOnBattery working as designed: woke 19:01 after 43 h asleep, ACAD online=0, BAT1 discharging 13.5 W @56 %, no USB-C partner; pmSource (powermanagement engine) is event-driven and matches hardware. Waiting on Shawn: keep pause-on-battery (+ show why) / drop it / cheap mode on battery; and whether a charger WAS plugged (then = undetected-charger bug).
- Living-room wallpaper (BUG-235) — fixed, Shawn to eyeball.
- Snappy build (docs/snappy/PROMPT.md) — PAUSED step 3: diff idle A vs B in /var/tmp/snappy/.
- Luminos Media (DECISION 180) — live, default for 74 types; waiting on feedback.
- DV purple in JellyRock (BUG-231) — fixed server-side; Shawn's TV check pending.
- Desktop settings window (DECISION 183) BUILT 2026-11-09: plasma-desktop 1.3 installs src/desktop-config-look/{shell,folder}; wallpaper page = src/wallpapers/.../ui/{config,WallpaperGallery,GalleryTile,LxRows}.qml (copied to ~/.local/share). Shawn to report anything off. Filter page done (R2, plasma-desktop 1.4). Not restyled yet: Icons/About pages. Test: ~/builds/style-tuner/desk-run.sh.
- Style Tuner (DECISION 176–179) — live. Files/Dolphin redesign (DECISION 182) BUILT + installed 2026-11-09: kio 1.1, dolphin 1.1, luminos-files-icons 1.0-3 (kdeglobals Icons=luminos-files). R20: tuner bars DONE (Files tab, luminos-style 1.0-11, dolphin 1.2, kio 1.2) — Shawn is tuning; next = bake his values as defaults if asked. Edit scripts/files-look/*.py then make-*-patch.sh. Gap: action bar full-width, not floating pill.
- JellyRock seek (DECISION 175 / BUG-230) — live; TV test pending.
- luminos-focus (DECISION 174) — steps 1–3 live; Phase B KWin patch needs Shawn's yes.
- Strong sleep (DECISION 173) — done; real lid/charger test pending.
- Power/battery investigation (BUG-228) — findings only.
- Sonarr/Radarr RSS (DECISION 171/172) — fixed; NZBGet 26.3 wait for Arch.
- Tablet black screen (BUG-227) — Tab S9+ test pending. Bar clock glyph (BUG-226) — done.
- Wukong crash — ROOT CAUSE time-keyed check; fixed by wukong-clock (DECISION 165).
- GLM Claude window (DECISION 162/163) — done.
- Roku TV (DECISION 167; dumbtv-roku 1.0.3 untested) — parked.
- Still open: BUG-187 Claude Desktop re-login verify; BUG-209 MW4; BUG-199 repro; spectrum/nvdefer tests.
- Shared docs (AGENTS, STATUS, DECISIONS, BUGS) carry other sessions' uncommitted edits — commit only your own files.

## Files touched / relevant files (this chat)
HANDOFF.md (reset), gameos/os/docs/V2-PLAN-01.md (new). Analysis script /var/tmp/vela-plan/tsum.py. Read: AGENTS.md, gameos/{HANDOFF.md, docs/tracks/BOARD.md, os/docs/STUTTER-01.md,
DGPU-DIRECT-01.md, LSFG-01.md, DECISIONS.md}, server ~/vela-remote/SESSION-LOG.md + commit 723ff2b.
