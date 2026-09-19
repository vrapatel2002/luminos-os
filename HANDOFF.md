# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-19 — Response 4 (Cowork chat; see the counter note)

> ⚠️ **Counter note, recorded deliberately per §0.1 — do not silently "fix" it.** This is a **Cowork**
> chat (cloud container + device bridge), not Claude Code on the box. It ran a long way **without
> emitting the `Response N` line at all**, and it has been through a **context compaction**. Both are
> exactly what the canary exists to signal. The counter is resumed here at **4** counting the replies
> since AGENTS.md was re-read; the true number of turns before that is not recoverable. If the next
> reply does not carry a counter, start a new chat and continue from this file.
> Previous copy: `git show 8d5d1c4f:HANDOFF.md` — it was the server/RAM thread and is carried forward
> below, condensed, not deleted.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**Lively Wallpaper parity for the KDE live wallpaper, without Chromium.** Shawn's words:
*"what things i want is like lively wallpaper app from windows"*, and
*"do not give me answer as NO i do not care every thing is just code at the end if some one else can
do it than so can we."* Plan and gap analysis: `docs/wallpaper/SPEC.md`. Frozen interfaces:
`docs/wallpaper/CONTRACTS.md`. Reasoning per session: `docs/wallpaper/BUILD_LOG.md`.

Two of six SPEC §3 items are done. **§3.3 (packages + gallery + Lively import) is next** unless Shawn
redirects — §3.4 (runtime shader loader) is the cheaper one and carries §3.2's deferred half with it.

