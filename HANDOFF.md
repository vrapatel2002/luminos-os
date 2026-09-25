# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-24 — Response 4

## Goal (the durable end objective)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**Claude Desktop is FIXED and documented (BUG-187). Closed out.** Sign-in works, the Cowork bridge
is green end-to-end, and two recurrence guards are in place. One cosmetic item left for Shawn.

### (a) SIGN-IN — FIXED. Root cause: `xdg-open` exits 0 without doing anything.
`shell.openExternal()` → `/usr/bin/xdg-open`. `detectDE()` sets `DE=kde` from
`XDG_CURRENT_DESKTOP=KDE`; `open_kde()` then branches on `KDE_SESSION_VERSION`, and when it is
**unset** runs `kfmclient exec` — removed in Plasma 6 — after which `kfmclient_fix_exit_code()`
**rewrites the 127 into 0**. xdg-open returns success having opened no browser, silently.
`XDG_CURRENT_DESKTOP=KDE` + `KDE_SESSION_VERSION` unset is the **poison pair**. It is not a missing
case; it is a case written to succeed.
**Proved with a control, not by reasoning:** a real launch writes `Started Google Chrome - Web
Browser` to the user journal. During the 32 s in which `main.log` recorded 22×
`[Auth] Using system browser for: /login/app-google-auth`, the journal has **no such line**. Then
traced directly with `sh -x /usr/bin/xdg-open`: unset → `kfmclient: command not found` → `rc 0`;
`KDE_SESSION_VERSION=6` → `kde-open` → Chrome opens.
**Source of the poison pair:** the `luminos-term` tmux server (socket `luminos`) held
`XDG_CURRENT_DESKTOP=KDE` and **no `KDE_*` at all** in its global environment, and every agent shell
under it inherits that. **Second time this shipped** — 2026-09-16 has the same root cause; that fix
repaired the instance and nothing repaired the source.
**Fixes, both applied and both tested:**
- `scripts/luminos-claude-restart` — reads the session env from `systemctl --user show-environment`
  and **refuses to start** if `KDE_SESSION_VERSION` is missing. It *asserts* rather than hardcodes,
  so the next variant fails loudly. Verified both ways: exit 0 recovering `6` from a shell where it
  was unset; exit 1 with a message when the value is stripped.
- `~/.config/luminos-spin/tmux.conf` pins `KDE_SESSION_VERSION=6` and `KDE_FULL_SESSION=true`; also
  applied live with `tmux -L luminos set-environment -g`.
⚠️ **Never restart Claude Desktop from a bare agent shell.** Use the script or the KDE menu.
⚠️ `/proc/<pid>/environ` of the app **cannot be read** — `kernel.yama.ptrace_scope=1` and it is not
our descendant. Assert the env **before** exec; there is no after.
⚠️ `pkill -f` is banned here — an agent shell's own command line matches its own pattern, and the
Cowork sandbox is a `qemu-system-x86_64`. Use `pkill -x claude-desktop`.

### (b) DEVICE BRIDGE — FIXED. The handed-over diagnosis was wrong; do not chase the enclave key.
- `[device-registry] enclave key unavailable — refusing to resolve row-PK` has been in the log since
  **2026-08-07 22:48**, the day the device was registered, and `main.log` holds **158
  `[remote-tools-device] authenticated` lines**, every one immediately *after* that same warning.
  `claude-native-binding.node` contains the literal **`hardwareKeyUnavailable:
  linux-not-yet-supported`**, and `app.asar` gates the software fallback on `lEr()`, compiled as
  **`function lEr(){return!1}`**. Hardware device keys are **not implemented on Linux** in 1.52386.6
  and the fallback is dead code. **Keyless is normal here.** No keyring, KWallet, TPM or `tss`-group
  change can affect it.
- **What actually broke:** `20:16:39 authenticated` → `20:16:59 served get_device_info` →
  **`20:17:29 pong timeout (1 consecutive) — resetting`** → every reconnect thereafter got
  `handshake timeout` (frame sent, server silent). Re-signing-in cleared it.
- **Verified green end-to-end:** `22:00:07 authenticated`, then `served get_device_info` at
  `22:05:53`, `22:13:16`, `22:15:02`. The cloud actually reached the laptop; a new Cowork chat works
  and can read files (Shawn confirmed).
- ⚠️ **Still unexplained, worth watching:** the app opens the DO bridge **twice in the same second**
  on every start (`init` → `close` → `init`), seen at both 20:16:38 and 22:00:05. Suspected wedge,
  **not proven** — do not write it up as the cause.

### (c) OLD COWORK CHATS — settled by experiment: they do NOT come back.
Signing in minted a **new device row**: `ant-device-registry.json` went `kl1:af780bec-…` →
`kl1:f27001c8-…` (account key unchanged). Shawn opened one old chat at 22:12:43 and it produced
`remote_cowork.bound_ledger_rehydrate_self_filtered {"sessionId":"cse_01Cak2Gby…",
"cls":"foreign_device"}` with `scheduledOrDispatch:false` — **filtered out, no link offered**. The
chat created at 22:05 got no such line and works. Folder grants are per-row and do not carry over,
so a new chat must re-request access to `~/luminos-os`.
⚠️ **`"verdict":"keyless"` in `late_link_offer_verdict` is NOT an error** — it appears on the working
sessions too (20:45, 22:00, 22:05). The only line that ever distinguished a broken session is
`cls":"foreign_device"`. Misreading `keyless` as a fault produced the original wrong diagnosis.


