# Playback Doctor — plan for a deep, whole-library fix of the media server
<!-- [CHANGE: claude | 2026-10-16] -->
Status: PLAN ONLY (nothing built, nothing changed). Owner: Shawn. Written so any model can pick it up cold.

## 1. The problem in one line
Every playback bug so far was found by Shawn on the couch, one episode at a time, then fixed with a one-off
script (`luminos-dv-fix`, `luminos-fix-e7`, `luminos-roku-compat`, `luminos-audio-audit`, `ozark-warm-once`…).
Nothing checks a file **before** someone presses play. That is the real bug.

## 2. What has actually gone wrong (evidence, not guesses)
| Symptom | Root cause found | Ref |
|---|---|---|
| Purple / violet picture | Dolby Vision **Profile 5** files (no HDR10 fallback layer) | BUG-189, DECISION 95 |
| Washed-out colours when transcoded | HDR source + `EnableTonemapping=false` → only relabelled bt709 | BUG-189, BUG-194 |
| Subs "sometimes", next ep never | Cold embedded-sub extraction reads whole 10–20 GB file off the 5400 rpm disk (170–205 s) | BUG-188, DECISION 132 |
| "No subtitles" on a film | Roku picked the **Forced** English track | STATUS (Evil Dead Burn) |
| Seek / Skip Intro jumps to 00:00 on Roku | Transcode restarts on seek (jellyfin-roku#582), forced by **ASS burn-in** | BUG-164, DECISION 114 |
| Transcodes that shouldn't happen | 26 files **DTS** audio, 20 **ASS** subs, TrueHD on remuxes | BUG-164 |
| Slow start on 4K | Full transcode of 40–55 Mbps remuxes; `HardwareDecodingCodecs` **empty** = software decode | STATUS subtitles row |
| Lag on the TV only | Roku on wifi pulling 27 Mbps direct-play, 486 ms ping | HANDOFF 09-25 |
| Phone stalls away from home | 55 Mbps transcode through Tailscale relay; always DERP, never direct | BUG-194, DECISION 142 (cap fixed, relay open) |
| Bad files keep arriving | Profiles allow 100 GB remuxes and WEB-DL DV P5 | README, BUG-189 |

## 3. Goal ("done means")
Any title plays **first try**, **right colours**, **English subs that show**, **seek works**, on all three real
clients — Roku (Philips 65PUL7973, Jellyfin Roku 3.2.3, home), Pixel 9 (Jellyfin Android 2.7.3, home + away),
web — and a newly downloaded file is checked and fixed **before** anyone watches it.

## 4. Phases
### Phase 0 — Baseline (read-only, 1 session)
- Snapshot all config: `/etc/jellyfin/*.xml`, user policy, Sonarr/Radarr quality + custom formats, Bazarr, Caddy, nft.
- Record client facts: Roku app quality setting, Android app settings, Roku wired/wifi.
- Exit: one `server/docs/doctor/BASELINE.md`.

### Phase 1 — Library census (read-only)
Script `luminos-doctor scan`: `ffprobe` **headers only** (fast, no full reads) on every file →
one JSON/CSV row per file: container, video codec/profile/level, HDR type, **DV profile**, bitrate,
every audio track (codec, channels, lang, default), every sub track (codec, text/image, lang, **forced**, default),
sidecar `.srt` present, sub cache warm (BUG-188 path check).
Then a **client capability matrix** (Roku / Android / web) predicts per file: DirectPlay · Remux · Transcode(reason) · BROKEN(why).
Run niced + ionice idle, never while a stream is active. Exit: counts per category + worst-offender list.

### Phase 2 — Ground truth from logs (read-only, in parallel with Phase 1)
Parser over 30 days of `/var/log/jellyfin/jellyfin*.log` + `FFmpeg.Transcode-*.log`: every session →
client, file, play method, transcode reasons, `-b:v`, time to first segment, **stopped-at < 60 s = failed start**,
restarts per minute (= seek resets), ffmpeg speed.
**Join with Phase 1.** Any file where prediction ≠ reality is a doctor bug (BUG-164 lesson: the old tool printed
"OK — every file should Direct Play" while Jellyfin was transcoding it).

### Phase 3 — Server config audit (read-only → proposals)
Check each against measurement, not docs: HW **decode** codecs (empty today), tonemapping path on this Intel iGPU
(VPP/OpenCL — needs runtime), transcode cache disk, throttling/segment deletion, subtitle extraction settings,
DECISION 142 cap, Tailscale direct path (BUG-194 B/C), Roku link.
Output: ranked list with expected effect, each change behind a 300 s auto-revert.

### Phase 4 — Fix by category, never by episode
Gate (DECISION 112): **one file by hand, watched by Shawn, then batch.** Originals kept until he signs off.
| Category | Fix (no re-download) |
|---|---|
| DV P5 | `luminos-dv-fix` → HDR10 (exists) |
| DTS / TrueHD only | **add** an AC3/AAC track by remux, keep original track |
| ASS / PGS only English | Bazarr text `.en.srt` sidecar → no burn-in |
| Forced-first English | set the full track default (mkvpropedit, header-only edit, seconds) |
| Cold subs | sidecars (permanent) instead of cache warm-up |
| HDR via transcode | enable tonemapping once Phase 3 proves it runs |

### Phase 5 — Prevention
- **On-Import hook** (Sonarr/Radarr Custom Script): doctor scans the new file → auto-applies the Phase 4 fix or flags it.
- Sonarr/Radarr **custom formats**: score DV P5-only and DTS-only negative; cap remux size.
- Nightly doctor report on the hub page (luminos-hub): "N files would fail on Roku".

### Phase 6 — Proof without a couch
A **test shelf** of ~8 real files (DV P5, HDR10, DTS, ASS, PGS, forced-first, 4K remux, plain 1080p).
Automated per client: `PlaybackInfo` with that client's real device profile (method + reason must match the
prediction) → 30 s real transcode → grab a frame and **measure colour** (purple/washed-out detector) →
sub track delivered as text, not burned. Runs after every Jellyfin/app upgrade.

