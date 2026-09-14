# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-14 — Response 5

> Previous goals, complete, do not reconstruct from memory:
> gaming/dGPU → `git show b08c3904:HANDOFF.md` · `org.luminos.style` QML → `git show 4273ed7e:HANDOFF.md`
> web-surface redesign → `git show fa8c1bf2:HANDOFF.md` · PS5 controller + BUG-157 diagnosis → `git show 0c69ced3:HANDOFF.md`

## Goal (durable)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
Both faults reported 2026-09-14 are now **FIXED and verified live** — BUG-158 (live wallpaper) and
BUG-159 (self-dimming screen). Resume the bar plan at step 2 (dGPU indicator). The reboot in
"Still outstanding" item 1 is the oldest thing on the list and is still not done.

## State — what is DONE

### ✅ 2026-09-14 — BUG-158 FIXED / DECISION 103: live wallpaper gone — desktop containment orphaned

**Fix, verified live:** `SetCurrentActivity` → containment 30 went `screen=-1` → `screen=0`, and
plasmashell now holds the mp4 open (`/proc/<pid>/fd` → the video, with libavcodec/libavformat/
libQt6Multimedia mapped). Made permanent by `scripts/luminos-desktop-guard` +
`config/luminos-desktop-guard.service` (installed to `/usr/local/bin/` and
`~/.config/systemd/user/`, enabled on `plasma-workspace.target`). The guard reads the wanted
activity **off the containment** rather than hardcoding the uuid, re-asserts it at login, and
**always** writes `[main] currentActivity=` into `kactivitymanagerdrc` — kactivitymanagerd keeps
that value in memory and only flushes on a clean exit, so a crash or hard reboot would otherwise
resurrect the bug. Known-good desktop config snapshotted to
`config/kde/plasma-appletsrc-known-good-20260914`.

Note: the broken state **cannot** be reproduced through the API — `SetCurrentActivity s ""`
returns `false`. It only arises when kactivitymanagerd starts with no stored currentActivity,
which is exactly what the guard now prevents.

**Diagnosis that led there:**
Nothing is missing or broken. Verified present and intact: the plugin
`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/` (metadata.json + contents/ui/main.qml
+ config), the 14 MB video, and every Qt dep it imports (qt6-multimedia 6.11.2-1,
qt6-multimedia-ffmpeg, qt6-webengine). The Caelestia bar rework is **innocent** — proven with
`git log -S "modules/background"`: our `config/quickshell/caelestia-bar/shell.qml` has never
contained a `Background {}` element, so it never drew the desktop at all.

The failure is in Plasma's containment→screen placement:

```
busctl --user call org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell evaluateScript ...
  → idx=0 id=30 screen=-1 wp=org.luminos.livewallpaper
```
`screen=-1` means containment 30 is assigned to **no screen**, so it is never rendered and you see
kwin's flat clear-colour instead. Plasma places a containment on a screen only when its `activityId`
matches the current activity. Containment 30 carries
`activityId=d1c73956-6304-4b5a-b773-295615a0378b` (the only activity that exists), but
`org.kde.ActivityManager` **CurrentActivity is empty** — so it matches nothing. A second containment
31 exists with `activityId=` (empty), `wallpaperplugin=org.kde.image`, `Image=` empty — the blank
fallback. `[ScreenMapping] itemsOnDisabledScreens=1,,1,desktop:/worldline.desktop` shows Plasma
recorded the desktop item as living on a *disabled* screen.

**When:** `~/.config/plasma-org.kde.plasma.desktop-appletsrc` was rewritten **2026-09-13 20:48:05**
and truncated to **1184 bytes**. `~/.config/plasma-welcomerc` was written **20:48:04** — one second
earlier. Welcome Center only runs on a first-run profile, so Plasma treated the profile as new at
that moment and reset the desktop config. That is "after yesterday".

**Unexplained, flag before touching:** `~/.local/share/kactivitymanagerd/resources/test-backup/` and
`working-backup/` (each a copy of `database` / `-shm` / `-wal`) were created **Sep 14 18:23**. Those
are not KDE-generated names.

