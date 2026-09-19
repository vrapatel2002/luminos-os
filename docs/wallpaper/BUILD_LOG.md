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

## 2026-09-19 — session 2b: the test ran on the box, and its WARNINGS were the useful part

`qml6 tests/wallpaper/audio_contract.qml` → **22/22, exit 0.** The contract holds on the real engine,
not just on a parser in a container.

But the line above the results said:

```
qt.qml.propertyCache.append: Member enabled of the object AudioBridge_QMLTYPE_0
overrides a member of the base object.
```

`Item` already has `enabled`. Mine was shadowing it. It *worked* — every check passed — and that is
exactly the problem: it would have kept working until something read `Item.enabled` on the bridge and
silently got the audio switch instead. Renamed to `audioEnabled` throughout (bridge, caller, test).

**Exit code 0 is not the whole result.** The test was green while the engine was telling us the type
was malformed. Read what the run printed, not just what it returned.

### Two bridge traps found the hard way
1. **`device_commit_files` can answer `written` before the bytes are visible to `device_bash`.** The
   first rename commit reported success; a `grep` in the very next call still saw the old file, and a
   `git commit` after it staged nothing and looked like the edit had failed. Re-sending it worked.
   **Always md5 the device copy against the container copy before acting on a commit**, the same way
   we already do for binaries — this time the risk was not corruption but *staleness*.
2. **Multi-line shell pastes with trailing `# comments` are dangerous.** A paste of three commented
   commands turned into `systemctl --user restart '#' then pick Spectrum '+' play music` and
   `git push origin main '#' remote is SSH the bridge has none` — systemd dutifully tried to restart
   `then.service` and `Spectrum.service`, and git tried to push refs named `remote` and `SSH`.
   Nothing was harmed, but **neither command actually ran**, and the output looked like failure of the
   real thing rather than of the comment. Hand over one command per line, no trailing comments.

## 2026-09-19 — session 3: SPEC §3.2, a scene that carries its own settings

### What landed
```
ui/props/PropertyStore.qml     new  schema load + merge; used by the wallpaper AND the panel
ui/props/PropertyEditor.qml    new  one row per schema key, changed(key,value) out
ui/props/PropertyControls.qml  new  the eight Lively control types, one Component each
ui/scene.js                    new  the built-in scene map, shared by host and config
ui/QmlMode.qml                 mod  owns the store, binds `props`, uses scene.js
ui/scenes/Spectrum.qml         mod  bars/sensitivity/colours/beat-flash from props
ui/scenes/Shader.qml           mod  uSpeed/uAudioGain/uTint bound by name
ui/scenes/{Shader,Spectrum}.properties.json   new
shaders/luminos-shader.frag    mod  3 uniforms appended at std140 104/108/112
ui/main.qml, ui/config.qml, config/main.xml   mod  the SceneProperties key and the panel
tests/wallpaper/props_contract.qml    new  21 checks, qml6 on the box
tests/wallpaper/test_shipped_props.py new  7 tests, the shipped schemas
```
Repo and the installed copy are `diff -rq` clean; every transfer md5-matched both ends.

### The decision worth writing down: the merge exists twice
`scripts/luminos-wallpaper-pkg` owns `validate_properties()` / `merge_props()` and has the property
tests. But **QML cannot call that Python**, and the merge has to happen inside plasmashell. So
`PropertyStore.qml` is a second copy of the same rules.

That is a real risk, not a shrug: two copies of a merge is how a slider ends up showing one number
while the wallpaper renders another, and nothing crashes. The mitigation is not "be careful" — it is
that `props_contract.qml` runs **the same cases** against the QML copy that the Python suite runs
against the Python one, including the garbage-input ones. Change one, change both, run the pair.

### Two things that are one bug waiting to happen, closed early
1. **The scene map lived in QmlMode.qml only.** `config.qml` needs to resolve the same scene to find
   its `properties.json`. A second copy of that table is how the panel ends up editing the properties
   of a scene the wallpaper is not showing — and that presents as "my settings don't do anything",
   which is about the worst symptom to debug. Moved to `ui/scene.js`, imported by both.
