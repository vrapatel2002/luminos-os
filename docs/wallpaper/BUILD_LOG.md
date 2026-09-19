# BUILD_LOG — Luminos Live Wallpaper, Lively parity
<!-- [CHANGE: claude-code | 2026-09-19] -->
Plain English, decisions and **why**. Append after each task, never at the end.

## 2026-09-19 — session 1: spec, contracts, and the first verified slice

### Research
Read Lively's repo and wiki rather than working from memory. What it actually pins down:
- Wallpaper types: **Video/GIF**, **Webpage**, **Application/Games** (Unity, Godot). Web is
  "minimal webpage renderer powered by chromium"; video is "mpv/vlc".
- **Both webpages AND applications are marked "Interactive."** Mouse "enabled by default";
  keyboard "requires user configuration"; application wallpapers "can create their input hooks."
  This is what settles the client's question — see SPEC §0.
- `livelyAudioListener(audioArray)` — **128 elements, values typically 0–1**.
- `livelySystemInformation(data)` — JSON: NameCpu, CurrentCpu, NameGpu, CurrentGpu3D, NameNetCard,
  CurrentNetDown, CurrentNetUp, TotalRam, CurrentRamAvail.
- `livelyPropertyListener(name, val)` + `LivelyProperties.json` — slider/textbox/dropdown/
  folderDropdown/button/color/checkbox/label.
- `.zip` packages, drag-and-drop import, generated thumbnail + preview gif.

Those numbers are why CONTRACTS §2 says 128 bands at 0–1: **matching Lively exactly is what lets
their wallpapers run here unmodified.** Picking 64 or 0–255 would have been a silent incompatibility.

### Decisions, and why

**1. The package layer is Python, not QML.** The build protocol says anything unverified is
unfinished. QML manifest parsing cannot be tested with an exit code from here; Python can. So
`scripts/luminos-wallpaper-pkg` owns manifests, the Lively import and property merging, and QML just
consumes its JSON. That split exists **to make the risky part testable**, not for elegance.

**2. Built and tested in the cloud container, deployed by checksum.** The bridge VM has no Qt and no
`claude` CLI; the cloud container has Qt 6.4 tooling (`qmllint`, `qsb`) and can spawn workers. So the
work happens there and crosses via `device_commit_files` — md5 verified on both ends, after the
2026-09-16 lesson where base64 through a shell silently corrupted a `.qsb`.

**3. Web mode stays for now.** Removing it before the external-producer path (SPEC §3.6) exists would
delete DOM support with nothing behind it. It is lazy-loaded and measured `WebEngine: not mapped`, so
it costs nothing while unused. Removal is a step in the plan, not a prerequisite.

**4. The capability probe gates everything.** The bridge cannot read the box's package database, so
four unknowns (kpipewire, `Caelestia.Services` importability, `qsb`, Quick 3D) were about to become
assumptions. `scripts/luminos-wallpaper-capabilities` turns them into exit codes.
**Nothing in SPEC §3 gets built against an unverified answer.**

### The nesting-budget failure, and why the metric changed rather than the code
First budget run said depth 4 against a budget of 3. Investigated instead of trusting it: Python's
AST represents `elif` as an `If` nested in the parent's `orelse`, so an `if/elif/else` chain measures
as depth 3 while reading as depth 1. The code was fine; **the instrument was wrong**. `budget_check.py`
now collapses elif chains. Real nesting still counts. Correcting an instrument is not relaxing a
budget — but it only counts as that because the cause was found first.

### The security round
Tests passed and budgets passed, and the review pass still found a hole: `_path_safe()` rejected
absolute paths and `..`, but **`~/.ssh/id_rsa` is neither** — one `os.path.expanduser()` downstream
and a third-party manifest reads your keys. Also unhandled: a NUL byte (truncates the path inside any
C-level `open()`) and UNC paths.
Sequence followed deliberately: **write the failing test first** (4 red), then send it back to the
implementer, then re-verify. The implementer never saw the test file.

