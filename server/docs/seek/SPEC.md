# SPEC — luminos-jf-ffmpeg (Jellyfin HLS remux seek alignment)
# [CHANGE: claude-code | 2026-11-07]

## What Shawn wants (his words)
"installed jellyrock on my tv cause its more stable for my rokuTV compare to jellyfin but the thing is
that i can not move back and forth on it."  Fix must cover every file automatically (standing rule).

## What is actually wrong (measured 2026-11-07, see BUILD_LOG.md)
- JellyRock plays Dolby Vision files as an HLS *remux* (video copied, cut into ~5 s .ts pieces).
- Jellyfin writes the playlist from the file's real keyframes (cumulative grid: segment n starts at the
  first keyframe >= n*L seconds, L = SegmentLength, 5 for JellyRock on these 4K files).
- When the viewer seeks past what is already cut, Jellyfin restarts ffmpeg with `-ss S -start_number N`.
  The restarted ffmpeg (a) seeks 3/23 s early (fftools B-frame heuristic) so it starts one keyframe
  BEFORE S, and (b) cuts on its own grid measured from that start, not from 0. Result: from then on,
  some pieces on disk do not hold the time span the playlist promises (measured: 1.6-4 s off).
- The Roku then pauses and jumps back to where it was before the seek (reproduced 4 times via ECP).

## The fix
A small wrapper that Jellyfin runs instead of ffmpeg. For exactly one kind of call — HLS remux with the
video copied into mpegts pieces, for a file Jellyfin has keyframe data for — it rewrites the muxer part
so ffmpeg cuts at exactly the playlist's boundaries. Every other call is passed through unchanged.

## Assumptions (gaps filled)
- A1 Keyframe list = Jellyfin's own `KeyframeData` row for the file (joined on `BaseItems.Path`). That is
     the exact data the playlist was built from. No row -> pass through (Jellyfin used equal-length
     pieces then, which cannot be aligned with a copied video anyway).
- A2 Only `-hls_segment_type mpegts` is handled; fmp4 passes through (JellyRock asks for ts).
- A3 Only video-copy calls are rewritten; real transcodes already get a keyframe per piece from ffmpeg.
- A4 Every matching run is rewritten, including the first (start 0), so all pieces of one session come
     from the same muxer and share one timestamp offset.
- A5 `-ss S` must equal the playlist start of piece N (within 2 ms); then it becomes `-ss S+0.15` so the
     seek lands exactly on keyframe S. Anything else (no -ss with N>0, -ss with N=0, S not a boundary)
     -> pass through unchanged.
- A6 Any error in the wrapper -> pass through unchanged. The wrapper must never be the reason a
     stream fails to start.
- A7 Real ffmpeg = /usr/lib/jellyfin-ffmpeg/ffmpeg; DB = /var/lib/jellyfin/data/jellyfin.db; both
     overridable by env for tests. Python 3 standard library only.
- A8 The wrapper replaces itself with ffmpeg (exec), so Jellyfin's stdin keys (q = stop, c/u = throttle
     pause/resume) still reach ffmpeg and the process id is ffmpeg's.

## Blind spots, decided
- Non-ASCII / spaces / quotes in paths: argv already split by .NET; compare paths as exact strings.
- DB busy/locked (Jellyfin writing): open read-only with a short timeout; on failure pass through.
- Huge keyframe list (3 h film): segment_times grows to ~20 KB of text; fine for argv.
- Restart near the end (N = last piece): no cut times left -> one piece to the end; still correct.
- Keyframe data newer/older than the file (file replaced): Jellyfin's playlist uses the same stale row,
  so we stay consistent with what the client was told. Not our problem to fix.
- Two sessions at once: wrapper is stateless per call.
- Jellyfin upgrade changes the argument shape: parser no longer matches -> pass through (old behaviour),
  and the e2e checker goes red.
- Restart of Jellyfin needed once to pick up the new path; done only when nothing is playing.

## Done means
1. On the server, a client that asks for a playlist, then forces two ffmpeg restarts by jumping ahead,
   gets pieces whose real start times match the playlist (constant offset, within 1 frame) — the e2e
   checker passes. Before the fix the same checker fails.
2. Every other ffmpeg call Jellyfin makes behaves exactly as before (unit tests: byte-identical argv).
3. On the TV, seeking forward and back in JellyRock lands and keeps playing (no jump back), tested by
   remote-control commands over the network.
4. Undo is one line (point Jellyfin back at /usr/lib/jellyfin-ffmpeg/ffmpeg) and documented.
