# Dolby Vision Profile 5 "purple picture" — every incident and every fix, compared
<!-- [CHANGE: claude | 2026-10-23] -->
One root cause, four incidents, three different fixes — only the last one is automatic.

**Root cause (all four):** the file is Dolby Vision **Profile 5** (`dv_bl_signal_compatibility_id=0`). Its base picture is in
Dolby's private IPT colour space with no fallback. The Jellyfin Roku app (3.2.x, still on master 2026-10-10) tells the server
"HEVC + Dolby Vision OK in any container" because the TV *panel* supports DV (`GetDisplayProperties().DolbyVision`), so Jellyfin
**direct-plays** the MKV, and the Roku player shows the raw IPT picture → violet/green. Profile 8.1 files are fine (their base
layer is ordinary HDR10). See BUG-207 for the code-level pinpoint.

| # | Date | Title | Files | How it was fixed | Automatic? | Why it came back |
|---|---|---|---|---|---|---|
| 1 | 2026-09-04 | A Knight of the Seven Kingdoms | S01E01 (P5), S01E04 (P5) | DECISION 95: built `luminos-dv-fix` (libplacebo reads the DV RPU → tagged HDR10 via VAAPI). E01 converted by hand; E04 replaced itself when Sonarr grabbed a Profile 8.1 release | ❌ manual (`--scan` by hand) | No scan on import. Series later emptied from the library; the P5 original still sits in `_dv_p5_originals` |
| 2 | 2026-09-26 | Ozark S02E03 | 1 file (lone WEBDL in the season) | BUG-189: same tool run by hand as a transient unit. Noted at the time: *"Why it wasn't caught: --scan is manual. Nothing scans new imports for P5"* — on-import scan left as "Shawn's call", never built | ❌ manual | Same gap, written down and not closed. Output file was 0644 root → the later import hook couldn't edit it |
| 3 | 2026-10-18/20 | (Playback Doctor) | none in library at census time | DECISION 148/152: OpenCL tonemapping for **transcodes** (fixes colours only when the server converts). The plan listed "DV P5 → luminos-dv-fix" as a category fix, but the census found 0 P5 files, so the gate was never wired in. Reported to Shawn as "purple fixed" — overclaim | ⚠️ transcodes only | The Roku **direct-plays** DV, so this path never runs for P5 |
| 4 | 2026-10-23 | VisionQuest | S01E01, S01E02 (both P5) | BUG-207 → DECISION 156: `luminos-dv-sweep` + 30-min timer runs `luminos-dv-fix` on **every** P5 file under Jellyfin's library roots; chmod 664 after swap; Jellyfin notified; `luminos-media-fix` skips the temp file | ✅ every file, every 30 min | — |

## What each fix actually does
- **luminos-dv-fix (95):** decodes the DV layer properly (only libplacebo can), re-encodes as HDR10 on the iGPU (~0.46–0.57× realtime),
  checks length + audio tracks, swaps, keeps the original. Correct, but someone had to run it.
- **OpenCL tonemapping (152):** when the server converts a stream, HDR/DV is mapped to normal colours on the GPU. Correct, but only
  for streams the server converts — the Roku asks for direct play on DV, so it never converts P5.
- **luminos-dv-sweep (156):** makes 95 automatic. Covers every current and future file regardless of title.

## Lessons
1. A gap written down as "owner's call" is still a gap — BUG-189 named this exact hole a month before it bit again.
2. A census of *today's* library proves nothing about *tomorrow's* downloads; prevention must be judged against the stream of imports.
3. "Fixed" must name the path it was proven on (direct play vs transcode). Proof on one path was reported as a fix for both.
4. Re-probe right before converting (DECISION 95 E04 near-miss) — the sweep calls `--dry-run` per file at run time.
