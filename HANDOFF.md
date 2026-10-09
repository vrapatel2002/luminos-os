# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-09 19:00 — Response 3

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now (2026-10-09, Response 1) — "@ can't mention project files" — FIXED for this chat
Shawn: typing @ no longer lists repo files (@AGENTS.md, @HANDOFF.md) like it used to.
Measured: `get_device_info` → `connectedFolders: []`. The @ picker only lists files in folders
connected to the conversation. Two causes stacked: (1) **BUG-187's re-login (09-24) minted a new
device row and folder grants are per row** — they did not carry over; (2) **Cowork merged into
Claude** (support.claude.com/en/articles/16761823): a claude.ai Project ("Luminous") only knows local
files if a local folder is in its context or granted to the chat. Fix: granted `~/luminos-os` to this
chat (`device_request_folder_access`, Shawn approved). **For new chats:** add `~/luminos-os` to the
Luminous project's context once ("Add a local folder"), or grant it per chat. Not yet confirmed by
Shawn that the @ list now shows files.
**Response 2 — root cause found: two different projects.** Desktop app's local projects ("spaces")
live in `~/.config/Claude/local-agent-mode-sessions/<acct>/<org>/spaces.json`. Space **`luminos-os`**
= folder `/home/shawn/luminos-os` (created via "pick a folder") — **never migrated** to the account.
The chat Shawn opened is in **`Luminous`**, a claude.ai account project (4 Vela docs, `sync_sources: []`,
no folder). Space `Games` *was* migrated (`migration.stage: complete`). So @ had nothing to list.
Fix options: work in the `luminos-os` project, or add `~/luminos-os` as a local folder in Luminous.
**Response 3 — consolidating onto `luminos-os` (Shawn's choice).** Copied Luminous's 4 docs + its
project memory to `gameos/docs/claude-project/` (gameos `231c243`); preferences pointer added to
`CLAUDE.md`. **Left for Shawn in the app:** move Luminous chats into `luminos-os` (chat dropdown →
move), then **Archive** Luminous (reversible) — delete only later. Luminous's project memory lives in
the account and may go with the project; the copy above is the backup.
Earlier the same chat (Vela/tooling, not Luminos — nothing on Luminos changed):
- `vela-crashd` crash/freeze reporter built and installed in `/vela.img` → `gameos/docs/tracks/CRASH.md`
  (Control froze 10-09 12:30:51, cause unknown, BOARD #18).
- `/build` skill (`~/.claude/skills/build/SKILL.md`, backup `.prev-20261009`): Opus 5.5 high for code
  and tests, Fable 5.1 for review/escalation, Sonnet only for mechanical edits. Sonnet workers looped at
  the 32k output cap on refactors; Opus did the same jobs in 3–5 min.
- Local build dashboard: `~/builds/build-monitor` (`python3 monitor.py` → 127.0.0.1:8765).

## Aim (Response 1, chat of 09-26) — fans maxed at idle, BUG-190, FIXED
Shawn: fans spinning hard, not hot. Measured 21:52: Tctl 37 °C, cpu/gpu/mid 6900/6800/7500 RPM,
Balanced curve read back as the **burst** curve (255 from 40 °C). Cause: a burst started on Balanced
at boot, AC unplug switched to Quiet mid-burst, exit restored only Quiet; replug at 21:47 loaded the
stale Balanced curve. Fixed in `cmd/luminos-power/main.go` (`thermalBurstProfiles` +
`restoreBurstProfiles()`, also on beast-mode cancel), rebuilt, installed, restarted → fans ~2000 RPM.
Backup: `~/.luminos-backups/luminos-power.bak-bug190-20260926`. Docs: BUGS.md BUG-190, AGENTS §15
row, notes + brain. Not yet seen: a real burst → unplug → exit cycle on the new binary.
Pre-existing: `gofmt -l` flags `cmd/luminos-power/fan_control.go` (not touched).

## Aim (Response 4, previous chat) — Roku TV lag = the TV's Wi-Fi link, read-only
Shawn: only the Roku TV (Philips 65PUL7973, 192.168.2.18, Jellyfin Roku 3.2.3) lags; phone and
others fine. Measured 21:40 from the server: TCP send queue to .18 backed up ~4 MB, **36,717
retransmits** on the stream socket, ping to .18 **65–1616 ms (avg 486 ms)** vs 2 ms router.
Delivery rate ~30 Mbit/s against a direct-played file averaging 26.6 Mbps with peaks to ~38
(Ozark 2160p files are all 26–28 Mbps). Server side healthy. Fix options for Shawn: Ethernet to
the TV (best), move router/5 GHz, or cap Roku app quality so Jellyfin transcodes to ~10–15 Mbps.
Nothing changed.

## Aim (Response 3) — "stream lagging", READ-ONLY (Shawn: do not fix)
21:38 findings: server is NOT the bottleneck — load 0.21, enp2s0 up at 1000 Mb/s, last transcode
ran at **5.17x** realtime, dv-fix finished 15:36 (E03 now 11.3 GB, 26.6 Mbps, no DV — same
bitrate class as E04 at 28.4). Two clients on E03: **Jellyfin for Android from 100.77.43.36
(Tailscale = off-LAN)**, Transcode `ContainerBitrateExceedsLimit` at 2560w / 12.7 Mbps; and Roku
DirectPlay, stopped/restarted at 21:31 and 21:37 around 42 min. Likely cause: remote link
(home upload / phone network) can't carry 12.7 Mbps; Roku side = its own wifi pulling 27 Mbps
direct. Not verified: home upload speed, Roku wifi. Post-dv-fix E03 colour not yet eyeballed.

## Aim (Response 2) — Ozark S02E03 violet picture, BUG-189
Dolby Vision **Profile 5** (only P5 file in Ozark — the lone WEBDL). Same as DECISION 95.
`luminos-dv-fix` started 13:17:32 on the server as unit **`dv-fix-ozark-s02e03`**
(`journalctl -u dv-fix-ozark-s02e03`; temp file `Season 2/.dvfix.<pid>.mkv`). Original →
`/srv/external/_dv_p5_originals/`. ETA ~2 h at 0.463x, **much slower while any Jellyfin
transcode runs** (shared iGPU; measured ~0.1x with Shawn still streaming E03).
After it finishes: confirm `ffprobe` shows bt2020/smpte2084 and no DV, re-warm subs for item
`4b95fa4a6d35b193a852e1023cf6bd88`, Shawn re-watches E03.
Jellyfin transcode does NOT rescue P5 here: `EnableTonemapping=false` → `setparams=bt709`.
Open options (Shawn's call): Jellyfin tonemapping (needs Intel OpenCL runtime), and an
on-import P5 scan.

## Aim (Response 1) — Ozark subtitles
**Ozark subtitles on the media server — BUG-188, DECISION 132. Fix applied, warm-up running.**
Symptom: every episode has subs, but they load "sometimes", and the next episode never does.
**Cause: cold embedded-subtitle cache, not missing subs.** All 20 files have English `subrip` at
stream index 2. Jellyfin 10.11.11 extracts on first request by reading the whole 10–20 GB file off
the 5400 rpm spindle: **170 s (S01E07), 205 s (S01E08)** in `/var/log/jellyfin/jellyfin2026092{3,4}.log`.
The Roku gives up first. Watched eps were warm (6/20), everything unwatched cold (14/20).
**Why it recurred:** DECISION 113's `luminos-subtitle-warm` timer was written 2026-09-16 *without a
route to the server* and **never installed** (unit not found on the box).

## State — what is DONE
- Installed on luminos-server: `/usr/local/bin/luminos-subtitle-warm`,
  `/etc/systemd/system/luminos-subtitle-warm.{service,timer}`; timer **enabled**, next 04:00 daily.
- Started transient unit **`ozark-warm-once`** (`/usr/local/bin/ozark-warm-once`) at 20:43 —
  warms the 14 cold Ozark eps in watch order (S01E09, E10, E01, E02, S02E01…E10), ~3 min each,
  then runs `systemctl start luminos-subtitle-warm.service` (full library).
- Docs: `docs/BUGS.md` BUG-188, `server/DECISIONS.md` DECISION 132 (options A–D),
  `server/STATUS.md` subtitle row, `luminos-notes.sh add [BUG]`, `luminos-brain log`,
  MemPalace drawer (luminos-os/decisions).
- **No media file modified, nothing re-downloaded** (Shawn's constraint).

## State — IN PROGRESS
- `ozark-warm-once` running. Check: `ssh … 'sudo journalctl -u ozark-warm-once -o cat'` — one
  `http=200 Ns` line per episode. Then `journalctl -u luminos-subtitle-warm` for the full sweep.

## Next steps (ordered)
1. Confirm all 20 Ozark eps show `2.srt` in the cache (the check script is in BUG-188's shape:
   `/var/lib/jellyfin/data/subtitles/<id[:2]>/<uuid>/2.srt`).
2. Shawn confirms on the Roku with S01E09 → E10 back-to-back.
3. **Shawn's call:** Option B (English `.en.srt` sidecars next to each MKV, survives cache wipes)
   and/or a Sonarr/Radarr **On-Import** hook so same-day imports are warm immediately.
4. After the one-off finishes: `sudo rm /usr/local/bin/ozark-warm-once` (transient unit disappears
   on its own).
5. Still pending from 2026-09-24: `main` is ahead of origin, unpushed on purpose — Shawn's call.
6. Parked wallpaper work — see below.

## Key decisions & constraints
- **Do not re-download media to fix subtitles** (Shawn, 2026-09-25). Embedded tracks are correct.
- **AGENTS.md §0.2 / Rule 12:** "no changes" scopes to code/config/system state; HANDOFF + §13 docs
  are written every turn.
- **Never restart Claude Desktop from a bare agent shell** (BUG-187) — use
  `scripts/luminos-claude-restart` or the KDE menu.
- **`pkill -f` is banned for broad patterns** — Cowork's sandbox is a `qemu-system-x86_64`.

## Gotchas / things NOT to redo (new this turn)
- **A timer in the repo is not a timer on the box.** Check `systemctl status <unit>` on the server
  before believing any server/ STATUS row that says "timer".
- **`IOSchedulingClass=idle` on `luminos-subtitle-warm.service` throttles nothing** — the read is
  done by Jellyfin's own ffmpeg; the script only issues HTTP requests.
- One Jellyfin request extracts **all** text tracks of a file in one pass — warm index 2 only.
- ⚠️ The one-off `ozark-warm-once` passes the Jellyfin token on curl's command line, so it is
  visible in `ps` on the server while it runs (and appeared in this session's tool output). Single-
  user box, low risk, but don't copy that pattern — the Python script uses in-process headers.
- Host-shell calls must stay well under 60 s; a long `ssh … grep` over logs timed out once.
- Server access: `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`, `sudo -n` works.

## Parked — the wallpaper launcher idea (unchanged, from 2026-09-21)
**Make the wallpaper the launcher**: Starfield's stars become clickable app icons. Verdict from the
read-only assessment: possible, graphics half easy, **input half is the whole risk**.
1. The desktop containment eats left clicks on empty desktop —
   `~/.config/plasma-org.kde.plasma.desktop-appletsrc` `[Containments][30]
   plugin=org.kde.plasma.folder`; `FolderView.qml:243` accepts `Qt.LeftButton` even with
   `hoveredItem === null`, above the `WallpaperItem`.
2. **`WebInteractive` is SUSPECT, not proven.** It is `true` live and `docs/wallpaper/SPEC.md` §0
   asserts clicks already reach the page, but **nothing has ever observed one**. Same shape as
   BUG-173/185. Do not build on it until a click is seen.
3. Escape hatch: `main.qml:429 FolderViewLayerLoader` is `active: root.isFolder…`; switching the
   containment to `org.kde.plasma.desktop` never creates that layer or its click grab. Cost: desktop
   icons and rubber-band selection.
4. **Do NOT bolt icons onto today's Starfield** — it is the `.js` Canvas path, **41.1 % of a core**
   (BUG-178), no hit-testing, no themed icons. Write a native `scenes/Starfield.qml`: `ShaderEffect`
   far field (6.6 % measured) + ~15–30 app stars as real `Item`s with `Kirigami.Icon` + `TapHandler`.
   Likely **cheaper** than what it replaces.
5. App list + launching already exists: `org.kde.plasma.private.kicker` `RootModel`/`AppsModel` with
   `trigger()`. ⚠️ **private import** — DECISION 26 rung L3. Fallback `kstart --application <id>`.
6. Two UX traps: accidental launches (arm the icons on `KWindowSystem.showingDesktop`, Meta+D) and
   keyboard focus (the containment takes none; v1 is click-only, **Esc always releases**).
7. **SECURITY — the lock screen runs the same plugin** (DECISION 77/127). Any launcher key joins the
   greeter withhold list and selftest **[7]** must assert it.
8. Option B if the containment fights us: a Quickshell layer-shell window on the background layer.
**Next action there is a PROBE needing Shawn's nod:** ~25-line scene with a `TapHandler` that logs
to the journal, set as `QmlScene`, tested under Folder View vs plain Desktop containment. Revert is
one `kwriteconfig6`. **Restart plasmashell after deploying — BUG-171: a deploy is not a load.**

### Standing wallpaper aim, unchanged
Lively Wallpaper parity for the KDE live wallpaper, without Chromium. §3.6 (games through a nested
compositor) is the largest unfinished item. `livelySystemInformation(json)` and
`livelyAudioListener(float[])` are still unimplemented; **only Rain is confirmed rendering** of the
five web packages. Lock screen still shows Rain while the desktop is Starfield — selftest's 1
failure, and it is correct. Docs: `docs/wallpaper/{SPEC,CONTRACTS,BUILD_LOG,VERIFY}.md`.

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
**2026-10-09:** `HANDOFF.md`, `.notes.db` (notes + brain log), MemPalace luminos-os/decisions drawer. No `/etc`, package or service change on Luminos.
**Repo, this turn:** `docs/BUGS.md` (BUG-188), `server/DECISIONS.md` (DECISION 132),
`server/STATUS.md`, `HANDOFF.md`, `.notes.db`.
**luminos-server (not the G14):** `/usr/local/bin/luminos-subtitle-warm`,
`/etc/systemd/system/luminos-subtitle-warm.{service,timer}` (enabled),
`/usr/local/bin/ozark-warm-once` (one-off). Jellyfin cache `/var/lib/jellyfin/data/subtitles` grows.
**G14:** nothing changed — no `/etc`, no package, no service. AGENTS.md §9 untouched.
Previous handoff (Claude Desktop, BUG-187): `git show HEAD:HANDOFF.md`.
