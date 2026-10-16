# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-10-15 19:00 — Response 6 (heat/Chrome chat)

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now (2026-10-15 19:00, heat chat R6) — exact reason for the dGPU wakes FOUND (read-only); fix choice is Shawn's
Shawn: "find why it's firing, then we decide the fix". Answer (BUGS.md, BUG-198 addendum): idle on AC with a full battery → 0 wakes in 6.5 min.
Every wake = a power-setting change → EC/BIOS recomputes the GPU's power share → Notify(PEGP or NPCF, 0xC0) → nvidia driver wakes the card ~20 s
(upstream NVIDIA #1300/#1299). Senders here: luminos-power profile switches (19 in 27 h), fan-curve applies (11), bursts (6), nvidia-smi at
daemon start. NEW **BUG-200**: beast-mode exit counters can desync, so it stays stuck in Performance (seen after my heat test; I restored it by restarting luminos-power).
(Notes/brain entries written at 19:00 said "BUG-199" — that number belongs to another chat's lock-screen bug; the beast-mode bug is BUG-200.)
All probes/dynamic-debug removed. Decompiled tables in .scratch-acpi (git-excluded); decompile done off-box.
NEXT: Shawn picks a fix (luminos-power write reduction + BUG-200, Integrated mode, or a DKMS patch).

## Previous aim (2026-10-15 18:50, heat chat R5) — WHY the firmware wakes the dGPU: mapped + proven live; fix choice is Shawn's
Decompiled DSDT/SSDTs (copy in .scratch-acpi/, git-excluded; decompile done off-box). Every wake path = `Notify(\_SB.NPCF, 0xC0)`
("platform power budget changed" to NVIDIA's NVPCF device) → the nvidia 610.57 open module resumes the card. Senders:
A) **asusd WMI calls** (DSDT WMNB): 0x00110024 = CPU fan curve (fires on `asusctl fan-curve --enable-fan-curves true`), 0x00120098
(NV dynamic boost), 0x001200C0 (NV temp target), and platform-profile switches. PROVEN live with kprobes on acpi_ev_queue_notify_request
+ nv_acpi_notify_event: a profile flip (thread tokio-rt-worker = asusd) and a no-op fan-curve re-enable (zbus thread) each → NPCF 0xC0 → rpm_resume.
B) **EC queries on its own**: _QA8, _QD4 (thermal table change, notifies twice), _Q7A/_QA9 (PEGP), _QBC (DNOT). GPIO pins 5/16 → PEGP 0x81 never fired (0 IRQs).
luminos-power today: 3 bursts + 3 restores = 6 fan-curve enables = 6 wakes. Probes + rpm trace removed afterwards. Profile restored to balanced.
Options put to Shawn: (1) luminos-power stops re-sending unchanged fan curves/profiles + drops the 52 °C 100 % burst (also matches his
"never max fan at 50-55 °C" preference); (2) Integrated mode (dgpu_disable=1) when no GPU job runs: card powered off at the firmware, no
notify can reach it; needs a switch to Hybrid before HIVE/games; (3) ACPI SSDT override to drop the NPCF notifies: not recommended,
it blinds NVIDIA power limiting when the card IS used. cmd/ is untouched pending his choice (§11).

## Previous aim (2026-10-15 18:25, heat chat R4) — BUG-198: dGPU wake cause PROVEN + YouTube runaway guard BUILT (Tab Sleeper 3.2)
Shawn: "why is the NVIDIA card waking, it should be cold until something uses it" + "why the loop, make sure it never happens again".
**dGPU, proven by an rpm_resume stacktrace trigger:** 18:12:45 wake = acpi_ev_notify_dispatch → rm_acpi_notify → nv_indicate_not_idle (ASUS
firmware ACPI notify, NVPCF class like BUG-161), fired as CPU went 74→86 °C with no profile change; awake 22 s. Chromium launch / sensors /
lsof / asound reads all tested, none wake it. Heat → firmware notify → wake. The tracer was armed only for this session and is now OFF.
**Loop:** YouTube page leak in long autoplay → main thread pegged; exact JS not recoverable. **Guard** in scripts/chrome-tab-sleeper
(content.js + background.js handleRunaway): heap > 600 MB, or long tasks ≥ 50 % for 2×60 s → reload at the same second; max 1 per tab per
10 min; runawayLog in storage.local. Live tests 3/3 PASS (test-runaway-live.mjs heap|busy|none). **NEXT (Shawn): chrome://extensions → Luminos
Tab Sleeper → Reload.** If it ever logs "gave-up", read runawayLog: that's the evidence for a deeper fix.
⚠️ My live tests briefly heated the laptop to 88 °C (two Chromiums + an injected burn) — that was me, not him.

## Previous aim (2026-10-15 17:45, heat chat R3) — "still hot after turning the blur off" — READ-ONLY, explained
17:16 measured: 55 °C, 16 W. Chrome YouTube tab renderer (pid 32847) at 118 % of a core: **main JS thread ~100 %**, Compositor 14 %,
Media 1 %, so it was neither decoding nor drawing. RSS grew 989 MB → 1.4 GB in ~5 min, then it dropped on its own to 0 % / 535 MB when the
playlist moved on. Ambient light is still enabled in Chrome, but its own switch is `enabled false`; Luminos Ambient (DECISION 140) is
NOT installed. Bench run4 (same playlist aSugSGCC12I, throwaway Chromium, 30 s): plain YouTube 60.2 %, Ambient light switched off
49.3 % → the switched-off extension adds nothing measurable. **Verdict: a runaway inside the YouTube page itself, cause not identified**;
a 30 s fresh-browser run can't reproduce a build-up. dGPU: holderless kworker resumes of 01:00.0 + 01:00.1 (HDMI audio function;
WirePlumber holds /dev/snd/controlC0), awake only ~5 % of uptime → minor, not chased.
⚠️ My benchmark (amb-bench4) ran 17:18–17:35 and caused part of that hour's 72–86 °C readings; it's stopped and the /tmp profiles are removed.
After the stop: 45.6 °C, 7 W, his YouTube still playing (renderer 16 %).
If it recurs: Chrome Task Manager (Shift+Esc) shows the tab; catch it live and check its main thread.

