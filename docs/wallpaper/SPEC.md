# Luminos Live Wallpaper — Lively parity SPEC
<!-- [CHANGE: claude-code | 2026-09-19] -->
Project dir: `src/wallpapers/org.luminos.livewallpaper/`
Docs: `docs/wallpaper/{SPEC,CONTRACTS,BUILD_LOG}.md`

## What the client asked, in their words

> "what things i want is like lively wallpaper app from windows"
> "i do not care every thing is just code at the end if some one else can do it than so can we"
> "if we run the game as video can we still interact with it? like with mouse or keyboard?"
> "list all the things we have and we need to and more"

Standing constraint from earlier in the same thread: **all the features, but not through
Chromium/Chrome.** The `qt6-webengine` package stays installed (HIVE needs it —
`src/hive/HiveWeb.qml`, `scripts/hive-popup-app.py`); only the wallpaper stops using it.

---

## 0. The interaction question, answered

**Yes — and streaming as video is only half of it.**

A PipeWire stream is one-way: pixels out. Interaction needs a **second, opposite channel**, and
Wayland has the primitives for it:

| direction | mechanism |
|---|---|
| pixels **out** of the game | PipeWire stream → `PipeWireSourceItem` (kpipewire) in the wallpaper |
| input **in** to the game | `zwlr_virtual_pointer_v1` + `zwp_virtual_keyboard_v1`, or kernel `uinput` |

The wallpaper already captures mouse events today — that is exactly what `WebInteractive` does. The
new part is forwarding them: QML `MouseArea`/`Keys` → Unix socket → a helper that injects into the
nested compositor (`cage` or `gamescope`, both wlroots-based, both support the virtual-input
protocols).

**This is not speculative: `wayvnc` already does precisely this pair** — streams a wlroots
compositor's output and injects remote pointer/keyboard into it. The architecture is proven; we are
re-pointing it at a local consumer instead of a network one.

**Lively has the same feature and the same shape.** Its wiki marks webpages and applications as
"Interactive", says mouse is "enabled by default … keyboard requires user configuration", and that
application wallpapers "can create their input hooks".

### The three real constraints (design around these, they are not bugs)

1. **Z-order.** The wallpaper is behind desktop icons and every window. Input reaches it only when
   the desktop has focus and the pointer is not over an icon. Lively hits this too; it is why
   interaction is a *mode*, not a default.
2. **Keyboard focus.** Plasma's desktop containment does not normally take keyboard focus. A
   deliberate toggle (hotkey) must grab it, and must be escapable — a wallpaper that eats your
   keyboard with no way out is a broken machine, so **Esc always releases**.
3. **Coordinate mapping.** Wallpaper is 2880×1800 at 2× scale; the nested compositor has its own
   resolution. Pointer coordinates must be mapped and scaled, or clicks land in the wrong place.

---

## 1. WE HAVE (verified by reading the code, 2026-09-19)

| capability | file types | renderer | Chromium? |
|---|---|---|---|
| Still image | `.jpg .jpeg .png .webp .bmp` | Qt `Image` | no |
| Animated GIF | `.gif` (auto-detected, `isGif()`) | Qt `AnimatedImage` | no |
| Video | `.mp4 .webm .mkv .mov .avi` | `MediaPlayer`+`VideoOutput`, **VA-API confirmed** | no |
| YouTube / URL | any YouTube link | **yt-dlp** resolves → normal video path | no |
| Web page | `.html .htm` | `WebEngineView` | **YES — the only one** |
| Native QML | built-in scenes + any `.qml` | QML directly | no |
| Shader scene | baked `.frag.qsb` | `ShaderEffect` (GPU) | no |
| Canvas scenes | aurora, particles | QML `Canvas` | no |
| Stats scene | sysmon | `Text` + DataSource | no |

Supporting behaviour already built:

- `PauseOnBattery` — freeze on battery
- `ObscurePolicy` 0/1/2 — freeze when covered / only under fullscreen / never (**this is Lively's
  "playback rules", already done**)
