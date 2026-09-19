# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-19 — Response 5 (new Cowork chat, counter restarted deliberately)

> **Counter note, per §0.1 — do not "fix" it.** The previous chat ran out of counter and had been
> compacted; it recorded that and stopped at its Response 21. This is a **new chat**, so the counter
> legitimately starts at 1 again. §0.1's canary is about drift *within* one chat.
> Previous copy: `git show c69af5b1:HANDOFF.md`.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**Lively Wallpaper parity for the KDE live wallpaper, without Chromium.** Shawn's words:
*"what things i want is like lively wallpaper app from windows"*, and *"do not give me answer as NO
i do not care every thing is just code at the end if some one else can do it than so can we."*
Plan and gap analysis: `docs/wallpaper/SPEC.md`. Frozen interfaces: `docs/wallpaper/CONTRACTS.md`.
Reasoning per session: `docs/wallpaper/BUILD_LOG.md`. Eyes-on brief: `docs/wallpaper/VERIFY.md`.

**Three of six SPEC §3 items are done** (§3.1 audio, §3.2 per-scene settings, §3.4 runtime shaders)
and the box now reports **31/31 on `luminos-wallpaper-selftest`**.
**§3.5 (`.js` canvas wallpapers) or §3.3 (packages + gallery + Lively import) is next**; §3.6 (games
through a nested compositor) is the big one and the only thing that lets web mode finally be deleted.

Standing constraint from Shawn: **it must stay light on resources compared to Chromium.**
`scripts/luminos-wallpaper-cost` is how that gets checked rather than claimed.