**Backups that exist** (do not overwrite without reading them):
`config/kde/plasma-org.kde.plasma.desktop-appletsrc`, `config/kde/plasma-appletsrc-tahoe-backup`,
and `~/.config/plasma-org.kde.plasma.desktop-appletsrc.{tahoe.bak,bak,bak-caelwp-20260818-121853,bak-wallpaper-20260724}`.

### ✅ 2026-09-14 — BUG-159 FIXED / DECISION 104: brightness dips on its own — PowerDevil DimDisplay with a 0-second timeout

**Fix, verified live:** this turned out to be a **regression against our own committed file**, not a
config to re-derive. `~/.config/powerdevilrc.bak-awake` — written 8 seconds before the bad change at
00:11:23 — is **byte-identical to `config/powerdevilrc` in git** (both 356 B, last touched by
`244f5eaf`, 2026-08-25). The `-awake` suffix names the intent: someone wanted the screen to stop
sleeping and wrote `0` meaning "no timeout". So the repair was a restore:

```
install -m644 config/powerdevilrc ~/.config/powerdevilrc
systemctl --user restart plasma-powerdevil.service
```

**The battery groups are deleted, not set to `-1`** — the committed file never had
`[Battery][Display]`/`[LowBattery][Display]`, so PowerDevil's shipped defaults now apply on battery.
Pinning `-1` there would mean a panel that never dims on battery, which nobody asked for.

**Verified:** 189 samples at 0.2 s on `/sys/class/backlight/amdgpu_bl2` with no input →
**exactly one distinct value.** The same watcher caught the fault *before* the fix
(`0.5775 → 0.5046 → 0.4317` of max in 0.4 s), so the instrument was proven able to see the bug
before it was trusted to declare it gone. Backup of the broken state:
`~/.luminos-backups/powerdevilrc.bak-bug159-20260914`.

⚠️ **Restarting PowerDevil mid-fade strands the panel at the interrupted ratio.** The dimming ratio
lives in the process, not the panel, so the restore it owed you is simply never issued. Measured
straight after the restart: hardware `195510` (49 %) while `org.kde.ScreenBrightness` still reported
7000/10000 (70 %) — flat, but wrong, and easy to misread as "still broken". Cure is to re-assert the
value it already claims:
```
busctl --user call org.kde.ScreenBrightness /org/kde/ScreenBrightness/display0 \
  org.kde.ScreenBrightness.Display SetBrightness iu 7000 0
```
→ `279300`, exact. Final check after that: **139 samples, one value, correct 70 %.**

**Original root cause (unchanged, kept for the reasoning trail):** `~/.config/powerdevilrc` had
`DimDisplayIdleTimeoutSec=0` in all three profiles
(`[AC][Display]`, `[Battery][Display]`, `[LowBattery][Display]`). In PowerDevil, **`-1` means never;
`0` is a real zero-second timeout**, so the dim action fires the instant input pauses and restores
the instant anything registers activity — a self-retriggering loop. File mtime **2026-09-13 00:11** —
also yesterday.

**Proof, measured live** (`/tmp/blwatch.sh`, 0.2 s poll on `/sys/class/backlight/amdgpu_bl2`):
KDE's user-facing brightness never moves while the hardware value does.

```
18:43:59.205  sysfs=278137  kde_dbus=7000  ratio=0.9958
18:43:59.442  sysfs=246715  kde_dbus=7000  ratio=0.8833
18:43:59.673  sysfs=214130  kde_dbus=7000  ratio=0.7667
18:43:59.908  sysfs=279300  kde_dbus=7000  ratio=1.0
```
`kde_dbus` = `org.kde.ScreenBrightness/display0 Brightness`, pinned at 7000/10000 = 70% = 279300/399000.
A user/app brightness change would move that property. Only a **dimming ratio** leaves it pinned while
the hardware moves — and `powerdevil_dimdisplayaction.so` exports exactly
`ScreenBrightnessController::setDimmingRatio(QString, double)`. One full fade reached **83791**, and
0.30 × 279300 = **83790** — PowerDevil's dim target to the unit.

**Ruled out by measurement, do not re-investigate:** AMD ABM (no `panel_power_savings` file exists
anywhere under `/sys/class/drm`, and ABM cannot move the *requested* value, only `actual_brightness`);
ambient light sensor (none present); `luminos-power` and `asusd` (neither binary contains any backlight
string); two-backlight-device conflict (the BUG-098 shim at `scripts/brightnessctl` routes everything
to `amdgpu_bl2` by DRM topology); Caelestia `Brightness.qml` round-tripping (it writes whole percents;
the observed values are 1/240 steps of the current value).

