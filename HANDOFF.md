# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-16 — Response 12

> ⚠️ **Counter discrepancy, recorded deliberately per AGENTS.md §0.1 (do not silently "fix" it).**
> The previous copy of this file said *Response 15*. This session was told by Shawn that it is
> **Response 12 of the Cowork chat** and to continue from there. Two different chats have been
> writing this one file. The number below is this session's; treat a jump as the canary it is.
>
> **This file was RESET again on 2026-09-16.** The previous copy was **610 lines** — still past the
> ~400-line tripwire in §0.2 even after its own reset. Old copy: `git show HEAD:HANDOFF.md`, and the
> one before that `git show 4dd0d7ae:HANDOFF.md`. Completed 2026-09-16 desktop/wallpaper work
> (BUG-162/163, DECISION 110–113) is finished and documented in `LUMINOS_DECISIONS.md`,
> `docs/BUGS.md` and `LUMINOS_STATUS.md` — it is **not** re-summarised here.
> Older goals: gaming/dGPU `git show b08c3904:HANDOFF.md` · `org.luminos.style` QML
> `git show 4273ed7e:HANDOFF.md` · web surface `git show fa8c1bf2:HANDOFF.md` · PS5 pad + BUG-157
> `git show 0c69ced3:HANDOFF.md`.

## Goal (durable)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**BUG-164 is root-caused on the real box for the first time. The standing hypothesis was wrong in
both halves, and nothing has been repaired yet.** The next move is Shawn's (see Next steps).

## Why / motivation
On the Jellyfin **Roku** app, *Skip Intro* and scrubbing both restart the episode at 00:00. Three
prior sessions worked on this without a route to the server, so every conclusion was inference.
This session ran it on the box.

## Process / approach
The media server is a **separate headless machine**, reached only from the G14:
`ssh -i ~/.ssh/luminos-server shawn@192.168.2.61` (server is `.61`, G14 is `.16`). `sudo` is
NOPASSWD there. Ground truth for a transcode question is **Jellyfin's own ffmpeg command lines** in
`/var/log/jellyfin/`, never a capability table.

---

## State — what is DONE (2026-09-16, this session)

**Installed on the server**, both mode 755, from `server/scripts/`:
`/usr/local/bin/luminos-roku-compat` and `/usr/local/bin/luminos-fix-e7`. Checksums verified
across the copy. All four library roots present, `jellyfin-ffmpeg` present.

**`sudo luminos-fix-e7 S01E07` was run. It changed nothing, correctly.**
The fault line was neither `audio:*` nor `video:*` — it was
`OK - every file in 4 root(s) should Direct Play on the Roku.`
`/srv/external/_roku_pre_ac3_originals/` exists and is **empty**; the E07 file is byte-for-byte
untouched (mtime still 2024-03-02); no `.rokufix.*` temp files anywhere. **No media was modified.**

### ⚠️ The premise was inverted — S01E07 is one of the episodes that WORKS
`Solo Leveling - S01E07` is `h264` + **one** AAC stereo English track and **no subtitle track at
all**. It appears **zero** times in four days of Jellyfin transcode logs. The jpn/kor "E07.5 recap
mis-map" audio theory (DECISION 98/101) is **disproven** — do not spend time on it again.

| Episodes | Subtitle tracks | Res | Ever transcoded? |
|---|---|---|---|
| E01, E03, **E07** | **none** | 1080p | **never** |
| E02 | 16 ass + 3 subrip | 1080p | yes |
| E04–E06, E08–E12 | 19 ass | 2160p | yes |

### The real cause is ASS subtitle burn-in, and the tool was built to ignore it
`ass` sat in the tool's `TEXT_SUBS` set. Jellyfin only converts **subrip-class** tracks to WebVTT
for client-side rendering; **ASS carries styling, positioning and embedded fonts the Roku cannot
render, so Jellyfin burns it into the picture** — a full video re-encode, i.e. the live transcode
the tool exists to prevent. So it printed *"OK — every file should Direct Play"* for a season
Jellyfin was transcoding at that moment.

**Proof, and it is airtight — S01E02:** 1080p source, `-codec:a:0 copy` (audio stream-**copied**),
no resize, yet `-codec:v:0 h264_vaapi`, with
`subtitles=f='…/8.ass':alpha=1:sub2video=1` composited by `overlay_vaapi`. Codec, resolution,
bitrate and audio were all fine. **Burn-in was the only cause present.**