2. **Delegate keys are handed over in `Loader.onLoaded`, not through the Loader's context.** Whether a
   `Component` declared outside a `Loader` can resolve that Loader's own properties is a QML scoping
   rule, and I cannot run a QML engine here to settle it. Two lines of explicit assignment have no
   rule to be wrong about. The same instinct as BUG-168: do not let a near-miss question pass.

### The half of §3.2 that is NOT here, said out loud
SPEC §3.2 also promises property keys mapping onto **any** shader's uniforms automatically. A QML
object cannot gain a property at runtime, so that means building the `ShaderEffect` from generated
source with `Qt.createQmlObject` — which is exactly what **§3.4** (drop in any Shadertoy `.frag`)
needs. Doing it here, against one shader whose uniforms are already known, would be inventing the
hard part in the easy case and then rewriting it. It lands with §3.4. The built-in shader's three
uniforms are bound by name today, so the mechanism is demonstrated, just not generalised.

### Budget check (SPEC §9)
`PropertyEditor` came out at 213 lines against a 200-line host budget. Rather than shaving comments
until the number passed, the eight control Components moved into `PropertyControls.qml` — 106 + 118,
and it reads better: one file is "what a row looks like", the other is "what a control is". A budget
that forces a real seam is doing its job; a budget met by deleting explanations is not.

| file | lines | budget |
|---|---|---|
| PropertyEditor.qml | 106 | 200 host |
| PropertyControls.qml | 118 | 200 host |
| PropertyStore.qml | 171 | 200 host |
| QmlMode.qml | 119 | 200 host |
| AudioBridge.qml | 156 | 200 host |
| Shader.qml | 136 | 150 scene |
| Spectrum.qml | 144 | 150 scene |

### Verified
| | |
|---|---|
| QML syntax, all new/changed files | `qmlformat` parse, clean |
| shader compiles; uniforms at 104/108/112 | `qsb` exit 0; offsets **read from `qsb --dump`** |
| `uTint` default reproduces the old constant | `#d959a6` vs `vec3(0.85,0.35,0.65)`, equal to 8-bit rounding |
| KConfig schema still valid, `SceneProperties` present | parsed with `xml.dom.minidom` |
| package + schema suite | **27 passed** in the build container (20 + 7 new) |
| transfer integrity | md5 identical cloud → device → installed, 12 files |
| **the QML merge rules** | `props_contract.qml`, 21 checks — **needs a QML engine, so it runs on the box** |
| **the panel on screen** | ❌ **not verified — plasmashell has not been restarted since §3.1** |

### Next
**§3.4, not §3.3.** It is the cheaper item, it carries §3.2's deferred half, and `iAudio` already
exists so Shadertoy audio shaders arrive with it. §3.3's Python half (`parse_manifest`,
`lively_to_manifest`, `_path_safe`) is already written and tested; what it still needs is the gallery
UI and the install path, which is a bigger surface than the shader loader.

## 2026-09-19 — session 4: SPEC §3.4, and the promise §3.2 had to defer

### What landed
```
contents/tools/luminos-shader-bake     new  the compiler, Python, 31 tests
contents/tools/shader-wrapper.glsl     new  the GLSL shell, as data not a string
ui/props/ShaderBaker.qml               new  runs it, validates the answer
ui/scenes/ShaderToy.qml                new  generates the ShaderEffect
ui/audio/AudioTexture.qml              new  the 128x1 spectrum, now shared
ui/scenes/Shader.qml                   mod  uses the shared texture (136 -> 101 lines)
ui/scene.js                            mod  a .frag is a scene
ui/QmlMode.qml                         mod  binds `source`, props read beside the shader
ui/props/PropertyStore.qml             mod  strips any extension, not just .qml
ui/config.qml                          mod  one file box for both kinds + a sample
samples/luminos-shadertoy.frag(+json)  new  a working Shadertoy-shaped example
scripts/luminos-wallpaper-cost         new  what it costs, as numbers
tests/wallpaper/test_shader_bake.py    new  31 tests
```

