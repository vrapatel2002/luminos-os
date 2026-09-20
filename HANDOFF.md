# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-20 — chat A Response 6 / chat B Response 18 (TWO Cowork chats ran in parallel; see the gaming-OS pointer below)

> **RESET, per §0.2's size tripwire.** The previous copy was **462 lines**, over the ~400 limit,
> stacked with the full wallpaper build history. Recovered with `git show 71fc3a82:HANDOFF.md`.
> History lives in git, `luminos-notes.sh`, `LUMINOS_DECISIONS.md` and `docs/BUGS.md` — this file
> carries only what a newcomer must not re-learn or re-break.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**Shawn asked why he cannot select the gallery wallpapers when I can. He is doing nothing wrong —
two faults, both ours. BUG-185 / DECISION 128.**

1. **The grid never had a selected state.** No highlight, no border, no checkmark, no hover or
   pressed feedback. Clicking a tile set a config key and changed **nothing on screen**, so a
   working gallery looked identical to a broken one; the only feedback in the whole flow was the
   Apply button un-greying, at the far end of the dialog, and it does not move at all if you click
   the wallpaper you already have. Fixed in a new `ui/GalleryTile.qml` (highlight, border, bold
   name + checkmark, hover, press). Which tile is current is passed DOWN from `config.qml`
   (`activeEntry`) — a tile that derived it would be a second copy of the answer.
2. **BUG-171, fourth appearance, and the first time its real cost was visible.** His System
   Settings had been open since **Sat 19:09** — 20 hours, 4 hours older than the `scene.js` that
   taught it about web packages — so `modeForType("web")` returned null and every web tile was
   inert. Worse: when he applied Starfield, the page wrote back **its own stale `cfg_` values**,
   restoring a `WebUrl` from the previous day and undoing the Rain wallpaper. *A Plasma config page
   writes every cfg_ property on Apply, so an old window is not a read-only inconvenience — it is a
   time machine pointed at your config.* New `ui/StaleCheck.qml` compares when the PAGE started to
   when the FILES were last written (`luminos-wallpaper-gallery --plugin-mtime`, a fresh process)
   and raises a `Kirigami.InlineMessage`. No build stamp, no deploy step. Deliberately not
   self-healing. `usePackage()`'s failure now shows in the dialog too, not only the journal.

**What Shawn must still do: fully quit System Settings and reopen it.** Nothing shipped today can
fix the process he already has — that is the whole point of the banner, which only helps next time.

**Two test gaps closed.** `gallery_contract.qml` checked `modeForType` for every type **except
`web`** — the one that broke. Now 12 checks, including the selection contract against real
`GalleryTile` instances. And selftest [5]'s Chromium check was wrong: a mapped library is never
unmapped, so once web mode is selected once, `libQt6WebEngineCore` stays for the life of the
process. It now accuses only when plasmashell started AFTER the config was written.

⚠️ **Selftest is 38/1, and the one failure is correct:** the lock screen still shows Rain while the
desktop is now Starfield, because the stale page reverted the desktop. Left deliberately — the
desktop is mid-experiment and re-syncing would be guessing at what he wants. One command settles it
once he has chosen: `scripts/luminos-wallpaper-lockscreen`.

### The two turns before this one, in one line each (detail: BUG-183/184, DECISION 126/127)
- **BUG-183:** Lively web wallpapers were never a WebGL problem — they *wait to be told what to
  draw* (`livelyPropertyListener` per property on load) and we never called it. `ui/LivelyApi.qml`
  now does; Rain's framebuffer went from mean 0 to 126/255. Their packages are never rewritten.
- **BUG-184:** `/dev/dri/renderD128`, the NVIDIA card's DRM render node, was mode **0666** — a door
  DECISION 25 never covered. Now `root:dgpu 0660`, matched by DRIVER not number, verified denied as
  `shawn` and still open through `dgpu-exec-v2`. Recorded in AGENTS.md §9.
- **DECISION 127:** the lock screen's wallpaper is a script's copy of the desktop's
  (`scripts/luminos-wallpaper-lockscreen`), with four lock-screen overrides; selftest [7] catches
  drift. Verified on screen in `kscreenlocker_greet --testing`.