### jellyfin-roku#582's mechanism was observed live, not inferred
S01E09, 2026-09-16, three encoder restarts in 90 seconds:
`start_number 0` → `-ss 00:03:12.192 start_number 32` → `-ss 00:06:54.414 start_number 69`.
Every seek tears `jellyfin-ffmpeg` down and restarts it at an offset. That is the bug, on this box.

### Two defects fixed in `server/scripts/luminos-roku-compat` (verified against the live library)
1. **`ass`/`ssa` moved out of `TEXT_SUBS` into a new `BURN_SUBS`.** After the fix the audit flags
   **exactly** the 8 episodes that actually transcoded and clears the 3 that never did.
2. **`JF_LOG_DIR` was `/var/lib/jellyfin/log`, which does not exist here** (real path:
   `/var/log/jellyfin`). `--observed` — the one function written to overrule the guessed table —
   had therefore **never once run**, and failed with *"run this on the server, as root"* **while
   running on the server as root**. Now probed, not hardcoded. `--observed` works.

### First honest library-wide numbers
**46 files will force a transcode: 26 `audio:dts` · 20 `subs:ass(burn-in)` · ZERO `video:*`.**
Nothing in the library needs re-downloading. `audio:dts` is what `--fix-audio` was built for;
`subs:ass` is **not** repairable by adding an audio track.

### ⚠️ A second trigger exists and is client-side — UNSETTLED
Today's S01E08/E09 sessions ran with subtitles **off** (`-map -0:s`) and still transcoded: 2160p
`h264 High@L5.1` sources pinned to `-level 42`, and on E09 `scale_vaapi=w=1920:h=1080` with a round
`-b:v 10000000`. **The server imposes no such limit** — `RemoteClientBitrateLimit` is `0` in
`/etc/jellyfin/system.xml` and the user policy is empty — so that ceiling arrives in the Roku's own
PlaybackInfo request. But an **earlier** session (E06, 00:21) emitted 4K at L5.1, so this is the
Roku app's **quality setting varying between sessions**, not a fixed Roku H.264 ceiling.

### ⚠️ Bazarr cannot be read as the all-clear here
`use_embedded_subs` is ON, so an embedded **ASS** track satisfies the profile and Bazarr reports
`missing_subtitles: []` — correct by its own rules and exactly wrong here, because that ASS track
is the thing forcing the transcode. **"Bazarr says nothing is missing" ≠ "these files are fine."**
This narrows DECISION 98's advice; it does not contradict the part about profiles being assigned.

---

## State — IN PROGRESS / where it was left off
Nothing is mid-flight. The tool is installed and correct on the server; no media file has been
altered; `--fix-audio --apply` has **not** been run on the library.

## Next steps (ordered)

1. **Shawn: watch an episode and confirm.** Play **S01E07** on the Roku and seek — it should work
   (it Direct Plays). Then play **S01E09** and seek — it should break. That one A/B confirms the
   whole model. Check with `pgrep -af jellyfin-ffmpeg` on the server during playback: **no process
   = Direct Play**.
2. **Decide the fix for the 20 `subs:ass(burn-in)` files.** Three options, in order:
   (a) get Bazarr to fetch real **SRT** sidecars for them — needs `use_embedded_subs` turned OFF or
   made to ignore ASS, otherwise it will keep reporting them complete;
   (b) turn subtitles **off** on the Roku for those titles (works today, costs the subs);
   (c) strip/convert the ASS track in place. **(a) is the right one** — it also fixes seeking.
3. **The 26 `audio:dts` files: run `--fix-audio` on ONE file, watch it, then the rest.**
   The DECISION 112 gate still stands and has never been satisfied — the ffmpeg invocation in
   `fix_audio()` has **never been run against real media**. Do one by hand, watch it end to end,
   confirm the AC3 track and the preserved original, and only then consider the other 25.
4. **Settle the client-side ceiling.** Check the Roku app's Settings → Playback video-quality
   setting. If it is pinned to a 1080p/10 Mbps preset rather than Auto/Maximum, that is a second,
   independent cause of transcoding on every 2160p file.
5. **Then, and only then, wire up the weekly `luminos-roku-compat` timer**
   (`server/systemd/luminos-roku-compat.{service,timer}`, still uncommitted/uninstalled).