## Previous aim (2026-10-12 19:10, remote-stream chat R1) — phone streams stall on mobile data, BUG-194, READ-ONLY
Shawn: server "not very responsive", streams don't load over mobile data; wants a list to fix (/build — diagnosis only, no workers spawned, nothing built yet).
**Found (all measured on the server):** (1) Pixel 9 Tailscale peer: 90 DERP-relay contacts, **0 direct** in 10 days. (2) Jellyfin
transcoded a 4K HDR remux to the phone at **54.8 Mbps** (`RemoteClientBitrateLimit=0`); app quit after 38 s. (3) nftables `policy drop`
has no accept for udp 41641 → inbound hole-punch + UPnP/NAT-PMP replies dropped (`portmap=` empty). (4) Dual NIC .61/.62 both on
41641 → STUN saw 2 public ports, `varies=true` → home looks like hard NAT. (5) Not the cause: server load 0, encode 3.07x, upload ~100+ Mbit/s.
**R2 DONE — DECISION 142:** Shawn rejected "just use :8096". Real fix: Jellyfin `KnownProxies=127.0.0.1` + `LocalNetworkSubnets=192.168.2.0/24`
+ `RemoteClientBitrateLimit=8000000` (backups `*.pre-bug194`). Verified 6 paths via `/System/Endpoint` (tailnet via Caddy now remote, forged XFF ignored,
LAN + Roku still home) and PlaybackInfo: tailnet via Caddy → 6.46 Mbps video. Shawn should replay something on mobile data to confirm by eye.
**Remaining (not applied):** A) `RemoteClientBitrateLimit` ~8 Mbps (one setting, biggest win). B) nftables `udp dport 41641 accept`
(+ allow router UPnP/PMP replies, or a router UDP 41641 port-forward). C) Tailscale bound to one NIC / one public port. D) Enable tonemapping (OpenCL) for HDR remote transcodes.
Each server change: 300 s auto-revert, re-check `tailscale status` shows `direct` for the phone while on mobile data.