### Still open on the wallpaper
`livelySystemInformation(json)` and `livelyAudioListener(float[])` are unimplemented; Simple System,
Music TV and Music Tunnel need them. The audio array already exists in `ui/audio/`; the
system-information payload does not — `luminos-monitor stats` carries no RAM, network or hardware
names, and zeroes there would draw empty charts that look like a different bug. **Only Rain is
confirmed rendering.** The other four web packages load with no JS errors but have not been
visually checked.

Standing aim, unchanged: **Lively Wallpaper parity for the KDE live wallpaper, without Chromium.**
**§3.6 (games through a nested compositor) is still the largest unfinished item.**
Docs: `docs/wallpaper/{SPEC,CONTRACTS,BUILD_LOG,VERIFY}.md`.

## Why / motivation
The dGPU question matters because BUG-047's true-0 W gating is the whole reason this laptop idles
cheaply; a card stuck in D0 burns ~1.5 W all day for nothing. The gate question matters because the
answer is *three unrelated mechanisms* that people keep conflating (see below), and conflating them
is how BUG-103, BUG-146 and BUG-160 each got mis-diagnosed at least once.

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

### Separate thread — NEW gaming OS feasibility (Cowork chat B, 2026-09-19/20). READ-ONLY, no overlap.
⚠️ **A second Cowork chat was running in parallel on this repo and this file was reset at 23:49
while that chat was mid-thread.** Nothing was lost — its output is durable in
**`docs/gamemode/FEASIBILITY.md`** (304 lines) and in `luminos-notes.sh search "console"`.
Pointer only, so this file stays short:
- **Shawn is scoping a NEW Arch-based, gaming-only OS for this laptop** — Steam + Proton + games,
  nothing else. It is **not** a Luminos mode, so Luminos-specific findings do not carry to it.
- 🔴 **AGENTS.md §2's "No MUX" was WRONG and is corrected in place.** `supergfxctl -s` →
  `[Integrated, Hybrid, AsusMuxDgpu]`. ⚠️ Before ever switching, check whether §9's
  `KWIN_DRM_DEVICES=/dev/dri/card2` + the Mesa EGL pin strand the desktop — plausible black screen.
  **Cross-ref BUG-182: supergfxd is what starts `nvidia-powerd` on entering Hybrid**, so a mode
  change moves that too.
- 🔴 **SPEC §3.6 IS NO LONGER PACKAGE-BLOCKED** — `xdg-desktop-portal-wlr 0.8.4-1` and
  `gst-plugin-pipewire 1:1.6.8-1` are now **both installed** (with `cage 0.3.1`). Verify before
  trusting any older "BLOCKED ON PACKAGES" note.
- **Hardware ceilings, measured, that no OS changes:** 128-bit LPDDR5 (4 × 32-bit channels) at
  **6400 MT/s configured though rated 7500** = 102.4 GB/s shared; 780M has **2 MB L2 and no
  Infinity Cache**; the 4050 is 96-bit/192 GB/s dedicated with **12 MB L2**, ~11–12 TF FP32 at our
  90 W ceiling. **The PS5-class part in this laptop is the 4050, not the iGPU**, and **6 GB VRAM is
  the hard ceiling.** DRAM speed is set at training time by AGESA — firmware, not kernel.