## Why / motivation
The wallpaper already did image / GIF / video / YouTube / web, but the web path was Chromium
(~130–150 MB mapped into plasmashell, BUG-083's 24 % of a core). DECISION 112 moved that import behind
a file; DECISION 113 replaced the four bundled effects with native QML. What is left is the part that
makes it *Lively*: audio, per-wallpaper settings, installable packages, drop-in shaders and JS, and
playable games.

## Process / approach
- **Build in the cloud container, deploy by checksum.** The container has Qt 6.4 tooling
  (`qmlformat`, `qsb`) and `pytest`/`hypothesis`; the box has Qt 6.11.2 and a real QML engine.
  Files cross via `device_commit_files` and **every transfer is md5-verified both ends**.
- **Anything unverified is unfinished.** Python logic is property-tested in the container; anything
  needing a QML engine ships as a `qml6` contract test that runs on the box and exits 0/1.
- **The bridge VM is NOT the G14** (uid 1004, hostname `claude`, no user `shawn`, empty `/run/user`).
  It cannot restart plasmashell, hear sound, run `luminos-brain`, `qml6`, `sqlite3` or `git push`
  (the remote is SSH). Anything needing those is handed to Shawn as one command per line.

## State — what is DONE
### Wallpaper (2026-09-19, this chat)
- **SPEC §3.1 audio — DECISION 117, commit `ef200445`.** Scenes get `audio` = 128 bands 0–1 +
  bass/mid/treble/beat/bpm/active, Lively's exact shape. **No daemon:** `Caelestia.Services` is a
  plain Qt QML module with no Quickshell dependency, `cavaprovider.cpp` links libcava (it never spawns
  the CLI), and `service.hpp` refcounts via `ServiceRef`, so the freeze contract is one Loader's
  `active`. Three files: `QmlMode.qml` → `ui/audio/AudioBridge.qml` (QtQuick only) →
  `ui/audio/CaelestiaAudio.qml` (the only importer, loaded **by URL**). New `spectrum` scene.
  `Shader.qml` gets an `iAudio` 128×1 texture + `iBass`/`iMid`/`iTreble`/`iAudioActive`.
  **Verified on the box: `qml6 tests/wallpaper/audio_contract.qml` → 22/22, exit 0.**
- **BUG-168 fixed** (`ef200445`) — the host tested `item.x !== undefined` before binding, so a scene
  declaring an uninitialised `property var` was silently handed nothing. Now `name in item`.
- **`AudioBridge.enabled` shadowed `Item.enabled`** — commit `2c62f8fb`. Found by reading the
  warnings *above* a green test result.
- **SPEC §3.2 per-scene properties — DECISION 118.** A scene ships `properties.json` and gets a
  generated settings panel (all eight Lively control types). Values live in ONE `SceneProperties`
  JSON config key, because a wallpaper's KConfig schema is fixed at build time. Panel and wallpaper
  share one `PropertyStore` and one scene map (`ui/scene.js`) so they cannot disagree.
  `Spectrum.properties.json` + `Shader.properties.json` prove it end to end; shader `uSpeed` /
  `uAudioGain` / `uTint` bound by name at std140 104/108/112.
- Package/manifest layer (`scripts/luminos-wallpaper-pkg`) and the capability gate
  (`scripts/luminos-wallpaper-capabilities`) were built earlier the same day. The gate **ran on the
  box**: `qsb` present (Qt 6.11.2), `Caelestia.Services` present with no Quickshell dep, kpipewire
  present, Qt Quick 3D present, `cage` present, `/dev/uinput` present, `chromium not mapped`.

### Server / RAM thread (2026-09-18, carried forward — not this chat's work)
- **DECISION 116 — `vm.page-cluster` stays at 3. It already was 3**; the premise that it was 0 came
  from reading a repo file that has never been installed. Pagefile confirmed live (`USED 16.3M`,
  measured readahead utility **75.6 %** vs a 16.8 % break-even). `page-cluster = 4` measures better
  still and is a live candidate, not a recommendation — needs a week's sample, not one burst.
- **BUG-167 filed** — `config/99-luminos-ram.conf` has never been on the box; `swappiness = 30` and
  `vfs_cache_pressure = 50` are **not live**. ⚠️ **Do not blind-install it** — it would set
  `page-cluster = 0` and undo DECISION 116.
- **BUG-164 root-caused** — Roku seek/Skip-Intro resets are **ASS subtitle burn-in**, not audio.
  S01E07 was never the broken episode. 46 files flagged (26 `audio:dts`, 20 `subs:ass`), **none
  fixed** — the DECISION 112 one-file-watched gate has never been satisfied.

## State — what is IN PROGRESS (and exactly where it was left off)
Nothing is half-written. Every file named below is deployed to
`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/` and `diff -rq` clean against the repo.

**Two things are waiting on Shawn, not on code:**
1. **plasmashell has not been restarted since §3.1/§3.2 landed**, so the running wallpaper is still
   the pre-audio build. Nothing is proven on screen yet.
2. **Three commits are unpushed** (`ef200445`, `2c62f8fb`, `9fa3d26b`, plus this session's §3.2
   commit). The remote is SSH and the bridge VM has no SSH.

## Next steps (ordered)
Wallpaper first; the server items below are unchanged and still Shawn's call.

1. **Shawn, on the box — one command per line, no trailing comments** (a pasted `# comment` becomes
   an argument; it already made systemd try to restart `then.service`):
   ```
   qml6 ~/luminos-os/tests/wallpaper/audio_contract.qml ; echo $?
   ```
   ```
   qml6 ~/luminos-os/tests/wallpaper/props_contract.qml ; echo $?
   ```
   ```
   systemctl --user restart plasma-plasmashell
   ```
   ```
   git -C ~/luminos-os push origin main
   ```
   Then Wallpaper settings → **Native QML → Spectrum**, play something, and check the new **Scene
   settings** panel moves the bars. `journalctl --user -b -t plasmashell | grep LUMINOS-WP` should be
   silent.
2. **SPEC §3.4 — runtime shader loader.** Cheapest remaining item and it carries §3.2's deferred half:
   binding arbitrary property keys to arbitrary uniforms needs a `ShaderEffect` built with
   `Qt.createQmlObject`, which is §3.4's machinery anyway. `iAudio` already exists, so Shadertoy audio
   shaders come free.
3. **SPEC §3.3 — packages + gallery + Lively import.** The Python half is already written and tested
   (`scripts/luminos-wallpaper-pkg`: `parse_manifest`, `lively_to_manifest`, `_path_safe`). What is
   missing is the gallery UI and the install path (`~/.local/share/luminos/wallpapers/<id>/`).
4. **SPEC §3.5** `.js` canvas loader (CONTRACTS §6 already specifies the shim), then **§3.6** external
   producer (games) — the big one, and the only thing that lets web mode finally be deleted.
5. **BUG-166 — verify it, then watch it for a day.** Both halves installed 2026-09-18, nothing proven.
   `luminos-tabs` must show a fresh `age_seconds`; `chrome://extensions` must read **3.1**. ⚠️ Saved
   options beat new defaults — check `graceSeconds`=1800 and `capOnPressure` unticked.
6. **BUG-167 — reconcile `config/99-luminos-ram.conf` with the box**, keeping `page-cluster = 3`, then
   sweep **every** `config/*.conf` against its `/etc/` counterpart.
7. **BUG-164 — Shawn's call:** confirm the model (S01E07 seeks fine, S01E09 breaks), then fix the 20
   ASS files by getting Bazarr to fetch real SRT sidecars (`use_embedded_subs` OFF), then run
   `--fix-audio` on ONE of the 26 DTS files and watch it before the rest.

## Key decisions & constraints
- **No Chromium in the wallpaper** — but `qt6-webengine` stays installed (HIVE needs it), and **web
  mode stays until §3.6 replaces it**; deleting it first removes DOM support with nothing behind it.
- **128 audio bands at 0–1** and the eight Lively control types are **Lively-exact on purpose**, so
  their wallpapers port unmodified. Not a taste call.
- **The plugin serves both the desktop containment and the lock screen** (`kscreenlockerrc` Greeter).
  Anything broken is broken twice.
- **Never a black desktop** (SPEC §6): malformed manifest → keep the previous wallpaper; shader fails
  → fall back to the Canvas aurora **and say so in the journal**; no audio provider → zeros, never a
  crash; no `properties.json` → no panel, not an error.
- **Budgets (SPEC §9):** QML scene 150 lines, loader/host 200; Python helper 150, function 40, nesting
  3. Over budget is a red build.
- **A config file in git is NOT evidence that a setting is live** (BUG-167). Read `/proc/sys/`.
- **`vm.page-cluster` = 3 is correct and stays** (DECISION 116). It has been called "wrong" three
  times by people reading a repo file.
- **AGENTS.md §0.2 / Rule 12 / §16:** "no changes" scopes to code, config and system state. This file
  and the §13 doc triggers are written on every turn regardless.

## Gotchas / dead-ends / things NOT to redo
**Repo hygiene**
- **Never `git add -A` in this repo.** An unpacked initramfs (`init`, `lib`, `sbin`, `usr/`, `var/`,
  `kernel/`, `keymap.bin`, `consolefont.psfu`) and `_to_delete/` sit untracked at the root. Stage
  named files only. The §13 git snippet says `-A`; it is wrong here.
- **Git from a Cowork session can CREATE lock files but not DELETE them.** That is the whole
  explanation for a 15-hour-old 0-byte `.git/index.lock` — not a crashed process. Every run also
  leaves `.git/HEAD.lock`, `.git/objects/maintenance.lock` and `.git/objects/*/tmp_obj_*`, and those
  block the *next* commit. Workaround: commit through a private `GIT_INDEX_FILE` (never takes the
  shared lock), then clear the locks and `git reset` (mixed) to rebuild the stale shared index.
- **`.notes.db` writes fail with `disk I/O error` through the bridge mount** and leave a hot journal
  that breaks later reads. Recovery: copy db + journal off the mount, let sqlite roll back on a normal
  filesystem, insert there, truncate the mounted journal to 0 bytes, copy the db back. (`sqlite3` the
  CLI is not in the bridge VM either; python's `sqlite3` module is.)
- **`device_commit_files` can answer `written` before the bytes are visible to `device_bash`.** Always
  md5 the device copy against the container copy before acting on the result.
- **Cowork does not fire Claude Code hooks** (BUG-087), so the code graph never auto-refreshes there —
  call `code-review-graph` MCP explicitly.
- **The `qemu-system-x86` process is Claude Desktop's own Cowork sandbox VM.** Identified 2026-09-18.
  Do not investigate it a third time. Killing it kills the Cowork session.

**Wallpaper**
- **`.qsb` files are not byte-reproducible** — a comment-only change differed in 3439 of 3493 bytes
  because the six shader variants are written unordered inside a compressed container. **Never md5 a
  `.qsb` to decide whether a shader changed; diff `qsb --dump`.** md5 is still right for transfers.
- **Exit code 0 is not the whole result.** The audio test passed 22/22 while the engine was printing
  `Member enabled … overrides a member of the base object`. Read what a run prints.
- **The near-miss question passes for the wrong reason.** `item.x !== undefined` instead of
  `"x" in item` (BUG-168); `cava` on `PATH` instead of in `ldd`; a checker pointed at the path the fix
  had just left (BUG-163). Three times in four days.
- **Caelestia never spawns the `cava` CLI** — it links libcava and reads PipeWire itself.
- **`/dev/uinput` is `root:input 660`** — existence is not access.
- **`pytest`/`hypothesis` are not on the G14.** Installing them is a Python package action and needs
  `luminos-brain safe` first. The suite runs in the build container; only `qml6` tests run on the box.
- **`luminos-brain safe` has produced a false `NO` five times.** Escape hatch:
  `luminos-brain safe "<action>" --reason "<why>"` → `OVERRIDE LOGGED`.

**Media server**
- The server is a separate headless machine: `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`
  (server `.61`, G14 `.16`), `sudo` NOPASSWD. Ground truth for any transcode question is **Jellyfin's
  own ffmpeg command lines** in `/var/log/jellyfin/` — never a capability table.
- `ass` is text but is **not** client-renderable on a Roku, so Jellyfin burns it in.
- "Bazarr says nothing is missing" ≠ "these files are fine" (`use_embedded_subs` is ON).
- The jpn/kor "E07.5 recap mis-map" audio theory (DECISION 98/101) is **disproven**.

## Files touched / relevant files
- **Wallpaper plugin:** `src/wallpapers/org.luminos.livewallpaper/contents/` — `ui/main.qml`,
  `ui/QmlMode.qml`, `ui/WebMode.qml`, `ui/config.qml`, `ui/scene.js`,
  `ui/audio/{AudioBridge,CaelestiaAudio}.qml`, `ui/props/{PropertyStore,PropertyEditor,PropertyControls}.qml`,
  `ui/scenes/{Shader,Aurora,Particles,SysMon,Spectrum}.qml` + `{Shader,Spectrum}.properties.json`,
  `shaders/luminos-shader.frag{,.qsb}`, `config/main.xml`.
- **Installed copy:** `~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/` — keep it
  `diff -rq` clean against the repo.
- **Docs:** `docs/wallpaper/{SPEC,CONTRACTS,BUILD_LOG}.md`, `LUMINOS_DECISIONS.md` (117, 118),
  `docs/BUGS.md` (BUG-168), `LUMINOS_STATUS.md`, `docs/CODE_REFERENCE.md`.
- **Scripts/tests:** `scripts/luminos-wallpaper-{pkg,capabilities,probe}`,
  `tests/wallpaper/{test_pkg.py,test_shipped_props.py,budget_check.py,audio_contract.qml,props_contract.qml}`.
- **Server/RAM thread:** `docs/LUMINOS_RAM_ARCHITECTURE.md`, `server/STATUS.md`, `server/DECISIONS.md`,
  `server/scripts/luminos-roku-compat`, `config/99-luminos-ram.conf` (BUG-167).