## Previous aim (2026-10-11 19:35, heat chat R2) — Luminos Ambient built (DECISION 140), waiting on Shawn's install click
R1: hot hour (52–61 °C) = YouTube in Chrome. R2 (/build): Shawn is sure it's "Ambient light for YouTube"; wants better code + an
audit of heavy/loose-end code.
**DONE:** `docs/ambient/AUDIT.md`: per video frame it re-uploads the full 1080p frame into WebGL + generateMipmap, then renders ~7
layers and re-blurs. Also lists loose ends: fps passed as ms to setTimeout, cancelAnimationFrame(true), a page-wide observer never
disconnected, etc. **Our replacement** `scripts/chrome-luminos-ambient/` (295 lines, 80 tests): 16-px sample → ≤64-px canvas
stretched by the compositor, 6 updates/s, stops when paused/hidden/fullscreen/off-screen/mini-player/disabled.
**Measured** (tests/ambient/bench.mjs, throwaway Chromium, maximized): Ambient light +18.3 % of a core over plain YouTube; ours at
6/s no measurable cost; ours at 12/s +4.7 %. Look: ours is softer/greyer than his spread-76 Ambient light.
**NEXT (Shawn):** chrome://extensions → Developer mode → Load unpacked → `~/luminos-os/scripts/chrome-luminos-ambient`, then turn
"Ambient light for YouTube" OFF. Then optionally re-measure in his real Chrome (the R1 MPRIS method: Play → /proc delta → Pause;
the mute via pactl did NOT work, so audio plays).
Gotchas: host-shell calls >60 s die → run bench via `systemd-run --user` with XDG_RUNTIME_DIR+DBUS set (without them systemd-run
fails silently); the worker VM runs on this laptop, so PPT readings are polluted while agents run. `--load-extension` works in
Chromium 153, not branded Chrome. Bench PNGs are git-excluded (.git/info/exclude). Upstream copy in `.scratch-ambient/` (excluded).