- Carries to ANY OS on this hardware: **BUG-069** (`nvidia-smi -pl` is a no-op on this mobile part;
  TGP must go via nvidia-powerd + read-back), the MUX, and gamescope's NVIDIA-*hybrid* bugs
  (#498/#611/#1220/#1590/#1643/#1662 — argues MUX first, then gamescope).
- `gamescope` 3.16.28-1 and `gamemode` 1.8.2-3 are in `extra`, **neither installed**. Nothing was
  installed, switched or changed by that chat.

## State — what is DONE

### dGPU investigation — BUG-182, READ-ONLY, closed
The card was awake and idle and it was **not** our daemons. `nvidia-powerd` was EXONERATED: it
holds 11 fds on `/dev/nvidia0` while the card sits in D3cold, so holding a node does not block
fine-grained RTD3 — but its open times move (23:18 → 23:41), making it a candidate *waker*, not a
holder. What pinned the card for ~3 hours is still unknown; `luminos-dgpu-watch` is what answers it
(a `### WOKE` line with a `HOLDER+` names the culprit; without one it is BUG-161's ACPI path).
Ruled out by measurement: `luminos-power` polling, `power/control=on`, persistence mode, the
compositor (all on card2/renderD129), AC/DC transitions, RTD3 config. Full detail in BUG-182.
**Method note worth keeping: a frozen counter dates the END of an event, not its cause.**

### The dGPU "gate" is THREE different mechanisms — stop conflating them
| | What it gates | Mechanism | Lives in |
|---|---|---|---|
| **Access** (DECISION 25) | *who may open* `/dev/nvidia*` | `NVreg_DeviceFileUID/GID/Mode` → `root:dgpu 0660`, group `dgpu` gid 948 **empty on purpose**, `dgpu-exec-v2` setgid door | `/etc/modprobe.d/luminos-dgpu-gate.conf`, `scripts/dgpu-gate/` |
| **UVM patch** (BUG-146/147) | the two nodes the driver params miss | `luminos-uvm-gate` on the PCI `add\|bind` uevent + a oneshot backstop | `scripts/dgpu-gate/luminos-uvm-gate.sh`, `config/udev/71-…` |
| **Power** (BUG-047/103) | whether the card may *sleep* | `DPM=0x02`, `power/control=auto`, Mesa EGL pin + `KWIN_DRM_DEVICES` so nothing renders on it | `/etc/modprobe.d/nvidia-pm.conf`, `/etc/environment` |
- Live verification of the gate's *purpose*: driver params read `DeviceFileUID: 0 / DeviceFileGID:
  948 / DeviceFileMode: 432` (0660 octal). It is **not a security boundary** (DECISION 53) — anything
  running as shawn can type `dgpu-exec-v2`. It stops *accidental* use.
- **The access gate cannot help with power.** An ACPI NVPCF wake (BUG-161) never opens a device node,
  so no fd scan will ever find that culprit — AGENTS.md §12 says so and it held again here.
- `config/udev/70-luminos-dgpu-access.rules` is **dead code** — has never fired; still installed and
  still miscited as "layer 2" by DECISION 90, STATUS.md:185 and `scripts/dgpu-gate/README.md`.

### Wallpaper — verified on the box 2026-09-19, 35/35 selftest
`WallpaperMode=qml QmlScene=spectrum AudioReactive=true ObscurePolicy=2`. Chromium **not** mapped
into plasmashell; `libcava.so` + `libcaelestia-services.so` are. All four eyes-on checks PASS.
SPEC §3.1 audio (DECISION 117) · §3.2 per-scene properties (118) · §3.3 packages + gallery + Lively
import (123, and **BUG-181** — the Lively type map was invented and the test defended the guess) ·
§3.4 runtime shaders (119) · §3.5 .js canvas (122). BUG-168→BUG-181 all fixed.

**Cost, honestly — memory is a rout, CPU is not:** shader scene **6.6 %** of a core / 135 MB PSS;
Spectrum 128 bars **20.3 %** / 143 MB; frozen 0.0 %; Chromium web mode ~24 % / ~810 MB **RSS**.
Never say "far lighter than Chromium" without naming the scene.

## State — what is IN PROGRESS
Nothing half-written. BUG-182 is diagnosed and deliberately unfixed by instruction.

## Next steps (ordered)
0. ✅✅ **BUG-182 FIXED, 2026-09-20 13:16 — DECISION 126. Nothing outstanding.**
   **`nvidia-powerd` holds one kernel runtime-PM reference with NO file descriptor.** Proven both
   directions on the rpm tracepoints: `stop` → `cnt-0` → `rpm_suspend ret=0` → asleep in **7 s**;
   `start` → powerd itself calls `rpm_resume`, count climbs to 3, `rpm_idle` returns `-11` (EAGAIN),
   awake forever. Baseline with powerd up was `usage_count=1, disable_depth=0`.
   **Fix: `systemctl mask nvidia-powerd`. MASKED, not disabled** — supergfxd runs
   `systemctl start nvidia-powerd.service` on entering Hybrid every boot, so `disabled` is silently
   overridden. **This RESTORES existing policy** — `luminos-game-mode:40` and `luminos-train-mode`'s
   `off` path both already say masked-at-idle (BUG-047), and both `unmask + start` on entry, so
   Dynamic Boost is untouched for games and training. It had drifted; the documented drift path is a
   `luminos-train-mode on <pattern>` whose keep-alive matches its own argv and "leaves nvidia-powerd
   unmasked forever" (game-mode:36, verified 2026-08-25).
   **Two guards, both tested:** `luminos-verify` [3] fails on it (SessionStart hook path, so every
   agent session sees the drift); `luminos-dgpu-watch` self-heals after `--autopark` s (default 300)
   when the card is awake, **nothing but powerd** holds a node, and no perf-mode keep-alive runs —
   a real workload always holds a node, so it cannot fire against a live game.
   **Also closed:** `/dev/nvidia-uvm{,-tools}` re-gated to `root:dgpu 660`, all five nodes ✓.
   ⚠️ **`luminos-uvm-gate` exiting 1 after a restart is CORRECT** — it deliberately fails when it had
   to *repair* rather than find the nodes already gated. Do not "fix" that exit code.
   ⚠️ **I was WRONG in amendment 2 when I exonerated nvidia-powerd.** It held fds while the card
   slept, and I read that as innocence. **An open file descriptor and a runtime-PM reference are
   different things.** That conflation cost three passes.
0a. ✅ **BUG-182 root cause detail, 2026-09-20 01:10 — we were auditing the wrong layer.**
   Every earlier check looked for a **process** (fds, `/proc`, `lsof`, `fuser`) and found none, and
   the card still would not sleep. **The reference is inside the kernel, held by the nvidia module,
   and no userspace tool can see it.** Proof — rpm tracepoints filtered to `0000:01:00.0`, 35 s,
   `overrun: 0`, filter verified applied: **ZERO events**, while the AMD card shows dozens per
   second with `usage_count` cycling 5↔6. **Zero is the finding:** a driver refusing would show
   `rpm_suspend` → `rpm_return_int ret=-16`. There is no attempt, because `usage_count` never
   reaches 0. The module took a `pm_runtime_get` on the externally-triggered resume (the `lspci`
   config-space read) and never put it back. `Video Memory: Active` with zero clients is the same
   stuck reference from the driver side.
   ⚠️ **`power/autosuspend_delay_ms` returning `Input/output error` is LOAD-BEARING, not a broken
   node** — the kernel returns EIO there when the driver has not enabled autosuspend, so **no kernel
   timer will ever clean this up**; the nvidia driver alone decides. Earlier passes read it as noise.
   ⚠️ **`CONFIG_PM_ADVANCED_DEBUG is not set`**, so `power/runtime_usage` and `runtime_enabled` do
   not exist on this box. The tracepoints are the ONLY way to see the count — and they only report
   it when an event fires, which is precisely what is not happening.
   Ruled out read-only: parent bridge `00:01.1`, the `01:00.1` audio function (`suspended`, D3hot),
   and every child of the GPU — `drm/card1`, `renderD128`, `controlD65`, `backlight/nvidia_0` all
   read `unsupported`, i.e. they hold no PM reference.
   **Levers, in order:** (a) stop running config-space readers on this box — the only one we fully
   control; (b) the one-query test below, to see if a clean client open/close rebalances the
   reference; (c) a driver bug report, noting 610.57.04 is pinned by DECISION 26.
   **Tracing was enabled and then fully restored** (`tracing_on=0`, `rpm_enable=0`, filters `none`,
   buffer back to default). Re-arm with the recipe in `docs/BUGS.md` BUG-182 amendment 3.
0b. ✅ **BUG-182 WAKER, 2026-09-20 00:47 — the audit unit paid for itself in one hour.**
   `### WOKE` at 23:57:43 with **no `HOLDER+` and no `PROFILE` change**, and the journal names
   `sudo /usr/bin/lspci -vnn -s 65:00.0` on the **exact same second**. `lspci` woke the NVIDIA card
   while being asked about the **AMD** one: `-s` filters what is *printed*, pciutils still
   enumerates the whole bus, and `-v` reads config space — which resumes a D3cold device. No device
   node is opened, so it is invisible to every fd-based check we own. **This was already on file as
   BUG-151** and had been recorded as a note about one command instead of the general rule.
   **Why it then stays awake: nothing is holding it.** 50 min of `slept_since_last=0s`, the only
   holder is `nvidia-powerd` (which holds handles while the card *sleeps*), and `Video Memory:
   Active` with zero clients. The driver was resumed from outside and never re-armed its idle path.
   **Cost in practice:** every hardware-inventory pass pins the card at ~1.5 W for hours — both pins
   this boot followed one (20:29 `nvidia-smi -q`+`dmidecode`, 23:57 `dmesg`+`dmidecode`+`lspci`).
   `lspci`, `lshw`, `inxi`, `hwinfo` and a bare root `nvidia-smi` all do it.
   **The one thing left to test** (cheap, needs Shawn's nod): with the card pinned, run
   `sudo dgpu-exec-v2 -- nvidia-smi --query-gpu=name --format=csv` once and watch whether
   `runtime_suspended_time` starts moving within ~2 min. The previous pin released ~2 min after two
   such queries — **but the 20:29 bare root `nvidia-smi` was also a client cycle and was followed by
   a 3-hour pin, so the rule is NOT established. Do not write it up as one.**
1. **Keep reading `/var/log/luminos/dgpu-watch.log`.** The temporary audit unit
   (DECISION 125) is running and is the next move; it needs hours, not minutes. What to look for:
   a **`### WOKE` with a `HOLDER+` beside it** names the culprit outright; a **`### WOKE` with NO
   `HOLDER+` but a `PROFILE` line** beside it is the BUG-161 ACPI NVPCF path, which holds no
   descriptor and which no fd scan can ever catch; a **`BEAT` line with `slept_since_last=0s`**
   means the pin is back. `nvidia-powerd` re-opening its handles (~23 min apart) will show as a
   `HOLDER-`/`HOLDER+` pair — expected, and interesting only if a `### WOKE` sits next to it.
   **Delete the unit when the question is answered** — command in AGENTS.md §9.
2. **OLD step 1, now superseded and kept only so nobody redoes it —** sampling
   powerd's fds by hand. The watcher does it continuously and better. The
   `systemctl stop nvidia-powerd` A/B is **no longer worth running** — see the exoneration below.
3. **Ask Shawn about the UVM gate re-assert** (`systemctl restart luminos-uvm-gate`). One command,
   but it is a state change and this turn was read-only.
4. **SPEC §3.6 — external producer (games).** Consumer half is built and proven (DECISION 124).
   **Blocker:** `org.freedesktop.impl.portal.ScreenCast.CreateSession` against `xdg-desktop-portal-wlr`
   gives no `Response` signal in 20 s. Probe at `/tmp/sc.py`. cage runs headless on the 780M
   (glxgears 62.8 FPS, picks the iGPU by itself). Producer must publish **packed RGB** (`format=BGRx`)
   or it renders greyscale. **DECISION 124a corrects 124:** input DOES exist — a live headless `cage`
   advertises `zwlr_virtual_pointer_manager_v1` + `zwp_virtual_keyboard_manager_v1`; the earlier
   measurement was taken against KWin, the wrong compositor.
5. **Spectrum on the GPU** — one `ShaderEffect` over the existing 128×1 `AudioTexture`.
   **DECISION 121: capping the publish rate was tried and measured WORSE. Do not redo it.**
6. **BUG-166 / BUG-167** — verify the tab sleeper (`chrome://extensions` must read 3.1), then
   reconcile `config/99-luminos-ram.conf` with the box **keeping `page-cluster = 3`** (DECISION 116).
7. **BUG-164** — 20 ASS files (Bazarr `use_embedded_subs` OFF), then one of the 26 DTS files.

## Key decisions & constraints
- **AGENTS.md §0.2 / Rule 12 / §16: "no changes" scopes to code, config and system state.**
  `HANDOFF.md` and the §13 doc triggers are written on **every** turn, investigation turns included.
- **The dGPU optimisation pass is FLAGGED, NOT NOW** (§14 item 0g). Constraint: the wallpaper must
  use the **AMD 780M, never the RTX 4050** — already satisfied, plasmashell holds `renderD129` only.
- **No Chromium in the wallpaper**, but web mode stays until §3.6 replaces it.
- **A config file in git is NOT evidence that a setting is live** (BUG-167). Read `/proc/sys/`.
- **Never switch to `AsusMuxDgpu`** before checking whether `KWIN_DRM_DEVICES=/dev/dri/card2` +
  the Mesa EGL pin strand the desktop on a card that no longer drives the display. §2 was corrected
  2026-09-19: this board **does** have a MUX.

## Gotchas / dead-ends / things NOT to redo
**Investigating the GPU**
- **Running `nvidia-smi` wakes a sleeping card and resets its autosuspend timer.** That is why
  `dgpuHasClients()` is a `/proc` walk (BUG-160) and why `luminos-monitor`/`luminos-verify` read
  `runtime_status` from sysfs first. Budget yourself **one** `nvidia-smi`, and only on a card that
  is already awake.
- **A ROOT `nvidia-smi` — even a read-only query — re-opens the UVM gate** (BUG-146). Proven again
  this turn by ctime. Use `nvidiaRead()` from the daemon; from a shell, expect to re-assert after.
- **A frozen counter dates the END of an event, not its cause.** `runtime_suspended_time` had not
  moved in hours, and the first pass reached for a cause that was still present — when the thing
  responsible had already stopped. Three samples over eleven minutes is not a sample of a
  three-hour window.
- **`lsof`/`fuser`/`/proc` answer "who has it OPEN". They do not answer "who has a REFERENCE on it."**
  On a runtime-PM device those are different questions with different tools. The rpm tracepoints
  answer the second, and without `CONFIG_PM_ADVANCED_DEBUG` they are the only thing that does.
  Bounce `power/control` on→auto to force an event and make `usage_count` visible.
- **`nvidia-powerd` must stay MASKED at idle** (DECISION 126). `disabled` is not enough — supergfxd
  starts it every boot into Hybrid. If the dGPU ever stops sleeping, check this FIRST.
- **When every tool you own says "nothing there", the absence IS the signal — go one layer down.**
  Four passes hunted for a process holding the dGPU and found none; twice that absence was turned
  into a wrong-but-plausible conclusion. The answer was three sysfs reads and a 35 s trace, and it
  took less time than any of the failed passes. **Zero events is data. Read it as data.**
- **`lspci` wakes the dGPU — even when you point it at the other card.** `-s` filters output, not
  the bus scan, and `-v` reads config space, which resumes a D3cold device. So do `lshw`, `inxi`,
  `hwinfo` and a bare root `nvidia-smi`. **A hardware-inventory pass costs ~1.5 W for hours.** Was
  already known as BUG-151 about one command and never generalised — that is why it cost two pins.
- **A wake with no holder is not a mystery, it is a category.** Holderless wake + a `PROFILE` line =
  ACPI NVPCF (BUG-161). Holderless wake + nothing = a config-space reader. Check `journalctl` for
  that exact second before theorising.
- **Holding `/dev/nvidia0` does NOT keep the card awake.** Proven: powerd held 11 fds while the card
  sat in D3cold. "Who holds it" and "what wakes it" are different questions — check the **fd open
  time**, not just the holder list.
- **Runtime PM gives cumulative counters and NO last-transition timestamp.** You cannot derive when
  a card woke by subtracting `runtime_active_time` from now — that assumes one contiguous block,
  which is the thing you are testing. Two spaced samples prove *currently awake*, nothing more.
- **`/proc/PID/fd` timestamps ARE real open-times here** (verified: re-listed twice, unchanged, and
  low fds keep their boot time). Good enough to date when a holder grabbed the device.
- `power/autosuspend_delay_ms` returns **`Input/output error`** on this device; `runtime_usage` does
  not exist on this kernel. Do not read those two as evidence of anything.
- **Delegating to a subagent: say `host-shell__run_command`, in those words.** A subagent told
  "use device_bash" investigated the Cowork VM and reported `Ubuntu 22.04`, virtio devices and zero
  nvidia modules — a completely coherent report about the wrong machine.

**The instruments have been wrong repeatedly — assume they are before assuming the feature is**
- **BUG-171 — a deploy is not a load.** `QQmlEngine` caches components by URL for the life of the
  engine; plasmashell is one long-lived engine. **Restart plasmashell after every deploy.** The
  settings page runs in `systemsettings`, so restart that separately after a `config.qml` change.
- **BUG-177 — a measurement taken in a state the feature never occupies is not a measurement.**
  `luminos-wallpaper-cost` from a terminal samples a wallpaper the terminal has frozen.
- **BUG-172 / BUG-175 — a warning that cannot tell "off on purpose" or "not finished yet" from
  "broken" is noise.** Three cry-wolf checkers in one week.
- **`grabToImage` returns a BLANK frame for anything the GPU composites** — black for `ShaderEffect`,
  white for `PipeWireSourceItem`. Capture the real window with `spectacle -a -b -n` instead.
- **A screenshot proves the first frame rendered and nothing else.** When the feature is motion,
  count frames (`CanvasJs.frames`).
- **Qt sends `console.log` to the journal when stderr is not a tty** — `QT_FORCE_STDERR_LOGGING=1`,
  or your contract tests are mute and exit code is all you have.
- **A `.js` canvas is expensive here (41.1 %) and a shader is cheap (6.6 %)** — Qt rasterises Canvas
  2D on the CPU. Resolution cap and render target both did NOTHING; frame rate is the only lever.

**Repo hygiene**
- **Never `git add -A` in this repo** — commit `022faa74` swept ~20 unrelated files into a wallpaper
  commit that way. **Name paths. A directory path is not a named path.** The §13 git snippet says
  `-A`; it is wrong here. An unpacked initramfs and `_to_delete/` sit untracked at the root.
- **Git from the bridge VM can CREATE lock files but not DELETE them** (a 15-hour `.git/index.lock`),
  and `.notes.db` writes fail there with `disk I/O error`. **Use the host shell.**
- **Cowork does not fire Claude Code hooks** (BUG-087) — call `code-review-graph` MCP explicitly.
- **`qemu-system-x86` is Claude Desktop's own Cowork sandbox VM.** Identified 2026-09-18. Do not
  investigate it again. Killing it kills the session.
- **`luminos-brain safe` has produced a false NO five times.** Escape hatch:
  `luminos-brain safe "<action>" --reason "<why>"` → `OVERRIDE LOGGED`.

**Media server** — separate machine, `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`. Ground truth
for any transcode question is Jellyfin's own ffmpeg command lines in `/var/log/jellyfin/`.

## Files touched / relevant files
**Latest turn (2026-09-20):** `scripts/luminos-dgpu-watch` (HOLDER~ re-open detection — arrivals
keyed on `pid:node` alone made powerd's 00:07:39 re-open invisible; lspci trap documented in the
header), `docs/BUGS.md` (BUG-182 amendment 2), `LUMINOS_STATUS.md`, `HANDOFF.md`.
**Previous turn:** `scripts/luminos-dgpu-watch` (extended — powerd filter removed, `--once`, holder
identity + fd open time, `HOLDER-` on release, `PROFILE`/`BEAT` lines), new
`systemd/luminos-dgpu-watch.service`, `docs/BUGS.md` (**BUG-182** + amendment),
`LUMINOS_DECISIONS.md` (**DECISION 125**), `AGENTS.md` §9 row, `LUMINOS_STATUS.md`, `HANDOFF.md`.
**System state changed (Shawn asked for it):** `/usr/local/bin/luminos-dgpu-watch` installed and
`/etc/systemd/system/luminos-dgpu-watch.service` enabled + started — **TEMPORARY, delete when
BUG-182 is answered.** Backup of the pre-edit script: `/tmp/dgpu-watch.bak` (and git).
**Evidence sources, for re-running the investigation:** `/sys/bus/pci/devices/0000:01:00.0/power/*`,
`/proc/driver/nvidia/{params,gpus/0000:01:00.0/power}`, `/proc/$(pgrep -x nvidia-powerd)/fd`,
`journalctl -b -u {supergfxd,nvidia-powerd,luminos-power}`.
**Gate code:** `config/modprobe.d/luminos-dgpu-gate.conf`, `scripts/dgpu-gate/{dgpu-exec-v2.c,
luminos-uvm-gate.sh,install-dgpu-gate.sh}`, `config/udev/71-luminos-uvm-gate.rules`,
`systemd/luminos-uvm-gate.service`, `cmd/luminos-power/main.go` (`dgpuHasClients` 1594,
`dgpuRuntimeSuspended` 1578, `nvidiaRead` 1692, `regateUVM` 1730, `setProfile` 1340).
**Wallpaper:** `src/wallpapers/org.luminos.livewallpaper/contents/` + installed copy at
`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/` — keep `diff -rq` clean.

---

## Desktop RAM audit — 2026-09-19/20 (appended by a SECOND Cowork chat; see §0.1)
> ⚠️ **Counter canary, recorded not fixed.** This file's header says *Response 1*; the chat that
> wrote this section is at **Response 11** (BUG-166 / DECISION 115 — tab sleeper + pagefile). Two
> chats, one file. Appended, never an overwrite. **Condensed on 2026-09-20 because appending pushed
> the file to 420 lines, past §0.2's tripwire — the detail is in `luminos-notes.sh search AUDIT`.**

**Read-only measurement. Nothing was changed.** Shawn's PSS table named `baloo_file` at 978 MB and a
"shell layer" of 1577 MB. Both are wrong in the same way:

- **PSS counts file-backed pages.** `baloo_file` = **138 MB anon** + 786 MB cache (the 3.0 GB index,
  mmapped read-only, dropped for free under pressure). **`Pss_Anon` is the number that answers "is
  this eating my RAM".** A report that does not split anon vs file chases the wrong process.
- Real anon: **qs 292 MB** (the actual heavyweight) · **kwin_wayland ~250 MB** · plasmashell 71 MB ·
  krunner 65 MB · kded6 20 MB. **Shell layer ≈ 730 MB real, not 1577 MB.**
- **kwin was missing from the original report** — `pgrep` matched only `kwin_wayland_wrapper`, a
  0 MB launcher. Always check the child.
- **baloo's real cost is the SSD, not RAM:** 22.44 GB written by 25.7 h uptime, **steady state
  ~362 MB/h (~8.7 GB/day)**. (An earlier "1.7 GB/h" in this file was front-loaded by the first
  index — do not quote it.) The parent shows 6.7 s CPU because `baloo_file_extractor` children do
  the work and exit, so **a CPU check alone says "idle" and is wrong.**
- **99.3% of the index is file CONTENT**; filename terms are 4.87 MB. `contentIndexing false`
  takes it 3.0 GB → ~20 MB and keeps filename search.
- **baloo cannot be uninstalled** — *Required By: baloo-widgets, dolphin, plasma-desktop*. Disable,
  never remove.
- **krunner is D-Bus activated** (`org.kde.krunner.service` → `plasma-krunner.service`), nothing
  autostarts it, nothing in `kglobalshortcutsrc` binds it. **Stopping it is safe; it comes back on
  demand.**
- **RAM is not the current problem:** 4.6 GB available, zram 1.4/8 G, pagefile 0 B used.
- ⚠️ **`systemd/luminos-pagefile.service` is still UNTRACKED in git** while the installed copy at
  `/etc/systemd/system/` is live — same class as `luminos-hive.service` in BUG-148. Commit it.
