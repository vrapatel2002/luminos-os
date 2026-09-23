# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-23 — Response 1 (new chat; session-start read-only turn — NOTHING changed; content below is from 2026-09-21 and still current for Luminos. Vela state lives in gameos/HANDOFF.md, updated 2026-09-22.)

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**NEW IDEA ON THE TABLE (Shawn, 2026-09-21): make the wallpaper the launcher.** Starfield's stars
become clickable app icons; no separate launcher. This turn was **read-only** — the idea was
assessed against the code on the box. Verdict: **possible, and the graphics half is easy. The
input half is the whole risk.**

### What was established this turn, by reading the live code (not assumed)
1. **The desktop containment eats left clicks on empty desktop.** `~/.config/plasma-org.kde.plasma.desktop-appletsrc`
   `[Containments][30] plugin=org.kde.plasma.folder` — Folder View. That package instantiates
   `FolderView.qml`'s `MouseEventListener`, `anchors.fill: parent`,
   `acceptedButtons: … Qt.LeftButton` **even with `hoveredItem === null`** (FolderView.qml:243),
   enabled whenever not in edit mode. It sits **above** the `WallpaperItem`. Rubber-band selection
   is what it is for.
2. **Therefore `WebInteractive` is SUSPECT, not proven.** It is `true` in the live config right now,
   and `docs/wallpaper/SPEC.md` §0 asserts "the wallpaper already captures mouse events today —
   that is exactly what `WebInteractive` does". **Nothing has ever verified a click reaching the
   page on this desktop.** Same shape as BUG-173 / BUG-185: a feature defended by a test that never
   exercised it. **Do not build on WebInteractive until a click is observed.** Not filed as a bug
   yet — it is unproven in both directions.
3. **The escape hatch is in Shawn's own idea.** `main.qml:429` `FolderViewLayerLoader` is
   `active: root.isFolder ? … : false` and `isFolder` is `Plasmoid.pluginName === "org.kde.plasma.folder"`
   (main.qml:53). Switch the containment to the plain **Desktop** containment
   (`org.kde.plasma.desktop`) and that entire layer — and its click grab — is **never created**.
   "No launcher, no desktop icons, the wallpaper IS the launcher" is exactly that configuration.
   Cost: desktop icons go (he has one, `worldline.desktop`) and rubber-band selection goes.
   BUG-163's desktop-indent overlay becomes moot in that configuration.
4. **Do NOT bolt icons onto today's Starfield.** It is the `.js` Canvas path
   (`QmlScene=~/.local/share/luminos/wallpapers/starfield/wallpaper.js`), which BUG-178 measured at
   **41.1 % of a core** because Qt 6 rasterises Canvas 2D on the CPU. Canvas also has no
   hit-testing and cannot draw themed icons. The right move is a **native `scenes/Starfield.qml`**:
   far field as a `ShaderEffect` (6.6 % measured for the shader scene), and ~15–30 "app stars" as
   real QML `Item`s with `Kirigami.Icon` + `TapHandler`. Real items give hit-testing for free and
   composite on the 780M, which §14 item 0g already verified plasmashell holds (renderD129 only).
   This is likely **cheaper** than the 41.1 % it replaces, not more expensive.
5. **App list + launching already exists on the box:** `org.kde.plasma.private.kicker`
   (`/usr/lib/qt6/qml/org/kde/plasma/private/kicker/libkickerplugin.so`) — `RootModel`/`AppsModel`
   give name + icon + a `trigger()` that launches through KIO. No parsing of the 279 `.desktop`
   files, no shelling out. ⚠️ It is a **private** import: a Plasma upgrade can break it, which is
   exactly DECISION 26 rung L3 exposure (§14 0f). Fallback: `kstart --application <id>` through the
   existing P5Support `executable` DataSource.
