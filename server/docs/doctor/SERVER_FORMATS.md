# Playback Doctor — Worker C: what this server's hardware can really do with every format
<!-- [CHANGE: claude | 2026-10-18] -->
Status: MEASURED, nothing changed. Experiments ran as user `jellyfin`, wrote only to `/tmp/doctor-hw/`
(tmpfs; clips deleted, PNG frames + logs + `results*.txt`/`colour.txt`/`cmp.txt` left for the PM), only while
`/Sessions?activeWithinSeconds=300` was empty. No `/etc/jellyfin` edit, no restart, no package, no media touched.

## Plain-language summary
- **The purple picture (Dolby Vision Profile 5) can be fixed live by the server, without converting the
  file** — but only at 1080p output. The CPU filter `tonemapx` in jellyfin-ffmpeg 7.1.4 knows how to read the
  Dolby Vision metadata (the "RPU") and undo the IPT colour trick. On this i5-10210U that runs at **29–36 fps**
  for a 4K-in → 1080p-out stream (needs ≥ 24). At 4K-out it manages **10 fps**, so a Roku asking for a 4K
  transcode of a P5 file would stutter. Keep `luminos-dv-fix` (DECISION 95) for the home-4K case; the live
  path covers phone / remote / anything capped at 1080p.
- **HDR that looks washed out** is because the transcode only *relabels* HDR as SDR today. Measured: colour
  saturation drops to **about a third** (0.142 vs 0.30 on the same frame) when nothing tone-maps. Turning
  tonemapping on fixes it at 63–65 fps (1080p, hardware decode + CPU tonemap) — comfortably real-time.
- **Hardware decode is off** (`HardwareDecodingCodecs` empty). This iGPU decodes H.264, HEVC Main/Main10,
  VP9 (8- and 10-bit), MPEG-2, VC-1 in hardware. **Not AV1** (software `dav1d` only). Enabling it roughly
  **triples** the no-tonemap 4K transcode speed (57 → 148 fps) and takes the 4K-source CPU load off the box.
- **The fastest tone-mapper on this chip (`tonemap_vaapi`, 124 fps at 1080p, 50 fps at 4K) is unreachable
  by Jellyfin today.** Jellyfin only uses its "full Intel" filter chain when an OpenCL runtime is present;
  with none installed it falls back to the "copy-back" chain (GPU decode → RAM → CPU filters → GPU encode).
  The Arch `extra/intel-compute-runtime` (26.x) **dropped Gen9 iGPUs**; the right package would be AUR
  `intel-compute-runtime-legacy` (24.35, maintained by an Arch dev). Not required for correctness —
  optional speed upgrade with real risk (see §5).
- **Audio:** DTS and TrueHD → AC3/AAC is an audio-only job with the video copied: **17× real-time** on a
  60 Mbps UHD remux, **158×** for a DTS track alone. Cheap, keep letting Jellyfin do it live.
- **Subtitles:** the Roku app only accepts **vtt / srt / ttml / sub as external files** (jellyfin-roku
  `getSubtitleProfiles()`); anything else risks burn-in = full re-encode + seek reset (BUG-164). The
  170–205 s cold start (BUG-188) is Jellyfin reading the whole file to pull the track out. A `.en.srt`
  **sidecar written at import** removes both problems permanently; the warm-cache timer (DECISION 132) is
  only a stop-gap for files that already exist.

