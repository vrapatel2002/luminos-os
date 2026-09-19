# Luminos Live Wallpaper — frozen contracts
<!-- [CHANGE: claude-code | 2026-09-19] -->
These do not change without an explicit re-plan. Everything else is implementation detail.

## 1. Scene interface

Every scene is a `.qml` file loaded **by URL** (never as a QML type — a type reference resolves at
compile time and drags its imports in for every mode; that was DECISION 112's bug and DECISION 113
restates it). A scene MAY declare any of these; the host binds only what exists:

| property | type | meaning |
|---|---|---|
| `running` | bool | false = freeze. Battery/obscured/paused all route here. |
| `stats` | var | system stats object, §3 |
| `audio` | var | audio object, §2 |
| `props` | var | this scene's own property values, §4 |
| `cursorX`, `cursorY` | real | pointer in scene pixels, `-1` when absent |

A scene declaring none of them still loads. A scene that throws → host falls back to the built-in
shader scene and logs `[LUMINOS-WP]`.

## 2. Audio contract  (Lively parity: `livelyAudioListener`)

```js
audio = {
  bands:   [128 floats],   // 0..1, low->high frequency. ALL ZEROS if no provider.
  bass:    float,          // 0..1, mean of bands[0..15]
  mid:     float,          // 0..1, mean of bands[16..63]
  treble:  float,          // 0..1, mean of bands[64..127]
  beat:    bool,           // true for exactly one frame on a beat
  bpm:     float,          // 0 when unknown
  active:  bool            // false = no provider; scenes must still render
}
```

- **128 bands, 0–1** is chosen to match Lively exactly so its wallpapers port unmodified.
- For shaders: uploaded as a 128×1 `R32F` texture named `iAudio`, matching Shadertoy's `iChannel0`
  audio convention so Shadertoy audio shaders work unmodified.
- **The provider stops when `running` is false.** Non-negotiable — see SPEC §5.3.

## 3. Stats contract  (already live; Lively parity: `livelySystemInformation`)

Source `luminos-monitor stats`, `KEY=value` lines, parsed once and published to every consumer.
Keys in use: `CPU_LOAD CPU_TEMP AMD_TEMP FAN_CPU PROFILE NV_STATE NV_PWR`.
Missing key → `undefined`; scenes must tolerate it.

## 4. Property schema  (Lively parity: `LivelyProperties.json`)

File `properties.json` beside the scene. Control types match Lively's one-for-one:

> **Clarification, 2026-09-19 (DECISION 118) — behaviour for packages is unchanged.** "Beside the
> scene" is unambiguous for a package, which is one scene per folder. The built-in scenes share
> `ui/scenes/`, so the loader tries `<Scene>.properties.json` first and `properties.json` second.

```json
{ "speed": { "type":"slider",   "label":"Speed", "value":1.0, "min":0.1, "max":5.0, "step":0.1 },
  "tint":  { "type":"color",    "label":"Tint",  "value":"#7c3aed" },
  "mode":  { "type":"dropdown", "label":"Mode",  "value":0, "items":["Calm","Wild"] },
  "name":  { "type":"textbox",  "label":"Name",  "value":"" },
  "on":    { "type":"checkbox", "label":"Glow",  "value":true },
  "file":  { "type":"file",     "label":"Image", "value":"" },
  "go":    { "type":"button",   "label":"Reset", "value":"reset" },
  "note":  { "type":"label",    "value":"read-only text" } }
```

**Storage.** ONE Plasma config key, `SceneProperties`, holding
`{"<sceneId>": {"speed":1.0, ...}}`. A wallpaper's KConfig schema is fixed at build time and cannot
grow at runtime — this is the only way to carry per-scene values.

**Delivery.** The host hands the scene `props` = the object for the current scene, defaults merged
under saved values. Unknown control type → skipped, rest still rendered.

**Shaders:** every key in `props` whose name matches a uniform in the `.frag` is bound to it
automatically. That is the whole point — declare a property, get a slider, no glue code.

## 5. Package manifest

`~/.local/share/luminos/wallpapers/<id>/luminos-wallpaper.json`

```json
{ "id":"aurora-01", "title":"Aurora", "author":"...", "version":1,
  "type":"scene|video|image|gif|shader|js|producer",
  "entry":"scene.qml", "preview":"preview.png",
  "properties":"properties.json",
  "interactive":false,
  "source":"native|lively" }
```

### Lively import mapping (read-only; we never write `LivelyInfo.json`)

| LivelyInfo.json | ours | note |
|---|---|---|
| `Title` | `title` | |
| `Author` | `author` | |
| `Type` (0 video,1 gif,2 web,3 app,…) | `type` | unmapped → import, mark unsupported, do not pretend |
| `FileName` | `entry` | |
| `Thumbnail` / `Preview` | `preview` | |
| `Arguments` | producer args | app types only |

`LivelyProperties.json` maps onto §4 by control name; Lively's `folderDropdown` → our `file`.

## 6. JS canvas shim  (for `.js` wallpapers)

The scene runs the user's JS against a browser-shaped surface. Provided, and nothing else:

```
canvas, ctx (= canvas.getContext('2d'))
requestAnimationFrame(fn), cancelAnimationFrame(id)
window.innerWidth, window.innerHeight, window.devicePixelRatio
addEventListener('mousemove'|'resize', fn)   // document + window both
window.luminos                                // stats, §3
livelyAudioListener(fn) / window.audio        // §2
console.log/warn/error -> journal, prefixed [LUMINOS-WP]
```

**Not provided:** DOM, CSS, `fetch`, `XMLHttpRequest`, timers beyond rAF, WebGL.
A script touching those fails at load with a named error — never a blank wallpaper.

## 7. External producer IPC  (games / three.js / DOM)

```
video:  producer -> PipeWire node -> PipeWireSourceItem (kpipewire)
input:  wallpaper -> unix socket ~/.local/state/luminos/wallpaper-input.sock -> injector
        -> zwlr_virtual_pointer_v1 / zwp_virtual_keyboard_v1  (or uinput)
```

Input messages, one JSON object per line:

```json
{"t":"motion","x":0.5123,"y":0.8871}      // NORMALISED 0..1, never pixels
{"t":"button","b":"left","s":"press"}
{"t":"key","code":30,"s":"press"}          // linux evdev keycode
{"t":"scroll","dx":0,"dy":-1}
```

**Normalised coordinates are the contract** because the wallpaper (2880×1800 @2×) and the producer's
output resolution differ; whoever injects does the scaling. Pixels would silently mis-aim.

**Lifecycle:** producer starts when its wallpaper is selected, dies when it is deselected or the
wallpaper freezes. No orphan on crash — the host reaps by pid and clears the socket.

**Safety:** interaction defaults OFF; keyboard grab requires an explicit toggle; **Esc always
releases**. A wallpaper that eats the keyboard with no way out is a broken machine.
