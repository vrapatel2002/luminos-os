# BUILD_LOG — luminos-jf-ffmpeg
## 2026-11-07
- Symptom from Shawn: "no option" to skip in JellyRock. ECP test from the server: >> / Right DO open the
  seek bar and land, but 3 of 4 seeks paused after 2-13 s and jumped back to the pre-seek position.
- Packet capture of the TV's requests: after the jump-back the TV re-requests the pieces it had before
  the seek. No SyncPlay, no server command involved.
- Server side: playlist built from KeyframeData (cumulative grid). After an ffmpeg restart (`-ss` +
  `-start_number`) the cut points drift (pieces 375/387/435/459/495 of Malware 1.6-4 s late) and the
  first piece starts one keyframe early (fftools subtracts 3/23 s before seeking). Reproduced offline.
- Fix chosen: wrapper that swaps the hls muxer for the segment muxer with explicit cut times and nudges
  -ss by +0.15 s. Tested offline with the real binary: segment muxer `segment_times` are relative to the
  first video packet and indexed by run-local count (read from FFmpeg 7.1 segment.c).
- Not chosen: disabling throttling/segment deletion (fewer restarts, but any restart still drifts and the
  cache would hold whole 10 GB episodes on the HDD); patching Jellyfin (rebuilt on every upgrade).
- 16:07 reviewer (Fable high) stalled 10 min with no transcript write after reading the file (API latency check 3 s = API fine) -> stopped by PID, re-run on Opus high.
- RE-PLAN 1 (16:10): live e2e after deploy: first run aligned, restarts NOT rewritten — Jellyfin sends -ss = playlist start + 0.5 s for HLS remux (EncodingHelper.GetFastSeekCommandLineParameter), wrapper refused (>2 ms) and passed through. Contract: accept base or base+0.5.
- RE-PLAN 2 (16:15): reviewer (Opus) findings adopted: unknown -hls_* option or non-vod playlist -> pass through; reset SIGPIPE before exec. Declined: shebang/python-missing (Arch box, /usr/bin/python3 present), URI escaping of DB env (default path is fixed). ffprobe symlink already installed.

## 2026-11-08 — RE-PLAN 3 (BUG-231, DV purple)
- Shawn: purple again on newer episodes. JellyRock 3.3.1 playing VisionQuest S01E06 (DV P5) through the wrapper ("aligned").
- Proof on the server, same 6 s of S01E06: stock hls muxer -> DOVI / dv_profile 5; wrapper-style segment muxer -> HEVC, no DV.
  `-segment_format_options strict=-2` -> DOVI / 5 again. The seek fix (RE-PLAN 0-2) is what broke DV on 2026-11-07.
- Decision: forward Jellyfin's own -strict value into the inner muxer (parity, not a hardcoded -2). Contract changed (rewrite).
- Not chosen: drop the wrapper for DV files (would bring the seek jump-back back on exactly the files that need remux);
  convert P5 to HDR10 again (loses real DV that JellyRock plays fine, DECISION 167).
- Workers: tester Opus high (5 tests, red on old code: 4 failures + 1 error), implementer Sonnet medium (7-line change). 25/25 green,
  file boundaries held, module 135/150 lines. Reviewer Opus high: safe to ship, all findings low. Declined with reason: (1) value
  whitelisting — the original -strict stays in argv, so a bad value already makes ffmpeg refuse; (2) -strict as another option's
  value — Jellyfin prefixes inputs with file:, impossible in practice; (3) input-side -strict — Jellyfin 10.11 sends -strict only
  after -i (seen in the live Remux log), contract stays "last -strict"; (4) pre-existing -segment_* — Jellyfin never sends them.
- Live: deployed 2026-11-08 ~11:10 (old binary ffmpeg.pre-replan3-20261108). e2e dv_check lost_dv 0 (old wrapper 3/3 lost);
  seek_check 19 pieces 0 misaligned on VisionQuest S01E06. Strip pass: nothing to remove (7 lines, all traceable to RE-PLAN 3).
