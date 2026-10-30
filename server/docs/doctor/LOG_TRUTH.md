# LOG_TRUTH — what really happened on playback, 2026-09-18 → 2026-10-18
<!-- [CHANGE: claude | 2026-10-18] Playback Doctor Phase 2 (Worker B). READ-ONLY run, nothing changed on the server. -->
Parser: `server/scripts/luminos-doctor-logs` (copy at `/var/lib/luminos-doctor/` on luminos-server).
Raw rows: `/var/lib/luminos-doctor/sessions.jsonl` (46 rows, api keys redacted). Re-run: `sudo luminos-doctor-logs`.

## 0. Read this first — the evidence is thin
- **`/var/log/jellyfin/` only holds 3 days** (`LogFileRetentionDays=3`, the "Clean Log Directory" task deletes the rest).
  Every `FFmpeg.Transcode-*.log` from the period is gone → **no ffmpeg speed lines, no TranscodeReasons, no first-segment time.**
- What survives: **journald** (`journalctl -u jellyfin`, back to 2026-07-30) — the main log incl. full ffmpeg command
  lines, "Playback stopped … Stopped at N ms", "FFmpeg exited", WS IPs; plus **ActivityLogs** in `jellyfin.db` (start events).
- So: play method = ffmpeg command present or not; transcode reasons are **inferred** (source streams vs ffmpeg args);
  speed only where ffmpeg ran to the end by itself; "start time" = ffmpeg launch → client's start report (not first frame).
- Roku opens no WebSocket → **its IP is never logged**. Web/Desktop come through Caddy → logged as 127.0.0.1.
- No playback at all since 2026-10-11. Source-stream info comes from today's DB, so files replaced since (Ozark S01, S02E03 after DV fix) show the *new* file.

## 1. Totals
| Client | Sessions | DirectPlay | DirectStream | Transcode | Failed start* |
|---|---|---|---|---|---|
| Jellyfin Roku 3.2.3 / 3.2.4 (TV) | 32 | 30 | 0 | 2 | 5 |
| Jellyfin Desktop 2.0.0 (G14) | 6 | 6 | 0 | 0 | 1 |
| Jellyfin Web 10.11.11 (Chrome, Chrome Android) | 3 | 2 | 0 | 1 | 3 |
| Jellyfin for Android 2.7.3 (Pixel 9) | 4 | 0 | 0 | 4 | 2 |
| no client session (ffmpeg only) | 1 | 0 | 1 | 0 | 0 |
| **All** | **46** | **38** | **1** | **7** | **11** |

\*stopped < 60 s, or no stop reported. No ffmpeg exit code ≠ 0 in the whole period (all 9 runs exit 0).

Network: Roku 32 unknown · via Caddy 9 · **tailnet 4 (all Pixel 9, incl. evenings when Shawn was home)** · LAN-IP 0.

## 2. Failure list (11)
| When (local) | Client | Title | Stopped at | Cause (from logs) |
|---|---|---|---|---|
| 09-18 18:50 | Web/Chrome | Solo Leveling S02E08 | 13 s (3 start reports) | Direct play failed in browser; 20 ASS tracks + fonts extracted (10 s). Same file then played fine in Desktop app → browser-side. |
| 09-18 18:56 | Web/Chrome | same | 3 s | same, gave up → switched to Jellyfin Desktop |
| 09-18 18:58 | Desktop | Solo Leveling "It Was All Worth It" | 0.9 s | auto-next skipped straight on — not a fault |
| 09-23 22:05 | Roku | Ozark S01E04 | 12 s | user skipping episodes (next ep 357 s, then a full one) — not a fault |
| 09-26 13:10 | Roku | Ozark S02E03 | 12 s | 2nd attempt after 86 s of violet direct play (DV P5, BUG-189); transcode restarted |
| 09-26 21:23 | Android, tailnet | India's Got Latent S02E01 | 5.7 s | 4K WEBDL → 1440p 12 Mbps transcode; user moved to Ozark 20 s later |
| 09-26 21:41 | Roku | Ozark S02E03 | 16 s | TV↔phone hand-off loop on one episode (8 sessions in 50 min) |
| 09-27 20:41 | Roku | Ozark S02E06 | 2 s after **10 min** | stuck at 2 s; Shawn was on the web UI at 20:39–20:41 and grabbed Ozark S3 at 20:40 — stall vs. pause not provable |
| 09-27 22:09 | Roku | Ozark S02E07 | **0 s**, no start report | during the S3 import storm (see §5-F); retry 2 min later played to the end |
| 10-11 12:03 | Web/Chrome Android, via Caddy | Dragon Ball Super: Super Hero | 11.7 s | 4K remux → **55.8 Mbps** h264 transcode, TrueHD→AAC (BUG-194) |
| 10-11 12:05 | Android, tailnet (DERP) | same | 38 s | 2 ffmpeg runs: **64 kbps 416×234** then **54.8 Mbps** full-4K, audio → MP3 (BUG-194) |