### Gate results
```
tests     20 passed        (12 property/example tests, hypothesis + pytest)
budgets   149 lines, max fn 33, nesting 3      PASS
boundary  implementer never touched tests/     clean
transfer  md5 identical cloud -> device        verified
device    imports, path gate + lively map + props behave      verified live
```

### Known gap, deliberately not closed
`pytest`/`hypothesis` are not installed on the G14, so the suite runs in the build container, not on
the box. Installing them is a Python package action and **AGENTS.md rules 5–6 require
`luminos-brain safe` first** — that is Shawn's gate, not mine to walk through unasked.

### Next
1. **Run `scripts/luminos-wallpaper-capabilities` on the box.** It is the gate; SPEC §3 is blocked on it.
2. Then SPEC §3.1 (audio) — highest payoff, and the provider already exists on the box.
3. Then §3.2 properties, §3.4 shader loader, §3.5 JS loader, §3.3 packages, §3.6 producer.

## 2026-09-19 — session 1b: the gate ran, and it caught the checker

Shawn ran `scripts/luminos-wallpaper-capabilities` on the box. **REQUIRED capabilities present**, and
the four SPEC §7 unknowns are now facts rather than assumptions:

| unknown | answer |
|---|---|
| `qsb` | **present, Qt 6.11.2** — runtime shader compilation is on |
| `Caelestia.Services` outside quickshell | **present at `/usr/lib/qt6/qml/Caelestia/Services`, and its qmldir names NO Quickshell dependency** |
| kpipewire | **present** — `PipeWireSourceItem` available, so the producer video path is real |
| Qt Quick 3D | **present** — glTF scenes buildable |

Bonus: `cage` present (nested compositor for SPEC §3.6), `/dev/uinput` present, SVG plugin present,
`chromium not mapped` still holding, current mode `video`.

**The `Caelestia.Services` answer is the important one.** That was the single largest risk in the
plan — if the audio provider had been Quickshell-bound, SPEC §3.1 would have needed a whole helper
daemon. It is a plain QML module with no Quickshell dependency, so the wallpaper can import cava +
beattracker directly.

### The probe reported one WARN that was MY BUG, not a missing capability

It said `cava absent — install cava`. Wrong question. Read the source rather than trusting my own
output:

```
cavaprovider.cpp:34      cava_execute(m_in, count, m_out, m_plan);   <- libcava C API
audiocollector.hpp:5     #include <pipewire/pipewire.h>              <- PipeWire directly
```

Caelestia **never spawns the cava CLI**. It links libcava and reads PipeWire itself. The binary on
PATH is irrelevant, and that WARN would have sent the next session off to install a package it does
not need — or worse, to build the "PipeWire FFT helper" the message suggested, which already exists.

Fixed: the check now inspects what the module actually links (`ldd`) instead of what is on PATH.

### A second correction in the same pass
`uinput` reported OK on existence alone. But it is `root:input 660` — whether *we* can open it is a
question about **group membership**, which the probe never asked. Reporting OK there is how you find
out at the moment input silently does nothing. It now checks writability and `input` group
membership, and warns with the actual reason.

**Lesson, and it is the same one BUG-163 taught: a checker that asks the wrong question is worse
than no checker, because its green is believed.** Both fixes are in
`scripts/luminos-wallpaper-capabilities`; re-run it to see the corrected lines.

### Now unblocked
Everything in SPEC §3 is buildable. Order unchanged: §3.1 audio (now known cheap), §3.2 properties,
§3.4 shader loader, §3.5 JS loader, §3.3 packages, §3.6 producer.

## 2026-09-19 — session 2: SPEC §3.1 audio, shipped and deployed

The gate said everything in SPEC §3 was buildable, so the order held: audio first.