- `MuteAudio`, `FillMode` (Stretch/Fit/Fill/Center/Tile), `BackgroundColor`
- `InjectSystemStats` → `window.luminos` (Lively's `livelySystemInformation` equivalent)
- `WebInteractive` — mouse into the page (**the input-capture half of interaction already exists**)
- Suspend/resume recovery for the video pipeline
- Used by **both** the desktop containment and the lock screen (`kscreenlockerrc` Greeter)

## 2. LIVELY HAS (from its repo + wiki, 2026-09-19)

| Lively | us | note |
|---|---|---|
| Video / GIF (mpv/vlc) | ✅ | ours is QtMultimedia + VA-API |
| Web page (chromium) | ✅ | the one thing we are removing |
| **Application / Games** (Unity, Godot, emulators) | ❌ | §3.6 |
| **Interactive** web + app wallpapers | ◑ | mouse yes (web); app/keyboard no |
| **`livelyAudioListener(audioArray)` — 128 bands, 0–1** | ❌ | §3.1 |
| `livelySystemInformation(data)` — CPU/GPU/NET/RAM | ✅ | ours is `window.luminos` |
| **`livelyPropertyListener(name,val)` + `LivelyProperties.json`** | ❌ | §3.2 |
| **`LivelyInfo.json` package + `.zip` import + gallery** | ❌ | §3.3 |
| Multi-monitor, per-display | ❌ | single screen; low priority |
| Playback rules by foreground app | ✅ | `ObscurePolicy` |
| Screensaver `.scr` | n/a | Windows-only concept |

## 3. WE NEED

### 3.1 Audio reactivity — ✅ **DONE 2026-09-19, DECISION 117**
Caelestia's C++ plugin ships `cavaprovider`, `audiocollector`, `audioprovider` **and `beattracker`**;
the bar's visualiser already consumes `Audio.cava.values`.
Deliver a `audio` object to every scene (shape in CONTRACTS §2). Lively parity = 128 bands, 0–1.

**Shipped:** `ui/audio/AudioBridge.qml` (contract + fallback, QtQuick only) →
`ui/audio/CaelestiaAudio.qml` (the only file importing `Caelestia.Services`, loaded by URL) →
`ui/scenes/Spectrum.qml` (new built-in scene) and `ui/scenes/Shader.qml` (`iAudio` 128×1 texture +
`iBass`/`iMid`/`iTreble`/`iAudioActive`). Config key `AudioReactive`, off by default, forced on for
the spectrum scene. Verified by `tests/wallpaper/audio_contract.qml` (22 checks, `qml6`, exit code).

### 3.2 Per-scene properties — ✅ **DONE 2026-09-19, DECISION 118** (one half deferred to §3.4)
Declarative control schema → generated settings UI → values delivered to the scene, and mapped onto
shader uniforms **by name** so a shader author gets a slider with zero glue.
Lively's control types, matched: slider, textbox, dropdown, folderDropdown, button, color, checkbox, label.

**Shipped:** `ui/props/PropertyStore.qml` (schema load + merge, used by the wallpaper AND the
settings panel), `ui/props/PropertyEditor.qml` + `PropertyControls.qml` (the generated panel, all
eight types), `ui/scene.js` (one scene map, so the panel cannot edit a different scene's values),
config key `SceneProperties`, and `Spectrum.properties.json` + `Shader.properties.json` to prove it
end to end. Verified by `tests/wallpaper/props_contract.qml` (21 checks) and
`test_shipped_props.py` (7 tests; suite is 27 passed).

**Deferred to §3.4 on purpose:** binding property keys to the uniforms of an *arbitrary* shader. A
QML object cannot gain a property at runtime, so that needs a `ShaderEffect` built from generated
source — which is §3.4's machinery anyway. The built-in shader's `uSpeed`/`uAudioGain`/`uTint` are
bound by name today.

### 3.3 Package format + gallery + **Lively import**
A wallpaper becomes a folder with a manifest and a preview, not a path typed into a textbox.
Reading Lively's own `LivelyInfo.json` makes their entire community library installable for every
type we support.

### 3.4 Runtime shader loader — drop in any Shadertoy `.frag`
Compile with `qsb` on load, cache by content hash. Shadertoy audio shaders work for free once §3.1
lands, because Shadertoy's `iChannel0` audio convention is a 1-D texture.

### 3.5 `.js` canvas loader — run Lively-style JS wallpapers natively
QML's `Canvas` is the same `getContext('2d')` API; QML has its own JS engine. Needs a browser-shaped
shim (CONTRACTS §4).

### 3.6 External producer — games, three.js, DOM pages, **all through one mechanism**
Nested compositor (`cage`/`gamescope`) renders → PipeWire → `PipeWireSourceItem`.
Input flows back via virtual-pointer/virtual-keyboard. §0 covers the design.

## 4. MORE — cheap here, absent from Lively

- **SVG wallpapers**, static and animated — Qt renders natively
- **Qt Quick 3D / glTF** scenes — no browser, no three.js needed
- **Scene hot-reload** — quickshell already proves the pattern; edit a shader, see it live
- **The lock screen inherits everything** — Lively cannot do this at all; ours is already wired
- **Beat detection**, not just FFT — Caelestia ships `beattracker`; Lively exposes only raw bands

---

## 5. ASSUMPTIONS (gaps filled without asking)

1. **Web mode stays until §3.6 lands.** Removing it first would lose DOM pages with no replacement.
   It is lazy-loaded and measured `WebEngine: not mapped`, so it costs nothing while unused.
2. **128 audio bands, floats 0–1**, to match Lively exactly so its wallpapers port unmodified.
3. **Audio capture stops whenever the wallpaper is frozen.** A 24/7 FFT on battery is BUG-083's
   shape again.
4. **Property values live in ONE JSON config key**, not new KConfig keys — a Plasma wallpaper's
   schema is fixed at build time and cannot grow at runtime.
5. **Interaction is opt-in and per-wallpaper**, off by default. **Esc always releases** a keyboard grab.
6. **Lively import covers video/GIF/image/shader now; web/app types once §3.6 lands.**
7. **Packages install to `~/.local/share/luminos/wallpapers/<id>/`** — XDG data dir, not the repo.
8. **`qsb` is assumed present** (`qt6-shadertools`, pulled in by `qt6-declarative`). If missing, the
   shader loader degrades loudly, never silently.
9. **Single monitor.** Multi-monitor is designed-for but not built.
10. **No network fetching of wallpapers.** Local files and manual import only; a gallery that
    downloads code from the internet is a security decision the client has not made.

## 6. BLIND SPOTS → decisions (step 2 of the build protocol)

| risk | decision |
|---|---|
| Scene file deleted/renamed while selected | fall back to the built-in shader scene + log; never a black desktop |
| Malformed/hostile manifest JSON | parse defensively, reject the package, keep the previous wallpaper |
| Property schema declares an unknown control type | skip that control, render the rest |
| Shader fails to compile at runtime | fall back to Canvas aurora and **say so in the journal** (already the pattern) |
| Two scenes with the same package id | last-installed wins, warn at install |
| Audio provider absent | scenes still run, `audio.bands` reads all zeros — never a crash |
| Game producer dies | wallpaper shows last frame, then the fallback scene; no zombie process |
| Lively package with an unsupported type | import it, mark it unsupported in the gallery, do not pretend |
| Huge video/8K in a package | no transcode; document the VRAM budget (4.6 GB, AGENTS §5.3) |
| User picks a `.qml` that throws | Loader error → fallback scene, error to the journal |

## 7. THE FOUR UNKNOWNS — resolved by a probe, not by assumption

The bridge VM cannot read the device's package DB, so these get measured on the box by
`scripts/luminos-wallpaper-capabilities`:

1. Is **kpipewire** installed and does `PipeWireSourceItem` load inside a wallpaper plugin?
2. Does **`Caelestia.Services`** import from plasmashell, or is it Quickshell-bound?
3. Is **`qsb`** present for runtime shader compilation?
4. Is **Qt Quick 3D** installed? Is **cage**/**gamescope**? **wayvnc**?

**Nothing in §3 gets built against an unverified answer.**

## 8. DONE MEANS

- A wallpaper is a folder you install, with a picture of itself in a gallery.
- Picking one shows its own settings — sliders and colour pickers it declared.
- It reacts to music.
- Shadertoy files and Lively-style JS files run by dropping them in.
- A game can run as the wallpaper and you can play it.
- None of it loads Chromium.
- The lock screen gets all of it for free.

## 9. BUDGETS

Adapted from the build protocol for a QML plugin (per-file, not per-project, because a Plasma
wallpaper is inherently many small files):

- QML scene/component: **150 lines**. Loader/host QML: **200 lines**.
- Python helper: **150 lines**; function **40 lines**; nesting depth **3**.
- Dependencies: stdlib + what is already on the box (Qt, ffmpeg, yt-dlp, cava). Anything new is
  logged with a reason in BUILD_LOG.md.
- Over budget is a red build.