6. **Two UX traps that decide whether the feature survives contact.** (a) **Accidental launches** —
   a desktop full of click targets means a stray click opens an app. The icons must be *armed*, not
   always live; `KWindowSystem.showingDesktop` is already read by `main.qml` (BUG-176) and is the
   natural arming signal, Meta+D being the deliberate "I am looking at my wallpaper" gesture.
   (b) **Keyboard** — type-to-search is what makes a launcher a launcher, and SPEC §0 constraint 2
   says the containment does not take keyboard focus. That is the genuinely hard half. v1 is
   click-only. If keys are ever grabbed, **Esc always releases** (SPEC §0).
7. **SECURITY — the lock screen runs the same plugin** (DECISION 77/127). A launcher wallpaper in
   front of a locked session is a hole. DECISION 127 already withholds `WebInteractive` and
   `InjectSystemStats` from the greeter; any launcher key must join that withheld list and
   selftest **[7]** must assert it.
8. **Option B, if the containment fights us:** a Quickshell layer-shell window on the *background*
   layer. Caelestia is Quickshell and already runs on both the KWin and Plasma sessions
   (DECISION 63/68), layer-shell gets real clicks and `keyboardFocus: OnDemand` — it is designed
   for this. Cost: it *becomes* the wallpaper, so audio reactivity, ObscurePolicy and PauseOnBattery
   would be bypassed or re-plumbed. Only if option A's probe fails.

### The next action is a PROBE, and it needs Shawn's nod (it is a state change)
~25-line scene with a `TapHandler` that logs to the journal and shows a visible marker; set as
`QmlScene`; observe a click (a) under the current Folder View containment, (b) under the plain
Desktop containment. Revert is one `kwriteconfig6`. **Restart plasmashell after deploying** —
BUG-171: a deploy is not a load.

### Standing wallpaper aim, unchanged
**Lively Wallpaper parity for the KDE live wallpaper, without Chromium.** §3.6 (games through a
nested compositor) is still the largest unfinished item. Previous turn's work (BUG-186 /
DECISION 129) left the Wallpaper settings page as **one file picker** — `Scene.modeForFile()` reads
the extension, the Type combo is gone, everything else is behind **Advanced options**; and
`tests/wallpaper/config_contract.qml` (20 checks) now actually *loads* that page and asserts
`Loader.Ready` first, because 39 checks passed while the page rendered blank.
Still open on the wallpaper: `livelySystemInformation(json)` and `livelyAudioListener(float[])` are
unimplemented (Simple System, Music TV, Music Tunnel need them); **only Rain is confirmed
rendering** of the five web packages. Lock screen still shows Rain while the desktop is Starfield —
selftest's 1 failure, and it is correct; Shawn chooses, then `scripts/luminos-wallpaper-lockscreen`.
Docs: `docs/wallpaper/{SPEC,CONTRACTS,BUILD_LOG,VERIFY}.md`.

## Why / motivation
The dGPU rules matter because BUG-047's true-0 W gating is the whole reason this laptop idles
cheaply; a card stuck in D0 burns ~1.5 W all day for nothing. Anything the wallpaper draws must stay
on the **AMD 780M, never the RTX 4050** — already satisfied, plasmashell holds `renderD129` only.

## ⚡ READ THIS FIRST — two shells, and only one of them is the G14
- `mcp__remote-devices__host-shell__run_command` **is the G14**, as shawn. `sudo -n` is passwordless.
  **Do not hand the user commands to paste — run them.**
- It starts with **no session environment**. Anything touching the session needs
  `export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`;
  every `qml6` call needs `QT_QPA_PLATFORM=offscreen`; `spectacle` needs `WAYLAND_DISPLAY=wayland-0`
  or it **core-dumps**. Without the first, `systemctl --user restart …` **exits 0 and does nothing**.
- **Each call must finish well under 60 s.** A 60 s watch loop is killed as "device did not respond".
  Backgrounding does not survive the call. Split long observations across calls.
- `device_bash` is a **different machine** (the Cowork VM, uid 1004). It sees the same connected
  folders; it does **not** see the desktop session, the real `/dev`, systemd, or the GPU.
  **A subagent told to "use device_bash" will silently investigate the wrong computer.**