## Still outstanding (unchanged from before this session)

- **0aa. BUG-165 — "loading subtitles crashes the stream" is a TIMEOUT, not a crash.** Jellyfin
  demuxes an embedded track on first request, reading the whole file (~144 s on a 2160p remux,
  DECISION 60); the Roku gives up first. Install and run the warm sweep once by hand:
  ```
  sudo install -m755 ~/luminos-os/server/scripts/luminos-subtitle-warm /usr/local/bin/
  sudo install -m644 ~/luminos-os/server/systemd/luminos-subtitle-warm.{service,timer} \
       /etc/systemd/system/ && sudo systemctl daemon-reload
  sudo /usr/local/bin/luminos-subtitle-warm          # first sweep is the slow one
  sudo systemctl enable --now luminos-subtitle-warm.timer
  ```
  ⚠️ A PGS/VOBSUB track cannot be helped by the sweep — that is burn-in, a different fault.
- **0b. `luminos-audio-audit` was auditing HALF the library** — `ROOTS` never grew when DECISION 91
  added `/srv/external` on 2026-09-03, and a missing path fails silently in `os.walk`. Fixed in the
  repo; **needs one real run to re-baseline.** ⚠️ **This is now the third hardcoded-path fault in
  `server/scripts/`** (with `JF_LOG_DIR` above). Every script in there with a baked path list needs
  the same check — probe it or refuse, never assume.
- **1. Read `.luminos-wallpaper-probe.log`** for the DECISION 113 result (did the native QML scenes
  load, and what do they cost). VA-API is already confirmed working; nothing to tune on decode.
- **2. The dGPU still wakes ~13 s per 180 s and BUG-161 does not explain it.** After the DECISION
  109 choke point there were **0 profile switches** in that window, so this is a different path from
  the NVPCF one. Next step: a longer `rpm_resume` trace — `filter` = `name == "0000:01:00.0"`,
  `trigger` = `stacktrace if name == "0000:01:00.0"`, leave it an hour, read the **tail**.
  Do **not** re-scan `/proc/*/fd`; proven blind to this class.
- **3. The lock-then-suspend path is still untested against a physical lid close.** The watcher has
  fired for real (journal 2026-09-15 17:39:43) but that was *before* the DECISION 107 lock fix.
  Close the lid, reopen, confirm it demands a password, check `journalctl -u luminos-lid`.
- **4. The SBIOS / Dynamic-Boost handshake failure SURVIVED the 2026-09-14 reboot.** All four
  attributes still read **ENODEV** (`nv_tgp`, `nv_dynamic_boost`, `ppt_pl1_spl`, `ppt_pl2_sppt`
  under `/sys/class/firmware-attributes/asus-armoury/attributes/*/current_value`). "Reboot first"
  has now been tried and failed; next theory is firmware/BIOS version or the `asus-armoury` module.
  **Do not use the log line `PlatformRequestHandler failed to get target temp from SBIOS` as the
  test** — it greps zero times even while the fault is present. Test the attributes directly.
  **This is NOT a power cap** — the enforced limit tracks the platform profile (60/75/90 W).
- **5. `server/config/Caddyfile`'s Bazarr `:8450` block is RECONSTRUCTED, not copied.** `diff` it
  against `/etc/caddy/Caddyfile` before installing, and record the result here. The redacted
  `luminos-space` token is an intentional difference.
- **6. `luminos-brain safe` has returned a false `NO` four times** by matching the bare word
  "install". Escape hatch: `luminos-brain safe "<action>" --reason "<why>"` → `OVERRIDE LOGGED`.
  Also open: make a `NO` print its real reason instead of unrelated canned incident lines.
- **7. Unexplained initramfs-looking untracked tree at the repo root** (`init`, `kernel/`, `usr/`,
  `etc/`, `lib`, `sbin`, `hooks/`, `early_cpio`, `buildconfig`, `keymap.bin`, `consolefont.psfu`)
  plus an untracked `_to_delete/`. **Find out what these are before anyone commits or deletes them.**
- **8. `systemd/luminos-lidsleep.conf` is an orphaned duplicate** of `config/luminos-lidsleep.conf`
  and should be DELETED, not maintained. `config/` is canonical.