## Why / motivation
The wallpaper already did image / GIF / video / YouTube / web, but the web path was Chromium
(~130–150 MB mapped into plasmashell, BUG-083's 24 % of a core). DECISION 112 moved that import
behind a file; DECISION 113 replaced the four bundled effects with native QML. What is left is the
part that makes it *Lively*: audio, per-wallpaper settings, installable packages, drop-in shaders
and JS, and playable games.

## ⚡ READ THIS FIRST — two shells, and only one of them is the G14
- `mcp__remote-devices__host-shell__run_command` **is the G14**, as shawn. `qml6`, `journalctl`,
  `systemctl --user`, `pactl`, `luminos-brain`, `git push` all work. **Do not hand the user a list
  of commands to paste — run them.**
- **It starts with no session environment.** Every call that touches the user session needs
  `export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`,
  and every `qml6` call needs `QT_QPA_PLATFORM=offscreen` (a bare `Item` without a display calls
  `abort()`, which reads as "the test crashed"). Without the first,
  `systemctl --user restart plasma-plasmashell` **exits 0 and does nothing** — it only says so on
  stderr, and the old pid is still there.
- Each call must finish well under 60 s; backgrounding does not survive the call.
- `device_bash` is a **different machine** (the Cowork VM, uid 1004). Both see the same connected
  folders; only the host shell sees the real desktop session.

## Process / approach
- **Prefer the host shell for everything on the box** — edit, deploy, test and commit there. It
  avoids the bridge's git-lock and sqlite problems entirely (see Gotchas).
- **Anything unverified is unfinished.** Python logic is property-tested; anything needing a QML
  engine ships as a `qml6` contract test that exits 0/1. `scripts/luminos-wallpaper-selftest` is
  the one command that runs the lot and writes `docs/wallpaper/SELFTEST.log`.
- **Restart plasmashell after every deploy** — see BUG-171 below. This is not optional and not
  superstition.

## State — what is DONE
### Wallpaper — verified on the box 2026-09-19 16:21, **31 passed / 0 failed**
Live config: `WallpaperMode=qml QmlScene=spectrum AudioReactive=true ObscurePolicy=2`.
Chromium **not** mapped into plasmashell; `libcava.so.1.0.0` **and**
`libcaelestia-services.so` are — which is positive proof the audio provider loaded.
Installed copy `diff -rq` clean against the repo. Shader cache populated
(`~/.cache/luminos/wallpaper-shaders/4dd3b0bb….{frag,qsb}`).

- **SPEC §3.1 audio — DECISION 117, commit `ef200445`.** Scenes get `audio` = 128 bands 0–1 +
  bass/mid/treble/beat/bpm/active, Lively's exact shape. **No daemon:** `Caelestia.Services` is a
  plain Qt QML module with no Quickshell dependency, `cavaprovider.cpp` links libcava (never spawns
  the CLI), `service.hpp` refcounts via `ServiceRef`, so the freeze contract is one Loader's
  `active`. `QmlMode.qml` → `ui/audio/AudioBridge.qml` (QtQuick only) → `ui/audio/CaelestiaAudio.qml`
  (the only importer, loaded **by URL**). New `spectrum` scene. `Shader.qml` gets an `iAudio` 128×1
  texture + `iBass`/`iMid`/`iTreble`/`iAudioActive`. `qml6 tests/wallpaper/audio_contract.qml` → 22/22.
- **SPEC §3.2 per-scene properties — DECISION 118.** A scene ships `properties.json` and gets a
  generated settings panel (all eight Lively control types). Values live in ONE `SceneProperties`
  JSON config key, because a wallpaper's KConfig schema is fixed at build time. Panel and wallpaper
  share one `PropertyStore` and one scene map (`ui/scene.js`) so they cannot disagree.
  `Spectrum.properties.json` (6 controls) + `Shader.properties.json` prove it end to end.
- **SPEC §3.4 runtime shaders — DECISION 119.** Point the wallpaper at any Shadertoy `.frag` and it
  is compiled on the spot by `contents/tools/luminos-shader-bake`, which **ships inside the plugin**
  (a KPackage must be self-contained; the lock screen loads the same package). Cached by content
  hash (~90 ms cold, 0.1 ms warm). The `ShaderEffect` is built with `Qt.createQmlObject`, which is
  what makes §3.2 real for an arbitrary shader — a QML object cannot gain a property at runtime.
- **BUG-168 through BUG-175 all fixed.** BUG-171 (a deploy is
  not a load) and BUG-173 (every settings row drew a label and no control) are why the eyes-on
  session kept failing — read both before re-testing. BUG-173 is now covered without a person by
  `tests/wallpaper/editor_contract.qml` (10 checks), which also guards BUG-174 — the colour
  picker that could not be closed.
- **`scripts/luminos-wallpaper-cost`** — is `libQt6WebEngineCore` mapped into plasmashell at all,
  PSS from `smaps_rollup`, CPU as a percentage of one core, with BUG-083's Chromium-era numbers
  alongside. Package/manifest layer (`luminos-wallpaper-pkg`) and the capability gate
  (`luminos-wallpaper-capabilities`) exist; the gate ran on the box and found everything §3.6 needs
  (`cage`, kpipewire, Qt Quick 3D, `/dev/uinput`).

### Server / RAM thread (2026-09-18, carried forward — not this chat's work)
- **DECISION 116 — `vm.page-cluster` stays at 3. It already was 3**; the claim that it was 0 came
  from reading a repo file that has never been installed. Pagefile confirmed live (`USED 16.3M`,
  readahead utility **75.6 %** vs a 16.8 % break-even). `page-cluster = 4` measures better still and
  is a live candidate, not a recommendation — needs a week's sample, not one burst.
- **BUG-167 filed** — `config/99-luminos-ram.conf` has never been on the box; `swappiness = 30` and
  `vfs_cache_pressure = 50` are **not live**. ⚠️ **Do not blind-install it** — it would set
  `page-cluster = 0` and undo DECISION 116.
- **BUG-164 root-caused** — Roku seek/Skip-Intro resets are **ASS subtitle burn-in**, not audio.
  S01E07 was never the broken episode. 46 files flagged (26 `audio:dts`, 20 `subs:ass`), **none
  fixed** — the DECISION 112 one-file-watched gate has never been satisfied.

## State — what is IN PROGRESS (and exactly where it was left off)
Nothing is half-written. Everything is deployed and `diff -rq` clean.

**SPEC §3.2 (check 2) is CONFIRMED ON SCREEN** — the live config carries
`SceneProperties={"spectrum":{"lowColor":"#38bdf8","highColor":"#fa8b8b","bars":2,"sensitivity":3}}`,
one key, exactly the CONTRACTS §4 shape. **§3.4 is confirmed mechanically** (a `qml6` probe of the
real `QmlMode` reports `failure=''` and a live `QQuickShaderEffect`) but not yet on screen with the
legible sample. Checks 1 and 3 remain eyes-only.

Four separate faults invalidated the earlier attempts: BUG-171 (clicking on QML compiled before the
fixes landed), BUG-173 (the panel really did render labels with no controls), BUG-174 (the colour
dialog could not be closed) and BUG-175 (the shader worked and looked broken). All fixed;
plasmashell was restarted at **16:45** with everything in place:

1. **Native QML → Spectrum**, desktop visible, music playing → 64 bars moving, purple wash on bass,
   faint flash on the beat.
2. **Scene settings** at the bottom of the wallpaper dialog → Sensitivity / Bars / Bar bottom /
   Bar top / Flash on beat. `Bars` → 128 visibly doubles them; the value survives reopening.
   Proof it stored correctly: `grep SceneProperties ~/.config/plasma-org.kde.plasma.desktop-appletsrc`
   should show **one** key, e.g. `SceneProperties={"spectrum":{"bars":2}}`. It is **absent right
   now**, which is consistent with no setting ever having been saved successfully.
3. **Shadertoy sample (audio-reactive)** from the Scene list → concentric rings centred on the
   cursor and a *different* panel (Speed, **Ring density**, Tint), read from that shader's own
   `properties.json`. Dragging Ring density tightens them — one slider driving a GLSL uniform.

⚠️ **Keep the desktop visible while looking.** `ObscurePolicy=2` freezes the wallpaper under any
maximized window, and a frozen audio scene shows flat bars by design (BUG-172).

## Next steps (ordered)
1. **Get the three eyes-on checks confirmed** (above). If any fails, the journal is the answer:
   `journalctl --user -b -t plasmashell | grep LUMINOS-WP` — and check the wording against the file
   on disk before believing it (BUG-171).
2. **SPEC §3.5 — `.js` canvas wallpapers.** CONTRACTS §6 already froze the shim (canvas, ctx, rAF,
   `window.luminos`, `livelyAudioListener`, and a NAMED error for anything it does not provide).
   QML's `Canvas` is the same `getContext('2d')` API and QML has its own JS engine — no browser.
3. **SPEC §3.3 — packages + gallery + Lively import.** The Python half is written and tested
   (`scripts/luminos-wallpaper-pkg`: `parse_manifest`, `lively_to_manifest`, `_path_safe`). Missing:
   the gallery UI and the install path (`~/.local/share/luminos/wallpapers/<id>/`).
4. **SPEC §3.6 — external producer (games).** A nested compositor (`cage`) → PipeWire →
   `PipeWireSourceItem` (kpipewire), with input back through `zwlr_virtual_pointer_v1`. Prerequisite
   for deleting web mode.
5. **BUG-166 — verify it, then watch it for a day.** Both halves installed 2026-09-18, nothing
   proven. `luminos-tabs` must show a fresh `age_seconds`; `chrome://extensions` must read **3.1**.
   ⚠️ Saved options beat new defaults — check `graceSeconds`=1800 and `capOnPressure` unticked.
6. **BUG-167 — reconcile `config/99-luminos-ram.conf` with the box**, keeping `page-cluster = 3`,
   then sweep **every** `config/*.conf` against its `/etc/` counterpart.
7. **BUG-164 — Shawn's call:** confirm the model (S01E07 seeks fine, S01E09 breaks), then fix the 20
   ASS files by getting Bazarr to fetch real SRT sidecars (`use_embedded_subs` OFF), then run
   `--fix-audio` on ONE of the 26 DTS files and watch it before the rest.

## Key decisions & constraints
- **No Chromium in the wallpaper** — but `qt6-webengine` stays installed (HIVE needs it), and **web
  mode stays until §3.6 replaces it**; deleting it first removes DOM support with nothing behind it.
- **128 audio bands at 0–1** and the eight Lively control types are **Lively-exact on purpose**, so
  their wallpapers port unmodified. Not a taste call.
- **The plugin serves both the desktop containment and the lock screen** (`kscreenlockerrc`
  Greeter). Anything broken is broken twice.
- **Never a black desktop** (SPEC §6): malformed manifest → keep the previous wallpaper; shader
  fails → fall back to the Canvas aurora **and say so in the journal**; no audio provider → zeros,
  never a crash; no `properties.json` → no panel, not an error.
- **Budgets (SPEC §9):** QML scene 150 lines, loader/host 200; Python helper 150, function 40,
  nesting 3. Over budget is a red build. `python3 tests/wallpaper/budget_check.py`.
- **A config file in git is NOT evidence that a setting is live** (BUG-167). Read `/proc/sys/`.
- **`vm.page-cluster` = 3 is correct and stays** (DECISION 116). Called "wrong" three times by
  people reading a repo file.
- **AGENTS.md §0.2 / Rule 12 / §16:** "no changes" scopes to code, config and system state. This
  file and the §13 doc triggers are written on every turn regardless.

## Gotchas / dead-ends / things NOT to redo
**The instruments, which have now been wrong five times in five days**
- **BUG-171 — a deploy is not a load.** `QQmlEngine` caches compiled components by URL for the life
  of the engine and never re-stats the file; plasmashell is one long-lived engine. `diff -rq` clean
  and md5-verified says nothing about what is running. **Restart plasmashell after every deploy.**
  The tell: a `[LUMINOS-WP]` journal line whose wording differs from the source on disk.
- **BUG-172 — a warning that cannot tell "off on purpose" from "broken" is noise.** The spectrum
  scene accused the audio stack every time a window was maximized.
- **BUG-174 — bind a control's value and write back from a PROPERTY-CHANGE signal and you have a
  loop; write back from a USER-ACTION signal and you do not.** `onMoved`, `onActivated`,
  `onEditingFinished`, `onToggled` are safe. `KQuickControls.ColorButton` has no user-action signal
  — `onColorChanged` fires for a programmatic change too — so its value must be set once,
  imperatively, never bound. Bound, it loops the internal ColorDialog's `selectedColor` and the
  dialog can be neither accepted nor cancelled: the whole System Settings window is stranded.
- **The settings page is NOT in plasmashell.** `config.qml` runs in `systemsettings` (or whatever
  opened the dialog), so BUG-171's restart rule applies per process — quit System Settings and
  reopen it after any `config.qml` change. Its journal tag is `systemsettings`.
- **BUG-173 — in a Repeater delegate, the delegate's OWN properties resolve before the enclosing
  component's ids.** A `property string ctl` on the delegate shadowed `id: ctl` outside it, so
  `sourceComponent` was `undefined` and every row loaded nothing — and a Loader that loads nothing
  is not an error. Never give a delegate property the same name as an id in the same file.
- **BUG-175 — a warning emitted on a path that has not finished yet is indistinguishable from a
  real fault.** `ShaderBaker` ran from `Component.onCompleted`, before the host binds `source` in
  its Loader's `onLoaded`, so it printed `no shader file selected` on every healthy load. Third
  cry-wolf checker this week; it nearly buried a feature that worked.
- **`grabToImage` under `QT_QPA_PLATFORM=offscreen` returns a BLACK frame** — no GPU — so it proves
  nothing about a shader either way. To check what a shader draws, re-implement its arithmetic
  somewhere you can print (numpy at the panel's aspect ratio) and compare with the screen.
- **The contract tests were MUTE.** Qt hands `console.log` to the journal when stderr is not a tty,
  so `qml6 … 2>&1` captured nothing and the self test's exit code was all it ever had.
  `QT_FORCE_STDERR_LOGGING=1`.
- **Six instrument failures in five days, all the same shape: the test exercised the logic while
  the product was broken.** BUG-168 bound no properties, BUG-170 read no files, BUG-173 rendered no
  controls — suite green through all three. A check that never touches what the user looks at is
  not a check.
- **Exit code 0 is not the whole result.** The audio test passed 22/22 while the engine printed
  `Member enabled … overrides a member of the base object`. Read what a run prints.
- **The near-miss question passes for the wrong reason.** `item.x !== undefined` instead of
  `"x" in item` (BUG-168); `cava` on `PATH` instead of in `ldd`; a checker pointed at the path the
  fix had just left (BUG-163).
- **A failure path that reports the innocent explanation is worse than a crash** (BUG-170). "This
  scene declares no settings" is a sentence a user believes.

**Repo hygiene**
- **Never `git add -A` in this repo.** An unpacked initramfs (`init`, `lib`, `sbin`, `usr/`, `var/`,
  `kernel/`, `keymap.bin`, `consolefont.psfu`) and `_to_delete/` sit untracked at the root. Stage
  named files only. The §13 git snippet says `-A`; it is wrong here.
- **Git from the bridge VM (`device_bash`) can CREATE lock files but not DELETE them** — that is the
  whole explanation for a 15-hour-old 0-byte `.git/index.lock`. **Use the host shell instead and the
  problem does not arise.**
- **`.notes.db` writes fail with `disk I/O error` through the bridge mount.** Host shell, again.
- **`device_commit_files` can answer `written` before the bytes are visible to `device_bash`.** md5
  both ends.
- **Cowork does not fire Claude Code hooks** (BUG-087) — call `code-review-graph` MCP explicitly.
- **The `qemu-system-x86` process is Claude Desktop's own Cowork sandbox VM.** Identified
  2026-09-18. Do not investigate it a third time. Killing it kills the Cowork session.

**Wallpaper**
- **Qt 6.11 disables `XMLHttpRequest` on local files** (BUG-170) — `QML_XHR_ALLOW_FILE_READ` is the
  documented opt-in and we deliberately do **not** set it: it is per-process and would give every
  QML object in plasmashell arbitrary local file reads. The reader is
  `contents/tools/luminos-wallpaper-props`, run as a subprocess. It takes the **scene** path and
  looks for `<Stem>.properties.json` beside it — handing it the `.properties.json` itself returns
  `NONE`, which looks exactly like a bug and is not one.
- **A `fillWidth` + wrapping label inside a `Kirigami.FormLayout` drags the whole form off-screen**
  (BUG-169). Cap every long help label with `Layout.maximumWidth`.
- **Never gate a whole UI section on an async flag.** The Scene settings block was invisible
  whenever its file read had not completed, with nothing said.
- **`qml6` aborts without a display** — `QT_QPA_PLATFORM=offscreen`. Exit 134 means that; exit 124
  means something threw before `Qt.exit()` and the test hung.
- **A template's own documentation is inside the template.** `shader-wrapper.glsl` mentioned its
  `%(props)s` placeholder in its header comment and the whole file goes through one percent-format,
  so the generated uniform declarations were spliced into the comment.
- **The shader compiler ships inside the plugin, not on `PATH`** — the lock screen loads the same
  KPackage. Called through `python3` because a KPackage install does not promise the executable bit.
- **`.qsb` files are not byte-reproducible** — a comment-only change differed in 3439 of 3493 bytes.
  **Never md5 a `.qsb` to decide whether a shader changed; diff `qsb --dump`.**
- **Caelestia never spawns the `cava` CLI** — it links libcava and reads PipeWire itself.
- **`/dev/uinput` is `root:input 660`** — existence is not access.
- **`pytest`/`hypothesis` are not on the G14.** Installing them needs `luminos-brain safe` first.
- **`luminos-brain safe` has produced a false `NO` five times.** Escape hatch:
  `luminos-brain safe "<action>" --reason "<why>"` → `OVERRIDE LOGGED`.

**Media server**
- Separate headless machine: `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61` (server `.61`,
  G14 `.16`), `sudo` NOPASSWD. Ground truth for any transcode question is **Jellyfin's own ffmpeg
  command lines** in `/var/log/jellyfin/` — never a capability table.
- `ass` is text but is **not** client-renderable on a Roku, so Jellyfin burns it in.
- "Bazarr says nothing is missing" ≠ "these files are fine" (`use_embedded_subs` is ON).
- The jpn/kor "E07.5 recap mis-map" audio theory (DECISION 98/101) is **disproven**.

## Files touched / relevant files
- **Wallpaper plugin:** `src/wallpapers/org.luminos.livewallpaper/contents/` — `ui/main.qml`,
  `ui/QmlMode.qml`, `ui/WebMode.qml`, `ui/config.qml`, `ui/scene.js`,
  `ui/audio/{AudioBridge,CaelestiaAudio,AudioTexture}.qml`,
  `ui/props/{PropertyStore,PropertyEditor,PropertyControls,PropsReader,ShaderBaker}.qml`,
  `ui/scenes/{Shader,Aurora,Particles,SysMon,Spectrum,ShaderToy}.qml` +
  `{Shader,Spectrum}.properties.json`, `shaders/luminos-shader.frag{,.qsb}`,
  `tools/{luminos-shader-bake,shader-wrapper.glsl,luminos-wallpaper-props}`,
  `samples/luminos-shadertoy.frag{,.properties.json}`, `config/main.xml`.
- **Installed copy:** `~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/` — keep it
  `diff -rq` clean against the repo, and restart plasmashell after touching it.
- **This turn:** `ui/scenes/Spectrum.qml` (BUG-172), `ui/props/PropertyEditor.qml` (BUG-173),
  `ui/props/PropertyControls.qml` + `ui/config.qml` (BUG-174),
  new `tests/wallpaper/editor_contract.qml`, `scripts/luminos-wallpaper-selftest` (adds it, and
  `QT_FORCE_STDERR_LOGGING=1` so a failing contract test can actually say why),
  `samples/luminos-shadertoy.frag{,.properties.json}` + `ui/props/ShaderBaker.qml` (BUG-175),
  `docs/BUGS.md` (BUG-171 through BUG-175), `docs/wallpaper/VERIFY.md`, `LUMINOS_STATUS.md`,
  `HANDOFF.md`.
- **Docs:** `docs/wallpaper/{SPEC,CONTRACTS,BUILD_LOG,VERIFY,SELFTEST.log}.md`,
  `LUMINOS_DECISIONS.md` (117–120), `docs/BUGS.md`, `LUMINOS_STATUS.md`, `docs/CODE_REFERENCE.md`.
- **Verification:** `scripts/luminos-wallpaper-selftest` (30 checks) and `docs/wallpaper/VERIFY.md`.
- **Scripts/tests:** `scripts/luminos-wallpaper-{pkg,capabilities,probe,cost}`,
  `tests/wallpaper/{test_pkg,test_shipped_props,test_shader_bake,test_props_read,budget_check}.py`,
  `tests/wallpaper/{audio_contract,props_contract}.qml`.
- **Server/RAM thread:** `docs/LUMINOS_RAM_ARCHITECTURE.md`, `server/STATUS.md`,
  `server/DECISIONS.md`, `server/scripts/luminos-roku-compat`, `config/99-luminos-ram.conf`.