Real failures: 7. False positives (user skipping / auto-next / pause): 4.

## 3. Transcodes — what ffmpeg was told (7 sessions, 8 runs + 1 orphan)
| Inferred reason | Count |
|---|---|
| video HEVC (4K, HDR) → h264_vaapi | 7 |
| subtitle burn-in of a **text SRT** (Roku) | 2 |
| audio TrueHD → AAC / MP3 | 2 |
| (audio copy in all Ozark/India transcodes; EAC3 passed through) | |

- **Every** transcode: `setparams=…bt709`, `tonemap` never → HDR10/DV relabelled, washed out / violet (BUG-189/194).
- Roku: 1920×1080, **`constrained_baseline` level 4.2**, 10 Mbps, `subtitles=…/2.srt` + `overlay_vaapi` (burn-in).
- Android: 2560×1440 @ 11.96 Mbps (home) / source-res @ 54.8 Mbps (DERP). Web: source-res @ 55.8 Mbps.
- Orphan 09-27 14:10: House of Cards S01E05 remux, video copy + audio → AC3 5.1 640k, seek to 22:43, no client
  start/stop recorded (looks like an API test, not a viewer).
- Speed: only one measurable run — Roku S02E03 burn-in transcode **2.49× realtime** (ran 13:10→13:33 to the end of the file).

## 4. Slowest starts / restarts
| Session | Measure |
|---|---|
| Roku S02E03 09-26 21:04 | **107 s** subtitle extraction inside the session (cache cold after the DV-fix file swap, as BUG-189 predicted) |
| Web Dragon Ball 10-11 | ffmpeg launch → start report 15 s |
| Roku S02E03 09-26 13:10 | 3 s (two runs) |
| Android Dragon Ball 10-11 | 2 ffmpeg runs in 80 s (seek-restart at 00:18) |
| Web Solo Leveling 09-18 | 3 start reports in 4 min, never played |

## 5. Patterns
- **A. Recurring title:** Ozark S02E03 = 11 of 46 sessions (DV P5 violet → transcode → still violet → file fixed → cold subs → TV/phone ping-pong).
- **B. Roku direct-plays almost everything** (30/32): 4K HEVC HDR10 at 24–31 Mbps. Its failures are content (DV P5) or disk, not transcode.
- **C. The phone uses the tailnet even when (almost certainly) at home** (09-26 21:23–21:44, TV and phone alternating on the same episode;
  phone IP 100.77.43.36). Jellyfin counts that as *remote* → since DECISION 142 the 8 Mbps cap and the DERP relay apply at home too.
- **D. Roku transcodes burn in plain SRT**, not only ASS. Once the Roku needs a transcode for any reason, subtitles are
  burned → every seek restarts ffmpeg (BUG-164 mechanism) even on SRT files.
- **E. `EnableThrottling=false` + `EnableSegmentDeletion=false`:** a transcode keeps encoding to the end of the file after
  the viewer stops/seeks (S02E03 run kept going 23 min) — wasted iGPU, cache growth, competes with the next stream.
- **F. Import storm while watching (09-27):** Sonarr grabbed all 10 Ozark S3 episodes at 20:40 and imported one every
  6–25 min until 23:05; after **each** import Intro Skipper re-analysed the *whole* season (1, 2, … 8 files) off the same disk.
  Both Roku failures of that evening (S02E06, S02E07) sit inside that window.
- **G. Android's first try at a remote 4K title was 64 kbps / 416×234** (bitrate probe over DERP), then 54.8 Mbps — two extremes, no middle.
- **H. Dragon Ball file:** default audio = Japanese TrueHD 7.1, default subtitles = **two Chinese PGS tracks**; English SRT is not default.
- **I. Logs:** 3-day file retention destroys the ffmpeg evidence this phase needs. Journald is the only 30-day record.
