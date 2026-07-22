# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-07-22 — Luminos Live Wallpaper COMPLETE, deployed, ready to test.

> This is the ONE handoff file. Never create a second one (no _v2, no dated copies).

## State: COMPLETE, deployed, loads clean. Ready for interactive testing.

A single native KDE wallpaper plugin (`org.luminos.livewallpaper`) that does
image / GIF / video / YouTube / web (HTML-JS-WebGL) — all chosen from the normal
**System Settings → Wallpaper → Type** dropdown. This is the Lively-equivalent.

### Source (in-repo)
- `src/wallpapers/org.luminos.livewallpaper/` — the plugin
  - `metadata.json` — Id org.luminos.livewallpaper, Plasma/Wallpaper
  - `contents/config/main.xml` — keys: WallpaperMode, Image, Video, WebUrl,
    FillMode, BackgroundColor, PauseOnBattery, PauseWhenObscured, MuteAudio,
    WebInteractive, InjectSystemStats
  - `contents/ui/main.qml` — render + guards + injection + cursor forwarding
  - `contents/ui/config.qml` — settings panel (Type, per-mode pickers, samples
    combo, web options, scaling, colour, pause/mute)
- `src/wallpapers/samples/` — luminos-aurora / -particles / -shader / -sysmon .html

### Installed
`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/`
Samples copied to `contents/samples/` there (config.qml resolves `../samples`).

### Features wired
- **Modes**: image (Image), GIF (AnimatedImage), video (MediaPlayer+VideoOutput+
  AudioOutput, mute toggle), web (WebEngineView).
- **Pause guards (power/thermal safety)**: PauseOnBattery via powermanagement
  DataSource (AC Adapter); PauseWhenObscured via TasksModel+Instantiator (maximized/
  fullscreen window covers desktop). Both freeze video/GIF and set WebEngine
  lifecycleState=Frozen. Defaults ON. This protects the box's tuning.
- **Mouse reactivity**: non-interactive = cursor-follow (synthetic mousemove via
  runJavaScript, 40ms, no click theft); WebInteractive toggle = full mouse+clicks
  (captures desktop clicks while on).
- **Live system stats** (opt-in): executable dataengine runs `luminos-monitor stats`
  every 2s → `window.luminos` + `luminos-stats` CustomEvent. sysmon sample demoes it.
- **YouTube** (video mode): yt-dlp resolves the stream URL. CODE IN PLACE BUT INERT —
  yt-dlp not installed (needs `luminos-brain safe` gate + user OK before install).

### Deploy / reload recipe
```
SRC=~/luminos-os/src/wallpapers/org.luminos.livewallpaper
DST=~/.local/share/plasma/wallpapers/org.luminos.livewallpaper
rm -rf "$DST"; mkdir -p "$DST"; cp -r "$SRC/." "$DST/"
mkdir -p "$DST/contents/samples"; cp ~/luminos-os/src/wallpapers/samples/*.html "$DST/contents/samples/"
systemctl --user restart plasma-plasmashell.service
```

### How to TEST (interactive — needs the live desktop)
1. Right-click desktop → Configure Desktop and Wallpaper → Wallpaper → Type =
   "Luminos Live Wallpaper".
2. Web: Type→Web, "Load sample" = Particles → move mouse (reacts). Try Shader.
3. Stats: sample = System monitor + tick "Expose live stats" → live temps/fans.
4. WebInteractive: tick "Let the page receive mouse clicks" for click-through pages.
5. Video: point at an mp4/webm. GIF: point image at a .gif. Unplug AC → freezes.
6. Maximize a window → wallpaper freezes (obscured guard).

### Known / pending
- YouTube inert until yt-dlp installed (gated).
- The downloaded `.mlw` (Lucyna Kushinada) is a proprietary obfuscated Lively-Windows
  container — no plain video stream inside. Get an mp4/webm version to use it.
- Not yet git-committed (awaiting user OK). qmllint clean; plasmashell loads with no
  errors.

### Reusable wallpapers (research)
- **Lively web wallpapers are just folders with index.html** → drop the folder in and
  point Web mode at its index.html. They run as-is.
- GitHub: `voncin/Lively-Wallpapers` (webType), plus topics `lively-wallpaper`,
  `live-wallpaper`, `lively-wallpaper-download`. `rocksdanister/lively-linux` is the
  experimental (non-working) Linux port — not needed, we render web ourselves.
- Any Shadertoy-style single-file shader or HTML5 canvas page works in Web mode.