- **9. Known, not fixed, flagged deliberately:** the RAM-pressure branch in `monitorLoop` logs
  `RAM 9% avail → +22% effective load (cap nudged down)`, but adding to `effectiveLoad` *raises*
  the cap in `computeAdaptiveCap`. Log text and arithmetic disagree about the sign. Decide intent
  before touching it.
- **10. Shawn's call, do not action unilaterally:** no FDE, `NOPASSWD: ALL`, sshd
  `PasswordAuthentication yes` on `0.0.0.0:22`, both SSH keys passphrase-less, `Autolock=false`,
  and the CAP_SYS_PTRACE/CAP_KILL half of `luminos-ram`.
- **11. BUG-086 — URGENT, user action required.** A live OpenRouter API key sits in
  `.claude/settings1.json`, tracked by git and already pushed. **Rotate the key at openrouter.ai
  first**; history rewriting is pointless while the credential is valid.
- **12. Bazarr has pre-existing errors** from its fresh install, unrelated to any skin
  (`KeyError: 'audio_only_include'`, a FOREIGN KEY failure, Sonarr sync timeouts) —
  `WEB_UI_FINDINGS.md` §10.2.

---

## Gotchas / dead-ends / things NOT to redo

### Jellyfin / Roku / media server
- **`ass` is text but is NOT client-renderable on a Roku.** Jellyfin converts only subrip-class
  tracks to WebVTT; ASS gets burned in, which is a full video re-encode. Treating ASS as "safe text"
  is what made the audit certify a library it was actively wrong about.
- **Ground truth for "why did this transcode" is the ffmpeg command line**, in
  `/var/log/jellyfin/jellyfin<date>.log` and the per-session `FFmpeg.Transcode-*.log`. Read
  `-codec:v`, `-codec:a`, `scale_vaapi=w=…`, `-b:v`, and whether `-vf`/`-filter_complex` contains
  `subtitles=`/`overlay_vaapi`. A capability table is a guess; this is Jellyfin's own decision
  against the Roku's real device profile.
- **A `subtitles=…:sub2video=1` + `overlay_vaapi` filter IS burn-in.** `-map -0:s` means subtitles
  were dropped, i.e. **not** burn-in — look elsewhere in that session.
- **The Jellyfin log directory is `/var/log/jellyfin`, not `/var/lib/jellyfin/log`.** Config lives
  in `/etc/jellyfin/*.xml`, not `/var/lib/jellyfin/config/`. The database is
  `/var/lib/jellyfin/data/jellyfin.db` (`Devices`, `Users` tables are readable with `sqlite3`).
- **A round `-b:v` (e.g. exactly `10000000`) is a client-imposed cap; a jagged one
  (`8859343`, `11769088`) is derived from the source.** That one character tells you whether a
  quality setting is in play.
- **`/var/log/jellyfin` is not readable as `shawn`** — a glob in an ssh command expands *before*
  `sudo` and fails. Wrap the whole loop: `sudo bash -c '…'`, or ship a script and `sudo bash` it.
- **Do not trust a curl to 192.168.2.61 that returns HTTP 403.** From a sandboxed agent VM the
  proxy answers 403 for **every** port including 22. The honest test is a raw TCP connect. From the
  G14 the box is simply reachable over ssh.
- **The three episodes with no subtitle track are the ones that work.** When a media fault looks
  per-file, diff the *stream lists* of a working and a failing file before theorising.

### Plasma desktop / containments
- **`~/.local/share/plasma/plasmoids/<id>/` does NOT shadow `/usr/share` for a containment reached
  through `X-Plasma-RootPath`** — measured 2026-09-15, the overlay was inert. The packaged file is
  the only route that works. Do not re-litigate.
- **`org.kde.plasma.folder` contains no QML** — it is a metadata shim whose `X-Plasma-RootPath` is
  `org.kde.desktopcontainment`. Patch *that*, whatever `appletsrc` says.
- **plasmashell does not see layer-shell exclusive zones.** `availableScreenRect` comes from its own
  Plasma panels only. "Maximized windows clear the bar" proves nothing about the desktop.
- **`ItemGeometries-<W>x<H>` is the desktop-WIDGET layout, not icon positions.** Do not explain an
  icon-placement fault with it again.
- **Changing the desktop's margins without changing `AppletsLayout.relayoutLock` freezes widget
  relayout forever.** They read the same rect on purpose (DECISION 111).