### Gaming OS (Vela) — MOVED OUT, pointer only
Own git repo at **`gameos/`** (parent `.gitignore`s it) with its own handoff: **`gameos/HANDOFF.md`**.
Nothing about it belongs in this file. **Installed on this disk since 2026-09-20 — DECISION 130**:
`/vela.img` (32 G ext4, `LABEL=VELA`), `/boot/vela/`, one menuentry in `/boot/grub/custom.cfg`.
**Luminos itself is unchanged** (no `/etc` edit, no service, no package; `grub.cfg` mtime still
2026-08-30 01:01, `GRUB_DEFAULT` still `0`, `luminos-verify` PASS). Undo:
`gameos/os/install/vela-uninstall.sh`. **Boots and displays since 2026-09-21 (DECISION 131):**
gamescope on eDP-2 at 2880x1800@120 on the 780M, Vela Home (Go + Ebitengine) rendering at native
resolution, controller-correct prompts, and a power menu whose "Exit to Luminos" writes GRUB's
`next_entry` — one-shot, stock mechanism, nothing on the Luminos side changed.
Test it in QEMU from here: `gameos/os/scripts/vela-vm.sh` (~40 s, `-snapshot`).
⚠️ **NEVER `pkill -f` anything qemu-shaped on this box** — Claude Desktop's Cowork sandbox is a
`qemu-system-x86_64` too, and killing it ends the session. Use `gameos/os/scripts/vela-vm-kill.sh`.
⚠️ **Never `export` a per-application variable from a session script** — `export` reaches every
child. Exporting `__NV_PRIME_RENDER_OFFLOAD=1` for *games* put the *front end* on the dGPU, and
amdgpu will not scan out a buffer imported from another GPU. Nine boots of black screen with every
check green. `gameos/os/docs/BOOT-10.md`.
⚠️ **`set -euo pipefail` + a noisy-but-fine command kills the whole script.** `$(lspci -nn | awk …)`
returns *lspci's* status, and lspci exits non-zero when it cannot read one device label.
**This shape has not been audited across this repo's scripts.** `gameos/os/tests/session-env.sh`.
⚠️ **`NetworkManager-wait-online` does not wait for connectivity**, and **a route is not the
internet** (that cost five boots: default route present, `/etc/resolv.conf` a real file with no
nameserver, NM's `rc-manager=symlink` refusing to clobber it). **Resolve a name before believing
`ping 1.1.1.1`, `ip route get` or `nmcli`.**
⚠️ **`pacstrap` inherits the host `/etc/pacman.conf`** — DECISION 26's `IgnorePkg` pin propagates
into any `--root` install and silently skips the kernel and the whole NVIDIA stack.
⚠️ **`chown`/`chgrp` clear setuid/setgid bits even when ownership does not change** (BOOT-03; it
disarmed all 20 setuid binaries in the image). Repair from pacman's own mtree.
**Rule about THIS installation: nothing from that project is installed or configured on Luminos.**
In particular **never run `swapoff -a`** — `/swapfile.luminos` is owned by
`/usr/local/bin/luminos-pagefile`, not `/etc/fstab`, so it does not come back on reboot.
Full rule: `gameos/docs/gamemode/RULE-HANDS-OFF-LUMINOS.md`.

## State — what is DONE

### dGPU — BUG-182 FIXED 2026-09-20, DECISION 126. Nothing outstanding.
**`nvidia-powerd` holds one kernel runtime-PM reference with NO file descriptor**, so `usage_count`
never reaches 0 and the kernel never even *attempts* a suspend. Proven both directions on the rpm
tracepoints: `stop` → `cnt-0` → `rpm_suspend ret=0` → asleep in **7 s**; `start` → powerd calls
`rpm_resume`, count climbs to 3, `rpm_idle` returns `-11`, awake forever.
**Fix: `systemctl mask nvidia-powerd`. MASKED, not disabled** — supergfxd starts it on entering
Hybrid every boot, so `disabled` is silently overridden. This **restores** existing policy
(`luminos-game-mode:40`, `luminos-train-mode`'s `off` path), so Dynamic Boost is untouched for games
and training. Two guards, both tested: `luminos-verify` [3] fails on drift (SessionStart hook, so
every agent session sees it), and `luminos-dgpu-watch` re-masks after `--autopark` s.
⚠️ **An open file descriptor and a runtime-PM reference are different things** — conflating them
exonerated powerd wrongly and cost three passes.
⚠️ `power/autosuspend_delay_ms` returning `Input/output error` is **load-bearing** (the driver has
not enabled autosuspend, so no kernel timer will ever clean this up); `CONFIG_PM_ADVANCED_DEBUG is
not set`, so `runtime_usage`/`runtime_enabled` do not exist here and the **tracepoints are the only
way to see the count**.
⚠️ **`luminos-uvm-gate` exiting 1 after a restart is CORRECT** — it fails deliberately when it had
to *repair* rather than find the nodes already gated. Do not "fix" that exit code.

### The dGPU "gate" is THREE different mechanisms — stop conflating them
| | What it gates | Mechanism | Lives in |
|---|---|---|---|
| **Access** (DECISION 25) | *who may open* `/dev/nvidia*` | `NVreg_DeviceFileUID/GID/Mode` → `root:dgpu 0660`, group `dgpu` gid 948 **empty on purpose**, `dgpu-exec-v2` setgid door | `/etc/modprobe.d/luminos-dgpu-gate.conf`, `scripts/dgpu-gate/` |
| **UVM patch** (BUG-146/147) | the two nodes the driver params miss | `luminos-uvm-gate` on the PCI `add\|bind` uevent + a oneshot backstop | `scripts/dgpu-gate/luminos-uvm-gate.sh`, `config/udev/71-…` |
| **Power** (BUG-047/103) | whether the card may *sleep* | `DPM=0x02`, `power/control=auto`, Mesa EGL pin + `KWIN_DRM_DEVICES` so nothing renders on it | `/etc/modprobe.d/nvidia-pm.conf`, `/etc/environment` |
It is **not a security boundary** (DECISION 53) — anything running as shawn can type `dgpu-exec-v2`.
It stops *accidental* use. **The access gate cannot help with power**: an ACPI NVPCF wake (BUG-161)
never opens a device node, so no fd scan will ever find that culprit.
`config/udev/70-luminos-dgpu-access.rules` is **dead code** — never fired; still miscited as
"layer 2" by DECISION 90, STATUS.md:185 and `scripts/dgpu-gate/README.md`.

### Wallpaper — verified on the box, selftest 39 passed / 1 failed (the lock-screen mismatch)
Live: `WallpaperMode=qml`, `QmlScene=…/starfield/wallpaper.js`, `AudioReactive=true`,
`ObscurePolicy=2`, `PauseOnBattery=true`, `WebInteractive=true` (see the SUSPECT note above).
Chromium **not** mapped into plasmashell in this mode; `libcava.so` + `libcaelestia-services.so` are.
SPEC §3.1 audio (DECISION 117) · §3.2 per-scene properties (118) · §3.3 packages + gallery + Lively
import (123, **BUG-181** — the Lively type map was invented and the test defended the guess) ·
§3.4 runtime shaders (119) · §3.5 `.js` canvas (122) · §3.6 consumer half proven (124/124a).
**BUG-183:** Lively web wallpapers *wait to be told what to draw* (`livelyPropertyListener` per
property on load) and we never called it; `ui/LivelyApi.qml` now does.
**BUG-184:** `/dev/dri/renderD128` was mode **0666** — now `root:dgpu 0660`, matched by **DRIVER not
number**, recorded in AGENTS.md §9.
**Cost, honestly — memory is a rout, CPU is not:** shader scene **6.6 %** of a core / 135 MB PSS;
Spectrum 128 bars **20.3 %** / 143 MB; `.js` canvas **41.1 %**; frozen 0.0 %; Chromium web mode
~24 % / ~810 MB RSS. Never say "far lighter than Chromium" without naming the scene.

## State — what is IN PROGRESS
Nothing half-written. The launcher-wallpaper idea is assessed, not started; it is waiting on the
probe above and on Shawn's answer about losing desktop icons.

## Next steps (ordered)
1. **Probe: does a left click reach the `WallpaperItem`?** Folder View vs plain Desktop containment.
   Needs Shawn's nod (state change). This single answer decides option A vs option B above.
2. **If yes → `scenes/Starfield.qml`** (ShaderEffect far field + real `Item` app stars). Replaces the
   41.1 % `.js` path. Measure before/after with `luminos-wallpaper-cost` — ⚠️ **never from a
   terminal** (BUG-177: that samples a wallpaper the terminal has frozen).
3. **Then icons via `org.kde.plasma.private.kicker` `RootModel`**, with the `kstart` fallback and a
   `luminos-verify` check that fails loudly if the private import stops resolving (§14 0f).
4. **Then arming** on `KWindowSystem.showingDesktop`, and the greeter withhold + selftest [7] assert.
5. **SPEC §3.6 — external producer (games).** Consumer half proven (DECISION 124). **Blocker:**
   `org.freedesktop.impl.portal.ScreenCast.CreateSession` against `xdg-desktop-portal-wlr` gives no
   `Response` signal in 20 s. Probe at `/tmp/sc.py`. Producer must publish **packed RGB**
   (`format=BGRx`) or it renders greyscale. DECISION 124a corrects 124: input DOES exist — a live
   headless `cage` advertises `zwlr_virtual_pointer_manager_v1` + `zwp_virtual_keyboard_manager_v1`.
6. **Spectrum on the GPU** — one `ShaderEffect` over the existing 128×1 `AudioTexture`.
   **DECISION 121: capping the publish rate was tried and measured WORSE. Do not redo it.**
7. **BUG-166 / BUG-167** — verify the tab sleeper (`chrome://extensions` must read 3.1), then
   reconcile `config/99-luminos-ram.conf` with the box **keeping `page-cluster = 3`** (DECISION 116).
8. **BUG-164** — 20 ASS files (Bazarr `use_embedded_subs` OFF), then one of the 26 DTS files.
9. **Ask Shawn about the UVM gate re-assert** (`systemctl restart luminos-uvm-gate`) — one command,
   but it is a state change.

## Key decisions & constraints
- **AGENTS.md §0.2 / Rule 12 / §16: "no changes" scopes to code, config and system state.**
  `HANDOFF.md` and the §13 doc triggers are written on **every** turn, investigation turns included.
- **The dGPU optimisation pass is FLAGGED, NOT NOW** (§14 0g). The wallpaper must use the **AMD
  780M, never the RTX 4050** — already satisfied. Nothing is optimised before §3.3 and §3.6 exist.
- **No Chromium in the wallpaper**, but web mode stays until §3.6 replaces it.
- **A config file in git is NOT evidence that a setting is live** (BUG-167). Read `/proc/sys/`.
  Corollary found this turn: **a config key being `true` is not evidence the feature does anything.**
- **Never switch to `AsusMuxDgpu`** before checking whether `KWIN_DRM_DEVICES=/dev/dri/card2` + the
  Mesa EGL pin strand the desktop on a card that no longer drives the display. This board **does**
  have a MUX (§2 corrected 2026-09-19).

## Gotchas / dead-ends / things NOT to redo
**Investigating the GPU**
- **`lspci` wakes the dGPU — even pointed at the other card.** `-s` filters output, not the bus
  scan, and `-v` reads config space, which resumes a D3cold device. So do `lshw`, `inxi`, `hwinfo`
  and a bare root `nvidia-smi`. **A hardware-inventory pass costs ~1.5 W for hours** (BUG-151,
  known about one command and never generalised — that is why it cost two pins).
- **A ROOT `nvidia-smi` — even a read-only query — re-opens the UVM gate** (BUG-146). Use
  `nvidiaRead()` from the daemon; from a shell, expect to re-assert after.
- **`lsof`/`fuser`/`/proc` answer "who has it OPEN", not "who has a REFERENCE on it."** Different
  questions, different tools. Bounce `power/control` on→auto to force an event.
- **A frozen counter dates the END of an event, not its cause.** Runtime PM gives cumulative
  counters and **no** last-transition timestamp.
- **A wake with no holder is a category, not a mystery.** Holderless + a `PROFILE` line = ACPI NVPCF
  (BUG-161). Holderless + nothing = a config-space reader. Check `journalctl` for that exact second.
- **When every tool says "nothing there", the absence IS the signal — go one layer down.**
  Zero events is data.
- **`nvidia-powerd` must stay MASKED at idle.** If the dGPU ever stops sleeping, check this FIRST.

**The instruments have been wrong repeatedly — assume they are before assuming the feature is**
- **BUG-171 — a deploy is not a load.** `QQmlEngine` caches components by URL for the life of the
  engine. **Restart plasmashell after every deploy**; the settings page runs in `systemsettings`, so
  restart that separately after a `config.qml` change.
- **BUG-185/186 — QML is JavaScript.** C-style implicit string concatenation (`"a"\n"b"`) is a parse
  error, Qt then loads **none** of the file, and the page renders blank. 39 tests passed while it
  was blank because nothing in the suite had ever loaded `config.qml`. **A test that never opens the
  file the user opens is not a test.**
- **BUG-177 — a measurement taken in a state the feature never occupies is not a measurement.**
- **BUG-172/175 — a warning that cannot tell "off on purpose" from "broken" is noise.**
- **`grabToImage` returns a BLANK frame for anything the GPU composites** — black for
  `ShaderEffect`, white for `PipeWireSourceItem`. Capture the real window: `spectacle -a -b -n`.
- **A screenshot proves the first frame rendered and nothing else.** When the feature is motion,
  count frames (`CanvasJs.frames`).
- **Qt sends `console.log` to the journal when stderr is not a tty** — `QT_FORCE_STDERR_LOGGING=1`,
  or your contract tests are mute and the exit code is all you have.

**Repo hygiene**
- **Never `git add -A` in this repo** — `022faa74` swept ~20 unrelated files into a wallpaper commit
  that way. **Name paths. A directory path is not a named path.** The §13 git snippet says `-A`; it
  is wrong here.
- **Git from the bridge VM can CREATE lock files but not DELETE them** (a 15-hour `.git/index.lock`),
  and `.notes.db` writes fail there with `disk I/O error`. **Use the host shell.**
- **Cowork does not fire Claude Code hooks** (BUG-087) — call `code-review-graph` MCP explicitly.
- **`luminos-brain safe` has produced a false NO five times.** Escape hatch:
  `luminos-brain safe "<action>" --reason "<why>"` → `OVERRIDE LOGGED`.

**Media server** — separate machine, `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`. Ground truth
for any transcode question is Jellyfin's own ffmpeg command lines in `/var/log/jellyfin/`.

## Files touched / relevant files
**This turn: NOTHING changed** (read-only feasibility assessment). Files *read*:
`AGENTS.md`, `HANDOFF.md`, `docs/wallpaper/SPEC.md`,
`src/wallpapers/org.luminos.livewallpaper/contents/ui/{main.qml,WebMode.qml,QmlMode.qml}`,
`~/.config/plasma-org.kde.plasma.desktop-appletsrc`,
`/usr/share/plasma/plasmoids/org.kde.desktopcontainment/contents/ui/{main.qml,FolderView.qml}`,
`/usr/lib/qt6/qml/org/kde/plasma/private/kicker/`.
**Written this turn:** `HANDOFF.md` (this file) + `luminos-notes.sh` + `luminos-brain log` only.
**Relevant for the next turn:** `src/wallpapers/org.luminos.livewallpaper/contents/ui/scenes/`
(where `Starfield.qml` would go), `~/.local/share/luminos/wallpapers/starfield/wallpaper.js`
(the current 41.1 % implementation), `tests/wallpaper/` (the contract harness a new scene must join).