### ✅ 2026-09-13 — BUG-157 / DECISION 102: luminos-power was blind to the dGPU and throttled the laptop mid-game
Reported first as *"way more gpu and still way less fps and graphics"*, then sharpened to
*"when I am using GPU and playing games it should have been fully unlocked, whole laptop, everything,
but it's not."* Both were the same root cause, and the second framing is the more serious half.

**Root cause, one line:** `readDGPULoad()` read `/sys/class/drm/card1/device/gpu_busy_percent`.
`card1` really is the RTX 4050, but `gpu_busy_percent` is an **amdgpu-only** attribute — it exists on
`card2` and has never existed on the NVIDIA node. The error was discarded into `_`, so **`dgpuLoad`
was hard-wired to 0.0%** for the life of the daemon. Every beast-mode line ever logged on this
machine says `dgpu=0%` while nvidia-smi reported 99% at the same instant.

**The chain that produced "not fully unlocked":**
```
dgpuLoad = 0 always
  ├─ applyGamingDetection(0,…) never returns Performance → beast mode unreachable from GPU
  ├─ beast mode EXITED mid-game  → 20:14:21 "exit → Balanced (cpu=15%, dgpu=0%)"
  ├─ quiet-idle: cpu 15<25 && igpu 3<15 && dgpu 0<5 → 60s → asusctl profile set Quiet
  │    ├─ platform_profile=quiet → firmware grants the dGPU only 60 W of the 90 W asked for
  │    └─ adaptive governor NOT suspended → CPU capped 3.68 GHz, EPP=power
  └─ TGP idle-revert `power<15 && util<20` → util half permanently true → false idle cuts
```

**Four fixes in `cmd/luminos-power/main.go`:**
1. dGPU utilisation now comes from `nvidia-smi --query-gpu=utilization.gpu`, folded into the **one**
   call `readGPUStats()` already made for power+temp. `readDGPULoad()` and `readGPULoad()` **deleted**
   (the latter had zero callers and globbed `card*`, returning the max across *both* GPUs — a
   landmine, since its comment advertised it for dGPU detection). The dead sysfs hwmon branch in
   `readGPUStats` went too.
2. Idle-revert now has a real `util` term, so one low wattage sample can't cut power mid-game.
3. Thermal **deadband**: `gpuTGPThermalDownC = 87.0` / `gpuTGPThermalUpC = 82.0` replace the single
   `gpuTGPThermalCeilC = 83.0`. Same split applied to the offload-pin branch in `monitorLoop`, which
   was worse — an unconditional per-tick reassertion could flip every 2 s, not every 60 s.
4. `initGPUTGP()` **adopts** the live limit instead of blind-writing 55 W on every daemon start.

**Measured before/after, same game, same boot, ~4 min apart:**

| | before | after |
|---|---|---|
| `asusctl profile` | **Quiet** → Balanced | **Performance** |
| EPP | `power` / `balance_power` | `performance` |
| `scaling_max_freq` | **3.68 GHz** of 5.14 | **5.14 GHz** (uncapped) |
| dGPU enforced limit | **60 W** → 75 W | **89.8 W** |
| dGPU temp | 73-75 °C | **68 °C** |
| beast-mode trigger | `trigger: cpu, dgpu=0%` | `trigger: gpu, dgpu=99%` |
| TGP switches / 90 s | ~1 per 63 s | **0** |

`beast mode → Performance (trigger: gpu, cpu=17%, dgpu=99%)` is the **first GPU-triggered beast mode
this machine has ever logged.** Every reason in `nvidia-smi -q -d PERFORMANCE` now reads
`Not Active`, including `SW Power Cap` (lifetime counter ≈191 s of capping).

Backup: `~/.luminos-backups/luminos-power.bak-bug157-20260913`.

