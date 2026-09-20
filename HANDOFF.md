# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-19 — Response 1 (new Cowork chat; counter legitimately restarts, §0.1)

> **RESET, per §0.2's size tripwire.** The previous copy was **462 lines**, over the ~400 limit,
> stacked with the full wallpaper build history. Recovered with `git show 71fc3a82:HANDOFF.md`.
> History lives in git, `luminos-notes.sh`, `LUMINOS_DECISIONS.md` and `docs/BUGS.md` — this file
> carries only what a newcomer must not re-learn or re-break.

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**This turn: read-only dGPU investigation.** Shawn: *"find out why is/was the NVIDIA gpu on — do not
turn it off just find out why its behaving such a way, and why our code that gate keeps the NVIDIA
dgpu."* Answered in **BUG-182** (new) plus the gate map below. **Nothing was changed.**

Standing aim before that, unchanged and still the main thread: **Lively Wallpaper parity for the KDE
live wallpaper, without Chromium.** Five of six SPEC §3 items done, box reports 35/35 on
`luminos-wallpaper-selftest`. **§3.6 (games through a nested compositor) is all that is left.**
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

## State — what is DONE

### dGPU investigation — BUG-182, filed this turn, READ-ONLY
**The card is awake and idle, and it is not our daemons doing it.**
- `control=auto`, `runtime_status=active`, `power_state=D0`, `d3cold_allowed=1`; three samples over
  11 min → `d_suspended = 0 ms` every time. P8 / 210 MHz / **1.54 W** / 2 MiB / 0 % util.
- This boot: **6h22m active / 3h33m suspended** — it *was* cycling and then stopped.
- `/proc/driver/nvidia/gpus/…/power` → `Runtime D3 status: Enabled (fine-grained)` but
  **`Video Memory: Active`**. That live allocation, not the PCI layer, is what blocks D3cold.
- **Ruled out by measurement, not reasoning:** `luminos-power` polling (45 s `/proc` scan caught
  **zero** `nvidia-smi`/`dgpu-exec` execs — BUG-160's fix is working); `power/control=on` (BUG-103);
  persistence mode (Disabled, persistenced dead); the compositor (kwin/plasmashell/qs/Chrome are all
  on **card2/renderD129 AMD**, **zero** holders on card1/renderD128); an AC/DC transition
  (`ACAD online=1` since boot); RTD3 config (`DynamicPowerManagement: 2`, as BUG-047 intended).
- **Sole holder:** `nvidia-powerd` PID 877, 11 fds on `/dev/nvidia0` + 1 on `/dev/nvidiactl`.
  Its own unit is **disabled** — **supergfxd starts it** on entering Hybrid. It errored at boot:
  `Client (presumably SBIOS) has requested to disable Dynamic Boost DC controller`.
- ⚠️ **DO NOT conclude "nvidia-powerd keeps it awake."** `/proc/877/fd` says those nvidia fds opened
  at **23:18:51**, hours *after* the card stopped sleeping. Timestamps verified real (re-listed
  twice, unchanged; fds 0–4 still read 13:26:33). **What opened them at 23:18:51 is the open
  question.**
- **Correlated trigger, not proven:** the only GPU-touching journal event all day is root
  `nvidia-smi -q -d DISPLAY` at **20:29:35**, corroborated by `/dev/nvidia-caps/*` created 20:29:37
  and the UVM ctime below. **Runtime PM has no last-transition timestamp**, so "it woke at 20:29" is
  *not* derivable from the counters — an earlier pass asserted it anyway and was wrong to.
- 🔴 **Separate live finding: the DECISION 25 gate is OPEN on two nodes.** `/dev/nvidia-uvm` and
  `-uvm-tools` are **`0666 root:root`**, ctime **20:29:37**, against `root:dgpu 0660` at boot.
  Textbook **BUG-146**: a root NVIDIA client makes setuid `nvidia-modprobe` re-apply the driver's
  hardcoded defaults to the two nodes `NVreg_DeviceFile*` cannot cover. `nvidia0`, `nvidiactl` and
  `nvidia-modeset` are still correct. Re-assert with `sudo systemctl restart luminos-uvm-gate`
  (**restart** — it is `active (exited)`). Not done: read-only turn.

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
1. **BUG-182 step 1 — find what opened nvidia-powerd's fds at 23:18:51.** Sample
   `ls -l --time-style=full-iso /proc/$(pgrep -x nvidia-powerd)/fd` + `power/runtime_status` once a
   minute for an hour. No state change, no GPU contact. **Only then** consider the
   `systemctl stop nvidia-powerd` A/B — that needs Shawn's word.
2. **Ask Shawn about the UVM gate re-assert** (`systemctl restart luminos-uvm-gate`). One command,
   but it is a state change and this turn was read-only.
3. **SPEC §3.6 — external producer (games).** Consumer half is built and proven (DECISION 124).
   **Blocker:** `org.freedesktop.impl.portal.ScreenCast.CreateSession` against `xdg-desktop-portal-wlr`
   gives no `Response` signal in 20 s. Probe at `/tmp/sc.py`. cage runs headless on the 780M
   (glxgears 62.8 FPS, picks the iGPU by itself). Producer must publish **packed RGB** (`format=BGRx`)
   or it renders greyscale. **DECISION 124a corrects 124:** input DOES exist — a live headless `cage`
   advertises `zwlr_virtual_pointer_manager_v1` + `zwp_virtual_keyboard_manager_v1`; the earlier
   measurement was taken against KWin, the wrong compositor.
4. **Spectrum on the GPU** — one `ShaderEffect` over the existing 128×1 `AudioTexture`.
   **DECISION 121: capping the publish rate was tried and measured WORSE. Do not redo it.**
5. **BUG-166 / BUG-167** — verify the tab sleeper (`chrome://extensions` must read 3.1), then
   reconcile `config/99-luminos-ram.conf` with the box **keeping `page-cluster = 3`** (DECISION 116).
6. **BUG-164** — 20 ASS files (Bazarr `use_embedded_subs` OFF), then one of the 26 DTS files.

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
**This turn (docs only, no code/config/system change):** `docs/BUGS.md` (new **BUG-182**),
`HANDOFF.md` (reset), `LUMINOS_STATUS.md`.
**Evidence sources, for re-running the investigation:** `/sys/bus/pci/devices/0000:01:00.0/power/*`,
`/proc/driver/nvidia/{params,gpus/0000:01:00.0/power}`, `/proc/$(pgrep -x nvidia-powerd)/fd`,
`journalctl -b -u {supergfxd,nvidia-powerd,luminos-power}`.
**Gate code:** `config/modprobe.d/luminos-dgpu-gate.conf`, `scripts/dgpu-gate/{dgpu-exec-v2.c,
luminos-uvm-gate.sh,install-dgpu-gate.sh}`, `config/udev/71-luminos-uvm-gate.rules`,
`systemd/luminos-uvm-gate.service`, `cmd/luminos-power/main.go` (`dgpuHasClients` 1594,
`dgpuRuntimeSuspended` 1578, `nvidiaRead` 1692, `regateUVM` 1730, `setProfile` 1340).
**Wallpaper:** `src/wallpapers/org.luminos.livewallpaper/contents/` + installed copy at
`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/` — keep `diff -rq` clean.