## 1. Test bed
| | |
|---|---|
| Box | Dell Inspiron 3590, i5-10210U (4c/8t Comet Lake), UHD 620 (Gen9.5), 16 GB, kernel 7.2.2-arch1-1 |
| Software | Jellyfin 10.11.11, jellyfin-ffmpeg 7.1.4p1-4, intel-media-driver 26.2.4 (iHD), libva 2.24.1, vulkan-intel 26.2.2 (ANV), **no OpenCL runtime** (`/etc/OpenCL/vendors` absent; `-init_hw_device opencl` → "No such device") |
| vainfo (renderD128) | Decode (VLD): H264 CBP/Main/High, HEVC Main, **HEVC Main10**, VP9 P0, **VP9 P2**, VP8, MPEG2, VC1, JPEG. Encode: H264, HEVC Main/Main10, VP8, MPEG2, JPEG. **No AV1 decode.** VideoProc present (scale/tonemap/procamp) |
| Library census (ffprobe headers, 27 files) | 20× Ozark 2160p HEVC Main10 (S2 = HDR10 smpte2084/bt2020, S3 = 10-bit SDR bt709), all E-AC3 5.1 + subrip; 1× UHD remux DV **7.6** (HDR10 base) TrueHD 7.1 + PGS; 2× **DV P5** originals in `/srv/external/_dv_p5_originals/`; 1× 1080p h264 AAC. **No DTS and no ASS file exists in the library right now** (BUG-164's 26/20 were pruned) — DTS was synthesised from the TrueHD track for the audio test; ASS could not be measured end-to-end. |
| Test files | HDR10: `Ozark S02E09` (4K HEVC Main10, PQ/BT.2020, ~15 Mbps). DV P5: `_dv_p5_originals/Ozark S02E03` (dv_profile=5, bl_compat_id=0, colour tags unknown). Heavy: `Dragon Ball Super Super Hero` UHD remux (DV 7.6, ~60 Mbps, TrueHD). Reference for "correct P5 colour": the `luminos-dv-fix` HDR10 output of the same S02E03 and a libplacebo `apply_dolbyvision=true` render. |
| Method | 30 s clips from 10:00 (20:00 for the remux), 4K in → 1080p out unless marked 4K, `h264_vaapi` 8 Mbps (20 Mbps at 4K), `nice 10` transient unit as `jellyfin`. fps = frames ÷ wall-clock incl. start-up, so slightly pessimistic. Colour = mean of frames at 2/5/8 s (numpy on PNG) plus a 4-timestamp hue comparison against the DoVi-correct render. |

## 2. Measured table
### 2a. Speed — 4K HEVC 10-bit in, h264_vaapi out (need ≥ 24 fps, want > 30)
| # | Pipeline (what Jellyfin would build) | Source | Out | **fps** | Colour OK? |
|---|---|---|---|---|---|
| T1 | **TODAY**: sw decode → `setparams bt709` (no tonemap) → hwupload | HDR10 | 1080p | 57.5 | no — washed out |
| R1 | same, heavy remux | HDR10 (DV7.6) | 1080p | 46.8 | no |
| T2 | hw decode, no tonemap (speed ceiling) | HDR10 | 1080p | **147.7** | no |
| T3 | hw decode → `tonemap_vaapi` (VPP) | HDR10 | 1080p | **124.1** | too dark alone (Y 15 vs 34) |
| T3b | hw decode → `tonemap_vaapi` + `procamp_vaapi=b=16:c=1` (Jellyfin's VPP chain) | HDR10 | 1080p | 124.3 | yes (Y 33, matches tonemapx) |
| R2 | T3b on the heavy remux | HDR10 | 1080p | 120.5 | yes |
| T6 / R4 | T3b at **4K out** | HDR10 | 4K | 50.4 / 51.9 | yes |
| T4 | hw decode → copy-back → `tonemapx` (CPU, bt2390) → hwupload | HDR10 | 1080p | **63.1** | yes |
| R3 | T4 on the heavy remux | HDR10 | 1080p | 64.9 | yes |
| T4b | as T4 but tonemapx at full 4K before scaling | HDR10 | 1080p | 23.9 | yes |
| T5 | **sw decode** → scale → `tonemapx` → hwupload (what the copy-back chain does with decode left in software) | HDR10 | 1080p | 36.9 | yes |
| R5 | T5 on the heavy remux | HDR10 | 1080p | 32.5 | yes |
| T7 | `tonemap_opencl` | HDR10 | 1080p | **did not run** — no OpenCL device | – |
| T8 | libplacebo (Vulkan/ANV) tonemap, 1 process | HDR10 | 1080p | did not run — vaapi↔vulkan hwupload format negotiation fails in one ffmpeg process; needs the 2-process pipe `luminos-dv-fix` uses | – |

### 2b. Dolby Vision Profile 5 — colour and speed
Reference = DoVi-reshaped render (tonemapx `apply_dovi`, which matches libplacebo within ~5/255 per channel and
matches the `luminos-dv-fix` HDR10 file re-tonemapped: 57/73/74 vs 51/69/69 vs 54/73/73 mean RGB). Hue error =
saturation-weighted mean |Δhue| in degrees against that reference over 4 timestamps (300/900/1500/2100 s).
| # | Pipeline | Out | **fps** | mean RGB @5s | hue error vs correct | verdict |
|---|---|---|---|---|---|---|
| P1 | **TODAY**: sw decode → `setparams bt709` | 1080p | 33.5 | 97/91/83 | **41–126°** | wrong (IPT drawn as YUV — grey-brown here, violet on the Roku) |
| P2 / P2b | hw decode → `tonemap_vaapi` (+procamp) | 1080p | 115 | 95/88/80 | **44–125°** | wrong — VPP cannot read the RPU |
| P3e | `tonemapx` with `apply_dovi=0` | 1080p | 20.7 | 132/109/91 | 52–100° | wrong |
| P3 / P3c / P3d | `tonemapx` DoVi reshape at full 4K (sw or hw decode) | 1080p / 4K | 11.8 / 10.6 / **10.0** | 57/73/74 | 0 (reference) | right, too slow |
| **P3f** | **Jellyfin 10.11 copy-back order**: sw decode → scale 1080p → `tonemapx` (DoVi) → hwupload | 1080p | **29.5** | 58/75/76 | 0 | **right, real-time** |
| **P3g** | same with `-hwaccel vaapi` copy-back decode | 1080p | **35.8** | 58/75/76 | 0 | **right, real-time** |
| P3h | P3f at 720p out | 720p | 32.1 | – | 0 | right |
| P4 | libplacebo `apply_dolbyvision=true` → SDR, 2-process pipe (DECISION 95 path) | 1080p | 15.8 | 52/71/70 | ~0 | right, too slow live |
| P5 / P5b | `luminos-dv-fix` HDR10 file → tonemap_vaapi / tonemapx | 1080p | 91.7 / 18.8* | 32/46/43 / 54/73/73 | – | right (*sw decode at 4K before scale) |
| P5c | `luminos-dv-fix` file → `setparams bt709` (today's chain on a converted file) | 1080p | 32.2 | 59/64/66 | – | **washed out: saturation 0.142 vs 0.30** |

The "purple %" detector (R>1.15G & B>1.15G) fired on < 5 % of pixels even on the broken renders: at these
timestamps the IPT misread comes out grey-brown, not violet, so the doctor's colour gate must use **hue error
against a DoVi-correct reference frame** (or simply "DV profile 5 present and chain lacks RPU reshaping"),
not a purple threshold.

### 2c. Audio-only transcodes (video `-c:v copy`)
| Job | Clip | Wall | Speed |
|---|---|---|---|
| TrueHD 7.1 → AC3 640k 5.1, video copied (60 Mbps UHD remux) | 60 s | 3.6 s | **17×** |
| TrueHD 7.1 → AAC 384k 5.1, video copied | 60 s | 3.5 s | 17.5× |
| DTS 5.1 (synthesised) → AC3 640k | 60 s | 0.4 s | 158× |
Decoders present: `dca`, `truehd`; encoders `ac3`, `eac3`, `aac`. Jellyfin issues `-codec:v:0 copy` for an
audio-only reason, so this stays cheap on the CPU and never touches the iGPU.

## 3. How Jellyfin 10.11.11 actually picks a chain on this box (read from `EncodingHelper.cs` at tag v10.11.11)
- `GetVaapiVidFilterChain`: if `!IsOpenclFullSupported()` → **"legacy vaapi pipeline (copy-back)"** =
  `GetSwVidFilterChain` + `hwupload=derive_device=vaapi`. `tonemap_vaapi` / `tonemap_opencl` /
  `EnableVppTonemapping` live only in `GetIntelVaapiFullVidFiltersPrefered`, which needs OpenCL. **So on this
  server today, every VAAPI option except the encoder itself is routed through the CPU chain.**
- In the copy-back chain `IsSwTonemapAvailable()` = bit-depth ≥ 10 ∧ `tonemapx` present ∧ `VideoRange==HDR`
  — it does **not** read `EnableTonemapping`. Order: `setparams(bt2020/PQ)` → sw scale → `tonemapx(…format=
  yuv420p for DOVI)` → hwupload. That is exactly P3f/P3g above.
- **Contradiction to settle in the Phase 4 one-file test:** BUG-189/BUG-194 recorded `setparams=…bt709` with
  no tonemap on the same build, which the source says should not happen for a stream Jellyfin classes as HDR.
  Either Jellyfin's probe stored `BitDepth`/`VideoRange` differently for those files or the log was from an older
  path. The server's `jellyfin*.log` files are now 6 KB/day and contain no ffmpeg command lines, so it cannot be
  checked from history — capture the real command line (`EnableFFmpegLogging`/transcode log) when the test runs.
- DV P5 in the full chain (if OpenCL were present): `IsIntelVppTonemapAvailable` excludes `DOVI` → falls to
  `tonemap_opencl`, whose jellyfin-ffmpeg version does RPU reshaping on the GPU (untested here, speed unknown).
- `HardwareDecodingCodecs` empty → `GetHardwareVideoDecoder` returns nothing → software decode in every chain.

## 4. Recommended `/etc/jellyfin/encoding.xml` (no package)
Change only these (diff against today's file; everything else stays):
```xml
<HardwareAccelerationType>vaapi</HardwareAccelerationType>          <!-- unchanged -->
<VaapiDevice>/dev/dri/renderD128</VaapiDevice>                       <!-- unchanged; verified = pci 00:02.0 Intel -->
<EnableHardwareEncoding>true</EnableHardwareEncoding>                <!-- unchanged -->
<HardwareDecodingCodecs>                                             <!-- was EMPTY -->
  <string>h264</string>
  <string>hevc</string>
  <string>vp9</string>
  <string>mpeg2video</string>
  <string>vc1</string>
</HardwareDecodingCodecs>                                            <!-- NOT av1: vainfo has no AV1 VLD -->
<EnableDecodingColorDepth10Hevc>true</EnableDecodingColorDepth10Hevc> <!-- unchanged, needed for Main10 -->
<EnableDecodingColorDepth10Vp9>true</EnableDecodingColorDepth10Vp9>   <!-- unchanged -->
<EnableTonemapping>true</EnableTonemapping>                          <!-- was false; harmless now, required the day OpenCL appears -->
<TonemappingAlgorithm>bt2390</TonemappingAlgorithm>                  <!-- unchanged; this is what was measured -->
<TonemappingPeak>100</TonemappingPeak> <TonemappingDesat>0</TonemappingDesat>
<EnableVppTonemapping>false</EnableVppTonemapping>                   <!-- leave false: unreachable without OpenCL -->
<AllowHevcEncoding>false</AllowHevcEncoding>                         <!-- leave; hevc_vaapi exists, Roku profile asks h264 -->
```
Expected after the change (from the table): HDR10 4K → 1080p **~63–65 fps** (was 47–57, and wrong colours);
HDR10 → 4K out: tonemapx at full res **~24 fps** — marginal, so DECISION 142's cap / Roku quality setting should
keep 4K-source transcodes at 1080p out; DV P5 → 1080p **~30–36 fps, correct colour, no file conversion**;
DV P5 → 4K out **~10 fps = will stutter** (keep `luminos-dv-fix` for P5 files the Roku must play at 4K, or
let the doctor convert on import — DECISION 95 unchanged). Non-HDR 4K/1080p transcodes: decode moves to the
iGPU, CPU freed for subtitle extraction and other streams.
Risks: (1) hw decode of broken/odd HEVC streams can fail where sw decode survived — Jellyfin falls back to
software automatically on decoder error at start, not mid-stream; (2) copy-back adds ~1 GB/s of PCIe/RAM traffic
per 4K stream — measured fine for one stream, untested for two concurrent; (3) the BUG-189 contradiction above —
if the sw tonemap really is not firing, `EnableTonemapping=true` alone will not change that and the one-file test
will show it immediately.
**Change procedure:** `cp /etc/jellyfin/encoding.xml /etc/jellyfin/encoding.xml.pre-doctor-$(date +%F)` →
edit → `systemctl restart jellyfin` → play the P5 original on the Pixel (1080p cap) and S02E09 on the Roku →
`luminos` colour check on a transcode segment from `/var/cache/jellyfin/transcodes/` → 300 s auto-revert timer
armed before the restart (Phase 3 rule).
**Rollback:** `cp /etc/jellyfin/encoding.xml.pre-doctor-* /etc/jellyfin/encoding.xml && systemctl restart jellyfin`.
Nothing else on disk changes.

## 5. Optional package for the fast path (not recommended yet)
| | |
|---|---|
| What it unlocks | Jellyfin's full Intel chain: `tonemap_vaapi` (**124 fps 1080p / 50 fps 4K** for HDR10, measured) and `tonemap_opencl` with GPU DoVi reshaping for P5 (not measurable without it). Set `EnableVppTonemapping=true`, `VppTonemappingBrightness=16`, `VppTonemappingContrast=1` once installed — measured: VPP alone is 2× too dark (Y 15), `procamp b=16` brings it to Y 33 ≈ tonemapx's 34. |
| Package | `extra/intel-compute-runtime` 26.31 **does not support Gen9.5** (Arch dropped Gen8–Gen11 at 24.39, packaging issue #3). Use AUR **`intel-compute-runtime-legacy`** 24.35.30872.45 (maintainer dbermond, an Arch developer; depends on `intel-gmmlib-legacy` + `intel-graphics-compiler-legacy`). Or `intel-compute-runtime-legacy-bin` 24.35.30872.36 (prebuilt). |
| Risk — why not now | `-legacy-bin` **conflicts with `intel-gmmlib`**, which `intel-media-driver` (the VAAPI driver that everything already depends on) is built against — a wrong gmmlib can break decode/encode outright. The source variant pulls `intel-gmmlib-legacy`, whose coexistence with `intel-gmmlib` 22.8 I could not verify from here; `intel-graphics-compiler-legacy` is a multi-hour LLVM build on this i5. Jellyfin also requires the `cl_intel_va_api_media_sharing` extension for its OpenCL check (`IsOpenclFullSupported`), which the legacy runtime has but was not tested. Do this only after §4 is proven, in its own 300 s-revert window, with `pacman -U` of a pre-built package and a snapshot of `/usr/lib/libigdgmm*`. |

## 6. Subtitles (BUG-164, BUG-188) — what to set
- Roku app 3.2.3 subtitle profile = **vtt, srt, ttml, sub — Method External only**. No `ass`, no `pgs`, no
  Encode entry. Any ASS/PGS track Jellyfin decides it cannot deliver externally becomes burn-in = full re-encode
  and the seek-reset of BUG-164. Keep `EnableSubtitleExtraction=true` (it is what makes External delivery of
  embedded tracks possible at all).
- **Cold start (170–205 s):** Jellyfin extracts an embedded track by reading the whole file on first request.
  A sidecar `<name>.en.srt` next to the file is served directly (and converted to vtt from the small file) —
  no extraction, no cache, no warm sweep needed. This is the permanent fix; DECISION 132's warm timer only
  covers files that already exist.
- Doctor's per-file subtitle fix, all automatic on import (Phase 4/5): (1) for every English **text** track
  (subrip/ass/ssa) write `.en.srt` (`ffmpeg -map 0:s:N -c:s srt`, ASS styling is dropped on purpose — Roku
  cannot show it anyway); (2) forced-only tracks → `.en.forced.srt`; (3) image-only (PGS/VOBSUB) English →
  Bazarr text download (`luminos-roku-compat` already flags `subs:image-only(burn-in)`); (4) clear the
  `default` flag on an embedded ASS track with `mkvpropedit` (header-only, seconds) so the sidecar is picked
  first — Jellyfin orders external tracks after embedded ones and a default-flagged embedded ASS wins the
  selection. Verify with the Phase 6 harness: `PlaybackInfo` with the Roku profile must answer
  `DeliveryMethod: External` for the chosen subtitle and no `SubtitleCodecNotSupported` transcode reason.
- Server-side there is no "prefer external over embedded" switch in 10.11; the default-flag edit is what
  makes the choice deterministic.

## 7. Artefacts
`/tmp/doctor-hw/` on the server (tmpfs — gone at reboot): `results.txt … results5.txt`, `colour.txt`,
`cmp.txt`, `census.txt`, `*_t{2,5,8}.png` (one per pipeline), `frames/t{300,900,1500,2100}_{A..D}_*.png`
(baseline / tonemapx-DoVi / tonemapx-noDoVi / tonemap_vaapi side by side), scripts `bench*.sh`, `colour.py`,
`cmp.py`, `frames.sh`. Copy them to `server/docs/doctor/evidence/` before the next reboot if wanted.