## Windowstyle (Nexus look) — current state, 2026-10-12 21:00, windowstyle chat R12
Goal: every KDE window looks like Caelestia Nexus (spec artifacts: "System Settings in Nexus Style" =
`docs/windowstyle/mock/nexus-replica.html`, "Sub-page Layouts" = `docs/windowstyle/mock/subpages.html`).
**Live:** KWin decoration `luminos-kdecoration-chromeos 1.0.0-2`; forks qqc2-desktop-style 6.30.0-1.6, kirigami 6.30.0-1.6,
kirigami-addons 1.13.1-1.2, kcmutils 6.30.0-1.1 (new), systemsettings 6.7.5-1.6, darkly 0.5.40-1.2 — all `packages/*-luminos/`, warn-only
hooks `luminos-<pkg>.hook`. `scripts/luminos-windowstyle-check` = 31 PASS (live System Settings probes SKIP while Shawn's instance runs).
DECISIONS 138–141 + 143, BUGS 193, 195–197. Sub-pages = Shawn's edge-drawer idea (left = all settings, top = search, right = page sections),
motion 180 ms no overshoot. Test aid: `LUMINOS_SS_OPEN_DRAWER=left|top[:q]|right systemsettings`.
**Phase 6 DONE (R14, DECISION 144):** approved prototype `docs/windowstyle/mock/popups.html` built for real — darkly 0.5.40-1.5 (BUG-196 fixed; QtWidgets menus/tooltips/scroll bars), qqc2 6.30.0-1.8, kirigami 6.30.0-1.8 (InlineMessage, PlaceholderMessage), plasma-desktop 6.7.5-1.2 (Keyboard empty states; repacked Arch binary + rebuilt kcm_keyboard.so, rebuild steps in its PKGBUILD), semantic colours. Checker 40 PASS. Workflow now: prototype → Shawn approves → build → checker → review.
**R15 (10-15, read-only):** BUG-199 lock-screen wallpaper black after lid-open — greeter crashes at suspend entry, the restarted greeter's WebEngine gets no GPU (WebGL disabled) → Rain can't render. Options listed to Shawn; waiting on his pick.
**R16 (10-15):** BUG-199 (renumbered from 198) crash catcher installed (DECISION 145): `/usr/lib/kscreenlocker_greet` is a wrapper, real = `.luminos-real`; reports in `~/.local/state/luminos/greeter-crash/`. `luminos-greeter-catch status|remove`. Waiting for Shawn to reproduce (lid close/open) → read newest crash log → fix.
**R17 (10-15):** BUG-201 fixed — live-wallpaper settings centred under the Wallpaper type card (config.qml alignment).
**R18 (10-15):** BUG-202 fixed — left/top/right drawer open-close loop (systemsettings 6.7.5-1.6).
**Known limits:** Dolphin row height / group lines are Dolphin's own; no red "danger" items in plain QMenu; Keyboard empty-state shortcut text not runtime-verified.
InlineMessage, menus/tooltips/scrollbars per Components sheet; systemsettings patch at its 520-line budget.
**Rule:** after ANY Plasma/KF/Qt upgrade rebuild all six forks + the decoration, then run the checker. Never `git add -A` (parallel chats share this tree).

## Previous aim (2026-10-10 12:00, cloud chat R7) — host-shell MCP "Failed" = BUG-192, FIXED
Settings → Local MCP servers showed `host-shell` **Failed / Server disconnected**. Log
`~/.config/Claude/logs/mcp-server-host-shell.log` 15:39:09Z call id=31 → `TypeError: can only concatenate
str (not "bytes") to str` → server exited 15:40:07. Cause: `~/.local/share/claude-host-shell/server.py` (not in
git) — on a command **timeout** Python returns partial output as bytes even with `text=True`, and `tools/call`
had no try/except, so one timed-out command killed the server. Fixed (decode, `killpg` on timeout, per-call
error handling), tested over stdio. Backup `~/.luminos-backups/claude-host-shell-server.py.bak-20261010`.
**Running server PID 28124 (started 10:57) still has the OLD code** — the app must respawn it: restart the
app via `scripts/luminos-claude-restart` / KDE menu, or toggle the server in Settings.
Suspicion, not proven: the timed-out call may be the command the 11:11 chat saw refused as "Remote Shell
Writes" (a permission prompt waiting until timeout).
**@ after the upgrade:** now offers only artifacts. Research found no official doc of the change; likely the
Chat/Cowork merge + Oct 6 cloud Cowork tasks (Code tab docs: "@mention is not available in cloud sessions").
Workarounds: Cowork (not Chat) + new task; type file paths; or **Code tab → Local → ~/luminos-os** for real `@file`.

## Previous aim (2026-10-10 11:11 chat, Response 1) — verify the Claude Desktop upgrade held
Shawn's prompt was only "read and follow AGENTS.md + HANDOFF.md" — no new task, so the open
items were checked read-only.
**Verified 11:15 on the G14:** `pacman -Q claude-desktop` = `2.31226.1-1`; main PID 27438 running;
`~/.config/Claude/Crashpad/completed` = 0 dumps; `ant-device-registry.json` sha256 = `079c414f…`
= same as before the upgrade → **no re-login, no foreign_device reset**. This chat's own device
bridge (folder mount + host-shell) worked on the new build — the bridge is fine.
**Still only Shawn can confirm (in the app):** "Update Claude to move this project" banner gone,
and @ in the `luminos-os` project lists repo files.
**Media server, verified 11:16:** `ozark-warm-once` and `dv-fix-ozark-s02e03` both inactive
(finished). `luminos-subtitle-warm.timer` fires daily ~04:29; last run: **592 ok, 0 failed, 730
files in cache** → BUG-188 warm-up is DONE. **Leftover:** `/usr/local/bin/ozark-warm-once` (has
the Jellyfin token in it) is still on the server — `sudo rm` was **blocked by the session's
permission check**; needs Shawn's OK or Shawn to run it.
**Permission note:** mid-turn the host-shell refused the server `rm` and one read-only `find` ("Remote Shell Writes"); notes + brain log DID go through afterwards.

## Previous aim (10:55, earlier chat) — Claude Desktop upgraded to 2.31226.1
**Why:** @ file mentions + "move project" were dead because the app was `1.52386.6-2`, a major version
behind; the Linux app never self-updates (BUG-191, DECISION 133). Earlier diagnosis (10-09/10): @ only
lists files in folders connected to the chat; BUG-187's re-login had reset folder grants; space
`luminos-os` (folder project) vs account project `Luminous` (consolidated onto `luminos-os`, Luminous
docs copied to `gameos/docs/claude-project/`; Shawn still to move chats + archive Luminous).
**DONE 10:55–10:58:** PKGBUILD reviewed (only the official `.deb` from downloads.claude.ai, SHA256
pinned, + its own launcher script; no new deps). Rollback copy
`~/.luminos-backups/claude-desktop-1.52386.6-20261010/` (app files + config.json,
claude_desktop_config.json, ant-device-registry.json, bridge-state.json, Preferences, spaces.json).
`yay -S claude-desktop` → `2.31226.1-1`. Restarted via `scripts/luminos-claude-restart`; new PID
started 10:57:31, `[remote-tools-device] authenticated` 10:57:37, no Crashpad dumps,
`ant-device-registry.json` sha256 unchanged (`079c414f…`).
**11:58:36 the app quit cleanly** (normal onQuitCleanup incl. cowork-vm-shutdown, no crash dump) after ~1 h up; not running at 11:58:41. Not relaunched — unknown whether Shawn closed it. If it should be running: `scripts/luminos-claude-restart` detached, or the KDE menu.
**WAITING ON SHAWN (in the app):** (1) "Update Claude to move this project" banner gone? (2) @ in the
`luminos-os` project lists repo files? (3) asked to sign in again? If (3) yes → compare
`ant-device-registry.json` with the backup; a different key means old chats go `cls=foreign_device`
and folder grants reset (BUG-187) — report, don't fix.
**Rollback (only if it won't start / sign-in breaks):** `sudo cp -a` the two backed-up paths back,
`sudo chown -R root:root /usr/lib/claude-desktop`, `sudo chmod 4755 …/chrome-sandbox` (backup was
made as shawn, setuid lost), restart via the script, note in BUGS.md that pacman then says 2.31226.1.
**Not pushed** — `main` is ahead of origin on purpose; pushing is Shawn's call.

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
- (2026-10-10) DONE — see top. Old note: `ozark-warm-once` running. Check: `ssh … 'sudo journalctl -u ozark-warm-once -o cat'` — one
  `http=200 Ns` line per episode. Then `journalctl -u luminos-subtitle-warm` for the full sweep.

## Next steps (ordered)
1. Confirm all 20 Ozark eps show `2.srt` in the cache (the check script is in BUG-188's shape:
   `/var/lib/jellyfin/data/subtitles/<id[:2]>/<uuid>/2.srt`).
2. Shawn confirms on the Roku with S01E09 → E10 back-to-back.
3. **Shawn's call:** Option B (English `.en.srt` sidecars next to each MKV, survives cache wipes)
   and/or a Sonarr/Radarr **On-Import** hook so same-day imports are warm immediately.
4. ⚠️ STILL OPEN (blocked by permission 10-10): `sudo rm /usr/local/bin/ozark-warm-once` (transient unit disappears
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
**2026-10-10 windowstyle chat:** `src/kdecoration-chromeos/`, `packages/luminos-kdecoration-chromeos/`, `packages/kirigami-luminos/PKGBUILD`, `config/pacman-hooks/luminos-kirigami.hook`, `scripts/luminos-windowstyle{,-check}`, `tests/windowstyle/`, `docs/windowstyle/`, AGENTS §9, STATUS, DECISIONS (138), BUGS (193). System: packages luminos-kdecoration-chromeos, darkly, kirigami 6.30.0-1.1; `/etc/pacman.d/hooks/luminos-kirigami.hook`; `/usr/local/bin/luminos-windowstyle`; kwinrc/kdeglobals/darklyrc/luminos-chromeosrc.
**2026-10-10 multinet chat:** `server/DECISIONS.md` (DECISION 134), `server/STATUS.md`, `server/docs/multinet/{SPEC,BUILD_LOG}.md` (new), `HANDOFF.md`, `.notes.db`. Server: nothing persistent (wlan0 band switched for the test and restored).
**2026-10-10 11:11 chat:** `HANDOFF.md` only (read-only checks).
**2026-10-10:** package `claude-desktop` 1.52386.6-2 → 2.31226.1-1 (no /etc, no service); `LUMINOS_STATUS.md`, `docs/BUGS.md` (BUG-191), `LUMINOS_DECISIONS.md` (DECISION 133), `HANDOFF.md`, `.notes.db`, MemPalace drawer.
**2026-10-09:** `HANDOFF.md`, `.notes.db` (notes + brain log), MemPalace luminos-os/decisions drawer. No `/etc`, package or service change on Luminos.
**Repo, this turn:** `docs/BUGS.md` (BUG-188), `server/DECISIONS.md` (DECISION 132),
`server/STATUS.md`, `HANDOFF.md`, `.notes.db`.
**luminos-server (not the G14):** `/usr/local/bin/luminos-subtitle-warm`,
`/etc/systemd/system/luminos-subtitle-warm.{service,timer}` (enabled),
`/usr/local/bin/ozark-warm-once` (one-off). Jellyfin cache `/var/lib/jellyfin/data/subtitles` grows.
**G14 (BUG-188 turn):** nothing changed — no `/etc`, no package, no service. AGENTS.md §9 untouched.
Previous handoff (Claude Desktop, BUG-187): `git show HEAD:HANDOFF.md`.