### Why the compiler ships inside the plugin
The first design called `luminos-shader-bake` from `PATH`, which means the wallpaper only works if a
separate install step copied a script to `/usr/local/bin`. Two things killed that: a KPackage is meant
to be self-contained, and **the lock screen loads this same package**, where nothing would have put it
on `PATH` at all. So it lives in `contents/tools/` and is called by a path derived from
`Qt.resolvedUrl`, through `python3` — a KPackage install does not promise to keep the executable bit.

### This is where §3.2's deferred half actually lands
§3.2 promised property keys mapping onto shader uniforms by name and stopped short, because **a QML
object cannot gain a property at runtime**. There is exactly one way round that: build the object from
generated source. Doing it in §3.2, against one shader whose uniforms were already known, would have
been inventing the hard part in the easy case. Here the source is arbitrary, so the machinery is
justified and it covers both. A `properties.json` key next to any `.frag` is now a slider AND a
uniform, with no glue code.

### The template bug, because it cost twenty minutes and looked like anything but itself
The GLSL wrapper is a data file so it can be read as GLSL. Its header comment *mentioned* the
`%(props)s` placeholder — and the whole file goes through one percent-format, so the generated uniform
declarations were spliced **into the comment**, leaving a stray backtick on the following line. The
compiler said:

```
ERROR: .../8aa113cf.frag:9: '`' : unexpected token
```

on a line that reads perfectly. The lesson is narrow and worth keeping: **a template's own
documentation is inside the template.** The file now says so in its header, and
`test_the_template_placeholder_never_survives_into_the_output` keeps it fixed.

### What is validated, and where
A uniform name goes into **generated QML**, and a path goes into a **URL string**. Both are produced by
the baker and both arrive in QML over a pipe, so both are checked twice:

| | baker (Python) | scene (QML) |
|---|---|---|
| uniform name | `^[A-Za-z_][A-Za-z0-9_]{0,31}$`, not in `_RESERVED` | same regex again before splicing |
| `.qsb` path | written by us into our own cache dir | absolute, ends `.qsb`, no `"` `'` `\` newline |
| `.frag` path | opened, never interpolated | POSIX single-quoted into the command |

`test_a_reserved_name_can_never_become_a_uniform` is property-based over generated schemas rather than
a list of examples, because the failure it prevents — a property called `iTime` compiling into a
duplicate declaration — takes the whole wallpaper down.

### Budgets (SPEC §9)
The baker hit 175 lines against a 150-line budget and `bake()` hit 41 against 40. Both were fixed by
real seams, not by deleting explanations: the GLSL moved into its own data file (where it belongs
anyway), and the compile step became `_compile()`. Same for the scene — `ShaderToy.qml` was 162, so
the "how a shader gets compiled" half became `ShaderBaker.qml`. `budget_check.py` passes on all of it.

| file | lines | budget |
|---|---|---|
| tools/luminos-shader-bake | 148 | 150 python |
| ui/scenes/ShaderToy.qml | 120 | 150 scene |
| ui/scenes/Shader.qml | 101 | 150 scene |
| ui/props/ShaderBaker.qml | 91 | 200 host |
| ui/audio/AudioTexture.qml | 67 | 200 host |
| ui/QmlMode.qml | 132 | 200 host |