### ✅ earlier 2026-09-13 — PS5 controller in Lutris (BUG-156 / DECISION 101)
`/dev/hidraw3` was `root:root 0600` because `steam-devices` was not installed — that one node decides
whether SDL uses its **HIDAPI PS5** driver (rumble, light bar, gyro, touchpad, correct map) or falls
back to generic evdev, which enumerates cleanly and throws no error. Fixed with
`pacman -S steam-devices`. Also deleted Black Myth Wukong's dead `sdl_gamecontrollerconfig` override
(GUID product `e60e` vs the real `e60c`, and a DualShock-3 body anyway). Verified as `shawn`, no
sudo: HIDAPI active, rumble felt, light bar went orange, gyro/accel/touchpad present.
Backup: `~/.config/lutris/games/black-myth-wukong-1788815087.yml.bak-ps5-20260913`.

### ✅ earlier — the web-surface redesign (DECISION 99)
All eight surfaces on one token set. Brief `server/docs/WEB_UI_PROMPT.md` **v3** (v2/v1 are
superseded — **do not merge them**); research trail and screenshots in `server/docs/WEB_UI_FINDINGS.md`.

| tier | what | how |
|---|---|---|
| 1 | `luminos-hub` `/` + `/offline`, `luminos-space` | ours, rebuilt from zero on `/app.css` |
| 2 | Jellyfin | Custom CSS via its own API — **ElegantFin removed** |
| 3 | Radarr, Sonarr, Prowlarr, NZBGet, **Bazarr** | skinned on disk + pacman hook |
| 4 | Jellyseerr | cannot be skinned — request flow **absorbed** as a first-party page |

## ⚠️ Read these before touching the web surface
1. **There are FIVE tier-3 apps, not the four the brief lists.** Bazarr arrived the same day the
   brief was written (DECISION 98). It is in `TIER3`, in the hook, and skinned.
2. **`login.html` is skinned too**, so `pacman -Qkk` reports **2** altered files per Servarr app, not
   the 1 that §8 check 10 calls "the ONLY acceptable result". Deliberate — all three run
   `AuthenticationMethod=Forms`. **Do not "fix" it back.**
3. **The pacman hook is proven live on NZBGet only.** The other four are not in
   `/var/cache/pacman/pkg/`, so the version-identical reinstall could not be run. Needs a
   re-download — ask first.
4. **`<Theme>dark</Theme>` is a write under `/var/lib/<app>/`**, which §6.13 otherwise forbids. It is
   the "free win" §4 instructs; Servarr persists that API field to `config.xml`. Flagged, not hidden.

## Still outstanding (ordered)
1. **Reboot — still urgent, and now the ONLY thing left from the gaming work.** 553 packages were
   upgraded at 11:27 on 2026-09-13 and the box has not booted since **2026-09-12 09:45**. Measured:
   `kwin_wayland` (pid 1564) is compositing with **198 deleted mappings** including `libEGL_mesa.so`,
   `libgbm.so`, `gbm/dri_gbm.so`, `libvulkan_radeon.so` and `libwayland-server.so.0.25.0`, while disk
   holds mesa 26.2.2 and `libwayland-server.so.0.26.0`. `Xwayland` (1663) and `plasmashell` (1751,
   1329 deleted maps) likewise. Plus glibc + systemd. On a PRIME box the game's frames cross that
   boundary every frame. Afterwards confirm `dgpu-exec-v2 -- nvidia-smi` and that beast mode still
   latches from GPU load. **No longer a prerequisite for BUG-157 — that is fixed without it.**
2. **The SBIOS / Dynamic-Boost handshake failure is real but is NOT a power cap.** `dmesg` 09:45:53:
   `PlatformRequestHandler failed to get target temp from SBIOS`. `asusd` can't read `nv_tgp` /
   `nv_dynamic_boost` / `ppt_pl*` (ENODEV on
   `/sys/class/firmware-attributes/asus-armoury/attributes/*/current_value`). Absent from boots
   -1/-2/-3/-5 on the identical driver. **BUG-157's write-up originally blamed the 60 W ceiling on
   this and it was wrong** — the enforced limit tracks the platform profile (quiet 60 / balanced 75 /
   performance 90 W), measured on this same un-rebooted boot. Do not explain a low power limit with
   this again. Reboot (item 1) is still the first thing to try for the handshake itself.