### What landed
```
contents/ui/audio/AudioBridge.qml     new   the contract, the maths, the fallback   (QtQuick only)
contents/ui/audio/CaelestiaAudio.qml  new   the only importer of Caelestia.Services (URL-loaded)
contents/ui/scenes/Spectrum.qml       new   64 bars from 128 bands, bass wash, beat flash
contents/ui/scenes/Shader.qml         mod   iAudio 128×1 texture + iBass/iMid/iTreble/iAudioActive
contents/shaders/luminos-shader.frag  mod   4 floats appended at std140 88/92/96/100 + sampler @1
contents/ui/QmlMode.qml               mod   owns the bridge, binds `audio`, + BUG-168
contents/ui/main.qml                  mod   wantAudio, passed down
contents/config/main.xml              mod   AudioReactive (default false)
contents/ui/config.qml                mod   Spectrum in the scene list, audio checkbox
tests/wallpaper/audio_contract.qml    new   22 checks, runs on the box with qml6
```
Repo and the installed copy under `~/.local/share/plasma/wallpapers/` are byte-identical
(`diff -rq` clean), `.qsb` md5 matched at both ends.

### The decision that made it small
Writing an FFT daemon was the plan. Reading Caelestia's plugin source instead of assuming turned it
into three QML files — `service.hpp` refcounts providers, so the freeze contract is a `Loader`'s
`active`, and `cavaprovider.cpp` links libcava rather than spawning it, so nothing external runs.
Full reasoning in DECISION 117; it is not repeated here.

### BUG-168 — found by trying to use the contract we wrote
`QmlMode.qml` decided whether to bind a scene property with `item.stats !== undefined`. A
`property var audio` with no initialiser **is** undefined, so a scene implementing CONTRACTS §1
correctly would have been handed nothing, silently, for ever. It never fired because every shipped
scene happens to initialise. Fixed to ask whether the property exists (`name in item`).

Third time this shape has bitten this project in four days: BUG-163 was a checker pointed at the path
the fix had just left, the `cava` WARN was a check on `PATH` when the answer was in `ldd`, and this
was a check on a value when the question was about a declaration. **The near-miss question passes for
the wrong reason and stays green until someone outside the original assumptions shows up.**

### A trap recorded before it costs anyone an hour
**`.qsb` files are not byte-reproducible.** Rebuilding the shader after changing only a comment
produced a file differing in 3439 of 3493 bytes. That is not a real change: `qsb --dump` calls its own
payload an "unordered list", and the six variants (SPIR-V, GLSL 100es/120/150, HLSL, MSL) come out in
a different order each run, inside a compressed container. Diffing the **dumps** showed identical
GLSL, identical reflection, identical offsets.

So: **never compare `.qsb` files by md5 to decide whether the shader changed.** Compare
`qsb --dump` output. An md5 check across the device bridge is still right — that is asking "did the
bytes arrive intact", which is a different question, and it is the check that caught the corrupted
transfer on 2026-09-16.

### What was verified, and what was not
| | |
|---|---|
| QML syntax, all 9 files | `qmlformat` parse, clean |
| shader compiles, all 6 targets | `qsb` exit 0; GLSL output read, audio terms present |
| std140 offsets 88/92/96/100 | `qsb --dump` reflection — **read, not counted by hand** |
| XML schema still valid, `AudioReactive` present | parsed with `xml.dom.minidom` |
| transfer integrity | md5 identical cloud → device → installed |
| **the contract itself** | `tests/wallpaper/audio_contract.qml`, 22 checks — **needs a QML engine, so it runs on the box, not here** |
| **audio actually reaching the screen** | ❌ **not verified — needs plasmashell restarted and something playing** |

The last row is the honest gap. The bridge VM is a different machine from the G14 (proven 2026-09-16:
uid 1004, hostname `claude`, no user `shawn`, empty `/run/user`), so nothing in this session can
restart plasmashell or hear a sound. Two commands close it, both on the box:

```bash
qml6 ~/luminos-os/tests/wallpaper/audio_contract.qml ; echo $?   # expect 0
systemctl --user restart plasma-plasmashell    # then pick Native QML → Spectrum, play music
journalctl --user -b -t plasmashell | grep LUMINOS-WP            # expect silence, not a warning
```

### Next
§3.2 per-scene properties. It is the one that turns a scene into something with its own settings
panel, and CONTRACTS §4 already froze the schema and the storage (one `SceneProperties` key, because
a wallpaper's KConfig schema is fixed at build time and cannot grow at runtime). After that §3.4
shader loader — now cheaper than it was this morning, because `iAudio` already exists and Shadertoy's
audio convention is the one we implemented.