- **Anything run from a pacman hook has `HOME=/root`.** A config read through `Path.home()` silently
  becomes "all upstream defaults" — a plausible wrong answer rather than an error. Resolve the real
  user or refuse. **`REPO = Path(__file__).resolve().parent.parent` breaks for a copy in
  `/usr/local/bin`** (it resolves to `/usr/local`).
- **`console.info` in QML can be filtered out of the journal; `console.warn` cannot.**
- **A warning that is only a line of prose in a log is not a warning.** Non-zero exits and a
  `luminos-verify` check are what make a problem observable.
- **A health check pinned to one delivery path breaks when the delivery moves.** Check every place
  the thing can legitimately live.

### Caelestia / the bar
- **`~/.config/quickshell/caelestia-kwin/` is 271 symlinks into pacman-owned
  `/etc/xdg/quickshell/caelestia/`** — deliberate, so an upgrade fails loudly instead of shipping a
  stale file. **Never edit a file in that tree in place** — edit
  `scripts/luminos-caelestia-kwin-overlay` and rebuild.
- **The bar's width is config, not code** (DECISION 110). `luminos-verify [4b]` prints the number.
- **`Config.border.thickness` is a shell-wide lever, not a bar lever** — it also sets the launcher
  and dashboard edge-indicator heights. Do not zero it.
- **`shell.json` is user config the Caelestia settings UI writes back.** Copying a repo file over it
  silently reverts Shawn's GUI toggles. Merge specific keys.
- **Look for a `.bak*` sibling BEFORE theorising about a wrong config value** — and read its *name*,
  which carries the author's intent. Paid off twice in two days.
- **Live KDE configs drift from `config/` in git with nothing to notice.** `diff` the pair first.
- **`0` is not "never" in `powerdevilrc`; `-1` is.** Any `*IdleTimeoutSec=0` is a zero-second
  timeout (BUG-159, now AGENTS.md §11). **Restarting `plasma-powerdevil.service` mid-dim leaves the
  panel dark** — the dimming ratio is process state; re-assert brightness.

### GPU / power
- **`gpu_busy_percent` is amdgpu-only; there is no NVIDIA equivalent**, nor `device/hwmon/`.
  Anything reading them for the 4050 silently gets 0 — this already cost BUG-157. Only honest
  source: `nvidia-smi --query-gpu=utilization.gpu`.
- **`card1` is the RTX 4050, `card2` is the 780M.** The numbering is not the trap; assuming the
  *attributes* are the same on both is.
- **One constant used as both a drop threshold and a re-raise gate is a latch, not a limit.** Cost
  BUG-157 and BUG-161. Adding a threshold to `luminos-power` means adding its pair at the same time.
- **Changing the asusctl profile WAKES THE dGPU** via ACPI NVPCF (~60 s at ~2 W per switch).
  **Never call `asusctl profile set` directly — use `setProfile()`.** (`asusctl profile -p`/`-P` do
  not exist; the subcommand is `asusctl profile get`.)
- **"Nothing is holding the GPU" is NOT "nothing is waking it."** An fd scan finds only *userspace*
  holders; BUG-161's wake came from firmware. Empty holder list + awake card ⇒ go to the tracepoint.
- **`/sys/kernel/tracing/events/rpm/rpm_resume` answers "who resumed this device."** tracefs is at
  `/sys/kernel/tracing`. Set `filter` or the iGPU floods the ring; the `trigger` is **separate**.
  Read the **tail** — stale lines above nearly convicted `nvidia-powerd`.
- **`nvidia-powerd` holds `/dev/nvidia0` + `/dev/nvidiactl` for all of uptime by design.** Do not
  convict it without an A/B.
- **A masking bug can hold a second bug's symptom at exactly zero.** When a fix is followed by a new
  report in the same subsystem, check whether it is a regression or an *uncovering* — `git log -S`
  on the suspect constant dates it. **Instrument the rate, not just the event** — BUG-161 hid four
  months because only the *frequency* was wrong and nothing counted.
- **"The GPU is slow" starts at `journalctl -b 0 -u luminos-power -g 'GPU TGP'`**, then
  `asusctl profile get`, then `nvidia-smi -q -d PERFORMANCE`. Not a one-shot nvidia-smi at idle.
  **`SW Thermal Slowdown: Active` at idle is a sampling artefact** — the query wakes the card.