3. ⚠️ **`server/config/Caddyfile` in the repo is STALE — missing the Bazarr `:8450` block that is
   live on the box.** DECISION 98 added it to `/etc/caddy/Caddyfile` on 2026-09-13 17:51 and never
   mirrored it back. Restoring the repo copy onto the box today would silently drop Bazarr's front
   door. **Mirror it back as its own change.** The one *other* difference is intentional and must
   stay: the repo redacts the `luminos-space` token, the live file has the real one.
4. **`luminos-brain safe` has now returned a false `NO` four times** by matching the bare word
   "install". **Its rule scope needs narrowing.** Until then the documented escape is
   `luminos-brain safe "<action>" --reason "<why it is not ML/venv>"`, which logs `OVERRIDE LOGGED`.
   Also open: make a `NO` print its actual reason instead of unrelated canned incident lines.
5. Bazarr has **pre-existing** errors from its fresh install, unrelated to the skin:
   `KeyError: 'audio_only_include'`, a `FOREIGN KEY constraint failed` on a Solo Leveling episode,
   and Sonarr sync timeouts. All timestamped before that work — see `WEB_UI_FINDINGS.md` §10.2.
6. `/etc/nftables.conf` was rewritten at 17:51 the same day, with a `.bak-20260913` alongside.
   **Checked, not assumed:** `policy drop` still holds and every `accept` is restricted by source
   address or interface — the only unrestricted ones are ICMP. Nothing is open to the internet.
7. **Still unexplained: the initramfs-looking untracked tree at the repo root** (`init`, `kernel/`,
   `usr/`, `etc/`, `lib`, `sbin`, `hooks/`, `early_cpio`, `buildconfig`, `keymap.bin`,
   `consolefont.psfu`). Plus an untracked `_to_delete/`. **Find out what these are before anyone
   commits or deletes them.**
