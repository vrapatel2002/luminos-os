# CONTRACTS — luminos-jf-ffmpeg
# [CHANGE: claude-code | 2026-11-07]

Files
- src/luminos-jf-ffmpeg      (implementer only)  executable, `#!/usr/bin/env python3`, stdlib only
- tests/test_wrapper.py      (tester only)       unittest, stdlib only, run: `python3 -m unittest discover -s tests -v`
  Tests import the script with importlib (SourceFileLoader on src/luminos-jf-ffmpeg, module name "jfw").

Budgets: src file <= 150 lines; any function <= 40 lines; nesting depth <= 3; no third-party imports.

Environment
- LUMINOS_JF_FFMPEG_REAL  default "/usr/lib/jellyfin-ffmpeg/ffmpeg"
- LUMINOS_JF_FFMPEG_DB    default "/var/lib/jellyfin/data/jellyfin.db"

Functions (exact names and signatures)

parse(args: list[str]) -> dict | None
  args = argv WITHOUT argv[0]. Returns None unless ALL hold:
    "-f" followed by "hls"; "-hls_segment_type" followed by "mpegts";
    "-codec:v:0" followed by "copy"; "-hls_time" followed by an int L >= 1;
    "-start_number" followed by an int N >= 0; "-hls_segment_filename" followed by pattern P;
    "-i" followed by a value starting "file:" (media path = value without the "file:" prefix);
    the last two args are "-y" and the playlist path OUT.
  Optional "-ss" value (only if it appears BEFORE "-i"), format HH:MM:SS(.fff) -> seconds float.
  Also returns None if ANY arg starts with "-hls_" and is not one of -hls_time, -hls_segment_type,
  -hls_segment_filename, -hls_playlist_type, -hls_list_size (unknown hls options would make the segment
  muxer fail after exec — RE-PLAN 2), and None if "-hls_playlist_type" is not "vod".
  Returns {"L": int, "N": int, "ss": float|None, "path": str, "pattern": str, "out": str}.

segment_starts(keyframe_ticks: list[int], total_ticks: int, L: int) -> list[int]
  Exact copy of Jellyfin 10.11 DynamicHlsPlaylistGenerator.ComputeSegments, returning segment START
  ticks: [0] + every keyframe k where k >= cut (cut starts at L*10_000_000 and += L*10_000_000 after
  each accepted keyframe). Raises ValueError if keyframe_ticks non-empty and total_ticks < last.
  (1 s = 10_000_000 ticks.)

load_keyframes(db: str, media_path: str) -> tuple[list[int], int] | None
  Read-only sqlite (uri "file:...?mode=ro", timeout 2 s):
    SELECT k.KeyframeTicks, k.TotalDuration FROM KeyframeData k JOIN BaseItems b ON b.Id = k.ItemId
    WHERE b.Path = ?
  KeyframeTicks is a JSON array of ints. No row -> None.

rewrite(args: list[str], plan: dict, starts: list[int]) -> list[str] | None
  N = plan["N"]. None if N >= len(starts).
  ss rule: N == 0 requires plan["ss"] is None; N > 0 requires abs(plan["ss"] - starts[N]/1e7) <= 0.002
  OR abs(plan["ss"] - starts[N]/1e7 - 0.5) <= 0.002 (Jellyfin 10.11 EncodingHelper.GetFastSeekCommandLineParameter
  adds +0.5 s to -ss for every HLS remux restart — RE-PLAN 1, 2026-11-07), else None. base = starts[N]/1e7.
  Output = args with:
    - the "-ss" value replaced by f"{base + 0.15:.3f}" (when present);
    - these pairs REMOVED: -f hls, -hls_time L, -hls_segment_type mpegts, -start_number N,
      -hls_segment_filename P, -hls_playlist_type <x>, -hls_list_size <x>; and the trailing "-y OUT";
    - appended at the end, in this order:
      -f segment -segment_format mpegts
      -segment_format_options strict=V — RE-PLAN 3 (2026-11-08): V = the value of the LAST "-strict" in args
         (verbatim, e.g. "-2" or "experimental"); the pair is omitted when args has no "-strict".
         Why: the hls muxer copies strict_std_compliance into its inner mpegts muxer, the segment muxer does
         not, and mpegts only writes the Dolby Vision descriptor at strict <= unofficial. Without it every
         DV P5 piece goes out tagged plain HEVC and the TV shows purple (BUG-231).
      -segment_times T (comma-joined f"{s/1e7 - base - 0.02:.3f}" for s in starts[N+1:]) — the pair is
         omitted entirely when starts[N+1:] is empty
      -segment_start_number N -segment_list OUT -segment_list_type m3u8 -y P
  Every other arg keeps its value and relative order (e.g. -max_delay 5000000 stays).

main(argv: list[str]) -> None
  Never raises. plan/keyframes/rewrite failure or any exception -> exec real ffmpeg with the ORIGINAL
  args. Success -> print one line to stderr:
    "luminos-jf-ffmpeg: aligned start=N cuts=K" then exec real ffmpeg with the rewritten args.
  exec = os.execv(real, [real] + args). (Tests patch os.execv.)
  Before EVERY execv (pass-through too), reset SIGPIPE to SIG_DFL (Python ignores it and the ignore
  survives exec — RE-PLAN 2). Tests may patch signal.signal.