## State — what is DONE
- Backup before anything: `~/.config/Claude.bak-2026-09-24-2148` (14 G). Nothing deleted or moved.
- Install: `aur/claude-desktop 1.52386.6-2`, `/usr/bin/claude-desktop`,
  `/usr/share/applications/com.anthropic.Claude.desktop`.
- **Checked and FINE — not the problem, do not re-investigate:** the `claude://` handler
  (`xdg-mime query default x-scheme-handler/claude` → `com.anthropic.Claude.desktop`; the entry
  carries `MimeType=x-scheme-handler/claude;`; `~/.config/mimeapps.list` agrees;
  `claude-code-url-handler.desktop` only claims `claude-cli://` and does not collide) ·
  gnome-keyring (owns `org.freedesktop.secrets`, `Login` collection **unlocked**, holds
  `Claude Safe Storage`; ksecretd only has `org.kde.secretservicecompat`;
  `--password-store=gnome-libsecret` still set in `~/.config/claude-desktop-flags.conf`) ·
  the TPM and the `tss` group.
- Written: `docs/BUGS.md` **BUG-187**, `LUMINOS_STATUS.md` (header + a new component row),
  `scripts/luminos-claude-restart`, `~/.config/luminos-spin/tmux.conf`,
  `luminos-notes.sh add [BUG]`, `luminos-brain log`.
- ⚠️ **A secret was printed to a terminal this turn.** `secret-tool search --all application Claude`
  echoes the *secret value* of `Claude Safe Storage`, not just metadata. It is in that session's
  scrollback only — never written to a file, a note or a commit. Next time pipe through
  `grep -v '^secret'`.
- ⚠️ **MCP was not available in this session.** `mempalace_search` and `code-review-graph` are
  Desktop/Cowork-side and this was a terminal CLI session, so AGENTS.md Rules 7/8 fell back to
  `luminos-notes.sh search` plus reading the code directly. No Go or Python was edited, so the
  CodeGraph requirement did not bite.


## Next steps (ordered)
1. **Shawn's one remaining item (cosmetic, not urgent):** delete the stale
   **"Claude Desktop (Linux)"** device added 2026-08-07, from claude.ai in a browser, the Windows
   app, or **now possibly the desktop app's own Settings → Cowork** — it used to refuse because that
   row was "This computer", and after the rotation it no longer is. Deleting it cannot touch the
   working row (different row id; `ant-device-registry.json` maps the account to the current row
   only).
2. **Push when Shawn is ready.** `main` is **2 commits ahead of origin** and was left unpushed on
   purpose (Shawn's call, 2026-09-24): `80e0497d` (BUG-187, this work) and `f4d89003`
   ("docs(agents): §9 Vela row"), which was already unpushed before this session. `git push origin
   main` sends both. Nothing else is needed to close this out.
3. Parked wallpaper work resumes — see "Parked" below. Next action there is the click probe.


## Key decisions & constraints
- **AGENTS.md §0.2 / Rule 12 / §16: "no changes" scopes to code, config and system state.**
  `HANDOFF.md` and the §13 doc triggers are written on **every** turn, investigation turns included.
- **Never restart Claude Desktop from a bare agent shell.** Use the relaunch helper, or launch it
  from the KDE menu. A bare shell costs you the sign-in browser and gives no error.
- **A warning that has been in the log for six weeks is not a root cause.** The enclave line was
  read as the cause of a failure it long predates. Check the *first* occurrence against the *last
  known-good* moment before believing any log line.
- **`pkill -f` is banned on this box for anything matching a broad word** — Cowork's sandbox is a
  `qemu-system-x86_64`, and an agent shell's own command line can match its own pattern. Use
  `pkill -x <exact-name>` or a PID.
- ⚠️ **A secret was printed to a terminal this turn.** `secret-tool search --all application Claude`
  echoes the *secret value* of `Claude Safe Storage`, not just the metadata. It is in this session's
  scrollback only — it was never written to a file, a note or a commit. Use
  `secret-tool search --all ... | grep -v '^secret'` next time.

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
**Repo, this turn:** `docs/BUGS.md` (BUG-187), `LUMINOS_STATUS.md`, `HANDOFF.md`,
`scripts/luminos-claude-restart` (new), `.notes.db`.
**Outside the repo:** `~/.config/luminos-spin/tmux.conf` (two `set-environment -g` lines).
System state: Claude Desktop stopped and relaunched with a real session environment. **No `/etc`
change, no sudo, no package change** — so AGENTS.md §9 is untouched.
**Read this turn:** `~/.config/Claude/logs/{main.log,main1.log,claude.ai-web.log}` (binary — always
`grep -a`), `~/.config/Claude/{ant-device-registry.json,bridge-state.json}`,
`/usr/lib/claude-desktop/resources/app.asar` and its `claude-native` binding, `/usr/bin/xdg-open`,
`/usr/local/bin/luminos-caelestia-plasma`.