- **Never add a bare `runCmd`/`exec.Command` for nvidia-smi in luminos-power** — use `nvidiaQuery`,
  `nvidiaRead` or `nvidiaCtl`. A **root** nvidia-smi reopens `/dev/nvidia-uvm` to 0666 by itself
  even for a read-only query (BUG-146), silently.

### Security, controllers, web surface
- **Changing *when* a machine sleeps changes *what a resume exposes*.** `Autolock=false` +
  `LockOnResume=false` were harmless only because the box never resumed.
- **"The port is firewalled" answers one threat model and hides another.** nftables closed
  `luminos-ram`'s LAN path, but `Access-Control-Allow-Origin: *` let any website make *your own
  browser* read `127.0.0.1:9091`. No firewall rule touches a request originating on this box.
- **`getfacl /dev/hidraw*` is the first check for any "controller not supported" report**, not
  `/dev/input` — evdev/joydev get `uaccess` from stock rules and look healthy while hidraw is
  locked. **Do not hand-write a udev rule or `sdl_gamecontrollerconfig`** (DECISION 101).
  `SDL_GameControllerRumbleTriggers` "not supported" on a DualSense is *correct* — that is the Xbox
  trigger-rumble API; adaptive triggers use `SDL_SendGamepadEffect`.
- **Screenshot the web surface through Caddy, never `127.0.0.1`** — the loopback port skips the
  proxy, the TLS and the token injection. **`server/SPEC.md` is a different project**; the web spec
  is `server/docs/WEB_UI_PROMPT.md`. Read
  `## ⚠️ Read these before touching the web surface` in `git show 4dd0d7ae:HANDOFF.md`.

### Process / tooling
- ⚠️ **Assume concurrent writers on this repo.** On 2026-09-16 two sessions wrote `server/*.md` and
  `HANDOFF.md`. Re-read a file immediately before writing it; never hold a copy across turns.
- **A Cowork session's `device_bash` has ZERO network and is not a shell on the desktop** — only the
  connected folders under `$HOME/mnt/`, no systemd, dbus, Wayland or `/etc`. **It cannot reach the
  media server at all.** Anything needing the live session or the server must run on the G14.
- **`luminos-notes.sh` cannot be written from a Cowork session** — sqlite3 gets `disk I/O error`
  over the folder bridge and leaves a stale `.notes.db-journal`, after which even reads fail. The
  copy-out/copy-back dance is **unsafe with a concurrent writer** (an insert between the two is
  silently destroyed). Run it on the box.
- **`code-review-graph` does not index extension-less scripts** — `file_summary` on
  `scripts/luminos-caelestia-kwin-overlay` returns 0 nodes because there is no `.py`. Most of
  `scripts/` is invisible to it. Not a broken graph, a blind spot.
- **MCP `mempalace` and `code-review-graph` ARE reachable from Cowork** (as
  `mcp__remote-devices__…`; may be deferred — load with ToolSearch). An older note said otherwise.

---

## Files touched this session

| file | change |
|---|---|
| `server/scripts/luminos-roku-compat` | `ass`/`ssa` out of `TEXT_SUBS` into new `BURN_SUBS`; `verdict()` reports `subs:<codec>(burn-in)`; `JF_LOG_DIR` probed not hardcoded; `observed()` reads only `jellyfin*` logs. Mode 755. |
| `server/scripts/luminos-fix-e7` | mode 755 (was `700`-ish `rwx--x--x`). Unchanged otherwise. |
| `server/STATUS.md` | BUG-164 row rewritten with the measured result and both corrections |
| `server/DECISIONS.md` | **DECISION 114** appended |
| `HANDOFF.md` | **reset** (610 → this), per AGENTS.md §0.2 |
| **server** `/usr/local/bin/luminos-{roku-compat,fix-e7}` | installed, mode 755 |

**No media file was modified on the server.** `/srv/external/_roku_pre_ac3_originals/` is empty.

**Committed as its own change** — the working tree carries unrelated modifications
(`scripts/chrome-luminos`, `scripts/jobhunt/*`, `scripts/luminos_moe_offload.py`, the untracked
initramfs tree, `_to_delete/`). **Never `git add -A` in this repo.**