## 5. Who does what (models)
- **PM (Opus/Fable, this chat):** spec, contracts, all server writes, auto-revert, verification by exit codes.
- **Worker A — census scanner + capability matrix:** Opus high. **Worker B — log parser:** Opus high. Run in parallel,
  never see each other's output; joined by the PM.
- **Worker C — test-shelf harness + colour detector:** Fable (hardest: colour pipeline + device profiles).
- **Sonarr/Radarr custom formats, hook wiring:** Sonnet (mechanical).
- **Independent reviewer:** Fable, never saw the code being written.
- Workers get **read-only** SSH on an allow-list (`ffprobe`, `jq`, `grep`, `cat` logs). Only the PM writes to the server.
- Gemini CLI / Antigravity optional for bulk report formatting only.
⚠️ HANDOFF: `device_bash` is NOT the G14 or the server — workers must use the host shell → ssh.

## 6. Hard rules
No re-downloads, no deletes, no media change without the one-file gate. Never run a scan during a stream
(check `/Sessions` first). Host-shell calls < 60 s — long scans run as `systemd-run` units on the server.
Every finding → `docs/BUGS.md`; every change → `server/DECISIONS.md` + `server/STATUS.md`.

## 7. Decisions only Shawn can make
1. OK to **edit media files** in place (add audio track / sub default / DV convert), originals moved to `/srv/external/_originals/` (407 GB free)?
2. OK to change Sonarr/Radarr scoring so bad formats stop arriving (fewer 4K remuxes)?
3. Can the Roku TV get an **ethernet cable**? (Fixes TV lag outright.)
4. Which to start with: Phase 0–2 (find everything first) — recommended — or jump at purple/subs now?
