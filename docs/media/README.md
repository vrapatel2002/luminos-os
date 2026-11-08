# Luminos Media — one window for every photo and video
<!-- [CHANGE: claude-code | 2026-11-08] DECISION 180 -->

**What:** `luminos-media [FILE|FOLDER]` — a single-file Qt/QML viewer (`src/media/Media.qml`) on the stock `qml6`
runtime, default handler for 74 photo + video MIME types. Zero new packages.
Prototype it was built from: `docs/media/mock/luminos-media.html` (artifact "Luminos Media").

## Files
| Path | Role |
|---|---|
| `src/media/Media.qml` | the whole app |
| `scripts/luminos-media` → `/usr/local/bin/luminos-media` | session env, VA-API shim preload, Trash bridge, arg handling |
| `scripts/vaapi-igpu/luminos-vaapi-igpu.c` → `/usr/local/lib/luminos/libluminos-vaapi-igpu.so` | BUG-234 fix (see below) |
| `config/luminos-media.desktop` → `~/.local/share/applications/` | app entry + MIME list |
| `scripts/luminos-media-install` | install · `--check` · `--uninstall` (restores the defaults saved in `~/.local/share/luminos/media-defaults.prior`) |
| `docs/media/shots/` | proof screenshots |

## Use
← → (or PgUp/PgDn, Space on photos) move through the folder · Space play/pause · Shift+← → ±10 s · wheel = zoom (photo) /
±5 s (video) · drag = pan · + − 0 1 = zoom in / out / fit / 1:1 · R rotate · F or double-click = fill · F11 full screen ·
I details · G folder strip · M mute · L loop · Up/Down = volume (video) · Del = move to Trash · Ctrl+O open · Esc/Ctrl+W close.
Drop a file on the window to open it. Controls fade after 2.5 s without mouse movement.

## Why it is light (measured 2026-11-08, PSS / CPU, double-click launch, dGPU `suspended` throughout)
| | Luminos Media | VLC (was the video default) |
|---|---|---|
| HEIC photo 12 MP | 112 MB · 0.2 % | 653 MB · 42 % (renders a still as a looping video) |
| JXL photo | 144 MB · 0 % | — |
| H.264 1080p | 162 MB · 7.8 % | 125 MB · 1.8 % |
| HEVC 10-bit 4K | 343 MB · 8.8 % | 152 MB · 3.2 % |
Design rules that keep it there: a photo is decoded **at window size**; full resolution is decoded only after you zoom past
fit and is released when you return to fit or move on. The folder strip and its thumbnails exist only while it is open.
No disk cache, no indexer. Closing the window ends the process (checked: no leftover process).
Engine choice (DECISION 180): Qt Multimedia's ffmpeg backend was 909 MB / 88 % on 4K HEVC until BUG-234 was fixed;
with the shim it decodes on the 780M via VA-API. mpv (lighter for video) needs a full `pacman -Syu` first — local sync DB
was stale on 2026-11-08 — so it was not taken.

## Things that bite
- **BUG-234:** ffmpeg's default VA-API device is renderD128 = the gated RTX 4050 → EACCES → no hardware decode. The shim
  fills in the AMD node (vendor 0x1002 from /sys). Missing shim → wrapper warns and falls back to Vulkan decode.
- **Trash:** pure QML cannot touch the filesystem, so `trash()` prints `LUMINOS_MEDIA_TRASH:<path>` and the wrapper's stderr
  bridge runs `gio trash` (regular files only). Needs `QT_FORCE_STDERR_LOGGING=1` — qml6 logs to journald otherwise.
- **AnimatedImage stretches when given `sourceSize`** (4:3 picture came out 2560×1640). So animation goes through it only for
  GIF, APNG and WebP whose VP8X header has the animation flag; a still WebP takes the normal decode-at-window-size path.
- **HEIC EXIF:** search for the TIFF header (`MM\0*\0\0\0\x08` / `II*\0\x08\0\0\0`), never for `"Exif"` — the first
  `"Exif"` in a HEIF file is the item TYPE name in `iinf`, not the data.
- `font.pixelSize` must be an int (13.5 → "Invalid property assignment: int expected", app does not load).
- Never `pkill -f` the Media.qml path from a shell whose own command line contains it (killed the test shell once).

## Self-test
`luminos-media FILE --luminos-debug` → one `LMDBG {json}` state line a second on stderr.
`luminos-media FILE --luminos-selftest[ --luminos-selftest-trash]` → drives zoom→full-res→fit, details, strip, next, next
(video), optional trash, then quits; prints `LMTEST` lines. Results 2026-11-08: all 13 test files open (HEIC, AVIF, JXL,
JPG, PNG, WebP still+animated, GIF, H.264, HEVC10 4K, VP9, AV1); 3× zoom loads 4032 px full image, fit releases it;
HEIC + JPEG EXIF read (camera, date, exposure); trash lands in ~/.local/share/Trash and the viewer moves on.