### "Lighter than Chromium" is now a number
Shawn asked for it to stay light. That is a claim until it is measured, so
`scripts/luminos-wallpaper-cost` reports the three things that can actually be checked: whether
`libQt6WebEngineCore` is mapped into plasmashell at all, PSS from `smaps_rollup` (not RSS — RSS
double-counts shared libraries and is why a shell can look like it owns a gigabyte it shares), and CPU
jiffies over a window as a percentage of one core. It prints BUG-083's recorded Chromium-era numbers
next to them, and it says out loud that it measures plasmashell as a whole and cannot separate the
desktop from the wallpaper. **Structurally the cost is already decided:** the only thing that maps
WebEngine is web mode, and nothing in §3.1/§3.2/§3.4 touches it — audio, properties and shaders are
all Qt objects in a process that was already running.

### Verified
| | |
|---|---|
| a real Shadertoy shader compiles | `mainImage` + `iTime`/`iResolution`/`iMouse`/`iChannel0`, all six qsb targets |
| reserved/invalid names cannot become uniforms | property-based over generated schemas |
| cache is content-addressed | same path twice; ~90 ms cold, 0.1 ms warm |
| every failure is one line | missing file, bad JSON, missing qsb, broken GLSL — all tested |
| QML syntax | `qmlformat` clean on every new and changed file |
| budgets | `budget_check.py` PASS |
| suite | **58 passed** (20 package + 7 schema + 31 shader) |
| transfer | md5 identical cloud → device → installed, 11 files |
| **on screen** | ❌ **still not verified — plasmashell has not been restarted since §3.1** |

### Next
**§3.5** (`.js` canvas wallpapers, CONTRACTS §6 already specifies the shim) or **§3.3** (packages +
gallery + Lively import, whose Python half is already written and tested). §3.6 — games through a
nested compositor — remains the big one and the only thing that lets web mode finally be deleted.

## 2026-09-19 — session 4b: the cost script's first run, and what it got wrong

Shawn ran `luminos-wallpaper-cost 10` before restarting plasmashell. The reading:

```
mode           video / scene ?
audio          false
chromium       not mapped
audio stack    libpipewire mapped
PSS            355 MB
CPU            1.9% of one core
```

**Two of those six lines were the instrument asking the wrong question**, which is the third time in
this project, so it gets written down rather than quietly patched.

1. **`audio stack  libpipewire mapped`** reads as "the wallpaper's audio is live". It is not evidence
   of anything. **KDE maps PipeWire into plasmashell regardless** — volume, screencasting — and
   `AudioReactive` was `false` on the very line above. The decisive library is **`libcava`**, which
   nothing else on this box pulls in. Fixed to report libcava, and to say in the same breath that
   libpipewire proves nothing.
2. **`scene ?`** made a perfectly normal config look like a failed read. `QmlScene` had simply never
   been changed, so the key is absent — which means *the default*, not *unknown*. Fixed to print
   `shader (default, never set)`.
3. And a latent one nobody saw yet: the config read took the **first match anywhere in the file**.
   That file holds other containments and the lock screen. It happened to be right here because there
   is exactly one containment — luck, not correctness. It now reads only the groups belonging to
   `org.luminos.livewallpaper`.

Also added: the run now says **"mode is not 'qml', so this is a BASELINE"**, because that is the most
important thing about this particular reading — none of §3.1/§3.2/§3.4 was running when it was taken.
And the comparison line now admits that **810 MB was RSS and 355 MB is PSS**, which are different
measures; only the CPU numbers are comparable.

### What the reading does legitimately say
- **`chromium not mapped`** — the headline, and unambiguous. libQt6WebEngineCore is not in
  plasmashell's address space. DECISION 112 is what made that possible and it is still holding.
- **1.9% of one core** against BUG-083's **~24%** for the Chromium-era wallpaper. Same measure, same
  kind of workload (a playing video), so this one is a fair comparison.
- **355 MB PSS** is the whole shell, not the wallpaper.

### The bridge trap fired again, and the documented check caught it
`device_commit_files` answered `written`; the device still had the previous 160-line copy, and only
the **md5 comparison** showed it. Re-sending fixed it. Second occurrence — this is a reliable hazard,
not a one-off, and "always md5 the device copy against the container copy" earns its place.