8. ⚠️ **`AGENTS.md` §9's `powerdevilrc` row is STALE** — found while fixing BUG-159, not fixed
   because it is a separate change. It documents DECISION 38's `AutoSuspendAction=1`, `LidAction=1`,
   `AutoSuspendIdleTimeoutSec=900/600/300`. The committed file has said `AutoSuspendAction=0`,
   `LidAction=0`, `3600/600/300` since `244f5eaf` (2026-08-25, *"stop the G14 suspending — it serves
   Dolphin to the phone now"*), which reversed DECISION 38. **An agent trusting that row would
   "restore" suspend-on-lid-close onto a machine that is deliberately a server.** Fix the row, keep
   the DECISION 38 history as history.
9. **Known, not fixed, flagged deliberately:** the RAM-pressure branch in `monitorLoop` logs
   `resource coord: RAM 9% avail → +22% effective load (cap nudged down)`, but adding to
   `effectiveLoad` *raises* the cap in `computeAdaptiveCap` (`base + load/100 × (max-base)`). The
   log text and the arithmetic disagree about the sign. Left alone — out of scope for BUG-157, and
   inert in Performance where the governor is suspended. Decide intent before touching it.

## How to change a skin
Edit `server/assets/skins/<app>/luminos.css`, then:
```
rsync -a server/assets/skins/ <box>:/tmp/skins/
sudo rsync -a /tmp/skins/ /usr/local/share/luminos/skins/
sudo luminos-skin-apply --check     # dry run, exits 1 if anything would change
sudo luminos-skin-apply             # apply
```
Comments and indentation are stripped at install time (that is how the 8 KB budget is met), so the
repo copy stays readable and `diff`ing installed-vs-git still works line by line. A colour-only
change never restarts a service; only inserting the `<link>` does.

## Key decisions & constraints

**Frozen token set** — every colour and size in the finished CSS resolves to one of these:

| token | value | token | value |
|---|---|---|---|
| `--bg` | `#0F0D0B` | `--accent` | `#FF7A18` |
| `--surface` | `#17140F` | `--ok` | `#3FBF6A` |
| `--line` | `#2A2520` | `--warn` | `#E8C547` |
| `--text` | `#F2EDE4` | `--danger` | `#FF4D3D` |
| `--muted` | `#8C8279` | `--r` | `4px` |

Type: `--t-display clamp(52px,15vw,76px)` / `--t-head 15px` / `--t-body 15px` / `--t-mono 14px` /
`--t-caption 12px`. Spacing `--s1..--s6` = 4/8/12/16/24/40 px. Faces: **Archivo** 500+800, **JetBrains
Mono** 400+800 (all numbers, all release names). Accent is deliberately a hue-step from `--warn`.

**`/app.css` and `/app.js` on port 8099 do NOT require the token.** Static constants, no library
data, no secrets. Every route returning library data or performing a delete keeps `compare_digest`.

**Fonts are a whitelist, not a path join.** `FONTS` is a fixed tuple and the route tests membership,
so traversal is impossible by construction. Verified with `/fonts/../../../etc/passwd` → 404.

## Gotchas / dead-ends / things NOT to redo

**GPU / power** — rewritten 2026-09-13, several old entries were wrong
- **`gpu_busy_percent` is amdgpu-only and there is no NVIDIA equivalent.** Neither is
  `device/hwmon/`. Any Go/Python reading them for the 4050 silently gets 0 — **and this already cost
  a real bug (BUG-157), so do not re-add a sysfs read for dGPU load.** The only honest source is
  `nvidia-smi --query-gpu=utilization.gpu`.
- **`card1` is the RTX 4050 and `card2` is the 780M** — the numbering is *not* the trap people
  assume; the trap is assuming the *attributes* are the same on both.
- **The dGPU's enforced power ceiling tracks the asusctl platform profile**, measured 2026-09-13 with
  a game running: quiet **60 W**, balanced **75 W**, performance **90 W**. So a low `Current Power
  Limit` is usually a *profile* problem, not a firmware or SBIOS problem. Check
  `asusctl profile get` before you chase ACPI.
- **`nvidia-smi -q -d POWER` "Current Power Limit" is what was granted, not what was asked for.**
  Compare it against the log before believing either. `--query-gpu=power.limit` reads `[N/A]`
  (BUG-069) — use `-q -d POWER` and parse it, as `readGPUPowerLimit()` now does.
- **Read the card's own thermal limits before inventing a ceiling.** `nvidia-smi -q -d TEMPERATURE`
  gives `GPU Target Temperature Specification: 87 C`; the `T.Limit` fields are **offsets from the
  current temp, not absolutes** (73 °C current with `Current T.Limit 16` ⇒ max operating 89 °C,
  slowdown 91 °C, shutdown 101 °C). The old 83 °C constant was 4 °C below the firmware's own target.
- **One constant used as both a drop threshold and a re-raise gate is a latch, not a limit.** A
  hysteresis *timer* does not damp that oscillation — it only sets its period. Always split into
  separate up/down values.
- **"The GPU is slow" starts at `journalctl -b 0 -u luminos-power -g 'GPU TGP'`, then
  `asusctl profile get`, then `nvidia-smi -q -d PERFORMANCE`** (every clocks-event reason, not just
  temperature). A one-shot nvidia-smi at idle tells you nothing about a governor oscillating under
  load. Do NOT start at nvidia-smi.
- **`SW Thermal Slowdown: Active` at idle is a sampling artefact** — the query itself wakes the card.
  Sample five times; the counters stop growing.
- **Never add a bare `runCmd`/`exec.Command` for nvidia-smi in luminos-power.** Three wrappers exist
  and one of them is always right: `nvidiaQuery` (`--query-gpu` reads), `nvidiaRead` (any other
  read), `nvidiaCtl` (the four state-changing calls, re-gates after). A **root** nvidia-smi reopens
  `/dev/nvidia-uvm` to 0666 by itself even for a read-only query — BUG-146, and it is silent.

**Controllers**
- **`getfacl /dev/hidraw*` is the first check for any "controller not supported" report**, not
  `/dev/input`. evdev/joydev get `uaccess` from stock systemd rules and look healthy while hidraw is
  locked and every real feature is missing.
- **Do not hand-write a udev rule or an `sdl_gamecontrollerconfig` for a pad** (DECISION 101).
- **`SDL_GameControllerRumbleTriggers` returning "not supported" on a DualSense is correct** — that
  is the Xbox trigger-rumble API. Adaptive triggers use `SDL_SendGamepadEffect`.
- **No 32-bit SDL on this box, and none is needed.** Installing one fixes nothing.

**Web surface**
- **Font weight lives in the hinting and ligature tables, not the glyphs.** A naive Latin-1 subset of
  JetBrains Mono Regular is 29,348 bytes; `--no-hinting` plus dropping `liga`/`calt` gives the same
  coverage in 7,884. Do not re-derive. **Keep `tnum`.** Subset range is **Latin-1 + Latin Extended-A,
  not ASCII** — the library holds titles like `Amélie` and a missing glyph falls back mid-word.
- **Screenshot through Caddy, never `127.0.0.1`** (the loopback port skips the proxy, the TLS and the
  token injection):
  `chromium --headless --disable-gpu --no-sandbox --ignore-certificate-errors
  --window-size=412,1400 --force-device-scale-factor=2 --virtual-time-budget=9000 --hide-scrollbars
  --screenshot=/tmp/x.png "https://192.168.2.61/"` (412 px = Pixel 9 CSS width).
- **`server/SPEC.md` is a different project** (the LLM prefill work). The web spec is
  `server/docs/WEB_UI_PROMPT.md`.
- **Tier-3 apps CAN be reskinned** — the brief once claimed otherwise and was wrong. What was proved
  is only that *proxy-level body rewriting* is unavailable in stock Caddy. Portable lesson, now in
  the brief's Phase 0 step 5: **"I tested route A and it failed" is not "the thing is impossible."**
- **NZBGet is the HARDEST of the five, not the easiest** — Bootstrap 2, no custom properties, ~120
  selectors by hand. Bazarr is the easiest (Mantine 7, real token layer, 2322 B).

**KDE config files**
- **Look for a `.bak*` sibling BEFORE theorising about a wrong config value.** BUG-159 was solved by
  `ls ~/.config/powerdevilrc*` — the backup was byte-identical to git, so the entire bug collapsed
  into a two-line diff, and the backup's *name* (`.bak-awake`) revealed the author's intent. This has
  now paid off twice in two days; do it first, not last.
- **`0` is not "never" in `powerdevilrc`. `-1` is.** Any `*IdleTimeoutSec=0` is a zero-second
  timeout. Now in AGENTS.md §11.
- **Restarting `plasma-powerdevil.service` mid-dim leaves the panel dark.** The dimming ratio is
  process state. Re-assert via `org.kde.ScreenBrightness … SetBrightness` — details in the BUG-159
  block above. Do not mistake the stranded-but-flat panel for an unfixed bug.
- **Live KDE configs drift from `config/` in git with nothing to notice it** — the same class as the
  installed-vs-repo script drift in AGENTS.md §9. `diff` the pair before assuming the live one is
  authoritative.

**Process**
- **MCP `mempalace` and `code-review-graph` are NOT connected in Cowork sessions.** AGENTS.md §6
  requires saying so rather than skipping silently. Confirmed again this session — fell back to
  `luminos-notes.sh search` + `luminos-brain query`, both of which returned nothing for this topic.
- **`asusctl profile -p` / `-P` do not exist.** The subcommand is `asusctl profile get`.

## Files touched this session (Response 5 — BUG-159)
- `docs/BUGS.md` — BUG-159 → **FIXED**, incl. the `.bak-awake` finding and the mid-fade side effect
- `LUMINOS_DECISIONS.md` — **DECISION 104** added
- `AGENTS.md` §11 — `0` in `*IdleTimeoutSec` added to Absolute Do-Nots
- `HANDOFF.md` — this file
- **Live system, not in the repo:** `~/.config/powerdevilrc` restored from `config/powerdevilrc`,
  `plasma-powerdevil.service` restarted, brightness re-asserted to 70%; backup
  `~/.luminos-backups/powerdevilrc.bak-bug159-20260914`
- **No repo file needed changing to fix the bug** — `config/powerdevilrc` was already correct

## Files touched earlier this session
- `cmd/luminos-power/main.go` — BUG-157, four fixes (see above)
- `docs/BUGS.md` — BUG-157 → **FIXED**, incl. the correction that the 60 W clamp was the platform
  profile and not the SBIOS handshake
- `LUMINOS_DECISIONS.md` — **DECISION 102** added
- `LUMINOS_STATUS.md` — `luminos-power` row updated
- `AGENTS.md` §9 — `/usr/local/bin/luminos-power` row added
- `HANDOFF.md` — this file
- **Live system, not in the repo:** `/usr/local/bin/luminos-power` rebuilt + reinstalled, daemon
  restarted; backup `~/.luminos-backups/luminos-power.bak-bug157-20260913`
